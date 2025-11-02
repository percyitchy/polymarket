"""
Polymarket Notifier Bot - Main Script
Monitors high-performing Polymarket wallets for consensus buy signals
"""

import os
import time
import asyncio
import logging
import threading
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

# Import our modules
try:
    from fetch_leaderboards import scrape_polymarket_leaderboards
    PLAYWRIGHT_AVAILABLE = True
    print("Using Playwright scraper")
except Exception as e:
    print(f"Playwright not available: {e}")
    from fetch_leaderboards_enhanced import scrape_polymarket_leaderboards_enhanced as scrape_polymarket_leaderboards
    PLAYWRIGHT_AVAILABLE = False

from db import PolymarketDB
from notify import TelegramNotifier
from wallet_analyzer import WalletAnalyzer, AnalysisConfig
from bet_monitor import BetDetector, TelegramNotifier as BetTelegramNotifier

# HashiDive API fallback (optional)
try:
    from hashdive_client import HashDiveClient
    HASHDIVE_AVAILABLE = True
    HASHDIVE_API_KEY = os.getenv("HASHDIVE_API_KEY", "2fcbbb010f3ff15f84dc47ebb0d92917d6fee90771407f56174423b9b28e5c3c")
except ImportError:
    HASHDIVE_AVAILABLE = False
    HASHDIVE_API_KEY = None
    # Don't log here as logger might not be initialized yet
    pass

# Load environment variables
load_dotenv()

# Configure logging
# Setup logging with absolute path
_log_dir = os.path.dirname(os.path.abspath(__file__))
_log_file = os.path.join(_log_dir, 'polymarket_notifier.log')

# Remove existing handlers to avoid duplicates
root_logger = logging.getLogger()
root_logger.handlers = []

# Create handlers
handlers = [
    logging.StreamHandler(),
    logging.FileHandler(_log_file)
]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers,
    force=True  # Force reconfiguration
)

logger = logging.getLogger(__name__)
logger.info(f"Logging initialized, log file: {_log_file}")

class PolymarketNotifier:
    @staticmethod
    def _get_env_int(key: str, default: int) -> int:
        """Get integer from env var, handling inline comments"""
        val = os.getenv(key, str(default))
        # Strip inline comments (after #)
        if '#' in val:
            val = val.split('#')[0]
        return int(val.strip())
    
    @staticmethod
    def _get_env_float(key: str, default: float) -> float:
        """Get float from env var, handling inline comments"""
        val = os.getenv(key, str(default))
        # Strip inline comments (after #)
        if '#' in val:
            val = val.split('#')[0]
        return float(val.strip())
    
    def __init__(self):
        # Configuration from environment
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.poll_interval = self._get_env_int("POLL_INTERVAL_SEC", 7)
        self.alert_window_min = self._get_env_float("ALERT_WINDOW_MIN", 15.0)
        self.alert_cooldown_min = self._get_env_float("ALERT_COOLDOWN_MIN", 10.0)
        self.conflict_window_min = self._get_env_float("ALERT_CONFLICT_WINDOW_MIN", 10.0)
        self.price_band = self._get_env_float("ALERT_PRICE_BAND", 0.02)
        self.refresh_interval_min = self._get_env_float("ALERT_REFRESH_MIN", 60.0)
        self.min_consensus = self._get_env_int("MIN_CONSENSUS", 3)  # Minimum 3 wallets required
        if self.min_consensus < 3:
            logger.warning(f"min_consensus is {self.min_consensus}, forcing to 3")
            self.min_consensus = 3
        self.max_wallets = self._get_env_int("MAX_WALLETS", 2000)
        self.max_predictions = self._get_env_int("MAX_PREDICTIONS", 1000)
        self.db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
        
        # Initialize HashiDive client if available (fallback API)
        self.hashdive_client = None
        if HASHDIVE_AVAILABLE and HASHDIVE_API_KEY:
            try:
                self.hashdive_client = HashDiveClient(HASHDIVE_API_KEY)
                logger.info("HashiDive API client initialized (fallback mode)")
            except Exception as e:
                logger.warning(f"Failed to initialize HashiDive client: {e}")
                self.hashdive_client = None
        
        # Heartbeat toggle for Telegram notifications
        heartbeat_env = os.getenv("TELEGRAM_HEARTBEAT", "0").strip().lower()
        self.telegram_heartbeat_enabled = heartbeat_env in ("1", "true", "yes", "on")
        
        # Analysis queue configuration
        self.api_max_workers = self._get_env_int("API_MAX_WORKERS", 7)
        self.api_timeout_sec = self._get_env_int("API_TIMEOUT_SEC", 20)
        self.api_retry_max = self._get_env_int("API_RETRY_MAX", 6)
        self.api_retry_base = self._get_env_float("API_RETRY_BASE", 1.2)
        self.analysis_ttl_min = self._get_env_int("ANALYSIS_TTL_MIN", 180)
        
        # Leaderboard URLs to scrape
        self.leaderboard_urls = [
            "https://polymarket.com/leaderboard/overall/today/profit",
            "https://polymarket.com/leaderboard/overall/weekly/profit",
            "https://polymarket.com/leaderboard/overall/monthly/profit"
        ]
        
        # Initialize components
        self.db = PolymarketDB(self.db_path)
        self.notifier = TelegramNotifier(self.telegram_token, self.telegram_chat_id)
        self.bet_detector = BetDetector(self.db_path)
        
        # Initialize wallet analyzer
        analysis_config = AnalysisConfig(
            api_max_workers=self.api_max_workers,
            api_timeout_sec=self.api_timeout_sec,
            api_retry_max=self.api_retry_max,
            api_retry_base=self.api_retry_base,
            analysis_ttl_min=self.analysis_ttl_min
        )
        self.wallet_analyzer = WalletAnalyzer(self.db, analysis_config)
        
        # Polymarket Data API endpoints
        self.data_api = "https://data-api.polymarket.com"
        self.trades_endpoint = f"{self.data_api}/trades"
        self.closed_positions_endpoint = f"{self.data_api}/closed-positions"
        self.traded_endpoint = f"{self.data_api}/traded"
        
        # Headers for API requests
        self.headers = {
            "User-Agent": "PolymarketNotifier/1.0 (+https://polymarket.com)"
        }
        
        # Monitoring state
        self.monitoring = False
        self.loop_count = 0
        # Diagnostic counters for suppressed alerts
        self.suppressed_counts = {
            'price_high': 0,
            'ignore_30m_same_outcome': 0,
            'dedupe_no_growth_10m': 0,
            'no_trigger_matched': 0,
            'opposite_recent': 0
        }
        
    def validate_config(self) -> bool:
        """Validate configuration and environment variables"""
        if not self.telegram_token or not self.telegram_chat_id:
            logger.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env file")
            return False
        
        logger.info("Configuration validated successfully")
        return True
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def http_get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make HTTP GET request with retry logic"""
        import requests
        
        response = requests.get(url, params=params, headers=self.headers, timeout=20)
        response.raise_for_status()
        return response

    def _get_current_price(self, condition_id: str, outcome_index: int) -> Optional[float]:
        """Get current price for market outcome. Returns None if unavailable, or 0.0 if market resolved."""
        try:
            import requests
            url = f"https://clob.polymarket.com/markets/{condition_id}"
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                return None
            data = resp.json()
            tokens = data.get('tokens') or []
            if tokens and outcome_index < len(tokens):
                token = tokens[outcome_index]
                for key in ("last_price", "price", "mark_price"):
                    val = token.get(key)
                    if isinstance(val, (int, float)):
                        price = float(val)
                        # Return 0.0 explicitly for resolved markets, not None
                        return price
            # Fallback to market-level price
            for key in ("last_price", "price", "mark_price"):
                val = data.get(key)
                if isinstance(val, (int, float)):
                    return float(val)
            return None
        except Exception as e:
            logger.debug(f"Error getting current price: {e}")
            return None
    
    async def collect_wallets_from_polymarket_analytics(self, limit: int = 2000) -> Dict[str, Dict[str, str]]:
        """Collect wallet addresses from polymarketanalytics.com"""
        logger.info(f"Collecting wallets from polymarketanalytics.com (limit: {limit})...")
        wallets = {}
        
        try:
            from fetch_polymarket_analytics_api import fetch_traders_from_api
            
            # Fetch addresses from API
            addresses = fetch_traders_from_api(target=limit)
            
            if addresses:
                logger.info(f"Got {len(addresses)} addresses from polymarketanalytics.com")
                
                # Convert to expected format
                for addr in addresses:
                    addr_lower = addr.lower()
                    wallets[addr_lower] = {
                        "display": addr_lower,
                        "source": "polymarket_analytics"
                    }
                
                logger.info(f"Collected {len(wallets)} unique wallets from polymarketanalytics.com")
            else:
                logger.warning("No addresses fetched from polymarketanalytics.com")
                
        except Exception as e:
            logger.error(f"Error collecting wallets from polymarketanalytics.com: {e}")
        
        return wallets
    
    async def collect_wallets_from_leaderboards(self) -> Dict[str, Dict[str, str]]:
        """Collect wallet addresses from Polymarket APIs"""
        logger.info("Starting wallet collection from Polymarket APIs...")
        
        all_wallets = {}
        
        # Also collect from polymarketanalytics.com
        try:
            analytics_wallets = await self.collect_wallets_from_polymarket_analytics(limit=2000)
            all_wallets.update(analytics_wallets)
            logger.info(f"Added {len(analytics_wallets)} wallets from polymarketanalytics.com")
        except Exception as e:
            logger.error(f"Error collecting from polymarketanalytics.com: {e}")
        
        try:
            # Use official API scraper for maximum wallet collection
            logger.info("Using official Polymarket API scraper")
            from api_scraper import PolymarketAPIScraper
            
            async with PolymarketAPIScraper() as scraper:
                wallet_addresses = await scraper.scrape_all_wallets()
            
            # Convert to expected format
            for addr in wallet_addresses:
                addr_lower = addr.lower()
                if addr_lower not in all_wallets:
                    all_wallets[addr_lower] = {
                        "display": addr_lower,
                    "source": "polymarket_api"
                }
            
            logger.info(f"Collected {len(all_wallets)} total unique wallets from all sources")
            return all_wallets
        except Exception as e:
            logger.error(f"Error collecting wallets from APIs: {e}")
            # Fallback to Playwright if API fails
            try:
                if PLAYWRIGHT_AVAILABLE:
                    logger.info("Falling back to Playwright scraper")
                    wallets = await scrape_polymarket_leaderboards(
                        self.leaderboard_urls,
                        headless=True
                    )
                else:
                    logger.info("Falling back to enhanced requests scraper")
                    from fetch_leaderboards_enhanced import scrape_polymarket_leaderboards_enhanced
                    wallets = scrape_polymarket_leaderboards_enhanced(
                        self.leaderboard_urls,
                        max_pages_per_url=40
                    )
                
                logger.info(f"Fallback collected {len(wallets)} unique wallets")
                return wallets
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                return {}
    
    
    def analyze_and_filter_wallets(self, wallets: Dict[str, Dict[str, str]]) -> int:
        """Add wallets to analysis queue instead of analyzing directly"""
        logger.info(f"Adding {len(wallets)} wallets to analysis queue...")
        
        # Add wallets to queue
        added_count = self.wallet_analyzer.add_wallets_to_queue(wallets)
        
        # Get queue status
        queue_status = self.wallet_analyzer.get_queue_status()
        
        logger.info(f"Added {added_count} wallets to queue. Queue status: {queue_status}")
        
        # Send summary notification
        self.notifier.send_wallet_collection_summary(
            len(wallets), added_count, {"method": "queue_based"}
        )
        
        return added_count
    
    def get_new_trades(self, address: str, last_seen_trade_id: Optional[str], side: str = "BUY") -> tuple[List[Dict[str, Any]], Optional[str]]:
        """Get new trades for a wallet filtered by side (BUY/SELL), with HashiDive fallback"""
        try:
            params = {"user": address, "side": side, "limit": 50}
            response = self.http_get(self.trades_endpoint, params=params)
            trades = response.json() if response.ok else []
            
            # Fallback to HashiDive API if Polymarket API fails or returns empty
            if (not response.ok or not trades) and self.hashdive_client:
                try:
                    logger.info(f"Polymarket API returned {len(trades)} trades, trying HashiDive fallback for {address[:12]}...")
                    
                    # Request only recent trades (last 7 days) from HashiDive to avoid old closed markets
                    from datetime import datetime, timezone, timedelta
                    now_iso = datetime.now(timezone.utc).isoformat()
                    week_ago_iso = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
                    
                    hashdive_data = self.hashdive_client.get_trades(
                        user_address=address,
                        page=1,
                        page_size=50,
                        timestamp_gte=week_ago_iso,  # Only trades from last 7 days
                        timestamp_lte=now_iso
                    )
                    # HashiDive returns dict with 'data' or list of trades
                    if isinstance(hashdive_data, dict):
                        trades = hashdive_data.get('data', hashdive_data.get('trades', []))
                    elif isinstance(hashdive_data, list):
                        trades = hashdive_data
                    else:
                        trades = []
                    
                    if trades:
                        # Analyze age of trades from HashiDive
                        current_time = time.time()
                        old_trades_count = 0
                        newest_trade_age = None
                        oldest_trade_age = None
                        
                        for trade in trades:
                            # Try to get timestamp from trade
                            trade_timestamp = None
                            for ts_key in ("timestamp", "createdAt", "created_at", "time", "date"):
                                ts_val = trade.get(ts_key)
                                if ts_val:
                                    try:
                                        if isinstance(ts_val, str):
                                            trade_timestamp = datetime.fromisoformat(ts_val.replace("Z", "+00:00")).timestamp()
                                        elif isinstance(ts_val, (int, float)):
                                            ts_float = float(ts_val)
                                            # Check if timestamp is in milliseconds (>= 1e12) or seconds
                                            if ts_float > 1e12:  # Likely milliseconds
                                                trade_timestamp = ts_float / 1000.0
                                            elif ts_float > 1e9:  # Seconds (valid range)
                                                trade_timestamp = ts_float
                                            else:
                                                # Too small, likely not a timestamp
                                                continue
                                        break
                                    except Exception:
                                        continue
                            
                            if trade_timestamp:
                                # Validate timestamp (should be reasonable - between 2000 and 2100)
                                if trade_timestamp < 946684800 or trade_timestamp > 4102444800:  # 2000-01-01 to 2100-01-01
                                    continue  # Invalid timestamp, skip
                                
                                trade_age_hours = (current_time - trade_timestamp) / 3600
                                # Only count if age is positive and reasonable
                                if trade_age_hours > 0 and trade_age_hours < 365 * 24:  # Less than 1 year old
                                    if trade_age_hours > 48:
                                        old_trades_count += 1
                                    if newest_trade_age is None or trade_age_hours < newest_trade_age:
                                        newest_trade_age = trade_age_hours
                                    if oldest_trade_age is None or trade_age_hours > oldest_trade_age:
                                        oldest_trade_age = trade_age_hours
                        
                        # Log HashiDive results with age info
                        if newest_trade_age is not None and oldest_trade_age is not None:
                            age_info = f" (age: newest={newest_trade_age:.1f}h, oldest={oldest_trade_age:.1f}h, old>48h={old_trades_count})"
                            logger.info(f"HashiDive fallback returned {len(trades)} trades for {address[:12]}...{age_info}")
                            
                            if old_trades_count > 0:
                                logger.warning(f"⚠️ HashiDive returned {old_trades_count}/{len(trades)} old trades (>48h) for {address[:12]}... - these will be filtered out to avoid closed markets")
                            elif oldest_trade_age > 24:
                                logger.info(f"ℹ️ HashiDive trades are recent (newest={newest_trade_age:.1f}h, oldest={oldest_trade_age:.1f}h)")
                        else:
                            # No timestamp info available - log sample trade structure
                            logger.info(f"HashiDive fallback returned {len(trades)} trades for {address[:12]}... (timestamp info not available)")
                            if trades:
                                sample_keys = list(trades[0].keys()) if isinstance(trades[0], dict) else []
                                logger.debug(f"HashiDive trade sample keys: {sample_keys[:10]}")
                        
                        # Filter by side (HashiDive may use different field names)
                        if side:
                            trades = [t for t in trades if str(t.get('side', t.get('direction', ''))).upper() == side.upper()]
                except Exception as hashdive_error:
                    logger.debug(f"HashiDive fallback failed for {address[:12]}...: {hashdive_error}")
                    trades = []
            
            new_events = []
            newest_id = last_seen_trade_id

            # If first time seeing this wallet, initialize last_seen_trade_id to latest trade
            if last_seen_trade_id is None and trades:
                top_trade_id = str(trades[0].get("id") or trades[0].get("tradeId") or 
                                 trades[0].get("_id") or trades[0].get("transactionHash") or "")
                return [], (top_trade_id or None)
            
            for trade in trades:
                # Support both Polymarket and HashiDive API formats
                trade_id = str(trade.get("id") or trade.get("tradeId") or 
                             trade.get("_id") or trade.get("transactionHash") or 
                             trade.get("txHash") or "")
                
                if not trade_id:
                    continue
                
                if last_seen_trade_id and trade_id == last_seen_trade_id:
                    break
                
                # HashiDive may use different field names
                condition_id = (trade.get("conditionId") or trade.get("market") or 
                               trade.get("marketId") or trade.get("assetId") or 
                               trade.get("tokenId"))
                outcome_index = (trade.get("outcomeIndex") if trade.get("outcomeIndex") is not None 
                               else trade.get("outcome") or trade.get("outcomeIndex"))
                
                if not condition_id or outcome_index is None:
                    continue
                
                timestamp = trade.get("timestamp") or trade.get("createdAt")
                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
                    except Exception:
                        timestamp = None
                elif isinstance(timestamp, (int, float)):
                    ts_float = float(timestamp)
                    # Check if timestamp is in milliseconds (>= 1e12) or seconds
                    if ts_float > 1e12:  # Likely milliseconds
                        timestamp = ts_float / 1000.0
                    elif ts_float > 1e9:  # Seconds (valid range)
                        timestamp = ts_float
                    else:
                        timestamp = None  # Invalid timestamp
                
                # Validate timestamp and set to None if invalid (will be filtered out)
                if timestamp:
                    current_time = time.time()
                    # Timestamp should be reasonable: between 2000 and 2100, and not in future
                    if timestamp < 946684800 or timestamp > 4102444800 or timestamp > current_time + 3600:
                        logger.debug(f"Invalid timestamp {timestamp} for trade {trade_id[:8]}, skipping")
                        timestamp = None
                
                if timestamp is None:
                    # Skip trades without valid timestamp
                    continue
                
                # Extract price
                price = float(trade.get("price", 0))
                
                # AGGRESSIVE FILTER: Skip trades with entry price indicating closed/resolved market
                # Price <= 0.02 or >= 0.98 means market is already closed/resolved (same as current_price filter)
                if price <= 0.02 or price >= 0.98:
                    logger.info(f"🚫 Skipping trade {trade_id[:12]}... with entry price ${price:.4f} (market closed/resolved, threshold: <=$0.02 or >=$0.98)")
                    continue
                
                # Extract side (BUY/SELL)
                side = trade.get("side", side)
                
                # Try to extract market title and slug from trade
                # Data API uses 'title' and 'slug' fields
                market_title = trade.get("title") or trade.get("question") or ""
                market_slug = trade.get("slug") or trade.get("eventSlug") or ""
                
                # If we don't have slug, fetch it from CLOB API
                if not market_slug and condition_id:
                    try:
                        import requests
                        slug_url = f"https://clob.polymarket.com/markets/{condition_id}"
                        slug_resp = requests.get(slug_url, timeout=3)
                        if slug_resp.status_code == 200:
                            slug_data = slug_resp.json()
                            market_slug = slug_data.get('market_slug') or slug_data.get('slug') or ""
                            if not market_title:
                                market_title = slug_data.get('question') or slug_data.get('title') or ""
                    except Exception:
                        pass  # Silently fail, will retry later
                
                # try extract usd amount
                usd_amount = 0.0
                # First, try direct USD value fields
                for key in ("usdValue", "amountUsd", "value_usd", "valueUsd", "usd_amount", "costUsd", "amount", "value", "size", "usd", "cost", "totalCost", "filledAmount"):
                    v = trade.get(key)
                    try:
                        if isinstance(v, str):
                            v = float(v)
                        if isinstance(v, (int, float)) and v > 0:
                            usd_amount = float(v)
                            logger.debug(f"Found USD from {key}: {usd_amount} for trade {trade_id[:8]}")
                            break
                    except Exception:
                        pass
                
                # Extract quantity for USD calculation fallback
                # IMPORTANT: "size" is the main field from Polymarket API
                quantity = 0.0
                # Check "size" first as it's the primary field
                size_val = trade.get("size")
                if size_val is not None:
                    try:
                        quantity = float(size_val)
                        logger.debug(f"Found quantity from 'size': {quantity} for trade {trade_id[:8]}")
                    except (ValueError, TypeError):
                        pass
                
                # If size not found, try other fields
                if quantity == 0.0:
                    for qty_key in ("quantity", "amount", "tokens", "shares", "filled", "filledAmount", "filledQuantity", "tokenAmount"):
                        qty = trade.get(qty_key)
                        try:
                            if isinstance(qty, str):
                                qty = float(qty)
                            if isinstance(qty, (int, float)) and qty > 0:
                                quantity = float(qty)
                                logger.debug(f"Found quantity from {qty_key}: {quantity} for trade {trade_id[:8]}")
                                break
                        except Exception:
                            pass
                
                # If no USD found, try to calculate from quantity * price
                if usd_amount == 0.0 and quantity > 0 and price and price > 0:
                    # Price is already in USD (e.g., 0.001 means $0.001 per share)
                    # So USD = quantity * price
                    usd_amount = quantity * float(price)
                    logger.info(f"Calculated USD from quantity*price: {quantity} * {price} = {usd_amount:.2f} for trade {trade_id[:8]}")
                
                # Log if still 0 for debugging
                if usd_amount == 0.0:
                    logger.warning(f"Warning: USD amount is 0 for trade {trade_id[:8]}, price={price}, quantity={quantity}, available_keys={list(trade.keys())}")
                
                new_events.append({
                    "trade_id": trade_id,
                    "conditionId": condition_id,
                    "outcomeIndex": int(outcome_index),
                    "timestamp": float(timestamp),
                    "marketTitle": market_title,  # Store title for alerts
                    "marketSlug": market_slug,  # Store slug for URL
                    "price": price,  # Store entry price
                    "side": side,  # Store direction
                    "usd": usd_amount,
                    "quantity": quantity  # Store quantity for fallback calculation
                })
                
                if newest_id is None:
                    newest_id = trade_id
            
            # Update newest_id to first trade's id if any
            if trades:
                top_trade_id = str(trades[0].get("id") or trades[0].get("tradeId") or 
                                 trades[0].get("_id") or trades[0].get("transactionHash") or newest_id or "")
                if top_trade_id:
                    newest_id = top_trade_id
            
            return new_events, newest_id
            
        except Exception as e:
            logger.warning(f"Error getting new {side} trades for {address}: {e}")
            return [], last_seen_trade_id

    def is_market_active(self, condition_id: str, outcome_index: Optional[int] = None) -> bool:
        """Check market status via CLOB API and return True if active/open."""
        try:
            import requests
            url = f"https://clob.polymarket.com/markets/{condition_id}"
            resp = requests.get(url, timeout=4)
            if resp.status_code != 200:
                # If API fails, also check price as indicator
                if outcome_index is not None:
                    price = self.notifier._get_current_price(condition_id, outcome_index)
                    if price is not None:
                        # Price >= 0.98 or <= 0.02 means closed/resolved (same threshold as entry price filter)
                        if price >= 0.98 or price <= 0.02:
                            return False
                return True  # fail-open to avoid silencing alerts on transient errors
            data = resp.json() or {}
            # Common flags/fields observed in CLOB payloads
            if isinstance(data, dict):
                # Check closed flag
                if data.get("closed") is True:
                    return False
                # Check status field
                status = str(data.get("status") or "").lower()
                if status in {"resolved", "finished", "closed", "ended", "finalized"}:
                    return False
                # Check active flag
                active = data.get("active")
                if active is False:
                    return False
                # Also check price as additional indicator if outcome_index provided
                if outcome_index is not None:
                    tokens = data.get('tokens') or []
                    if tokens and outcome_index < len(tokens):
                        token = tokens[outcome_index]
                        for key in ("last_price", "price", "mark_price"):
                            val = token.get(key)
                            if isinstance(val, (int, float)):
                                price = float(val)
                                # Price >= 0.98 or <= 0.02 means closed/resolved (same threshold as entry price filter)
                                if price >= 0.98 or price <= 0.02:
                                    return False
                                break
            return True
        except Exception as e:
            logger.debug(f"Error checking market status: {e}")
            # If check fails, also try price check as fallback
            if outcome_index is not None:
                try:
                    price = self.notifier._get_current_price(condition_id, outcome_index)
                    if price is not None:
                        # Price >= 0.98 or <= 0.02 means closed/resolved (same threshold as entry price filter)
                        if price >= 0.98 or price <= 0.02:
                            return False
                except Exception:
                    pass
            return True
    
    def check_consensus_and_alert(self, condition_id: str, outcome_index: int, 
                                 wallet: str, trade_id: str, timestamp: float, 
                                 price: float = 0, side: str = "BUY", 
                                 market_title: str = "", market_slug: str = "",
                                 usd_amount: float = 0.0, quantity: float = 0.0):
        """Check for consensus and send alert if threshold met"""
        try:
            # FIRST CHECK: Skip markets that are already closed/resolved (check at entry)
            # Note: At this point we don't have wallets_in_window yet, so we'll send details later
            if not self.is_market_active(condition_id, outcome_index):
                self.suppressed_counts['market_closed'] = self.suppressed_counts.get('market_closed', 0) + 1
                logger.warning(f"[SUPPRESS] BLOCKING: market_closed (entry check) condition={condition_id} outcome={outcome_index}")
                # Send details to reports (with minimal info since we don't have wallets yet)
                try:
                    self.notifier.send_suppressed_alert_details(
                        reason="market_closed",
                        condition_id=condition_id,
                        outcome_index=outcome_index,
                        wallets=[wallet],  # Just the current wallet
                        wallet_prices={wallet: price},
                        market_title=market_title,
                        market_slug=market_slug,
                        side=side
                    )
                except Exception as e:
                    logger.debug(f"Failed to send suppressed alert details: {e}")
                return
            # Check if this is first entry for this wallet in this market direction
            if self.db.has_traded_market(wallet, condition_id, side):
                logger.debug(f"Skipping {wallet}: already traded {condition_id} ({side})")
                return
            
            # Mark this market as traded for this wallet
            self.db.mark_market_traded(wallet, condition_id, side, timestamp)
            
            # Update rolling window grouped by direction
            key, window_data = self.db.update_rolling_window(
                condition_id, outcome_index, wallet, trade_id, timestamp, 
                self.alert_window_min, market_title, market_slug, price, side,
                usd_amount=usd_amount, quantity=quantity
            )
            
            # Get unique wallets in window for this direction
            wallets_in_window = sorted({e["wallet"] for e in window_data.get("events", [])})
            
            if len(wallets_in_window) < self.min_consensus:
                return
            
            # Check if alert already sent for this direction
            alert_key = f"{condition_id}:{outcome_index}:{side}"
            if self.db.is_alert_sent(condition_id, outcome_index, 
                                    window_data["first_ts"], window_data["last_ts"], alert_key):
                return
            
            # Extract market info and prices from window events
            market_title = ""
            market_slug = ""
            wallet_prices = {}  # Map wallet -> price
            
            for event in window_data.get("events", []):
                if event.get("marketTitle"):
                    market_title = event["marketTitle"]
                if event.get("marketSlug"):
                    market_slug = event["marketSlug"]
                if event.get("price") and event.get("wallet"):
                    wallet_prices[event["wallet"]] = event.get("price", 0)
            
            # Apply entry price divergence rule based on first three traders by time
            try:
                events_sorted = sorted(window_data.get("events", []), key=lambda e: e.get("ts", 0))
                first_three_prices = []
                seen_wallets = set()
                for e in events_sorted:
                    w = e.get("wallet")
                    if not w or w in seen_wallets:
                        continue
                    seen_wallets.add(w)
                    p = e.get("price")
                    if isinstance(p, (int, float)) and p > 0:
                        first_three_prices.append(float(p))
                    if len(first_three_prices) == 3:
                        break
                if len(first_three_prices) == 3:
                    p_min = min(first_three_prices)
                    p_max = max(first_three_prices)
                    # Determine band thresholds
                    if p_max <= 0.05:
                        price_ok = True  # any divergence allowed
                    elif p_max < 0.5:
                        price_ok = (p_max - p_min) / p_max <= 0.25
                    else:
                        price_ok = (p_max - p_min) / p_max <= 0.10
                    if not price_ok:
                        logger.info(
                            f"Skip alert due to entry price divergence: prices={first_three_prices}"
                        )
                        return
            except Exception as _e:
                # If any error occurs during divergence check, do not block alert
                logger.debug(f"Price divergence check skipped: {_e}")
            
            # Compute simple avg entry price across wallets in window
            avg_price = 0.0
            if wallet_prices:
                avg_price = sum(wallet_prices.values()) / max(1, len(wallet_prices))
            # Total USD across events in window (best-effort)
            total_usd = 0.0
            try:
                events = window_data.get("events", [])
                logger.info(f"Calculating total_usd from {len(events)} events for condition={condition_id}")
                for i, e in enumerate(events):
                    # Try direct USD field first
                    usd_val = e.get("usd")
                    if isinstance(usd_val, (int, float)) and usd_val > 0:
                        total_usd += float(usd_val)
                        logger.info(f"  Event {i+1}: Added usd={usd_val} from event.usd, total now={total_usd:.2f}")
                    else:
                        # Fallback: calculate from price * quantity if available
                        price = e.get("price")
                        quantity = e.get("quantity")
                        logger.debug(f"  Event {i+1}: usd={usd_val}, price={price}, quantity={quantity}")
                        if isinstance(price, (int, float)) and price > 0 and isinstance(quantity, (int, float)) and quantity > 0:
                            # Price in Polymarket is per share, so USD = price * shares
                            calculated = float(price) * float(quantity)
                            total_usd += calculated
                            logger.info(f"  Event {i+1}: Calculated usd={calculated:.2f} from price={price} * quantity={quantity}, total now={total_usd:.2f}")
                        else:
                            logger.warning(f"  Event {i+1}: Cannot calculate USD - usd={usd_val}, price={price}, quantity={quantity}")
                logger.info(f"Final total_usd={total_usd:.2f} for condition={condition_id}, outcome={outcome_index}, events={len(events)}")
            except Exception as e:
                logger.error(f"Error calculating total_usd: {e}", exc_info=True)
                total_usd = 0.0
            
            # Fetch current market price for outcome
            current_price = self._get_current_price(condition_id, outcome_index)
            now_iso = datetime.now(timezone.utc).isoformat()
            
            # CRITICAL: Block all alerts for resolved/closed markets
            # MUST check price before sending ANY alert
            try:
                if current_price is not None:
                    price_val = float(current_price)
                    logger.info(f"[PRICE CHECK] condition={condition_id}, outcome={outcome_index}, price={price_val}")
                    # Price = 1.0 or exactly 0.0 (or very close) means market is resolved - BLOCK ALERT
                    if price_val >= 0.999 or price_val <= 0.001:
                        self.suppressed_counts['resolved'] = self.suppressed_counts.get('resolved', 0) + 1
                        logger.warning(f"[SUPPRESS] BLOCKING: resolved market condition={condition_id} outcome={outcome_index} price={price_val:.6f}")
                        # Send suppressed alert details to reports
                        try:
                            self.notifier.send_suppressed_alert_details(
                                reason="resolved",
                                condition_id=condition_id,
                                outcome_index=outcome_index,
                                wallets=wallets_in_window,
                                wallet_prices=wallet_prices,
                                market_title=market_title,
                                market_slug=market_slug,
                                current_price=current_price,
                                side=side,
                                total_usd=total_usd
                            )
                        except Exception as e:
                            logger.debug(f"Failed to send suppressed alert details: {e}")
                        return
                    # Price >= 0.98 or <= 0.02 also indicates closed/almost resolved - BLOCK ALERT  
                    if price_val >= 0.98 or price_val <= 0.02:
                        self.suppressed_counts['price_high'] = self.suppressed_counts.get('price_high', 0) + 1
                        logger.warning(f"[SUPPRESS] BLOCKING: price too high/low condition={condition_id} outcome={outcome_index} price={price_val:.6f}")
                        # Send suppressed alert details to reports
                        try:
                            self.notifier.send_suppressed_alert_details(
                                reason="price_high",
                                condition_id=condition_id,
                                outcome_index=outcome_index,
                                wallets=wallets_in_window,
                                wallet_prices=wallet_prices,
                                market_title=market_title,
                                market_slug=market_slug,
                                current_price=current_price,
                                side=side,
                                total_usd=total_usd
                            )
                        except Exception as e:
                            logger.debug(f"Failed to send suppressed alert details: {e}")
                        return
                    logger.info(f"[PRICE CHECK] Price OK: {price_val:.6f}, allowing alert")
                else:
                    # Price is None - could mean API error or market not found
                    # BLOCK if price cannot be verified (fail-safe)
                    logger.warning(f"[SUPPRESS] BLOCKING: price is None for condition={condition_id} outcome={outcome_index} - cannot verify market status")
                    self.suppressed_counts['price_none'] = self.suppressed_counts.get('price_none', 0) + 1
                    # Send suppressed alert details to reports
                    try:
                        self.notifier.send_suppressed_alert_details(
                            reason="price_none",
                            condition_id=condition_id,
                            outcome_index=outcome_index,
                            wallets=wallets_in_window,
                            wallet_prices=wallet_prices,
                            market_title=market_title,
                            market_slug=market_slug,
                            current_price=None,
                            side=side,
                            total_usd=total_usd
                        )
                    except Exception as e:
                        logger.debug(f"Failed to send suppressed alert details: {e}")
                    return
            except (ValueError, TypeError) as e:
                logger.error(f"[SUPPRESS] BLOCKING: Error parsing price {current_price}: {e}, condition={condition_id}")
                # On parsing error, block to be safe
                self.suppressed_counts['price_check_error'] = self.suppressed_counts.get('price_check_error', 0) + 1
                # Send suppressed alert details to reports
                try:
                    self.notifier.send_suppressed_alert_details(
                        reason="price_check_error",
                        condition_id=condition_id,
                        outcome_index=outcome_index,
                        wallets=wallets_in_window,
                        wallet_prices=wallet_prices,
                        market_title=market_title,
                        market_slug=market_slug,
                        current_price=None,
                        side=side,
                        total_usd=total_usd
                    )
                except Exception as send_err:
                    logger.debug(f"Failed to send suppressed alert details: {send_err}")
                return
            
            # Final check: Verify market is still active before sending alert
            if not self.is_market_active(condition_id, outcome_index):
                self.suppressed_counts['market_closed'] = self.suppressed_counts.get('market_closed', 0) + 1
                logger.info(f"[SUPPRESS] market_closed (final check) condition={condition_id} outcome={outcome_index}")
                # Send suppressed alert details to reports
                try:
                    self.notifier.send_suppressed_alert_details(
                        reason="market_closed",
                        condition_id=condition_id,
                        outcome_index=outcome_index,
                        wallets=wallets_in_window,
                        wallet_prices=wallet_prices,
                        market_title=market_title,
                        market_slug=market_slug,
                        current_price=current_price,
                        side=side,
                        total_usd=total_usd
                    )
                except Exception as e:
                    logger.debug(f"Failed to send suppressed alert details: {e}")
                return

            # Dedupe/trigger rules using recent alerts
            recent = self.db.get_recent_alerts(condition_id, outcome_index, limit=3)
            if recent:
                last = recent[0]
                # Parse time delta
                try:
                    from datetime import datetime as _dt
                    last_ts = _dt.fromisoformat(last['sent_at']).replace(tzinfo=timezone.utc).timestamp()
                except Exception:
                    last_ts = time.time() - 999999
                minutes_since = (time.time() - last_ts) / 60.0
                last_wallets = int(last.get('wallet_count') or 0)
                last_price = float(last.get('price') or 0)
                same_outcome = (outcome_index == int(last.get('outcome_index') or outcome_index))
                price_change = 0.0
                if current_price and last_price:
                    price_change = abs(current_price - last_price) / max(1e-9, last_price)
                
                # Build set of wallets from last 3 alerts
                prev_wallets = set()
                for r in recent:
                    csv = r.get('wallets_csv') or ''
                    for w in csv.split(','):
                        w = w.strip()
                        if w:
                            prev_wallets.add(w)
                current_wallets_set = set(wallets_in_window)
                has_new_wallet = len(current_wallets_set - prev_wallets) > 0
                wallets_grew = len(wallets_in_window) > last_wallets
                outcome_changed = not same_outcome
                should_refresh_due_time = minutes_since > self.refresh_interval_min
                
                # Global ignore: within 30 minutes for the same market and same outcome
                if same_outcome and minutes_since < 30.0:
                    self.suppressed_counts['ignore_30m_same_outcome'] += 1
                    logger.info(f"[SUPPRESS] ignore_30m same outcome condition={condition_id} mins={minutes_since:.1f}")
                    # Send suppressed alert details to reports
                    try:
                        self.notifier.send_suppressed_alert_details(
                            reason="ignore_30m_same_outcome",
                            condition_id=condition_id,
                            outcome_index=outcome_index,
                            wallets=wallets_in_window,
                            wallet_prices=wallet_prices,
                            market_title=market_title,
                            market_slug=market_slug,
                            current_price=current_price,
                            side=side,
                            total_usd=total_usd
                        )
                    except Exception as e:
                        logger.debug(f"Failed to send suppressed alert details: {e}")
                    return
                # Legacy ignore if within 10 min and none of the triggers met
                if minutes_since < 10.0 and same_outcome and (not wallets_grew) and (price_change < 0.01):
                    self.suppressed_counts['dedupe_no_growth_10m'] += 1
                    logger.info(f"[SUPPRESS] dedupe_no_growth_10m condition={condition_id}")
                    # Send suppressed alert details to reports
                    try:
                        self.notifier.send_suppressed_alert_details(
                            reason="dedupe_no_growth_10m",
                            condition_id=condition_id,
                            outcome_index=outcome_index,
                            wallets=wallets_in_window,
                            wallet_prices=wallet_prices,
                            market_title=market_title,
                            market_slug=market_slug,
                            current_price=current_price,
                            side=side,
                            total_usd=total_usd
                        )
                    except Exception as e:
                        logger.debug(f"Failed to send suppressed alert details: {e}")
                    return
                # Else proceed only if any trigger met
                if not (outcome_changed or wallets_grew or has_new_wallet or price_change >= 0.01 or should_refresh_due_time):
                    self.suppressed_counts['no_trigger_matched'] += 1
                    logger.info(f"[SUPPRESS] no_trigger_matched condition={condition_id}")
                    # Send suppressed alert details to reports
                    try:
                        self.notifier.send_suppressed_alert_details(
                            reason="no_trigger_matched",
                            condition_id=condition_id,
                            outcome_index=outcome_index,
                            wallets=wallets_in_window,
                            wallet_prices=wallet_prices,
                            market_title=market_title,
                            market_slug=market_slug,
                            current_price=current_price,
                            side=side,
                            total_usd=total_usd
                        )
                    except Exception as e:
                        logger.debug(f"Failed to send suppressed alert details: {e}")
                    return
            
            # Don't send if we recently alerted same market/side
            if self.db.has_recent_alert(condition_id, outcome_index, side, self.alert_cooldown_min):
                return
            # Don't send if there was an opposite-side alert recently (conflict avoidance)
            if self.db.has_recent_opposite_alert(condition_id, outcome_index, side, self.conflict_window_min):
                self.suppressed_counts['opposite_recent'] += 1
                logger.info(f"[SUPPRESS] opposite_recent condition={condition_id}")
                # Send suppressed alert details to reports
                try:
                    self.notifier.send_suppressed_alert_details(
                        reason="opposite_recent",
                        condition_id=condition_id,
                        outcome_index=outcome_index,
                        wallets=wallets_in_window,
                        wallet_prices=wallet_prices,
                        market_title=market_title,
                        market_slug=market_slug,
                        current_price=current_price,
                        side=side,
                        total_usd=total_usd
                    )
                except Exception as e:
                    logger.debug(f"Failed to send suppressed alert details: {e}")
                return

            # Send alert with prices and consensus flow (events per minute)
            alert_id = key[:8]
            success = self.notifier.send_consensus_alert(
                condition_id, outcome_index, wallets_in_window, wallet_prices,
                self.alert_window_min, self.min_consensus, alert_id, market_title, market_slug, side,
                consensus_events=len(window_data.get("events", [])),
                total_usd=total_usd
            )
            
            if success:
                # Collect wallet details (address, usd_amount, price) for saving
                wallet_details = []
                try:
                    events = window_data.get("events", [])
                    wallet_usd_map = {}  # wallet -> total USD
                    wallet_price_map = {}  # wallet -> entry price
                    
                    for event in events:
                        wallet = event.get("wallet", "")
                        if not wallet:
                            continue
                        
                        # Calculate USD for this event
                        usd = float(event.get("usd", 0) or 0)
                        quantity = float(event.get("quantity", 0) or 0)
                        price = float(event.get("price", 0) or 0)
                        
                        if usd == 0 and quantity > 0 and price > 0:
                            usd = quantity * price
                        
                        # Aggregate by wallet
                        if wallet not in wallet_usd_map:
                            wallet_usd_map[wallet] = 0.0
                            wallet_price_map[wallet] = price
                        
                        wallet_usd_map[wallet] += usd
                    
                    # Build wallet_details list
                    for wallet in wallets_in_window:
                        wallet_details.append({
                            "wallet": wallet,
                            "usd_amount": round(wallet_usd_map.get(wallet, 0.0), 2),
                            "price": round(wallet_price_map.get(wallet, 0.0), 4)
                        })
                    
                    wallet_details_json = json.dumps(wallet_details)
                    logger.info(f"Saved wallet details for {len(wallet_details)} wallets: {wallet_details_json[:200]}...")
                except Exception as e:
                    logger.warning(f"Error collecting wallet details: {e}")
                    wallet_details_json = ""
                
                # Mark alert as sent
                self.db.mark_alert_sent(
                    condition_id, outcome_index, len(wallets_in_window),
                    window_data["first_ts"], window_data["last_ts"], alert_key, side,
                    price=(current_price or 0.0), wallets_csv=",".join(wallets_in_window),
                    wallet_details_json=wallet_details_json
                )
                logger.info(f"Sent consensus alert for {condition_id}:{outcome_index} "
                           f"({len(wallets_in_window)} wallets)")
            
        except Exception as e:
            logger.error(f"Error checking consensus: {e}")
    
    def monitor_wallets(self):
        """Main monitoring loop"""
        logger.info("Starting wallet monitoring...")
        self.monitoring = True
        
        while self.monitoring:
            try:
                # Get tracked wallets - strict criteria: 75%+ win rate
                wallets = self.db.get_tracked_wallets(
                    min_trades=6, max_trades=self.max_predictions,
                    min_win_rate=0.75, max_win_rate=1.0,  # Increased to 75%
                    max_daily_freq=20.0, limit=self.max_wallets
                )
                
                if not wallets:
                    logger.warning("No wallets to monitor")
                    time.sleep(self.poll_interval)
                    continue
                
                self.loop_count += 1
                
                # Send heartbeat every 10 loops (every ~70 seconds with 7s poll interval)
                if self.loop_count % 10 == 0:
                    stats = self.db.get_wallet_stats()
                    queue_stats = self.wallet_analyzer.get_queue_status()
                    logger.info(f"Monitoring {len(wallets)} wallets, loop #{self.loop_count}")
                    logger.info(f"Queue status: {queue_stats}")
                    if self.telegram_heartbeat_enabled:
                        self.notifier.send_heartbeat(stats)
                # Send suppression diagnostics roughly hourly
                # ~514 loops ≈ 1 hour at 7s interval
                if self.loop_count % 514 == 0:
                    try:
                        self.notifier.send_suppression_report(self.suppressed_counts)
                        # reset after sending
                        for k in list(self.suppressed_counts.keys()):
                            self.suppressed_counts[k] = 0
                    except Exception as e:
                        logger.warning(f"Failed to send suppression report: {e}")
                
                # Heartbeat log every 30 seconds (every ~4 loops with 7s poll interval)
                if self.loop_count % 4 == 0:
                    stats = self.db.get_wallet_stats()
                    queue_stats = self.wallet_analyzer.get_queue_status()
                    now_iso = datetime.now(timezone.utc).isoformat()
                    
                    # Format: [HB] queue=447 analyzed=129 wallets=74 time=2025-01-01T12:01:33Z
                    queue_total = queue_stats.get('total_jobs', 0)
                    analyzed_count = stats.get('total_wallets', 0)
                    tracked_wallets = stats.get('tracked_wallets', 0)
                    
                    logger.info(f"[HB] queue={queue_total} analyzed={analyzed_count} wallets={tracked_wallets} time={now_iso}")
                
                # Collect new wallets from leaderboard if needed (every 20 loops)
                if self.loop_count % 20 == 0:
                    current_wallets = self.db.get_tracked_wallets(min_trades=6, max_trades=1000, min_win_rate=0.75, max_win_rate=1.0, max_daily_freq=20.0, limit=self.max_wallets)
                    if len(current_wallets) < self.max_wallets:
                        logger.info(f"Only {len(current_wallets)} wallets, collecting more...")
                        wallets_dict = asyncio.run(self.collect_wallets_from_leaderboards())
                        self.analyze_and_filter_wallets(wallets_dict)
                
                # Clean up old wallets every 50 loops
                if self.loop_count % 50 == 0:
                    self.db.cleanup_old_wallets(self.max_predictions, self.max_wallets)
                
                # Clean up expired cache every 100 loops
                if self.loop_count % 100 == 0:
                    cleaned = self.db.cleanup_expired_cache()
                    if cleaned > 0:
                        logger.info(f"Cleaned up {cleaned} expired cache entries")
                
                # Monitor each wallet
                for wallet in wallets:
                    try:
                        last_trade_id = self.db.get_last_seen_trade_id(wallet)
                        # Fetch BUY and SELL trades
                        buy_events, newest_buy_id = self.get_new_trades(wallet, last_trade_id, "BUY")
                        sell_events, newest_sell_id = self.get_new_trades(wallet, last_trade_id, "SELL")
                        new_events = buy_events + sell_events
                        newest_id = newest_buy_id or newest_sell_id
                        
                        if new_events:
                            logger.info(f"{wallet}: {len(new_events)} new events")
                        
                        # Process each new event (filter out old events to avoid processing closed markets)
                        current_time = time.time()
                        max_event_age_hours = 48  # Ignore events older than 48 hours
                        max_event_age_seconds = max_event_age_hours * 3600
                        
                        for event in new_events:
                            # Skip events that are too old (likely from closed markets)
                            event_timestamp = event.get("timestamp", 0)
                            if event_timestamp and event_timestamp > 0:
                                # Validate timestamp is reasonable
                                if event_timestamp < 946684800 or event_timestamp > current_time + 3600:
                                    logger.debug(f"Invalid timestamp {event_timestamp} for event {event.get('trade_id', 'unknown')[:12]}..., skipping")
                                    continue
                                
                                event_age = current_time - event_timestamp
                                if event_age < 0:
                                    logger.warning(f"Event {event.get('trade_id', 'unknown')[:12]}... has future timestamp (age: {event_age:.1f}s), skipping")
                                    continue
                                
                                if event_age > max_event_age_seconds:
                                    logger.info(f"Skipping old event: {event.get('trade_id', 'unknown')[:12]}... (age: {event_age/3600:.1f}h)")
                                    continue
                            elif not event_timestamp or event_timestamp <= 0:
                                logger.debug(f"Event {event.get('trade_id', 'unknown')[:12]}... has no valid timestamp, skipping")
                                continue
                            
                            market_title = event.get("marketTitle", "")
                            market_slug = event.get("marketSlug", "")
                            price = event.get("price", 0)
                            side = event.get("side", "BUY")
                            usd_amount = event.get("usd", 0.0)
                            quantity = event.get("quantity", 0.0)
                            condition_id = event["conditionId"]
                            outcome_index = event["outcomeIndex"]
                            
                            # EARLY CHECK: Verify market is still active before processing event
                            # This prevents creating suppressed alerts for already-closed markets
                            if not self.is_market_active(condition_id, outcome_index):
                                logger.debug(f"Skipping event for closed market: {condition_id[:20]}... outcome={outcome_index} (entry price was ${price:.3f})")
                                continue
                            
                            self.check_consensus_and_alert(
                                condition_id, outcome_index,
                                wallet, event["trade_id"], event["timestamp"], 
                                price, side, market_title, market_slug,
                                usd_amount=usd_amount, quantity=quantity
                            )
                        
                        # Update last seen trade ID (always update if we got trades, even if empty list)
                        if newest_id and newest_id != last_trade_id:
                            self.db.set_last_seen_trade_id(wallet, newest_id)
                        elif new_events and not newest_id:
                            # If we have events but no newest_id, log warning
                            logger.warning(f"{wallet}: Have {len(new_events)} events but newest_id is None")
                        
                        # Spread load across wallets
                        time.sleep(max(0.0, self.poll_interval / max(1, len(wallets))))
                        
                    except Exception as e:
                        logger.error(f"Error monitoring wallet {wallet}: {e}")
                        continue
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.poll_interval)
    
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.monitoring = False
        logger.info("Monitoring stopped")
    
    async def start_bet_monitoring(self):
        """Start bet monitoring in background"""
        logger.info("Starting bet monitoring...")
        
        # Get wallet addresses from database
        wallet_addresses = self.db.get_tracked_wallet_addresses()
        logger.info(f"Monitoring {len(wallet_addresses)} wallets for matching bets")
        
        # Initialize Telegram notifier for bet alerts
        bet_telegram_notifier = BetTelegramNotifier(self.telegram_token, self.telegram_chat_id)
        
        # Start monitoring in background task
        monitoring_task = asyncio.create_task(
            self.bet_detector.monitor_wallets(wallet_addresses, bet_telegram_notifier)
        )
        
        return monitoring_task

    async def run(self):
        """Main run method"""
        logger.info("Starting Polymarket Notifier Bot...")
        
        # Validate configuration
        if not self.validate_config():
            return
        
        # Test Telegram connection (skip if failed)
        if not self.notifier.test_connection():
            logger.warning("Telegram connection test failed - continuing without Telegram notifications")
            # Don't return, continue with wallet collection
        
        # Start wallet analyzer workers
        logger.info("Starting wallet analysis workers...")
        self.wallet_analyzer.start_workers()
        queue_stats = self.wallet_analyzer.get_queue_status()
        logger.info(f"Wallet analyzer workers started. Queue status: {queue_stats}")
        
        # Start bet monitoring
        bet_monitoring_task = await self.start_bet_monitoring()
        
        # Send startup notification
        stats = self.db.get_wallet_stats()
        queue_stats = self.wallet_analyzer.get_queue_status()
        self.notifier.send_startup_notification(
            stats.get('total_wallets', 0),
            stats.get('tracked_wallets', 0)
        )
        
        # Collect wallets from leaderboards
        wallets = await self.collect_wallets_from_leaderboards()
        if wallets:
            self.analyze_and_filter_wallets(wallets)
        
        # Start monitoring
        try:
            self.monitor_wallets()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, stopping...")
            self.stop_monitoring()
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.notifier.send_error_notification("System Error", str(e))
        finally:
            # Stop wallet analyzer workers
            self.wallet_analyzer.stop_workers()
            # Cancel bet monitoring task
            bet_monitoring_task.cancel()

def main():
    """Main entry point"""
    notifier = PolymarketNotifier()
    
    try:
        asyncio.run(notifier.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")

if __name__ == "__main__":
    main()