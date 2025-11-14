"""
Telegram Notification Functions for Polymarket Notifier
Handles sending formatted alerts via Telegram Bot API
"""

import os
import requests
import logging
from typing import List, Dict, Any, Optional
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
        headers = {}
        # if self.polymarket_auth and self.polymarket_auth.has_auth:
        #     from urllib.parse import urlparse
        #     parsed = urlparse(url)
        #     request_path = parsed.path
        #     auth_headers = self.polymarket_auth.get_auth_headers("GET", request_path)
        #     headers.update(auth_headers)
        return requests.get(url, headers=headers, timeout=timeout)
    
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
                           current_price: Optional[float] = None) -> bool:
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
        
        logger.info(f"[NOTIFY] 📨 Preparing to send consensus alert: {len(wallets)} wallets, condition={condition_id[:20]}... outcome={outcome_index} side={side}")
        
        # We will render specific trader lines below (Markdown)
        # Calculate consensus strength
        strength = self._calculate_consensus_strength(len(wallets), window_minutes)
        logger.info(f"[NOTIFY] Consensus strength calculated: {strength}")
        
        # Format market URL - For sports markets, use event slug instead of market slug
        # Try to get event slug first (for sports markets like NFL/NBA)
        event_slug = self._get_event_slug(condition_id)
        
        if event_slug:
            # Use event slug for sports markets (e.g., "nfl-nyj-ne-2025-11-13" instead of "nfl-nyj-ne-2025-11-13-total-42pt5-697")
            slug_clean = event_slug.strip().strip('/')
            market_url = f"https://polymarket.com/event/{slug_clean}"
            logger.info(f"[URL] Using event slug for sports market: {slug_clean} (condition_id={condition_id[:20]}...)")
        else:
            # Fallback: Use market slug (current behavior)
            if not market_slug:
                market_slug = self._get_market_slug(condition_id)
            
            # Use /event/ format (correct for Polymarket)
            # Try to use slug from API first, then fallback to search
            if market_slug:
                # Remove any leading/trailing slashes and ensure clean slug
                slug_clean = market_slug.strip().strip('/')
                market_url = f"https://polymarket.com/event/{slug_clean}"
                logger.info(f"[URL] Using market slug from API: {slug_clean} (fallback from event slug)")
            else:
                # Fallback: use search with question or condition_id
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
                            market_url = f"https://polymarket.com/search?q={search_query}"
                        else:
                            market_url = f"https://polymarket.com/search?q={condition_id[:20]}"
                    else:
                        market_url = f"https://polymarket.com/search?q={condition_id[:20]}"
                except Exception:
                    # If API call fails, use condition_id search
                    market_url = f"https://polymarket.com/search?q={condition_id[:20]}"
        
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
            current_price = self._get_current_price(
                condition_id, 
                outcome_index, 
                wallet_prices=wallet_prices,
                hashdive_client=self.hashdive_client,
                slug=market_slug if market_slug else None
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
            
            # For display: Avoid rounding up to 1.000 when price is extremely close to 1
            display_price = current_price
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
        header = f"*🔮 Alpha Signal Detected ({len(wallets)} wallets)*"
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

        message = f"""{header}

🎯 *Market:* {market_title}
{total_line}

*Outcome:* {position_display}
👤 Traders involved:

{chr(10).join(wallet_info)}

{price_display}{end_time_info}

📅 {timestamp_utc} UTC"""
        
        # Inline keyboard with View Market button
        reply_markup = {
            "inline_keyboard": [[
                {"text": "View Market", "url": market_url}
            ]]
        }
        
        # Log topic_id for debugging
        if self.topic_id:
            logger.info(f"Sending alert to chat_id={self.chat_id}, topic_id={self.topic_id}")
        else:
            logger.warning(f"Sending alert to chat_id={self.chat_id}, topic_id=None (may not be in forum)")
        
        # Route ALL consensus alerts to reports channel (as requested)
        target_chat = self.reports_chat_id
        
        logger.info(f"[NOTIFY] 📤 Sending consensus alert to Telegram (chat_id={target_chat}, topic_id={self.topic_id})")
        logger.info(f"[NOTIFY] 📤 Calling send_message() to Telegram for condition={condition_id[:20]}... outcome={outcome_index} side={side} wallets={len(wallets)}")
        try:
            result = self.send_message(message, reply_markup=reply_markup, chat_id=target_chat, message_thread_id=self.topic_id)
        except Exception as e:
            logger.error(f"[NOTIFY] ❌ Exception in send_message(): {e}", exc_info=True)
            result = False
        
        if result:
            logger.info(f"[NOTIFY] ✅ Consensus alert sent successfully to Telegram: condition={condition_id[:20]}... outcome={outcome_index} side={side} wallets={len(wallets)}")
        else:
            logger.error(f"[NOTIFY] ❌ Failed to send consensus alert to Telegram: condition={condition_id[:20]}... outcome={outcome_index} side={side} wallets={len(wallets)}")
        
        return result
    
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
        # Build market URL - For sports markets, use event slug instead of market slug
        # Try to get event slug first (for sports markets like NFL/NBA)
        event_slug = self._get_event_slug(condition_id)
        
        if event_slug:
            # Use event slug for sports markets (e.g., "nfl-nyj-ne-2025-11-13" instead of "nfl-nyj-ne-2025-11-13-total-42pt5-697")
            slug_clean = event_slug.strip().strip('/')
            market_url = f"https://polymarket.com/event/{slug_clean}"
            logger.info(f"[URL] Using event slug for sports market: {slug_clean} (condition_id={condition_id[:20]}...)")
        else:
            # Fallback: Use market slug (current behavior)
            if not market_slug:
                market_slug = self._get_market_slug(condition_id)
            
            # Use /event/ format (correct for Polymarket)
            # Try to use slug from API first, then fallback to search
            if market_slug:
                # Remove any leading/trailing slashes and ensure clean slug
                slug_clean = market_slug.strip().strip('/')
                market_url = f"https://polymarket.com/event/{slug_clean}"
                logger.info(f"[URL] Using market slug from API: {slug_clean} (fallback from event slug)")
            else:
                # Fallback: use search with condition_id or question
                # This is more reliable when API returns outcome-specific slug
                # Note: condition_id URLs don't work well, so use search as last resort
                # Try to get question from API for better search
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
                            market_url = f"https://polymarket.com/search?q={search_query}"
                        else:
                            market_url = f"https://polymarket.com/search?q={condition_id[:20]}"
                    else:
                        market_url = f"https://polymarket.com/search?q={condition_id[:20]}"
                except Exception:
                    # If API call fails, use condition_id search
                    market_url = f"https://polymarket.com/search?q={condition_id[:20]}"
        
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
    
    def _get_event_slug(self, condition_id: str) -> Optional[str]:
        """
        Get event slug from Gamma API for sports markets.
        For sports markets, this returns the game/event slug (e.g., "nfl-nyj-ne-2025-11-13")
        instead of the market-specific slug (e.g., "nfl-nyj-ne-2025-11-13-total-42pt5-697").
        
        Returns:
            str: Event slug if found, None otherwise
        """
        try:
            from gamma_client import get_event_by_condition_id
            event = get_event_by_condition_id(condition_id)
            if event:
                # Try to get event slug directly from event object
                event_slug = (event.get("slug") or 
                             event.get("eventSlug") or 
                             event.get("event_slug"))
                
                if event_slug:
                    # Clean slug
                    event_slug = str(event_slug).strip().strip('/')
                    if 'polymarket.com' in event_slug:
                        event_slug = event_slug.split('polymarket.com/')[-1].strip('/')
                    if event_slug.startswith('event/'):
                        event_slug = event_slug[6:]
                    elif event_slug.startswith('sports/'):
                        # Extract slug from sports path
                        parts = event_slug.split('/')
                        if len(parts) > 0:
                            event_slug = parts[-1]
                    logger.info(f"[EVENT_SLUG] Got event slug from Gamma API: {event_slug} (condition_id={condition_id[:20]}...)")
                    return event_slug
                
                # Fallback: Try to extract event slug from first market's slug
                # For sports markets, market slug often contains event slug as prefix
                markets = event.get("markets", [])
                if markets:
                    market_slug = markets[0].get("slug", "")
                    if market_slug:
                        # For sports markets like "nfl-nyj-ne-2025-11-13-total-42pt5-697"
                        # Extract base event slug by removing market-specific suffixes
                        market_slug_clean = str(market_slug).strip().strip('/')
                        if 'polymarket.com' in market_slug_clean:
                            market_slug_clean = market_slug_clean.split('polymarket.com/')[-1].strip('/')
                        if market_slug_clean.startswith('event/'):
                            market_slug_clean = market_slug_clean[6:]
                        
                        # Try to extract event slug by removing common market suffixes
                        # Patterns: -total-*, -spread-*, -moneyline-*, etc.
                        import re
                        # Remove market-specific suffixes (total, spread, moneyline, etc.)
                        # Pattern matches: nfl-nyj-ne-2025-11-13-total-42pt5-697 -> nfl-nyj-ne-2025-11-13
                        # Also handles: nfl-nyj-ne-2025-11-13-spread-3-5 -> nfl-nyj-ne-2025-11-13
                        event_slug_match = re.match(r'^([^-]+(?:-[^-]+)*?)(?:-(?:total|spread|moneyline|ou|o\/u|over-under|h2h|head-to-head)-[^-]+(?:-[^-]+)*)?$', market_slug_clean)
                        if event_slug_match:
                            potential_event_slug = event_slug_match.group(1)
                            # Verify it looks like an event slug (has date pattern YYYY-MM-DD)
                            if re.search(r'\d{4}-\d{2}-\d{2}', potential_event_slug):
                                logger.info(f"[EVENT_SLUG] Extracted event slug from market slug: {potential_event_slug} (condition_id={condition_id[:20]}...)")
                                return potential_event_slug
                        
                        # If extraction failed, return None to use fallback
                        logger.debug(f"[EVENT_SLUG] Could not extract event slug from market slug: {market_slug_clean}")
        except Exception as e:
            logger.debug(f"[EVENT_SLUG] Failed to get event slug from Gamma API: {e}")
        
        return None
    
    def _get_market_slug(self, condition_id: str) -> str:
        """
        Get market slug from API
        
        IMPORTANT: We need market-level slug, not outcome-specific slug.
        Strategy:
        1. Try Gamma API first (most reliable for market-level slugs)
        2. Try CLOB API question_slug or market_slug
        3. Fallback to search
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
                            # Clean slug
                            slug = str(slug).strip().strip('/')
                            if 'polymarket.com' in slug:
                                slug = slug.split('polymarket.com/')[-1].strip('/')
                            if slug.startswith('event/'):
                                slug = slug[6:]
                            elif slug.startswith('market/'):
                                slug = slug[7:]
                            logger.info(f"[SLUG] Got market slug from Gamma API: {slug} (condition_id={condition_id[:20]}...)")
                            return slug
                # If no exact match, use first market's slug (they should share the same event slug)
                if markets:
                    slug = markets[0].get("slug", "")
                    if slug:
                        slug = str(slug).strip().strip('/')
                        if 'polymarket.com' in slug:
                            slug = slug.split('polymarket.com/')[-1].strip('/')
                        if slug.startswith('event/'):
                            slug = slug[6:]
                        elif slug.startswith('market/'):
                            slug = slug[7:]
                        logger.info(f"[SLUG] Got market slug from Gamma API (first market): {slug} (condition_id={condition_id[:20]}...)")
                        return slug
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
                    # Clean slug
                    slug = str(slug).strip().strip('/')
                    if 'polymarket.com' in slug:
                        slug = slug.split('polymarket.com/')[-1].strip('/')
                    if slug.startswith('event/'):
                        slug = slug[6:]
                    elif slug.startswith('market/'):
                        slug = slug[7:]
                    
                    logger.info(f"[SLUG] Got market slug from CLOB API: {slug} (condition_id={condition_id[:20]}...)")
                    return slug
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
                    slug = str(slug).strip().strip('/')
                    if 'polymarket.com' in slug:
                        slug = slug.split('polymarket.com/')[-1].strip('/')
                    if slug.startswith('event/'):
                        slug = slug[6:]
                    elif slug.startswith('market/'):
                        slug = slug[7:]
                    logger.info(f"[SLUG] Got market slug from data-api: {slug} (condition_id={condition_id[:20]}...)")
                    return slug
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
        
        Returns float on success, None on failure. Never raises exceptions.
        """
        # Step 0: Try new price_fetcher module (with all fallbacks, including wallet_prices)
        try:
            from price_fetcher import get_current_price as fetch_price
            logger.info(f"[Price] Trying price_fetcher module with wallet_prices fallback (provided {len(wallet_prices) if wallet_prices else 0} wallets)")
            result = fetch_price(condition_id=condition_id, outcome_index=outcome_index, wallet_prices=wallet_prices, slug=slug)
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
                                       window_minutes, min_consensus)

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
