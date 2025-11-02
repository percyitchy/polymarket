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

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None, reports_chat_id: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")  # public signals
        # admin/reports channel; default to provided id if env not set
        self.reports_chat_id = reports_chat_id or os.getenv("TELEGRAM_REPORTS_CHAT_ID", "-1002792658553")
        # Topic ID for forum groups (optional)
        topic_id_str = os.getenv("TELEGRAM_TOPIC_ID")
        self.topic_id = int(topic_id_str) if topic_id_str and topic_id_str.isdigit() else None
        
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram credentials not configured. Notifications will be printed to console.")
    
    def send_message(self, text: str, parse_mode: str = "Markdown", 
                    disable_web_page_preview: bool = True,
                    reply_markup: Optional[Dict[str, Any]] = None,
                    chat_id: Optional[str] = None,
                    message_thread_id: Optional[int] = None) -> bool:
        """
        Send a message to Telegram
        
        Args:
            text: Message text
            parse_mode: HTML or Markdown
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
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id
        
        try:
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            logger.info("Telegram message sent successfully")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram message: {e}")
            return False
    
    def send_consensus_alert(self, condition_id: str, outcome_index: int, 
                           wallets: List[str], wallet_prices: Dict[str, float] = {},
                           window_minutes: float = 10.0, min_consensus: int = 3, 
                           alert_id: str = "", market_title: str = "", 
                           market_slug: str = "", side: str = "BUY",
                           consensus_events: Optional[int] = None,
                           total_usd: Optional[float] = None) -> bool:
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
            logger.warning(f"Not enough wallets for consensus: {len(wallets)} < {min_consensus}")
            return False
        
        # We will render specific trader lines below (Markdown)
        # Calculate consensus strength
        strength = self._calculate_consensus_strength(len(wallets), window_minutes)
        
        # Format market URL - Polymarket uses /market/{slug} (singular, not markets)
        # This is the correct format that redirects to actual market page
        if market_slug:
            market_url = f"https://polymarket.com/market/{market_slug}"
        else:
            # Fallback: try to get slug from API
            slug = self._get_market_slug(condition_id)
            if slug:
                market_url = f"https://polymarket.com/market/{slug}"
            else:
                # Last resort: use condition_id (might redirect to search)
                market_url = f"https://polymarket.com/markets/{condition_id}"
        
        # Current timestamp
        timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        
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
        
        # Fetch current price from orderbook/market data
        current_price = self._get_current_price(condition_id, outcome_index)
        
        # CRITICAL FINAL CHECK: Don't send alerts for resolved markets (price = 1.0 or 0.0)
        if current_price is not None:
            price_val = float(current_price)
            logger.info(f"[NOTIFY PRICE CHECK] condition={condition_id}, outcome={outcome_index}, price={price_val}")
            # Block resolved markets (price >= 0.999 or <= 0.001)
            if price_val >= 0.999 or price_val <= 0.001:
                logger.error(f"[NOTIFY] BLOCKING: resolved market price={price_val}, condition={condition_id}, outcome={outcome_index}")
                # Send suppressed alert details to reports
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
                        total_usd=total_usd
                    )
                except Exception as e:
                    logger.debug(f"Failed to send suppressed alert details: {e}")
                return False
            # Block closed markets (price >= 0.98 or <= 0.02)
            if price_val >= 0.98 or price_val <= 0.02:
                logger.error(f"[NOTIFY] BLOCKING: closed market price={price_val}, condition={condition_id}, outcome={outcome_index}")
                # Send suppressed alert details to reports
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
            # Price is None - block to be safe
            logger.error(f"[NOTIFY] BLOCKING: price is None, condition={condition_id}, outcome={outcome_index}")
            # Send suppressed alert details to reports
            try:
                self.send_suppressed_alert_details(
                    reason="price_none",
                    condition_id=condition_id,
                    outcome_index=outcome_index,
                    wallets=wallets,
                    wallet_prices=wallet_prices,
                    market_title=market_title,
                    market_slug=market_slug,
                    current_price=None,
                    side=side,
                    total_usd=total_usd
                )
            except Exception as e:
                logger.debug(f"Failed to send suppressed alert details: {e}")
            return False

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

        message = f"""{header}

🎯 Market: {market_title}
{total_line}

*Outcome:* {position_display}
👤 Traders involved:

{chr(10).join(wallet_info)}

Current price: *{current_price_str}*

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
        
        return self.send_message(message, reply_markup=reply_markup, chat_id=self.chat_id, message_thread_id=self.topic_id)
    
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
    
    def send_suppressed_alert_details(self, reason: str, condition_id: str, outcome_index: int,
                                     wallets: List[str], wallet_prices: Dict[str, float] = {},
                                     market_title: str = "", market_slug: str = "",
                                     current_price: Optional[float] = None,
                                     side: str = "BUY", total_usd: Optional[float] = None) -> bool:
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
        """
        # Build market URL
        if market_slug:
            market_url = f"https://polymarket.com/event/{market_slug}"
        else:
            market_url = f"https://polymarket.com/event/{condition_id}"
        
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
        message = f"""📈 *Wallet Collection Complete*

📊 *Collection Results:*
• Wallets found: {total_found}
• Wallets meeting criteria: {filtered_count}
• Min trades: {criteria.get('min_trades', 50)}
• Min win rate: {criteria.get('min_win_rate', 0.65):.1%}
• Max daily frequency: {criteria.get('max_daily_freq', 10.0)}

_{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC_"""
        
        return self.send_message(message, chat_id=self.reports_chat_id)
    
    def _get_market_slug(self, condition_id: str) -> str:
        """Get market slug from API"""
        try:
            import requests
            
            # Try CLOB API first (most reliable for markets)
            url = f"https://clob.polymarket.com/markets/{condition_id}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                slug = data.get('market_slug') or data.get('slug')
                if slug:
                    return slug
                    
        except Exception as e:
            logger.debug(f"Failed to get market slug from API: {e}")
        
        return ""
    
    def _get_outcome_name(self, condition_id: str, outcome_index: int) -> str:
        """Get outcome name (Yes/No/etc) from API"""
        try:
            import requests
            
            # Try CLOB API
            url = f"https://clob.polymarket.com/markets/{condition_id}"
            response = requests.get(url, timeout=5)
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
            import requests
            
            # Try CLOB API first (most reliable for markets)
            url2 = f"https://clob.polymarket.com/markets/{condition_id}"
            response2 = requests.get(url2, timeout=5)
            if response2.status_code == 200:
                data = response2.json()
                # Try multiple possible title fields
                title = data.get('title') or data.get('question') or data.get('name')
                if title:
                    return title
            
            # Try Data API as fallback
            url = f"https://data-api.polymarket.com/condition/{condition_id}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                title = data.get('title') or data.get('question') or data.get('name')
                if title:
                    return title
                    
        except Exception as e:
            logger.debug(f"Failed to get market title from API: {e}")
        
        # Fallback to truncated condition ID
        return f"{condition_id[:10]}..."

    def _get_current_price(self, condition_id: str, outcome_index: int) -> Optional[float]:
        """Try to fetch current last price for the given market outcome from CLOB API"""
        try:
            import requests
            url = f"https://clob.polymarket.com/markets/{condition_id}"
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                return None
            data = resp.json()
            # Try token-specific price fields
            tokens = data.get('tokens') or []
            if tokens and outcome_index < len(tokens):
                token = tokens[outcome_index]
                for key in ("last_price", "price", "mark_price"):  # best-effort
                    val = token.get(key)
                    if val is not None:
                        try:
                            price = float(val)
                            # Return 0.0 explicitly if price is 0 (not None)
                            return price
                        except (ValueError, TypeError):
                            continue
            # Fallback to market-level fields if present
            for key in ("last_price", "price", "mark_price"):
                val = data.get(key)
                if val is not None:
                    try:
                        price = float(val)
                        return price
                    except (ValueError, TypeError):
                        continue
        except Exception as e:
            logger.debug(f"Failed to get current price: {e}")
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
