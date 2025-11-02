#!/usr/bin/env python3
"""
Periodic check for new wallets from polymarketanalytics.com
Runs every 12 hours to check for new wallets and add them to analysis queue
"""

import os
import sys
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import PolymarketDB
from wallet_analyzer import WalletAnalyzer, AnalysisConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_new_wallets_from_analytics(limit: int = 2000):
    """Check for new wallets from polymarketanalytics.com and add to queue"""
    load_dotenv()
    
    db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
    db = PolymarketDB(db_path)
    
    logger.info("=" * 60)
    logger.info("Checking for new wallets from polymarketanalytics.com")
    logger.info("=" * 60)
    
    try:
        # Fetch addresses from API
        from fetch_polymarket_analytics_api import fetch_traders_from_api
        
        logger.info(f"Fetching up to {limit} addresses from polymarketanalytics.com...")
        addresses = fetch_traders_from_api(target=limit)
        
        if not addresses:
            logger.warning("No addresses fetched from polymarketanalytics.com")
            return
        
        logger.info(f"Fetched {len(addresses)} addresses")
        
        # Check which ones are new (not in database)
        new_count = 0
        already_exists = 0
        
        for addr in addresses:
            addr_lower = addr.lower()
            
            # Check if wallet already exists in database
            existing = db.get_wallet(addr_lower)
            if existing:
                already_exists += 1
                continue
            
            # Check if already in analysis queue
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM wallet_analysis_jobs WHERE address = ?",
                    (addr_lower,)
                )
                in_queue = cursor.fetchone()[0] > 0
            
            if in_queue:
                already_exists += 1
                continue
            
            # Add to analysis queue
            if db.add_wallet_to_queue(addr_lower, display=addr_lower, source="polymarket_analytics_periodic"):
                new_count += 1
        
        logger.info(f"✅ Check complete:")
        logger.info(f"   - Total fetched: {len(addresses)}")
        logger.info(f"   - New wallets added to queue: {new_count}")
        logger.info(f"   - Already exists: {already_exists}")
        
        # Get queue status
        analyzer = WalletAnalyzer(db, AnalysisConfig())
        queue_stats = analyzer.get_queue_status()
        logger.info(f"   - Queue status: {queue_stats}")
        
    except Exception as e:
        logger.error(f"Error checking new wallets: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    limit = int(os.getenv("POLYMARKET_ANALYTICS_CHECK_LIMIT", "2000"))
    check_new_wallets_from_analytics(limit=limit)

