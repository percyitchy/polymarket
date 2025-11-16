"""
Wallet Analysis Worker with Queue System
Handles wallet analysis with retry logic and exponential backoff
"""

import os
import time
import random
import logging
import asyncio
import threading
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests
import urllib3
from requests.exceptions import RequestException, Timeout, ConnectionError
from dotenv import load_dotenv

# Disable SSL warnings for proxy connections
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from db import PolymarketDB
from proxy_manager import ProxyManager

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Global semaphore to limit concurrent HTTP requests
HTTP_SEMAPHORE = threading.Semaphore(6)  # Max 6 concurrent API requests

# Filtering criteria constants
WIN_RATE_THRESHOLD = float(os.getenv("WIN_RATE_THRESHOLD", "0.65"))  # Minimum win rate to accept wallet (65%, configurable via .env)
MAX_DAILY_FREQUENCY = float(os.getenv("MAX_DAILY_FREQUENCY", "35.0"))  # Maximum daily trading frequency (configurable via .env)
MIN_TRADES = 6  # Minimum number of trades required
MAX_CLOSED_POSITIONS = int(os.getenv("MAX_CLOSED_POSITIONS", "250"))  # Maximum closed positions to analyze (last 250 or 3 months, whichever is more)
ANALYSIS_LOOKBACK_DAYS = int(os.getenv("ANALYSIS_LOOKBACK_DAYS", "90"))  # Days to look back for market analysis (default 90, configurable via .env)
INACTIVITY_DAYS = int(os.getenv("INACTIVITY_DAYS", "150"))  # Days of inactivity threshold (default 150, configurable via .env)

# New quality thresholds for wallet filtering
MINIMUM_ROI = float(os.getenv("MINIMUM_ROI", "0.0025"))  # Minimum ROI = 0.25% (Total PnL / Total Volume)
MINIMUM_AVG_PNL = float(os.getenv("MINIMUM_AVG_PNL", "50.0"))  # Minimum average PnL per market, $50
MINIMUM_VOLUME = float(os.getenv("MINIMUM_VOLUME", "25000.0"))  # Minimum total trading volume, $25k
MINIMUM_MARKETS = int(os.getenv("MINIMUM_MARKETS", "12"))  # Minimum number of closed markets in analysis window
MINIMUM_AVG_STAKE = float(os.getenv("MINIMUM_AVG_STAKE", "100.0"))  # Minimum average stake per market, $100

# Analysis result categories - all possible values for analysis_result field
# This ensures consistent categorization and helps with Filter Breakdown statistics
#
# Complete list of analysis_result values:
# - "accepted" - Wallet meets all criteria (MIN_TRADES+, WIN_RATE_THRESHOLD+, quality thresholds+)
# - "rejected_low_trades" - Wallet has < MIN_TRADES trades
# - "rejected_low_winrate" - Wallet has < WIN_RATE_THRESHOLD win rate
# - "rejected_high_frequency" - Wallet has > MAX_DAILY_FREQUENCY daily trading frequency
# - "rejected_inactive" - Wallet's last_trade_at is older than INACTIVITY_DAYS
# - "rejected_no_stats" - No closed positions data available from API
# - "rejected_api_error" - HTTP/API errors after retries (timeout, connection error, etc.)
# - "rejected_invalid_data" - Invalid/unparseable data (None win_rate, etc.)
# - "rejected_low_markets" - Wallet has < MINIMUM_MARKETS closed markets in analysis window
# - "rejected_low_volume" - Wallet has < MINIMUM_VOLUME total trading volume
# - "rejected_low_roi" - Wallet has < MINIMUM_ROI ROI
# - "rejected_low_avg_pnl" - Wallet has < MINIMUM_AVG_PNL average PnL per market
# - "rejected_low_avg_stake" - Wallet has < MINIMUM_AVG_STAKE average stake per market
# - "rejected_legacy" - Old format values from previous code versions (mapped during aggregation)
#
# Note: Any values NOT in this list that exist in the database are automatically
# mapped to "rejected_legacy" during Filter Breakdown aggregation in daily_wallet_analysis.py.
# The "Legacy other" category represents the aggregate of all old/unmapped values.
#
ANALYSIS_RESULT_ACCEPTED = "accepted"
ANALYSIS_RESULT_REJECTED_LOW_TRADES = "rejected_low_trades"
ANALYSIS_RESULT_REJECTED_LOW_WINRATE = "rejected_low_winrate"
ANALYSIS_RESULT_REJECTED_HIGH_FREQUENCY = "rejected_high_frequency"
ANALYSIS_RESULT_REJECTED_INACTIVE = "rejected_inactive"
ANALYSIS_RESULT_REJECTED_NO_STATS = "rejected_no_stats"  # No data available from API
ANALYSIS_RESULT_REJECTED_API_ERROR = "rejected_api_error"  # HTTP/API errors after retries
ANALYSIS_RESULT_REJECTED_INVALID_DATA = "rejected_invalid_data"  # Invalid/unparseable data
ANALYSIS_RESULT_REJECTED_LOW_MARKETS = "rejected_low_markets"  # < MINIMUM_MARKETS closed markets
ANALYSIS_RESULT_REJECTED_LOW_VOLUME = "rejected_low_volume"  # < MINIMUM_VOLUME total volume
ANALYSIS_RESULT_REJECTED_LOW_ROI = "rejected_low_roi"  # < MINIMUM_ROI ROI
ANALYSIS_RESULT_REJECTED_LOW_AVG_PNL = "rejected_low_avg_pnl"  # < MINIMUM_AVG_PNL avg PnL per market
ANALYSIS_RESULT_REJECTED_LOW_AVG_STAKE = "rejected_low_avg_stake"  # < MINIMUM_AVG_STAKE avg stake per market
ANALYSIS_RESULT_REJECTED_LEGACY = "rejected_legacy"  # Old format values from previous versions

@dataclass
class AnalysisConfig:
    """Configuration for wallet analysis"""
    api_max_workers: int = 4  # Reduced from 10 to avoid rate limiting
    api_timeout_sec: int = 10  # Reduced from 20
    api_retry_max: int = 6
    api_retry_base: float = 1.2
    analysis_ttl_min: int = 180
    retry_jitter: float = 0.1

class WalletAnalyzer:
    """Wallet analysis worker with queue system"""
    
    def __init__(self, db: PolymarketDB, config: AnalysisConfig = None):
        self.db = db
        self.config = config or AnalysisConfig()
        
        # Polymarket Data API endpoints
        self.data_api = "https://data-api.polymarket.com"
        self.trades_endpoint = f"{self.data_api}/trades"
        self.closed_positions_endpoint = f"{self.data_api}/closed-positions"
        self.traded_endpoint = f"{self.data_api}/traded"
        
        # Headers for API requests
        self.headers = {
            "User-Agent": "PolymarketNotifier/1.0 (+https://polymarket.com)"
        }
        
        # Initialize proxy manager (optional)
        self.proxy_manager = ProxyManager()
        
        # Thread-local storage for requests.Session
        self.local = threading.local()
        
        # Worker state
        self.running = False
        self.workers = []
        self.stop_event = threading.Event()
    
    def _get_session(self):
        """Get or create thread-local requests.Session"""
        if not hasattr(self.local, "session"):
            self.local.session = requests.Session()
        return self.local.session
    
    def start_workers(self):
        """Start analysis workers"""
        if self.running:
            logger.warning("Workers already running")
            return
        
        self.running = True
        self.stop_event.clear()
        
        # Start worker threads
        for i in range(self.config.api_max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"WalletAnalyzer-{i+1}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"Started {self.config.api_max_workers} wallet analysis workers")
    
    def stop_workers(self):
        """Stop analysis workers"""
        if not self.running:
            return
        
        logger.info("Stopping wallet analysis workers...")
        self.running = False
        self.stop_event.set()
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=5)
        
        self.workers.clear()
        logger.info("Wallet analysis workers stopped")
    
    def _worker_loop(self):
        """Main worker loop"""
        worker_name = threading.current_thread().name
        logger.info(f"{worker_name} started")
        last_idle_log = time.time()
        
        while self.running and not self.stop_event.is_set():
            try:
                # Get pending jobs
                batch_size = 10  # Get more jobs to increase chances of claiming one
                jobs = self.db.get_pending_jobs(limit=batch_size)
                
                # Log how many jobs were fetched
                logger.info(f"{worker_name} fetched {len(jobs)} jobs from get_pending_jobs(limit={batch_size})")
                
                if not jobs:
                    # No jobs available, wait a bit
                    # Log every 5 minutes that we're idle (for visibility)
                    now = time.time()
                    if now - last_idle_log > 300:
                        # Check queue size using stats for better accuracy
                        queue_stats = self.db.get_queue_stats()
                        pending_count = queue_stats.get('pending_jobs', 0)
                        ready_count = queue_stats.get('ready_jobs', 0)
                        total_count = queue_stats.get('total_jobs', 0)
                        logger.info(f"{worker_name} idle - no pending jobs (queue: {pending_count} pending, {ready_count} ready, {total_count} total)")
                        last_idle_log = now
                    time.sleep(1)
                    continue
                
                # Try to claim a job atomically
                job = None
                for candidate_job in jobs:
                    if self.db.claim_job(candidate_job['id']):
                        job = candidate_job
                        break
                
                if not job:
                    # No job was available for claiming, wait a short moment to reduce contention
                    logger.debug(f"{worker_name} could not claim any job from {len(jobs)} candidates (contention)")
                    time.sleep(0.1)
                    continue
                
                logger.info(f"{worker_name} start processing job_id={job['id']} address={job['address'][:12]}...")
                
                # Process the job with timeout monitoring
                start_time = time.time()
                max_analysis_time = self.config.api_timeout_sec * 5  # 5x API timeout for full analysis
                success = False
                
                try:
                    # Process the job
                    success = self._analyze_wallet(job)
                    elapsed = time.time() - start_time
                    
                    if elapsed > max_analysis_time:
                        logger.warning(f"{worker_name} job {job['id']} took {elapsed:.2f}s (exceeded {max_analysis_time}s)")
                    else:
                        logger.debug(f"{worker_name} job {job['id']} analysis took {elapsed:.2f}s")
                    
                except Exception as e:
                    elapsed = time.time() - start_time
                    logger.error(f"{worker_name} job {job['id']} error after {elapsed:.2f}s: {e}", exc_info=True)
                    # Error handling is done in _analyze_wallet via _handle_analysis_error
                    success = False
                
                if success:
                    # Job completed successfully - check if DB update succeeded
                    elapsed = time.time() - start_time
                    if self.db.complete_job(job['id']):
                        logger.info(f"{worker_name} completed job {job['id']} for {job['address']} in {elapsed:.2f}s")
                    else:
                        logger.error(f"{worker_name} failed to mark job {job['id']} as completed in DB (database locked?)")
                else:
                    # Job failed, will be retried later (already handled by _handle_analysis_error)
                    logger.warning(f"{worker_name} failed job {job['id']} for {job['address']}")
                
                # Small delay between jobs (tuned for higher throughput)
                time.sleep(0.05)
                
            except Exception as e:
                logger.error(f"{worker_name} error in worker loop: {e}", exc_info=True)
                time.sleep(1)
        
        logger.info(f"{worker_name} stopped")
    
    def _analyze_wallet(self, job: Dict[str, Any]) -> bool:
        """Analyze a single wallet with detailed step-by-step logging"""
        address = job['address']
        job_id = job['id']
        
        start = time.time()
        t0 = start
        
        def log_step(step: str):
            """Helper to log each step with timing"""
            nonlocal t0
            elapsed_step = time.time() - t0
            elapsed_total = time.time() - start
            logger.debug(f"Job {job_id} {step} took {elapsed_step:.2f}s (total {elapsed_total:.2f}s)")
            t0 = time.time()
        
        try:
            log_step("start")
            
            # Check cache first
            cached = self.db.get_cached_analysis(address)
            log_step("cache_lookup")
            last_trade_at = None  # Initialize last_trade_at
            
            if cached:
                logger.info(f"Using cached analysis for {address}")
                traded = cached['traded_total']
                win_rate = cached['win_rate']
                pnl_total = cached['realized_pnl_total']
                daily_freq = cached['daily_trading_frequency']
                analysis_result = cached['analysis_result']
                last_trade_at = cached.get('last_trade_at')
                
                # If cached result is "accepted", ensure wallet is saved to wallets table
                if analysis_result == "accepted":
                    # Check if wallet already exists in wallets table
                    existing_wallet = self.db.get_wallet(address)
                    if not existing_wallet:
                        # Wallet was accepted but not saved - save it now
                        logger.info(f"Wallet {address} was cached as accepted but not in wallets table, saving now...")
                        success = self.db.upsert_wallet(
                            address, job.get('display', address), traded, win_rate,
                            pnl_total, daily_freq, job.get('source', 'queue'), last_trade_at
                        )
                        if success:
                            logger.info(f"Successfully saved cached accepted wallet {address} to wallets table")
                        else:
                            logger.error(f"Failed to save cached accepted wallet {address} to wallets table")
                    else:
                        logger.debug(f"Wallet {address} already exists in wallets table")
                
                # Return True for cached results (successfully processed, even if filtered out)
                return True
            else:
                # Get wallet metrics from API
                try:
                    traded = self._get_total_traded(address)
                    log_step("get_total_traded")
                except Exception as e:
                    logger.error(f"API error getting traded total for {address}: {e}")
                    # Cache API error result
                    analysis_result = ANALYSIS_RESULT_REJECTED_API_ERROR
                    self.db.cache_analysis_result(
                        address=address,
                        traded_total=0,
                        win_rate=0.0,
                        realized_pnl_total=0.0,
                        daily_frequency=0.0,
                        analysis_result=analysis_result,
                        last_trade_at=None,
                        source=job.get("source", "queue")
                    )
                    return True  # Successfully handled (filtered out due to API error)
                
                # Fast filter: if traded below threshold, short-circuit without heavy calls
                if traded < MIN_TRADES:
                    logger.info(f"Fast-skip {address}: traded={traded} (<{MIN_TRADES})")
                    win_rate = 0.0
                    pnl_total = 0.0
                    daily_freq = 0.0
                    last_trade_at = None
                    # Cache negative result to avoid repeat work
                    analysis_result = ANALYSIS_RESULT_REJECTED_LOW_TRADES
                    self.db.cache_analysis_result(
                        address=address,
                        traded_total=traded,
                        win_rate=win_rate,
                        realized_pnl_total=pnl_total,
                        daily_frequency=daily_freq,
                        analysis_result=analysis_result,
                        last_trade_at=last_trade_at,
                        source=job.get("source", "queue")
                    )
                    return True
                
                try:
                    closed_positions = self._get_closed_positions(address)
                    log_step("get_closed_positions")
                except Exception as e:
                    logger.error(f"API error getting closed positions for {address}: {e}")
                    # Cache API error result
                    analysis_result = ANALYSIS_RESULT_REJECTED_API_ERROR
                    self.db.cache_analysis_result(
                        address=address,
                        traded_total=traded,
                        win_rate=0.0,
                        realized_pnl_total=0.0,
                        daily_frequency=0.0,
                        analysis_result=analysis_result,
                        last_trade_at=None,
                        source=job.get("source", "queue")
                    )
                    return True  # Successfully handled (filtered out due to API error)
                
                win_rate, pnl_total = self._compute_win_rate_and_pnl(closed_positions)
                
                # Check if we have valid data for analysis
                if not closed_positions or len(closed_positions) == 0:
                    logger.warning(f"No closed positions data for {address}")
                    analysis_result = ANALYSIS_RESULT_REJECTED_NO_STATS
                    self.db.cache_analysis_result(
                        address=address,
                        traded_total=traded,
                        win_rate=0.0,
                        realized_pnl_total=0.0,
                        daily_frequency=0.0,
                        analysis_result=analysis_result,
                        last_trade_at=None,
                        source=job.get("source", "queue")
                    )
                    return True  # Successfully handled (no stats available)
                
                try:
                    daily_freq = self._get_daily_trading_frequency(address)
                    log_step("get_daily_trading_frequency")
                except Exception as e:
                    logger.warning(f"API error getting daily frequency for {address}: {e}, continuing with None")
                    daily_freq = None  # Continue analysis without daily frequency
                
                # Get last trade timestamp
                last_trade_at = self._get_last_trade_timestamp(address)
                log_step("get_last_trade_timestamp")
                
                # Check activity filter: only reject if last_trade_at is known and older than threshold
                if last_trade_at is None:
                    # No last_trade_at data - don't reject based on activity, use other filters
                    logger.debug(f"[Activity] {address}: last_trade_at missing, using other filters")
                else:
                    # We have last_trade_at - check if wallet is inactive
                    try:
                        last_trade_dt = datetime.fromisoformat(last_trade_at.replace("Z", "+00:00"))
                        inactivity_threshold = datetime.now(timezone.utc) - timedelta(days=INACTIVITY_DAYS)
                        
                        if last_trade_dt < inactivity_threshold:
                            # Wallet is inactive (older than threshold)
                            logger.info(f"[Activity] {address}: last_trade_at={last_trade_dt.strftime('%Y-%m-%d')}, inactive (older than {INACTIVITY_DAYS}d)")
                            # Cache negative result
                            analysis_result = ANALYSIS_RESULT_REJECTED_INACTIVE
                            self.db.cache_analysis_result(
                                address=address,
                                traded_total=traded,
                                win_rate=win_rate,
                                realized_pnl_total=pnl_total,
                                daily_frequency=daily_freq,
                                analysis_result=analysis_result,
                                last_trade_at=last_trade_at,
                                source=job.get("source", "queue")
                            )
                            return True  # Successfully filtered out
                        else:
                            # Wallet is active
                            logger.debug(f"[Activity] {address}: last_trade_at={last_trade_dt.strftime('%Y-%m-%d')}, active")
                    except Exception as e:
                        logger.debug(f"Error parsing last_trade_at for {address}: {e}")
                        # Continue if we can't parse timestamp - don't reject based on activity
                        pass
                
                # Check daily trading frequency filter
                if daily_freq is not None and daily_freq > MAX_DAILY_FREQUENCY:
                    logger.info(f"Skipping {address}: daily frequency {daily_freq:.2f} > {MAX_DAILY_FREQUENCY}")
                    analysis_result = ANALYSIS_RESULT_REJECTED_HIGH_FREQUENCY
                    self.db.cache_analysis_result(
                        address=address,
                        traded_total=traded,
                        win_rate=win_rate,
                        realized_pnl_total=pnl_total,
                        daily_frequency=daily_freq,
                        analysis_result=analysis_result,
                        last_trade_at=last_trade_at,
                        source=job.get("source", "queue")
                    )
                    return True  # Successfully filtered out
                
                # Calculate new quality metrics from filtered closed positions
                num_markets = len(closed_positions)
                total_volume, avg_stake = self._compute_volume_and_stake(closed_positions)
                
                # Calculate ROI and average PnL per market
                roi = (pnl_total / total_volume) if total_volume > 0 else 0.0
                avg_pnl_per_market = (pnl_total / num_markets) if num_markets > 0 else 0.0
                
                # Apply new quality filters (after old filters)
                # Check minimum markets
                if num_markets < MINIMUM_MARKETS:
                    logger.info(f"[Quality] Rejecting {address}: markets {num_markets} < MINIMUM_MARKETS={MINIMUM_MARKETS}")
                    analysis_result = ANALYSIS_RESULT_REJECTED_LOW_MARKETS
                    self.db.cache_analysis_result(
                        address=address,
                        traded_total=traded,
                        win_rate=win_rate,
                        realized_pnl_total=pnl_total,
                        daily_frequency=daily_freq,
                        analysis_result=analysis_result,
                        last_trade_at=last_trade_at,
                        source=job.get("source", "queue")
                    )
                    return True  # Successfully filtered out
                
                # Check minimum volume
                if total_volume < MINIMUM_VOLUME:
                    logger.info(f"[Quality] Rejecting {address}: volume ${total_volume:.2f} < MINIMUM_VOLUME=${MINIMUM_VOLUME:.2f}")
                    analysis_result = ANALYSIS_RESULT_REJECTED_LOW_VOLUME
                    self.db.cache_analysis_result(
                        address=address,
                        traded_total=traded,
                        win_rate=win_rate,
                        realized_pnl_total=pnl_total,
                        daily_frequency=daily_freq,
                        analysis_result=analysis_result,
                        last_trade_at=last_trade_at,
                        source=job.get("source", "queue")
                    )
                    return True  # Successfully filtered out
                
                # Check minimum ROI
                if roi < MINIMUM_ROI:
                    logger.info(f"[Quality] Rejecting {address}: ROI {roi:.4f} ({roi*100:.2f}%) < MINIMUM_ROI={MINIMUM_ROI:.4f} ({MINIMUM_ROI*100:.2f}%)")
                    analysis_result = ANALYSIS_RESULT_REJECTED_LOW_ROI
                    self.db.cache_analysis_result(
                        address=address,
                        traded_total=traded,
                        win_rate=win_rate,
                        realized_pnl_total=pnl_total,
                        daily_frequency=daily_freq,
                        analysis_result=analysis_result,
                        last_trade_at=last_trade_at,
                        source=job.get("source", "queue")
                    )
                    return True  # Successfully filtered out
                
                # Check minimum average PnL per market
                if avg_pnl_per_market < MINIMUM_AVG_PNL:
                    logger.info(f"[Quality] Rejecting {address}: avg_pnl_per_market ${avg_pnl_per_market:.2f} < MINIMUM_AVG_PNL=${MINIMUM_AVG_PNL:.2f}")
                    analysis_result = ANALYSIS_RESULT_REJECTED_LOW_AVG_PNL
                    self.db.cache_analysis_result(
                        address=address,
                        traded_total=traded,
                        win_rate=win_rate,
                        realized_pnl_total=pnl_total,
                        daily_frequency=daily_freq,
                        analysis_result=analysis_result,
                        last_trade_at=last_trade_at,
                        source=job.get("source", "queue")
                    )
                    return True  # Successfully filtered out
                
                # Check minimum average stake
                if avg_stake < MINIMUM_AVG_STAKE:
                    logger.info(f"[Quality] Rejecting {address}: avg_stake ${avg_stake:.2f} < MINIMUM_AVG_STAKE=${MINIMUM_AVG_STAKE:.2f}")
                    analysis_result = ANALYSIS_RESULT_REJECTED_LOW_AVG_STAKE
                    self.db.cache_analysis_result(
                        address=address,
                        traded_total=traded,
                        win_rate=win_rate,
                        realized_pnl_total=pnl_total,
                        daily_frequency=daily_freq,
                        analysis_result=analysis_result,
                        last_trade_at=last_trade_at,
                        source=job.get("source", "queue")
                    )
                    return True  # Successfully filtered out
                
            # Debug log before final filter
            # Format daily_freq safely (can be None)
            freq_str = f"{daily_freq:.2f}" if daily_freq is not None else "None"
            
            # Calculate quality metrics if we have closed_positions (for logging)
            # Note: closed_positions may not be defined in all code paths (e.g., cached results)
            try:
                if 'closed_positions' in locals() and closed_positions and len(closed_positions) > 0:
                    num_markets = len(closed_positions)
                    total_volume, avg_stake = self._compute_volume_and_stake(closed_positions)
                    roi = (pnl_total / total_volume) if total_volume > 0 else 0.0
                    avg_pnl_per_market = (pnl_total / num_markets) if num_markets > 0 else 0.0
                    logger.debug(
                        f"Analyze wallet {address}: traded={traded}, win_rate={win_rate:.3f}, "
                        f"pnl={pnl_total:.2f}, daily_freq={freq_str}, "
                        f"markets={num_markets}, volume=${total_volume:.2f}, "
                        f"roi={roi:.4f} ({roi*100:.2f}%), avg_pnl=${avg_pnl_per_market:.2f}, "
                        f"avg_stake=${avg_stake:.2f}, last_trade_at={last_trade_at}"
                    )
                else:
                    logger.debug(
                        f"Analyze wallet {address}: traded={traded}, win_rate={win_rate:.3f}, "
                        f"pnl={pnl_total:.2f}, daily_freq={freq_str}, "
                        f"last_trade_at={last_trade_at}"
                    )
            except (NameError, UnboundLocalError):
                # closed_positions not defined in this code path (e.g., cached result)
                logger.debug(
                    f"Analyze wallet {address}: traded={traded}, win_rate={win_rate:.3f}, "
                    f"pnl={pnl_total:.2f}, daily_freq={freq_str}, "
                    f"last_trade_at={last_trade_at}"
                )
            
            # Validate data before final decision
            if win_rate is None or not isinstance(win_rate, (int, float)):
                logger.warning(f"Invalid win_rate for {address}: {win_rate}")
                analysis_result = ANALYSIS_RESULT_REJECTED_INVALID_DATA
            elif traded >= MIN_TRADES and win_rate >= WIN_RATE_THRESHOLD:
                # All filters passed (old + new quality filters)
                analysis_result = ANALYSIS_RESULT_ACCEPTED
            else:
                analysis_result = ANALYSIS_RESULT_REJECTED_LOW_WINRATE
            
            # Cache the result (always cache, even if accepted)
            self.db.cache_analysis_result(
                address=address,
                traded_total=traded,
                win_rate=win_rate,
                realized_pnl_total=pnl_total,
                daily_frequency=daily_freq,
                analysis_result=analysis_result,
                last_trade_at=last_trade_at,
                source=job.get("source", "queue")
            )
            
            # Apply criteria: traded >= MIN_TRADES and win_rate >= WIN_RATE_THRESHOLD
            # Note: New quality filters (markets, volume, ROI, avg_pnl, avg_stake) are already checked above
            if traded >= MIN_TRADES and win_rate >= WIN_RATE_THRESHOLD:
                # Store wallet in database with last_trade_at
                success = self.db.upsert_wallet(
                    address, job.get('display', address), traded, win_rate, 
                    pnl_total, daily_freq, job.get('source', 'queue'), last_trade_at
                )
                
                if success:
                    # Log acceptance with quality metrics if available
                    # Try to get quality metrics from closed_positions if they were calculated
                    try:
                        # Check if we're in the branch where closed_positions exist
                        if 'closed_positions' in locals() and closed_positions and len(closed_positions) > 0:
                            num_markets = len(closed_positions)
                            total_volume, avg_stake = self._compute_volume_and_stake(closed_positions)
                            roi = (pnl_total / total_volume) if total_volume > 0 else 0.0
                            avg_pnl_per_market = (pnl_total / num_markets) if num_markets > 0 else 0.0
                            logger.info(
                                f"[FILTER] ✅ ACCEPTED {address}: {traded} trades, {win_rate:.2%} win rate, "
                                f"${pnl_total:.2f} PnL, {num_markets} markets, ${total_volume:.2f} volume, "
                                f"{roi*100:.2f}% ROI, ${avg_pnl_per_market:.2f} avg PnL, ${avg_stake:.2f} avg stake"
                            )
                        else:
                            logger.info(f"[FILTER] ✅ ACCEPTED {address}: {traded} trades, {win_rate:.2%} win rate, {pnl_total:.2f} PnL")
                    except Exception as e:
                        # Fallback if there's any error calculating metrics
                        logger.info(f"[FILTER] ✅ ACCEPTED {address}: {traded} trades, {win_rate:.2%} win rate, {pnl_total:.2f} PnL")
                    return True
                else:
                    logger.error(f"[FILTER] ❌ FAILED to save wallet {address} to database")
                    return False
            else:
                logger.info(f"[FILTER] ⏭️  REJECTED {address}: {traded} trades, {win_rate:.2%} win rate (criteria: >={MIN_TRADES} trades, >={WIN_RATE_THRESHOLD:.0%} win rate)")
                return True  # Consider this a successful analysis (wallet filtered out)
                
        except Exception as e:
            logger.error(f"Error analyzing wallet {address}: {e}")
            # Cache API error result before handling retry logic
            try:
                analysis_result = ANALYSIS_RESULT_REJECTED_API_ERROR
                self.db.cache_analysis_result(
                    address=address,
                    traded_total=0,
                    win_rate=0.0,
                    realized_pnl_total=0.0,
                    daily_frequency=0.0,
                    analysis_result=analysis_result,
                    last_trade_at=None,
                    source=job.get("source", "queue")
                )
            except Exception as cache_error:
                logger.error(f"Failed to cache error result for {address}: {cache_error}")
            
            self._handle_analysis_error(job_id, str(e))
            return False
    
    def _handle_analysis_error(self, job_id: int, error_message: str):
        """Handle analysis error with retry logic"""
        try:
            # Get current job info directly by ID
            job = self.db.get_job_by_id(job_id)
            
            if not job:
                logger.error(f"Job {job_id} not found for error handling")
                # Reset job to pending if it exists but wasn't found (might be stuck in processing)
                self.db.update_job_status(job_id, 'pending', error_message)
                return
            
            retry_count = job.get('retry_count', 0)
            max_retries = job.get('max_retries', self.config.api_retry_max)
            
            if retry_count >= max_retries:
                logger.error(f"Job {job_id} exceeded max retries ({max_retries}), marking as failed")
                self.db.update_job_status(job_id, 'failed', error_message)
                return
            
            # Calculate next retry time with exponential backoff + jitter
            base_delay = self.config.api_retry_base ** retry_count
            jitter = random.uniform(0, self.config.retry_jitter * base_delay)
            delay_seconds = base_delay + jitter
            
            # Check if it's a 429 error and extract Retry-After
            if "429" in error_message or "rate limit" in error_message.lower():
                # Try to extract Retry-After header if available
                retry_after_match = None
                if hasattr(error_message, 'response') and hasattr(error_message.response, 'headers'):
                    retry_after = error_message.response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            retry_after_seconds = int(retry_after)
                            delay_seconds = max(delay_seconds, retry_after_seconds)
                        except ValueError:
                            pass
            
            # Limit maximum retry delay to 120 seconds (2 minutes)
            delay_seconds = min(delay_seconds, 120)
            
            next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
            next_retry_iso = next_retry_at.isoformat()
            
            # Update job with retry info
            self.db.increment_job_retry(job_id, next_retry_iso, error_message)
            
            logger.warning(
                f"Job {job_id} error='{error_message[:100]}' retry_count={retry_count + 1}/{max_retries} "
                f"next_retry_at={next_retry_iso} (delay={delay_seconds:.1f}s)"
            )
            
        except Exception as e:
            logger.error(f"Error handling analysis error for job {job_id}: {e}")
    
    def _http_get_resilient(self, url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """Make HTTP GET request with resilient retry logic and 429 handling"""
        max_retries = 1  # Reduced from 3 to speed up processing
        base_delay = 1.0
        timeout = self.config.api_timeout_sec
        
        for attempt in range(max_retries):
            try:
                # Use semaphore to limit concurrent requests
                with HTTP_SEMAPHORE:
                    # Get proxy if available
                    proxy = self.proxy_manager.get_proxy(rotate=True) if self.proxy_manager.proxy_enabled else None
                    
                    # Add proxy-specific headers for HTTP proxies with IP rotation
                    headers = self.headers.copy()
                    if proxy:
                        headers['Connection'] = 'close'  # Avoid connection reuse issues with rotating proxies
                        headers['Proxy-Connection'] = 'close'
                    
                    # Use thread-local session for connection reuse
                    session = self._get_session()
                    
                    # Use verify=False for proxies that might have SSL issues
                    response = session.get(url, params=params, headers=headers, timeout=timeout, proxies=proxy, verify=False)
                
                # Handle 429 rate limiting
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            delay = int(retry_after)
                            # If Retry-After is 0 or too small, use minimum delay
                            if delay <= 0:
                                delay = 5  # Minimum 5 seconds even if server says 0
                            logger.warning(f"Rate limited (429), waiting {delay}s as requested by server")
                            time.sleep(delay)
                            # Rotate proxy on retry if available
                            if self.proxy_manager.proxy_enabled:
                                proxy = self.proxy_manager.get_proxy(rotate=True)
                            continue
                        except ValueError:
                            pass
                    
                    # Fallback exponential backoff (minimum 5 seconds)
                    delay = max(5, base_delay * (2 ** attempt))
                    logger.warning(f"Rate limited (429), waiting {delay:.1f}s (attempt {attempt + 1})")
                    time.sleep(delay)
                    continue
                
                # Handle other HTTP errors
                if response.status_code >= 400:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"HTTP {response.status_code}, retrying in {delay:.1f}s (attempt {attempt + 1})")
                        time.sleep(delay)
                        continue
                    else:
                        response.raise_for_status()
                
                return response
                
            except requests.exceptions.ProxyError as e:
                # If proxy fails, try without proxy as fallback
                if proxy and self.proxy_manager.proxy_enabled:
                    error_msg = str(e)
                    logger.warning(f"Proxy failed ({error_msg[:50]}...), retrying without proxy for {url[:80]}...")
                    try:
                        # Remove proxy-specific headers for direct connection
                        direct_headers = self.headers.copy()
                        session = self._get_session()
                        response = session.get(url, params=params, headers=direct_headers, timeout=timeout, verify=False)
                        if response.status_code == 200:
                            logger.info(f"Fallback successful: direct connection worked for {url[:80]}...")
                            return response
                    except Exception as fallback_error:
                        logger.debug(f"Fallback request also failed: {fallback_error}")
                # Re-raise if fallback also failed or proxy not enabled
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Proxy error, retrying in {delay:.1f}s (attempt {attempt + 1})")
                    time.sleep(delay)
                    continue
                raise
            except (Timeout, ConnectionError) as e:
                # Check if this is a proxy-related timeout/connection error
                error_msg = str(e).lower()
                if proxy and self.proxy_manager.proxy_enabled and ("socks" in error_msg or "proxy" in error_msg or "connection not allowed" in error_msg):
                    logger.warning(f"Proxy connection failed ({error_msg[:50]}...), retrying without proxy for {url[:80]}...")
                    try:
                        # Try without proxy as fallback
                        direct_headers = self.headers.copy()
                        session = self._get_session()
                        response = session.get(url, params=params, headers=direct_headers, timeout=timeout, verify=False)
                        if response.status_code == 200:
                            logger.info(f"Fallback successful: direct connection worked for {url[:80]}...")
                            return response
                    except Exception as fallback_error:
                        logger.debug(f"Fallback request also failed: {fallback_error}")
                
                # Normal retry logic for non-proxy errors
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Request failed: {e}, retrying in {delay:.1f}s (attempt {attempt + 1})")
                    time.sleep(delay)
                    continue
                else:
                    raise
        
        # This should never be reached, but just in case
        raise RequestException("Max retries exceeded")
    
    def _get_total_traded(self, address: str) -> int:
        """Get total number of trades for a wallet"""
        try:
            response = self._http_get_resilient(self.traded_endpoint, params={"user": address})
            data = response.json()
            
            if isinstance(data, dict) and "traded" in data:
                return int(data["traded"])
            elif isinstance(data, list) and data:
                return int(data[0]["traded"])
            return 0
        except Exception as e:
            logger.warning(f"Failed to get traded total for {address}: {e}")
            raise  # Re-raise to trigger retry logic
    
    def _get_closed_positions(self, address: str, max_positions: int = MAX_CLOSED_POSITIONS, page_limit: int = 500) -> List[Dict[str, Any]]:
        """Get closed positions for a wallet with pagination (up to max_positions).
        Returns positions filtered by ANALYSIS_LOOKBACK_DAYS and sorted by closed_at/timestamp descending (most recent first).
        """
        positions = []
        offset = 0
        
        try:
            # Fetch more positions than needed to ensure we have enough after filtering by date
            # We'll fetch up to max_positions * 3 to account for filtering by date
            fetch_limit = max_positions * 3  # Fetch extra to ensure we have enough recent positions after date filtering
            
            # Calculate cutoff date for filtering
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=ANALYSIS_LOOKBACK_DAYS)
            
            while len(positions) < fetch_limit:
                limit = min(page_limit, fetch_limit - len(positions))
                params = {"user": address, "limit": limit, "offset": offset}
                
                response = self._http_get_resilient(
                    self.closed_positions_endpoint, 
                    params=params
                )
                
                data = response.json()
                batch = data if isinstance(data, list) else (data.get("positions", []) if isinstance(data, dict) else [])
                
                if not batch:
                    break
                
                positions.extend(batch)
                offset += len(batch)
                
                # Protection against infinite loop: if we got fewer items than requested, we've reached the end
                if len(batch) < limit:
                    break
            
            # Sort positions by closed_at/timestamp descending (most recent first)
            def get_timestamp(pos: Dict[str, Any]) -> float:
                """Extract timestamp from position for sorting"""
                # Try different possible timestamp fields
                timestamp = (
                    pos.get("closed_at") or 
                    pos.get("closedAt") or 
                    pos.get("timestamp") or 
                    pos.get("created_at") or 
                    pos.get("createdAt") or
                    0
                )
                
                # Handle string timestamps
                if isinstance(timestamp, str):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        return dt.timestamp()
                    except Exception:
                        return 0.0
                
                # Handle numeric timestamps (might be in milliseconds)
                if isinstance(timestamp, (int, float)):
                    # If timestamp is > 1e10, it's likely in milliseconds, convert to seconds
                    if timestamp > 1e10:
                        return timestamp / 1000.0
                    return float(timestamp)
                
                return 0.0
            
            def get_datetime(pos: Dict[str, Any]) -> Optional[datetime]:
                """Extract datetime from position for date filtering"""
                timestamp = (
                    pos.get("closed_at") or 
                    pos.get("closedAt") or 
                    pos.get("timestamp") or 
                    pos.get("created_at") or 
                    pos.get("createdAt") or
                    None
                )
                
                if timestamp is None:
                    return None
                
                if isinstance(timestamp, str):
                    try:
                        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    except Exception:
                        return None
                
                if isinstance(timestamp, (int, float)):
                    if timestamp > 1e10:
                        timestamp = timestamp / 1000.0
                    return datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
                
                return None
            
            # Sort by timestamp descending (newest first)
            positions.sort(key=get_timestamp, reverse=True)
            
            # Filter by date: only keep positions within ANALYSIS_LOOKBACK_DAYS
            filtered_positions = []
            for pos in positions:
                pos_dt = get_datetime(pos)
                if pos_dt is None:
                    # If we can't determine date, include it (conservative approach)
                    filtered_positions.append(pos)
                elif pos_dt >= cutoff_date:
                    filtered_positions.append(pos)
                else:
                    # Position is older than cutoff, stop here since positions are sorted by date descending
                    break
            
            # Take only the most recent max_positions
            recent_positions = filtered_positions[:max_positions]
            
            logger.debug(
                f"Fetched {len(positions)} total closed positions for {address}, "
                f"filtered to {len(filtered_positions)} within {ANALYSIS_LOOKBACK_DAYS} days, "
                f"using {len(recent_positions)} most recent (requested up to {max_positions})"
            )
            
            return recent_positions
            
        except Exception as e:
            logger.warning(f"Failed to get closed positions for {address}: {e}")
            raise  # Re-raise to trigger retry logic
    
    def _get_last_trade_timestamp(self, address: str) -> Optional[str]:
        """Get timestamp of the most recent trade for a wallet"""
        try:
            response = self._http_get_resilient(
                self.trades_endpoint, 
                params={"user": address, "limit": 1}
            )
            trades = response.json() if response.ok else []
            
            if not trades:
                return None
            
            # Get the most recent trade (first in list)
            trade = trades[0]
            timestamp = trade.get("timestamp")
            
            if timestamp:
                if isinstance(timestamp, str):
                    # Return ISO format timestamp
                    try:
                        # Parse and normalize to ISO format
                        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        return dt.isoformat()
                    except Exception:
                        return None
                elif isinstance(timestamp, (int, float)):
                    # Unix timestamp
                    dt = datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
                    return dt.isoformat()
            
            return None
        except Exception as e:
            logger.debug(f"Failed to get last trade timestamp for {address}: {e}")
            return None
    
    def _get_daily_trading_frequency(self, address: str) -> float:
        """Calculate average trades per day for a wallet"""
        try:
            response = self._http_get_resilient(
                self.trades_endpoint, 
                params={"user": address, "limit": 100}
            )
            trades = response.json() if response.ok else []
            
            if len(trades) < 10:
                return 0.0
            
            # Calculate time span
            timestamps = []
            for trade in trades:
                ts = trade.get("timestamp")
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                    except Exception:
                        continue
                elif ts is None:
                    continue
                timestamps.append(float(ts))
            
            if len(timestamps) < 2:
                return 0.0
            
            time_span_days = (max(timestamps) - min(timestamps)) / (24 * 3600)
            if time_span_days < 1:
                time_span_days = 1.0
            
            return len(timestamps) / time_span_days
            
        except Exception as e:
            logger.warning(f"Failed to calculate daily frequency for {address}: {e}")
            raise  # Re-raise to trigger retry logic
    
    def _compute_win_rate_and_pnl(self, closed_positions: List[Dict[str, Any]]) -> Tuple[float, float]:
        """Compute win rate and total PnL from closed positions"""
        if not closed_positions:
            return 0.0, 0.0
        
        wins = 0
        pnl_sum = 0.0
        
        for position in closed_positions:
            pnl = float(position.get("realizedPnl", 0) or 0)
            pnl_sum += pnl
            if pnl > 0:
                wins += 1
        
        win_rate = wins / len(closed_positions)
        return win_rate, pnl_sum
    
    def _compute_volume_and_stake(self, closed_positions: List[Dict[str, Any]]) -> Tuple[float, float]:
        """Compute total volume and average stake from closed positions.
        
        Returns:
            Tuple[float, float]: (total_volume, avg_stake)
            - total_volume: Sum of all stakes (totalBought * avgPrice) across all positions
            - avg_stake: Average stake per market (total_volume / num_markets)
        """
        if not closed_positions:
            return 0.0, 0.0
        
        total_volume = 0.0
        
        for position in closed_positions:
            # Try to get volume from position data
            # Check for existing volume field first
            volume = position.get("volume") or position.get("totalVolume") or position.get("total_volume")
            
            if volume is not None:
                try:
                    total_volume += float(volume)
                    continue
                except (ValueError, TypeError):
                    pass
            
            # Calculate stake from totalBought and avgPrice
            total_bought = float(position.get("totalBought", 0) or position.get("total_bought", 0) or 0)
            avg_price = float(position.get("avgPrice", 0) or position.get("avg_price", 0) or 0)
            
            # If we have both values, calculate stake
            if total_bought > 0 and avg_price > 0:
                stake = total_bought * avg_price
                total_volume += stake
            elif total_bought > 0:
                # Fallback: use totalBought as volume estimate if avgPrice is missing
                total_volume += total_bought
        
        num_markets = len(closed_positions)
        avg_stake = total_volume / num_markets if num_markets > 0 else 0.0
        
        return total_volume, avg_stake
    
    def add_wallets_to_queue(self, wallets: Dict[str, Dict[str, str]]) -> int:
        """Add multiple wallets to analysis queue"""
        added_count = 0
        
        for addr, meta in wallets.items():
            if self.db.add_wallet_to_queue(addr, meta.get("display"), meta.get("source")):
                added_count += 1
        
        logger.info(f"Added {added_count} wallets to analysis queue")
        return added_count
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        stats = self.db.get_queue_stats()
        stats['workers_running'] = self.running
        stats['active_workers'] = len(self.workers)
        return stats

# Example usage
if __name__ == "__main__":
    # Test the analyzer
    db = PolymarketDB("test_polymarket.db")
    config = AnalysisConfig(api_max_workers=2)
    analyzer = WalletAnalyzer(db, config)
    
    # Add some test wallets
    test_wallets = {
        "0x1234567890123456789012345678901234567890": {"display": "Test Wallet 1", "source": "test"},
        "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd": {"display": "Test Wallet 2", "source": "test"}
    }
    
    analyzer.add_wallets_to_queue(test_wallets)
    
    # Start workers
    analyzer.start_workers()
    
    try:
        # Let it run for a bit
        time.sleep(10)
        
        # Check status
        status = analyzer.get_queue_status()
        print(f"Queue status: {status}")
        
    finally:
        analyzer.stop_workers()
