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
from requests.exceptions import RequestException, Timeout, ConnectionError

from db import PolymarketDB

logger = logging.getLogger(__name__)

@dataclass
class AnalysisConfig:
    """Configuration for wallet analysis"""
    api_max_workers: int = 3
    api_timeout_sec: int = 20
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
        
        # Worker state
        self.running = False
        self.workers = []
        self.stop_event = threading.Event()
    
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
                jobs = self.db.get_pending_jobs(limit=10)  # Get more jobs to increase chances of claiming one
                
                if not jobs:
                    # No jobs available, wait a bit
                    # Log every 5 minutes that we're idle (for visibility)
                    now = time.time()
                    if now - last_idle_log > 300:
                        # Check queue size directly
                        pending_count = len(self.db.get_pending_jobs(limit=1000))
                        logger.info(f"{worker_name} idle - no pending jobs (checked {pending_count} total pending)")
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
                    # No job was available for claiming, wait a bit
                    time.sleep(0.5)
                    continue
                
                logger.info(f"{worker_name} processing job {job['id']} for {job['address']}")
                
                # Process the job
                success = self._analyze_wallet(job)
                
                if success:
                    # Job completed successfully
                    self.db.complete_job(job['id'])
                    logger.info(f"{worker_name} completed job {job['id']} for {job['address']}")
                else:
                    # Job failed, will be retried later
                    logger.warning(f"{worker_name} failed job {job['id']} for {job['address']}")
                
                # Small delay between jobs
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"{worker_name} error: {e}")
                time.sleep(1)
        
        logger.info(f"{worker_name} stopped")
    
    def _analyze_wallet(self, job: Dict[str, Any]) -> bool:
        """Analyze a single wallet"""
        address = job['address']
        job_id = job['id']
        
        try:
            # Check cache first
            cached = self.db.get_cached_analysis(address)
            if cached:
                logger.info(f"Using cached analysis for {address}")
                traded = cached['traded_total']
                win_rate = cached['win_rate']
                pnl_total = cached['realized_pnl_total']
                daily_freq = cached['daily_trading_frequency']
                analysis_result = cached['analysis_result']
            else:
                # Get wallet metrics from API
                traded = self._get_total_traded(address)
                # Fast filter: if traded below threshold, short-circuit without heavy calls
                if traded < 6:
                    logger.info(f"Fast-skip {address}: traded={traded} (<6)")
                    win_rate = 0.0
                    pnl_total = 0.0
                    daily_freq = 0.0
                    # Cache negative result to avoid repeat work
                    self.db.cache_analysis_result(address, traded, win_rate, pnl_total, daily_freq, "rejected")
                    return True
                
                closed_positions = self._get_closed_positions(address)
                win_rate, pnl_total = self._compute_win_rate_and_pnl(closed_positions)
                daily_freq = self._get_daily_trading_frequency(address)
                
            # Determine analysis result - strict criteria: 6+ trades, 75%+ win rate
            if traded >= 6 and win_rate >= 0.75:
                analysis_result = "accepted"
            else:
                analysis_result = "rejected"
                
                # Cache the result
                self.db.cache_analysis_result(
                    address, traded, win_rate, pnl_total, daily_freq, analysis_result
                )
            
            # Apply criteria: traded >= 6 and win_rate >= 0.75 (strict)
            if traded >= 6 and win_rate >= 0.75:
                # Store wallet in database
                success = self.db.upsert_wallet(
                    address, job.get('display', address), traded, win_rate, 
                    pnl_total, daily_freq, job.get('source', 'queue')
                )
                
                if success:
                    logger.info(f"Added {address}: {traded} trades, {win_rate:.2%} win rate, {pnl_total:.2f} PnL")
                    return True
                else:
                    logger.error(f"Failed to save wallet {address} to database")
                    return False
            else:
                logger.info(f"Skipping {address}: {traded} trades, {win_rate:.2%} win rate (criteria: >=6 trades, >=75% win rate)")
                return True  # Consider this a successful analysis (wallet filtered out)
                
        except Exception as e:
            logger.error(f"Error analyzing wallet {address}: {e}")
            self._handle_analysis_error(job_id, str(e))
            return False
    
    def _handle_analysis_error(self, job_id: int, error_message: str):
        """Handle analysis error with retry logic"""
        try:
            # Get current job info
            jobs = self.db.get_pending_jobs(limit=1000)  # Get all jobs to find this one
            job = next((j for j in jobs if j['id'] == job_id), None)
            
            if not job:
                logger.error(f"Job {job_id} not found for error handling")
                return
            
            retry_count = job['retry_count']
            max_retries = job['max_retries']
            
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
            
            next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
            next_retry_iso = next_retry_at.isoformat()
            
            # Update job with retry info
            self.db.increment_job_retry(job_id, next_retry_iso, error_message)
            
            logger.info(f"Job {job_id} will retry in {delay_seconds:.1f}s (attempt {retry_count + 1}/{max_retries})")
            
        except Exception as e:
            logger.error(f"Error handling analysis error for job {job_id}: {e}")
    
    def _http_get_resilient(self, url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """Make HTTP GET request with resilient retry logic and 429 handling"""
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, headers=self.headers, timeout=self.config.api_timeout_sec)
                
                # Handle 429 rate limiting
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            delay = int(retry_after)
                            logger.warning(f"Rate limited (429), waiting {delay}s as requested by server")
                            time.sleep(delay)
                            continue
                        except ValueError:
                            pass
                    
                    # Fallback exponential backoff
                    delay = base_delay * (2 ** attempt)
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
                
            except (RequestException, Timeout, ConnectionError) as e:
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
    
    def _get_closed_positions(self, address: str) -> List[Dict[str, Any]]:
        """Get closed positions for a wallet"""
        try:
            response = self._http_get_resilient(
                self.closed_positions_endpoint, 
                params={"user": address, "limit": 500, "offset": 0}
            )
            data = response.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning(f"Failed to get closed positions for {address}: {e}")
            raise  # Re-raise to trigger retry logic
    
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
