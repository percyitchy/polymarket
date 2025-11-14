#!/usr/bin/env python3
"""
Daily wallet refresh script
Collects new wallets from all sources and adds them to analysis queue
Designed to run daily via systemd timer or cron
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import PolymarketDB
from wallet_analyzer import WalletAnalyzer, AnalysisConfig
from notify import TelegramNotifier
from polymarket_notifier import PolymarketNotifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('daily_wallet_refresh.log')
    ]
)
logger = logging.getLogger(__name__)

async def main():
    """Main function for daily wallet refresh"""
    load_dotenv()
    
    start_time = datetime.now(timezone.utc)
    logger.info("=" * 80)
    logger.info("🚀 Starting daily wallet refresh")
    logger.info(f"Started at: {start_time.isoformat()}")
    logger.info("=" * 80)
    
    db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
    db = PolymarketDB(db_path)
    
    # Initialize notifier for Telegram alerts
    notifier = TelegramNotifier()
    
    # Get initial stats
    initial_stats = db.get_wallet_stats()
    initial_queue = db.get_queue_stats()
    
    logger.info(f"Initial state:")
    logger.info(f"  - Total wallets: {initial_stats.get('total_wallets', 0)}")
    logger.info(f"  - Tracked wallets: {initial_stats.get('tracked_wallets', 0)}")
    logger.info(f"  - Queue pending: {initial_queue.get('pending_jobs', 0)}")
    
    try:
        # Initialize notifier for wallet collection
        polymarket_notifier = PolymarketNotifier()
        
        # Configure leaderboard URLs (weekly and monthly, first 20 pages each)
        polymarket_notifier.leaderboard_urls = [
            "https://polymarket.com/leaderboard/overall/weekly/profit",
            "https://polymarket.com/leaderboard/overall/monthly/profit"
        ]
        
        # Start wallet analyzer workers
        logger.info("Starting wallet analyzer workers...")
        polymarket_notifier.wallet_analyzer.start_workers()
        
        total_collected = 0
        total_added = 0
        
        # Source 1: polymarketanalytics.com
        try:
            logger.info("=" * 80)
            logger.info("📊 Collecting from polymarketanalytics.com...")
            logger.info("=" * 80)
            
            analytics_limit = int(os.getenv("POLYMARKET_ANALYTICS_CHECK_LIMIT", "2500"))
            wallets_analytics = await polymarket_notifier.collect_wallets_from_polymarket_analytics(limit=analytics_limit)
            
            if wallets_analytics:
                logger.info(f"Collected {len(wallets_analytics)} wallets from polymarketanalytics.com")
                added_analytics = polymarket_notifier.analyze_and_filter_wallets(wallets_analytics)
                total_collected += len(wallets_analytics)
                total_added += added_analytics
                logger.info(f"Added {added_analytics} new wallets from polymarketanalytics.com")
            else:
                logger.warning("No wallets collected from polymarketanalytics.com")
        except Exception as e:
            logger.error(f"Error collecting from polymarketanalytics.com: {e}", exc_info=True)
        
        # Source 2: Polymarket leaderboards
        try:
            logger.info("=" * 80)
            logger.info("📊 Collecting from Polymarket leaderboards...")
            logger.info("=" * 80)
            
            wallets_leaderboards = await polymarket_notifier.collect_wallets_from_leaderboards()
            
            if wallets_leaderboards:
                logger.info(f"Collected {len(wallets_leaderboards)} wallets from leaderboards")
                added_leaderboards = polymarket_notifier.analyze_and_filter_wallets(wallets_leaderboards)
                total_collected += len(wallets_leaderboards)
                total_added += added_leaderboards
                logger.info(f"Added {added_leaderboards} new wallets from leaderboards")
            else:
                logger.warning("No wallets collected from leaderboards")
        except Exception as e:
            logger.error(f"Error collecting from leaderboards: {e}", exc_info=True)
        
        # Get final stats
        final_stats = db.get_wallet_stats()
        final_queue = db.get_queue_stats()
        
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        logger.info("=" * 80)
        logger.info("✅ Daily wallet refresh completed")
        logger.info("=" * 80)
        logger.info(f"Results:")
        logger.info(f"  - Total collected: {total_collected}")
        logger.info(f"  - New wallets added to queue: {total_added}")
        logger.info(f"  - Final tracked wallets: {final_stats.get('tracked_wallets', 0)}")
        logger.info(f"  - Queue pending: {final_queue.get('pending_jobs', 0)}")
        logger.info(f"  - Time elapsed: {elapsed:.1f} seconds")
        logger.info("=" * 80)
        
        # Send summary to Telegram
        summary_message = f"""📅 *Daily Wallet Refresh Complete*

📊 *Results:*
• Wallets collected: {total_collected}
• New wallets added: {total_added}
• Tracked wallets: {final_stats.get('tracked_wallets', 0)}
• Queue pending: {final_queue.get('pending_jobs', 0)}
• Time: {elapsed:.1f}s

✅ Refresh completed successfully"""
        
        target_chat = notifier.reports_chat_id if hasattr(notifier, 'reports_chat_id') and notifier.reports_chat_id else notifier.chat_id
        if target_chat != notifier.chat_id:
            temp_notifier = TelegramNotifier(chat_id=target_chat)
            temp_notifier.send_message(summary_message)
        else:
            notifier.send_message(summary_message)
        
    except Exception as e:
        logger.error(f"Critical error during daily refresh: {e}", exc_info=True)
        
        # Send error notification
        error_message = f"""❌ *Daily Wallet Refresh Failed*

*Error:* `{str(e)[:200]}`

Please check logs for details."""
        
        target_chat = notifier.reports_chat_id if hasattr(notifier, 'reports_chat_id') and notifier.reports_chat_id else notifier.chat_id
        if target_chat != notifier.chat_id:
            temp_notifier = TelegramNotifier(chat_id=target_chat)
            temp_notifier.send_message(error_message)
        else:
            notifier.send_message(error_message)
        raise
    
    finally:
        # Stop wallet analyzer workers
        try:
            polymarket_notifier.wallet_analyzer.stop_workers()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(main())

