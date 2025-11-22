#!/usr/bin/env python3
"""
Telegram alerts for matching bets from multiple wallets
"""

import asyncio
import aiohttp
import logging
import os
from typing import Dict, List, Set, Tuple, Optional, Union
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import json


def normalize_timestamp(timestamp_value: Union[int, float, str]) -> datetime:
    """
    Normalize timestamp to datetime, handling both seconds and milliseconds.
    
    This function ensures consistent timestamp parsing across the codebase.
    It detects if a numeric timestamp is in milliseconds (values > 1e10) and
    converts to seconds before creating the datetime object.
    
    Args:
        timestamp_value: Timestamp as int, float, or ISO-8601 string
        
    Returns:
        datetime: Normalized datetime object in UTC timezone
    """
    if isinstance(timestamp_value, (int, float)):
        # Detect milliseconds: values > 1e10 are likely milliseconds
        if timestamp_value > 1e10:
            # Convert milliseconds to seconds
            timestamp_value = timestamp_value / 1000
        timestamp = datetime.fromtimestamp(timestamp_value, tz=timezone.utc)
    elif isinstance(timestamp_value, str):
        # ISO string - support trailing Z
        timestamp = datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
    else:
        # Fallback to current time
        timestamp = datetime.now(timezone.utc)
    
    return timestamp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class BetPosition:
    """Represents a betting position"""
    wallet_address: str
    market_id: str
    market_title: str
    outcome: str
    outcome_index: int
    amount: float
    price: float
    timestamp: datetime
    position_type: str  # 'buy' or 'sell'

@dataclass
class MatchingBet:
    """Represents a group of matching bets"""
    market_id: str
    market_title: str
    outcome: str
    outcome_index: int
    side: str  # 'buy' or 'sell' - actual trade direction
    wallets: List[str]
    total_amount: float
    avg_price: float
    first_seen: datetime
    last_seen: datetime

class TelegramNotifier:
    """Handles Telegram notifications"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def send_message(self, message: str, parse_mode: str = "HTML", max_retries: int = 3) -> bool:
        """Send message to Telegram channel with retry logic for rate limiting"""
        url = f"{self.api_url}/sendMessage"
        data = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        
        for attempt in range(max_retries):
            try:
                async with self.session.post(url, json=data) as response:
                    if response.status == 200:
                        logger.info("✅ Telegram message sent successfully")
                        return True
                    elif response.status == 429:
                        # Rate limited - get retry_after from response
                        try:
                            error_data = await response.json()
                            retry_after = error_data.get("parameters", {}).get("retry_after", 60)
                            logger.warning(f"⏳ Telegram rate limited (attempt {attempt + 1}/{max_retries}), retry after {retry_after} seconds")
                            
                            # If this is not the last attempt, wait and retry
                            if attempt < max_retries - 1:
                                await asyncio.sleep(retry_after)
                                continue  # Retry
                            else:
                                logger.error(f"❌ Telegram rate limit exceeded after {max_retries} attempts")
                                return False
                        except Exception as e:
                            logger.warning(f"⏳ Telegram rate limited, but failed to parse retry_after: {e}")
                            # Default wait time if we can't parse the response
                            if attempt < max_retries - 1:
                                await asyncio.sleep(60)
                                continue  # Retry
                            else:
                                return False
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Failed to send Telegram message: {response.status} - {error_text}")
                        # Non-429 errors are not retryable
                        return False
                        
            except Exception as e:
                logger.error(f"❌ Error sending Telegram message (attempt {attempt + 1}/{max_retries}): {e}")
                # For network errors, retry with exponential backoff
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return False
        
        # All retries exhausted
        logger.error(f"❌ Failed to send Telegram message after {max_retries} attempts")
        return False
    
class BetDetector:
    """Detects matching bets from multiple wallets"""
    
    def __init__(self, db_path: str = "polymarket_notifier.db"):
        self.db_path = db_path
        self.active_positions: Dict[str, List[BetPosition]] = {}
        self.matching_bets: Dict[str, MatchingBet] = {}
        self.sent_alerts: Set[str] = set()
        
        # Configuration - handle inline comments in env vars
        def _get_int(key, default):
            val = os.getenv(key, str(default))
            if '#' in val:
                val = val.split('#')[0]
            return int(val.strip())
        
        # Configuration - handle inline comments in env vars
        def _get_int(key, default):
            val = os.getenv(key, str(default))
            if '#' in val:
                val = val.split('#')[0]
            return int(val.strip())
        
        def _get_float(key, default):
            val = os.getenv(key, str(default))
            if '#' in val:
                val = val.split('#')[0]
            return float(val.strip())
        
        self.min_consensus = _get_int('MIN_CONSENSUS', 2)
        self.alert_window_min = _get_float('ALERT_WINDOW_MIN', 15.0)
        self.poll_interval = _get_int('POLL_INTERVAL_SEC', 7)
        
        # Polymarket API endpoints
        self.data_api = "https://data-api.polymarket.com"
        self.trades_endpoint = f"{self.data_api}/trades"
        
    async def get_recent_trades(self, wallet_address: str, session: aiohttp.ClientSession, limit: int = 50) -> List[Dict]:
        """Get recent trades for a wallet using a shared session"""
        try:
            url = self.trades_endpoint
            params = {
                "user": wallet_address,
                "limit": limit,
                "sort": "timestamp",
                "order": "desc"
            }
            
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data if isinstance(data, list) else []
                else:
                    logger.warning(f"Failed to get trades for {wallet_address}: {response.status}")
                    return []
                    
        except Exception as e:
            logger.warning(f"Error getting trades for {wallet_address}: {e}")
            return []
    
    def parse_trade_to_position(self, trade: Dict, wallet_address: str) -> Optional[BetPosition]:
        """Parse trade data to BetPosition"""
        try:
            # Extract market information
            market_id = trade.get("conditionId", "")
            market_title = trade.get("title", "Unknown Market")
            
            # Extract outcome information
            outcome = trade.get("outcome", "")
            outcome_index = trade.get("outcomeIndex", 0)
            
            # Extract trade details
            amount = float(trade.get("amount", 0))
            price = float(trade.get("price", 0))
            
            # Determine position type - only treat explicit "buy" or "sell" as valid
            side = trade.get("side", "").lower()
            if side == "buy":
                position_type = "buy"
            elif side == "sell":
                position_type = "sell"
            else:
                # Unknown or missing trade side - skip this trade
                logger.debug(f"Skipping trade with unknown/missing side: {trade.get('side')}")
                return None
            
            # Parse timestamp using normalized helper function
            timestamp_value = trade.get("timestamp", "")
            if timestamp_value:
                timestamp = normalize_timestamp(timestamp_value)
            else:
                timestamp = datetime.now(timezone.utc)
            
            return BetPosition(
                wallet_address=wallet_address,
                market_id=market_id,
                market_title=market_title,
                outcome=outcome,
                outcome_index=outcome_index,
                amount=amount,
                price=price,
                timestamp=timestamp,
                position_type=position_type
            )
            
        except Exception as e:
            logger.warning(f"Error parsing trade: {e}")
            return None
    
    def detect_matching_bets(self, positions: List[BetPosition]) -> List[MatchingBet]:
        """Detect matching bets from positions"""
        matching_bets = []
        
        # Group positions by market, outcome, AND side (trade direction)
        # This ensures buys and sells are not mixed into a single consensus group
        market_groups: Dict[str, List[BetPosition]] = {}
        
        for position in positions:
            # Include side in the grouping key
            key = f"{position.market_id}_{position.outcome_index}_{position.position_type}"
            if key not in market_groups:
                market_groups[key] = []
            market_groups[key].append(position)
        
        # Check for matching bets
        for key, group_positions in market_groups.items():
            if len(group_positions) >= self.min_consensus:
                # Filter by recent time window
                now = datetime.now(timezone.utc)
                recent_positions = [
                    p for p in group_positions 
                    if (now - p.timestamp).total_seconds() <= self.alert_window_min * 60
                ]
                
                if len(recent_positions) >= self.min_consensus:
                    # Create matching bet
                    wallets = list(set(p.wallet_address for p in recent_positions))
                    total_amount = sum(p.amount for p in recent_positions)
                    avg_price = sum(p.price for p in recent_positions) / len(recent_positions)
                    
                    # Determine side from the actual trade direction (all positions in group have same side)
                    side = recent_positions[0].position_type
                    
                    matching_bet = MatchingBet(
                        market_id=recent_positions[0].market_id,
                        market_title=recent_positions[0].market_title,
                        outcome=recent_positions[0].outcome,
                        outcome_index=recent_positions[0].outcome_index,
                        side=side,
                        wallets=wallets,
                        total_amount=total_amount,
                        avg_price=avg_price,
                        first_seen=min(p.timestamp for p in recent_positions),
                        last_seen=max(p.timestamp for p in recent_positions)
                    )
                    
                    matching_bets.append(matching_bet)
        
        return matching_bets
    
    def _get_wallet_winrate(self, wallet_address: str) -> str:
        """Get wallet winrate from database if available"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT win_rate FROM wallets WHERE address = ?', (wallet_address,))
            result = cursor.fetchone()
            conn.close()
            if result and result[0]:
                return f"{result[0]:.1%}"
            return "Unknown"
        except:
            return "Unknown"
    
    def format_matching_bet_alert(self, matching_bet: MatchingBet) -> str:
        """Format matching bet alert message in Pro Signal style"""
        
        # Use the actual trade side from the aggregated MatchingBet instance
        # This reflects what traders actually did (buy or sell)
        side = matching_bet.side.upper() if matching_bet.side else "UNKNOWN"
        
        # Get wallet info with winrates
        wallet_info = []
        for i, wallet in enumerate(matching_bet.wallets[:4], 1):
            try:
                import sqlite3
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT win_rate FROM wallets WHERE address = ?', (wallet,))
                result = cursor.fetchone()
                conn.close()
                
                short_addr = f"{wallet[:8]}...{wallet[-4:]}"
                if result and result[0]:
                    winrate = f"{result[0]:.1%}"
                    wallet_info.append(f"{i}. <code>{short_addr}</code> • WR: {winrate}")
                else:
                    wallet_info.append(f"{i}. <code>{short_addr}</code>")
            except:
                short_addr = f"{wallet[:8]}...{wallet[-4:]}"
                wallet_info.append(f"{i}. <code>{short_addr}</code>")
        
        # Build message
        message = f"""
🔥 <b>Consensus Signal Detected ({len(matching_bet.wallets)} wallets)</b>

🎯 <b>Market:</b> {matching_bet.market_title}
🔗 <a href="https://polymarket.com/market/{matching_bet.market_id}">View Market</a>

🛒 <b>Position:</b> {side} @ {matching_bet.avg_price:.3f}
<b>Outcome:</b> {matching_bet.outcome}
💵 <b>Combined Size:</b> ${matching_bet.total_amount:,.0f} USDC

👤 <b>Traders involved:</b>

{chr(10).join(wallet_info)}

📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
        """.strip()
        
        return message
    
    async def check_wallet_positions(self, wallet_address: str, session: aiohttp.ClientSession) -> List[BetPosition]:
        """Check recent positions for a wallet using a shared session"""
        trades = await self.get_recent_trades(wallet_address, session)
        positions = []
        
        for trade in trades:
            position = self.parse_trade_to_position(trade, wallet_address)
            if position:
                positions.append(position)
        
        return positions
    
    async def monitor_wallets(self, wallet_addresses: List[str], telegram_notifier: TelegramNotifier):
        """Monitor wallets for matching bets with concurrent requests"""
        logger.info(f"Starting monitoring of {len(wallet_addresses)} wallets...")
        
        # Concurrency limit to avoid overwhelming the API
        MAX_CONCURRENT_REQUESTS = 10
        
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    all_positions = []
                    
                    # Create semaphore to limit concurrent requests
                    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
                    
                    async def fetch_wallet_positions(wallet_address: str) -> List[BetPosition]:
                        """Fetch positions for a single wallet with concurrency control"""
                        async with semaphore:
                            return await self.check_wallet_positions(wallet_address, session)
                    
                    # Fetch positions for all wallets concurrently
                    tasks = [fetch_wallet_positions(wallet) for wallet in wallet_addresses]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Collect positions from all results
                    for result in results:
                        if isinstance(result, Exception):
                            logger.warning(f"Error fetching wallet positions: {result}")
                        elif isinstance(result, list):
                            all_positions.extend(result)
                    
                    # Detect matching bets
                    matching_bets = self.detect_matching_bets(all_positions)
                    
                    # Send alerts for new matching bets
                    for matching_bet in matching_bets:
                        # Include side in alert key so BUY and SELL consensus are treated as distinct alerts
                        alert_key = f"{matching_bet.market_id}_{matching_bet.outcome_index}_{matching_bet.side}_{len(matching_bet.wallets)}"
                        
                        if alert_key not in self.sent_alerts:
                            message = self.format_matching_bet_alert(matching_bet)
                            success = await telegram_notifier.send_message(message)
                            
                            if success:
                                self.sent_alerts.add(alert_key)
                                logger.info(f"🚨 Alert sent for {matching_bet.market_title} - {matching_bet.outcome}")
                    
                    # Clean old alerts (older than 1 hour)
                    self.cleanup_old_alerts()
                    
                    # Wait before next check
                    await asyncio.sleep(self.poll_interval)
                    
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    await asyncio.sleep(self.poll_interval)
    
    def cleanup_old_alerts(self):
        """Clean up old alerts to prevent memory leaks"""
        # Keep only recent alerts (last 100)
        if len(self.sent_alerts) > 100:
            self.sent_alerts = set(list(self.sent_alerts)[-100:])

async def main():
    """Main function to start bet monitoring"""
    
    # Load configuration
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        logger.error("❌ Missing Telegram configuration. Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return
    
    # Load wallet addresses from our database
    import sqlite3
    db_path = os.getenv('DB_PATH', 'polymarket_notifier.db')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT address FROM wallets ORDER BY realized_pnl_total DESC LIMIT 50")
        wallet_addresses = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        logger.info(f"Loaded {len(wallet_addresses)} wallets from database")
        
    except Exception as e:
        logger.error(f"Error loading wallets from database: {e}")
        return
    
    # Initialize components
    bet_detector = BetDetector(db_path)
    
    async with TelegramNotifier(bot_token, chat_id) as telegram_notifier:
        # Send startup message
        startup_message = f"""
🤖 <b>Polymarket Bet Monitor Started</b>

👥 Monitoring: {len(wallet_addresses)} wallets
🎯 Min Consensus: {bet_detector.min_consensus} wallets
⏰ Alert Window: {bet_detector.alert_window_min} minutes
🔄 Poll Interval: {bet_detector.poll_interval} seconds

Ready to detect matching bets! 🚨
        """.strip()
        
        await telegram_notifier.send_message(startup_message)
        
        # Start monitoring
        await bet_detector.monitor_wallets(wallet_addresses, telegram_notifier)

if __name__ == "__main__":
    asyncio.run(main())
