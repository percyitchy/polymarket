"""
Telegram Notification Functions for Polymarket Notifier
Handles sending formatted alerts via Telegram Bot API
"""

import os
import requests
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from dotenv import load_dotenv

# Import datetime module to avoid conflicts with datetime class
import datetime as dt_module

# Load environment variables
load_dotenv()

# Import PolymarketAuth for authenticated requests
try:
    from polymarket_auth import PolymarketAuth
    POLYMARKET_AUTH_AVAILABLE = True
except ImportError:
    POLYMARKET_AUTH_AVAILABLE = False

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None, 
                 reports_chat_id: Optional[str] = None, hashdive_client: Optional[Any] = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")  # public signals
        # admin/reports channel; default to provided id if env not set
        self.reports_chat_id = reports_chat_id or os.getenv("TELEGRAM_REPORTS_CHAT_ID", "-1002792658553")
        # test reports channel (for experimental alerts)
        self.reports_test_chat_id = os.getenv("TELEGRAM_REPORTS_TEST_CHAT_ID") or self.reports_chat_id
        # Topic ID for forum groups (optional)
        topic_id_str = os.getenv("TELEGRAM_TOPIC_ID")
        self.topic_id = int(topic_id_str) if topic_id_str and topic_id_str.isdigit() else None
        
        # Topic IDs for size-based routing
        low_size_topic_id_str = os.getenv("TELEGRAM_LOW_SIZE_TOPIC_ID")
        self.low_size_topic_id = int(low_size_topic_id_str) if low_size_topic_id_str and low_size_topic_id_str.isdigit() else None
        
        high_size_topic_id_str = os.getenv("TELEGRAM_HIGH_SIZE_TOPIC_ID")
        self.high_size_topic_id = int(high_size_topic_id_str) if high_size_topic_id_str and high_size_topic_id_str.isdigit() else None
        
        # Topic ID for A-list alerts (2+ A-list traders)
        a_list_topic_id_str = os.getenv("TELEGRAM_A_LIST_TOPIC_ID")
        self.a_list_topic_id = int(a_list_topic_id_str) if a_list_topic_id_str and a_list_topic_id_str.isdigit() else None
        
        # Topic ID for insider alerts (suspicious trading patterns)
        insider_topic_id_str = os.getenv("TELEGRAM_INSIDER_TOPIC_ID")
        self.insider_topic_id = int(insider_topic_id_str) if insider_topic_id_str and insider_topic_id_str.isdigit() else None
        
        # Topic ID for OI spike alerts
        oi_spike_topic_id_str = os.getenv("TELEGRAM_OI_SPIKE_TOPIC_ID")
        self.oi_spike_topic_id = int(oi_spike_topic_id_str) if oi_spike_topic_id_str and oi_spike_topic_id_str.isdigit() else None
        
        # Topic ID for whale position alerts
        whale_position_topic_id_str = os.getenv("TELEGRAM_WHALE_POSITION_TOPIC_ID")
        self.whale_position_topic_id = int(whale_position_topic_id_str) if whale_position_topic_id_str and whale_position_topic_id_str.isdigit() else None
        
        order_flow_topic_id_str = os.getenv("TELEGRAM_ORDER_FLOW_TOPIC_ID")
        self.order_flow_topic_id = int(order_flow_topic_id_str) if order_flow_topic_id_str and order_flow_topic_id_str.isdigit() else None
        
        # Insider detection thresholds (for alert display)
        self.insider_min_position_size = float(os.getenv("INSIDER_MIN_POSITION_SIZE", "5000.0"))
        
        # Size threshold for routing (default: $10,000)
        self.size_threshold_usd = float(os.getenv("SIZE_THRESHOLD_USD", "10000.0"))
        
        # Store HashiDive client for price fallback
        self.hashdive_client = hashdive_client
        
        # Initialize Polymarket authentication (optional)
        self.polymarket_auth = None
        if POLYMARKET_AUTH_AVAILABLE:
            try:
                self.polymarket_auth = PolymarketAuth()
            except Exception as e:
                logger.debug(f"Failed to initialize PolymarketAuth: {e}")
        
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram credentials not configured. Notifications will be printed to console.")
    
    def _make_authenticated_get(self, url: str, timeout: int = 5) -> requests.Response:
        """Make authenticated GET request to Polymarket API if auth is available"""
        # TEMPORARILY DISABLED: Builder API authentication disabled (keys not visible on site)
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }
        # if self.polymarket_auth and self.polymarket_auth.has_auth:
        #     from urllib.parse import urlparse
        #     parsed = urlparse(url)
        #     request_path = parsed.path
        #     auth_headers = self.polymarket_auth.get_auth_headers("GET", request_path)
        #     headers.update(auth_headers)
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            return response
        except requests.exceptions.Timeout:
            logger.warning(f"[HTTP] Timeout for {url[:100]}...")
            raise
        except requests.exceptions.RequestException as e:
            logger.warning(f"[HTTP] Request error for {url[:100]}...: {type(e).__name__}: {e}")
            raise
        except Exception as e:
            logger.error(f"[HTTP] Unexpected error for {url[:100]}...: {type(e).__name__}: {e}")
            raise
    
    def send_message(self, text: str, parse_mode: Optional[str] = "Markdown", 
                    disable_web_page_preview: bool = True,
                    reply_markup: Optional[Dict[str, Any]] = None,
                    chat_id: Optional[str] = None,
                    message_thread_id: Optional[int] = None) -> bool:
        """
        Send a message to Telegram
        
        Args:
            text: Message text
            parse_mode: HTML, Markdown, or None for plain text (default: "Markdown")
            disable_web_page_preview: Disable link previews
            reply_markup: Inline keyboard markup
            chat_id: Override default chat ID
            message_thread_id: Topic/thread ID for forum groups
            
        Returns:
            True if successful, False otherwise
        """
        target_chat = chat_id or self.chat_id
        if not self.bot_token or not target_chat:
            logger.info(f"[TELEGRAM] Would send: {text}")
            return False
            
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview
        }
        # Only include parse_mode if it's not None (plain text mode)
        if parse_mode is not None:
            payload["parse_mode"] = parse_mode
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id
        
        try:
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            logger.info(f"[NOTIFY] ✅ Telegram message sent successfully to chat_id={chat_id or self.chat_id}")
            return True
        except requests.exceptions.HTTPError as e:
            # Log response details for debugging
            if hasattr(e.response, 'text'):
                logger.error(f"[NOTIFY] ❌ Failed to send Telegram message: {e} - Response: {e.response.text[:200]}")
            else:
                logger.error(f"[NOTIFY] ❌ Failed to send Telegram message: {e}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"[NOTIFY] ❌ Failed to send Telegram message (RequestException): {e}")
            return False
        except Exception as e:
            logger.error(f"[NOTIFY] ❌ Unexpected error sending Telegram message: {e}", exc_info=True)
            return False
    
    def send_consensus_alert(self, condition_id: str, outcome_index: int, 
                           wallets: List[str], wallet_prices: Dict[str, float] = {},
                           window_minutes: float = 10.0, min_consensus: int = 3, 
                           alert_id: str = "", market_title: str = "", 
                           market_slug: str = "", side: str = "BUY",
                           consensus_events: Optional[int] = None,
                           total_usd: Optional[float] = None,
                           end_date: Optional[dt_module.datetime] = None,
                           current_price: Optional[float] = None,
                           category: Optional[str] = None,
                           a_list_wallets: Optional[List[str]] = None,
                           oi_confirmed: bool = False,
                           order_flow_confirmed: bool = False,
                           news_context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send a consensus buy signal alert
        
        Args:
            condition_id: Market condition ID
            outcome_index: Outcome index being bought
            wallets: List of wallet addresses that bought
            window_minutes: Time window for consensus
            min_consensus: Minimum wallets required for alert
            alert_id: Unique alert identifier
            market_title: Market title to display
            
        Returns:
            True if sent successfully
        """
        if len(wallets) < min_consensus:
            logger.warning(f"[NOTIFY] ⚠️  Not enough wallets for consensus: {len(wallets)} < {min_consensus}")
            return False
        
        # CRITICAL EARLY CHECK: Don't send alerts for closed markets (check end_date first)
        if end_date:
            current_time = dt_module.datetime.now(dt_module.timezone.utc)
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=dt_module.timezone.utc)
            if current_time > end_date:
                logger.info(f"[NOTIFY] ⏭️  BLOCKED: Market closed (end_date passed: {end_date.isoformat()}) condition={condition_id[:20]}... outcome={outcome_index} wallets={len(wallets)}")
                # Only send suppressed alert if we have consensus (multiple wallets)
                if len(wallets) >= min_consensus:
                    try:
                        self.send_suppressed_alert_details(
                            reason="market_closed",
                            condition_id=condition_id,
                            outcome_index=outcome_index,
                            wallets=wallets,
                            wallet_prices=wallet_prices,
                            market_title=market_title,
                            market_slug=market_slug,
                            current_price=current_price,
                            side=side,
                            total_usd=total_usd,
                            market_active=False
                        )
                    except Exception as e:
                        logger.debug(f"Failed to send suppressed alert details: {e}")
                return False
        
        logger.info(f"[NOTIFY] 📨 Preparing to send consensus alert: {len(wallets)} wallets, condition={condition_id[:20]}... outcome={outcome_index} side={side}")
        
        # DIAGNOSTICS: Log initial values before any transformations
        logger.info(
            f"[URL] [DIAGNOSTICS] Initial values for URL resolution: "
            f"condition_id={condition_id[:20]}..., "
            f"market_title='{market_title[:50] if market_title else 'None'}', "
            f"market_slug_param='{market_slug[:50] if market_slug else 'None'}'"
        )
        
        # We will render specific trader lines below (Markdown)
        # Calculate consensus strength
        strength = self._calculate_consensus_strength(len(wallets), window_minutes)
        logger.info(f"[NOTIFY] Consensus strength calculated: {strength}")
        
        # Format market URL - Support complex markets with event_slug/market_slug format and sports URLs
        # CRITICAL: Always fetch slugs via API - market_slug parameter from events is no longer trusted
        # If market_slug parameter is empty/None, we always call _get_event_slug_and_market_id() and _get_market_slug()
        # Wrap in try-except to prevent exceptions from blocking notifications
        try:
            event_slug, market_id, market_slug_from_api, event_obj = self._get_event_slug_and_market_id(condition_id)
        except Exception as e:
            logger.error(f"[URL] ❌ Exception in _get_event_slug_and_market_id: {type(e).__name__}: {e}", exc_info=True)
            # Fallback: set to None and continue - we'll use search URL fallback
            event_slug, market_id, market_slug_from_api, event_obj = None, None, None, None
            logger.warning(f"[URL] ⚠️  Continuing with fallback URL generation after API error (condition_id={condition_id[:20]}...)")
        
        # DIAGNOSTICS: Log API-fetched values
        logger.info(
            f"[URL] [DIAGNOSTICS] API-fetched values: "
            f"event_slug='{event_slug[:50] if event_slug else 'None'}', "
            f"market_slug_from_api='{market_slug_from_api[:50] if market_slug_from_api else 'None'}', "
            f"market_id={market_id}, "
            f"event_obj_available={event_obj is not None}"
        )
        
        # If market_slug parameter is empty, fetch it via API (market_slug_from_api may also be None)
        # This ensures we always have normalized slugs from API, not from raw events
        if not market_slug:
            logger.debug(f"[URL] market_slug parameter is empty, fetching via _get_market_slug() for condition={condition_id[:20]}...")
            if not market_slug_from_api:
                market_slug_from_api = self._get_market_slug(condition_id)
        else:
            # If market_slug was provided (legacy/fallback), log warning but still prefer API slug
            logger.warning(f"[URL] ⚠️  market_slug parameter provided from events (deprecated): {market_slug[:50] if market_slug else 'empty'}. "
                         f"Preferring API-fetched slug: {market_slug_from_api[:50] if market_slug_from_api else 'None'} (condition_id={condition_id[:20]}...)")
            # Still use API slug if available, otherwise use provided slug as fallback
            if not market_slug_from_api:
                market_slug_from_api = market_slug
        
        # If market_id is still None, try to get it from CLOB API directly (CRITICAL for complex markets)
        if not market_id:
            logger.warning(f"[URL] market_id is None after Gamma API, trying CLOB API fallback for condition={condition_id[:20]}...")
            try:
                clob_url = f"https://clob.polymarket.com/markets/{condition_id}"
                clob_response = self._make_authenticated_get(clob_url, timeout=5)
                if clob_response and clob_response.status_code == 200:
                    clob_data = clob_response.json()
                    # Try multiple field names for market ID
                    clob_market_id = (clob_data.get('id') or 
                                    clob_data.get('marketId') or 
                                    clob_data.get('tid') or
                                    clob_data.get('market_id') or
                                    clob_data.get('marketIdNum'))
                    if clob_market_id:
                        try:
                            # Handle string IDs with numeric extraction
                            if isinstance(clob_market_id, str):
                                import re
                                numeric_match = re.search(r'\d+', str(clob_market_id))
                                if numeric_match:
                                    market_id = int(numeric_match.group())
                                else:
                                    market_id = None
                            else:
                                market_id = int(clob_market_id)
                            if market_id:
                                logger.info(f"[URL] ✅ Got market_id={market_id} from CLOB API direct query for condition={condition_id[:20]}...")
                        except (ValueError, TypeError) as e:
                            logger.debug(f"[URL] Failed to parse market_id from CLOB API: {clob_market_id}, error: {e}")
                            market_id = None
                    else:
                        logger.warning(f"[URL] No market_id found in CLOB API response for condition={condition_id[:20]}... Available fields: {list(clob_data.keys())[:20]}")
                else:
                    logger.warning(f"[URL] CLOB API returned status {clob_response.status_code if clob_response else 'None'} for condition={condition_id[:20]}...")
            except Exception as e:
                logger.warning(f"[URL] Failed to get market_id from CLOB API direct query: {e}")
            
            # Fallback: Try Data API if CLOB API didn't provide market_id
            if not market_id:
                logger.warning(f"[URL] market_id is still None after CLOB API, trying Data API fallback for condition={condition_id[:20]}...")
                try:
                    data_api_url = f"https://data-api.polymarket.com/condition/{condition_id}"
                    data_api_response = self._make_authenticated_get(data_api_url, timeout=5)
                    if data_api_response and data_api_response.status_code == 200:
                        data_api_data = data_api_response.json()
                        # Try multiple field names for market ID
                        data_api_market_id = (data_api_data.get('id') or 
                                            data_api_data.get('marketId') or 
                                            data_api_data.get('tid') or
                                            data_api_data.get('market_id') or
                                            data_api_data.get('marketIdNum'))
                        if data_api_market_id:
                            try:
                                # Handle string IDs with numeric extraction
                                if isinstance(data_api_market_id, str):
                                    import re
                                    numeric_match = re.search(r'\d+', str(data_api_market_id))
                                    if numeric_match:
                                        market_id = int(numeric_match.group())
                                    else:
                                        market_id = None
                                else:
                                    market_id = int(data_api_market_id)
                                if market_id:
                                    logger.info(f"[URL] ✅ Got market_id={market_id} from Data API fallback for condition={condition_id[:20]}...")
                            except (ValueError, TypeError) as e:
                                logger.debug(f"[URL] Failed to parse market_id from Data API: {data_api_market_id}, error: {e}")
                                market_id = None
                        else:
                            logger.warning(f"[URL] No market_id found in Data API response for condition={condition_id[:20]}... Available fields: {list(data_api_data.keys())[:20]}")
                    else:
                        logger.warning(f"[URL] Data API returned status {data_api_response.status_code if data_api_response else 'None'} for condition={condition_id[:20]}...")
                except Exception as e:
                    logger.warning(f"[URL] Failed to get market_id from Data API fallback: {e}")
        
        # Detect if this is a sports market
        # Use market_slug_from_api (always prefer API-fetched slug, never use parameter from events)
        slug_for_detection = market_slug_from_api or event_slug
        is_sports_market = self._detect_sports_event(event_obj, event_slug, slug_for_detection)
        
        # DIAGNOSTICS: Unified logging for URL resolution context
        logger.info(
            f"[URL] [DIAGNOSTICS] URL resolution context: "
            f"condition_id={condition_id[:20]}..., "
            f"event_slug='{event_slug[:50] if event_slug else 'None'}', "
            f"market_slug_from_api='{market_slug_from_api[:50] if market_slug_from_api else 'None'}', "
            f"market_slug_param='{market_slug[:50] if market_slug else 'None'}', "
            f"market_id={market_id}, "
            f"is_sports_market={is_sports_market}, "
            f"event_obj_available={event_obj is not None}"
        )
        
        # Log sports market detection result
        logger.info(f"[URL] [SPORTS] Sports market detected: is_sports={is_sports_market}")
        logger.debug(f"[URL] [SPORTS]   - event_slug: {event_slug}")
        logger.debug(f"[URL] [SPORTS]   - market_slug_from_api: {market_slug_from_api}")
        logger.debug(f"[URL] [SPORTS]   - event_obj available: {event_obj is not None}")
        logger.debug(f"[URL] [SPORTS]   - slug_for_detection: {slug_for_detection}")
        
        # Fetch event for sports markets when event_obj is None
        if is_sports_market and event_obj is None:
            logger.info(f"[GAMMA] [SPORTS] Fetching event for sports market using slug={slug_for_detection}")
            try:
                from gamma_client import get_event_by_slug
                fetched_event = get_event_by_slug(slug_for_detection)
                if fetched_event:
                    event_obj = fetched_event
                    event_id = fetched_event.get('id')
                    logger.info(f"[GAMMA] [SPORTS] Successfully fetched event for sports market, event_id={event_id}")
                else:
                    logger.info(f"[GAMMA] [SPORTS] Failed to fetch event for sports market using slug={slug_for_detection}")
            except Exception as e:
                logger.debug(f"[GAMMA] [SPORTS] Exception while fetching event for sports market: {e}")
        
        # Priority 1: Sports markets - try multiple data sources for URL construction
        sports_url = None
        if is_sports_market:
            # Step 1: If event_obj is available, try to get sports URL from event object
            if event_obj:
                logger.debug(f"[URL] [SPORTS] Attempting to extract sports URL from event object...")
                sports_url = self._get_sports_url_from_event(event_obj, event_slug)
                
                if sports_url:
                    market_url = sports_url
                    logger.info(f"[URL] [SPORTS] Using sports URL from event: {market_url} (condition_id={condition_id[:20]}...)")
                    logger.info(f"[URL] [SPORTS] FINAL SPORTS URL: {market_url} (method: sports_url_from_event, condition_id={condition_id[:20]}...)")
                else:
                    logger.debug(f"[URL] [SPORTS] Sports URL extraction result: NOT FOUND")
            
            # Step 2: If no sports URL from event object (or event_obj is None), try slug-based construction
            if not sports_url:
                logger.debug(f"[URL] [SPORTS] Attempting slug-based sports URL construction...")
                constructed_sports_url = self._construct_sports_url_from_slug(slug_for_detection, event_obj)
                if constructed_sports_url:
                    sports_url = constructed_sports_url
                    market_url = sports_url
                    logger.info(f"[URL] [SPORTS] Constructed sports URL from slug pattern: {sports_url}")
                    logger.info(f"[URL] [SPORTS] FINAL SPORTS URL: {market_url} (method: constructed_from_slug, condition_id={condition_id[:20]}...)")
            
            # Step 3: If slug-based construction failed, try CLOB-based /sports/ URL scan
            if not sports_url:
                logger.debug(f"[URL] [SPORTS] Attempting CLOB-based /sports/ URL discovery...")
                clob_sports_url_found = False
                try:
                    clob_url = f"https://clob.polymarket.com/markets/{condition_id}"
                    clob_response = self._make_authenticated_get(clob_url, timeout=5)
                    if clob_response and clob_response.status_code == 200:
                        clob_data = clob_response.json()
                        
                        # Check for /sports/ URL in CLOB data
                        sports_url_fields = ['url', 'web_url', 'page_path', 'canonical_url', 'permalink', 'sportsUrl', 'webUrl', 'pagePath']
                        clob_sports_url = None
                        
                        # Check direct fields
                        for field in sports_url_fields:
                            field_value = clob_data.get(field)
                            if field_value and isinstance(field_value, str) and '/sports/' in field_value:
                                clob_sports_url = field_value
                                logger.info(f"[URL] [SPORTS] Found /sports/ URL in CLOB field '{field}': {clob_sports_url[:100]}...")
                                break
                        
                        # If not found in direct fields, scan all string values
                        if not clob_sports_url:
                            for key, value in clob_data.items():
                                if isinstance(value, str) and '/sports/' in value:
                                    clob_sports_url = value
                                    logger.info(f"[URL] [SPORTS] Found /sports/ URL in CLOB field '{key}': {clob_sports_url[:100]}...")
                                    break
                        
                        # Normalize and use sports URL if found
                        if clob_sports_url:
                            clob_sports_url_clean = str(clob_sports_url).strip().strip('/')
                            if clob_sports_url_clean.startswith('http'):
                                sports_url = clob_sports_url_clean
                            elif clob_sports_url_clean.startswith('/'):
                                sports_url = f"https://polymarket.com{clob_sports_url_clean}"
                            else:
                                sports_url = f"https://polymarket.com/{clob_sports_url_clean}"
                            
                            if sports_url:
                                market_url = sports_url
                                logger.info(f"[URL] [SPORTS] Found sports URL from CLOB API: {market_url}")
                                logger.info(f"[URL] [SPORTS] FINAL SPORTS URL: {market_url} (method: clob_api_sports_url, condition_id={condition_id[:20]}...)")
                                clob_sports_url_found = True
                except Exception as e:
                    logger.debug(f"[URL] [SPORTS] Failed to get sports URL from CLOB API: {e}")
            
            # Step 4: If all sports-specific attempts failed, fall back to generic /event/ URL construction
            if not sports_url:
                logger.debug(f"[URL] [SPORTS] All sports-specific URL attempts failed, falling back to generic /event/ URL construction...")
                # For sports markets, try to use event_slug/market_slug format if market_slug is available
                # This is needed for markets like Counter-Strike that need the full path
                if event_slug:
                    event_slug_clean = self._clean_slug(event_slug)
                    # Always use API-fetched slug, never use market_slug parameter from events
                    sports_market_slug = market_slug_from_api
                
                if not sports_market_slug:
                    sports_market_slug = self._get_market_slug(condition_id)
                
                if sports_market_slug:
                    sports_market_slug_clean = self._clean_slug(sports_market_slug)
                    logger.debug(f"[URL] [SPORTS] Using fallback: event_slug/market_slug format")
                    logger.debug(f"[URL] [SPORTS]   - event_slug_clean: {event_slug_clean}")
                    logger.debug(f"[URL] [SPORTS]   - sports_market_slug_clean: {sports_market_slug_clean}")
                    
                    # If market_slug equals event_slug, use only event_slug (don't duplicate)
                    if sports_market_slug_clean == event_slug_clean:
                        market_url = f"https://polymarket.com/event/{event_slug_clean}"
                        logger.info(f"[URL] [SPORTS] Market slug equals event slug, using only event_slug: {event_slug_clean} (condition_id={condition_id[:20]}...)")
                        logger.info(f"[URL] [SPORTS] FINAL SPORTS URL: {market_url} (method: event_slug_only, condition_id={condition_id[:20]}...)")
                    # Remove event_slug prefix from market_slug if it's already there
                    elif sports_market_slug_clean.startswith(event_slug_clean + '/'):
                        market_url = f"https://polymarket.com/event/{sports_market_slug_clean}"
                        logger.info(f"[URL] [SPORTS] Market slug already contains event slug, using as-is: {sports_market_slug_clean} (condition_id={condition_id[:20]}...)")
                        logger.info(f"[URL] [SPORTS] FINAL SPORTS URL: {market_url} (method: market_slug_as_is, condition_id={condition_id[:20]}...)")
                    elif sports_market_slug_clean.startswith(event_slug_clean + '-'):
                        # Market slug starts with event slug followed by dash, extract suffix
                        market_suffix = sports_market_slug_clean[len(event_slug_clean) + 1:]
                        market_url = f"https://polymarket.com/event/{event_slug_clean}/{market_suffix}"
                        logger.info(f"[URL] [SPORTS] Using event_slug/market_suffix format: event={event_slug_clean}, suffix={market_suffix} (condition_id={condition_id[:20]}...)")
                        logger.info(f"[URL] [SPORTS] FINAL SPORTS URL: {market_url} (method: event_slug_market_suffix, condition_id={condition_id[:20]}...)")
                    elif sports_market_slug_clean.startswith(event_slug_clean):
                        # Market slug starts with event slug (no separator), use full market_slug
                        market_url = f"https://polymarket.com/event/{event_slug_clean}/{sports_market_slug_clean}"
                        logger.info(f"[URL] [SPORTS] Using event_slug/market_slug format: event={event_slug_clean}, market_slug={sports_market_slug_clean} (condition_id={condition_id[:20]}...)")
                        logger.info(f"[URL] [SPORTS] FINAL SPORTS URL: {market_url} (method: event_slug_market_slug, condition_id={condition_id[:20]}...)")
                    else:
                        # Combine event_slug and market_slug
                        market_url = f"https://polymarket.com/event/{event_slug_clean}/{sports_market_slug_clean}"
                        logger.info(f"[URL] [SPORTS] Using event_slug/market_slug format: event={event_slug_clean}, market_slug={sports_market_slug_clean} (condition_id={condition_id[:20]}...)")
                        logger.info(f"[URL] [SPORTS] FINAL SPORTS URL: {market_url} (method: event_slug_market_slug_combined, condition_id={condition_id[:20]}...)")
                else:
                    # Fallback: use event slug for sports (without market_slug)
                    market_url = f"https://polymarket.com/event/{event_slug_clean}"
                    logger.info(f"[URL] [SPORTS] Fallback: event slug without market_slug: {event_slug_clean} (condition_id={condition_id[:20]}...)")
                    logger.info(f"[URL] [SPORTS] FINAL SPORTS URL: {market_url} (method: event_slug_fallback, condition_id={condition_id[:20]}...)")
            else:
                # No event_slug available - try to extract event_slug from market_slug patterns
                logger.debug(f"[URL] [SPORTS] No event_slug available, extracting from market_slug patterns...")
                # Always use API-fetched slug, never use market_slug parameter from events
                sports_market_slug_for_extraction = market_slug_from_api
                if not sports_market_slug_for_extraction:
                    sports_market_slug_for_extraction = self._get_market_slug(condition_id)
                if sports_market_slug_for_extraction:
                        market_slug_clean = self._clean_slug(sports_market_slug_for_extraction)
                        logger.debug(f"[URL] [SPORTS]   - Extracting event_slug from market_slug: {market_slug_clean}")
                        
                        # VALIDATION: Check if slug from events looks like market-specific slug
                        # If it does, don't try to build event_slug from it - check CLOB/Data API for separate event_slug
                        if self._is_market_specific_slug(market_slug_clean):
                            logger.warning(
                                f"[URL] [SPORTS] [VALIDATION] ⚠️ Slug from events looks market-specific: "
                                f"'{market_slug_clean[:50]}' (condition_id={condition_id[:20]}...). "
                                f"Checking CLOB/Data API for separate event_slug instead of extracting from market_slug."
                            )
                        # Try to extract event_slug from market_slug (for sports markets like "nfl-was-mia-2025-11-16-spread-home-2pt5")
                        # Event slug is usually the base part before market-specific suffix (e.g., "spread-home-2pt5")
                        fallback_event_slug = None
                        
                        # Try to get event_slug/market_slug from CLOB API (sports URL already checked in Step 3)
                        try:
                            clob_url = f"https://clob.polymarket.com/markets/{condition_id}"
                            clob_response = self._make_authenticated_get(clob_url, timeout=5)
                            if clob_response and clob_response.status_code == 200:
                                clob_data = clob_response.json()
                                
                                clob_event_slug = clob_data.get('event_slug') or clob_data.get('eventSlug')
                                clob_market_slug = clob_data.get('market_slug') or clob_data.get('marketSlug') or clob_data.get('question_slug')
                                
                                if clob_event_slug:
                                    # Use centralized cleaning function
                                    clob_event_slug = self._clean_slug(clob_event_slug)
                                    if clob_event_slug and clob_event_slug != market_slug_clean:
                                        fallback_event_slug = clob_event_slug
                                        logger.info(f"[URL] [SPORTS] Got event_slug from CLOB API: {fallback_event_slug} (condition_id={condition_id[:20]}...)")
                                        logger.info(f"[URL] [SPORTS] Using CLOB API slugs for URL construction: event_slug={fallback_event_slug}, market_slug={clob_market_slug}")
                                
                                if clob_market_slug and not sports_market_slug_for_extraction:
                                    # Use centralized cleaning function
                                    sports_market_slug_for_extraction = self._clean_slug(clob_market_slug, strip_market_prefix=True)
                                    market_slug_clean = sports_market_slug_for_extraction
                                    logger.info(f"[URL] [SPORTS] Got market_slug from CLOB API: {sports_market_slug_for_extraction}")
                        except Exception as e:
                            logger.debug(f"[URL] [SPORTS] Failed to get event_slug from CLOB API: {e}")
                        
                        # Extract event_slug from market_slug pattern if not found from CLOB
                        # If no event_slug from API, try to extract from market_slug
                        # For sports markets like "nfl-was-mia-2025-11-16-spread-home-2pt5", 
                        # try to find the base event slug (e.g., "nfl-was-mia-2025-11-16")
                        if not fallback_event_slug:
                            logger.debug(f"[URL] [SPORTS]   - Extracting event_slug from market_slug pattern...")
                            # Try common patterns: remove market-specific suffixes
                            market_parts = market_slug_clean.split('-')
                            # Look for date pattern (YYYY-MM-DD) and keep everything before market type
                            market_types = ['spread', 'total', 'moneyline', 'over', 'under', 'home', 'away']
                            for i, part in enumerate(market_parts):
                                if part in market_types:
                                    # Found market type, event_slug is everything before it
                                    fallback_event_slug = '-'.join(market_parts[:i])
                                    logger.debug(f"[URL] [SPORTS]   - Extracted event_slug from market type pattern: {fallback_event_slug}")
                                    break
                            # If no market type found, try to extract base slug (everything before last few parts)
                            if not fallback_event_slug and len(market_parts) > 3:
                                # Assume last 2-3 parts are market-specific
                                fallback_event_slug = '-'.join(market_parts[:-2])
                                logger.debug(f"[URL] [SPORTS]   - Extracted event_slug from suffix pattern: {fallback_event_slug}")
                        
                        if fallback_event_slug and fallback_event_slug != market_slug_clean:
                            fallback_event_slug_clean = self._clean_slug(fallback_event_slug)
                            # Extract market suffix if market_slug starts with event_slug
                            if market_slug_clean.startswith(fallback_event_slug_clean + '-'):
                                market_suffix = market_slug_clean[len(fallback_event_slug_clean) + 1:]
                                market_url = f"https://polymarket.com/event/{fallback_event_slug_clean}/{market_suffix}"
                                logger.info(f"[URL] [SPORTS] Using extracted event_slug/market_suffix: {fallback_event_slug_clean}/{market_suffix} (condition_id={condition_id[:20]}...)")
                                logger.info(f"[URL] [SPORTS] FINAL SPORTS URL: {market_url} (method: extracted_event_slug_market_suffix, condition_id={condition_id[:20]}...)")
                            else:
                                market_url = f"https://polymarket.com/event/{fallback_event_slug_clean}/{market_slug_clean}"
                                logger.info(f"[URL] [SPORTS] Using event_slug/market_slug format: {fallback_event_slug_clean}/{market_slug_clean} (condition_id={condition_id[:20]}...)")
                                logger.info(f"[URL] [SPORTS] FINAL SPORTS URL: {market_url} (method: extracted_event_slug_market_slug, condition_id={condition_id[:20]}...)")
                        else:
                            # No event_slug found - use market_slug/market_slug format
                            market_url = f"https://polymarket.com/event/{market_slug_clean}/{market_slug_clean}"
                            logger.info(f"[URL] [SPORTS] No event_slug found, using market_slug/market_slug format: {market_slug_clean}/{market_slug_clean} (condition_id={condition_id[:20]}...)")
                            logger.info(f"[URL] [SPORTS] FINAL SPORTS URL: {market_url} (method: market_slug_market_slug_fallback, condition_id={condition_id[:20]}...)")
                else:
                    logger.debug(f"[URL] [SPORTS]   - Using search URL fallback")
                    market_url = self._get_search_url_fallback(condition_id)
                    logger.info(f"[URL] [SPORTS] Fallback: search URL (condition_id={condition_id[:20]}...)")
                    logger.info(f"[URL] [SPORTS] FINAL SPORTS URL: {market_url} (method: search_url_fallback, condition_id={condition_id[:20]}...)")
        
        # Priority 2: Complex markets (non-sports) - ALWAYS prefer event_slug?tid={market_id} format if market_id available
        # This is the most reliable format for complex markets with multiple sub-markets (e.g., Bitcoin price markets)
        if not is_sports_market and event_slug and market_id:
            slug_clean = self._clean_slug(event_slug)
            market_url = f"https://polymarket.com/event/{slug_clean}?tid={market_id}"
            logger.info(f"[URL] ✅ Using event_slug?tid format for complex market: event={slug_clean}, tid={market_id} (condition_id={condition_id[:20]}...)")
        
        # Priority 3: Complex markets (non-sports) - use event_slug/market_slug format if no market_id
        elif not is_sports_market and event_slug and market_slug_from_api:
            event_slug_clean = self._clean_slug(event_slug)
            market_slug_clean = self._clean_slug(market_slug_from_api)
            
            # VALIDATION: Check for confusion between event_slug and market_slug
            # If both slugs look market-specific, don't build URL as event_slug/market_slug
            event_slug_is_market_specific = self._is_market_specific_slug(event_slug_clean)
            market_slug_is_market_specific = self._is_market_specific_slug(market_slug_clean)
            
            if event_slug_is_market_specific and market_slug_is_market_specific:
                # Both slugs are market-specific - this indicates confusion
                # Prefer event_slug?tid={market_id} format if market_id is available, otherwise fallback to search
                logger.warning(
                    f"[URL] [VALIDATION] ⚠️ Both event_slug and market_slug appear market-specific: "
                    f"event_slug='{event_slug_clean[:50]}', market_slug='{market_slug_clean[:50]}' "
                    f"(condition_id={condition_id[:20]}...). "
                    f"Using fallback format to avoid incorrect URL."
                )
                if market_id:
                    slug_clean = self._clean_slug(event_slug)
                    market_url = f"https://polymarket.com/event/{slug_clean}?tid={market_id}"
                    logger.info(f"[URL] [VALIDATION] Using event_slug?tid fallback: event={slug_clean}, tid={market_id} (condition_id={condition_id[:20]}...)")
                else:
                    market_url = self._get_search_url_fallback(condition_id)
                    logger.info(f"[URL] [VALIDATION] Using search URL fallback (no market_id available) (condition_id={condition_id[:20]}...)")
            else:
                # Normal case: proceed with event_slug/market_slug construction
                # Remove event_slug prefix from market_slug if it's already there
                if market_slug_clean.startswith(event_slug_clean + '/'):
                    # Market slug already contains event slug with separator, use as-is
                    market_url = f"https://polymarket.com/event/{market_slug_clean}"
                    logger.info(f"[URL] Market slug already contains event slug, using as-is: {market_slug_clean} (condition_id={condition_id[:20]}...)")
                elif market_slug_clean.startswith(event_slug_clean + '-'):
                    # Market slug starts with event slug followed by dash, extract suffix
                    market_suffix = market_slug_clean[len(event_slug_clean) + 1:]
                    market_url = f"https://polymarket.com/event/{event_slug_clean}/{market_suffix}"
                    logger.info(f"[URL] Using event_slug/market_suffix format: event={event_slug_clean}, suffix={market_suffix} (condition_id={condition_id[:20]}...)")
                elif market_slug_clean == event_slug_clean:
                    # If market_slug equals event_slug, still use event_slug/market_slug format (required by Polymarket)
                    market_url = f"https://polymarket.com/event/{event_slug_clean}/{market_slug_clean}"
                    logger.info(f"[URL] Market slug equals event slug, using event_slug/market_slug format: {event_slug_clean}/{market_slug_clean} (condition_id={condition_id[:20]}...)")
                elif market_slug_clean.startswith(event_slug_clean):
                    # Market slug starts with event slug (no separator), use full market_slug
                    market_url = f"https://polymarket.com/event/{event_slug_clean}/{market_slug_clean}"
                    logger.info(f"[URL] Using event_slug/market_slug for complex market: event={event_slug_clean}, market_slug={market_slug_clean} (condition_id={condition_id[:20]}...)")
                else:
                    # Combine event_slug and market_slug
                    market_url = f"https://polymarket.com/event/{event_slug_clean}/{market_slug_clean}"
                    logger.info(f"[URL] Using event_slug/market_slug for complex market: event={event_slug_clean}, market_slug={market_slug_clean} (condition_id={condition_id[:20]}...)")
        
        # Priority 4: Event slug without market_slug/tid (fallback for complex markets)
        # WARNING: This should only be used if market_id and market_slug_from_api are both unavailable
        # Try to get market_slug using _get_market_slug() before falling back to just event_slug
        elif not is_sports_market and event_slug:
            event_slug_clean = self._clean_slug(event_slug)
            # Try to get market_slug as fallback (always use API, never use market_slug parameter from events)
            fallback_market_slug = market_slug_from_api
            if not fallback_market_slug:
                fallback_market_slug = self._get_market_slug(condition_id)
            
            # If still no market_slug, try CLOB API directly as last resort
            if not fallback_market_slug:
                try:
                    clob_url = f"https://clob.polymarket.com/markets/{condition_id}"
                    clob_response = self._make_authenticated_get(clob_url, timeout=5)
                    if clob_response and clob_response.status_code == 200:
                        clob_data = clob_response.json()
                        # Try to get market_slug from CLOB API
                        clob_market_slug = (clob_data.get('question_slug') or 
                                          clob_data.get('market_slug') or 
                                          clob_data.get('slug') or
                                          clob_data.get('event_slug'))
                        if clob_market_slug:
                            # Use centralized cleaning function
                            clob_market_slug = self._clean_slug(clob_market_slug, strip_market_prefix=True)
                            if clob_market_slug:
                                # Always use market_slug even if it equals event_slug (we'll use event_slug/market_slug format)
                                fallback_market_slug = clob_market_slug
                                logger.info(f"[URL] Got market_slug from CLOB API fallback: {fallback_market_slug} (condition_id={condition_id[:20]}...)")
                except Exception as e:
                    logger.debug(f"[URL] Failed to get market_slug from CLOB API fallback: {e}")
            
            if fallback_market_slug:
                fallback_market_slug_clean = self._clean_slug(fallback_market_slug)
                # Remove event_slug prefix from market_slug if it's already there
                if fallback_market_slug_clean.startswith(event_slug_clean + '/'):
                    market_url = f"https://polymarket.com/event/{fallback_market_slug_clean}"
                    logger.warning(f"[URL] ⚠️  Fallback: market_slug already contains event_slug, using as-is: {fallback_market_slug_clean} (condition_id={condition_id[:20]}...)")
                elif fallback_market_slug_clean.startswith(event_slug_clean + '-'):
                    # Market slug starts with event slug followed by dash (e.g., "event-slug-220-239")
                    # Extract the market-specific suffix
                    market_suffix = fallback_market_slug_clean[len(event_slug_clean) + 1:]  # +1 to skip the dash
                    market_url = f"https://polymarket.com/event/{event_slug_clean}/{market_suffix}"
                    logger.warning(f"[URL] ⚠️  Fallback: Extracted market suffix from market_slug: event={event_slug_clean}, suffix={market_suffix} (condition_id={condition_id[:20]}...)")
                elif fallback_market_slug_clean == event_slug_clean:
                    # If market_slug equals event_slug, still use event_slug/market_slug format (required by Polymarket)
                    market_url = f"https://polymarket.com/event/{event_slug_clean}/{fallback_market_slug_clean}"
                    logger.warning(f"[URL] ⚠️  Fallback: market_slug equals event_slug, using event_slug/market_slug format: {event_slug_clean}/{fallback_market_slug_clean} (condition_id={condition_id[:20]}...)")
                elif fallback_market_slug_clean.startswith(event_slug_clean):
                    # Market slug starts with event slug (no separator), use full market_slug
                    market_url = f"https://polymarket.com/event/{event_slug_clean}/{fallback_market_slug_clean}"
                    logger.warning(f"[URL] ⚠️  Fallback: Using event_slug/market_slug format: event={event_slug_clean}, market_slug={fallback_market_slug_clean} (condition_id={condition_id[:20]}...)")
                else:
                    # Combine event_slug and market_slug
                    market_url = f"https://polymarket.com/event/{event_slug_clean}/{fallback_market_slug_clean}"
                    logger.warning(f"[URL] ⚠️  Fallback: Using event_slug/market_slug format: event={event_slug_clean}, market_slug={fallback_market_slug_clean} (condition_id={condition_id[:20]}...)")
            else:
                # No market_slug available - use event_slug/market_slug format with event_slug as both parts (last resort)
                # This ensures we always use the required format even if market_slug is unavailable
                market_url = f"https://polymarket.com/event/{event_slug_clean}/{event_slug_clean}"
                logger.warning(f"[URL] ⚠️  Fallback: No market_slug found, using event_slug/market_slug format with duplicate: {event_slug_clean}/{event_slug_clean} (condition_id={condition_id[:20]}...)")
        
        # Priority 5: Market slug fallback
        else:
            if not market_slug:
                market_slug = self._get_market_slug(condition_id)
            
            if market_slug:
                market_slug_clean = self._clean_slug(market_slug)
                # Try to get event_slug from CLOB API if not available
                fallback_event_slug = event_slug
                if not fallback_event_slug:
                    try:
                        clob_url = f"https://clob.polymarket.com/markets/{condition_id}"
                        clob_response = self._make_authenticated_get(clob_url, timeout=5)
                        if clob_response and clob_response.status_code == 200:
                            clob_data = clob_response.json()
                            # Try to extract event_slug from question or description
                            question = clob_data.get('question') or clob_data.get('description') or ""
                            # Also try to get event_slug from market_slug by removing market-specific parts
                            clob_event_slug = clob_data.get('event_slug')
                            if clob_event_slug:
                                # Use centralized cleaning function
                                clob_event_slug = self._clean_slug(clob_event_slug)
                                if clob_event_slug and clob_event_slug != market_slug_clean:
                                    fallback_event_slug = clob_event_slug
                                    logger.info(f"[URL] Got event_slug from CLOB API (Priority 5): {fallback_event_slug} (condition_id={condition_id[:20]}...)")
                    except Exception as e:
                        logger.debug(f"[URL] Failed to get event_slug from CLOB API (Priority 5): {e}")
                
                # If still no event_slug and this is a sports market, try to extract from market_slug
                if not fallback_event_slug and is_sports_market:
                    # For sports markets, try to extract event_slug by removing market-specific suffixes
                    market_parts = market_slug_clean.split('-')
                    # Check if market_slug contains a date pattern (YYYY-MM-DD)
                    has_date_pattern = False
                    date_start_idx = None
                    for i, part in enumerate(market_parts):
                        # Check if this part looks like a year (4 digits starting with 20xx)
                        if len(part) == 4 and part.isdigit() and part.startswith('20'):
                            # Check if next parts form MM-DD pattern
                            if i + 2 < len(market_parts):
                                month_part = market_parts[i + 1]
                                day_part = market_parts[i + 2]
                                if month_part.isdigit() and day_part.isdigit() and len(month_part) <= 2 and len(day_part) <= 2:
                                    has_date_pattern = True
                                    date_start_idx = i
                                    break
                    
                    # Look for market-specific suffixes (spread, total, etc.)
                    market_types = ['spread', 'total', 'moneyline', 'over', 'under', 'home', 'away']
                    for i, part in enumerate(market_parts):
                        if part in market_types:
                            # Found market type, event_slug is everything before it
                            fallback_event_slug = '-'.join(market_parts[:i])
                            logger.info(f"[URL] Extracted event_slug from market_slug (Priority 5, sports, found market type): {fallback_event_slug} from {market_slug_clean} (condition_id={condition_id[:20]}...)")
                            break
                    
                    # If no market type found and we have a date pattern, don't split the date
                    # For simple markets like "nba-por-dal-2025-11-16", use the full slug as-is
                    if not fallback_event_slug and has_date_pattern:
                        # This is a simple market with date, don't extract event_slug - use full market_slug
                        fallback_event_slug = None  # Don't extract, will use full market_slug later
                        logger.info(f"[URL] Simple sports market with date pattern detected: {market_slug_clean}, will use full slug (condition_id={condition_id[:20]}...)")
                    elif not fallback_event_slug and len(market_parts) > 4:
                        # Only try to remove country/team codes if we don't have a date pattern
                        # Check if last part looks like a country/team code (2-4 chars, lowercase, not a number)
                        last_part = market_parts[-1]
                        if len(last_part) <= 4 and last_part.isalpha() and last_part.islower() and not last_part.isdigit():
                            # Likely a country/team code, but only remove if it's not part of a date
                            # Check if previous part is not a year
                            prev_part = market_parts[-2] if len(market_parts) > 1 else None
                            if not (prev_part and len(prev_part) == 4 and prev_part.isdigit() and prev_part.startswith('20')):
                                # Not part of date, safe to remove
                                fallback_event_slug = '-'.join(market_parts[:-1])
                                logger.info(f"[URL] Extracted event_slug from market_slug (Priority 5, sports, removed country code): {fallback_event_slug} from {market_slug_clean} (condition_id={condition_id[:20]}...)")
                
                # Use event_slug/market_slug format if event_slug is available
                if fallback_event_slug:
                    fallback_event_slug_clean = fallback_event_slug.strip().strip('/')
                    # Remove event_slug prefix from market_slug if it's already there
                    if market_slug_clean.startswith(fallback_event_slug_clean + '/'):
                        market_url = f"https://polymarket.com/event/{market_slug_clean}"
                        logger.info(f"[URL] Priority 5: market_slug already contains event_slug, using as-is: {market_slug_clean} (condition_id={condition_id[:20]}...)")
                    elif market_slug_clean.startswith(fallback_event_slug_clean + '-'):
                        # Market slug starts with event slug followed by dash, extract suffix
                        market_suffix = market_slug_clean[len(fallback_event_slug_clean) + 1:]
                        market_url = f"https://polymarket.com/event/{fallback_event_slug_clean}/{market_suffix}"
                        logger.info(f"[URL] Priority 5: Using event_slug/market_suffix format: event={fallback_event_slug_clean}, suffix={market_suffix} (condition_id={condition_id[:20]}...)")
                    elif market_slug_clean == fallback_event_slug_clean:
                        # If market_slug equals event_slug, still use event_slug/market_slug format
                        market_url = f"https://polymarket.com/event/{fallback_event_slug_clean}/{market_slug_clean}"
                        logger.info(f"[URL] Priority 5: market_slug equals event_slug, using event_slug/market_slug format: {fallback_event_slug_clean}/{market_slug_clean} (condition_id={condition_id[:20]}...)")
                    elif market_slug_clean.startswith(fallback_event_slug_clean):
                        # Market slug starts with event slug (no separator), use full market_slug
                        market_url = f"https://polymarket.com/event/{fallback_event_slug_clean}/{market_slug_clean}"
                        logger.info(f"[URL] Priority 5: Using event_slug/market_slug format: event={fallback_event_slug_clean}, market_slug={market_slug_clean} (condition_id={condition_id[:20]}...)")
                    else:
                        # Combine event_slug and market_slug
                        market_url = f"https://polymarket.com/event/{fallback_event_slug_clean}/{market_slug_clean}"
                        logger.info(f"[URL] Priority 5: Using event_slug/market_slug format: event={fallback_event_slug_clean}, market_slug={market_slug_clean} (condition_id={condition_id[:20]}...)")
                else:
                    # No event_slug available - for simple markets with date pattern, use full slug without splitting
                    # For markets like "nba-por-dal-2025-11-16", use the full slug as-is
                    market_url = f"https://polymarket.com/event/{market_slug_clean}"
                    logger.info(f"[URL] Priority 5: No event_slug found, using full market_slug: {market_slug_clean} (condition_id={condition_id[:20]}...)")
            else:
                # Priority 6: Search URL fallback
                market_url = self._get_search_url_fallback(condition_id)
                logger.info(f"[URL] Fallback: search URL (condition_id={condition_id[:20]}...)")
        
        # Final logging
        logger.info(f"[URL] Final market URL for condition={condition_id[:20]}...: {market_url}")
        
        # Current timestamp - use dt_module to avoid conflicts
        timestamp_utc = dt_module.datetime.now(dt_module.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        
        # side is passed as parameter now
        position_side = side
        
        # Get outcome name from API if needed
        outcome_name = self._get_outcome_name(condition_id, outcome_index)
        
        # Use provided title or try to get from API
        if not market_title:
            market_title = self._get_market_title(condition_id)
        
        # If we don't have slug, try to get it from API
        if not market_slug:
            market_slug = self._get_market_slug(condition_id)
        
        # Get wallet info with winrates and prices from database
        wallet_info = []
        for i, wallet in enumerate(wallets[:4], 1):
            try:
                import sqlite3
                conn = sqlite3.connect('polymarket_notifier.db')
                cursor = conn.cursor()
                cursor.execute('SELECT win_rate, traded_total FROM wallets WHERE address = ?', (wallet,))
                result = cursor.fetchone()
                conn.close()
                
                # Mask address: keep first 3 hex after '0x' and last 3 chars
                try:
                    prefix = wallet[:5]  # '0x' + 3 hex
                    suffix = wallet[-3:]
                    short_addr = f"{prefix}.......{suffix}"
                except Exception:
                    short_addr = wallet
                
                # Format price
                price = wallet_prices.get(wallet, 0) if wallet in wallet_prices else 0
                price_str = f" @ ${price:.3f}"
                
                # Build trader info (Markdown)
                if result:
                    wr, trades = result
                    if wr and trades:
                        trader_info = f"{i}. `{short_addr}` • WR: {wr:.1%} ({int(trades)} trades){price_str}"
                    else:
                        trader_info = f"{i}. `{short_addr}`{price_str}"
                else:
                    trader_info = f"{i}. `{short_addr}`{price_str}"
                
                wallet_info.append(trader_info)
            except Exception as e:
                try:
                    prefix = wallet[:5]
                    suffix = wallet[-3:]
                    short_addr = f"{prefix}.......{suffix}"
                except Exception:
                    short_addr = wallet
                price = wallet_prices.get(wallet, 0) if wallet in wallet_prices else 0
                price_str = f" @ ${price:.3f}"
                wallet_info.append(f"{i}. `{short_addr}`{price_str}")
        
        # Fetch current price with multi-level fallback (if not provided)
        if current_price is None:
            logger.info(f"[NOTIFY] 🔍 Fetching current price for condition_id={condition_id[:20]}... outcome={outcome_index}, wallet_prices provided: {len(wallet_prices) if wallet_prices else 0} wallets")
            # Use API-fetched slug (event_slug or market_slug_from_api) for price fetcher, not market_slug parameter from events
            # event_slug is preferred as it's more reliable for Gamma API /events endpoint
            slug_for_price = event_slug if event_slug else (market_slug_from_api if market_slug_from_api else None)
            current_price = self._get_current_price(
                condition_id, 
                outcome_index, 
                wallet_prices=wallet_prices,
                hashdive_client=self.hashdive_client,
                slug=slug_for_price
            )
            if current_price is None:
                logger.warning(f"[NOTIFY] ⚠️  Price unavailable after all fallbacks for condition_id={condition_id[:20]}... outcome={outcome_index}, wallet_prices: {wallet_prices}")
            else:
                logger.info(f"[NOTIFY] ✅ Got current price: {current_price:.6f} for condition_id={condition_id[:20]}... outcome={outcome_index}")
        
        # CRITICAL FINAL CHECK: Don't send alerts for resolved markets (price = 1.0 or 0.0)
        # But if price is None, check market status - if active, send alert with Price: N/A
        if current_price is not None:
            price_val = float(current_price)
            logger.info(f"[NOTIFY] Step 10/10: Final price check - condition={condition_id[:20]}... outcome={outcome_index}, price={price_val:.6f}")
            # Block resolved markets (price >= 0.999 or <= 0.001)
            if price_val >= 0.999 or price_val <= 0.001:
                logger.info(f"[NOTIFY] ⏭️  BLOCKED: Market resolved (price={price_val:.6f} >= 0.999 or <= 0.001) condition={condition_id[:20]}... outcome={outcome_index} wallets={len(wallets)}")
                # Only send suppressed alert if we have consensus (multiple wallets)
                if len(wallets) >= min_consensus:
                    try:
                        self.send_suppressed_alert_details(
                            reason="resolved",
                            condition_id=condition_id,
                            outcome_index=outcome_index,
                            wallets=wallets,
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
                    logger.debug(f"[NOTIFY] Skipping suppressed alert for resolved market: only {len(wallets)} wallet(s), below consensus threshold ({min_consensus})")
                return False
            # Block closed markets (price >= 0.98 or <= 0.02)
            if price_val >= 0.98 or price_val <= 0.02:
                logger.info(f"[NOTIFY] ⏭️  BLOCKED: Market closed (price={price_val:.6f} >= 0.98 or <= 0.02) condition={condition_id[:20]}... outcome={outcome_index} wallets={len(wallets)}")
                # Only send suppressed alert if we have consensus (multiple wallets)
                if len(wallets) >= min_consensus:
                    try:
                        self.send_suppressed_alert_details(
                            reason="price_high",
                            condition_id=condition_id,
                            outcome_index=outcome_index,
                            wallets=wallets,
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
                    logger.debug(f"[NOTIFY] Skipping suppressed alert for closed market: only {len(wallets)} wallet(s), below consensus threshold ({min_consensus})")
                return False
            
            # For display: Use average entry price from traders if available, otherwise use current market price
            # This shows the price at which traders entered, not the current market price
            display_price = current_price
            if wallet_prices and len(wallet_prices) > 0:
                # Calculate average entry price from traders
                valid_prices = [p for p in wallet_prices.values() if p is not None and p > 0]
                if valid_prices:
                    avg_entry_price = sum(valid_prices) / len(valid_prices)
                    display_price = avg_entry_price
                    logger.info(f"[NOTIFY] Using average entry price from traders: {display_price:.6f} (from {len(valid_prices)} traders) instead of current market price: {current_price:.6f}")
            
            # Avoid rounding up to 1.000 when price is extremely close to 1
            if display_price >= 0.9995:
                display_price = 0.999
            # Clamp negative/invalid values
            if display_price < 0:
                display_price = 0.0
            current_price_str = f"$\u2009{display_price:.3f}"
        else:
            # Price is None - check if market is closed
            # If market is active, send alert with Price: N/A (fail-open approach)
            market_closed = False
            try:
                # Try to check market status via API
                url = f"https://clob.polymarket.com/markets/{condition_id}"
                response = self._make_authenticated_get(url, timeout=10)
                
                # Handle 404 first - market not found means it's closed/removed
                if response.status_code == 404:
                    market_closed = True
                    logger.warning(f"[Price] Market {condition_id[:20]}... not found (404) - market closed/removed")
                elif response.status_code == 200:
                    data = response.json()
                    # Check if market is closed (multiple indicators)
                    if data.get("closed") is True:
                        market_closed = True
                        logger.debug(f"Market {condition_id[:20]}... marked as closed (closed flag)")
                    
                    # Check end_date
                    if data.get("end_date_iso"):
                        # Use dt_module to avoid conflicts
                        try:
                            end_date_str = data["end_date_iso"].replace("Z", "+00:00")
                            end_date = dt_module.datetime.fromisoformat(end_date_str)
                            if end_date.tzinfo is None:
                                end_date = end_date.replace(tzinfo=dt_module.timezone.utc)
                            current_time = dt_module.datetime.now(dt_module.timezone.utc)
                            if current_time > end_date:
                                market_closed = True
                                logger.debug(f"Market {condition_id[:20]}... closed (end_date passed: {end_date.isoformat()})")
                        except Exception as e:
                            logger.debug(f"Failed to parse end_date: {e}")
                    
                    # Check status field
                    status = str(data.get("status") or "").lower()
                    if status in {"resolved", "finished", "closed", "ended", "finalized"}:
                        market_closed = True
                        logger.debug(f"Market {condition_id[:20]}... closed (status: {status})")
                    
                    # Check active flag
                    if data.get("active") is False:
                        market_closed = True
                        logger.debug(f"Market {condition_id[:20]}... closed (active=False)")
                    
                    # Also check if tokens exist and have extreme prices (resolved market)
                    tokens = data.get("tokens", [])
                    if tokens and outcome_index < len(tokens):
                        token = tokens[outcome_index]
                        for price_key in ("last_price", "price", "mark_price"):
                            price_val = token.get(price_key)
                            if isinstance(price_val, (int, float)):
                                price_float = float(price_val)
                                # Extreme prices indicate resolved/closed market
                                if price_float >= 0.999 or price_float <= 0.001:
                                    market_closed = True
                                    logger.debug(f"Market {condition_id[:20]}... closed (extreme price: {price_float})")
                                    break
                else:
                    # Other HTTP errors - log but don't assume closed
                    logger.debug(f"[Price] Market status check returned status {response.status_code} for condition_id={condition_id[:20]}...")
            except Exception as e:
                logger.debug(f"Failed to check market status: {type(e).__name__}: {e}")
                # If we can't check market status, assume it's active (fail-open)
                # This allows alerts to be sent even if price lookup failed
                market_closed = False
                logger.warning(f"[Price] Market status check failed for condition_id={condition_id}, assuming active (fail-open)")
            
            if market_closed:
                # Market is confirmed closed - send suppressed alert
                if len(wallets) >= min_consensus:
                    logger.info(f"[NOTIFY] ⏭️  BLOCKED: Market closed (price unavailable) condition={condition_id[:20]}... outcome={outcome_index} wallets={len(wallets)}")
                    try:
                        self.send_suppressed_alert_details(
                            reason="market_closed",
                            condition_id=condition_id,
                            outcome_index=outcome_index,
                            wallets=wallets,
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
                    logger.debug(f"[NOTIFY] Skipping suppressed alert for closed market: only {len(wallets)} wallet(s), below consensus threshold ({min_consensus})")
                return False
            else:
                # Price is None but market appears active - send alert with Price: N/A (fail-open)
                logger.warning(f"[Price] Price lookup failed for condition_id={condition_id}, outcome={outcome_index}, sending alert with Price: N/A")
                current_price_str = "N/A"
                # Continue to send alert (don't block)

        # Build message in Markdown style per new template
        position_display = outcome_name if outcome_name else f"Index {outcome_index}"
        
        # Format header with A-list info if available
        a_list_count = len(a_list_wallets) if a_list_wallets else 0
        # Add order flow emoji to header if confirmed
        order_flow_emoji = "📊 " if order_flow_confirmed else ""
        if a_list_count >= 2:
            header = f"*{order_flow_emoji}🔮 Alpha Signal Detected ({len(wallets)} wallets, {a_list_count}× A List in {category or 'category'})*"
        else:
            header = f"*{order_flow_emoji}🔮 Alpha Signal Detected ({len(wallets)} wallets)*"
        # Always show total position if we have USD data, even if 0 (for debugging)
        if isinstance(total_usd, (int, float)):
            if total_usd > 0:
                total_line = f"\nTotal position: {total_usd:,.0f} USDC💰"
            else:
                total_line = f"\nTotal position: {total_usd:,.0f} USDC💰"  # Show even if 0 for now
        else:
            total_line = ""

        # Calculate and format market end time if available
        end_time_info = ""
        if end_date:
            try:
                # Use dt_module to avoid conflicts
                current_time = dt_module.datetime.now(dt_module.timezone.utc)
                if end_date.tzinfo is None:
                    end_date = end_date.replace(tzinfo=dt_module.timezone.utc)
                
                # Calculate time remaining
                time_diff = end_date - current_time
                if time_diff.total_seconds() > 0:
                    total_seconds = int(time_diff.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    
                    # Format: "Ends in: 3h 24m" (only this line, bold)
                    ends_in_str = f"*🕐 Ends in: {hours}h {minutes}m*"
                    
                    end_time_info = f"\n{ends_in_str}"
                else:
                    # Market has already ended - just show the end date
                    end_date_str = end_date.strftime("%Y-%m-%d %H:%M:%S")
                    end_time_info = f"\n*📅 Ended: {end_date_str} UTC*"
            except Exception as e:
                logger.debug(f"Error formatting end time: {e}")

        # Format price display - show N/A if unavailable
        price_display = f"Price: *{current_price_str}*" if current_price_str != "N/A" else "Price: *N/A* (unavailable)"

        # Format category info
        category_line = ""
        if category:
            category_line = f"\n📊 *Category:* {category}"
        
        # Format A-list wallets info
        a_list_info = ""
        if a_list_wallets and len(a_list_wallets) > 0:
            a_list_wallet_lines = []
            for wallet in a_list_wallets[:5]:  # Limit to 5 A-list wallets
                try:
                    prefix = wallet[:5]
                    suffix = wallet[-3:]
                    short_addr = f"{prefix}.......{suffix}"
                except Exception:
                    short_addr = wallet
                a_list_wallet_lines.append(f"  • `{short_addr}` [A List: {category or 'category'}]")
            if len(a_list_wallets) > 5:
                a_list_wallet_lines.append(f"  ... и еще {len(a_list_wallets) - 5} A List трейдеров")
            a_list_info = f"\n⭐ *A List Traders:*\n{chr(10).join(a_list_wallet_lines)}"
        
        # Format OI confirmation info
        oi_confirmation_line = ""
        # Add order flow confirmation indicator
        order_flow_line = ""
        if order_flow_confirmed:
            order_flow_line = "\n✅ *Order Flow Confirmed*\nOrder flow analysis confirms strong {side} pressure".format(side=side.lower())
        
        if oi_confirmed:
            oi_confirmation_line = "\n✅ *OI Confirmed:* Open interest spiked, indicating strong conviction"
        
        # Format news context section if available
        news_section = ""
        if news_context:
            headline = news_context.get('headline', '')
            source = news_context.get('source', 'Unknown')
            published_at = news_context.get('published_at', '')
            
            # Truncate headline to 100 characters
            if len(headline) > 100:
                headline = headline[:100] + "..."
            
            # Format relative time
            relative_time = ""
            if published_at:
                try:
                    # Parse published_at timestamp
                    if isinstance(published_at, str):
                        try:
                            pub_dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                            if pub_dt.tzinfo is None:
                                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                        except ValueError:
                            # Try Unix timestamp
                            pub_dt = datetime.fromtimestamp(float(published_at), tz=timezone.utc)
                    else:
                        pub_dt = datetime.fromtimestamp(float(published_at), tz=timezone.utc)
                    
                    # Calculate relative time
                    now = datetime.now(timezone.utc)
                    diff = now - pub_dt
                    minutes = int(diff.total_seconds() / 60)
                    hours = int(minutes / 60)
                    
                    if minutes < 1:
                        relative_time = "just now"
                    elif minutes < 60:
                        relative_time = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
                    elif hours < 24:
                        relative_time = f"{hours} hour{'s' if hours != 1 else ''} ago"
                    else:
                        days = int(hours / 24)
                        relative_time = f"{days} day{'s' if days != 1 else ''} ago"
                except Exception as e:
                    logger.debug(f"[NOTIFY] Could not parse news timestamp: {e}")
                    relative_time = ""
            
            news_section = f"\n\n📰 *Breaking News Context:*\n\"{headline}\"\nSource: {source}" + (f" • {relative_time}" if relative_time else "")
            logger.info(f"[NOTIFY] Including news context in alert: {headline[:50]}...")
        else:
            logger.debug(f"[NOTIFY] No news context available for this alert")
        
        message = f"""{header}

🎯 *Market:* {market_title}{category_line}
{total_line}{news_section}

*Outcome:* {position_display}
👤 Traders involved:

{chr(10).join(wallet_info)}{a_list_info}{oi_confirmation_line}{order_flow_line}

{price_display}{end_time_info}

📅 {timestamp_utc} UTC"""
        
        # Inline keyboard with View Market button and optional Read News button
        keyboard_buttons = [{"text": "View Market", "url": market_url}]
        
        # Add Read News button if news context has a valid URL
        if news_context and news_context.get('url'):
            news_url = news_context['url']
            if isinstance(news_url, str) and (news_url.startswith('http://') or news_url.startswith('https://')):
                keyboard_buttons.append({"text": "📰 Read News", "url": news_url})
        
        reply_markup = {
            "inline_keyboard": [keyboard_buttons]
        }
        
        # Route ALL consensus alerts to reports channel (as requested)
        target_chat = self.reports_chat_id
        
        # Determine topic ID based on A-list status first, then size
        # Priority 1: A-list alerts (2+ A-list traders) → A-list topic
        # Priority 2: Size-based routing (Low/High Size)
        selected_topic_id = None
        size_category = None
        
        a_list_count = len(a_list_wallets) if a_list_wallets else 0
        
        # Debug: Log topic IDs configuration
        logger.info(f"[NOTIFY] Topic IDs config: low_size_topic_id={self.low_size_topic_id}, high_size_topic_id={self.high_size_topic_id}, a_list_topic_id={self.a_list_topic_id}, size_threshold_usd={self.size_threshold_usd}")
        logger.info(f"[NOTIFY] A-list check: a_list_count={a_list_count}, category={category}")
        
        # Priority 1: Check if this is an A-list alert (2+ A-list traders)
        if a_list_count >= 2 and self.a_list_topic_id:
            selected_topic_id = self.a_list_topic_id
            size_category = "A List"
            logger.info(f"[NOTIFY] Routing A-list alert: {a_list_count} A-list traders in category={category}, a_list_topic_id={self.a_list_topic_id}, selected_topic_id={selected_topic_id}")
        elif isinstance(total_usd, (int, float)) and total_usd is not None:
            # Priority 2: Route based on size (if not A-list)
            if total_usd < self.size_threshold_usd:
                # Low Size alert (< $10k)
                selected_topic_id = self.low_size_topic_id
                size_category = "Low Size"
                logger.info(f"[NOTIFY] Routing Low Size alert: total_usd=${total_usd:.2f} < ${self.size_threshold_usd:.2f}, low_size_topic_id={self.low_size_topic_id}, selected_topic_id={selected_topic_id}")
            else:
                # High Size alert (>= $10k)
                selected_topic_id = self.high_size_topic_id
                size_category = "High Size"
                logger.info(f"[NOTIFY] Routing High Size alert: total_usd=${total_usd:.2f} >= ${self.size_threshold_usd:.2f}, high_size_topic_id={self.high_size_topic_id}, selected_topic_id={selected_topic_id}")
        else:
            # Fallback to legacy topic_id if total_usd is not available
            # This handles cases where total_usd is None or not calculated
            selected_topic_id = self.topic_id
            size_category = "Unknown Size"
            logger.warning(f"[NOTIFY] total_usd is not available (value: {total_usd}), using legacy topic_id={self.topic_id}")
        
        # Log topic selection for debugging
        total_usd_str = f"${total_usd:.2f}" if isinstance(total_usd, (int, float)) and total_usd is not None else "$0.00"
        if selected_topic_id:
            logger.info(f"[NOTIFY] Sending {size_category} alert to chat_id={target_chat}, topic_id={selected_topic_id}, total_usd={total_usd_str}")
        else:
            logger.warning(f"[NOTIFY] ⚠️  Sending alert to chat_id={target_chat}, topic_id=None (no topic configured for {size_category}). low_size_topic_id={self.low_size_topic_id}, high_size_topic_id={self.high_size_topic_id}")
        
        logger.info(f"[NOTIFY] 📤 Sending consensus alert to Telegram (chat_id={target_chat}, topic_id={selected_topic_id}, size_category={size_category})")
        logger.info(f"[NOTIFY] 📤 Calling send_message() to Telegram for condition={condition_id[:20]}... outcome={outcome_index} side={side} wallets={len(wallets)} total_usd={total_usd_str}")
        try:
            result = self.send_message(message, reply_markup=reply_markup, chat_id=target_chat, message_thread_id=selected_topic_id)
        except requests.exceptions.Timeout as e:
            logger.error(f"[NOTIFY] ❌ Timeout error in send_message(): {e}")
            result = False
        except requests.exceptions.RequestException as e:
            logger.error(f"[NOTIFY] ❌ Request error in send_message(): {type(e).__name__}: {e}")
            result = False
        except Exception as e:
            logger.error(f"[NOTIFY] ❌ Exception in send_message(): {type(e).__name__}: {e}", exc_info=True)
            result = False
        
        if result:
            logger.info(f"[NOTIFY] ✅ Consensus alert sent successfully to Telegram: condition={condition_id[:20]}... outcome={outcome_index} side={side} wallets={len(wallets)}")
        else:
            logger.error(f"[NOTIFY] ❌ Failed to send consensus alert to Telegram: condition={condition_id[:20]}... outcome={outcome_index} side={side} wallets={len(wallets)}")
        
        return result
    
    def _format_usd(self, amount: Optional[float]) -> str:
        """Format USD amount with commas and 2 decimal places"""
        if amount is None:
            return "$0.00"
        return f"${amount:,.2f}"
    
    def _shorten_address(self, address: Optional[str]) -> str:
        """Format wallet address as 0x{first4}...{last4}"""
        if not address or len(address) < 8:
            return address or "N/A"
        return f"0x{address[2:6]}...{address[-4:]}" if address.startswith("0x") else f"{address[:4]}...{address[-4:]}"
    
    def _format_insider_reason(self, reason: str) -> str:
        """Format insider detection reason for display"""
        reason_map = {
            "new_wallet_large_position": "🆕 New Wallet with Large Position",
            "high_winrate_new_wallet": "🎯 High Win Rate on First Trades",
            "concentrated_trading": "🎲 Concentrated Trading Pattern"
        }
        return reason_map.get(reason, f"⚠️ {reason}")
    
    def send_oi_spike_alert(self, condition_id: str, market_title: str, market_slug: str,
                           old_oi: float, new_oi: float, spike_percent: float,
                           timestamp: str) -> bool:
        """Send open interest spike alert"""
        try:
            logger.info(f"[OI] Preparing OI spike alert: {condition_id[:20]}... spike={spike_percent:.1f}%")
            
            # Build market URL
            event_slug, market_id, market_slug_from_api, event_data = self._get_event_slug_and_market_id(condition_id)
            market_url = self._build_market_url(
                condition_id=condition_id,
                event_slug=event_slug,
                market_id=market_id,
                market_slug=market_slug or market_slug_from_api,
                event_data=event_data
            )
            
            # Format OI values
            old_oi_str = self._format_usd(old_oi)
            new_oi_str = self._format_usd(new_oi)
            
            # Build message
            timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            
            message = f"""🔥 *Open Interest Spike Detected*

🎯 *Market:* {market_title}
📊 *OI Change:* {old_oi_str} → {new_oi_str}
📈 *Spike:* +{spike_percent:.1f}%

💡 Large increase in open interest may indicate smart money entering

📅 {timestamp_utc} UTC"""
            
            # Inline keyboard with View Market button
            reply_markup = {
                "inline_keyboard": [[
                    {"text": "View Market", "url": market_url}
                ]]
            }
            
            # Route to OI spike topic if configured
            target_chat = self.chat_id
            selected_topic_id = self.oi_spike_topic_id
            
            logger.info(f"[OI] 📤 Sending OI spike alert to Telegram (chat_id={target_chat}, topic_id={selected_topic_id})")
            result = self.send_message(
                message,
                reply_markup=reply_markup,
                chat_id=target_chat,
                message_thread_id=selected_topic_id
            )
            
            if result:
                logger.info(f"[OI] ✅ OI spike alert sent successfully: {condition_id[:20]}... spike={spike_percent:.1f}%")
            else:
                logger.error(f"[OI] ❌ Failed to send OI spike alert: {condition_id[:20]}...")
            
            return result
            
        except Exception as e:
            logger.error(f"[OI] Error sending OI spike alert: {e}", exc_info=True)
            return False
    
    def send_whale_position_alert(self, user_address: str, condition_id: str, outcome_index: int,
                                 market_title: str, market_slug: str, position_size_usd: float,
                                 position_type: str, current_price: float) -> bool:
        """Send whale position alert"""
        try:
            logger.info(f"[WHALE] Preparing whale position alert: {user_address[:12]}... type={position_type} size=${position_size_usd:,.0f}")
            
            # Build market URL
            event_slug, market_id, market_slug_from_api, event_data = self._get_event_slug_and_market_id(condition_id)
            market_url = self._build_market_url(
                condition_id=condition_id,
                event_slug=event_slug,
                market_id=market_id,
                market_slug=market_slug or market_slug_from_api,
                event_data=event_data
            )
            
            # Get outcome name
            outcome_name = self._get_outcome_name(condition_id, outcome_index)
            if not outcome_name:
                outcome_name = "Yes" if outcome_index == 0 else "No"
            
            # Format wallet address
            wallet_short = self._shorten_address(user_address)
            
            # Format position type
            position_type_display = "WHALE ENTRY" if position_type == "entry" else "WHALE EXIT"
            emoji = "🐋" if position_type == "entry" else "🐋"
            
            # Format position size and price
            position_size_str = self._format_usd(position_size_usd)
            price_str = f"{current_price:.2f}¢" if current_price < 1.0 else f"${current_price:.2f}"
            
            # Build wallet links
            wallet_links = []
            try:
                # PolymarketAnalytics link
                wallet_links.append(f"[PolymarketAnalytics](https://polymarketanalytics.com/wallet/{user_address})")
            except Exception:
                pass
            
            try:
                # HashDive link (if available)
                if self.hashdive_client:
                    wallet_links.append(f"[HashDive](https://hashdive.com/wallet/{user_address})")
            except Exception:
                pass
            
            wallet_links_str = " | ".join(wallet_links) if wallet_links else f"`{wallet_short}`"
            
            # Build message
            timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            
            message = f"""{emoji} *{position_type_display}*

👤 *Wallet:* {wallet_short}
🔗 {wallet_links_str}

🎯 *Market:* {market_title}
📊 *Outcome:* {outcome_name}
💰 *Position Size:* {position_size_str}
💵 *Current Price:* {price_str}

📅 {timestamp_utc} UTC"""
            
            # Inline keyboard with View Market button
            reply_markup = {
                "inline_keyboard": [[
                    {"text": "View Market", "url": market_url}
                ]]
            }
            
            # Route to whale position topic if configured
            target_chat = self.chat_id
            selected_topic_id = self.whale_position_topic_id
            
            logger.info(f"[WHALE] 📤 Sending whale position alert to Telegram (chat_id={target_chat}, topic_id={selected_topic_id})")
            result = self.send_message(
                message,
                reply_markup=reply_markup,
                chat_id=target_chat,
                message_thread_id=selected_topic_id
            )
            
            if result:
                logger.info(f"[WHALE] ✅ Whale position alert sent successfully: {user_address[:12]}... type={position_type}")
            else:
                logger.error(f"[WHALE] ❌ Failed to send whale position alert: {user_address[:12]}...")
            
            return result
            
        except Exception as e:
            logger.error(f"[WHALE] Error sending whale position alert: {e}", exc_info=True)
            return False
    
    def send_order_flow_alert(self, condition_id: str, outcome_index: int,
                              buy_count: int, sell_count: int,
                              buy_volume: float, sell_volume: float,
                              buy_sell_ratio: float, imbalance_direction: str,
                              window_minutes: float,
                              market_title: str = "", market_slug: str = "",
                              current_price: Optional[float] = None,
                              end_date: Optional[datetime] = None) -> bool:
        """Send order flow imbalance alert"""
        try:
            logger.info(f"[ORDER_FLOW] Preparing order flow alert: {condition_id[:12]}... direction={imbalance_direction} ratio={buy_sell_ratio:.2%}")
            
            # Build market URL
            event_slug, market_id, market_slug_from_api, event_data = self._get_event_slug_and_market_id(condition_id)
            market_url = self._build_market_url(
                condition_id=condition_id,
                event_slug=event_slug,
                market_id=market_id,
                market_slug=market_slug or market_slug_from_api,
                event_data=event_data
            )
            
            # Format numbers
            ratio_percent = buy_sell_ratio * 100.0
            buy_volume_str = self._format_usd(buy_volume)
            sell_volume_str = self._format_usd(sell_volume)
            
            # Determine emoji and direction indicators
            if imbalance_direction.upper() == 'BUY':
                direction_emoji = "🟢"
                trend_emoji = "📈"
                direction_text = "Strong buying pressure"
            else:
                direction_emoji = "🔴"
                trend_emoji = "📉"
                direction_text = "Strong selling pressure"
            
            # Format price
            price_str = "N/A"
            if current_price is not None:
                if current_price < 1.0:
                    price_str = f"${current_price:.2f}¢"
                else:
                    price_str = f"${current_price:.2f}"
            
            # Format end date
            end_date_str = ""
            if end_date:
                try:
                    end_date_str = end_date.strftime("%b %d, %Y %H:%M UTC")
                except Exception:
                    pass
            
            # Build message
            timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            
            message = f"""📊 *Order Flow Imbalance Detected*

**Market**: {market_title or 'N/A'}

⚖️ **Imbalance**: {direction_emoji} {imbalance_direction} {ratio_percent:.1f}%
{trend_emoji} **Direction**: {direction_text}

**Order Flow (Last {window_minutes:.0f} min)**:
• Buy Orders: {buy_count} ({buy_volume_str})
• Sell Orders: {sell_count} ({sell_volume_str})
• Ratio: {ratio_percent:.1f}% {imbalance_direction} / {100-ratio_percent:.1f}% {"SELL" if imbalance_direction == "BUY" else "BUY"}

💰 **Current Price**: {price_str}"""
            
            if end_date_str:
                message += f"\n⏰ **Closes**: {end_date_str}"
            
            message += f"\n\n📅 {timestamp_utc} UTC"
            
            # Add inline keyboard with "View Market" button
            reply_markup = {
                "inline_keyboard": [[
                    {"text": "View Market", "url": market_url}
                ]]
            }
            
            # Determine target chat and topic
            target_chat = self.reports_chat_id
            selected_topic_id = self.order_flow_topic_id
            
            if selected_topic_id:
                logger.info(f"[ORDER_FLOW] Routing to order flow topic: chat_id={target_chat}, topic_id={selected_topic_id}")
            else:
                logger.info(f"[ORDER_FLOW] No order flow topic configured, using reports channel: chat_id={target_chat}")
            
            logger.info(f"[ORDER_FLOW] 📤 Sending order flow alert to Telegram (chat_id={target_chat}, topic_id={selected_topic_id})")
            result = self.send_message(
                message,
                reply_markup=reply_markup,
                chat_id=target_chat,
                message_thread_id=selected_topic_id,
                parse_mode="Markdown"
            )
            
            if result:
                logger.info(f"[ORDER_FLOW] ✅ Order flow alert sent successfully: {condition_id[:12]}... {imbalance_direction} {ratio_percent:.1f}%")
            else:
                logger.error(f"[ORDER_FLOW] ❌ Failed to send order flow alert: {condition_id[:12]}...")
            
            return result
            
        except Exception as e:
            logger.error(f"[ORDER_FLOW] Error sending order flow alert: {e}", exc_info=True)
            return False
    
    def send_insider_alert(self, condition_id: str, outcome_index: int, wallet: str,
                          reason: str, market_title: str, market_slug: str, side: str,
                          position_size: float, win_rate: float, total_trades: int,
                          total_markets: int, current_price: Optional[float] = None,
                          category: Optional[str] = None) -> bool:
        """Send insider alert for suspicious trading patterns"""
        try:
            logger.info(f"[INSIDER] Preparing insider alert for wallet {wallet[:12]}... reason={reason}")
            
            # Format reason display
            reason_display = self._format_insider_reason(reason)
            
            # Build market URL using existing logic
            event_slug, market_id, market_slug_from_api, event_data = self._get_event_slug_and_market_id(condition_id)
            market_url = self._build_market_url(
                condition_id=condition_id,
                event_slug=event_slug,
                market_id=market_id,
                market_slug=market_slug or market_slug_from_api,
                event_data=event_data
            )
            
            # Get outcome name
            outcome_name = self._get_outcome_name(condition_id, outcome_index)
            if not outcome_name:
                outcome_name = f"Outcome {outcome_index}"
            
            # Format wallet info
            wallet_short = f"{wallet[:6]}...{wallet[-4:]}"
            
            # Build message
            timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            
            message = f"""*🚨 Insider Alert: {reason_display}*

🎯 *Market:* {market_title}
📊 *Category:* {category or "N/A"}

*Outcome:* {outcome_name}
*Side:* {side}

👤 *Wallet:* `{wallet_short}`
📊 *Stats:*
• Win Rate: {win_rate:.1%}
• Total Trades: {total_trades}
• Markets Traded: {total_markets}
• Position Size: ${position_size:,.0f}

*Price:* {current_price:.6f if current_price is not None else "N/A"}

📅 {timestamp_utc} UTC"""
            
            # Add inline keyboard with "View Market" button
            reply_markup = {
                "inline_keyboard": [[
                    {"text": "View Market", "url": market_url}
                ]]
            }
            
            # Route to insider topic
            target_chat = self.reports_chat_id
            selected_topic_id = self.insider_topic_id
            
            if selected_topic_id:
                logger.info(f"[INSIDER] Routing to insider topic: chat_id={target_chat}, topic_id={selected_topic_id}")
            else:
                logger.info(f"[INSIDER] No insider topic configured, using reports channel: chat_id={target_chat}")
            
            # Send message
            logger.info(f"[INSIDER] 📤 Sending insider alert to Telegram (chat_id={target_chat}, topic_id={selected_topic_id})")
            try:
                result = self.send_message(
                    message,
                    reply_markup=reply_markup,
                    chat_id=target_chat,
                    message_thread_id=selected_topic_id
                )
            except Exception as e:
                logger.error(f"[INSIDER] ❌ Exception in send_message(): {e}", exc_info=True)
                result = False
            
            if result:
                logger.info(f"[INSIDER] ✅ Insider alert sent successfully: wallet={wallet[:12]}... reason={reason}")
            else:
                logger.error(f"[INSIDER] ❌ Failed to send insider alert: wallet={wallet[:12]}... reason={reason}")
            
            return result
            
        except Exception as e:
            logger.error(f"[INSIDER] Error sending insider alert: {e}", exc_info=True)
            return False
    
    def send_startup_notification(self, wallet_count: int, tracked_count: int) -> bool:
        """Send startup notification with system status to reports channel"""
        message = f"""🤖 *Polymarket Notifier Started*

📊 *System Status:*
• Total wallets in DB: {wallet_count}
• Actively tracked: {tracked_count}
• Monitoring: Active

_{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC_"""
        
        return self.send_message(message, chat_id=self.reports_chat_id)
    
    def send_error_notification(self, error_type: str, error_message: str) -> bool:
        """Send error notification to reports channel"""
        message = f"""⚠️ *Polymarket Notifier Error*

*Type:* {error_type}
*Message:* `{error_message}`

_{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC_"""
        
        return self.send_message(message, chat_id=self.reports_chat_id)
    
    def send_heartbeat(self, stats: Dict[str, Any]) -> bool:
        """Send periodic heartbeat with statistics to reports channel"""
        message = f"""💓 *Polymarket Notifier Heartbeat*

📊 *Current Stats:*
• Tracked wallets: {stats.get('tracked_wallets', 0)}
• Total wallets: {stats.get('total_wallets', 0)}
• High win rate (80%+): {stats.get('high_winrate', 0)}
• Medium win rate (70-80%): {stats.get('medium_winrate', 0)}
• Low win rate (<70%): {stats.get('low_winrate', 0)}

_{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC_"""
        
        return self.send_message(message, chat_id=self.reports_chat_id)

    def send_suppression_report(self, counters: Dict[str, int]) -> bool:
        """Send diagnostics about suppressed alerts to reports channel"""
        lines = [f"• {k}: {v}" for k,v in counters.items()]
        message = f"""🧪 *Alerts Suppression Report*

{chr(10).join(lines)}

_{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC_"""
        return self.send_message(message, chat_id=self.reports_chat_id)
    
    def send_error_report(self, counters: Dict[str, int]) -> bool:
        """Send aggregated error counters to reports channel"""
        lines = [f"• {k}: {v}" for k, v in counters.items()]
        message = f"""🧯 *Errors Report (last hour)*

{chr(10).join(lines)}

_{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC_"""
        return self.send_message(message, chat_id=self.reports_chat_id)
    
    def send_suppressed_alert_details(self, reason: str, condition_id: str, outcome_index: int,
                                     wallets: List[str], wallet_prices: Dict[str, float] = {},
                                     market_title: str = "", market_slug: str = "",
                                     current_price: Optional[float] = None,
                                     side: str = "BUY", total_usd: Optional[float] = None,
                                     market_active: Optional[bool] = None) -> bool:
        """
        Send details of a suppressed alert to reports channel for review
        
        Args:
            reason: Reason for suppression (e.g., "resolved", "price_high", "market_closed")
            condition_id: Market condition ID
            outcome_index: Outcome index
            wallets: List of wallet addresses
            wallet_prices: Map of wallet -> entry price
            market_title: Market title
            market_slug: Market slug for URL
            current_price: Current market price
            side: Trade side (BUY/SELL)
            total_usd: Total USD position size
            market_active: Whether market is active (if None, will check if reason indicates closed market)
        """
        # Check if this is a suppressed alert for closed/resolved market
        # If so, only log to file, don't send to Telegram
        # Suppressed alerts for closed/resolved markets should not be sent to Telegram
        if reason in ("market_closed", "resolved"):
            # If market is not active (False) or status is unknown (None), only log, don't send
            if not market_active or market_active is None:
                logger.info(
                    f"[SUPPRESSED ALERT] Closed/Resolved market - logging only (not sending to Telegram): "
                    f"condition_id={condition_id}, outcome={outcome_index}, reason={reason}"
                )
                return True  # Return True to indicate "handled", but no message sent
        # Build market URL - Support complex markets with event_slug/market_slug format and sports URLs
        # Try to get event slug, market_id, market_slug, and event object first
        event_slug, market_id, market_slug_from_api, event_obj = self._get_event_slug_and_market_id(condition_id)
        
        # If market_id is still None, try to get it from CLOB API directly (CRITICAL for complex markets)
        if not market_id:
            logger.warning(f"[URL] market_id is None after Gamma API (suppressed alert), trying CLOB API fallback for condition={condition_id[:20]}...")
            try:
                clob_url = f"https://clob.polymarket.com/markets/{condition_id}"
                clob_response = self._make_authenticated_get(clob_url, timeout=5)
                if clob_response and clob_response.status_code == 200:
                    clob_data = clob_response.json()
                    # Try multiple field names for market ID
                    clob_market_id = (clob_data.get('id') or 
                                    clob_data.get('marketId') or 
                                    clob_data.get('tid') or
                                    clob_data.get('market_id') or
                                    clob_data.get('marketIdNum'))
                    if clob_market_id:
                        try:
                            # Handle string IDs with numeric extraction
                            if isinstance(clob_market_id, str):
                                import re
                                numeric_match = re.search(r'\d+', str(clob_market_id))
                                if numeric_match:
                                    market_id = int(numeric_match.group())
                                else:
                                    market_id = None
                            else:
                                market_id = int(clob_market_id)
                            if market_id:
                                logger.info(f"[URL] ✅ Got market_id={market_id} from CLOB API direct query (suppressed alert) for condition={condition_id[:20]}...")
                        except (ValueError, TypeError) as e:
                            logger.debug(f"[URL] Failed to parse market_id from CLOB API (suppressed alert): {clob_market_id}, error: {e}")
                            market_id = None
                    else:
                        logger.warning(f"[URL] No market_id found in CLOB API response (suppressed alert) for condition={condition_id[:20]}... Available fields: {list(clob_data.keys())[:20]}")
                else:
                    logger.warning(f"[URL] CLOB API returned status {clob_response.status_code if clob_response else 'None'} (suppressed alert) for condition={condition_id[:20]}...")
            except Exception as e:
                logger.warning(f"[URL] Failed to get market_id from CLOB API direct query (suppressed alert): {e}")
            
            # Fallback: Try Data API if CLOB API didn't provide market_id
            if not market_id:
                logger.warning(f"[URL] market_id is still None after CLOB API (suppressed alert), trying Data API fallback for condition={condition_id[:20]}...")
                try:
                    data_api_url = f"https://data-api.polymarket.com/condition/{condition_id}"
                    data_api_response = self._make_authenticated_get(data_api_url, timeout=5)
                    if data_api_response and data_api_response.status_code == 200:
                        data_api_data = data_api_response.json()
                        # Try multiple field names for market ID
                        data_api_market_id = (data_api_data.get('id') or 
                                            data_api_data.get('marketId') or 
                                            data_api_data.get('tid') or
                                            data_api_data.get('market_id') or
                                            data_api_data.get('marketIdNum'))
                        if data_api_market_id:
                            try:
                                # Handle string IDs with numeric extraction
                                if isinstance(data_api_market_id, str):
                                    import re
                                    numeric_match = re.search(r'\d+', str(data_api_market_id))
                                    if numeric_match:
                                        market_id = int(numeric_match.group())
                                    else:
                                        market_id = None
                                else:
                                    market_id = int(data_api_market_id)
                                if market_id:
                                    logger.info(f"[URL] ✅ Got market_id={market_id} from Data API fallback (suppressed alert) for condition={condition_id[:20]}...")
                            except (ValueError, TypeError) as e:
                                logger.debug(f"[URL] Failed to parse market_id from Data API (suppressed alert): {data_api_market_id}, error: {e}")
                                market_id = None
                        else:
                            logger.warning(f"[URL] No market_id found in Data API response (suppressed alert) for condition={condition_id[:20]}... Available fields: {list(data_api_data.keys())[:20]}")
                    else:
                        logger.warning(f"[URL] Data API returned status {data_api_response.status_code if data_api_response else 'None'} (suppressed alert) for condition={condition_id[:20]}...")
                except Exception as e:
                    logger.warning(f"[URL] Failed to get market_id from Data API fallback (suppressed alert): {e}")
        
        # Detect if this is a sports market
        # Use market_slug parameter as fallback if market_slug_from_api is None
        slug_for_detection = market_slug_from_api or event_slug
        is_sports_market = self._detect_sports_event(event_obj, event_slug, slug_for_detection)
        
        # Priority 1: Sports markets - try to use sports URL from event object
        if is_sports_market and event_obj:
            # Try to get sports URL using helper function
            sports_url = self._get_sports_url_from_event(event_obj, event_slug)
            
            if sports_url:
                market_url = sports_url
                logger.info(f"[URL] [SPORTS] Using sports URL from event: {market_url} (condition_id={condition_id[:20]}...)")
            elif event_slug:
                # For sports markets, try to use event_slug/market_slug format if market_slug is available
                # This is needed for markets like Counter-Strike that need the full path
                event_slug_clean = event_slug.strip().strip('/')
                sports_market_slug = market_slug_from_api or market_slug
                
                if not sports_market_slug:
                    sports_market_slug = self._get_market_slug(condition_id)
                
                if sports_market_slug:
                    sports_market_slug_clean = sports_market_slug.strip().strip('/')
                    # If market_slug equals event_slug, use only event_slug (don't duplicate)
                    if sports_market_slug_clean == event_slug_clean:
                        market_url = f"https://polymarket.com/event/{event_slug_clean}"
                        logger.info(f"[URL] [SPORTS] Market slug equals event slug, using only event_slug: {event_slug_clean} (condition_id={condition_id[:20]}...)")
                    # Remove event_slug prefix from market_slug if it's already there
                    elif sports_market_slug_clean.startswith(event_slug_clean + '/'):
                        market_url = f"https://polymarket.com/event/{sports_market_slug_clean}"
                        logger.info(f"[URL] [SPORTS] Market slug already contains event slug, using as-is: {sports_market_slug_clean} (condition_id={condition_id[:20]}...)")
                    elif sports_market_slug_clean.startswith(event_slug_clean + '-'):
                        # Market slug starts with event slug followed by dash, extract suffix
                        market_suffix = sports_market_slug_clean[len(event_slug_clean) + 1:]
                        market_url = f"https://polymarket.com/event/{event_slug_clean}/{market_suffix}"
                        logger.info(f"[URL] [SPORTS] Using event_slug/market_suffix format: event={event_slug_clean}, suffix={market_suffix} (condition_id={condition_id[:20]}...)")
                    elif sports_market_slug_clean.startswith(event_slug_clean):
                        # Market slug starts with event slug (no separator), use full market_slug
                        market_url = f"https://polymarket.com/event/{event_slug_clean}/{sports_market_slug_clean}"
                        logger.info(f"[URL] [SPORTS] Using event_slug/market_slug format: event={event_slug_clean}, market_slug={sports_market_slug_clean} (condition_id={condition_id[:20]}...)")
                    else:
                        # Combine event_slug and market_slug
                        market_url = f"https://polymarket.com/event/{event_slug_clean}/{sports_market_slug_clean}"
                        logger.info(f"[URL] [SPORTS] Using event_slug/market_slug format: event={event_slug_clean}, market_slug={sports_market_slug_clean} (condition_id={condition_id[:20]}...)")
                else:
                    # Fallback: use event slug for sports (without market_slug)
                    market_url = f"https://polymarket.com/event/{event_slug_clean}"
                    logger.info(f"[URL] [SPORTS] Fallback: event slug without market_slug: {event_slug_clean} (condition_id={condition_id[:20]}...)")
            else:
                # Fallback to market slug
                if not market_slug:
                    market_slug = self._get_market_slug(condition_id)
                if market_slug:
                    slug_clean = market_slug.strip().strip('/')
                    market_url = f"https://polymarket.com/event/{slug_clean}"
                    logger.info(f"[URL] [SPORTS] Fallback: market slug: {slug_clean} (condition_id={condition_id[:20]}...)")
                else:
                    market_url = self._get_search_url_fallback(condition_id)
                    logger.info(f"[URL] [SPORTS] Fallback: search URL (condition_id={condition_id[:20]}...)")

        
        # Priority 2: Complex markets (non-sports) - ALWAYS prefer event_slug?tid={market_id} format if market_id available
        # This is the most reliable format for complex markets with multiple sub-markets (e.g., Bitcoin price markets)
        if not is_sports_market and event_slug and market_id:
            slug_clean = self._clean_slug(event_slug)
            market_url = f"https://polymarket.com/event/{slug_clean}?tid={market_id}"
            logger.info(f"[URL] ✅ Using event_slug?tid format for complex market: event={slug_clean}, tid={market_id} (condition_id={condition_id[:20]}...)")
        
        # Priority 3: Complex markets (non-sports) - use event_slug/market_slug format if no market_id
        elif not is_sports_market and event_slug and market_slug_from_api:
            event_slug_clean = self._clean_slug(event_slug)
            market_slug_clean = self._clean_slug(market_slug_from_api)
            
            # VALIDATION: Check for confusion between event_slug and market_slug
            # If both slugs look market-specific, don't build URL as event_slug/market_slug
            event_slug_is_market_specific = self._is_market_specific_slug(event_slug_clean)
            market_slug_is_market_specific = self._is_market_specific_slug(market_slug_clean)
            
            if event_slug_is_market_specific and market_slug_is_market_specific:
                # Both slugs are market-specific - this indicates confusion
                # Prefer event_slug?tid={market_id} format if market_id is available, otherwise fallback to search
                logger.warning(
                    f"[URL] [VALIDATION] ⚠️ Both event_slug and market_slug appear market-specific: "
                    f"event_slug='{event_slug_clean[:50]}', market_slug='{market_slug_clean[:50]}' "
                    f"(condition_id={condition_id[:20]}...). "
                    f"Using fallback format to avoid incorrect URL."
                )
                if market_id:
                    slug_clean = self._clean_slug(event_slug)
                    market_url = f"https://polymarket.com/event/{slug_clean}?tid={market_id}"
                    logger.info(f"[URL] [VALIDATION] Using event_slug?tid fallback: event={slug_clean}, tid={market_id} (condition_id={condition_id[:20]}...)")
                else:
                    market_url = self._get_search_url_fallback(condition_id)
                    logger.info(f"[URL] [VALIDATION] Using search URL fallback (no market_id available) (condition_id={condition_id[:20]}...)")
            else:
                # Normal case: proceed with event_slug/market_slug construction
                # Remove event_slug prefix from market_slug if it's already there
                if market_slug_clean.startswith(event_slug_clean + '/'):
                    # Market slug already contains event slug with separator, use as-is
                    market_url = f"https://polymarket.com/event/{market_slug_clean}"
                    logger.info(f"[URL] Market slug already contains event slug, using as-is: {market_slug_clean} (condition_id={condition_id[:20]}...)")
                elif market_slug_clean.startswith(event_slug_clean + '-'):
                    # Market slug starts with event slug followed by dash, extract suffix
                    market_suffix = market_slug_clean[len(event_slug_clean) + 1:]
                    market_url = f"https://polymarket.com/event/{event_slug_clean}/{market_suffix}"
                    logger.info(f"[URL] Using event_slug/market_suffix format: event={event_slug_clean}, suffix={market_suffix} (condition_id={condition_id[:20]}...)")
                elif market_slug_clean == event_slug_clean:
                    # If market_slug equals event_slug, still use event_slug/market_slug format (required by Polymarket)
                    market_url = f"https://polymarket.com/event/{event_slug_clean}/{market_slug_clean}"
                    logger.info(f"[URL] Market slug equals event slug, using event_slug/market_slug format: {event_slug_clean}/{market_slug_clean} (condition_id={condition_id[:20]}...)")
                elif market_slug_clean.startswith(event_slug_clean):
                    # Market slug starts with event slug (no separator), use full market_slug
                    market_url = f"https://polymarket.com/event/{event_slug_clean}/{market_slug_clean}"
                    logger.info(f"[URL] Using event_slug/market_slug for complex market: event={event_slug_clean}, market_slug={market_slug_clean} (condition_id={condition_id[:20]}...)")
                else:
                    # Combine event_slug and market_slug
                    market_url = f"https://polymarket.com/event/{event_slug_clean}/{market_slug_clean}"
                    logger.info(f"[URL] Using event_slug/market_slug for complex market: event={event_slug_clean}, market_slug={market_slug_clean} (condition_id={condition_id[:20]}...)")
        
        # Priority 4: Event slug without market_slug/tid (fallback for complex markets)
        # WARNING: This should only be used if market_id and market_slug_from_api are both unavailable
        # Try to get market_slug using _get_market_slug() before falling back to just event_slug
        elif not is_sports_market and event_slug:
            event_slug_clean = self._clean_slug(event_slug)
            # Try to get market_slug as fallback (always use API, never use market_slug parameter from events)
            fallback_market_slug = market_slug_from_api
            if not fallback_market_slug:
                fallback_market_slug = self._get_market_slug(condition_id)
            
            # If still no market_slug, try CLOB API directly as last resort
            if not fallback_market_slug:
                try:
                    clob_url = f"https://clob.polymarket.com/markets/{condition_id}"
                    clob_response = self._make_authenticated_get(clob_url, timeout=5)
                    if clob_response and clob_response.status_code == 200:
                        clob_data = clob_response.json()
                        # Try to get market_slug from CLOB API
                        clob_market_slug = (clob_data.get('question_slug') or 
                                          clob_data.get('market_slug') or 
                                          clob_data.get('slug') or
                                          clob_data.get('event_slug'))
                        if clob_market_slug:
                            # Use centralized cleaning function
                            clob_market_slug = self._clean_slug(clob_market_slug, strip_market_prefix=True)
                            if clob_market_slug:
                                # Always use market_slug even if it equals event_slug (we'll use event_slug/market_slug format)
                                fallback_market_slug = clob_market_slug
                                logger.info(f"[URL] Got market_slug from CLOB API fallback: {fallback_market_slug} (condition_id={condition_id[:20]}...)")
                except Exception as e:
                    logger.debug(f"[URL] Failed to get market_slug from CLOB API fallback: {e}")
            
            if fallback_market_slug:
                fallback_market_slug_clean = self._clean_slug(fallback_market_slug)
                # Remove event_slug prefix from market_slug if it's already there
                if fallback_market_slug_clean.startswith(event_slug_clean + '/'):
                    market_url = f"https://polymarket.com/event/{fallback_market_slug_clean}"
                    logger.warning(f"[URL] ⚠️  Fallback: market_slug already contains event_slug, using as-is: {fallback_market_slug_clean} (condition_id={condition_id[:20]}...)")
                elif fallback_market_slug_clean.startswith(event_slug_clean + '-'):
                    # Market slug starts with event slug followed by dash (e.g., "event-slug-220-239")
                    # Extract the market-specific suffix
                    market_suffix = fallback_market_slug_clean[len(event_slug_clean) + 1:]  # +1 to skip the dash
                    market_url = f"https://polymarket.com/event/{event_slug_clean}/{market_suffix}"
                    logger.warning(f"[URL] ⚠️  Fallback: Extracted market suffix from market_slug: event={event_slug_clean}, suffix={market_suffix} (condition_id={condition_id[:20]}...)")
                elif fallback_market_slug_clean == event_slug_clean:
                    # If market_slug equals event_slug, still use event_slug/market_slug format (required by Polymarket)
                    market_url = f"https://polymarket.com/event/{event_slug_clean}/{fallback_market_slug_clean}"
                    logger.warning(f"[URL] ⚠️  Fallback: market_slug equals event_slug, using event_slug/market_slug format: {event_slug_clean}/{fallback_market_slug_clean} (condition_id={condition_id[:20]}...)")
                elif fallback_market_slug_clean.startswith(event_slug_clean):
                    # Market slug starts with event slug (no separator), use full market_slug
                    market_url = f"https://polymarket.com/event/{event_slug_clean}/{fallback_market_slug_clean}"
                    logger.warning(f"[URL] ⚠️  Fallback: Using event_slug/market_slug format: event={event_slug_clean}, market_slug={fallback_market_slug_clean} (condition_id={condition_id[:20]}...)")
                else:
                    # Combine event_slug and market_slug
                    market_url = f"https://polymarket.com/event/{event_slug_clean}/{fallback_market_slug_clean}"
                    logger.warning(f"[URL] ⚠️  Fallback: Using event_slug/market_slug format: event={event_slug_clean}, market_slug={fallback_market_slug_clean} (condition_id={condition_id[:20]}...)")
            else:
                # No market_slug available - use event_slug/market_slug format with event_slug as both parts (last resort)
                # This ensures we always use the required format even if market_slug is unavailable
                market_url = f"https://polymarket.com/event/{event_slug_clean}/{event_slug_clean}"
                logger.warning(f"[URL] ⚠️  Fallback: No market_slug found, using event_slug/market_slug format with duplicate: {event_slug_clean}/{event_slug_clean} (condition_id={condition_id[:20]}...)")
        
        # Priority 5: Market slug fallback
        else:
            if not market_slug:
                market_slug = self._get_market_slug(condition_id)
            
            if market_slug:
                market_slug_clean = self._clean_slug(market_slug)
                # Try to get event_slug from CLOB API if not available
                fallback_event_slug = event_slug
                if not fallback_event_slug:
                    try:
                        clob_url = f"https://clob.polymarket.com/markets/{condition_id}"
                        clob_response = self._make_authenticated_get(clob_url, timeout=5)
                        if clob_response and clob_response.status_code == 200:
                            clob_data = clob_response.json()
                            # Try to extract event_slug from question or description
                            question = clob_data.get('question') or clob_data.get('description') or ""
                            # Also try to get event_slug from market_slug by removing market-specific parts
                            clob_event_slug = clob_data.get('event_slug')
                            if clob_event_slug:
                                # Use centralized cleaning function
                                clob_event_slug = self._clean_slug(clob_event_slug)
                                if clob_event_slug and clob_event_slug != market_slug_clean:
                                    fallback_event_slug = clob_event_slug
                                    logger.info(f"[URL] Got event_slug from CLOB API (Priority 5): {fallback_event_slug} (condition_id={condition_id[:20]}...)")
                    except Exception as e:
                        logger.debug(f"[URL] Failed to get event_slug from CLOB API (Priority 5): {e}")
                
                # If still no event_slug and this is a sports market, try to extract from market_slug
                if not fallback_event_slug and is_sports_market:
                    # For sports markets, try to extract event_slug by removing market-specific suffixes
                    market_parts = market_slug_clean.split('-')
                    # Check if market_slug contains a date pattern (YYYY-MM-DD)
                    has_date_pattern = False
                    date_start_idx = None
                    for i, part in enumerate(market_parts):
                        # Check if this part looks like a year (4 digits starting with 20xx)
                        if len(part) == 4 and part.isdigit() and part.startswith('20'):
                            # Check if next parts form MM-DD pattern
                            if i + 2 < len(market_parts):
                                month_part = market_parts[i + 1]
                                day_part = market_parts[i + 2]
                                if month_part.isdigit() and day_part.isdigit() and len(month_part) <= 2 and len(day_part) <= 2:
                                    has_date_pattern = True
                                    date_start_idx = i
                                    break
                    
                    # Look for market-specific suffixes (spread, total, etc.)
                    market_types = ['spread', 'total', 'moneyline', 'over', 'under', 'home', 'away']
                    for i, part in enumerate(market_parts):
                        if part in market_types:
                            # Found market type, event_slug is everything before it
                            fallback_event_slug = '-'.join(market_parts[:i])
                            logger.info(f"[URL] Extracted event_slug from market_slug (Priority 5, sports, found market type): {fallback_event_slug} from {market_slug_clean} (condition_id={condition_id[:20]}...)")
                            break
                    
                    # If no market type found and we have a date pattern, don't split the date
                    # For simple markets like "nba-por-dal-2025-11-16", use the full slug as-is
                    if not fallback_event_slug and has_date_pattern:
                        # This is a simple market with date, don't extract event_slug - use full market_slug
                        fallback_event_slug = None  # Don't extract, will use full market_slug later
                        logger.info(f"[URL] Simple sports market with date pattern detected: {market_slug_clean}, will use full slug (condition_id={condition_id[:20]}...)")
                    elif not fallback_event_slug and len(market_parts) > 4:
                        # Only try to remove country/team codes if we don't have a date pattern
                        # Check if last part looks like a country/team code (2-4 chars, lowercase, not a number)
                        last_part = market_parts[-1]
                        if len(last_part) <= 4 and last_part.isalpha() and last_part.islower() and not last_part.isdigit():
                            # Likely a country/team code, but only remove if it's not part of a date
                            # Check if previous part is not a year
                            prev_part = market_parts[-2] if len(market_parts) > 1 else None
                            if not (prev_part and len(prev_part) == 4 and prev_part.isdigit() and prev_part.startswith('20')):
                                # Not part of date, safe to remove
                                fallback_event_slug = '-'.join(market_parts[:-1])
                                logger.info(f"[URL] Extracted event_slug from market_slug (Priority 5, sports, removed country code): {fallback_event_slug} from {market_slug_clean} (condition_id={condition_id[:20]}...)")
                
                # Use event_slug/market_slug format if event_slug is available
                if fallback_event_slug:
                    fallback_event_slug_clean = fallback_event_slug.strip().strip('/')
                    # Remove event_slug prefix from market_slug if it's already there
                    if market_slug_clean.startswith(fallback_event_slug_clean + '/'):
                        market_url = f"https://polymarket.com/event/{market_slug_clean}"
                        logger.info(f"[URL] Priority 5: market_slug already contains event_slug, using as-is: {market_slug_clean} (condition_id={condition_id[:20]}...)")
                    elif market_slug_clean.startswith(fallback_event_slug_clean + '-'):
                        # Market slug starts with event slug followed by dash, extract suffix
                        market_suffix = market_slug_clean[len(fallback_event_slug_clean) + 1:]
                        market_url = f"https://polymarket.com/event/{fallback_event_slug_clean}/{market_suffix}"
                        logger.info(f"[URL] Priority 5: Using event_slug/market_suffix format: event={fallback_event_slug_clean}, suffix={market_suffix} (condition_id={condition_id[:20]}...)")
                    elif market_slug_clean == fallback_event_slug_clean:
                        # If market_slug equals event_slug, still use event_slug/market_slug format
                        market_url = f"https://polymarket.com/event/{fallback_event_slug_clean}/{market_slug_clean}"
                        logger.info(f"[URL] Priority 5: market_slug equals event_slug, using event_slug/market_slug format: {fallback_event_slug_clean}/{market_slug_clean} (condition_id={condition_id[:20]}...)")
                    elif market_slug_clean.startswith(fallback_event_slug_clean):
                        # Market slug starts with event slug (no separator), use full market_slug
                        market_url = f"https://polymarket.com/event/{fallback_event_slug_clean}/{market_slug_clean}"
                        logger.info(f"[URL] Priority 5: Using event_slug/market_slug format: event={fallback_event_slug_clean}, market_slug={market_slug_clean} (condition_id={condition_id[:20]}...)")
                    else:
                        # Combine event_slug and market_slug
                        market_url = f"https://polymarket.com/event/{fallback_event_slug_clean}/{market_slug_clean}"
                        logger.info(f"[URL] Priority 5: Using event_slug/market_slug format: event={fallback_event_slug_clean}, market_slug={market_slug_clean} (condition_id={condition_id[:20]}...)")
                else:
                    # No event_slug available - for simple markets with date pattern, use full slug without splitting
                    # For markets like "nba-por-dal-2025-11-16", use the full slug as-is
                    market_url = f"https://polymarket.com/event/{market_slug_clean}"
                    logger.info(f"[URL] Priority 5: No event_slug found, using full market_slug: {market_slug_clean} (condition_id={condition_id[:20]}...)")
            else:
                # Priority 6: Search URL fallback
                market_url = self._get_search_url_fallback(condition_id)
                logger.info(f"[URL] Fallback: search URL (condition_id={condition_id[:20]}...)")
        
        # Final logging
        logger.info(f"[URL] Final market URL for condition={condition_id[:20]}...: {market_url}")
        
        # Format wallets list
        wallets_list = []
        for i, wallet in enumerate(wallets[:10], 1):  # Limit to 10 wallets
            wallet_short = f"{wallet[:6]}...{wallet[-4:]}" if len(wallet) > 10 else wallet
            entry_price = wallet_prices.get(wallet, 0)
            wallets_list.append(f"{i}. `{wallet_short}` @ ${entry_price:.3f}")
        
        if len(wallets) > 10:
            wallets_list.append(f"... и еще {len(wallets) - 10} кошельков")
        
        # Format reason description
        reason_descriptions = {
            "market_closed": "🚫 Рынок закрыт",
            "resolved": "✅ Рынок разрешен",
            "price_high": "💰 Цена слишком высокая/низкая (>= $0.98 или <= $0.02)",
            "price_none": "❓ Цена недоступна",
            "price_check_error": "⚠️ Ошибка проверки цены",
            "ignore_30m_same_outcome": "⏰ Игнор 30 минут (тот же outcome)",
            "dedupe_no_growth_10m": "🔁 Дубликат (10 минут, нет роста)",
            "no_trigger_matched": "❌ Нет триггеров для публикации",
            "opposite_recent": "🔄 Конфликт с противоположной стороной"
        }
        reason_desc = reason_descriptions.get(reason, f"❓ {reason}")
        
        # Format price info
        price_info = ""
        if current_price is not None:
            price_info = f"Current price: ${current_price:.3f}\n"
        
        # Format total position
        position_info = ""
        if total_usd is not None and total_usd > 0:
            position_info = f"Total position: {total_usd:,.0f} USDC💰\n"
        
        # Build message
        message = f"""🚫 *Alert Suppressed: {reason_desc}*

🎯 *Market:* {market_title or condition_id[:20] + '...'}
📊 *Outcome:* {outcome_index} ({side})
{price_info}{position_info}
👤 *Wallets:* {len(wallets)}
{chr(10).join(wallets_list)}

🔗 [View Market]({market_url})
📋 Condition ID: `{condition_id}`

_{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC_"""
        
        return self.send_message(message, chat_id=self.reports_chat_id, parse_mode="Markdown")
    
    def send_wallet_collection_summary(self, total_found: int, filtered_count: int, 
                                     criteria: Dict[str, Any]) -> bool:
        """Send summary of wallet collection process to reports channel"""
        
        # Get criteria values
        min_trades = criteria.get('min_trades', 6)
        min_win_rate = criteria.get('min_win_rate', 0.65)
        max_daily_freq = criteria.get('max_daily_freq', 35.0)
        
        # Build message
        message = f"""📈 *Wallet Collection Complete*

📊 *Collection Results:*
• Wallets found: {total_found}
• Wallets meeting criteria: {filtered_count}
• Min trades: {min_trades}
• Min win rate: {min_win_rate:.1%}
• Max daily frequency: {max_daily_freq}"""
        
        # Add rejection breakdown if analytics_stats available
        analytics_stats = criteria.get('analytics_stats')
        if analytics_stats:
            rejected_total = (
                analytics_stats.get('below_trades', 0) +
                analytics_stats.get('below_winrate', 0) +
                analytics_stats.get('above_freq', 0) +
                analytics_stats.get('missing_stats', 0)
            )
            
            if rejected_total > 0:
                message += f"""

❌ *Rejected:*
• Low trades: {analytics_stats.get('below_trades', 0)}
• Low win rate: {analytics_stats.get('below_winrate', 0)}
• High daily frequency: {analytics_stats.get('above_freq', 0)}
• Missing stats: {analytics_stats.get('missing_stats', 0)}"""
        
        message += f"\n\n_{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC_"
        
        return self.send_message(message, chat_id=self.reports_chat_id)
    
    def _normalize_condition_id(self, condition_id: str) -> str:
        """Normalize condition_id for comparison (remove 0x prefix, lowercase)"""
        if not condition_id:
            return ""
        # Remove 0x prefix if present
        normalized = condition_id.lower().strip()
        if normalized.startswith('0x'):
            normalized = normalized[2:]
        return normalized
    
    def _clean_slug(self, raw_slug: str, strip_market_prefix: bool = False, remove_outcome_words: bool = False) -> str:
        """
        Universal slug cleaning and normalization function.
        Handles slugs from Gamma, CLOB, Data API, and raw events.
        
        Args:
            raw_slug: The raw slug string to clean (can be from any source)
            strip_market_prefix: If True, also strip 'market/' prefix (default: False, only strips 'event/')
            remove_outcome_words: If True, remove trailing outcome-specific words like 'yes', 'no', 'over', 'under' (default: False)
        
        Returns:
            str: Cleaned and normalized slug string
        
        This function:
        - Removes domain prefixes (polymarket.com/)
        - Strips 'event/' and optionally 'market/' prefixes
        - Normalizes whitespace and slashes
        - Optionally removes outcome-specific words
        - Normalizes repeated dashes
        - Trims trailing/leading dashes
        """
        if not raw_slug:
            return ""
        
        import re
        
        # Convert to string and strip whitespace/slashes
        cleaned = str(raw_slug).strip().strip('/')
        
        # Remove polymarket.com/ prefix (handles full URLs)
        if 'polymarket.com' in cleaned:
            # Extract path after domain
            parts = cleaned.split('polymarket.com/')
            if len(parts) > 1:
                cleaned = parts[-1].strip('/')
            else:
                # If no path after domain, try to extract from URL structure
                cleaned = cleaned.split('polymarket.com')[-1].strip('/')
        
        # Strip event/ prefix (common in Gamma/CLOB responses)
        if cleaned.startswith('event/'):
            cleaned = cleaned[6:]
        
        # Optionally strip market/ prefix
        if strip_market_prefix and cleaned.startswith('market/'):
            cleaned = cleaned[7:]
        
        # Optionally remove trailing outcome-specific words (yes, no, over, under)
        # This helps normalize market-specific slugs that include outcome indicators
        if remove_outcome_words:
            outcome_pattern = r'-(yes|no|over|under)$'
            cleaned = re.sub(outcome_pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Normalize repeated dashes (e.g., "slug---name" -> "slug-name")
        cleaned = re.sub(r'-+', '-', cleaned)
        
        # Trim trailing and leading dashes
        cleaned = cleaned.strip('-')
        
        return cleaned
    
    def _is_market_specific_slug(self, slug: str) -> bool:
        """
        Detect if a slug is market-specific (contains dates, prices, or specific question patterns)
        rather than a parent event slug.
        
        Returns:
            bool: True if slug appears to be market-specific, False if it's likely a parent event slug
        """
        if not slug:
            return False
        
        import re
        
        # Check for specific dates: YYYY-MM-DD pattern
        if re.search(r'\d{4}-\d{2}-\d{2}', slug):
            return True
        
        # Check for month names with years (e.g., "november-2025", "nov-2025")
        month_pattern = r'(january|february|march|april|may|june|july|august|september|october|november|december)-\d{4}'
        if re.search(month_pattern, slug, re.IGNORECASE):
            return True
        
        month_abbr_pattern = r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)-\d{4}'
        if re.search(month_abbr_pattern, slug, re.IGNORECASE):
            return True
        
        # Check for specific prices/numbers: $X,XXX or 4+ consecutive digits
        if re.search(r'\$?\d{1,3}(,\d{3})+', slug):
            return True
        
        # Check for trailing year pattern (e.g., "event-name-2024") - exempt from market-specific classification
        # This should be checked BEFORE the broader 4+ digit pattern
        if re.search(r'-\d{4}$', slug):
            # This is likely a year suffix, not a market-specific identifier
            # Continue to other checks but don't classify as market-specific based on digits alone
            pass
        # Check for 4+ consecutive digits (likely prices or specific numbers)
        # Only apply if NOT a trailing year pattern
        elif re.search(r'\d{4,}', slug):
            return True
        
        # Check for question patterns: "will-X-do-Y-on-DATE", "will-X-reach-Y-by-DATE"
        if re.search(r'^will-.*-(on|by|in|before|after)-', slug, re.IGNORECASE):
            return True
        
        # Check slug length > 60 characters (very specific questions)
        if len(slug) > 60:
            return True
        
        # Check for outcome-specific words at end: "yes", "no", "over", "under"
        outcome_pattern = r'-(yes|no|over|under)$'
        if re.search(outcome_pattern, slug, re.IGNORECASE):
            return True
        
        return False
    
    def _get_event_slug_and_market_id(self, condition_id: str) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[Dict[str, Any]]]:
        """
        Get canonical event slug, market ID, market slug, and full canonical event object from Gamma API.
        Uses /events/{event_id} to get the canonical event (not market-specific).
        For complex markets (tweets, elections, etc.), returns event_slug, market_id (tid), and market_slug.
        For sports markets, returns event_slug and None for market_id.
        
        Returns:
            Tuple[Optional[str], Optional[int], Optional[str], Optional[Dict]]: (canonical_event_slug, market_id, market_slug, canonical_event_object) if found, (None, None, None, None) otherwise
        """
        try:
            from gamma_client import get_event_by_condition_id, get_event_by_id
            from enhanced_market_data import get_market_data_from_graphql
            
            # Step 1: Get initial event (may be market-specific)
            # Try GraphQL API first as it's more reliable
            initial_event = None
            try:
                graphql_data = get_market_data_from_graphql(condition_id)
                if graphql_data:
                    # Convert GraphQL response to event format
                    event_data = graphql_data.get("event")
                    if event_data:
                        initial_event = {
                            "id": event_data.get("id"),
                            "slug": event_data.get("slug"),
                            "title": event_data.get("title"),
                            "category": event_data.get("category"),
                            "tags": event_data.get("tags"),
                            "markets": event_data.get("markets", [])
                        }
                        logger.info(f"[EVENT_SLUG] Got initial event from GraphQL API for condition={condition_id[:20]}...")
            except Exception as e:
                logger.debug(f"[EVENT_SLUG] GraphQL API failed, falling back to REST API: {e}")
            
            # Fallback to REST API if GraphQL didn't work
            if not initial_event:
                initial_event = get_event_by_condition_id(condition_id)
            
            if not initial_event:
                logger.warning(f"[EVENT_SLUG] Initial event not found for condition_id={condition_id[:20]}..., trying CLOB API fallback")
                # Fallback: Try to get event_slug and market_id from CLOB API
                try:
                    clob_url = f"https://clob.polymarket.com/markets/{condition_id}"
                    clob_response = self._make_authenticated_get(clob_url, timeout=5)
                    if clob_response and clob_response.status_code == 200:
                        clob_data = clob_response.json()
                        clob_market_id = clob_data.get('id') or clob_data.get('marketId') or clob_data.get('tid')
                        clob_event_slug = (clob_data.get('event_slug') or 
                                         clob_data.get('eventSlug') or
                                         clob_data.get('question_slug') or
                                         clob_data.get('slug'))
                        if clob_event_slug:
                            # Extract event slug from question_slug if it contains market-specific part
                            if '/' in clob_event_slug:
                                clob_event_slug = clob_event_slug.split('/')[0]
                            # Normalize using shared cleaning logic
                            clob_event_slug = self._clean_slug(clob_event_slug)
                            
                            # Validate slug - check if it's market-specific
                            if clob_event_slug and self._is_market_specific_slug(clob_event_slug):
                                # Market-specific slug detected, need to search for parent slug using CLOB/Data fallback
                                logger.warning(f"[EVENT_SLUG] [VALIDATION] ⚠️ CLOB fallback returned market-specific slug: {clob_event_slug}, searching for parent slug")
                                
                                # Try CLOB API for parent event_slug field
                                clob_parent_slug = None
                                try:
                                    clob_parent_slug = (clob_data.get('event_slug') or clob_data.get('eventSlug'))
                                    if clob_parent_slug:
                                        clob_parent_slug = self._clean_slug(clob_parent_slug)
                                        if clob_parent_slug != clob_event_slug and not self._is_market_specific_slug(clob_parent_slug):
                                            clob_event_slug = clob_parent_slug
                                            logger.info(f"[EVENT_SLUG] [CLOB_FALLBACK] ✅ Found parent event slug from CLOB API: {clob_event_slug}")
                                        else:
                                            clob_parent_slug = None
                                except Exception:
                                    pass
                                
                                # If CLOB didn't provide valid parent slug, try Data API
                                if not clob_parent_slug or self._is_market_specific_slug(clob_event_slug):
                                    try:
                                        data_api_url = f"https://data-api.polymarket.com/condition/{condition_id}"
                                        data_api_response = self._make_authenticated_get(data_api_url, timeout=5)
                                        if data_api_response and data_api_response.status_code == 200:
                                            data_api_data = data_api_response.json()
                                            data_api_event_slug = (data_api_data.get('event_slug') or data_api_data.get('eventSlug'))
                                            if data_api_event_slug:
                                                data_api_event_slug = self._clean_slug(data_api_event_slug)
                                                if data_api_event_slug != clob_event_slug and not self._is_market_specific_slug(data_api_event_slug):
                                                    clob_event_slug = data_api_event_slug
                                                    logger.info(f"[EVENT_SLUG] [DATA_API_FALLBACK] ✅ Found parent event slug from Data API: {clob_event_slug}")
                                    except Exception as e:
                                        logger.debug(f"[EVENT_SLUG] Failed to get parent event slug from Data API: {e}")
                                
                                # If still market-specific, try heuristic extraction
                                if self._is_market_specific_slug(clob_event_slug):
                                    import re
                                    extracted_slug = clob_event_slug
                                    
                                    # Remove date patterns (YYYY-MM-DD, month-year)
                                    extracted_slug = re.sub(r'\d{4}-\d{2}-\d{2}', '', extracted_slug)
                                    extracted_slug = re.sub(r'(january|february|march|april|may|june|july|august|september|october|november|december)-\d{4}', '', extracted_slug, flags=re.IGNORECASE)
                                    extracted_slug = re.sub(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)-\d{4}', '', extracted_slug, flags=re.IGNORECASE)
                                    
                                    # Remove price patterns ($X,XXX, numbers)
                                    extracted_slug = re.sub(r'\$?\d{1,3}(,\d{3})+', '', extracted_slug)
                                    extracted_slug = re.sub(r'\d{4,}', '', extracted_slug)
                                    
                                    # Remove trailing outcome words (yes, no, over, under)
                                    extracted_slug = re.sub(r'-(yes|no|over|under)$', '', extracted_slug, flags=re.IGNORECASE)
                                    
                                    # Clean up multiple consecutive dashes and trailing/leading dashes
                                    extracted_slug = re.sub(r'-+', '-', extracted_slug)
                                    extracted_slug = extracted_slug.strip('-')
                                    
                                    # Truncate to first 50 characters if > 60 characters
                                    if len(extracted_slug) > 60:
                                        extracted_slug = extracted_slug[:50].rstrip('-')
                                    
                                    if extracted_slug and extracted_slug != clob_event_slug:
                                        logger.info(f"[EVENT_SLUG] [HEURISTIC] Extracted potential parent slug: {extracted_slug}")
                                        clob_event_slug = extracted_slug
                            
                            # Only return if we have a non-empty slug that's not market-specific
                            if clob_event_slug and not self._is_market_specific_slug(clob_event_slug):
                                if clob_market_id:
                                    try:
                                        market_id = int(clob_market_id)
                                    except (ValueError, TypeError):
                                        market_id = None
                                logger.info(f"[EVENT_SLUG] Got event_slug={clob_event_slug}, market_id={market_id} from CLOB API fallback for condition={condition_id[:20]}...")
                                return clob_event_slug, market_id, None, None
                        
                        # Extract market_id if we have it
                        if clob_market_id:
                            try:
                                market_id = int(clob_market_id)
                            except (ValueError, TypeError):
                                market_id = None
                        
                        # If we have market_id but no valid slug, return what we have
                        if market_id:
                            logger.info(f"[EVENT_SLUG] Got market_id={market_id} from CLOB API fallback, but no valid slug")
                            return None, market_id, None, None
                except Exception as e:
                    logger.debug(f"[EVENT_SLUG] Failed to get event_slug/market_id from CLOB API fallback: {e}")
                return None, None, None, None
            
            # Step 2: Extract event_id from initial event
            # Prioritize eventId/event_id over id to detect grouped markets
            # Grouped markets have eventId pointing to parent, while id is market-specific
            market_id_from_event = initial_event.get("id")
            parent_event_id = (initial_event.get("eventId") or 
                              initial_event.get("event_id"))
            
            # Detect grouped markets: if eventId exists and differs from id, it's a grouped market
            is_grouped_market = False
            if parent_event_id and market_id_from_event and parent_event_id != market_id_from_event:
                is_grouped_market = True
                logger.info(f"[EVENT_SLUG] [GROUPED_MARKET] Detected grouped market: market_id={market_id_from_event}, parent_event_id={parent_event_id}")
            
            # Extract market slug from initial event before fetching parent
            initial_market_slug = (initial_event.get("slug") or 
                                 initial_event.get("eventSlug") or 
                                 initial_event.get("event_slug") or
                                 initial_event.get("questionSlug"))
            if initial_market_slug:
                # Clean the slug (remove prefixes, normalize)
                initial_market_slug = self._clean_slug(initial_market_slug, strip_market_prefix=True)
            
            # Determine which event_id to use for fetching canonical/parent event
            event_id = parent_event_id if is_grouped_market else (parent_event_id or market_id_from_event)
            
            if not event_id:
                logger.warning(f"[EVENT_SLUG] No event_id found in initial event for condition={condition_id[:20]}..., using initial event as fallback")
                # Fallback: use initial event (may not be canonical, but better than nothing)
                canonical_event = initial_event
            else:
                # Step 3: Get canonical/parent event by event_id
                if is_grouped_market:
                    logger.info(f"[EVENT_SLUG] [GROUPED_MARKET] Fetching parent event by id={event_id}")
                else:
                    logger.info(f"[EVENT_SLUG] Fetching canonical event by id={event_id} for condition={condition_id[:20]}...")
                canonical_event = get_event_by_id(event_id)
                
                if not canonical_event:
                    logger.warning(f"[EVENT_SLUG] Failed to get canonical event by id={event_id}, falling back to initial event")
                    canonical_event = initial_event
            
            # Step 4: Get canonical event slug
            canonical_event_slug = (canonical_event.get("slug") or 
                                   canonical_event.get("eventSlug") or 
                                   canonical_event.get("event_slug") or
                                   canonical_event.get("questionSlug"))
            
            # Step 4.5: Validate canonical_event_slug - detect market-specific slugs
            needs_parent_slug_lookup = False
            if canonical_event_slug:
                canonical_event_slug = self._clean_slug(canonical_event_slug)
                
                # Check if slug is market-specific
                if self._is_market_specific_slug(canonical_event_slug):
                    logger.warning(f"[EVENT_SLUG] [VALIDATION] ⚠️ Detected market-specific slug: {canonical_event_slug}, will try to get parent event slug from CLOB/Data API")
                    needs_parent_slug_lookup = True
                else:
                    logger.debug(f"[EVENT_SLUG] [VALIDATION] Slug validation passed: {canonical_event_slug}")
            
            # Step 5: Normalize condition_id for comparison
            normalized_condition_id = self._normalize_condition_id(condition_id)
            
            # Step 6: Find market matching condition_id in canonical event's markets
            markets = canonical_event.get("markets", [])
            market_id = None
            market_slug = None
            matching_market = None
            
            # Try multiple ways to match condition_id
            for market in markets:
                # Try different field names for condition_id
                market_condition_id_candidates = [
                    market.get("conditionId"),
                    market.get("condition_id"),
                    market.get("conditionIdHex"),
                    market.get("condition_id_hex"),
                ]
                
                # Also try token_id format (condition_id:outcome_index)
                token_id = market.get("tokenId") or market.get("token_id")
                if token_id and isinstance(token_id, str) and ':' in token_id:
                    token_condition_id = token_id.split(':')[0]
                    market_condition_id_candidates.append(token_condition_id)
                
                # Compare normalized versions
                for candidate in market_condition_id_candidates:
                    if not candidate:
                        continue
                    candidate_normalized = self._normalize_condition_id(str(candidate))
                    if candidate_normalized == normalized_condition_id:
                        matching_market = market
                        # Get market ID (tid) - try different field names
                        # Note: Gamma API may use different field names for market ID
                        market_id = (market.get("id") or 
                                    market.get("marketId") or 
                                    market.get("market_id") or
                                    market.get("tid") or
                                    market.get("marketIdNum") or
                                    market.get("tokenId") or  # Sometimes tokenId contains market ID
                                    market.get("token_id"))
                        
                        # If tokenId is in format "condition_id:outcome_index", extract just the condition_id part
                        if market_id and isinstance(market_id, str) and ':' in str(market_id):
                            # Try to extract numeric ID from tokenId or use it as-is if it's already numeric
                            try:
                                # If tokenId format, try to get actual market ID from elsewhere
                                market_id = market.get("id") or market.get("marketId") or market.get("tid")
                            except:
                                pass
                        
                        if market_id is not None:
                            try:
                                # Try to convert to int, but handle string IDs too
                                if isinstance(market_id, str):
                                    # If it's a string, try to extract numeric part
                                    import re
                                    numeric_match = re.search(r'\d+', str(market_id))
                                    if numeric_match:
                                        market_id = int(numeric_match.group())
                                    else:
                                        market_id = None
                                else:
                                    market_id = int(market_id)
                            except (ValueError, TypeError):
                                market_id = None
                        
                        # Log what we found for debugging
                        if market_id:
                            logger.info(f"[EVENT_SLUG] Found market_id={market_id} for condition={condition_id[:20]}... (from field: {[k for k, v in market.items() if v == market_id][0] if market_id else 'unknown'})")
                        else:
                            logger.warning(f"[EVENT_SLUG] No market_id found in Gamma API for condition={condition_id[:20]}... Available fields: {list(market.keys())[:15]}")
                            # Fallback 1: Try to get market_id from CLOB API
                            try:
                                clob_url = f"https://clob.polymarket.com/markets/{condition_id}"
                                clob_response = self._make_authenticated_get(clob_url, timeout=5)
                                if clob_response and clob_response.status_code == 200:
                                    clob_data = clob_response.json()
                                    # Try multiple field names for market ID
                                    clob_market_id = (clob_data.get('id') or 
                                                    clob_data.get('marketId') or 
                                                    clob_data.get('tid') or
                                                    clob_data.get('market_id') or
                                                    clob_data.get('marketIdNum'))
                                    if clob_market_id:
                                        try:
                                            # Handle string IDs with numeric extraction
                                            if isinstance(clob_market_id, str):
                                                import re
                                                numeric_match = re.search(r'\d+', str(clob_market_id))
                                                if numeric_match:
                                                    market_id = int(numeric_match.group())
                                                else:
                                                    market_id = None
                                            else:
                                                market_id = int(clob_market_id)
                                            if market_id:
                                                logger.info(f"[EVENT_SLUG] ✅ Got market_id={market_id} from CLOB API fallback for condition={condition_id[:20]}...")
                                        except (ValueError, TypeError) as e:
                                            logger.debug(f"[EVENT_SLUG] Failed to parse market_id from CLOB API: {clob_market_id}, error: {e}")
                            except Exception as e:
                                logger.debug(f"[EVENT_SLUG] Failed to get market_id from CLOB API: {e}")
                            
                            # Fallback 2: Try to get market_id from Data API
                            if not market_id:
                                try:
                                    data_api_url = f"https://data-api.polymarket.com/condition/{condition_id}"
                                    data_api_response = self._make_authenticated_get(data_api_url, timeout=5)
                                    if data_api_response and data_api_response.status_code == 200:
                                        data_api_data = data_api_response.json()
                                        # Try multiple field names for market ID
                                        data_api_market_id = (data_api_data.get('id') or 
                                                            data_api_data.get('marketId') or 
                                                            data_api_data.get('tid') or
                                                            data_api_data.get('market_id') or
                                                            data_api_data.get('marketIdNum'))
                                        if data_api_market_id:
                                            try:
                                                # Handle string IDs with numeric extraction
                                                if isinstance(data_api_market_id, str):
                                                    import re
                                                    numeric_match = re.search(r'\d+', str(data_api_market_id))
                                                    if numeric_match:
                                                        market_id = int(numeric_match.group())
                                                    else:
                                                        market_id = None
                                                else:
                                                    market_id = int(data_api_market_id)
                                                if market_id:
                                                    logger.info(f"[EVENT_SLUG] ✅ Got market_id={market_id} from Data API fallback for condition={condition_id[:20]}...")
                                            except (ValueError, TypeError) as e:
                                                logger.debug(f"[EVENT_SLUG] Failed to parse market_id from Data API: {data_api_market_id}, error: {e}")
                                except Exception as e:
                                    logger.debug(f"[EVENT_SLUG] Failed to get market_id from Data API: {e}")
                        
                        # Get market slug - try different field names
                        market_slug = (market.get("slug") or 
                                      market.get("marketSlug") or 
                                      market.get("market_slug") or
                                      market.get("questionSlug") or
                                      market.get("question_slug"))
                        if market_slug:
                            # Clean market slug
                            market_slug = self._clean_slug(market_slug, strip_market_prefix=True)
                            
                            # Compare event slug with market slug - if identical, it's likely wrong
                            if canonical_event_slug and market_slug == canonical_event_slug:
                                logger.warning(f"[EVENT_SLUG] [VALIDATION] ⚠️ Event slug equals market slug, likely market-specific event returned by Gamma API")
                                needs_parent_slug_lookup = True
                            
                            # If market_slug is the same as event_slug, try to get more specific slug from CLOB/data-api
                            if canonical_event_slug and market_slug == canonical_event_slug:
                                logger.debug(f"[EVENT_SLUG] Market slug equals event slug, trying to get more specific slug from CLOB/data-api")
                                # Try to get market slug from CLOB API
                                try:
                                    clob_url = f"https://clob.polymarket.com/markets/{condition_id}"
                                    clob_response = self._make_authenticated_get(clob_url, timeout=5)
                                    if clob_response and clob_response.status_code == 200:
                                        clob_data = clob_response.json()
                                        clob_market_slug = (clob_data.get('question_slug') or 
                                                          clob_data.get('market_slug') or 
                                                          clob_data.get('slug'))
                                        if clob_market_slug and clob_market_slug != canonical_event_slug:
                                            market_slug = self._clean_slug(clob_market_slug)
                                            logger.info(f"[EVENT_SLUG] Got more specific market slug from CLOB API: {market_slug}")
                                except Exception as e:
                                    logger.debug(f"[EVENT_SLUG] Failed to get market slug from CLOB API: {e}")
                        break
                
                if matching_market:
                    break
            
            # Step 7: Fallback to initial event's market if not found in canonical event
            if not matching_market:
                logger.warning(f"[EVENT_SLUG] Market not found in canonical event for condition={condition_id[:20]}... (event has {len(markets)} markets)")
                # Fallback: try to use initial event's market
                initial_markets = initial_event.get("markets", [])
                for market in initial_markets:
                    market_condition_id_candidates = [
                        market.get("conditionId"),
                        market.get("condition_id"),
                        market.get("conditionIdHex"),
                        market.get("condition_id_hex"),
                    ]
                    token_id = market.get("tokenId") or market.get("token_id")
                    if token_id and isinstance(token_id, str) and ':' in token_id:
                        token_condition_id = token_id.split(':')[0]
                        market_condition_id_candidates.append(token_condition_id)
                    
                    for candidate in market_condition_id_candidates:
                        if not candidate:
                            continue
                        candidate_normalized = self._normalize_condition_id(str(candidate))
                        if candidate_normalized == normalized_condition_id:
                            matching_market = market
                            # Get market ID (tid) - try different field names
                            # Note: Gamma API may use different field names for market ID
                            market_id = (market.get("id") or 
                                        market.get("marketId") or 
                                        market.get("market_id") or
                                        market.get("tid") or
                                        market.get("marketIdNum") or
                                        market.get("tokenId") or  # Sometimes tokenId contains market ID
                                        market.get("token_id"))
                            
                            # If tokenId is in format "condition_id:outcome_index", extract just the condition_id part
                            if market_id and isinstance(market_id, str) and ':' in str(market_id):
                                # Try to extract numeric ID from tokenId or use it as-is if it's already numeric
                                try:
                                    # If tokenId format, try to get actual market ID from elsewhere
                                    market_id = market.get("id") or market.get("marketId") or market.get("tid")
                                except:
                                    pass
                            
                            if market_id is not None:
                                try:
                                    # Try to convert to int, but handle string IDs too
                                    if isinstance(market_id, str):
                                        # If it's a string, try to extract numeric part
                                        import re
                                        numeric_match = re.search(r'\d+', str(market_id))
                                        if numeric_match:
                                            market_id = int(numeric_match.group())
                                        else:
                                            market_id = None
                                    else:
                                        market_id = int(market_id)
                                except (ValueError, TypeError):
                                    market_id = None
                            
                            # If still no market_id, try CLOB API fallback
                            if not market_id:
                                try:
                                    clob_url = f"https://clob.polymarket.com/markets/{condition_id}"
                                    clob_response = self._make_authenticated_get(clob_url, timeout=5)
                                    if clob_response and clob_response.status_code == 200:
                                        clob_data = clob_response.json()
                                        clob_market_id = clob_data.get('id') or clob_data.get('marketId') or clob_data.get('tid')
                                        if clob_market_id:
                                            try:
                                                market_id = int(clob_market_id)
                                                logger.info(f"[EVENT_SLUG] Got market_id={market_id} from CLOB API fallback (initial event) for condition={condition_id[:20]}...")
                                            except (ValueError, TypeError):
                                                pass
                                except Exception as e:
                                    logger.debug(f"[EVENT_SLUG] Failed to get market_id from CLOB API (initial event): {e}")
                            
                            # Get market slug from initial event market
                            market_slug = (market.get("slug") or 
                                          market.get("marketSlug") or 
                                          market.get("market_slug") or
                                          market.get("questionSlug") or
                                          market.get("question_slug"))
                            if market_slug:
                                market_slug = self._clean_slug(market_slug, strip_market_prefix=True)
                                
                                # If market_slug is the same as event_slug, try to get more specific slug from CLOB/data-api
                                if canonical_event_slug and market_slug == canonical_event_slug:
                                    logger.debug(f"[EVENT_SLUG] Market slug equals event slug (initial event), trying to get more specific slug from CLOB/data-api")
                                    # Try to get market slug from CLOB API
                                    try:
                                        clob_url = f"https://clob.polymarket.com/markets/{condition_id}"
                                        clob_response = self._make_authenticated_get(clob_url, timeout=5)
                                        if clob_response and clob_response.status_code == 200:
                                            clob_data = clob_response.json()
                                            clob_market_slug = (clob_data.get('question_slug') or 
                                                              clob_data.get('market_slug') or 
                                                              clob_data.get('slug'))
                                            if clob_market_slug and clob_market_slug != canonical_event_slug:
                                                market_slug = self._clean_slug(clob_market_slug)
                                                logger.info(f"[EVENT_SLUG] Got more specific market slug from CLOB API (initial event): {market_slug}")
                                    except Exception as e:
                                        logger.debug(f"[EVENT_SLUG] Failed to get market slug from CLOB API (initial event): {e}")
                            break
                    if matching_market:
                        break
            
            # Step 8: Set market_slug for grouped markets
            # For grouped markets, use the initial event's slug as market_slug (market-specific question)
            if is_grouped_market and initial_market_slug:
                if not market_slug:
                    market_slug = initial_market_slug
                logger.info(f"[EVENT_SLUG] [GROUPED_MARKET] Using initial event slug as market_slug: {market_slug}")
            
            # Step 8.5: Enhanced CLOB/Data API fallback for market-specific slugs
            if needs_parent_slug_lookup and canonical_event_slug:
                # Try CLOB API fallback first
                try:
                    clob_url = f"https://clob.polymarket.com/markets/{condition_id}"
                    clob_response = self._make_authenticated_get(clob_url, timeout=5)
                    if clob_response and clob_response.status_code == 200:
                        clob_data = clob_response.json()
                        # Extract event_slug field (distinct from question_slug or market_slug)
                        clob_event_slug = (clob_data.get('event_slug') or 
                                         clob_data.get('eventSlug'))
                        
                        if clob_event_slug:
                            # Clean CLOB event slug
                            clob_event_slug = self._clean_slug(clob_event_slug)
                            
                            # Validate it's NOT market-specific
                            if clob_event_slug != canonical_event_slug and not self._is_market_specific_slug(clob_event_slug):
                                canonical_event_slug = clob_event_slug
                                logger.info(f"[EVENT_SLUG] [CLOB_FALLBACK] ✅ Replaced market-specific slug with parent event slug from CLOB API: {canonical_event_slug}")
                                needs_parent_slug_lookup = False
                except Exception as e:
                    logger.debug(f"[EVENT_SLUG] [CLOB_FALLBACK] Failed to get parent event slug from CLOB API: {e}")
                
                # If CLOB fallback didn't find valid parent slug, try Data API
                if needs_parent_slug_lookup:
                    try:
                        data_api_url = f"https://data-api.polymarket.com/condition/{condition_id}"
                        data_api_response = self._make_authenticated_get(data_api_url, timeout=5)
                        if data_api_response and data_api_response.status_code == 200:
                            data_api_data = data_api_response.json()
                            # Extract event_slug or eventSlug field
                            data_api_event_slug = (data_api_data.get('event_slug') or 
                                                 data_api_data.get('eventSlug'))
                            
                            if data_api_event_slug:
                                # Clean Data API event slug
                                data_api_event_slug = self._clean_slug(data_api_event_slug)
                                
                                # Validate it's NOT market-specific
                                if data_api_event_slug != canonical_event_slug and not self._is_market_specific_slug(data_api_event_slug):
                                    canonical_event_slug = data_api_event_slug
                                    logger.info(f"[EVENT_SLUG] [DATA_API_FALLBACK] ✅ Replaced market-specific slug with parent event slug from Data API: {canonical_event_slug}")
                                    needs_parent_slug_lookup = False
                    except Exception as e:
                        logger.debug(f"[EVENT_SLUG] [DATA_API_FALLBACK] Failed to get parent event slug from Data API: {e}")
            
            # Step 9: Log results
            if matching_market and market_id:
                logger.info(f"[EVENT_SLUG] (complex) condition={condition_id[:20]}... canonical_event_slug={canonical_event_slug}, market_id={market_id}, market_slug={market_slug}")
            elif matching_market and not market_id:
                logger.warning(f"[EVENT_SLUG] Found market but no market_id for condition={condition_id[:20]}... (market fields: {list(matching_market.keys())[:10]})")
            
            # Step 10: Clean and return canonical event slug
            if canonical_event_slug:
                # Clean slug (handle sports/ prefix specially)
                if canonical_event_slug.startswith('sports/'):
                    # For sports, keep full path structure if available
                    # We'll use event object to get full URL later
                    pass
                else:
                    canonical_event_slug = self._clean_slug(canonical_event_slug)
                
                # Final validation: always check if slug is still market-specific after all fallbacks
                # This ensures any slug that passes through but still looks market-specific gets normalized
                if self._is_market_specific_slug(canonical_event_slug):
                    logger.error(f"[EVENT_SLUG] [VALIDATION] ❌ Failed to get parent event slug, still using market-specific slug: {canonical_event_slug}")
                    # Try to extract parent slug heuristically
                    import re
                    extracted_slug = canonical_event_slug
                    
                    # Remove date patterns (YYYY-MM-DD, month-year)
                    extracted_slug = re.sub(r'\d{4}-\d{2}-\d{2}', '', extracted_slug)
                    extracted_slug = re.sub(r'(january|february|march|april|may|june|july|august|september|october|november|december)-\d{4}', '', extracted_slug, flags=re.IGNORECASE)
                    extracted_slug = re.sub(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)-\d{4}', '', extracted_slug, flags=re.IGNORECASE)
                    
                    # Remove price patterns ($X,XXX, numbers)
                    extracted_slug = re.sub(r'\$?\d{1,3}(,\d{3})+', '', extracted_slug)
                    extracted_slug = re.sub(r'\d{4,}', '', extracted_slug)
                    
                    # Remove trailing outcome words (yes, no, over, under)
                    extracted_slug = re.sub(r'-(yes|no|over|under)$', '', extracted_slug, flags=re.IGNORECASE)
                    
                    # Clean up multiple consecutive dashes and trailing/leading dashes
                    extracted_slug = re.sub(r'-+', '-', extracted_slug)
                    extracted_slug = extracted_slug.strip('-')
                    
                    # Truncate to first 50 characters if > 60 characters
                    if len(extracted_slug) > 60:
                        extracted_slug = extracted_slug[:50].rstrip('-')
                    
                    if extracted_slug and extracted_slug != canonical_event_slug:
                        logger.info(f"[EVENT_SLUG] [HEURISTIC] Extracted potential parent slug: {extracted_slug}")
                        canonical_event_slug = extracted_slug
                
                if is_grouped_market:
                    logger.info(f"[EVENT_SLUG] [GROUPED_MARKET] Returning parent_event_slug={canonical_event_slug}, market_slug={market_slug}")
                else:
                    logger.info(f"[EVENT_SLUG] Got canonical event slug from Gamma API: {canonical_event_slug}, market_id={market_id}, market_slug={market_slug} (condition_id={condition_id[:20]}...)")
                return canonical_event_slug, market_id, market_slug, canonical_event
            
            # Fallback: Try to extract event slug from first market's slug (only if canonical slug not found)
            if markets and not canonical_event_slug:
                fallback_market_slug = markets[0].get("slug", "")
                if fallback_market_slug:
                    # For sports markets like "nfl-nyj-ne-2025-11-13-total-42pt5-697"
                    # Extract base event slug by removing market-specific suffixes
                    market_slug_clean = self._clean_slug(fallback_market_slug, strip_market_prefix=True)
                    
                    # Try to extract event slug by removing common market suffixes
                    import re
                    event_slug_match = re.match(r'^([^-]+(?:-[^-]+)*?)(?:-(?:total|spread|moneyline|ou|o\/u|over-under|h2h|head-to-head)-[^-]+(?:-[^-]+)*)?$', market_slug_clean)
                    if event_slug_match:
                        potential_event_slug = event_slug_match.group(1)
                        # Verify it looks like an event slug (has date pattern YYYY-MM-DD)
                        if re.search(r'\d{4}-\d{2}-\d{2}', potential_event_slug):
                            # Use market_slug from matching_market if available, otherwise use fallback
                            final_market_slug = market_slug if market_slug else market_slug_clean
                            logger.info(f"[EVENT_SLUG] Extracted event slug from market slug (fallback): {potential_event_slug}, market_id={market_id}, market_slug={final_market_slug} (condition_id={condition_id[:20]}...)")
                            return potential_event_slug, market_id, final_market_slug, canonical_event
                    
                    logger.debug(f"[EVENT_SLUG] Could not extract event slug from market slug: {market_slug_clean}")
        except Exception as e:
            logger.warning(f"[EVENT_SLUG] Failed to resolve canonical event+market for condition={condition_id[:20]}..., falling back: {e}")
        
        return None, None, None, None
    
    def _detect_sports_event(self, event: Optional[Dict[str, Any]], event_slug: Optional[str], market_slug: Optional[str] = None) -> bool:
        """
        Detect if an event is a sports event by checking event object fields and slug patterns.
        
        Returns:
            bool: True if this is a sports event, False otherwise
        """
        event_id = None
        detection_reason = None
        
        # Initialize variables to prevent UnboundLocalError when event is None
        category = None
        groupType = None
        event_type = None
        eventType = None
        group = None
        tags = []
        
        # Log event object structure for diagnostics
        logger.debug(f"[SPORTS_DETECT] Analyzing event for sports detection:")
        logger.debug(f"[SPORTS_DETECT]   - event_slug: {event_slug}")
        logger.debug(f"[SPORTS_DETECT]   - market_slug: {market_slug}")
        
        if event:
            event_id = event.get("id") or event.get("eventId") or event.get("event_id")
            
            # Log all category-related fields
            category = event.get("category")
            groupType = event.get("groupType")
            event_type = event.get("type")
            eventType = event.get("eventType")
            group = event.get("group")
            tags = event.get("tags", [])
            
            logger.debug(f"[SPORTS_DETECT]   - event_id: {event_id}")
            logger.debug(f"[SPORTS_DETECT]   - category: {category}")
            logger.debug(f"[SPORTS_DETECT]   - groupType: {groupType}")
            logger.debug(f"[SPORTS_DETECT]   - type: {event_type}")
            logger.debug(f"[SPORTS_DETECT]   - eventType: {eventType}")
            logger.debug(f"[SPORTS_DETECT]   - group: {group}")
            logger.debug(f"[SPORTS_DETECT]   - tags: {tags}")
            
            # Check event object fields - explicit category check
            if category:
                category_lower = str(category).lower()
                if category_lower == "sports":
                    detection_reason = f"category='sports'"
                    logger.info(f"[SPORTS_DETECT] ✅ SPORTS DETECTED: {detection_reason} (event_id={event_id}, slug={event_slug})")
                    return True
            
            # Check groupType, type, eventType, group fields
            category_fields = [
                event.get("groupType"),
                event.get("type"),
                event.get("eventType"),
                event.get("group"),
            ]
            
            # Check for sports-related keywords in category fields
            sports_category_keywords = ['sport', 'football', 'soccer', 'uef', 'uefa', 'nfl', 'nba', 'nhl', 'mlb', 'fif', 'fifa', 'ufc', 'mma', 'boxing', 'wrestling']
            for field_name, field_value in zip(["groupType", "type", "eventType", "group"], category_fields):
                if field_value:
                    field_lower = str(field_value).lower()
                    matched_keyword = next((kw for kw in sports_category_keywords if kw in field_lower), None)
                    if matched_keyword:
                        detection_reason = f"keyword '{matched_keyword}' in {field_name}='{field_value}'"
                        logger.info(f"[SPORTS_DETECT] ✅ SPORTS DETECTED: {detection_reason} (event_id={event_id}, slug={event_slug})")
                        return True
            
            # Check tags
            if isinstance(tags, list):
                for tag in tags:
                    tag_str = str(tag).lower()
                    matched_keyword = next((kw for kw in sports_category_keywords if kw in tag_str), None)
                    if matched_keyword:
                        detection_reason = f"keyword '{matched_keyword}' in tag='{tag}'"
                        logger.info(f"[SPORTS_DETECT] ✅ SPORTS DETECTED: {detection_reason} (event_id={event_id}, slug={event_slug})")
                        return True
        
        # Check slug patterns - expanded keywords for football/soccer
        slug_to_check = (event_slug or market_slug or "").lower()
        sports_keywords = [
            # Major sports leagues
            'nfl', 'nba', 'nhl', 'mlb', 'ncaa', 'sports',
            # Combat sports
            'ufc', 'mma', 'boxing', 'wrestling',
            # Football/Soccer
            'uef', 'uefa', 'fif', 'fifa', 'soccer', 'football',
            # Football competitions
            'qualifier', 'qualifiers', 'friendly', 'friendlies',
            'premier', 'champions', 'world-cup', 'euro',
            # General sports terms
            'match', 'game', 'games',
            # Country codes (common in football slugs)
            'gib', 'mon', 'nld', 'pol', 'fin', 'and'
        ]
        
        matched_keyword = next((kw for kw in sports_keywords if kw in slug_to_check), None)
        is_sports = matched_keyword is not None
        
        if is_sports:
            detection_reason = f"keyword '{matched_keyword}' in slug='{slug_to_check[:100]}'"
            logger.info(f"[SPORTS_DETECT] ✅ SPORTS DETECTED: {detection_reason} (event_id={event_id})")
        else:
            logger.debug(f"[SPORTS_DETECT] ❌ NOT SPORTS: No sports indicators found in category fields, tags, or slug")
            logger.debug(f"[SPORTS_DETECT]   - Checked category: {category}")
            logger.debug(f"[SPORTS_DETECT]   - Checked groupType: {groupType}")
            logger.debug(f"[SPORTS_DETECT]   - Checked type: {event_type}")
            logger.debug(f"[SPORTS_DETECT]   - Checked eventType: {eventType}")
            logger.debug(f"[SPORTS_DETECT]   - Checked tags: {tags}")
            logger.debug(f"[SPORTS_DETECT]   - Checked slug: {slug_to_check[:100]}")
        
        logger.info(f"[SPORTS_DETECT] event_id={event_id}, slug={event_slug}, market_slug={market_slug}, is_sports={is_sports}, category={category}, tags={tags}, reason={detection_reason}")
        return is_sports
    
    def _get_sports_url_from_event(self, event: Optional[Dict[str, Any]], event_slug: Optional[str] = None) -> Optional[str]:
        """
        Extract sports URL path from event object.
        Looks for fields containing /sports/... path in the event.
        
        Args:
            event: Event object from Gamma API
            event_slug: Event slug (for logging)
            
        Returns:
            str: Full URL (https://polymarket.com/sports/...) if found, None otherwise
        """
        if not event:
            logger.debug(f"[URL] [SPORTS] No event object provided for sports URL extraction (event_slug={event_slug})")
            return None
        
        # Log event object structure for diagnostics
        logger.debug(f"[URL] [SPORTS] [DEBUG] Event object structure for event_slug={event_slug}:")
        
        # Log all top-level keys with types and sample values
        event_keys = list(event.keys())
        logger.debug(f"[URL] [SPORTS] [DEBUG]   - Available keys: {event_keys}")
        
        # Log all string fields
        string_fields = {}
        nested_objects = []
        for key, value in event.items():
            if isinstance(value, str):
                # Truncate long strings for readability
                preview = value[:100] + "..." if len(value) > 100 else value
                string_fields[key] = preview
            elif isinstance(value, (dict, list)):
                nested_objects.append(key)
        
        logger.debug(f"[URL] [SPORTS] [DEBUG]   - String fields: {string_fields}")
        logger.debug(f"[URL] [SPORTS] [DEBUG]   - Nested objects: {nested_objects}")
        
        # Log full event object as JSON (truncated)
        try:
            event_json = json.dumps(event, indent=2, default=str)
            event_json_truncated = event_json[:2000]
            logger.debug(f"[URL] [SPORTS] [DEBUG]   - Full event object (truncated to 2000 chars): {event_json_truncated}")
        except Exception as e:
            logger.debug(f"[URL] [SPORTS] [DEBUG]   - Failed to serialize event object: {e}")
        
        # Collect candidate paths from multiple fields
        candidate_paths = []
        
        # Inspect nested objects for /sports/ strings (shallow traversal - one level down)
        logger.debug(f"[URL] [SPORTS] [DEBUG] Scanning nested objects for /sports/ pattern...")
        for nested_key in nested_objects:
            nested_value = event.get(nested_key)
            if nested_value is None:
                continue
            
            # Handle dict values
            if isinstance(nested_value, dict):
                logger.debug(f"[URL] [SPORTS] [DEBUG]   - Inspecting nested dict '{nested_key}'...")
                for sub_key, sub_value in nested_value.items():
                    if isinstance(sub_value, str) and "/sports/" in sub_value:
                        nested_path = f"{nested_key}.{sub_key}"
                        logger.debug(f"[URL] [SPORTS] [DEBUG]   - Found /sports/ in nested path '{nested_path}': {sub_value[:150]}...")
                        candidate_paths.append((nested_path, sub_value.strip()))
            
            # Handle list values
            elif isinstance(nested_value, list):
                logger.debug(f"[URL] [SPORTS] [DEBUG]   - Inspecting nested list '{nested_key}' ({len(nested_value)} items)...")
                for idx, list_item in enumerate(nested_value):
                    # Check if list item is a string
                    if isinstance(list_item, str) and "/sports/" in list_item:
                        nested_path = f"{nested_key}[{idx}]"
                        logger.debug(f"[URL] [SPORTS] [DEBUG]   - Found /sports/ in nested path '{nested_path}': {list_item[:150]}...")
                        candidate_paths.append((nested_path, list_item.strip()))
                    # Check if list item is dict-like
                    elif isinstance(list_item, dict):
                        for sub_key, sub_value in list_item.items():
                            if isinstance(sub_value, str) and "/sports/" in sub_value:
                                nested_path = f"{nested_key}[{idx}].{sub_key}"
                                logger.debug(f"[URL] [SPORTS] [DEBUG]   - Found /sports/ in nested path '{nested_path}': {sub_value[:150]}...")
                                candidate_paths.append((nested_path, sub_value.strip()))
        possible_fields = [
            "url",
            "path",
            "pagePath",
            "webUrl",
            "sportsUrl",
            "link",
            "permalink",
            "canonicalUrl",
        ]
        
        # Log each candidate field being checked
        for field_name in possible_fields:
            field_value = event.get(field_name)
            if field_value:
                value_preview = str(field_value)[:100] + "..." if len(str(field_value)) > 100 else str(field_value)
                logger.debug(f"[URL] [SPORTS] [DEBUG]   - Checking field '{field_name}': {value_preview}")
                candidate_paths.append((field_name, str(field_value).strip()))
            else:
                logger.debug(f"[URL] [SPORTS] [DEBUG]   - Checking field '{field_name}': not present")
        
        # Try each candidate path
        for field_name, field_value_str in candidate_paths:
            logger.debug(f"[URL] [SPORTS] [DEBUG]   - Evaluating field '{field_name}': {field_value_str[:150]}...")
            # Check if this field contains /sports/ path
            if "/sports/" in field_value_str:
                # Normalize the path
                if field_value_str.startswith("http"):
                    # Already a full URL
                    sports_url = field_value_str
                elif field_value_str.startswith("/"):
                    # Path starting with /
                    sports_url = f"https://polymarket.com{field_value_str}"
                else:
                    # Path without leading /
                    sports_url = f"https://polymarket.com/{field_value_str}"
                
                logger.info(f"[URL] [SPORTS] Extracted sports path from event field '{field_name}': {sports_url} (event_slug={event_slug})")
                return sports_url
        
        # Also check if any string value in event contains /sports/
        logger.debug(f"[URL] [SPORTS] [DEBUG] Scanning all string fields for /sports/ pattern...")
        for key, value in event.items():
            if isinstance(value, str) and "/sports/" in value:
                value_str = value.strip()
                logger.debug(f"[URL] [SPORTS] [DEBUG]   - Found /sports/ in field '{key}': {value_str[:150]}...")
                if value_str.startswith("http"):
                    sports_url = value_str
                elif value_str.startswith("/"):
                    sports_url = f"https://polymarket.com{value_str}"
                else:
                    sports_url = f"https://polymarket.com/{value_str}"
                
                logger.info(f"[URL] [SPORTS] Extracted sports path from event field '{key}': {sports_url} (event_slug={event_slug})")
                return sports_url
        
        # Log available fields for debugging
        available_fields = [f for f in possible_fields if event.get(f)]
        logger.warning(f"[URL] [SPORTS] No /sports/ path found in event. Available fields: {available_fields}, event keys: {list(event.keys())[:15]}... (event_slug={event_slug})")
        logger.debug(f"[URL] [SPORTS] [DEBUG] Fallback to event_slug/market_slug construction logic")
        return None
    
    def _construct_sports_url_from_slug(self, market_slug: str, event_obj: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Construct sports URL using slug patterns when Gamma API doesn't provide /sports/ paths.
        
        This method parses the market_slug to identify league prefixes, extract date patterns,
        and construct URLs in the format: /sports/{league}/games/week/{week}/{base-slug}
        or /sports/{league}/games/{base-slug} if week is unknown.
        
        The method uses enhanced parsing logic:
        1. Identifies date patterns (YYYY-MM-DD) and includes them in the base slug
        2. Excludes trailing outcome suffixes after the date, including:
           - Market type indicators (spread, total, moneyline, etc.)
           - Numeric outcomes (e.g., "2pt5", "42pt5")
           - Short team/outcome codes (3-letter codes like 'tun', 'bra' that appear after the date)
        3. Validates the constructed base slug against event_obj when available
        4. Falls back to slug length heuristics for ambiguous cases
        
        Args:
            market_slug: Market slug (e.g., "nfl-was-mia-2025-11-16-spread-home-2pt5" or "fif-bra-tun-2025-11-18-tun")
            event_obj: Optional event object from Gamma API for additional context
            
        Returns:
            str: Full sports URL (https://polymarket.com/sports/...) if construction succeeds, None otherwise
        """
        if not market_slug:
            logger.debug(f"[URL] [SPORTS] [SLUG] No market_slug provided for URL construction")
            return None
        
        logger.info(f"[URL] [SPORTS] [SLUG] Constructing sports URL from slug: {market_slug[:100]}...")
        
        # Parse market_slug to identify league prefix
        market_slug_clean = market_slug.strip().strip('/')
        slug_parts = market_slug_clean.split('-')
        
        if len(slug_parts) < 2:
            logger.debug(f"[URL] [SPORTS] [SLUG] Slug too short to parse: {market_slug_clean}")
            return None
        
        # League prefix mapping
        league_prefixes = {
            'fif': 'fifa-world-cup-qualifiers',
            'uef': 'uef-qualifiers',
            'nfl': 'nfl',
            'nba': 'nba',
            'nhl': 'nhl',
            'mlb': 'mlb',
        }
        
        # Identify league from prefix
        league_prefix = slug_parts[0].lower()
        league_name = league_prefixes.get(league_prefix)
        
        # If event_obj is provided, check for league information
        if not league_name and event_obj:
            group_type = event_obj.get('groupType') or event_obj.get('type')
            tags = event_obj.get('tags', [])
            
            if group_type:
                logger.debug(f"[URL] [SPORTS] [SLUG] Found groupType/type from event_obj: {group_type}")
                # Try to map groupType to league name
                group_type_lower = str(group_type).lower()
                if 'nfl' in group_type_lower:
                    league_name = 'nfl'
                elif 'nba' in group_type_lower:
                    league_name = 'nba'
                elif 'nhl' in group_type_lower:
                    league_name = 'nhl'
                elif 'mlb' in group_type_lower:
                    league_name = 'mlb'
                elif 'fifa' in group_type_lower or 'fif' in group_type_lower:
                    league_name = 'fifa-world-cup-qualifiers'
                elif 'uefa' in group_type_lower or 'uef' in group_type_lower:
                    league_name = 'uef-qualifiers'
            
            if not league_name and tags:
                logger.debug(f"[URL] [SPORTS] [SLUG] Checking tags for league info: {tags}")
                for tag in tags:
                    tag_str = str(tag).lower()
                    if 'nfl' in tag_str:
                        league_name = 'nfl'
                        break
                    elif 'nba' in tag_str:
                        league_name = 'nba'
                        break
                    elif 'nhl' in tag_str:
                        league_name = 'nhl'
                        break
                    elif 'mlb' in tag_str:
                        league_name = 'mlb'
                        break
        
        if not league_name:
            logger.debug(f"[URL] [SPORTS] [SLUG] Could not identify league from slug prefix: {league_prefix}")
            return None
        
        logger.info(f"[URL] [SPORTS] [SLUG] Identified league: {league_name}")
        
        # Extract base slug by removing outcome suffixes
        outcome_suffixes = ['spread', 'total', 'moneyline', 'over', 'under', 'home', 'away', 'pt5', 'pt']
        base_slug_parts = []
        found_market_type = False
        date_end_index = None
        
        # First, identify date pattern (4-digit year starting with 20, followed by month and day)
        for i in range(len(slug_parts) - 2):
            part = slug_parts[i]
            # Check if this is a 4-digit year starting with 20
            if len(part) == 4 and part.startswith('20') and part.isdigit():
                # Check if next two parts look like month and day
                if i + 2 < len(slug_parts):
                    month_part = slug_parts[i + 1]
                    day_part = slug_parts[i + 2]
                    # Month should be 1-2 digits (1-12), day should be 1-2 digits (1-31)
                    if (month_part.isdigit() and 1 <= int(month_part) <= 12 and
                        day_part.isdigit() and 1 <= int(day_part) <= 31):
                        # Found date pattern - include year, month, day in base_slug_parts
                        date_end_index = i + 3  # Index after the date (year, month, day)
                        logger.debug(f"[URL] [SPORTS] [SLUG] Found date pattern at index {i}: {part}-{month_part}-{day_part}")
                        break
        
        # Helper function to detect team/outcome codes (3-letter codes that appear after date)
        def is_team_code_after_date(part: str, i: int) -> bool:
            """Check if part is a short team/outcome code that should be excluded after date"""
            if date_end_index is None or i < date_end_index:
                return False
            # Check for 3-letter lowercase codes (common team codes like 'tun', 'bra', 'usa')
            if len(part) == 3 and part.isalpha() and part.islower():
                return True
            # Check for 2-letter codes (less common but possible)
            if len(part) == 2 and part.isalpha() and part.islower():
                return True
            return False
        
        # Build base_slug_parts: include everything up to and including the date, then stop at market-specific suffixes
        for i, part in enumerate(slug_parts):
            # Always include date components in base_slug_parts
            if date_end_index is not None and i < date_end_index:
                base_slug_parts.append(part)
                continue
            
            # After date, check for market-specific suffixes and stop
            if part in outcome_suffixes:
                found_market_type = True
                break
            
            # After date, exclude short team/outcome codes (e.g., 'tun', 'bra' after date)
            if date_end_index is not None and i >= date_end_index:
                # Check for team codes first (before numeric checks)
                if is_team_code_after_date(part, i):
                    found_market_type = True
                    logger.debug(f"[URL] [SPORTS] [SLUG] Excluding team code '{part}' after date at index {i}")
                    break
                
                # Skip numeric parts that look like outcomes (e.g., "2pt5", "42pt5")
                if part.isdigit() or (len(part) > 2 and part[0].isdigit() and 'pt' in part.lower()):
                    found_market_type = True
                    break
                
                # Stop if next part is a short alphanumeric that doesn't resemble date/month/day
                # This catches edge cases where team codes might not be exactly 3 letters
                if len(part) <= 3 and part.isalnum() and not part.isdigit():
                    # Since it's alphanumeric but not all digits, exclude it as likely outcome/team code
                    found_market_type = True
                    logger.debug(f"[URL] [SPORTS] [SLUG] Excluding short alphanumeric '{part}' after date at index {i}")
                    break
                
                # Continue adding parts after date until we hit a market type
                base_slug_parts.append(part)
            else:
                # No date pattern found - use original logic
                # Stop at market type indicators
                if part in outcome_suffixes:
                    found_market_type = True
                    break
                # Skip numeric parts that look like outcomes (e.g., "2pt5", "42pt5")
                if part.isdigit() or (len(part) > 2 and part[0].isdigit() and 'pt' in part.lower()):
                    found_market_type = True
                    break
                base_slug_parts.append(part)
        
        # If no market type found, use all parts except last few
        if not found_market_type and len(slug_parts) > 3:
            base_slug_parts = slug_parts[:-2]
        
        if not base_slug_parts:
            logger.debug(f"[URL] [SPORTS] [SLUG] Could not extract base slug from: {market_slug_clean}")
            return None
        
        base_slug = '-'.join(base_slug_parts)
        logger.info(f"[URL] [SPORTS] [SLUG] Extracted base slug: {base_slug}")
        
        # Validate and adjust base slug using event_obj if available
        if event_obj:
            # Try to get canonical slug from event_obj
            markets = event_obj.get('markets', [])
            if markets and len(markets) > 0:
                canonical_slug = markets[0].get('slug', '').strip()
                if canonical_slug:
                    # Extract base from canonical slug (remove outcome suffixes)
                    canonical_parts = canonical_slug.split('-')
                    # Find date in canonical slug
                    canonical_date_end = None
                    for j in range(len(canonical_parts) - 2):
                        if (len(canonical_parts[j]) == 4 and canonical_parts[j].startswith('20') and
                            canonical_parts[j].isdigit() and j + 2 < len(canonical_parts)):
                            month_part = canonical_parts[j + 1]
                            day_part = canonical_parts[j + 2]
                            if (month_part.isdigit() and 1 <= int(month_part) <= 12 and
                                day_part.isdigit() and 1 <= int(day_part) <= 31):
                                canonical_date_end = j + 3
                                break
                    
                    # Build expected base slug from canonical
                    if canonical_date_end:
                        expected_base_parts = canonical_parts[:canonical_date_end]
                        expected_base = '-'.join(expected_base_parts)
                        # Compare lengths - if our base_slug is longer, it likely includes outcomes
                        if len(base_slug) > len(expected_base):
                            logger.info(f"[URL] [SPORTS] [SLUG] Adjusting base slug based on event_obj: {base_slug} -> {expected_base}")
                            base_slug = expected_base
            
            # Also check event slug directly
            event_slug = event_obj.get('slug', '').strip()
            if event_slug:
                event_slug_clean = event_slug.strip().strip('/')
                event_parts = event_slug_clean.split('-')
                # Find date in event slug
                event_date_end = None
                for j in range(len(event_parts) - 2):
                    if (len(event_parts[j]) == 4 and event_parts[j].startswith('20') and
                        event_parts[j].isdigit() and j + 2 < len(event_parts)):
                        month_part = event_parts[j + 1]
                        day_part = event_parts[j + 2]
                        if (month_part.isdigit() and 1 <= int(month_part) <= 12 and
                            day_part.isdigit() and 1 <= int(day_part) <= 31):
                            event_date_end = j + 3
                            break
                
                if event_date_end:
                    expected_base_parts = event_parts[:event_date_end]
                    expected_base = '-'.join(expected_base_parts)
                    if len(base_slug) > len(expected_base):
                        logger.info(f"[URL] [SPORTS] [SLUG] Adjusting base slug based on event slug: {base_slug} -> {expected_base}")
                        base_slug = expected_base
        
        # Enhanced validation function for base slug structure
        def validate_base_slug(base_slug: str, market_slug_clean: str) -> str:
            """
            Validate and potentially adjust base slug to ensure it ends correctly.
            Returns the validated (possibly adjusted) base slug.
            """
            # Check for known outcome patterns at the end
            known_outcome_patterns = [
                r'-[a-z]{2,3}$',  # 2-3 letter codes at end (team codes)
                r'-\d+pt\d*$',    # Numeric outcomes like "-220pt5"
                r'-\d+$',         # Standalone numbers
            ]
            
            import re
            for pattern in known_outcome_patterns:
                if re.search(pattern, base_slug):
                    # Extract date from base_slug
                    base_parts = base_slug.split('-')
                    date_end_idx = None
                    for k in range(len(base_parts) - 2):
                        if (len(base_parts[k]) == 4 and base_parts[k].startswith('20') and
                            base_parts[k].isdigit() and k + 2 < len(base_parts)):
                            month_part = base_parts[k + 1]
                            day_part = base_parts[k + 2]
                            if (month_part.isdigit() and 1 <= int(month_part) <= 12 and
                                day_part.isdigit() and 1 <= int(day_part) <= 31):
                                date_end_idx = k + 3
                                break
                    
                    if date_end_idx:
                        # Trim to date end
                        adjusted_parts = base_parts[:date_end_idx]
                        adjusted_slug = '-'.join(adjusted_parts)
                        logger.warning(f"[URL] [SPORTS] [SLUG] ⚠️  Adjusted base slug (removed trailing outcome): {base_slug} -> {adjusted_slug}")
                        return adjusted_slug
            
            return base_slug
        
        # Apply validation
        base_slug = validate_base_slug(base_slug, market_slug_clean)
        
        # Enhanced unit-test-style checks for various slug patterns
        test_cases = [
            ('fif-bra-tun-2025-11-18-tun', 'fif-bra-tun-2025-11-18'),
            ('nfl-nyj-ne-2025-11-13-spread', 'nfl-nyj-ne-2025-11-13'),
            ('nba-lal-gsw-2025-01-15-total-220pt5', 'nba-lal-gsw-2025-01-15'),
        ]
        
        for test_input, expected_output in test_cases:
            if test_input in market_slug_clean.lower():
                if base_slug.lower() != expected_output.lower():
                    logger.warning(f"[URL] [SPORTS] [SLUG] ⚠️  Base slug mismatch for test case '{test_input}': got '{base_slug}', expected '{expected_output}'")
                else:
                    logger.debug(f"[URL] [SPORTS] [SLUG] ✅ Base slug matches expected for '{test_input}': {base_slug}")
        
        # Try to determine week number
        week_number = None
        if event_obj:
            week = event_obj.get('week') or event_obj.get('round') or event_obj.get('matchday')
            if week:
                try:
                    week_number = int(week)
                    logger.info(f"[URL] [SPORTS] [SLUG] Found week number from event_obj: {week_number}")
                except (ValueError, TypeError):
                    pass
        
        # Construct URL
        if week_number:
            sports_url = f"https://polymarket.com/sports/{league_name}/games/week/{week_number}/{base_slug}"
        else:
            sports_url = f"https://polymarket.com/sports/{league_name}/games/{base_slug}"
        
        logger.info(f"[URL] [SPORTS] [SLUG] Constructed sports URL: {sports_url}")
        logger.info(f"[URL] [SPORTS] [SLUG] Base slug validation: input='{market_slug_clean[:80]}...', base_slug='{base_slug}'")
        return sports_url
    
    def _get_event_slug(self, condition_id: str) -> Optional[str]:
        """
        Get event slug from Gamma API for sports markets.
        For sports markets, this returns the game/event slug (e.g., "nfl-nyj-ne-2025-11-13")
        instead of the market-specific slug (e.g., "nfl-nyj-ne-2025-11-13-total-42pt5-697").
        
        Returns:
            str: Event slug if found, None otherwise
        """
        event_slug, _, _, _ = self._get_event_slug_and_market_id(condition_id)
        return event_slug
    
    def _get_search_url_fallback(self, condition_id: str) -> str:
        """Get search URL as final fallback"""
        try:
            url = f"https://clob.polymarket.com/markets/{condition_id}"
            response = self._make_authenticated_get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                question = data.get('question') or data.get('title') or ""
                if question:
                    # Use question for search (more reliable than condition_id)
                    import urllib.parse
                    search_query = urllib.parse.quote(question[:50])  # Limit length
                    return f"https://polymarket.com/search?q={search_query}"
        except Exception:
            pass
        return f"https://polymarket.com/search?q={condition_id[:20]}"
    
    def _get_market_slug(self, condition_id: str) -> str:
        """
        Get market slug from API
        
        IMPORTANT: We need market-level slug, not outcome-specific slug.
        Strategy:
        1. Try Gamma API first (most reliable for market-level slugs)
        2. Try CLOB API question_slug or market_slug
        3. Fallback to search
        
        All slug normalization is handled by _clean_slug() - this function only selects
        the appropriate field from API responses.
        """
        # Priority 1: Try Gamma API (returns market-level slug)
        try:
            from gamma_client import get_event_by_condition_id
            event = get_event_by_condition_id(condition_id)
            if event:
                markets = event.get("markets", [])
                # Find market matching condition_id
                for market in markets:
                    market_condition_id = market.get("conditionId") or market.get("condition_id", "")
                    if market_condition_id and market_condition_id.lower() == condition_id.lower():
                        slug = market.get("slug", "")
                        if slug:
                            # Use centralized cleaning function
                            cleaned_slug = self._clean_slug(slug, strip_market_prefix=True)
                            logger.info(f"[SLUG] Got market slug from Gamma API: {cleaned_slug} (condition_id={condition_id[:20]}...)")
                            return cleaned_slug
                # If no exact match, use first market's slug (they should share the same event slug)
                if markets:
                    slug = markets[0].get("slug", "")
                    if slug:
                        # Use centralized cleaning function
                        cleaned_slug = self._clean_slug(slug, strip_market_prefix=True)
                        logger.info(f"[SLUG] Got market slug from Gamma API (first market): {cleaned_slug} (condition_id={condition_id[:20]}...)")
                        return cleaned_slug
        except Exception as e:
            logger.debug(f"Failed to get market slug from Gamma API: {e}")
        
        # Priority 2: Try CLOB API
        try:
            url = f"https://clob.polymarket.com/markets/{condition_id}"
            response = self._make_authenticated_get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Prefer question_slug or market_slug (these are market-level)
                slug = (data.get('question_slug') or 
                       data.get('market_slug') or 
                       data.get('slug') or 
                       data.get('event_slug'))
                
                if slug:
                    # Use centralized cleaning function
                    cleaned_slug = self._clean_slug(slug, strip_market_prefix=True)
                    logger.info(f"[SLUG] Got market slug from CLOB API: {cleaned_slug} (condition_id={condition_id[:20]}...)")
                    return cleaned_slug
        except Exception as e:
            logger.debug(f"Failed to get market slug from CLOB API: {e}")
        
        # Priority 3: Try data-api.polymarket.com
        try:
            url = f"https://data-api.polymarket.com/condition/{condition_id}"
            response = self._make_authenticated_get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                slug = (data.get('question_slug') or 
                       data.get('market_slug') or 
                       data.get('slug') or 
                       data.get('event_slug'))
                if slug:
                    # Use centralized cleaning function
                    cleaned_slug = self._clean_slug(slug, strip_market_prefix=True)
                    logger.info(f"[SLUG] Got market slug from data-api: {cleaned_slug} (condition_id={condition_id[:20]}...)")
                    return cleaned_slug
        except Exception as e:
            logger.debug(f"Failed to get market slug from data-api: {e}")
        
        logger.debug(f"[SLUG] No slug found for condition_id={condition_id[:20]}..., will use search fallback")
        return ""
    
    def _get_outcome_name(self, condition_id: str, outcome_index: int) -> str:
        """Get outcome name (Yes/No/etc) from API"""
        try:
            # Try CLOB API
            url = f"https://clob.polymarket.com/markets/{condition_id}"
            response = self._make_authenticated_get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                tokens = data.get('tokens', [])
                if tokens and outcome_index < len(tokens):
                    outcome_data = tokens[outcome_index]
                    outcome_name = outcome_data.get('outcome')
                    if outcome_name:
                        return outcome_name
        except Exception as e:
            logger.debug(f"Failed to get outcome name: {e}")
        
        return ""
    
    def _get_market_title(self, condition_id: str) -> str:
        """Get market title and slug from API"""
        try:
            # Try CLOB API first (most reliable for markets)
            url2 = f"https://clob.polymarket.com/markets/{condition_id}"
            response2 = self._make_authenticated_get(url2, timeout=5)
            if response2.status_code == 200:
                data = response2.json()
                # Try multiple possible title fields
                title = data.get('title') or data.get('question') or data.get('name')
                if title:
                    return title
            
            # Try Data API as fallback
            url = f"https://data-api.polymarket.com/condition/{condition_id}"
            response = self._make_authenticated_get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                title = data.get('title') or data.get('question') or data.get('name')
                if title:
                    return title
                    
        except Exception as e:
            logger.debug(f"Failed to get market title from API: {e}")
        
        # Fallback to truncated condition ID
        return f"{condition_id[:10]}..."

    def _get_current_price(self, condition_id: str, outcome_index: int, 
                          wallet_prices: Optional[Dict[str, float]] = None,
                          hashdive_client: Optional[Any] = None,
                          slug: Optional[str] = None) -> Optional[float]:
        """
        Try to fetch current last price with multi-level fallback:
        1. New price_fetcher module (Polymarket CLOB /price, HashiDive, trades history, FinFeed)
        2. Legacy CLOB API /markets endpoint
        3. Average price from wallet_prices (if provided)
        4. Polymarket data-api (last resort)
        
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
            
            # CRITICAL: Only pass slug to price_fetcher if it's cleaned and market-level
            # If slug is provided, clean it and validate it's not market-specific before passing
            cleaned_slug_for_price = None
            if slug:
                cleaned_slug = self._clean_slug(slug, strip_market_prefix=True)
                # Only pass slug if it's not market-specific (market-specific slugs may not work with Gamma /events)
                if cleaned_slug and not self._is_market_specific_slug(cleaned_slug):
                    cleaned_slug_for_price = cleaned_slug
                    logger.debug(f"[Price] Using cleaned market-level slug for price fetcher: {cleaned_slug_for_price[:50]}")
                else:
                    logger.debug(f"[Price] Skipping slug for price fetcher (market-specific or invalid): {slug[:50] if slug else 'None'}")
            
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
            resp = self._make_authenticated_get(url, timeout=5)
            
            # Handle 404 - market not found (closed/removed)
            if resp.status_code == 404:
                logger.debug(f"[Price] CLOB API returned 404 for condition_id={condition_id[:20]}... (market not found - likely closed)")
                # Don't try other methods if market doesn't exist
                return None
            
            if resp.status_code == 200:
                data = resp.json()
                # Try token-specific price fields (priority order: price, last_price, mark_price)
                # Note: API может возвращать price даже когда last_price=None
                tokens = data.get('tokens') or []
                if tokens and outcome_index < len(tokens):
                    token = tokens[outcome_index]
                    # Сначала пробуем price (более надежное поле)
                    for key in ("price", "last_price", "mark_price"):
                        val = token.get(key)
                        if val is not None:
                            try:
                                price = float(val)
                                logger.debug(f"[Price] Got price from CLOB API token[{outcome_index}].{key}: {price}")
                                return price
                            except (ValueError, TypeError) as e:
                                logger.debug(f"[Price] Failed to parse {key}={val}: {e}")
                                continue
                # Fallback to market-level fields if present
                for key in ("price", "last_price", "mark_price"):
                    val = data.get(key)
                    if val is not None:
                        try:
                            price = float(val)
                            logger.debug(f"[Price] Got price from CLOB API market.{key}: {price}")
                            return price
                        except (ValueError, TypeError) as e:
                            logger.debug(f"[Price] Failed to parse market-level {key}={val}: {e}")
                            continue
            else:
                logger.debug(f"[Price] CLOB API returned status {resp.status_code} for condition_id={condition_id[:20]}...")
        except Exception as e:
            logger.debug(f"[Price] CLOB API failed: {type(e).__name__}: {e}")
        
        # Step 2: Try HashiDive API (if available, legacy method)
        if hashdive_client:
            try:
                # HashiDive uses asset_id (token ID) format: condition_id:outcome_index
                asset_id = f"{condition_id}:{outcome_index}"
                price_data = hashdive_client.get_last_price(asset_id)
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
            try:
                prices = [p for p in wallet_prices.values() if isinstance(p, (int, float)) and p > 0]
                if prices:
                    avg_price = sum(prices) / len(prices)
                    logger.debug(f"[Price] Using average price from wallet_prices: {avg_price:.3f} (from {len(prices)} wallets)")
                    return avg_price
            except Exception as e:
                logger.debug(f"[Price] Failed to calculate average from wallet_prices: {e}")
        
        # Step 4: Try Polymarket data-api (last resort)
        try:
            url = f"https://data-api.polymarket.com/markets/{condition_id}"
            resp = self._make_authenticated_get(url, timeout=5)
            if resp and resp.status_code == 200:
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
    
    def _calculate_consensus_strength(self, wallet_count: int, window_minutes: float) -> str:
        """Calculate consensus strength based on wallet count and time window"""
        if wallet_count >= 10:
            return "🔥 Very Strong"
        elif wallet_count >= 7:
            return "⚡ Strong"
        elif wallet_count >= 5:
            return "📈 Moderate"
        elif wallet_count >= 3:
            return "👀 Weak"
        else:
            return "❓ Unknown"
    
    def test_connection(self) -> bool:
        """Test Telegram bot connection"""
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram credentials not configured")
            return False
        
        test_message = f"""🧪 *Telegram Connection Test*

This is a test message from Polymarket Notifier.

_{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC_"""
        
        return self.send_message(test_message, chat_id=self.reports_chat_id)

# Convenience functions for backward compatibility
def send_telegram(text: str) -> bool:
    """Legacy function for sending Telegram messages"""
    notifier = TelegramNotifier()
    return notifier.send_message(text)

def send_consensus_alert(condition_id: str, outcome_index: int, wallets: List[str], 
                        window_minutes: float = 10.0, min_consensus: int = 3) -> bool:
    """Legacy function for sending consensus alerts"""
    notifier = TelegramNotifier()
    return notifier.send_consensus_alert(condition_id, outcome_index, wallets, 
                                       wallet_prices={}, window_minutes=window_minutes, min_consensus=min_consensus)

# Example usage and testing
if __name__ == "__main__":
    # Test notification system
    notifier = TelegramNotifier()
    
    # Test connection
    if notifier.test_connection():
        print("Telegram connection test successful")
        
        # Test consensus alert
        test_wallets = [
            "0x1234567890abcdef1234567890abcdef12345678",
            "0xabcdef1234567890abcdef1234567890abcdef12",
            "0x9876543210fedcba9876543210fedcba98765432"
        ]
        
        notifier.send_consensus_alert(
            condition_id="0x1234567890abcdef",
            outcome_index=0,
            wallets=test_wallets,
            alert_id="TEST123"
        )
        
        print("Test notifications sent")
    else:
        print("Telegram connection test failed - check credentials")
