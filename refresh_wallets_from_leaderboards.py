#!/usr/bin/env python3
"""
Refresh wallets from Polymarket leaderboards (week/month)
Scans leaderboards and adds qualifying wallets to the analysis queue
"""

import asyncio
import os
import logging
from dotenv import load_dotenv

# Import from main notifier
from polymarket_notifier import PolymarketNotifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('refresh_wallets.log')
    ]
)
logger = logging.getLogger(__name__)

async def main():
    """Main function to refresh wallets from leaderboards"""
    load_dotenv()
    
    logger.info("=" * 60)
    logger.info("Starting wallet refresh from Polymarket leaderboards")
    logger.info("=" * 60)
    
    # Initialize notifier
    notifier = PolymarketNotifier()
    
    # Configure to scan only week and month leaderboards
    notifier.leaderboard_urls = [
        "https://polymarket.com/leaderboard/overall/weekly/profit",
        "https://polymarket.com/leaderboard/overall/monthly/profit"
    ]
    
    logger.info(f"Scanning leaderboards: {notifier.leaderboard_urls}")
    
    # Start wallet analyzer workers
    notifier.wallet_analyzer.start_workers()
    
    try:
        # Collect wallets from leaderboards
        wallets = await notifier.collect_wallets_from_leaderboards()
        
        if not wallets:
            logger.warning("No wallets collected from leaderboards")
            return
        
        logger.info(f"Collected {len(wallets)} unique wallets from leaderboards")
        
        # Add wallets to analysis queue
        added_count = notifier.analyze_and_filter_wallets(wallets)
        
        logger.info(f"Added {added_count} wallets to analysis queue")
        
        # Get queue status
        queue_status = notifier.wallet_analyzer.get_queue_status()
        logger.info(f"Queue status: {queue_status}")
        
        logger.info("=" * 60)
        logger.info("Wallet refresh completed successfully")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error during wallet refresh: {e}", exc_info=True)
    finally:
        # Stop wallet analyzer workers
        notifier.wallet_analyzer.stop_workers()

if __name__ == "__main__":
    asyncio.run(main())

