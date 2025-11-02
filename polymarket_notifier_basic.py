"""
Alternative Polymarket Notifier Bot - No Playwright Version
Uses requests + BeautifulSoup for basic leaderboard scraping
"""

import os
import time
import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential
import requests
from bs4 import BeautifulSoup

# Import our modules
from db import PolymarketDB
from notify import TelegramNotifier

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('polymarket_notifier.log')
    ]
)
logger = logging.getLogger(__name__)

class PolymarketNotifierBasic:
    def __init__(self):
        # Configuration from environment
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.poll_interval = int(os.getenv("POLL_INTERVAL_SEC", "7"))
        self.alert_window_min = float(os.getenv("ALERT_WINDOW_MIN", "10"))
        self.min_consensus = int(os.getenv("MIN_CONSENSUS", "3"))
        self.max_wallets = int(os.getenv("MAX_WALLETS", "200"))
        self.max_predictions = int(os.getenv("MAX_PREDICTIONS", "1000"))
        self.db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
        
        # Leaderboard URLs to scrape (basic version - first page only)
        self.leaderboard_urls = [
            "https://polymarket.com/leaderboard/overall/monthly/profit",
        ]
        
        # Initialize components
        self.db = PolymarketDB(self.db_path)
        self.notifier = TelegramNotifier(self.telegram_token, self.telegram_chat_id)
        
        # Polymarket Data API endpoints
        self.data_api = "https://data-api.polymarket.com"
        self.trades_endpoint = f"{self.data_api}/trades"
        self.closed_positions_endpoint = f"{self.data_api}/closed-positions"
        self.traded_endpoint = f"{self.data_api}/traded"
        
        # Headers for API requests
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # Monitoring state
        self.monitoring = False
        self.loop_count = 0
        
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
        response = requests.get(url, params=params, headers=self.headers, timeout=20)
        response.raise_for_status()
        return response
    
    def scrape_leaderboard_basic(self, url: str) -> Dict[str, Dict[str, str]]:
        """
        Basic leaderboard scraping (first page only)
        This is a fallback when Playwright is not available
        """
        logger.info(f"Scraping leaderboard (basic): {url}")
        wallets = {}
        
        try:
            response = self.http_get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for profile links
            profile_links = soup.find_all('a', href=True)
            
            for link in profile_links:
                href = link.get('href', '')
                if '/profile/' in href:
                    # Extract address from href
                    tail = href.split('/profile/')[-1]
                    tail = tail.split('?')[0].split('#')[0]  # Remove query params
                    
                    # Check if it's a valid Ethereum address
                    if self._is_valid_address(tail):
                        display_text = link.get_text(strip=True) or tail
                        wallets[tail.lower()] = {
                            "display": display_text,
                            "source": url
                        }
            
            logger.info(f"Found {len(wallets)} wallets from {url}")
            return wallets
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {}
    
    def _is_valid_address(self, address: str) -> bool:
        """Check if string is a valid Ethereum address"""
        if not address.startswith('0x'):
            return False
        if len(address) != 42:
            return False
        try:
            int(address[2:], 16)
            return True
        except ValueError:
            return False
    
    def collect_wallets_from_leaderboards(self) -> Dict[str, Dict[str, str]]:
        """Collect wallet addresses from leaderboards (basic version)"""
        logger.info("Starting wallet collection from leaderboards (basic mode)...")
        
        all_wallets = {}
        for url in self.leaderboard_urls:
            wallets = self.scrape_leaderboard_basic(url)
            all_wallets.update(wallets)
        
        logger.info(f"Collected {len(all_wallets)} unique wallets from leaderboards")
        return all_wallets
    
    def get_total_traded(self, address: str) -> int:
        """Get total number of trades for a wallet"""
        try:
            response = self.http_get(self.traded_endpoint, params={"user": address})
            data = response.json()
            
            if isinstance(data, dict) and "traded" in data:
                return int(data["traded"])
            elif isinstance(data, list) and data:
                return int(data[0]["traded"])
            return 0
        except Exception as e:
            logger.warning(f"Failed to get traded total for {address}: {e}")
            return 0
    
    def get_closed_positions(self, address: str) -> List[Dict[str, Any]]:
        """Get closed positions for a wallet"""
        try:
            response = self.http_get(
                self.closed_positions_endpoint, 
                params={"user": address, "limit": 500, "offset": 0}
            )
            data = response.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning(f"Failed to get closed positions for {address}: {e}")
            return []
    
    def get_daily_trading_frequency(self, address: str) -> float:
        """Calculate average trades per day for a wallet"""
        try:
            response = self.http_get(
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
            return 0.0
    
    def compute_win_rate_and_pnl(self, closed_positions: List[Dict[str, Any]]) -> tuple[float, float]:
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
    
    def analyze_and_filter_wallets(self, wallets: Dict[str, Dict[str, str]]) -> int:
        """Analyze wallets and filter based on criteria"""
        logger.info(f"Analyzing {len(wallets)} wallets...")
        
        filtered_count = 0
        criteria = {
            "min_trades": 50,
            "min_win_rate": 0.65,
            "max_daily_freq": 10.0
        }
        
        for addr, meta in wallets.items():
            try:
                # Get wallet metrics
                traded = self.get_total_traded(addr)
                if traded < criteria["min_trades"]:
                    continue
                if traded > self.max_predictions:
                    logger.info(f"Skipping {addr}: {traded} trades (limit: {self.max_predictions})")
                    continue
                
                closed_positions = self.get_closed_positions(addr)
                win_rate, pnl_total = self.compute_win_rate_and_pnl(closed_positions)
                
                if win_rate <= criteria["min_win_rate"]:
                    continue
                if win_rate >= 0.99:
                    logger.info(f"Skipping {addr}: {win_rate:.1%} win rate (too high)")
                    continue
                
                daily_freq = self.get_daily_trading_frequency(addr)
                if daily_freq > criteria["max_daily_freq"]:
                    logger.info(f"Skipping {addr}: {daily_freq:.1f} trades/day (limit: {criteria['max_daily_freq']})")
                    continue
                
                # Store wallet in database
                self.db.upsert_wallet(
                    addr, meta["display"], traded, win_rate, 
                    pnl_total, daily_freq, meta["source"]
                )
                
                filtered_count += 1
                logger.info(f"Added {addr}: {traded} trades, {win_rate:.2%} win rate, {pnl_total:.2f} PnL")
                
            except Exception as e:
                logger.warning(f"Error analyzing wallet {addr}: {e}")
                continue
        
        # Clean up old wallets
        self.db.cleanup_old_wallets(self.max_predictions, self.max_wallets)
        
        logger.info(f"Filtered to {filtered_count} wallets meeting criteria")
        
        # Send summary notification
        self.notifier.send_wallet_collection_summary(
            len(wallets), filtered_count, criteria
        )
        
        return filtered_count
    
    def get_new_buys(self, address: str, last_seen_trade_id: Optional[str]) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """Get new buy trades for a wallet"""
        try:
            params = {"user": address, "side": "BUY", "limit": 50}
            response = self.http_get(self.trades_endpoint, params=params)
            trades = response.json() if response.ok else []
            
            new_events = []
            newest_id = last_seen_trade_id
            
            for trade in trades:
                trade_id = str(trade.get("id") or trade.get("tradeId") or 
                             trade.get("_id") or trade.get("transactionHash") or "")
                
                if not trade_id:
                    continue
                
                if last_seen_trade_id and trade_id == last_seen_trade_id:
                    break
                
                condition_id = trade.get("conditionId") or trade.get("market") or trade.get("marketId")
                outcome_index = trade.get("outcomeIndex")
                
                if not condition_id or outcome_index is None:
                    continue
                
                timestamp = trade.get("timestamp") or trade.get("createdAt")
                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
                    except Exception:
                        timestamp = time.time()
                elif timestamp is None:
                    timestamp = time.time()
                
                new_events.append({
                    "trade_id": trade_id,
                    "conditionId": condition_id,
                    "outcomeIndex": int(outcome_index),
                    "timestamp": float(timestamp)
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
            logger.warning(f"Error getting new buys for {address}: {e}")
            return [], last_seen_trade_id
    
    def check_consensus_and_alert(self, condition_id: str, outcome_index: int, 
                                 wallet: str, trade_id: str, timestamp: float):
        """Check for consensus and send alert if threshold met"""
        try:
            # Update rolling window
            key, window_data = self.db.update_rolling_window(
                condition_id, outcome_index, wallet, trade_id, timestamp, self.alert_window_min
            )
            
            # Get unique wallets in window
            wallets_in_window = sorted({e["wallet"] for e in window_data.get("events", [])})
            
            if len(wallets_in_window) < self.min_consensus:
                return
            
            # Check if alert already sent
            if self.db.is_alert_sent(condition_id, outcome_index, 
                                    window_data["first_ts"], window_data["last_ts"]):
                return
            
            # Send alert
            alert_id = key[:8]
            success = self.notifier.send_consensus_alert(
                condition_id, outcome_index, wallets_in_window,
                self.alert_window_min, self.min_consensus, alert_id
            )
            
            if success:
                # Mark alert as sent
                self.db.mark_alert_sent(
                    condition_id, outcome_index, len(wallets_in_window),
                    window_data["first_ts"], window_data["last_ts"]
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
                # Get tracked wallets
                wallets = self.db.get_tracked_wallets(
                    min_trades=50, max_trades=self.max_predictions,
                    min_win_rate=0.65, max_win_rate=0.99,
                    max_daily_freq=10.0, limit=self.max_wallets
                )
                
                if not wallets:
                    logger.warning("No wallets to monitor")
                    time.sleep(self.poll_interval)
                    continue
                
                self.loop_count += 1
                
                # Send heartbeat every 10 loops
                if self.loop_count % 10 == 0:
                    stats = self.db.get_wallet_stats()
                    logger.info(f"Monitoring {len(wallets)} wallets, loop #{self.loop_count}")
                    self.notifier.send_heartbeat(stats)
                
                # Monitor each wallet
                for wallet in wallets:
                    try:
                        last_trade_id = self.db.get_last_seen_trade_id(wallet)
                        new_events, newest_id = self.get_new_buys(wallet, last_trade_id)
                        
                        if new_events:
                            logger.info(f"{wallet}: {len(new_events)} new events")
                        
                        # Process each new event
                        for event in new_events:
                            self.check_consensus_and_alert(
                                event["conditionId"], event["outcomeIndex"],
                                wallet, event["trade_id"], event["timestamp"]
                            )
                        
                        # Update last seen trade ID
                        if newest_id and newest_id != last_trade_id:
                            self.db.set_last_seen_trade_id(wallet, newest_id)
                        
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
    
    def run(self):
        """Main run method"""
        logger.info("Starting Polymarket Notifier Bot (Basic Version)...")
        
        # Validate configuration
        if not self.validate_config():
            return
        
        # Test Telegram connection
        if not self.notifier.test_connection():
            logger.error("Telegram connection test failed")
            return
        
        # Send startup notification
        stats = self.db.get_wallet_stats()
        self.notifier.send_startup_notification(
            stats.get('total_wallets', 0),
            stats.get('tracked_wallets', 0)
        )
        
        # Collect wallets from leaderboards
        wallets = self.collect_wallets_from_leaderboards()
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

def main():
    """Main entry point"""
    notifier = PolymarketNotifierBasic()
    
    try:
        notifier.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")

if __name__ == "__main__":
    main()
