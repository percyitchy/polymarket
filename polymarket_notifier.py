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
from market_utils import classify_market
from wallet_analyzer import WalletAnalyzer, AnalysisConfig, WIN_RATE_THRESHOLD, MAX_DAILY_FREQUENCY, MIN_TRADES
from clickhouse_client import ClickHouseClient
try:
    from adj_news_client import AdjNewsClient, RateLimitExceeded as AdjNewsRateLimitExceeded
    ADJ_NEWS_AVAILABLE = True
except ImportError:
    ADJ_NEWS_AVAILABLE = False
    AdjNewsClient = None
    AdjNewsRateLimitExceeded = None
try:
    from bet_monitor import BetDetector, TelegramNotifier as BetTelegramNotifier
    BET_MONITOR_AVAILABLE = True
except Exception as e:
    print(f"Bet monitor not available: {e}")
    BET_MONITOR_AVAILABLE = False
    BetDetector = None
    BetTelegramNotifier = None
try:
    from polymarket_auth import PolymarketAuth
    POLYMARKET_AUTH_AVAILABLE = True
except Exception as e:
    print(f"Polymarket auth not available: {e}")
    POLYMARKET_AUTH_AVAILABLE = False
    PolymarketAuth = None
from proxy_manager import ProxyManager

# HashiDive API fallback (optional)
try:
    from hashdive_client import HashDiveClient
    HASHDIVE_AVAILABLE = True
    # Only use API key if explicitly set (not empty)
    hashdive_key = os.getenv("HASHDIVE_API_KEY", "").strip()
    HASHDIVE_API_KEY = hashdive_key if hashdive_key else None
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
        self.alert_window_min = self._get_env_float("ALERT_WINDOW_MIN", 20.0)
        self.alert_cooldown_min = self._get_env_float("ALERT_COOLDOWN_MIN", 30.0)  # 30 minutes cooldown to prevent spam
        self.conflict_window_min = self._get_env_float("ALERT_CONFLICT_WINDOW_MIN", 10.0)
        self.price_band = self._get_env_float("ALERT_PRICE_BAND", 0.02)
        self.refresh_interval_min = self._get_env_float("ALERT_REFRESH_MIN", 60.0)
        self.min_consensus = self._get_env_int("MIN_CONSENSUS", 3)  # Minimum wallets required
        if self.min_consensus < 2:
            logger.warning(f"min_consensus is {self.min_consensus}, forcing to 2")
            self.min_consensus = 2
        
        # Minimum total position size (in USDC)
        self.min_total_position_usd = self._get_env_float("MIN_TOTAL_POSITION_USD", 2000.0)
        
        self.max_wallets = self._get_env_int("MAX_WALLETS", 2000)
        # Log configuration at startup
        logger.info(
            f"[Config] MIN_CONSENSUS={self.min_consensus}, "
            f"MAX_WALLETS={self.max_wallets}, "
            f"ALERT_WINDOW_MIN={self.alert_window_min}, "
            f"ALERT_COOLDOWN_MIN={self.alert_cooldown_min} minutes, "
            f"MIN_TOTAL_POSITION_USD=${self.min_total_position_usd:.0f}"
        )
        logger.info(f"[CONFIG] Consensus / alert window: {self.alert_window_min} minutes")
        self.max_predictions = self._get_env_int("MAX_PREDICTIONS", 1000)
        self.db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
        # Resolve absolute path to ensure consistency
        if not os.path.isabs(self.db_path):
            self.db_path = os.path.abspath(self.db_path)
        logger.info(f"[DB] Using database at {self.db_path}")
        
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
        self.notifier = TelegramNotifier(
            self.telegram_token, 
            self.telegram_chat_id,
            hashdive_client=self.hashdive_client
        )
        
        # Initialize ClickHouse client
        self.clickhouse_client = ClickHouseClient()
        
        # Initialize AdjNewsClient for news correlation
        self.adj_news_client = None
        if ADJ_NEWS_AVAILABLE:
            try:
                adj_news_api_key = os.getenv("ADJ_NEWS_API_KEY", "").strip()
                if adj_news_api_key:
                    self.adj_news_client = AdjNewsClient(api_key=adj_news_api_key)
                    logger.info("[AdjNews] AdjNewsClient initialized successfully with API key")
                else:
                    self.adj_news_client = AdjNewsClient()
                    logger.info("[AdjNews] AdjNewsClient initialized without API key (lower rate limits)")
            except Exception as e:
                logger.warning(f"[AdjNews] Failed to initialize AdjNewsClient: {e}")
                self.adj_news_client = None
        
        # News correlation configuration
        news_correlation_enabled_str = os.getenv("NEWS_CORRELATION_ENABLED", "true").strip().lower()
        self.news_correlation_enabled = news_correlation_enabled_str in ("1", "true", "yes", "on")
        self.news_min_wallets_for_check = self._get_env_int("NEWS_MIN_WALLETS_FOR_CHECK", 4)
        self.news_min_a_list_for_check = self._get_env_int("NEWS_MIN_A_LIST_FOR_CHECK", 2)
        self.news_time_window_hours = self._get_env_float("NEWS_TIME_WINDOW_HOURS", 1.0)
        
        # Initialize news correlation tracking stats
        self.news_correlation_stats = {'total_checks': 0, 'news_found': 0, 'rate_limited': 0, 'errors': 0}
        
        # Log news correlation configuration
        if self.adj_news_client:
            rate_limit_status = self.adj_news_client.get_rate_limit_status()
            logger.info(
                f"[AdjNews] News correlation enabled: {self.news_correlation_enabled}, "
                f"min_wallets={self.news_min_wallets_for_check}, "
                f"min_a_list={self.news_min_a_list_for_check}, "
                f"time_window={self.news_time_window_hours}h, "
                f"daily_limit={rate_limit_status['daily_queries_limit']}/day"
            )
        else:
            logger.info("[AdjNews] News correlation disabled (AdjNewsClient not available)")
        
        # Open Interest and Whale Position monitoring configuration
        self.oi_spike_threshold_percent = self._get_env_float("OI_SPIKE_THRESHOLD_PERCENT", 20.0)
        self.whale_position_size_usd = self._get_env_float("WHALE_POSITION_SIZE_USD", 10000.0)
        self.oi_check_interval_min = self._get_env_float("OI_CHECK_INTERVAL_MIN", 5.0)
        
        # Order Flow Imbalance Detection configuration
        self.order_flow_imbalance_threshold = self._get_env_float("ORDER_FLOW_IMBALANCE_THRESHOLD", 0.70)
        self.order_flow_time_window_min = self._get_env_float("ORDER_FLOW_TIME_WINDOW_MIN", 15.0)
        self.order_flow_check_interval_min = self._get_env_float("ORDER_FLOW_CHECK_INTERVAL_MIN", 5.0)
        
        # Initialize tracking state
        self.last_oi_check_time = 0
        self.oi_check_stats = {'total_checks': 0, 'spikes_detected': 0, 'errors': 0}
        self.whale_check_stats = {'total_checks': 0, 'positions_detected': 0, 'errors': 0}
        self.last_order_flow_check_time = 0
        self.order_flow_stats = {'total_checks': 0, 'imbalances_detected': 0, 'errors': 0}
        
        logger.info(
            f"[Config] Order Flow: threshold={self.order_flow_imbalance_threshold:.2f}, "
            f"time_window={self.order_flow_time_window_min:.1f}min, "
            f"check_interval={self.order_flow_check_interval_min:.1f}min"
        )
        if BET_MONITOR_AVAILABLE:
            self.bet_detector = BetDetector(self.db_path)
        else:
            self.bet_detector = None
        
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
        
        # Initialize Polymarket API authentication (optional)
        if POLYMARKET_AUTH_AVAILABLE:
            self.polymarket_auth = PolymarketAuth()
        else:
            self.polymarket_auth = None
        
        # Initialize proxy manager (optional)
        self.proxy_manager = ProxyManager()
        
        # Headers for API requests
        self.headers = {
            "User-Agent": "PolymarketNotifier/1.0 (+https://polymarket.com)"
        }
        
        # Monitoring state
        self.monitoring = False
        self.loop_count = 0
        # Diagnostic counters for suppressed alerts
        self.suppressed_counts = {
            'cooldown': 0,
            'price_high': 0,
            'ignore_30m_same_outcome': 0,
            'dedupe_no_growth_10m': 0,
            'no_trigger_matched': 0,
            'opposite_recent': 0
        }
        
        # IMPORTANT: Log that we no longer extract market_slug from events
        # All slug normalization is now handled by notify.TelegramNotifier
        logger.warning(
            "[SLUG] ⚠️  IMPORTANT: market_slug extraction from events is DISABLED. "
            "All slug normalization is handled by notify.TelegramNotifier via "
            "_get_event_slug_and_market_id() and _get_market_slug(). "
            "Do not rely on event['marketSlug'] - it is often outcome-specific and incorrect."
        )
        # Diagnostic counters for errors
        self.error_counts = {
            'retry_error': 0,
            'http_error': 0,
            'timeout': 0,
            'connection_error': 0,
            'json_error': 0,
            'other_error': 0
        }
        
        # Insider detection statistics
        self.insider_stats = {
            'total_detected': 0,
            'by_reason': {}
        }
        
    def validate_config(self) -> bool:
        """Validate configuration and environment variables"""
        if not self.telegram_token or not self.telegram_chat_id:
            logger.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env file")
            return False
        
        logger.info("Configuration validated successfully")
        return True
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def http_get(self, url: str, params: Optional[Dict[str, Any]] = None, *, allow_404_as_none: bool = False) -> Any:
        """
        Make HTTP GET request with retry logic and optional authentication.
        
        Args:
            url: Request URL
            params: Query parameters
            allow_404_as_none: If True, return None for 404 instead of response object (for closed markets)
        
        Returns:
            Response object on success, None if allow_404_as_none=True and status is 404, raises exception on other errors
        """
        import requests
        import time
        import urllib3
        
        # Disable SSL warnings for proxy connections
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        headers = self.headers.copy()
        
        # Get proxy if available
        proxy = self.proxy_manager.get_proxy(rotate=True) if self.proxy_manager.proxy_enabled else None
        
        # Add proxy-specific headers for HTTP proxies with IP rotation
        if proxy:
            headers['Connection'] = 'close'  # Avoid connection reuse issues with rotating proxies
            headers['Proxy-Connection'] = 'close'
        
        try:
            # Use verify=False for proxies that might have SSL issues
            response = requests.get(url, params=params, headers=headers, timeout=20, proxies=proxy, verify=False)
            
            # Log non-200 status codes with detailed information
            if response.status_code != 200:
                # Extract response body preview for logging (first 300-500 chars)
                response_preview = ""
                try:
                    if hasattr(response, 'text') and response.text:
                        response_preview = response.text[:500]
                    elif hasattr(response, 'content') and response.content:
                        response_preview = str(response.content[:500])
                except Exception:
                    response_preview = "(unable to read response body)"
                
                # Handle 404 specifically
                if response.status_code == 404:
                    if allow_404_as_none:
                        logger.info(f"[HTTP] 404 Not Found for URL {url[:100]}... — treating as None (likely closed/invalid market)")
                        if params:
                            logger.debug(f"[HTTP] Request params: {params}")
                        return None
                    else:
                        logger.warning(f"[HTTP] 404 Not Found for URL {url[:100]}...")
                        if params:
                            logger.warning(f"[HTTP] Request params: {params}")
                        logger.debug(f"[HTTP] Response preview: {response_preview[:300]}")
                        return response
                
                # Handle 429 Rate Limit specifically
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After')
                    logger.warning(f"[HTTP] Rate limited (429) for URL {url[:100]}...")
                    if params:
                        logger.warning(f"[HTTP] Request params: {params}")
                    if retry_after:
                        try:
                            wait_seconds = int(retry_after)
                            if wait_seconds <= 0:
                                wait_seconds = 5  # Minimum 5 seconds even if server says 0
                            logger.warning(f"[HTTP] Waiting {wait_seconds}s as requested by server")
                            time.sleep(wait_seconds)
                            # Rotate proxy on retry if available
                            if self.proxy_manager.proxy_enabled:
                                proxy = self.proxy_manager.get_proxy(rotate=True)
                                logger.debug(f"[HTTP] Rotating proxy for retry")
                            # Retry once after waiting
                            response = requests.get(url, params=params, headers=headers, timeout=20, proxies=proxy, verify=False)
                            if response.status_code == 200:
                                logger.info(f"[HTTP] Retry successful after rate limit wait")
                                return response
                            if response.status_code == 429:
                                logger.warning(f"[HTTP] Still rate limited after waiting {wait_seconds}s, using exponential backoff")
                        except (ValueError, TypeError):
                            pass
                    # Fallback: exponential backoff (minimum 5 seconds)
                    logger.warning(f"[HTTP] Rate limited (429) for {url[:100]}..., using exponential backoff")
                    self.error_counts['rate_limit'] = self.error_counts.get('rate_limit', 0) + 1
                    raise requests.exceptions.HTTPError(f"429 Rate Limit: {response_preview[:200]}")
                
                # Log other non-200 status codes with details
                logger.warning(f"[HTTP] Non-200 status {response.status_code} for URL {url[:100]}...")
                if params:
                    logger.warning(f"[HTTP] Request params: {params}")
                logger.debug(f"[HTTP] Response preview: {response_preview[:300]}")
            
            # Success - raise for status to catch any other errors
            response.raise_for_status()
            return response
            
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if hasattr(e, 'response') and e.response else 'unknown'
            error_preview = ""
            try:
                if hasattr(e, 'response') and e.response:
                    error_preview = e.response.text[:300] if hasattr(e.response, 'text') else str(e.response.content[:300])
            except Exception:
                pass
            logger.error(f"[HTTP] HTTPError {status_code} in http_get: {url[:100]}...", exc_info=True)
            if params:
                logger.error(f"[HTTP] Request params: {params}")
            if error_preview:
                logger.error(f"[HTTP] Error response preview: {error_preview}")
            self.error_counts['http_error'] += 1
            raise
        except requests.exceptions.Timeout as e:
            logger.error(f"[HTTP] Timeout error in http_get: {url[:100]}...", exc_info=True)
            if params:
                logger.error(f"[HTTP] Request params: {params}")
            self.error_counts['timeout'] += 1
            raise
        except requests.exceptions.ProxyError as e:
            error_msg = str(e)
            logger.warning(f"[HTTP] Proxy error in http_get: {type(e).__name__} - {url[:100]}...")
            logger.debug(f"[HTTP] Proxy error details: {error_msg[:200]}")
            self.error_counts['proxy_error'] = self.error_counts.get('proxy_error', 0) + 1
            # If proxy fails, try without proxy as fallback
            if proxy and self.proxy_manager.proxy_enabled:
                logger.warning(f"[HTTP] Proxy failed, retrying without proxy for {url[:100]}...")
                try:
                    # Remove proxy-specific headers for direct connection
                    direct_headers = self.headers.copy()
                    response = requests.get(url, params=params, headers=direct_headers, timeout=20, verify=False)
                    if response.status_code == 200:
                        logger.info(f"[HTTP] Fallback successful: direct connection worked for {url[:100]}...")
                        return response
                    else:
                        logger.warning(f"[HTTP] Fallback returned status {response.status_code}")
                except Exception as fallback_error:
                    logger.error(f"[HTTP] Fallback request also failed: {fallback_error}", exc_info=True)
            raise
        except requests.exceptions.ConnectionError as e:
            error_msg = str(e).lower()
            logger.error(f"[HTTP] Connection error in http_get: {type(e).__name__} - {url[:100]}...", exc_info=True)
            if params:
                logger.error(f"[HTTP] Request params: {params}")
            # Check if this is a proxy-related connection error
            if proxy and self.proxy_manager.proxy_enabled and ("socks" in error_msg or "proxy" in error_msg or "connection not allowed" in error_msg):
                logger.warning(f"[HTTP] Proxy connection failed, retrying without proxy for {url[:100]}...")
                try:
                    direct_headers = self.headers.copy()
                    response = requests.get(url, params=params, headers=direct_headers, timeout=20, verify=False)
                    if response.status_code == 200:
                        logger.info(f"[HTTP] Fallback successful: direct connection worked for {url[:100]}...")
                        return response
                    else:
                        logger.warning(f"[HTTP] Fallback returned status {response.status_code}")
                except Exception as fallback_error:
                    logger.error(f"[HTTP] Fallback request also failed: {fallback_error}", exc_info=True)
            
            self.error_counts['connection_error'] += 1
            raise
        except Exception as e:
            logger.error(f"[HTTP] Unexpected error in http_get: {type(e).__name__} - {url[:100]}...", exc_info=True)
            if params:
                logger.error(f"[HTTP] Request params: {params}")
            raise

    def _get_current_price(self, condition_id: str, outcome_index: int,
                          wallet_prices: Optional[Dict[str, float]] = None,
                          slug: Optional[str] = None) -> Optional[float]:
        """
        Get current price for market outcome with multi-level fallback:
        1. New price_fetcher module (Polymarket CLOB /price, HashiDive, trades history, FinFeed)
        2. Legacy CLOB API /markets endpoint
        3. HashiDive API (if available, legacy method)
        4. Average price from wallet_prices (if provided)
        5. Polymarket data-api (last resort)
        
        Args:
            slug: Slug parameter (optional). Should be market-level slug, cleaned and normalized.
                  Only pass if slug is known to be market-level and suitable for Gamma /events API.
                  If uncertain, pass None and price_fetcher will use condition_id fallback.
        
        Returns float on success, None on failure. Never raises exceptions.
        """
        # Step 0: Try new price_fetcher module (with all fallbacks, including wallet_prices)
        try:
            from price_fetcher import get_current_price as fetch_price
            logger.info(f"[Price] Trying price_fetcher module with wallet_prices fallback (provided {len(wallet_prices) if wallet_prices else 0} wallets)")
            # CRITICAL: Only pass slug if it's cleaned and market-level (not market-specific)
            # Since we no longer extract slugs from events, slug will typically be None here
            # If slug is provided, it should already be cleaned and validated by the caller
            cleaned_slug_for_price = slug  # Pass as-is if provided (caller should have cleaned it)
            result = fetch_price(condition_id=condition_id, outcome_index=outcome_index, wallet_prices=wallet_prices, slug=cleaned_slug_for_price)
            # Обработка tuple (цена, источник) или просто цена (для обратной совместимости)
            if isinstance(result, tuple):
                price, source = result
            else:
                price = result
            if price is not None:
                logger.info(f"[Price] ✅ Got price from price_fetcher module: {price:.6f}")
                return price
            else:
                logger.debug(f"[Price] price_fetcher module returned None")
        except ImportError:
            logger.warning("[Price] ⚠️  price_fetcher module not available, using legacy methods")
        except Exception as e:
            logger.warning(f"[Price] ⚠️  price_fetcher failed: {type(e).__name__}: {e}")
        
        # Step 1: Try legacy CLOB API /markets endpoint (primary method)
        try:
            url = f"https://clob.polymarket.com/markets/{condition_id}"
            resp = self.http_get(url)
            
            # Handle None response or missing status_code
            if resp is None:
                logger.debug(f"[Price] CLOB API returned None for condition_id={condition_id[:20]}...")
            elif not hasattr(resp, 'status_code'):
                logger.debug(f"[Price] CLOB API response missing status_code for condition_id={condition_id[:20]}...")
            # Handle 404 - market not found (closed/removed)
            elif resp.status_code == 404:
                logger.debug(f"[Price] CLOB API returned 404 for condition_id={condition_id[:20]}... (market not found - likely closed)")
                # Don't try other methods if market doesn't exist
                return None
            elif resp.status_code == 200:
                data = resp.json()
                tokens = data.get('tokens') or []
                if tokens and outcome_index < len(tokens):
                    token = tokens[outcome_index]
                    for key in ("last_price", "price", "mark_price"):
                        val = token.get(key)
                        if isinstance(val, (int, float)):
                            price = float(val)
                            logger.debug(f"[Price] Got price from CLOB API token[{outcome_index}].{key}: {price}")
                            return price
                # Fallback to market-level fields if present
                for key in ("price", "last_price", "mark_price"):
                    val = data.get(key)
                    if isinstance(val, (int, float)):
                        price = float(val)
                        logger.debug(f"[Price] Got price from CLOB API market.{key}: {price}")
                        return price
            else:
                logger.debug(f"[Price] CLOB API returned status {resp.status_code if hasattr(resp, 'status_code') else 'unknown'} for condition_id={condition_id[:20]}...")
        except Exception as e:
            logger.debug(f"[Price] CLOB API failed: {type(e).__name__}: {e}")
        
        # Step 2: Try HashiDive API (if available, legacy method)
        if self.hashdive_client:
            try:
                # HashiDive uses asset_id (token ID) format: condition_id:outcome_index
                asset_id = f"{condition_id}:{outcome_index}"
                price_data = self.hashdive_client.get_last_price(asset_id)
                if price_data and isinstance(price_data, dict):
                    price = price_data.get('price') or price_data.get('last_price')
                    if price is not None:
                        try:
                            price_float = float(price)
                            logger.debug(f"[Price] Got price from HashiDive (legacy): {price_float}")
                            return price_float
                        except (ValueError, TypeError):
                            pass
            except Exception as e:
                logger.debug(f"[Price] HashiDive API failed: {e}")
        
        # Step 3: Try average price from wallet_prices (if provided)
        if wallet_prices:
            logger.info(f"[Price] [Legacy Step 3] Trying wallet_prices fallback (provided {len(wallet_prices)} wallet prices)...")
            logger.info(f"[Price] [Legacy Step 3] wallet_prices content: {wallet_prices}")
            try:
                prices = [p for p in wallet_prices.values() if isinstance(p, (int, float)) and p > 0]
                logger.info(f"[Price] [Legacy Step 3] Valid prices extracted: {prices} (from {len(wallet_prices)} total)")
                if prices:
                    avg_price = sum(prices) / len(prices)
                    logger.info(f"[Price] ✅ [Legacy] Got average price from wallet_prices: {avg_price:.3f} (from {len(prices)} wallets)")
                    return avg_price
                else:
                    logger.warning(f"[Price] [Legacy Step 3] ❌ wallet_prices provided ({len(wallet_prices)} entries) but no valid prices found after filtering")
                    logger.warning(f"[Price] [Legacy Step 3] wallet_prices values: {list(wallet_prices.values())}")
            except Exception as e:
                logger.error(f"[Price] [Legacy Step 3] ❌ Failed to calculate average from wallet_prices: {type(e).__name__}: {e}")
                import traceback
                logger.error(f"[Price] [Legacy Step 3] Traceback: {traceback.format_exc()}")
        else:
            logger.warning(f"[Price] [Legacy Step 3] ⚠️  wallet_prices not provided, skipping fallback")
        
        # Step 4: Try Polymarket data-api (last resort)
        try:
            url = f"https://data-api.polymarket.com/markets/{condition_id}"
            resp = self.http_get(url)
            if resp is not None and hasattr(resp, 'status_code') and resp.status_code == 200:
                data = resp.json()
                # Try to find price in data-api response
                tokens = data.get('tokens') or data.get('outcomes') or []
                if tokens and outcome_index < len(tokens):
                    token = tokens[outcome_index]
                    for key in ("last_price", "price", "mark_price", "current_price"):
                        val = token.get(key)
                        if val is not None:
                            try:
                                price = float(val)
                                logger.debug(f"[Price] Got price from data-api: {price}")
                                return price
                            except (ValueError, TypeError):
                                continue
        except Exception as e:
            logger.debug(f"[Price] data-api failed: {e}")
        
        # All methods failed
        logger.warning(f"[Price] All price lookup methods failed for condition_id={condition_id}, outcome={outcome_index}")
        return None
    
    async def collect_wallets_from_polymarket_analytics(self, limit: int = 2000) -> tuple[Dict[str, Dict[str, str]], Dict[str, int]]:
        """
        Collect wallet addresses from polymarketanalytics.com
        
        Returns:
            Tuple of (wallets dict, stats dict)
        """
        logger.info(f"Collecting wallets from polymarketanalytics.com (limit: {limit})...")
        wallets = {}
        stats = {
            "total_traders": 0,
            "missing_stats": 0,
            "below_trades": 0,
            "below_winrate": 0,
            "above_freq": 0,
            "meets_all": 0
        }
        
        try:
            from fetch_polymarket_analytics_api import fetch_traders_from_api, MIN_TRADES, MIN_WIN_RATE, MAX_DAILY_FREQ
            
            # Fetch addresses from API with statistics
            # IMPORTANT: Run in executor to avoid blocking event loop
            # fetch_traders_from_api is synchronous, so we run it in executor
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: fetch_traders_from_api(target=limit, return_stats=True)
            )
            # fetch_traders_from_api always returns a list (never None), so unpacking is safe
            if isinstance(result, tuple):
                addresses, api_stats = result
                stats.update(api_stats)
            else:
                # Fallback if return_stats=False (shouldn't happen, but be safe)
                addresses = result if result else []
                api_stats = {}
            
            if addresses:
                logger.info(f"Got {len(addresses)} addresses from polymarketanalytics.com")
                
                # Convert to expected format and log to raw_collected_wallets
                for addr in addresses:
                    addr_lower = addr.lower()
                    wallets[addr_lower] = {
                        "display": addr_lower,
                        "source": "polymarket_analytics"
                    }
                    # Log to raw_collected_wallets
                    self.db.insert_raw_collected_wallet(addr_lower, "polymarket_analytics")
                
                logger.info(f"Collected {len(wallets)} unique wallets from polymarketanalytics.com")
                
                # Log detailed statistics
                logger.info(
                    "[Analytics] Filtering stats: total=%d, meets_all=%d, "
                    "below_trades=%d, below_winrate=%d, above_freq=%d, missing_stats=%d "
                    "(MIN_TRADES=%d, MIN_WIN_RATE=%.2f, MAX_DAILY_FREQ=%.1f)",
                    stats["total_traders"], stats["meets_all"],
                    stats["below_trades"], stats["below_winrate"], stats["above_freq"], stats["missing_stats"],
                    MIN_TRADES, MIN_WIN_RATE, MAX_DAILY_FREQ
                )
            else:
                logger.warning("No addresses fetched from polymarketanalytics.com")
                
        except Exception as e:
            logger.error(f"Error collecting wallets from polymarketanalytics.com: {e}")
        
        return wallets, stats
    
    async def collect_wallets_from_hashdive_trader_explorer(self) -> Dict[str, Dict[str, str]]:
        """Collect wallet addresses from HashiDive Trader Explorer page"""
        wallets = {}
        
        try:
            logger.info("[HashiDive] Collecting wallets from Trader Explorer...")
            
            # Import scraper
            try:
                from fetch_hashdive_trader_explorer import scrape_trader_explorer
            except ImportError:
                logger.warning("[HashiDive] Trader Explorer scraper not available (Playwright required)")
                return wallets
            
            # Scrape addresses
            # Get max_pages from environment or use default
            max_pages = int(os.getenv("HASHDIVE_TRADER_EXPLORER_MAX_PAGES", "100"))
            addresses = await scrape_trader_explorer(
                url="https://hashdive.com/Trader_explorer",
                max_pages=max_pages,
                use_proxy=True,
                headless=True,
                delay_between_pages=2.0
            )
            
            logger.info(f"[HashiDive] Found {len(addresses)} unique addresses from Trader Explorer")
            
            # Convert to wallets dict
            for addr in addresses:
                addr_lower = addr.lower()
                wallets[addr_lower] = {
                    "display": addr_lower,
                    "source": "hashdive_trader_explorer"
                }
                self.db.insert_raw_collected_wallet(addr_lower, "hashdive_trader_explorer")
            
            logger.info(f"[HashiDive] Added {len(wallets)} wallets from Trader Explorer")
            
        except Exception as e:
            logger.error(f"[HashiDive] Error collecting from Trader Explorer: {e}")
        
        return wallets
    
    async def collect_wallets_from_hashdive_whales(self, min_usd: int = 5000, limit: int = 200) -> Dict[str, Dict[str, str]]:
        """Collect wallet addresses from HashiDive whale trades"""
        wallets = {}
        
        if not self.hashdive_client:
            logger.debug("HashiDive client not available, skipping whale trades collection")
            return wallets
        
        try:
            logger.info(f"[HashiDive] Collecting whale wallets (min ${min_usd:,}, limit {limit})...")
            
            # Check API usage first
            try:
                usage = self.hashdive_client.get_api_usage()
                credits_used = usage.get('credits_used', 0)
                credits_limit = usage.get('credits_limit', 1000)
                remaining = credits_limit - credits_used
                logger.info(f"[HashiDive] API credits: {credits_used}/{credits_limit} used, {remaining} remaining")
                
                if remaining < 10:
                    logger.warning(f"[HashiDive] Low credits remaining ({remaining}), skipping whale trades collection")
                    return wallets
            except Exception as e:
                logger.warning(f"[HashiDive] Could not check API usage: {e}, proceeding anyway...")
            
            # Get whale trades
            hashdive_data = self.hashdive_client.get_latest_whale_trades(
                min_usd=min_usd,
                limit=limit
            )
            
            # Parse response (can be dict with 'results' or list)
            if isinstance(hashdive_data, dict):
                results = hashdive_data.get('results', hashdive_data.get('data', []))
            elif isinstance(hashdive_data, list):
                results = hashdive_data
            else:
                results = []
            
            logger.info(f"[HashiDive] Found {len(results)} whale trades")
            
            # Extract unique wallet addresses
            for trade in results:
                user = trade.get('user_address') or trade.get('user') or trade.get('wallet')
                if user:
                    addr_lower = user.lower()
                    if addr_lower not in wallets:
                        wallets[addr_lower] = {
                            "display": addr_lower,
                            "source": "hashdive_whale"
                        }
                        self.db.insert_raw_collected_wallet(addr_lower, "hashdive_whale")
            
            logger.info(f"[HashiDive] Extracted {len(wallets)} unique whale wallets")
            
        except Exception as e:
            logger.error(f"[HashiDive] Error collecting whale wallets: {e}")
        
        return wallets
    
    async def collect_wallets_from_leaderboards(self) -> Dict[str, Dict[str, str]]:
        """Collect wallet addresses from multiple sources: polymarketanalytics.com, HTML leaderboards, HashiDive whales, and optional API scraper"""
        logger.info("=" * 80)
        logger.info("[COLLECTION] Starting wallet collection from all sources...")
        logger.info("=" * 80)
        
        all_wallets = {}
        analytics_stats = {
            "total_traders": 0,
            "missing_stats": 0,
            "below_trades": 0,
            "below_winrate": 0,
            "above_freq": 0,
            "meets_all": 0
        }
        
        # Step 1: Collect from polymarketanalytics.com
        analytics_wallets = {}
        try:
            logger.info("[COLLECTION] Step 1: Collecting from polymarketanalytics.com...")
            analytics_wallets, analytics_stats = await self.collect_wallets_from_polymarket_analytics(limit=2500)
            all_wallets.update(analytics_wallets)
            logger.info(f"[COLLECTION] ✅ Analytics: collected {len(analytics_wallets)} wallets from polymarketanalytics.com")
            for addr_lower in analytics_wallets.keys():
                self.db.insert_raw_collected_wallet(addr_lower, "polymarket_analytics")
        except Exception as e:
            logger.error(f"[COLLECTION] ❌ Error collecting from polymarketanalytics.com: {e}", exc_info=True)
        
        # Step 1.5: Collect from HashiDive whale trades (if enabled and API key available)
        hashdive_wallets = {}
        if self.hashdive_client and os.getenv("ENABLE_HASHDIVE_WHALES", "false").strip().lower() in ("true", "1", "yes", "on"):
            try:
                logger.info("[COLLECTION] Step 1.5: Collecting from HashiDive whale trades...")
                hashdive_wallets = await self.collect_wallets_from_hashdive_whales(min_usd=5000, limit=200)
                all_wallets.update(hashdive_wallets)
                logger.info(f"[COLLECTION] ✅ HashiDive Whales: collected {len(hashdive_wallets)} wallets")
            except Exception as e:
                logger.error(f"[COLLECTION] ❌ Error collecting from HashiDive whales: {e}", exc_info=True)
        
        # Step 1.6: Collect from HashiDive Trader Explorer (if enabled)
        hashdive_explorer_wallets = {}
        if os.getenv("ENABLE_HASHDIVE_TRADER_EXPLORER", "false").strip().lower() in ("true", "1", "yes", "on"):
            try:
                logger.info("[COLLECTION] Step 1.6: Collecting from HashiDive Trader Explorer...")
                hashdive_explorer_wallets = await self.collect_wallets_from_hashdive_trader_explorer()
                all_wallets.update(hashdive_explorer_wallets)
                logger.info(f"[COLLECTION] ✅ HashiDive Explorer: collected {len(hashdive_explorer_wallets)} wallets")
            except Exception as e:
                logger.error(f"[COLLECTION] ❌ Error collecting from HashiDive Trader Explorer: {e}", exc_info=True)
        
        # Step 2: ALWAYS parse HTML leaderboards (weekly + monthly, 20 pages each)
        leaderboard_wallets = {}
        try:
            logger.info("[COLLECTION] Step 2: Collecting from HTML leaderboards...")
            # Ensure leaderboard_urls are set (should be set by daily_wallet_analysis.py)
            if not hasattr(self, 'leaderboard_urls') or not self.leaderboard_urls:
                logger.warning("leaderboard_urls not set, using default weekly/monthly URLs")
                self.leaderboard_urls = [
                    "https://polymarket.com/leaderboard/overall/weekly/profit",
                    "https://polymarket.com/leaderboard/overall/monthly/profit"
                ]
            
            logger.info(f"[COLLECTION] Parsing {len(self.leaderboard_urls)} leaderboard URLs (max 30 pages each)")
            
            # Always use Playwright scraper for HTML leaderboards
            if PLAYWRIGHT_AVAILABLE:
                leaderboard_wallets = await scrape_polymarket_leaderboards(
                    self.leaderboard_urls,
                    headless=True,
                    max_pages_per_url=30,  # Up to 30 pages per URL (as configured in fetch_leaderboards.py)
                    use_proxy=True
                )
            else:
                # Fallback to enhanced requests scraper if Playwright not available
                logger.warning("Playwright not available, using enhanced requests scraper for leaderboards")
                try:
                    from fetch_leaderboards_enhanced import scrape_polymarket_leaderboards_enhanced
                    leaderboard_wallets = scrape_polymarket_leaderboards_enhanced(
                        self.leaderboard_urls,
                        max_pages_per_url=20
                    )
                except ImportError:
                    logger.error("Neither Playwright nor enhanced scraper available for leaderboards")
                    leaderboard_wallets = {}
            
            # Merge leaderboard wallets into all_wallets and log to raw_collected_wallets
            for addr, info in leaderboard_wallets.items():
                addr_lower = addr.lower()
                # Log to raw_collected_wallets
                self.db.insert_raw_collected_wallet(addr_lower, "leaderboards_html")
                if addr_lower not in all_wallets:
                    all_wallets[addr_lower] = {
                        "display": info.get("display", addr_lower),
                        "source": info.get("source", "leaderboards_html")
                    }
            
            logger.info(f"[COLLECTION] ✅ Leaderboards HTML: collected {len(leaderboard_wallets)} wallets from {len(self.leaderboard_urls)} URLs")
        except Exception as e:
            logger.error(f"[COLLECTION] ❌ Error parsing HTML leaderboards: {e}", exc_info=True)
            # Continue even if leaderboard parsing fails - we still have analytics wallets
        
        # Step 3: Optionally add wallets from Polymarket API scraper (additional source, not fallback)
        api_wallet_addresses = []
        try:
            logger.info("[COLLECTION] Step 3: Collecting from Polymarket API scraper...")
            from api_scraper import PolymarketAPIScraper
            
            async with PolymarketAPIScraper() as scraper:
                api_wallet_addresses = await scraper.scrape_all_wallets()
            
            # Add API wallets to all_wallets (avoid duplicates) and log to raw_collected_wallets
            api_added_count = 0
            for addr in api_wallet_addresses:
                addr_lower = addr.lower()
                # Log to raw_collected_wallets
                self.db.insert_raw_collected_wallet(addr_lower, "polymarket_api")
                if addr_lower not in all_wallets:
                    all_wallets[addr_lower] = {
                        "display": addr_lower,
                        "source": "polymarket_api"
                    }
                    api_added_count += 1
            
            logger.info(f"[COLLECTION] ✅ API Scraper: collected {len(api_wallet_addresses)} wallets (added {api_added_count} new)")
        except ImportError:
            logger.debug("[COLLECTION] PolymarketAPIScraper not available, skipping")
        except Exception as e:
            logger.warning(f"[COLLECTION] ❌ Error collecting from Polymarket API scraper: {e}", exc_info=True)
            # Continue - HTML leaderboards already worked, so this is not critical
        
        # Final summary
        logger.info("=" * 80)
        logger.info(f"[COLLECTION] 📊 FINAL SUMMARY: Total unique wallets from all sources: {len(all_wallets)}")
        logger.info(f"[COLLECTION] Breakdown:")
        logger.info(f"[COLLECTION]   - Analytics: {len(analytics_wallets)}")
        logger.info(f"[COLLECTION]   - Leaderboards HTML: {len(leaderboard_wallets)}")
        logger.info(f"[COLLECTION]   - HashiDive Whales: {len(hashdive_wallets)}")
        logger.info(f"[COLLECTION]   - HashiDive Explorer: {len(hashdive_explorer_wallets)}")
        logger.info(f"[COLLECTION]   - API Scraper: {len(api_wallet_addresses)}")
        logger.info("=" * 80)
        
        # Store analytics_stats for later use in analyze_and_filter_wallets
        self._last_analytics_stats = analytics_stats
        
        return all_wallets
    
    
    def analyze_and_filter_wallets(self, wallets: Dict[str, Dict[str, str]], 
                                   analytics_stats: Optional[Dict[str, int]] = None) -> int:
        """
        Add wallets to analysis queue instead of analyzing directly
        
        Args:
            wallets: Dictionary of wallets to add
            analytics_stats: Optional statistics from analytics API filtering
        """
        logger.info("=" * 80)
        logger.info(f"[FILTER] Starting wallet filtering process...")
        logger.info(f"[FILTER] Input: {len(wallets)} wallets to analyze")
        logger.info("=" * 80)
        
        # Get initial stats
        initial_stats = self.db.get_wallet_stats()
        initial_tracked = initial_stats.get('tracked_wallets', 0)
        initial_total = initial_stats.get('total_wallets', 0)
        
        logger.info(f"[FILTER] Current database state: {initial_total} total wallets, {initial_tracked} tracked")
        
        # Add wallets to queue
        added_count = self.wallet_analyzer.add_wallets_to_queue(wallets)
        
        # Get queue status
        queue_status = self.wallet_analyzer.get_queue_status()
        
        logger.info(f"[FILTER] ✅ Added {added_count} new wallets to analysis queue")
        logger.info(f"[FILTER] Queue status: {queue_status}")
        
        # Prepare criteria for summary
        from wallet_analyzer import MIN_TRADES, WIN_RATE_THRESHOLD, MAX_DAILY_FREQUENCY
        criteria = {
            "method": "queue_based",
            "min_trades": MIN_TRADES,
            "min_win_rate": WIN_RATE_THRESHOLD,
            "max_daily_freq": MAX_DAILY_FREQUENCY
        }
        
        logger.info(f"[FILTER] Filter criteria:")
        logger.info(f"[FILTER]   - MIN_TRADES: {MIN_TRADES}")
        logger.info(f"[FILTER]   - WIN_RATE_THRESHOLD: {WIN_RATE_THRESHOLD:.1%}")
        logger.info(f"[FILTER]   - MAX_DAILY_FREQUENCY: {MAX_DAILY_FREQUENCY}")
        
        # Add analytics stats if available
        if analytics_stats:
            criteria["analytics_stats"] = analytics_stats
            logger.info(f"[FILTER] Analytics pre-filter stats: {analytics_stats}")
        
        # Send summary notification
        self.notifier.send_wallet_collection_summary(
            len(wallets), added_count, criteria
        )
        
        logger.info("=" * 80)
        logger.info(f"[FILTER] Filtering process started. Wallets will be analyzed by workers.")
        logger.info(f"[FILTER] Monitor queue status to see filtering progress.")
        logger.info("=" * 80)
        
        return added_count
    
    def get_new_trades(self, address: str, last_seen_trade_id: Optional[str], side: str = "BUY") -> tuple[List[Dict[str, Any]], Optional[str]]:
        """Get new trades for a wallet filtered by side (BUY/SELL), with HashiDive fallback"""
        try:
            params = {"user": address, "side": side, "limit": 50}
            response = self.http_get(self.trades_endpoint, params=params)
            
            # Check if response is None or invalid - will fall through to HashiDive fallback below
            if response is None:
                logger.warning(f"[TRADES] HTTP call returned None for address={address[:12]}... side={side}, trying HashiDive fallback")
                trades = []  # Will trigger HashiDive fallback below
            elif not hasattr(response, 'ok'):
                logger.error(f"[TRADES] Invalid response type for address={address[:12]}... side={side}, trying HashiDive fallback")
                trades = []  # Will trigger HashiDive fallback below
            else:
                trades = response.json() if response.ok else []
                logger.debug(f"[TRADES] Wallet {address[:12]}...: fetched {len(trades)} raw trades from API (side={side})")
            
            # Fallback to HashiDive API if Polymarket API fails, returns None, or returns empty
            if (not trades and self.hashdive_client):
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
                
                # Allow processing without condition_id - use market slug/title as fallback
                # This allows signals even when condition_id is not available
                if not condition_id:
                    # Try to use market slug or title as identifier
                    market_slug = trade.get("slug") or trade.get("eventSlug") or ""
                    market_title = trade.get("title") or trade.get("question") or ""
                    if market_slug:
                        condition_id = f"SLUG:{market_slug}"
                    elif market_title:
                        # Use first 50 chars of title as identifier
                        condition_id = f"TITLE:{market_title[:50]}"
                    else:
                        # Skip only if we have no way to identify the market
                        logger.debug(f"[TRADES] Skipping trade {trade_id[:12]}...: no condition_id and no market identifier")
                        continue
                
                if outcome_index is None:
                    # Default to 0 if outcome_index is missing
                    outcome_index = 0
                    logger.debug(f"[TRADES] Using default outcome_index=0 for trade {trade_id[:12]}...")
                
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
                        slug_url = f"https://clob.polymarket.com/markets/{condition_id}"
                        slug_resp = self.http_get(slug_url, allow_404_as_none=True)
                        if slug_resp is not None and hasattr(slug_resp, 'status_code') and slug_resp.status_code == 200:
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
            error_type = type(e).__name__
            error_msg = str(e)
            # Log detailed error info for debugging
            if "RetryError" in error_type or "RetryError" in error_msg:
                # Extract underlying error from RetryError
                underlying_error = error_msg
                if hasattr(e, 'last_attempt') and hasattr(e.last_attempt, 'exception'):
                    underlying_error = str(e.last_attempt.exception())
                logger.warning(f"Error getting new {side} trades for {address[:12]}...: {error_type} - {underlying_error[:200]}")
                self.error_counts['retry_error'] += 1
            else:
                logger.warning(f"Error getting new {side} trades for {address[:12]}...: {error_type} - {error_msg[:200]}")
                self.error_counts['other_error'] += 1
            return [], last_seen_trade_id

    def get_market_info(self, condition_id: str) -> Dict[str, Any]:
        """Get market information including end date from CLOB API"""
        try:
            url = f"https://clob.polymarket.com/markets/{condition_id}"
            resp = self.http_get(url, allow_404_as_none=True)
            if resp is None:
                logger.info(f"[MARKET] Market {condition_id[:20]}... not found or closed (404), skipping consensus/signal")
                return {}
            if not hasattr(resp, 'status_code') or resp.status_code != 200:
                logger.warning(f"[MARKET] HTTP error {resp.status_code if hasattr(resp, 'status_code') else 'unknown'} for url={url[:100]}...")
                return {}
            data = resp.json() or {}
            if not isinstance(data, dict):
                return {}
            
            # Extract market info
            market_info = {
                "closed": data.get("closed", False),
                "active": data.get("active", True),
                "status": data.get("status", ""),
                "end_date_iso": data.get("end_date_iso"),
                "game_start_time": data.get("game_start_time"),
                "accepting_order_timestamp": data.get("accepting_order_timestamp")
            }
            
            # Parse end_date_iso if available
            if market_info.get("end_date_iso"):
                try:
                    from datetime import datetime
                    end_date_str = market_info["end_date_iso"]
                    # Parse ISO format: "2025-10-29T00:00:00Z" or "2025-10-29T00:00:00+00:00"
                    end_date_str = end_date_str.replace("Z", "+00:00")
                    market_info["end_date"] = datetime.fromisoformat(end_date_str)
                except Exception as e:
                    logger.debug(f"Failed to parse end_date_iso: {e}")
                    market_info["end_date"] = None
            else:
                market_info["end_date"] = None
            
            return market_info
        except Exception as e:
            logger.debug(f"Error getting market info: {e}")
            return {}
    
    def is_market_active(self, condition_id: str, outcome_index: Optional[int] = None) -> bool:
        """
        Check market status via CLOB API and return True if active/open.
        
        IMPORTANT: Приоритет проверки цен токенов над флагами closed/end_date.
        Если все токены имеют цены 0/1, рынок разрешен (закрыт).
        
        Returns True if market is active, False if closed/resolved.
        If check fails (API error), returns True by default (fail-open).
        """
        try:
            logger.debug(f"[MarketActive] Checking market status for condition_id={condition_id[:20]}... outcome_index={outcome_index}")
            # Get market info (includes end_date check)
            market_info = self.get_market_info(condition_id)
            
            # If market_info is empty, try to fetch directly or assume active (fail-open)
            if not market_info:
                logger.warning(f"[MarketActive] market_info is empty for condition_id={condition_id[:20]}..., trying direct API call or assuming active (fail-open)")
                # Try direct API call
                try:
                    import requests
                    url = f"https://clob.polymarket.com/markets/{condition_id}"
                    resp = requests.get(url, timeout=5)
                    if resp and resp.status_code == 200:
                        data = resp.json()
                        market_info = {
                            "closed": data.get("closed", False),
                            "active": data.get("active", True),
                            "status": data.get("status", ""),
                            "end_date_iso": data.get("end_date_iso"),
                        }
                        # Parse end_date if available
                        if market_info.get("end_date_iso"):
                            try:
                                from datetime import datetime
                                end_date_str = market_info["end_date_iso"].replace("Z", "+00:00")
                                market_info["end_date"] = datetime.fromisoformat(end_date_str)
                            except Exception:
                                market_info["end_date"] = None
                        else:
                            market_info["end_date"] = None
                    else:
                        # If API call fails, assume active (fail-open)
                        logger.warning(f"[MarketActive] Direct API call failed (status={resp.status_code if resp else 'None'}), assuming ACTIVE (fail-open)")
                        return True
                except Exception as api_err:
                    logger.warning(f"[MarketActive] Direct API call exception: {api_err}, assuming ACTIVE (fail-open)")
                    return True
            
            # Store flags for later (but check prices first)
            closed_flag = market_info.get("closed") is True
            end_date_passed = False
            
            # Check if market has ended based on end_date
            if market_info.get("end_date"):
                from datetime import datetime, timezone
                end_date = market_info["end_date"]
                if end_date.tzinfo is None:
                    # Assume UTC if no timezone
                    end_date = end_date.replace(tzinfo=timezone.utc)
                current_time = datetime.now(timezone.utc)
                
                # If end date has passed, note it (but check prices first)
                if current_time > end_date:
                    end_date_passed = True
                    hours_since_end = (current_time - end_date).total_seconds() / 3600
                    logger.debug(f"Market {condition_id[:20]}... end_date passed ({hours_since_end:.1f}h ago), but checking prices first")
            
            # Check status field (more reliable than closed flag)
            status = str(market_info.get("status") or "").lower()
            if status in {"resolved", "finished", "closed", "ended", "finalized"}:
                logger.debug(f"Market {condition_id[:20]}... closed (status: {status})")
                return False
            
            # Check active flag
            active = market_info.get("active")
            if active is False:
                logger.debug(f"Market {condition_id[:20]}... closed (active=False)")
                return False
            
            # CRITICAL: Check token prices FIRST - most reliable indicator
                # Re-fetch to get tokens data (could be optimized to reuse market_info)
                url = f"https://clob.polymarket.com/markets/{condition_id}"
                resp = self.http_get(url, allow_404_as_none=True)
            
            # Fallback: if http_get returns None, try direct request
            if resp is None:
                try:
                    import requests
                    resp = requests.get(url, timeout=5)
                except Exception as e:
                    logger.debug(f"Direct request also failed: {e}")
                    resp = None
            
                if resp is not None and hasattr(resp, 'status_code') and resp.status_code == 200:
                    data = resp.json() if hasattr(resp, 'json') else (resp.json() if callable(getattr(resp, 'json', None)) else {})
                if not data and hasattr(resp, 'text'):
                    try:
                        import json
                        data = json.loads(resp.text)
                    except Exception:
                        data = {}
                
                    tokens = data.get('tokens') or []
                
                if tokens:
                    # Check if ALL tokens have extreme prices (0 or 1) - market is resolved
                    all_resolved = True
                    for token in tokens:
                        price = token.get('price') or token.get('last_price') or token.get('mark_price')
                        if price is not None:
                            try:
                                price_float = float(price)
                                # If price is not 0/1 (or very close), market is not fully resolved
                                if not (price_float <= 0.001 or price_float >= 0.999):
                                    all_resolved = False
                                    break
                            except (ValueError, TypeError):
                                # If we can't parse price, assume not resolved
                                all_resolved = False
                                break
                        else:
                            # If no price available, assume not resolved (might be new market)
                            all_resolved = False
                            break
                    
                    if all_resolved:
                        logger.debug(f"Market {condition_id[:20]}... closed (all tokens resolved: prices are 0/1)")
                        return False
                    
                    # Also check specific outcome if provided
                    if outcome_index is not None and outcome_index < len(tokens):
                        token = tokens[outcome_index]
                        for key in ("price", "last_price", "mark_price"):
                            val = token.get(key)
                            if isinstance(val, (int, float)):
                                price = float(val)
                                # Price >= 0.98 or <= 0.02 means closed/resolved
                                if price >= 0.98 or price <= 0.02:
                                    logger.debug(f"Market {condition_id[:20]}... closed (outcome {outcome_index} price: {price})")
                                    return False
            
            # If prices indicate market is active, ignore closed flag and end_date
            # (they might be inaccurate - e.g., event end date vs market resolution date)
            if closed_flag or end_date_passed:
                # Prices were checked above - if they're not 0/1, market is active
                logger.debug(f"Market {condition_id[:20]}... closed flag or end_date passed, but prices indicate active - assuming active")
            
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
            return True # Assume active on error to avoid blocking valid markets
    
    def check_consensus_and_alert(self, condition_id: str, outcome_index: int, 
                                 wallet: str, trade_id: str, timestamp: float, 
                                 price: float = 0, side: str = "BUY", 
                                 market_title: str = "", market_slug: str = "",
                                 usd_amount: float = 0.0, quantity: float = 0.0):
        """Check for consensus and send alert if threshold met"""
        try:
            # Get unique wallets in window first to log candidate
            key, window_data = self.db.update_rolling_window(
                condition_id, outcome_index, wallet, trade_id, timestamp, 
                self.alert_window_min, market_title, market_slug, price, side,
                usd_amount=usd_amount, quantity=quantity
            )
            # CRITICAL: Filter events by time window before counting wallets
            # Only include events within the alert_window_min from the most recent event
            events = window_data.get("events", [])
            if events:
                # Get the most recent event timestamp
                latest_event_ts = max(e["ts"] for e in events)
                window_start_ts = latest_event_ts - (self.alert_window_min * 60)
                
                # Filter events to only include those within the time window
                recent_events = [e for e in events if e["ts"] >= window_start_ts]
                
                # Log if we filtered out old events
                if len(recent_events) < len(events):
                    filtered_count = len(events) - len(recent_events)
                    logger.warning(
                        f"[CONSENSUS] ⚠️  Filtered out {filtered_count} old event(s) outside {self.alert_window_min}min window. "
                        f"Events: {len(events)} -> {len(recent_events)} (window: {window_start_ts:.0f} to {latest_event_ts:.0f})"
                    )
                
                events = recent_events
            
            wallets_in_window = sorted({e["wallet"] for e in events})
            # Save a copy of wallets_in_window for database storage (to prevent modification)
            wallets_for_db = list(wallets_in_window) if wallets_in_window else []
            
            # Log candidate with detailed info
            if not hasattr(self, 'monitoring_stats'):
                self.monitoring_stats = {"total_consensus_candidates": 0, "total_alerts_blocked": 0, "blocked_reasons": {}}
            self.monitoring_stats["total_consensus_candidates"] = self.monitoring_stats.get("total_consensus_candidates", 0) + 1
            
            logger.info(
                f"[CONSENSUS] 🔍 Candidate #{self.monitoring_stats['total_consensus_candidates']}: "
                f"condition={condition_id[:20]}... outcome={outcome_index} side={side} "
                f"wallets={len(wallets_in_window)}/{self.min_consensus} window={self.alert_window_min} min"
            )
            
            # FIRST CHECK: Skip markets that are already closed/resolved (check at entry)
            # Skip this check if condition_id is a fallback (starts with SLUG: or TITLE:)
            # This allows signals even when condition_id is not available
            if condition_id and not condition_id.startswith(("SLUG:", "TITLE:")):
                if not self.is_market_active(condition_id, outcome_index):
                    self.suppressed_counts['market_closed'] = self.suppressed_counts.get('market_closed', 0) + 1
                    if not hasattr(self, 'monitoring_stats'):
                        self.monitoring_stats = {"total_alerts_blocked": 0, "blocked_reasons": {}}
                    self.monitoring_stats["total_alerts_blocked"] = self.monitoring_stats.get("total_alerts_blocked", 0) + 1
                    reason = "market_inactive_early"
                    self.monitoring_stats["blocked_reasons"][reason] = self.monitoring_stats["blocked_reasons"].get(reason, 0) + 1
                    logger.info(
                        f"[CONSENSUS] ❌ BLOCKED (early check): Market {condition_id[:20]}... is closed or not found (404). Skipping signal. "
                        f"wallets={len(wallets_in_window)}/{self.min_consensus} outcome={outcome_index} side={side}"
                    )
                    # Don't send suppressed alert here - will be sent in final check if consensus reached
                    return
            
            # Check if this is first entry for this wallet in this market direction
            # Skip this check for fallback condition_ids to allow processing
            if condition_id and not condition_id.startswith(("SLUG:", "TITLE:")):
                if self.db.has_traded_market(wallet, condition_id, side):
                    logger.debug(f"[CONSENSUS] Skipping {wallet[:12]}...: already traded {condition_id[:20]}... ({side})")
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
            # CRITICAL: Filter events by time window before counting wallets
            # Only include events within the alert_window_min from the most recent event
            all_events = window_data.get("events", [])
            filtered_events = all_events  # Will be filtered below
            
            if all_events:
                # Get the most recent event timestamp
                latest_event_ts = max(e["ts"] for e in all_events)
                window_start_ts = latest_event_ts - (self.alert_window_min * 60)
                
                # Filter events to only include those within the time window
                filtered_events = [e for e in all_events if e["ts"] >= window_start_ts]
                
                # Log if we filtered out old events
                if len(filtered_events) < len(all_events):
                    filtered_count = len(all_events) - len(filtered_events)
                    logger.warning(
                        f"[CONSENSUS] ⚠️  Filtered out {filtered_count} old event(s) outside {self.alert_window_min}min window. "
                        f"Events: {len(all_events)} -> {len(filtered_events)} (window: {window_start_ts:.0f} to {latest_event_ts:.0f})"
                    )
                
                # Calculate actual time window for recent events
                if filtered_events:
                    first_recent_ts = min(e["ts"] for e in filtered_events)
                    actual_window_minutes = (latest_event_ts - first_recent_ts) / 60.0
                    logger.info(
                        f"[CONSENSUS] Time window check: {len(filtered_events)} events within {self.alert_window_min}min window, "
                        f"actual span: {actual_window_minutes:.1f} minutes"
                    )
            
            wallets_in_window = sorted({e["wallet"] for e in filtered_events})
            # Save a copy of wallets_in_window for database storage (to prevent modification)
            wallets_for_db = list(wallets_in_window) if wallets_in_window else []
            
            if len(wallets_in_window) < self.min_consensus:
                if not hasattr(self, 'monitoring_stats'):
                    self.monitoring_stats = {"total_alerts_blocked": 0, "blocked_reasons": {}}
                self.monitoring_stats["total_alerts_blocked"] = self.monitoring_stats.get("total_alerts_blocked", 0) + 1
                reason = "below_threshold"
                self.monitoring_stats["blocked_reasons"][reason] = self.monitoring_stats["blocked_reasons"].get(reason, 0) + 1
                logger.debug(
                    f"[CONSENSUS] Not enough wallets for market {condition_id[:20]}...: "
                    f"{len(wallets_in_window)}/{self.min_consensus} within window={self.alert_window_min} min"
                )
                logger.info(
                    f"[CONSENSUS] ⏭️  BLOCKED: Below threshold - {len(wallets_in_window)} < {self.min_consensus} wallets "
                    f"condition={condition_id[:20]}... outcome={outcome_index} side={side} window={self.alert_window_min} min"
                )
                return
            
            logger.info(
                f"[CONSENSUS] ✅ Threshold met: {len(wallets_in_window)} >= {self.min_consensus} wallets "
                f"condition={condition_id[:20]}... outcome={outcome_index} side={side}"
            )
            
            # STEP 1: Check if market is active (early check after threshold met)
            # Skip this check if condition_id is a fallback (starts with SLUG: or TITLE:)
            # This allows signals even when condition_id is not available
            logger.info(f"[CONSENSUS] Step 1/7: Checking market status for condition={condition_id[:20]}... outcome={outcome_index}")
            market_is_active_early = True  # Default to True for fallback condition_ids
            if condition_id and not condition_id.startswith(("SLUG:", "TITLE:")):
                market_is_active_early = self.is_market_active(condition_id, outcome_index)
            logger.info(f"[CONSENSUS] Step 1/7: Market active status = {market_is_active_early}")
            
            # EARLY CHECK: If market is already closed, skip processing events from rolling window
            # This prevents delayed alerts for markets that closed while events were in the window
            # IMPORTANT: Don't send suppressed alerts for old events from closed markets
            # Suppressed alerts should only be sent in real-time when consensus is detected but market is closed
            # Skip this check for fallback condition_ids
            if not market_is_active_early and condition_id and not condition_id.startswith(("SLUG:", "TITLE:")):
                self.suppressed_counts['market_closed'] = self.suppressed_counts.get('market_closed', 0) + 1
                if not hasattr(self, 'monitoring_stats'):
                    self.monitoring_stats = {"total_alerts_blocked": 0, "blocked_reasons": {}}
                self.monitoring_stats["total_alerts_blocked"] = self.monitoring_stats.get("total_alerts_blocked", 0) + 1
                reason = "market_inactive_window"
                self.monitoring_stats["blocked_reasons"][reason] = self.monitoring_stats["blocked_reasons"].get(reason, 0) + 1
                logger.info(
                    f"[CONSENSUS] ❌ BLOCKED (window check): Market {condition_id[:20]}... is closed or not found (404). Skipping signal. "
                    f"wallets={len(wallets_in_window)}/{self.min_consensus} outcome={outcome_index} side={side} "
                    f"(events in window from closed market)"
                )
                # Don't send suppressed alert here - these are old events from closed markets
                # Suppressed alerts should only be sent in real-time, not for historical events
                return
            
            # STEP 2: Check if alert already sent for this direction
            logger.info(f"[CONSENSUS] Step 2/7: Checking if alert already sent for condition={condition_id[:20]}... outcome={outcome_index} side={side}")
            alert_key = f"{condition_id}:{outcome_index}:{side}"
            already_sent = self.db.is_alert_sent(condition_id, outcome_index, 
                                    window_data["first_ts"], window_data["last_ts"], alert_key)
            logger.info(f"[CONSENSUS] Step 2/7: Alert already sent = {already_sent}")
            if already_sent:
                if not hasattr(self, 'monitoring_stats'):
                    self.monitoring_stats = {"total_alerts_blocked": 0, "blocked_reasons": {}}
                self.monitoring_stats["total_alerts_blocked"] = self.monitoring_stats.get("total_alerts_blocked", 0) + 1
                reason = "already_sent"
                self.monitoring_stats["blocked_reasons"][reason] = self.monitoring_stats["blocked_reasons"].get(reason, 0) + 1
                logger.info(
                    f"[CONSENSUS] ⏭️  BLOCKED: Alert already sent - "
                    f"condition={condition_id[:20]}... outcome={outcome_index} side={side} "
                    f"wallets={len(wallets_in_window)}"
                )
                return
            
            # Extract market info and prices from window events
            # BEST-EFFORT: Try to get market_title from events (for display purposes only)
            # NOTE: We NO LONGER extract market_slug from events - all slug normalization
            # is handled by notify.TelegramNotifier._get_event_slug_and_market_id() and _get_market_slug()
            market_title = ""
            market_slug = ""  # Always empty - notify.py will fetch and normalize slug via API
            for event in window_data.get("events", []):
                if event.get("marketTitle"):
                    market_title = event["marketTitle"]
                    break  # Use first available marketTitle
            wallet_prices = {}  # Map wallet -> price
            
            logger.info(f"[CONSENSUS] Extracting wallet_prices from {len(window_data.get('events', []))} events...")
            for event in window_data.get("events", []):
                # BEST-EFFORT: Update market_title if we haven't found one yet
                if event.get("marketTitle") and not market_title:
                    market_title = event["marketTitle"]
                # NOTE: We NO LONGER extract marketSlug from events - all slug normalization
                # is handled by notify.TelegramNotifier._get_event_slug_and_market_id() and _get_market_slug()
                event_price = event.get("price")
                event_wallet = event.get("wallet")
                if event_price and event_wallet:
                    wallet_prices[event_wallet] = event.get("price", 0)
                    logger.debug(f"[CONSENSUS] Added wallet_price: {event_wallet[:12]}... = {event_price}")
                else:
                    logger.debug(f"[CONSENSUS] Skipping event - price={event_price}, wallet={event_wallet}")
            
            logger.info(f"[CONSENSUS] Extracted wallet_prices: {len(wallet_prices)} wallets with prices: {wallet_prices}")
            
            # STEP 3: Apply entry price divergence rule based on first three traders by time
            logger.info(f"[CONSENSUS] Step 3/7: Checking price divergence for condition={condition_id[:20]}... outcome={outcome_index}")
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
                    # Maximum 25% divergence allowed for all prices (as per requirements)
                    # Calculate divergence as (max - min) / max
                    divergence = (p_max - p_min) / p_max if p_max > 0 else 0
                    max_allowed_divergence = 0.25  # 25% maximum divergence
                    price_ok = divergence <= max_allowed_divergence
                    if not price_ok:
                        if not hasattr(self, 'monitoring_stats'):
                            self.monitoring_stats = {"total_alerts_blocked": 0, "blocked_reasons": {}}
                        self.monitoring_stats["total_alerts_blocked"] = self.monitoring_stats.get("total_alerts_blocked", 0) + 1
                        reason = "price_divergence"
                        self.monitoring_stats["blocked_reasons"][reason] = self.monitoring_stats["blocked_reasons"].get(reason, 0) + 1
                        logger.info(
                            f"[CONSENSUS] ⏭️  BLOCKED: Entry price divergence - "
                            f"condition={condition_id[:20]}... outcome={outcome_index} side={side} "
                            f"prices={first_three_prices} (divergence={(p_max - p_min) / p_max * 100:.1f}%) wallets={len(wallets_in_window)}"
                        )
                        return
                    else:
                        logger.info(f"[CONSENSUS] Step 3/7: Price divergence OK (prices={first_three_prices})")
            except Exception as _e:
                # If any error occurs during divergence check, do not block alert
                logger.debug(f"[CONSENSUS] Step 3/7: Price divergence check skipped: {_e}")
            
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
            
            # STEP 4: Fetch price FIRST using multi-level fallback (including HashiDive API and wallet_prices)
            # This allows HashiDive to provide accurate prices even if CLOB API shows resolved prices
            # Only AFTER getting price, we check if market is closed based on the actual price
            logger.info(f"[CONSENSUS] Step 4/7: Fetching current price for condition_id={condition_id[:20]}... outcome={outcome_index}, wallet_prices provided: {len(wallet_prices) if wallet_prices else 0} wallets")
            current_price = self._get_current_price(
                condition_id, 
                outcome_index,
                wallet_prices=wallet_prices,
                slug=market_slug if market_slug else None
            )
            if current_price is None:
                logger.warning(f"[CONSENSUS] Step 4/7: ⚠️  Price unavailable after all fallbacks for condition_id={condition_id[:20]}... outcome={outcome_index}, wallet_prices: {wallet_prices}")
            else:
                logger.info(f"[CONSENSUS] Step 4/7: ✅ Got current price: {current_price:.6f} for condition_id={condition_id[:20]}... outcome={outcome_index}")
            
            # Check for insider candidates in consensus
            insider_wallets = []
            for w in wallets_in_window:
                wallet_info = self.db.get_wallet(w)
                if wallet_info and wallet_info.get('is_insider_candidate'):
                    insider_wallets.append({
                        'address': w,
                        'reason': wallet_info.get('insider_detection_reason'),
                        'total_trades': wallet_info.get('traded_total'),
                        'win_rate': wallet_info.get('win_rate'),
                        'total_markets': wallet_info.get('total_markets_traded')
                    })
            
            # If insider candidates found, send insider alert for each
            if insider_wallets:
                logger.info(f"[INSIDER] Detected {len(insider_wallets)} insider candidate(s) in consensus for condition={condition_id[:20]}...")
                for insider in insider_wallets:
                    # Calculate position size from events
                    position_size = 0.0
                    for e in window_data.get('events', []):
                        if e.get('wallet') == insider['address']:
                            position_size += e.get('usd', 0.0)
                    
                    # Get category if available
                    category = None
                    try:
                        # Try to get category from market classification
                        if market_title:
                            from market_utils import classify_market
                            event_slug, market_id, market_slug_from_api, event_data = self.notifier._get_event_slug_and_market_id(condition_id)
                            category = classify_market(event_data or {}, market_slug or market_slug_from_api or "", market_title)
                    except Exception as e:
                        logger.debug(f"Error getting category for insider alert: {e}")
                    
                    # Send insider alert
                    try:
                        self.notifier.send_insider_alert(
                            condition_id=condition_id,
                            outcome_index=outcome_index,
                            wallet=insider['address'],
                            reason=insider['reason'],
                            market_title=market_title,
                            market_slug=market_slug,
                            side=side,
                            position_size=position_size,
                            win_rate=insider['win_rate'] or 0.0,
                            total_trades=insider['total_trades'] or 0,
                            total_markets=insider['total_markets'] or 0,
                            current_price=current_price,
                            category=category
                        )
                        logger.info(f"[INSIDER] Sent insider alert for wallet {insider['address'][:12]}... reason={insider['reason']}")
                        
                        # Update insider stats
                        self.insider_stats['total_detected'] += 1
                        reason = insider['reason']
                        self.insider_stats['by_reason'][reason] = self.insider_stats['by_reason'].get(reason, 0) + 1
                    except Exception as e:
                        logger.error(f"[INSIDER] Failed to send insider alert: {e}", exc_info=True)
            
            # STEP 5: Check market status based on the actual price we got
            # IMPORTANT: First check if market is active, then check price
            # If market is active, allow alert even if price is high/low (fail-open)
            # Only block if market is confirmed closed AND price indicates resolved
            logger.info(f"[CONSENSUS] Step 5/7: Checking price-based market status for condition={condition_id[:20]}... outcome={outcome_index}")
            if current_price is not None:
                price_val = float(current_price)
                logger.info(f"[CONSENSUS] Step 5/7: Price={price_val:.6f} for condition={condition_id[:20]}... outcome={outcome_index}")
                
                # First check: Price = 1.0 or 0.0 (or very close) - definitely resolved
                if price_val >= 0.999 or price_val <= 0.001:
                    self.suppressed_counts['resolved'] = self.suppressed_counts.get('resolved', 0) + 1
                    logger.info(
                        f"[CONSENSUS] ⏭️  BLOCKED: Market resolved (price={price_val:.6f} >= 0.999 or <= 0.001) "
                        f"condition={condition_id[:20]}... outcome={outcome_index} side={side} wallets={len(wallets_in_window)}"
                    )
                    # Only send suppressed alert if we have consensus (multiple wallets)
                    if len(wallets_in_window) >= self.min_consensus:
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
                                total_usd=total_usd,
                                market_active=False  # Market is resolved, not active
                            )
                        except Exception as e:
                            logger.debug(f"Failed to send suppressed alert details: {e}")
                    else:
                        logger.debug(f"Skipping suppressed alert for resolved market: only {len(wallets_in_window)} wallet(s), below consensus threshold")
                    return
                
                # Second check: Price >= 0.98 or <= 0.02 - might be closed, but check market status first
                if price_val >= 0.98 or price_val <= 0.02:
                    # Check if market is actually active before blocking
                    market_is_active = self.is_market_active(condition_id, outcome_index)
                    logger.info(
                        f"[CONSENSUS PRICE CHECK] price={price_val:.6f} >= 0.98 or <= 0.02, "
                        f"market_is_active={market_is_active} for condition={condition_id[:20]}... outcome={outcome_index}"
                    )
                    
                    if not market_is_active:
                        # Market is confirmed closed AND price is high/low - block alert
                        self.suppressed_counts['market_closed'] = self.suppressed_counts.get('market_closed', 0) + 1
                        logger.info(
                            f"[CONSENSUS] ⏭️  BLOCKED: Market closed (price={price_val:.6f} >= 0.98 or <= 0.02 AND market_is_active=False) "
                            f"condition={condition_id[:20]}... outcome={outcome_index} side={side} wallets={len(wallets_in_window)}"
                        )
                        # Only send suppressed alert if we have consensus (multiple wallets)
                        if len(wallets_in_window) >= self.min_consensus:
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
                        else:
                            logger.debug(f"Skipping suppressed alert for closed market: only {len(wallets_in_window)} wallet(s), below consensus threshold")
                        return
                    else:
                        # Market is active but price is high/low - allow alert (fail-open)
                        # This could be a temporary price spike or market still trading
                        logger.warning(
                            f"[CONSENSUS] ⚠️  Price high/low (price={price_val:.6f} >= 0.98 or <= 0.02) BUT market is ACTIVE - "
                            f"allowing alert to proceed (fail-open) condition={condition_id[:20]}... outcome={outcome_index} side={side} "
                            f"wallets={len(wallets_in_window)}"
                        )
                        # Continue to send alert - price will be shown in alert
            
            # If price is None, check market status via is_market_active (but only as fallback)
            # This is less reliable than actual price, so we use it only if price unavailable
            if current_price is None:
                logger.warning(
                    f"[CONSENSUS] ⚠️  Price unavailable (None) for condition={condition_id[:20]}... outcome={outcome_index}, "
                    f"checking market status via is_market_active..."
                )
                market_is_active = self.is_market_active(condition_id, outcome_index)
                logger.info(
                    f"[CONSENSUS PRICE CHECK] price=None, market_is_active={market_is_active} "
                    f"for condition={condition_id[:20]}... outcome={outcome_index}"
                )
                
                if not market_is_active:
                    # Market is confirmed closed AND price unavailable - block alert
                    self.suppressed_counts['market_closed'] = self.suppressed_counts.get('market_closed', 0) + 1
                    logger.info(
                        f"[CONSENSUS] ⏭️  BLOCKED: Market closed (price unavailable AND market_is_active=False) "
                        f"condition={condition_id[:20]}... outcome={outcome_index} side={side} wallets={len(wallets_in_window)}"
                    )
                    # Only send suppressed alert if we have consensus (multiple wallets)
                    if len(wallets_in_window) >= self.min_consensus:
                        try:
                            self.notifier.send_suppressed_alert_details(
                                reason="market_closed",
                                condition_id=condition_id,
                                outcome_index=outcome_index,
                                wallets=wallets_in_window,
                                wallet_prices=wallet_prices,
                                market_title=market_title,
                                market_slug=market_slug,
                                current_price=None,
                                side=side,
                                total_usd=total_usd,
                                market_active=False  # Market is closed, not active
                            )
                        except Exception as e:
                            logger.debug(f"Failed to send suppressed alert details: {e}")
                    else:
                        logger.debug(f"Skipping suppressed alert for closed market: only {len(wallets_in_window)} wallet(s), below consensus threshold")
                    return
                else:
                    # Market is active but price unavailable - allow alert (fail-open)
                    logger.warning(
                        f"[FAIL-OPEN] Market active but price=None — continuing alert with Price: N/A "
                        f"condition={condition_id[:20]}... outcome={outcome_index} side={side} "
                        f"wallets={len(wallets_in_window)}"
                    )
                    # Continue to send alert - price will be shown as "N/A" in alert
            
            # NOTE: Price and market status checks were already done above (lines 1546-1709)
            # Import datetime here to avoid conflicts with local imports in nested blocks
            # Use full module path to avoid conflicts
            import datetime as dt_module
            now_iso = dt_module.datetime.now(dt_module.timezone.utc).isoformat()
            # Continue with deduplication and other checks
            
            # Dedupe/trigger rules using recent alerts
            try:
                # Additional price check for deduplication logic (if needed)
                if current_price is not None:
                    price_val = float(current_price)
                    logger.debug(f"[DEDUPE PRICE CHECK] condition={condition_id}, outcome={outcome_index}, price={price_val}")
                    # Price = 1.0 or exactly 0.0 (or very close) means market is resolved - BLOCK ALERT
                    # (This is a redundant check, but kept for safety in dedupe logic)
                    if price_val >= 0.999 or price_val <= 0.001:
                        self.suppressed_counts['resolved'] = self.suppressed_counts.get('resolved', 0) + 1
                        if not hasattr(self, 'monitoring_stats'):
                            self.monitoring_stats = {"total_alerts_blocked": 0, "blocked_reasons": {}}
                        self.monitoring_stats["total_alerts_blocked"] = self.monitoring_stats.get("total_alerts_blocked", 0) + 1
                        reason = "resolved"
                        self.monitoring_stats["blocked_reasons"][reason] = self.monitoring_stats["blocked_reasons"].get(reason, 0) + 1
                        
                        # Check if events are recent (within last hour) - only send suppressed alerts for recent events
                        # Use dt_module to avoid conflicts
                        now_ts = dt_module.datetime.now(dt_module.timezone.utc).timestamp()
                        last_event_age = now_ts - window_data.get("last_ts", 0)
                        recent_threshold = 3600  # 1 hour in seconds
                        is_recent = last_event_age <= recent_threshold
                        
                        logger.info(
                            f"[CONSENSUS] ⏭️  BLOCKED: Market resolved - "
                            f"condition={condition_id[:20]}... outcome={outcome_index} side={side} "
                            f"price={price_val:.6f} wallets={len(wallets_in_window)} "
                            f"(last event age: {last_event_age/60:.1f} min, recent: {is_recent})"
                        )
                        # Only send suppressed alert if events are recent (within last hour)
                        # AND if we haven't already sent a suppressed alert for this market/outcome/side/reason recently
                        if len(wallets_in_window) >= self.min_consensus and is_recent:
                            if not self.db.is_suppressed_alert_sent(condition_id, outcome_index, side, "resolved", window_minutes=30.0):
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
                                    self.db.mark_suppressed_alert_sent(
                                        condition_id, outcome_index, side, "resolved",
                                        wallet_count=len(wallets_in_window)
                                    )
                                except Exception as e:
                                    logger.debug(f"Failed to send suppressed alert details: {e}")
                            else:
                                logger.debug(f"Suppressed alert for resolved already sent recently for {condition_id[:20]}... outcome={outcome_index} side={side}")
                        else:
                            if not is_recent:
                                logger.debug(f"Skipping suppressed alert for resolved market: events too old ({last_event_age/60:.1f} min ago)")
                        return
                    # Price >= 0.98 or <= 0.02 also indicates closed/almost resolved - BLOCK ALERT  
                    if price_val >= 0.98 or price_val <= 0.02:
                        self.suppressed_counts['price_high'] = self.suppressed_counts.get('price_high', 0) + 1
                        if not hasattr(self, 'monitoring_stats'):
                            self.monitoring_stats = {"total_alerts_blocked": 0, "blocked_reasons": {}}
                        self.monitoring_stats["total_alerts_blocked"] = self.monitoring_stats.get("total_alerts_blocked", 0) + 1
                        reason = "price_high"
                        self.monitoring_stats["blocked_reasons"][reason] = self.monitoring_stats["blocked_reasons"].get(reason, 0) + 1
                        
                        # Check if events are recent (within last hour) - only send suppressed alerts for recent events
                        # Use dt_module to avoid conflicts
                        now_ts = dt_module.datetime.now(dt_module.timezone.utc).timestamp()
                        last_event_age = now_ts - window_data.get("last_ts", 0)
                        recent_threshold = 3600  # 1 hour in seconds
                        is_recent = last_event_age <= recent_threshold
                        
                        logger.info(
                            f"[CONSENSUS] ⏭️  BLOCKED: Price too high/low - "
                            f"condition={condition_id[:20]}... outcome={outcome_index} side={side} "
                            f"price={price_val:.6f} wallets={len(wallets_in_window)} "
                            f"(last event age: {last_event_age/60:.1f} min, recent: {is_recent})"
                        )
                        # Only send suppressed alert if events are recent (within last hour)
                        # AND if we haven't already sent a suppressed alert for this market/outcome/side/reason recently
                        if len(wallets_in_window) >= self.min_consensus and is_recent:
                            if not self.db.is_suppressed_alert_sent(condition_id, outcome_index, side, "price_high", window_minutes=30.0):
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
                                    self.db.mark_suppressed_alert_sent(
                                        condition_id, outcome_index, side, "price_high",
                                        wallet_count=len(wallets_in_window)
                                    )
                                except Exception as e:
                                    logger.debug(f"Failed to send suppressed alert details: {e}")
                            else:
                                logger.debug(f"Suppressed alert for price_high already sent recently for {condition_id[:20]}... outcome={outcome_index} side={side}")
                        else:
                            if not is_recent:
                                logger.debug(f"Skipping suppressed alert for closed market: events too old ({last_event_age/60:.1f} min ago)")
                        return
                    logger.info(f"[PRICE CHECK] Price OK: {price_val:.6f}, allowing alert")
                else:
                    # Price is None - could mean API error, market not found, or market is closed
                    # ALWAYS check if market is closed first (more reliable than price check)
                    # Use get_market_info for comprehensive check
                    market_info = self.get_market_info(condition_id)
                    market_closed = False
                    
                    # Check multiple indicators of closed market
                    if market_info.get("closed") is True:
                        market_closed = True
                        logger.debug(f"Market {condition_id[:20]}... closed (closed flag)")
                    
                    # Check end_date
                    if market_info.get("end_date"):
                        from datetime import datetime, timezone
                        end_date = market_info["end_date"]
                        if end_date.tzinfo is None:
                            end_date = end_date.replace(tzinfo=timezone.utc)
                        current_time = datetime.now(timezone.utc)
                        if current_time > end_date:
                            market_closed = True
                            logger.debug(f"Market {condition_id[:20]}... closed (end_date passed)")
                    
                    # Check status
                    status = str(market_info.get("status") or "").lower()
                    if status in {"resolved", "finished", "closed", "ended", "finalized"}:
                        market_closed = True
                        logger.debug(f"Market {condition_id[:20]}... closed (status: {status})")
                    
                    # Check active flag
                    if market_info.get("active") is False:
                        market_closed = True
                        logger.debug(f"Market {condition_id[:20]}... closed (active=False)")
                    
                    # Also try is_market_active as additional check
                    if not market_closed:
                        try:
                            if not self.is_market_active(condition_id, outcome_index):
                                market_closed = True
                                logger.debug(f"Market {condition_id[:20]}... closed (is_market_active=False)")
                        except Exception as e:
                            logger.debug(f"is_market_active check failed: {e}, using market_info result")
                    
                    if market_closed:
                        # Market is closed - use market_closed reason
                        self.suppressed_counts['market_closed'] = self.suppressed_counts.get('market_closed', 0) + 1
                        if not hasattr(self, 'monitoring_stats'):
                            self.monitoring_stats = {"total_alerts_blocked": 0, "blocked_reasons": {}}
                        self.monitoring_stats["total_alerts_blocked"] = self.monitoring_stats.get("total_alerts_blocked", 0) + 1
                        reason = "market_closed_price_unavailable"
                        self.monitoring_stats["blocked_reasons"][reason] = self.monitoring_stats["blocked_reasons"].get(reason, 0) + 1
                        
                        # Check if events are recent (within last hour) - only send suppressed alerts for recent events
                        # Use dt_module to avoid conflicts
                        now_ts = dt_module.datetime.now(dt_module.timezone.utc).timestamp()
                        last_event_age = now_ts - window_data.get("last_ts", 0)
                        recent_threshold = 3600  # 1 hour in seconds
                        is_recent = last_event_age <= recent_threshold
                        
                        logger.info(
                            f"[CONSENSUS] ⏭️  BLOCKED: Market closed (price unavailable) - "
                            f"condition={condition_id[:20]}... outcome={outcome_index} side={side} "
                            f"wallets={len(wallets_in_window)} "
                            f"(last event age: {last_event_age/60:.1f} min, recent: {is_recent})"
                        )
                        # Only send suppressed alert if:
                        # 1. We have consensus (multiple wallets)
                        # 2. Events are recent (within last hour) - don't send for old historical events
                        # 3. We haven't already sent a suppressed alert for this market/outcome/side/reason recently
                        if len(wallets_in_window) >= self.min_consensus and is_recent:
                            if not self.db.is_suppressed_alert_sent(condition_id, outcome_index, side, "market_closed", window_minutes=30.0):
                                try:
                                    self.notifier.send_suppressed_alert_details(
                                        reason="market_closed",
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
                                    self.db.mark_suppressed_alert_sent(
                                        condition_id, outcome_index, side, "market_closed",
                                        wallet_count=len(wallets_in_window)
                                    )
                                except Exception as e:
                                    logger.debug(f"Failed to send suppressed alert details: {e}")
                            else:
                                logger.debug(f"Suppressed alert for market_closed already sent recently for {condition_id[:20]}... outcome={outcome_index} side={side}")
                        else:
                            if len(wallets_in_window) < self.min_consensus:
                                logger.debug(f"Skipping suppressed alert: only {len(wallets_in_window)} wallet(s), below consensus threshold")
                            else:
                                logger.debug(f"Skipping suppressed alert: events too old ({last_event_age/60:.1f} min ago), not recent enough")
                        return
                    else:
                        # Price is None but market appears ACTIVE - allow alert to proceed (fail-open)
                        # This could be a temporary API issue, but market is still trading
                        # IMPORTANT: Don't block real alerts for active markets just because price is temporarily unavailable
                        logger.warning(
                            f"[CONSENSUS] ⚠️  Price unavailable but market is ACTIVE - allowing alert to proceed "
                            f"condition={condition_id[:20]}... outcome={outcome_index} side={side} "
                            f"wallets={len(wallets_in_window)} "
                            f"(price might be temporarily unavailable, but market is still active - fail-open)"
                        )
                        # Continue to send real alert (price will be shown as "N/A" or similar)
                        # The alert will proceed to the next checks (deduplication, etc.)
                        # current_price remains None, but alert will be sent with Price: N/A
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
            
            # STEP 6: Final check: Verify market is still active before sending alert
            # IMPORTANT: Check if events are recent (within window) - don't send suppressed alerts for old events
            logger.info(f"[CONSENSUS] Step 6/7: Final market status check for condition={condition_id[:20]}... outcome={outcome_index}")
            market_is_active_final = self.is_market_active(condition_id, outcome_index)
            logger.info(f"[CONSENSUS] Step 6/7: Final market active status = {market_is_active_final}")
            if not market_is_active_final:
                self.suppressed_counts['market_closed'] = self.suppressed_counts.get('market_closed', 0) + 1
                
                # Check if events are recent (within last hour) - only send suppressed alerts for recent events
                # Use dt_module to avoid conflicts
                now_ts = dt_module.datetime.now(dt_module.timezone.utc).timestamp()
                last_event_age = now_ts - window_data.get("last_ts", 0)
                recent_threshold = 3600  # 1 hour in seconds
                
                is_recent = last_event_age <= recent_threshold
                
                logger.info(
                    f"[Consensus] skipped: market_inactive (final check) condition={condition_id[:20]}... outcome={outcome_index} side={side} "
                    f"(last event age: {last_event_age/60:.1f} min, recent: {is_recent})"
                )
                
                # Only send suppressed alert if:
                # 1. We have consensus (multiple wallets)
                # 2. Events are recent (within last hour) - don't send for old historical events
                # 3. We haven't already sent a suppressed alert for this market/outcome/side/reason recently
                if len(wallets_in_window) >= self.min_consensus and is_recent:
                    if not self.db.is_suppressed_alert_sent(condition_id, outcome_index, side, "market_closed", window_minutes=30.0):
                        # Send suppressed alert details to reports (only for recent consensus-level events)
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
                            self.db.mark_suppressed_alert_sent(
                                condition_id, outcome_index, side, "market_closed",
                                wallet_count=len(wallets_in_window)
                            )
                        except Exception as e:
                            logger.debug(f"Failed to send suppressed alert details: {e}")
                    else:
                        logger.debug(f"Suppressed alert for market_closed already sent recently for {condition_id[:20]}... outcome={outcome_index} side={side}")
                else:
                    if len(wallets_in_window) < self.min_consensus:
                        logger.debug(f"Skipping suppressed alert for closed market: only {len(wallets_in_window)} wallet(s), below consensus threshold")
                    else:
                        logger.debug(f"Skipping suppressed alert for closed market: events too old ({last_event_age/60:.1f} min ago), not recent enough")
                return

            # STEP 7: Dedupe/trigger rules using recent alerts
            logger.info(f"[CONSENSUS] Step 7/7: Checking deduplication rules for condition={condition_id[:20]}... outcome={outcome_index} side={side}")
            recent = self.db.get_recent_alerts(condition_id, outcome_index, limit=3)
            logger.info(f"[CONSENSUS] Step 7/7: Found {len(recent)} recent alerts")
            if recent:
                last = recent[0]
                # Parse time delta
                try:
                    # Use dt_module to avoid conflicts
                    last_ts = dt_module.datetime.fromisoformat(last['sent_at']).replace(tzinfo=dt_module.timezone.utc).timestamp()
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
                    logger.info(
                        f"[CONSENSUS] ⏭️  BLOCKED: ignore_30m_same_outcome condition={condition_id[:20]}... outcome={outcome_index} side={side} mins={minutes_since:.1f}"
                    )
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
                    logger.info(
                        f"[CONSENSUS] ⏭️  BLOCKED: dedupe_no_growth_10m condition={condition_id[:20]}... outcome={outcome_index} side={side} "
                        f"(minutes_since={minutes_since:.1f}, wallets_grew={wallets_grew}, price_change={price_change:.4f})"
                    )
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
                    logger.info(
                        f"[CONSENSUS] ⏭️  BLOCKED: no_trigger_matched condition={condition_id[:20]}... outcome={outcome_index} side={side} "
                        f"(outcome_changed={outcome_changed}, wallets_grew={wallets_grew}, has_new_wallet={has_new_wallet}, "
                        f"price_change={price_change:.4f}, should_refresh={should_refresh_due_time})"
                    )
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
            
            # STEP 8: Don't send if we recently alerted same market/side (30-minute cooldown to prevent spam)
            logger.info(f"[CONSENSUS] Step 8/9: Checking cooldown for condition={condition_id[:20]}... outcome={outcome_index} side={side} (cooldown={self.alert_cooldown_min} min)")
            has_recent_cooldown = self.db.has_recent_alert(condition_id, outcome_index, side, self.alert_cooldown_min)
            logger.info(f"[CONSENSUS] Step 8/9: Has recent alert in cooldown = {has_recent_cooldown}")
            if has_recent_cooldown:
                self.suppressed_counts['cooldown'] = self.suppressed_counts.get('cooldown', 0) + 1
                if not hasattr(self, 'monitoring_stats'):
                    self.monitoring_stats = {"total_alerts_blocked": 0, "blocked_reasons": {}}
                self.monitoring_stats["total_alerts_blocked"] = self.monitoring_stats.get("total_alerts_blocked", 0) + 1
                reason = "cooldown"
                self.monitoring_stats["blocked_reasons"][reason] = self.monitoring_stats["blocked_reasons"].get(reason, 0) + 1
                logger.info(
                    f"[CONSENSUS] ⏭️  BLOCKED: Cooldown (30min) - "
                    f"condition={condition_id[:20]}... outcome={outcome_index} side={side} "
                    f"wallets={len(wallets_in_window)}"
                )
                return
            # STEP 9: Don't send if there was an opposite-side alert recently (conflict avoidance)
            logger.info(f"[CONSENSUS] Step 9/9: Checking opposite side alerts for condition={condition_id[:20]}... outcome={outcome_index} side={side}")
            has_opposite_recent = self.db.has_recent_opposite_alert(condition_id, outcome_index, side, self.conflict_window_min)
            logger.info(f"[CONSENSUS] Step 9/9: Has recent opposite side alert = {has_opposite_recent}")
            if has_opposite_recent:
                self.suppressed_counts['opposite_recent'] = self.suppressed_counts.get('opposite_recent', 0) + 1
                if not hasattr(self, 'monitoring_stats'):
                    self.monitoring_stats = {"total_alerts_blocked": 0, "blocked_reasons": {}}
                self.monitoring_stats["total_alerts_blocked"] = self.monitoring_stats.get("total_alerts_blocked", 0) + 1
                reason = "opposite_recent"
                self.monitoring_stats["blocked_reasons"][reason] = self.monitoring_stats["blocked_reasons"].get(reason, 0) + 1
                logger.info(
                    f"[CONSENSUS] ⏭️  BLOCKED: Opposite side recent - "
                    f"condition={condition_id[:20]}... outcome={outcome_index} side={side} "
                    f"wallets={len(wallets_in_window)}"
                )
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

            # STEP 10: Check minimum total position size
            logger.info(f"[CONSENSUS] Step 10/10: Checking minimum total position size: ${total_usd:.2f} >= ${self.min_total_position_usd:.2f}")
            if total_usd < self.min_total_position_usd:
                if not hasattr(self, 'monitoring_stats'):
                    self.monitoring_stats = {"total_alerts_blocked": 0, "blocked_reasons": {}}
                self.monitoring_stats["total_alerts_blocked"] = self.monitoring_stats.get("total_alerts_blocked", 0) + 1
                reason = "insufficient_position_size"
                self.monitoring_stats["blocked_reasons"][reason] = self.monitoring_stats["blocked_reasons"].get(reason, 0) + 1
                logger.info(
                    f"[CONSENSUS] ⏭️  BLOCKED: Insufficient total position size - "
                    f"${total_usd:.2f} < ${self.min_total_position_usd:.2f} "
                    f"condition={condition_id[:20]}... outcome={outcome_index} side={side} wallets={len(wallets_in_window)}"
                )
                return
            
            # STEP 11: Check if this is a repeat alert (position increased >2x)
            is_repeat_alert = False
            has_existing_alert = self.db.has_alert_for_market(condition_id, outcome_index, side)
            
            if has_existing_alert:
                first_total_usd = self.db.get_first_total_usd(condition_id, outcome_index, side)
                if first_total_usd is not None:
                    if total_usd >= 2.0 * first_total_usd:
                        is_repeat_alert = True
                        logger.info(
                            f"[CONSENSUS] 🔄 REPEAT ALERT: Position increased >2x - "
                            f"${total_usd:.2f} >= 2 * ${first_total_usd:.2f} = ${2.0 * first_total_usd:.2f} "
                            f"condition={condition_id[:20]}... outcome={outcome_index} side={side}"
                        )
                    else:
                        logger.info(
                            f"[CONSENSUS] ⏭️  BLOCKED: Alert already sent, position not increased >2x - "
                            f"${total_usd:.2f} < 2 * ${first_total_usd:.2f} = ${2.0 * first_total_usd:.2f} "
                            f"condition={condition_id[:20]}... outcome={outcome_index} side={side}"
                        )
                        return
                else:
                    # Alert exists but first_total_usd is not set (old alert), treat as first alert
                    logger.info(
                        f"[CONSENSUS] ℹ️  Alert exists but first_total_usd not set, treating as first alert - "
                        f"condition={condition_id[:20]}... outcome={outcome_index} side={side}"
                    )
            else:
                logger.info(
                    f"[CONSENSUS] ℹ️  First alert for this market - "
                    f"condition={condition_id[:20]}... outcome={outcome_index} side={side} total_usd=${total_usd:.2f}"
                )
            
            # All checks passed! Prepare to send alert
            alert_type = "REPEAT" if is_repeat_alert else "FIRST"
            logger.info(f"[CONSENSUS] ✅ All checks passed! Preparing to send {alert_type} alert for condition={condition_id[:20]}... outcome={outcome_index} side={side}")
            
            # Get market info to extract end_date
            market_info = self.get_market_info(condition_id)
            end_date = market_info.get("end_date") if market_info else None
            
            # Get category for this market
            category = "other/Unknown"
            try:
                from gamma_client import get_event_by_condition_id
                event = get_event_by_condition_id(condition_id)
                if event:
                    markets = event.get("markets", [])
                    for market in markets:
                        market_condition_id = market.get("conditionId") or market.get("condition_id")
                        if market_condition_id and market_condition_id.lower() == condition_id.lower():
                            slug = market.get("slug") or market.get("marketSlug")
                            question = market.get("question") or market.get("title")
                            category = classify_market(event, slug, question)
                            break
                    if category == "other/Unknown":
                        slug = event.get("slug") or event.get("eventSlug")
                        question = event.get("question") or event.get("title")
                        category = classify_market(event, slug, question)
                else:
                    # Fallback: classify from slug/question if available
                    category = classify_market({}, market_slug, market_title)
            except Exception as e:
                logger.debug(f"[CONSENSUS] Error classifying market category: {e}")
                # Fallback: classify from slug/question if available
                category = classify_market({}, market_slug, market_title)
            
            logger.info(f"[CONSENSUS] Category for condition={condition_id[:20]}...: {category}")
            
            # Get A List status for wallets in this category
            a_list_wallets = []
            for wallet in wallets_in_window:
                if self.db.is_wallet_a_list_in_category(wallet, category):
                    a_list_wallets.append(wallet)
            
            logger.info(f"[CONSENSUS] A List traders in this signal: {len(a_list_wallets)}/{len(wallets_in_window)}")
            if a_list_wallets:
                logger.info(f"[CONSENSUS] A List wallets: {', '.join([w[:12] + '...' for w in a_list_wallets[:5]])}")
            
            # Send alert with prices and consensus flow (events per minute)
            # Pass current_price (may be None) - send_consensus_alert will handle it
            alert_id = key[:8]
            # Use filtered events count (events within time window)
            events_count = len(filtered_events) if 'filtered_events' in locals() else len(window_data.get("events", []))
            
            logger.info("=" * 80)
            logger.info(f"[CONSENSUS] 📤 SENDING ALERT:")
            logger.info(f"[CONSENSUS]   - Condition: {condition_id[:30]}...")
            logger.info(f"[CONSENSUS]   - Outcome: {outcome_index}")
            logger.info(f"[CONSENSUS]   - Side: {side}")
            logger.info(f"[CONSENSUS]   - Category: {category}")
            logger.info(f"[CONSENSUS]   - A List traders: {len(a_list_wallets)}/{len(wallets_in_window)}")
            logger.info(f"[CONSENSUS]   - Wallets: {len(wallets_in_window)}")
            logger.info(f"[CONSENSUS]   - Events: {events_count}")
            logger.info(f"[CONSENSUS]   - Total USD: ${total_usd:.2f}")
            logger.info(f"[CONSENSUS]   - Current Price: {current_price}")
            logger.info(f"[CONSENSUS]   - Market Title: {market_title[:50] if market_title else 'N/A'}...")
            logger.info("=" * 80)
            
            # Check for OI spike confirmation (enforce 5-minute window between samples)
            oi_confirmed = False
            order_flow_confirmed = False
            try:
                spike_result = self.db.calculate_oi_spike(condition_id, self.oi_spike_threshold_percent, max_minutes=5)
                if spike_result:
                    oi_confirmed = True
                    logger.info(f"[CONSENSUS] ✅ OI confirmed: {condition_id[:20]}... spiked by {spike_result['spike_percent']:.1f}%")
            except Exception as e:
                logger.debug(f"[CONSENSUS] Could not check OI spike: {e}")
            
            # Check for order flow confirmation
            try:
                latest_order_flow = self.db.get_latest_order_flow(condition_id, outcome_index)
                if latest_order_flow and latest_order_flow.get('is_imbalanced'):
                    flow_direction = latest_order_flow.get('imbalance_direction', '').upper()
                    
                    # Check freshness of the order flow metric
                    detected_at = latest_order_flow.get('detected_at')
                    age_minutes = None
                    if detected_at:
                        try:
                            # Parse detected_at as aware UTC datetime
                            detected_time = datetime.fromisoformat(detected_at.replace('Z', '+00:00'))
                            if detected_time.tzinfo is None:
                                detected_time = detected_time.replace(tzinfo=timezone.utc)
                            # Compute age in minutes
                            age_minutes = (datetime.now(timezone.utc) - detected_time).total_seconds() / 60.0
                        except Exception as e:
                            logger.debug(f"[CONSENSUS] Could not parse detected_at timestamp: {e}")
                    
                    # Set freshness threshold (default: 2x the order flow time window)
                    max_age_min = self.order_flow_time_window_min * 2
                    
                    # Confirm if order flow direction matches consensus side AND metric is fresh
                    direction_matches = (side.upper() == 'BUY' and flow_direction == 'BUY') or \
                                      (side.upper() == 'SELL' and flow_direction == 'SELL')
                    
                    if direction_matches:
                        if age_minutes is not None and age_minutes <= max_age_min:
                            order_flow_confirmed = True
                            logger.info(f"[CONSENSUS] ✅ Order flow confirmed: {condition_id[:20]}... {flow_direction} imbalance matches {side} consensus (age: {age_minutes:.1f}min)")
                        elif age_minutes is not None:
                            logger.info(f"[CONSENSUS] ⚠️ Order flow present but too old: {condition_id[:20]}... {flow_direction} imbalance matches {side} consensus but age {age_minutes:.1f}min exceeds threshold {max_age_min:.1f}min")
                        else:
                            # If we can't determine age, don't confirm (safety first)
                            logger.debug(f"[CONSENSUS] Order flow present but detected_at timestamp unavailable or invalid: {condition_id[:20]}...")
            except Exception as e:
                logger.debug(f"[CONSENSUS] Could not check order flow: {e}")
            
            # Check for news correlation (only for high-confidence consensus)
            news_context = None
            is_high_confidence = (
                len(wallets_in_window) >= self.news_min_wallets_for_check or
                len(a_list_wallets) >= self.news_min_a_list_for_check
            )
            
            if is_high_confidence:
                try:
                    consensus_timestamp = window_data.get('last_ts', time.time())
                    news_context = self.check_news_correlation(market_title, condition_id, consensus_timestamp)
                    if news_context:
                        logger.info(f"[CONSENSUS] ✅ News correlation found: {news_context.get('headline', '')[:50]}...")
                    else:
                        logger.info(f"[CONSENSUS] ⚠️ No news correlation found for high-confidence consensus")
                except Exception as e:
                    logger.debug(f"[CONSENSUS] Could not check news correlation: {e}")
                    news_context = None
            else:
                logger.debug(f"[CONSENSUS] Skipping news check (low confidence: {len(wallets_in_window)} wallets, {len(a_list_wallets)} A-list)")
            
            logger.info(f"[NOTIFY] Preparing to send consensus alert: condition={condition_id[:20]}... outcome={outcome_index} side={side} wallets={len(wallets_in_window)} oi_confirmed={oi_confirmed} order_flow_confirmed={order_flow_confirmed} news_context={'present' if news_context else 'none'}")
            try:
                success = self.notifier.send_consensus_alert(
                    condition_id, outcome_index, wallets_in_window, wallet_prices,
                    self.alert_window_min, self.min_consensus, alert_id, market_title, market_slug, side,
                    consensus_events=events_count,
                    total_usd=total_usd,
                    end_date=end_date,
                    current_price=current_price,  # Pass current_price (may be None)
                    oi_confirmed=oi_confirmed,  # Pass OI confirmation flag
                    order_flow_confirmed=order_flow_confirmed,  # Pass order flow confirmation flag
                    news_context=news_context  # Pass news context
                    # Removed category and a_list_wallets - not in method signature
                )
            except Exception as e:
                logger.error(f"[NOTIFY] ❌ Exception while calling send_consensus_alert: {e}", exc_info=True)
                success = False
            
            if success:
                if not hasattr(self, 'monitoring_stats'):
                    self.monitoring_stats = {"total_alerts_sent": 0}
                self.monitoring_stats["total_alerts_sent"] = self.monitoring_stats.get("total_alerts_sent", 0) + 1
                logger.info(
                    f"[CONSENSUS] ✅ ALERT SENT SUCCESSFULLY (#{self.monitoring_stats['total_alerts_sent']}): "
                    f"condition={condition_id[:20]}... outcome={outcome_index} side={side} "
                    f"wallets={len(wallets_in_window)}"
                )
            else:
                if not hasattr(self, 'monitoring_stats'):
                    self.monitoring_stats = {"total_alerts_blocked": 0, "blocked_reasons": {}}
                self.monitoring_stats["total_alerts_blocked"] = self.monitoring_stats.get("total_alerts_blocked", 0) + 1
                reason = "send_failed"
                self.monitoring_stats["blocked_reasons"][reason] = self.monitoring_stats["blocked_reasons"].get(reason, 0) + 1
                logger.error(
                    f"[CONSENSUS] ❌ ALERT SEND FAILED: "
                    f"condition={condition_id[:20]}... outcome={outcome_index} side={side} "
                    f"wallets={len(wallets_in_window)}"
                )
                return
            
            # Collect wallet details (address, usd_amount, price) for saving
            # Use filtered events (only events within time window)
            wallet_details = []
            try:
                # Use filtered_events if available, otherwise filter from window_data
                if 'filtered_events' in locals():
                    events = filtered_events
                else:
                    events = window_data.get("events", [])
                    # Re-filter events to ensure we only use recent ones within time window
                    if events:
                        latest_event_ts = max(e["ts"] for e in events)
                        window_start_ts = latest_event_ts - (self.alert_window_min * 60)
                        events = [e for e in events if e["ts"] >= window_start_ts]
                
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
                logger.info(f"[CONSENSUS] Saved wallet details for {len(wallet_details)} wallets: {wallet_details_json[:200]}...")
            except Exception as e:
                logger.warning(f"[CONSENSUS] Error collecting wallet details: {e}")
                wallet_details_json = ""
            
            # Mark alert as sent
            # Use wallets_for_db (saved copy) to ensure wallets are always saved correctly
            wallets_csv_str = ",".join(wallets_for_db) if wallets_for_db else ""
            wallet_count_for_db = len(wallets_for_db)
            
            # Log warning if wallets_csv is empty but we have wallet_count > 0
            if not wallets_csv_str and wallet_count_for_db > 0:
                logger.warning(f"[CONSENSUS] ⚠️  wallets_csv is empty but wallets_for_db has {wallet_count_for_db} wallets!")
            
            # Log if wallets_in_window was modified
            if len(wallets_in_window) != wallet_count_for_db:
                logger.warning(f"[CONSENSUS] ⚠️  wallets_in_window was modified! Original: {wallet_count_for_db}, Current: {len(wallets_in_window)}")
            
            alert_saved = self.db.mark_alert_sent(
                condition_id, outcome_index, wallet_count_for_db,
                window_data["first_ts"], window_data["last_ts"], alert_key, side,
                price=(current_price or 0.0), wallets_csv=wallets_csv_str,
                wallet_details_json=wallet_details_json,
                total_usd=total_usd,
                is_repeat=is_repeat_alert
            )
            
            if alert_saved:
                logger.info(
                    f"[Consensus] ALERT condition={condition_id[:20]}... outcome={outcome_index} side={side} "
                    f"wallets={len(wallets_in_window)} price={current_price or 0.0:.4f}"
                )
            else:
                logger.error(f"❌ Failed to save alert to database for {condition_id}:{outcome_index} "
                            f"(alert was sent to Telegram but not saved)")
            
        except Exception as e:
            logger.error(f"Error checking consensus: {e}")
    
    def check_open_interest_spikes(self) -> Dict[str, int]:
        """Check for open interest spikes in active markets
        
        Note: Currently, OI monitoring operates only on markets seen in rolling_buys
        (markets with recent consensus activity), not on all tracked markets. This narrower
        scope is intentional and focuses monitoring on markets with active trading activity
        from tracked wallets. To monitor all tracked markets, you would need to expand
        the selection logic to include markets from tracked wallet positions or a dedicated
        tracked markets table.
        """
        try:
            import time
            from clickhouse_client import RateLimitExceeded
            
            # Check if enough time has passed since last check
            current_time = time.time()
            if self.last_oi_check_time > 0:
                time_since_last_check = (current_time - self.last_oi_check_time) / 60.0
                if time_since_last_check < self.oi_check_interval_min:
                    return {'checked': 0, 'spikes': 0, 'errors': 0}
            
            self.oi_check_stats['total_checks'] += 1
            
            # Get list of active markets from recent consensus events
            # Note: This limits OI monitoring to markets with recent rolling consensus activity
            active_markets = self.db.get_active_markets_from_rolling_buys(minutes=30)
            
            if not active_markets:
                logger.debug("[OI] No active markets found for OI check")
                return {'checked': 0, 'spikes': 0, 'errors': 0}
            
            spikes_detected = 0
            errors = 0
            
            for condition_id in active_markets:
                try:
                    # Query ClickHouse for OI data
                    oi_data = self.clickhouse_client.get_market_open_interest(condition_id)
                    
                    if not oi_data:
                        continue
                    
                    open_interest = oi_data.get('open_interest')
                    timestamp = oi_data.get('timestamp')
                    
                    if open_interest is None or timestamp is None:
                        continue
                    
                    # Insert OI data into database
                    self.db.insert_open_interest(condition_id, open_interest, timestamp)
                    
                    # Calculate spike (enforce 5-minute window between samples)
                    spike_result = self.db.calculate_oi_spike(condition_id, self.oi_spike_threshold_percent, max_minutes=5)
                    
                    if spike_result:
                        spikes_detected += 1
                        self.oi_check_stats['spikes_detected'] += 1
                        
                        # Get market details for alert
                        market_title = ""
                        market_slug = ""
                        try:
                            # Try to get market details from API
                            market_url = f"{self.data_api}/markets/{condition_id}"
                            market_response = self.http_get(market_url, allow_404_as_none=True)
                            if market_response:
                                market_data = market_response.json() if hasattr(market_response, 'json') else market_response
                                market_title = market_data.get('question', market_title)
                                market_slug = market_data.get('slug', market_slug)
                        except Exception as e:
                            logger.debug(f"[OI] Could not fetch market details for {condition_id}: {e}")
                        
                        # Send OI spike alert
                        self.notifier.send_oi_spike_alert(
                            condition_id=condition_id,
                            market_title=market_title,
                            market_slug=market_slug,
                            old_oi=spike_result['old_oi'],
                            new_oi=spike_result['new_oi'],
                            spike_percent=spike_result['spike_percent'],
                            timestamp=spike_result['timestamp']
                        )
                        
                        logger.info(f"[OI] 🔥 Spike detected: {condition_id[:20]}... OI increased by {spike_result['spike_percent']:.1f}%")
                
                except RateLimitExceeded as e:
                    logger.warning(f"[OI] Rate limit exceeded, skipping remaining markets: {e}")
                    errors += 1
                    break
                
                except Exception as e:
                    logger.error(f"[OI] Error checking OI for {condition_id}: {e}")
                    errors += 1
                    self.oi_check_stats['errors'] += 1
            
            self.last_oi_check_time = current_time
            
            stats = {
                'checked': len(active_markets),
                'spikes': spikes_detected,
                'errors': errors
            }
            
            logger.info(f"[OI] Check complete: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"[OI] Error in check_open_interest_spikes: {e}", exc_info=True)
            return {'checked': 0, 'spikes': 0, 'errors': 1}
    
    def check_news_correlation(self, market_title: str, condition_id: str, consensus_timestamp: float) -> Optional[Dict[str, Any]]:
        """
        Check for news articles correlated with a consensus event
        
        Args:
            market_title: Market title/topic to search for news
            condition_id: Market condition ID (for logging)
            consensus_timestamp: Unix timestamp of consensus event
            
        Returns:
            Dict with keys {'headline': str, 'source': str, 'published_at': str, 'url': str} or None
        """
        # Check if news correlation is enabled and client is available
        if not self.adj_news_client or not self.news_correlation_enabled:
            return None
        
        # Validate inputs
        if not market_title or not isinstance(market_title, str) or not market_title.strip():
            logger.debug(f"[AdjNews] Invalid market_title for news check: {condition_id[:20]}...")
            return None
        
        # Increment stats
        self.news_correlation_stats['total_checks'] += 1
        
        try:
            # Query adj.news API for market news (1 day lookback, limit 5 articles)
            articles = self.adj_news_client.get_market_news(market_title.strip(), days=1, limit=5)
            
            if not articles or len(articles) == 0:
                logger.debug(f"[AdjNews] No news articles found for market: {market_title[:50]}...")
                return None
            
            # Filter articles published within time window of consensus event
            time_window_seconds = self.news_time_window_hours * 3600
            relevant_articles = []
            
            for article in articles:
                try:
                    # Extract published_at timestamp from article
                    published_at = article.get('published_at') or article.get('publishedAt') or article.get('timestamp')
                    if not published_at:
                        continue
                    
                    # Parse timestamp (handle both ISO format and Unix timestamp)
                    if isinstance(published_at, (int, float)):
                        article_timestamp = float(published_at)
                    elif isinstance(published_at, str):
                        try:
                            # Try ISO format first
                            dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                            article_timestamp = dt.timestamp()
                        except (ValueError, AttributeError):
                            # Try Unix timestamp string
                            try:
                                article_timestamp = float(published_at)
                            except ValueError:
                                continue
                    else:
                        continue
                    
                    # Check if article is within time window
                    time_diff = abs(consensus_timestamp - article_timestamp)
                    if time_diff <= time_window_seconds:
                        relevant_articles.append({
                            'article': article,
                            'timestamp': article_timestamp,
                            'time_diff': time_diff
                        })
                except Exception as e:
                    logger.debug(f"[AdjNews] Error parsing article timestamp: {e}")
                    continue
            
            if not relevant_articles:
                logger.debug(f"[AdjNews] No news articles within {self.news_time_window_hours}h window for: {market_title[:50]}...")
                return None
            
            # Sort by time difference (closest to consensus event first)
            relevant_articles.sort(key=lambda x: x['time_diff'])
            
            # Extract first relevant article
            best_article = relevant_articles[0]['article']
            
            # Extract article fields
            headline = best_article.get('headline') or best_article.get('title') or best_article.get('text', '')[:100]
            source = best_article.get('source') or best_article.get('domain') or 'Unknown'
            published_at = best_article.get('published_at') or best_article.get('publishedAt') or best_article.get('timestamp')
            url = best_article.get('url') or best_article.get('link') or ''
            
            # Increment stats
            self.news_correlation_stats['news_found'] += 1
            
            # Log API usage stats
            rate_limit_status = self.adj_news_client.get_rate_limit_status()
            cache_stats = self.adj_news_client.get_cache_stats()
            
            logger.info(
                f"[AdjNews] ✅ News correlation found: {headline[:50]}... "
                f"(daily: {rate_limit_status['daily_queries_used']}/{rate_limit_status['daily_queries_limit']}, "
                f"cache: {cache_stats['hit_rate_percent']:.1f}%)"
            )
            
            # Log warning if approaching daily limit
            if rate_limit_status['daily_queries_used'] > 25:
                logger.warning(
                    f"[AdjNews] ⚠️ Approaching daily rate limit: "
                    f"{rate_limit_status['daily_queries_used']}/{rate_limit_status['daily_queries_limit']} used"
                )
            
            return {
                'headline': headline,
                'source': source,
                'published_at': str(published_at),
                'url': url
            }
            
        except AdjNewsRateLimitExceeded as e:
            self.news_correlation_stats['rate_limited'] += 1
            logger.warning(
                f"[AdjNews] ⚠️ Rate limit exceeded: {e.wait_time:.1f}s wait time. "
                f"Skipping news check for: {market_title[:50]}..."
            )
            return None
            
        except Exception as e:
            self.news_correlation_stats['errors'] += 1
            logger.error(f"[AdjNews] ❌ Error checking news correlation for {market_title[:50]}...: {e}", exc_info=True)
            return None
            self.oi_check_stats['errors'] += 1
            return {'checked': 0, 'spikes': 0, 'errors': 1}
    
    def check_whale_positions(self) -> Dict[str, int]:
        """Check for whale position changes in A-list wallets"""
        try:
            import time
            from clickhouse_client import RateLimitExceeded
            
            self.whale_check_stats['total_checks'] += 1
            
            # Get list of A-list wallets
            a_list_wallets = self.db.get_a_list_wallets()
            
            if not a_list_wallets:
                logger.debug("[WHALE] No A-list wallets found")
                return {'checked': 0, 'positions': 0, 'errors': 0}
            
            positions_detected = 0
            errors = 0
            
            for wallet_address in a_list_wallets:
                try:
                    # Query ClickHouse for user positions
                    positions = self.clickhouse_client.get_user_positions(wallet_address)
                    
                    if not positions:
                        continue
                    
                    for position in positions:
                        try:
                            condition_id = position.get('condition_id')
                            outcome_index = position.get('outcome_index', 0)
                            quantity = position.get('quantity', 0.0)
                            
                            if not condition_id:
                                continue
                            
                            # Get current price for position size calculation
                            token_id = f"{condition_id}:{outcome_index}"
                            current_price = self.clickhouse_client.get_latest_price(token_id)
                            
                            if current_price is None or current_price <= 0:
                                continue
                            
                            # Calculate position size in USD
                            position_size_usd = quantity * current_price
                            
                            # Get last known position before applying threshold filter
                            # This allows us to detect full exits when position falls below threshold
                            last_position = self.db.get_last_whale_position(wallet_address, condition_id)
                            
                            # Check if this is a full exit (previously whale-sized, now below threshold)
                            if last_position:
                                last_size = last_position.get('position_size_usd', 0)
                                last_position_type = last_position.get('position_type', '')
                                
                                # Detect full exit: previously whale-sized, now below threshold
                                if last_size >= self.whale_position_size_usd and position_size_usd < self.whale_position_size_usd:
                                    # This is a full exit - position fell below whale threshold
                                    position_type = 'exit'
                                    
                                    # Insert whale position record for the exit
                                    self.db.insert_whale_position(
                                        user_address=wallet_address,
                                        condition_id=condition_id,
                                        outcome_index=outcome_index,
                                        position_size_usd=position_size_usd,
                                        position_type=position_type
                                    )
                                    
                                    positions_detected += 1
                                    self.whale_check_stats['positions_detected'] += 1
                                    
                                    # Get market details for alert
                                    market_title = ""
                                    market_slug = ""
                                    try:
                                        market_url = f"{self.data_api}/markets/{condition_id}"
                                        market_response = self.http_get(market_url, allow_404_as_none=True)
                                        if market_response:
                                            market_data = market_response.json() if hasattr(market_response, 'json') else market_response
                                            market_title = market_data.get('question', market_title)
                                            market_slug = market_data.get('slug', market_slug)
                                    except Exception as e:
                                        logger.debug(f"[WHALE] Could not fetch market details for {condition_id}: {e}")
                                    
                                    # Send whale position alert for exit
                                    self.notifier.send_whale_position_alert(
                                        user_address=wallet_address,
                                        condition_id=condition_id,
                                        outcome_index=outcome_index,
                                        market_title=market_title,
                                        market_slug=market_slug,
                                        position_size_usd=position_size_usd,
                                        position_type=position_type,
                                        current_price=current_price
                                    )
                                    
                                    logger.info(f"[WHALE] 🐋 {position_type.upper()} detected: {wallet_address[:12]}... position ${position_size_usd:,.0f} in {condition_id[:20]}... (full exit from ${last_size:,.0f})")
                                    continue  # Skip further processing for this position
                            
                            # Process positions that are currently above whale threshold
                            if position_size_usd >= self.whale_position_size_usd:
                                # Detect entry or partial exit
                                position_type = 'entry'
                                if last_position:
                                    last_size = last_position.get('position_size_usd', 0)
                                    if position_size_usd < last_size * 0.5:  # Position reduced by >50%
                                        position_type = 'exit'  # Partial exit
                                    elif position_size_usd <= last_size * 1.1:  # Position similar (within 10%)
                                        continue  # Skip if position hasn't changed significantly
                                
                                # Insert whale position
                                self.db.insert_whale_position(
                                    user_address=wallet_address,
                                    condition_id=condition_id,
                                    outcome_index=outcome_index,
                                    position_size_usd=position_size_usd,
                                    position_type=position_type
                                )
                                
                                positions_detected += 1
                                self.whale_check_stats['positions_detected'] += 1
                                
                                # Get market details for alert
                                market_title = ""
                                market_slug = ""
                                try:
                                    market_url = f"{self.data_api}/markets/{condition_id}"
                                    market_response = self.http_get(market_url, allow_404_as_none=True)
                                    if market_response:
                                        market_data = market_response.json() if hasattr(market_response, 'json') else market_response
                                        market_title = market_data.get('question', market_title)
                                        market_slug = market_data.get('slug', market_slug)
                                except Exception as e:
                                    logger.debug(f"[WHALE] Could not fetch market details for {condition_id}: {e}")
                                
                                # Send whale position alert
                                self.notifier.send_whale_position_alert(
                                    user_address=wallet_address,
                                    condition_id=condition_id,
                                    outcome_index=outcome_index,
                                    market_title=market_title,
                                    market_slug=market_slug,
                                    position_size_usd=position_size_usd,
                                    position_type=position_type,
                                    current_price=current_price
                                )
                                
                                logger.info(f"[WHALE] 🐋 {position_type.upper()} detected: {wallet_address[:12]}... position ${position_size_usd:,.0f} in {condition_id[:20]}...")
                        
                        except Exception as e:
                            logger.error(f"[WHALE] Error processing position for {wallet_address}: {e}")
                            errors += 1
                
                except RateLimitExceeded as e:
                    logger.warning(f"[WHALE] Rate limit exceeded, skipping remaining wallets: {e}")
                    errors += 1
                    break
                
                except Exception as e:
                    logger.error(f"[WHALE] Error checking positions for {wallet_address}: {e}")
                    errors += 1
                    self.whale_check_stats['errors'] += 1
            
            stats = {
                'checked': len(a_list_wallets),
                'positions': positions_detected,
                'errors': errors
            }
            
            logger.info(f"[WHALE] Check complete: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"[WHALE] Error in check_whale_positions: {e}", exc_info=True)
            self.whale_check_stats['errors'] += 1
            return {'checked': 0, 'positions': 0, 'errors': 1}
    
    def process_pending_whale_alerts(self) -> int:
        """Process pending whale alerts that haven't been sent yet"""
        try:
            pending_alerts = self.db.get_pending_whale_alerts(limit=10)
            
            alerts_sent = 0
            for alert in pending_alerts:
                try:
                    condition_id = alert['condition_id']
                    user_address = alert['user_address']
                    outcome_index = alert['outcome_index']
                    position_size_usd = alert['position_size_usd']
                    position_type = alert['position_type']
                    
                    # Get market details
                    market_title = ""
                    market_slug = ""
                    current_price = 0.0
                    
                    try:
                        market_url = f"{self.data_api}/markets/{condition_id}"
                        market_response = self.http_get(market_url, allow_404_as_none=True)
                        if market_response:
                            market_data = market_response.json() if hasattr(market_response, 'json') else market_response
                            market_title = market_data.get('question', market_title)
                            market_slug = market_data.get('slug', market_slug)
                        
                        # Get current price
                        token_id = f"{condition_id}:{outcome_index}"
                        current_price = self.clickhouse_client.get_latest_price(token_id) or 0.0
                    except Exception as e:
                        logger.debug(f"[WHALE] Could not fetch market details for pending alert: {e}")
                    
                    # Send alert
                    success = self.notifier.send_whale_position_alert(
                        user_address=user_address,
                        condition_id=condition_id,
                        outcome_index=outcome_index,
                        market_title=market_title,
                        market_slug=market_slug,
                        position_size_usd=position_size_usd,
                        position_type=position_type,
                        current_price=current_price
                    )
                    
                    if success:
                        # Mark as alerted
                        self.db.mark_whale_position_alerted(alert['id'])
                        alerts_sent += 1
                
                except Exception as e:
                    logger.error(f"[WHALE] Error processing pending alert {alert.get('id')}: {e}")
            
            if alerts_sent > 0:
                logger.info(f"[WHALE] Sent {alerts_sent} pending whale alerts")
            
            return alerts_sent
            
        except Exception as e:
            logger.error(f"[WHALE] Error processing pending whale alerts: {e}", exc_info=True)
            return 0

    def check_order_flow_imbalances(self) -> Dict[str, int]:
        """Check for order flow imbalances in active markets"""
        try:
            import time
            from datetime import datetime, timezone, timedelta
            from clickhouse_client import RateLimitExceeded
            
            # Check if enough time has passed since last check
            now = time.time()
            if now - self.last_order_flow_check_time < (self.order_flow_check_interval_min * 60):
                return {'checked': 0, 'imbalances': 0, 'errors': 0}
            
            self.order_flow_stats['total_checks'] += 1
            
            # Get list of active markets from recent consensus alerts (last 24 hours)
            cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            active_markets = []
            
            try:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT DISTINCT condition_id, outcome_index
                        FROM alerts_sent
                        WHERE sent_at >= ?
                    """, (cutoff_time,))
                    rows = cursor.fetchall()
                    active_markets = [(row[0], row[1]) for row in rows]
            except Exception as e:
                logger.error(f"[ORDER_FLOW] Error getting active markets: {e}")
                return {'checked': 0, 'imbalances': 0, 'errors': 1}
            
            if not active_markets:
                logger.debug("[ORDER_FLOW] No active markets found")
                return {'checked': 0, 'imbalances': 0, 'errors': 0}
            
            imbalances_detected = 0
            errors = 0
            
            for condition_id, outcome_index in active_markets:
                try:
                    # Query ClickHouse for recent orders
                    orders = self.clickhouse_client.get_orders_matched(
                        condition_id=condition_id,
                        outcome_index=outcome_index,
                        minutes_back=int(self.order_flow_time_window_min)
                    )
                    
                    if not orders:
                        continue
                    
                    # Calculate buy/sell counts and volumes
                    buy_count = 0
                    sell_count = 0
                    buy_volume = 0.0
                    sell_volume = 0.0
                    
                    for order in orders:
                        side = order.get('side', '').upper()
                        size = float(order.get('size', 0.0))
                        price = float(order.get('price', 0.0))
                        volume = size * price
                        
                        if side == 'BUY':
                            buy_count += 1
                            buy_volume += volume
                        elif side == 'SELL':
                            sell_count += 1
                            sell_volume += volume
                    
                    total_volume = buy_volume + sell_volume
                    if total_volume == 0:
                        continue
                    
                    # Calculate buy/sell ratio
                    buy_sell_ratio = buy_volume / total_volume
                    
                    # Detect imbalance
                    is_imbalanced = False
                    imbalance_direction = None
                    
                    if buy_sell_ratio > self.order_flow_imbalance_threshold:
                        is_imbalanced = True
                        imbalance_direction = 'BUY'
                    elif buy_sell_ratio < (1 - self.order_flow_imbalance_threshold):
                        is_imbalanced = True
                        imbalance_direction = 'SELL'
                    
                    if not is_imbalanced:
                        continue
                    
                    # Check if imbalance already detected recently (within last check interval)
                    latest_metric = self.db.get_latest_order_flow(condition_id, outcome_index)
                    if latest_metric:
                        latest_detected_at = latest_metric.get('detected_at')
                        if latest_detected_at:
                            try:
                                latest_time = datetime.fromisoformat(latest_detected_at.replace('Z', '+00:00'))
                                if latest_time.tzinfo is None:
                                    latest_time = latest_time.replace(tzinfo=timezone.utc)
                                time_diff = (datetime.now(timezone.utc) - latest_time).total_seconds() / 60.0
                                if time_diff < self.order_flow_check_interval_min:
                                    continue  # Already detected recently
                            except Exception:
                                pass  # Continue if timestamp parsing fails
                    
                    # Insert new imbalance metric
                    window_start = (datetime.now(timezone.utc) - timedelta(minutes=self.order_flow_time_window_min)).isoformat()
                    window_end = datetime.now(timezone.utc).isoformat()
                    
                    success = self.db.insert_order_flow_metric(
                        condition_id=condition_id,
                        outcome_index=outcome_index,
                        window_start=window_start,
                        window_end=window_end,
                        buy_count=buy_count,
                        sell_count=sell_count,
                        buy_volume=buy_volume,
                        sell_volume=sell_volume,
                        buy_sell_ratio=buy_sell_ratio,
                        is_imbalanced=True,
                        imbalance_direction=imbalance_direction
                    )
                    
                    if success:
                        imbalances_detected += 1
                        self.order_flow_stats['imbalances_detected'] += 1
                        logger.info(
                            f"[ORDER_FLOW] Imbalance detected: {condition_id[:20]}... "
                            f"{imbalance_direction} {buy_sell_ratio*100:.1f}% "
                            f"(buy={buy_count}, sell={sell_count}, vol=${total_volume:.2f})"
                        )
                
                except RateLimitExceeded as e:
                    logger.warning(f"[ORDER_FLOW] Rate limit exceeded: {e}")
                    errors += 1
                    self.order_flow_stats['errors'] += 1
                    break  # Stop processing if rate limited
                
                except Exception as e:
                    logger.error(f"[ORDER_FLOW] Error checking market {condition_id[:20]}...: {e}")
                    errors += 1
                    self.order_flow_stats['errors'] += 1
                    continue
            
            self.last_order_flow_check_time = now
            logger.info(
                f"[ORDER_FLOW] Checked {len(active_markets)} markets, "
                f"detected {imbalances_detected} imbalances, {errors} errors"
            )
            
            return {'checked': len(active_markets), 'imbalances': imbalances_detected, 'errors': errors}
            
        except Exception as e:
            logger.error(f"[ORDER_FLOW] Error in check_order_flow_imbalances: {e}", exc_info=True)
            self.order_flow_stats['errors'] += 1
            return {'checked': 0, 'imbalances': 0, 'errors': 1}
    
    def process_pending_order_flow_alerts(self) -> int:
        """Process pending order flow alerts that haven't been sent yet"""
        try:
            pending_alerts = self.db.get_pending_order_flow_alerts(limit=10)
            
            alerts_sent = 0
            for alert in pending_alerts:
                try:
                    condition_id = alert['condition_id']
                    outcome_index = alert['outcome_index']
                    buy_count = alert['buy_count']
                    sell_count = alert['sell_count']
                    buy_volume = alert['buy_volume']
                    sell_volume = alert['sell_volume']
                    buy_sell_ratio = alert['buy_sell_ratio']
                    imbalance_direction = alert['imbalance_direction']
                    window_end = alert['window_end']
                    
                    # Calculate window minutes from window_end
                    try:
                        window_end_dt = datetime.fromisoformat(window_end.replace('Z', '+00:00'))
                        if window_end_dt.tzinfo is None:
                            window_end_dt = window_end_dt.replace(tzinfo=timezone.utc)
                        window_start_dt = datetime.fromisoformat(alert['window_start'].replace('Z', '+00:00'))
                        if window_start_dt.tzinfo is None:
                            window_start_dt = window_start_dt.replace(tzinfo=timezone.utc)
                        window_minutes = (window_end_dt - window_start_dt).total_seconds() / 60.0
                    except Exception:
                        window_minutes = self.order_flow_time_window_min
                    
                    # Get market details
                    market_title = ""
                    market_slug = ""
                    current_price = None
                    end_date = None
                    
                    try:
                        market_url = f"{self.data_api}/markets/{condition_id}"
                        market_response = self.http_get(market_url, allow_404_as_none=True)
                        if market_response:
                            market_data = market_response.json() if hasattr(market_response, 'json') else market_response
                            market_title = market_data.get('question', market_title)
                            market_slug = market_data.get('slug', market_slug)
                            
                            # Get end date
                            end_date_str = market_data.get('endDate')
                            if end_date_str:
                                try:
                                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                                    if end_date.tzinfo is None:
                                        end_date = end_date.replace(tzinfo=timezone.utc)
                                except Exception:
                                    pass
                        
                        # Get current price
                        token_id = f"{condition_id}:{outcome_index}"
                        current_price = self.clickhouse_client.get_latest_price(token_id)
                    except Exception as e:
                        logger.debug(f"[ORDER_FLOW] Could not fetch market details for pending alert: {e}")
                    
                    # Send alert
                    success = self.notifier.send_order_flow_alert(
                        condition_id=condition_id,
                        outcome_index=outcome_index,
                        buy_count=buy_count,
                        sell_count=sell_count,
                        buy_volume=buy_volume,
                        sell_volume=sell_volume,
                        buy_sell_ratio=buy_sell_ratio,
                        imbalance_direction=imbalance_direction,
                        window_minutes=window_minutes,
                        market_title=market_title,
                        market_slug=market_slug,
                        current_price=current_price,
                        end_date=end_date
                    )
                    
                    if success:
                        # Mark as alerted
                        self.db.mark_order_flow_alerted(alert['id'])
                        alerts_sent += 1
                
                except Exception as e:
                    logger.error(f"[ORDER_FLOW] Error processing pending alert {alert.get('id')}: {e}")
            
            if alerts_sent > 0:
                logger.info(f"[ORDER_FLOW] Sent {alerts_sent} pending order flow alerts")
            
            return alerts_sent
            
        except Exception as e:
            logger.error(f"[ORDER_FLOW] Error processing pending order flow alerts: {e}", exc_info=True)
            return 0

    def monitor_wallets(self):
        """Main monitoring loop"""
        logger.info("=" * 80)
        logger.info("[MONITOR] Starting wallet monitoring...")
        logger.info("=" * 80)
        self.monitoring = True
        
        # Initialize monitoring stats
        self.monitoring_stats = {
            "total_loops": 0,
            "total_trades_found": 0,
            "total_events_processed": 0,
            "total_consensus_candidates": 0,
            "total_alerts_sent": 0,
            "total_alerts_blocked": 0,
            "blocked_reasons": {}
        }
        
        while self.monitoring:
            try:
                # Get tracked wallets - use strict criteria for wallets with data, relaxed for new wallets
                # New wallets (without analysis data) will be included with relaxed criteria so they can be analyzed
                # Wallets with analysis data will be filtered using strict quality criteria
                wallets = self.db.get_tracked_wallets(
                    min_trades=MIN_TRADES, max_trades=self.max_predictions,
                    min_win_rate=WIN_RATE_THRESHOLD, max_win_rate=1.0,
                    max_daily_freq=MAX_DAILY_FREQUENCY, limit=self.max_wallets,
                    use_strict_criteria=True  # Apply strict quality filters (markets, volume, ROI, avg_pnl, avg_stake)
                )
                
                if not wallets:
                    logger.warning("[MONITOR] ⚠️  No wallets to monitor - check wallet collection and filtering")
                    time.sleep(self.poll_interval)
                    continue
                
                logger.info(f"[MONITOR] 📊 Monitoring {len(wallets)} tracked wallets")
                
                self.loop_count += 1
                self.monitoring_stats["total_loops"] += 1
                
                # Send heartbeat every 10 loops (every ~70 seconds with 7s poll interval)
                if self.loop_count % 10 == 0:
                    stats = self.db.get_wallet_stats()
                    queue_stats = self.wallet_analyzer.get_queue_status()
                    logger.info(f"[MONITOR] Loop #{self.loop_count} - Monitoring {len(wallets)} wallets")
                    logger.info(f"[MONITOR] Queue status: {queue_stats}")
                    logger.info(f"[MONITOR] Stats: trades={self.monitoring_stats['total_trades_found']} "
                              f"events={self.monitoring_stats['total_events_processed']} "
                              f"candidates={self.monitoring_stats['total_consensus_candidates']} "
                              f"alerts_sent={self.monitoring_stats['total_alerts_sent']} "
                              f"alerts_blocked={self.monitoring_stats['total_alerts_blocked']}")
                    if self.telegram_heartbeat_enabled:
                        self.notifier.send_heartbeat(stats)
                # Send suppression diagnostics roughly hourly
                # ~514 loops ≈ 1 hour at 7s interval
                if self.loop_count % 514 == 0:
                    try:
                        self.notifier.send_suppression_report(self.suppressed_counts)
                        # Also send errors report
                        if hasattr(self.notifier, 'send_error_report'):
                            self.notifier.send_error_report(self.error_counts)
                        # reset after sending
                        for k in list(self.suppressed_counts.keys()):
                            self.suppressed_counts[k] = 0
                        for k in list(self.error_counts.keys()):
                            self.error_counts[k] = 0
                    except Exception as e:
                        logger.warning(f"Failed to send suppression report: {e}")
                
                # Heartbeat log every 30 seconds (every ~4 loops with 7s poll interval)
                # Heartbeat log every 30 seconds (every ~4 loops with 7s poll interval)
                if self.loop_count % 4 == 0:
                    stats = self.db.get_wallet_stats()
                    queue_stats = self.wallet_analyzer.get_queue_status()
                    now_iso = datetime.now(timezone.utc).isoformat()
                    
                    # Format: [HB] queue=447 analyzed=129 wallets=74 time=2025-01-01T12:01:33Z
                    queue_total = queue_stats.get('total_jobs', 0)
                    queue_pending = queue_stats.get('pending_jobs', 0)
                    queue_completed = queue_stats.get('completed_jobs', 0)
                    analyzed_count = stats.get('total_wallets', 0)
                    tracked_wallets = stats.get('tracked_wallets', 0)
                    
                    # Get recent alerts count (last 7 hours)
                    from datetime import timedelta
                    seven_hours_ago = datetime.now(timezone.utc) - timedelta(hours=7)
                    recent_alerts = self.db.get_recent_alerts_count(since=seven_hours_ago.isoformat())
                    
                    logger.info(
                        f"[HB] queue_total={queue_total} queue_pending={queue_pending} queue_completed={queue_completed} "
                        f"analyzed={analyzed_count} tracked={tracked_wallets} alerts_7h={recent_alerts} "
                        f"trades={self.monitoring_stats['total_trades_found']} events={self.monitoring_stats['total_events_processed']} "
                        f"candidates={self.monitoring_stats['total_consensus_candidates']} sent={self.monitoring_stats['total_alerts_sent']} "
                        f"blocked={self.monitoring_stats['total_alerts_blocked']} time={now_iso}"
                    )
                
                # Collect new wallets from leaderboard if needed (every 20 loops)
                if self.loop_count % 20 == 0:
                    # Temporarily use relaxed filters to include newly added wallets (they will be analyzed later)
                    # New wallets have traded_total=0 and win_rate=0.0, so we need to include them
                    current_wallets = self.db.get_tracked_wallets(min_trades=0, max_trades=self.max_predictions, min_win_rate=0.0, max_win_rate=1.0, max_daily_freq=MAX_DAILY_FREQUENCY, limit=self.max_wallets)
                    if len(current_wallets) < self.max_wallets:
                        logger.info(f"Only {len(current_wallets)} wallets, collecting more...")
                        wallets_dict = asyncio.run(self.collect_wallets_from_leaderboards())
                        # Use stored analytics_stats if available
                        analytics_stats = getattr(self, '_last_analytics_stats', None)
                        self.analyze_and_filter_wallets(wallets_dict, analytics_stats=analytics_stats)
                
                # Clean up old wallets every 50 loops
                if self.loop_count % 50 == 0:
                    self.db.cleanup_old_wallets(self.max_predictions, self.max_wallets)
                
                # Clean up expired cache every 100 loops
                if self.loop_count % 100 == 0:
                    cleaned = self.db.cleanup_expired_cache()
                    if cleaned > 0:
                        logger.info(f"Cleaned up {cleaned} expired cache entries")
                
                # Check open interest spikes every 5 minutes (~43 loops at 7s interval)
                if self.loop_count % 43 == 0:
                    try:
                        oi_stats = self.check_open_interest_spikes()
                        if oi_stats['checked'] > 0:
                            logger.info(f"[OI] Stats: {oi_stats}")
                    except Exception as e:
                        logger.error(f"[OI] Error in OI check: {e}")
                
                # Check whale positions every 5 minutes (~43 loops at 7s interval)
                if self.loop_count % 43 == 0:
                    try:
                        whale_stats = self.check_whale_positions()
                        
                        # Check for order flow imbalances
                        try:
                            order_flow_stats = self.check_order_flow_imbalances()
                        except Exception as e:
                            logger.error(f"[ORDER_FLOW] Error in check_order_flow_imbalances: {e}", exc_info=True)
                        if whale_stats['checked'] > 0:
                            logger.info(f"[WHALE] Stats: {whale_stats}")
                    except Exception as e:
                        logger.error(f"[WHALE] Error in whale check: {e}")
                
                # Process pending whale alerts every loop
                try:
                    pending_count = self.process_pending_whale_alerts()
                    
                    # Process pending order flow alerts
                    try:
                        order_flow_pending = self.process_pending_order_flow_alerts()
                    except Exception as e:
                        logger.error(f"[ORDER_FLOW] Error in process_pending_order_flow_alerts: {e}", exc_info=True)
                    if pending_count > 0:
                        logger.info(f"[WHALE] Processed {pending_count} pending alerts")
                except Exception as e:
                    logger.error(f"[WHALE] Error processing pending alerts: {e}")
                
                # Log OI, whale, and order flow stats periodically (every 10 loops)
                if self.loop_count % 10 == 0:
                    logger.info(f"[STATS] OI: {self.oi_check_stats}, Whale: {self.whale_check_stats}, Order Flow: {self.order_flow_stats}")
                
                # Monitor each wallet
                loop_trades_found = 0
                loop_events_processed = 0
                for wallet in wallets:
                    try:
                        last_trade_id = self.db.get_last_seen_trade_id(wallet)
                        # Fetch BUY and SELL trades
                        buy_events, newest_buy_id = self.get_new_trades(wallet, last_trade_id, "BUY")
                        sell_events, newest_sell_id = self.get_new_trades(wallet, last_trade_id, "SELL")
                        new_events = buy_events + sell_events
                        newest_id = newest_buy_id or newest_sell_id
                        
                        if new_events:
                            loop_trades_found += 1
                            self.monitoring_stats["total_trades_found"] += len(new_events)
                            logger.info(f"[MONITOR] 💰 {wallet[:12]}...: {len(new_events)} new trades (BUY: {len(buy_events)}, SELL: {len(sell_events)})")
                        
                        # Process each new event (filter out old events to avoid processing closed markets)
                        current_time = time.time()
                        max_event_age_hours = 48  # Ignore events older than 48 hours
                        max_event_age_seconds = max_event_age_hours * 3600
                        
                        events_skipped_old = 0
                        events_skipped_invalid = 0
                        events_skipped_closed = 0
                        recent_events = []
                        
                        for event in new_events:
                            # Skip events that are too old (likely from closed markets)
                            event_timestamp = event.get("timestamp", 0)
                            if event_timestamp and event_timestamp > 0:
                                # Validate timestamp is reasonable
                                if event_timestamp < 946684800 or event_timestamp > current_time + 3600:
                                    events_skipped_invalid += 1
                                    logger.debug(f"[MONITOR] Invalid timestamp {event_timestamp} for event {event.get('trade_id', 'unknown')[:12]}..., skipping")
                                    continue
                                
                                event_age = current_time - event_timestamp
                                if event_age < 0:
                                    events_skipped_invalid += 1
                                    logger.warning(f"[MONITOR] Event {event.get('trade_id', 'unknown')[:12]}... has future timestamp (age: {event_age:.1f}s), skipping")
                                    continue
                                
                                if event_age > max_event_age_seconds:
                                    events_skipped_old += 1
                                    logger.debug(f"[MONITOR] Skipping old event: {event.get('trade_id', 'unknown')[:12]}... (age: {event_age/3600:.1f}h)")
                                    continue
                                
                                # Event passed age filter
                                recent_events.append(event)
                            elif not event_timestamp or event_timestamp <= 0:
                                events_skipped_invalid += 1
                                logger.debug(f"[MONITOR] Event {event.get('trade_id', 'unknown')[:12]}... has no valid timestamp, skipping")
                                continue
                        
                        # Log filtering summary
                        if new_events:
                            logger.info(f"[TRADES] 💰 Wallet {wallet[:12]}...: {len(recent_events)} recent trades (<= {max_event_age_hours}h) "
                                      f"out of {len(new_events)} total (skipped: old={events_skipped_old}, invalid={events_skipped_invalid})")
                        
                        # Process only recent events
                        for event in recent_events:
                            # BEST-EFFORT: Extract market_title from event (for display purposes only)
                            # NOTE: We NO LONGER extract market_slug from events - all slug normalization
                            # is handled by notify.TelegramNotifier._get_event_slug_and_market_id() and _get_market_slug()
                            market_title = event.get("marketTitle", "")
                            market_slug = ""  # Always empty - notify.py will fetch and normalize slug via API
                            price = event.get("price", 0)
                            side = event.get("side", "BUY")
                            usd_amount = event.get("usd", 0.0)
                            quantity = event.get("quantity", 0.0)
                            
                            # Handle missing condition_id - use fallback identifier
                            condition_id = event.get("conditionId")
                            if not condition_id:
                                # Use market title as fallback identifier (market_slug is no longer extracted from events)
                                if market_title:
                                    condition_id = f"TITLE:{market_title[:50]}"
                                else:
                                    logger.warning(f"[MONITOR] Skipping event: no condition_id and no market_title")
                                    continue
                            
                            outcome_index = event.get("outcomeIndex")
                            if outcome_index is None:
                                outcome_index = 0  # Default to 0
                            
                            # EARLY CHECK: Verify market is still active before processing event
                            # Skip this check if condition_id is a fallback (starts with SLUG: or TITLE:)
                            # This allows signals even when condition_id is not available
                            if condition_id and not condition_id.startswith(("SLUG:", "TITLE:")):
                                if not self.is_market_active(condition_id, outcome_index):
                                    events_skipped_closed += 1
                                    logger.debug(f"[MONITOR] Skipping event for closed market: {condition_id[:20]}... outcome={outcome_index} (entry price was ${price:.3f})")
                                    continue
                            
                            # Process event for consensus
                            loop_events_processed += 1
                            self.monitoring_stats["total_events_processed"] += 1
                            
                            self.check_consensus_and_alert(
                                condition_id, outcome_index,
                                wallet, event["trade_id"], event["timestamp"], 
                                price, side, market_title, market_slug,
                                usd_amount=usd_amount, quantity=quantity
                            )
                        
                        # Log summary for this wallet if we processed events
                        if new_events:
                            processed_count = len(recent_events) - events_skipped_closed
                            if events_skipped_old > 0 or events_skipped_invalid > 0 or events_skipped_closed > 0:
                                logger.info(f"[MONITOR] {wallet[:12]}...: processed {processed_count}/{len(new_events)} events "
                                          f"(skipped: old={events_skipped_old}, invalid={events_skipped_invalid}, closed={events_skipped_closed})")
                        
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
        if not BET_MONITOR_AVAILABLE or not self.bet_detector:
            logger.info("Bet monitoring not available, skipping...")
            return None
        
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
        
        # Start bet monitoring (if available)
        bet_monitoring_task = await self.start_bet_monitoring()
        
        # Send startup notification
        stats = self.db.get_wallet_stats()
        queue_stats = self.wallet_analyzer.get_queue_status()
        
        # Log database path and stats for debugging
        logger.info(f"[DB] Database path: {self.db_path}")
        logger.info(f"[DB] Total wallets in DB: {stats.get('total_wallets', 0)}")
        logger.info(f"[DB] Actively tracked: {stats.get('tracked_wallets', 0)}")
        logger.info(f"[DB] Queue status: {queue_stats}")
        
        self.notifier.send_startup_notification(
            stats.get('total_wallets', 0),
            stats.get('tracked_wallets', 0)
        )
        
        # Collect wallets from leaderboards (non-blocking, with timeout)
        # Check if startup collection should be skipped
        skip_collection = os.getenv("SKIP_STARTUP_COLLECTION", "false").lower() == "true"
        
        if not skip_collection:
            try:
                logger.info("Starting wallet collection from leaderboards...")
                # IMPORTANT: Use timeout to prevent blocking monitoring
                # collect_wallets_from_leaderboards is async, so we can await it directly with timeout
                wallets = await asyncio.wait_for(
                    self.collect_wallets_from_leaderboards(),
                    timeout=120.0  # 2 min timeout
                )
                if wallets:
                    logger.info(f"Collected {len(wallets)} wallets from leaderboards")
                    # Use stored analytics_stats if available
                    analytics_stats = getattr(self, '_last_analytics_stats', None)
                    self.analyze_and_filter_wallets(wallets, analytics_stats=analytics_stats)
                else:
                    logger.info("No new wallets collected from leaderboards")
            except asyncio.TimeoutError:
                logger.warning("Wallet collection timed out after 2 minutes, continuing with monitoring...")
            except Exception as e:
                logger.error(f"Error collecting wallets from leaderboards: {e}, continuing with monitoring...", exc_info=True)
        else:
            logger.info("[STARTUP] SKIP_STARTUP_COLLECTION=true — пропускаю сбор кошельков при старте")
        
        # Start monitoring (CRITICAL: This must always run)
        logger.info("=" * 80)
        logger.info("Starting wallet monitoring loop...")
        logger.info("=" * 80)
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
            if bet_monitoring_task:
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