#!/usr/bin/env python3
"""
Batch wallet analysis script
Collects 1200 wallets from multiple sources and adds them to analysis queue
"""

import os
import sys
import logging
import asyncio
from dotenv import load_dotenv

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import PolymarketDB
from wallet_analyzer import WalletAnalyzer, AnalysisConfig

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('batch_analyze_wallets.log')
    ]
)
logger = logging.getLogger(__name__)


async def collect_wallets(limit: int = 1200):
    """Collect wallets from multiple sources"""
    all_wallets = {}
    
    try:
        # Source 1: polymarketanalytics.com (up to limit)
        logger.info(f"Collecting from polymarketanalytics.com (limit: {limit})...")
        from fetch_polymarket_analytics_api import fetch_traders_from_api
        
        analytics_addresses = fetch_traders_from_api(target=limit)
        logger.info(f"Got {len(analytics_addresses)} addresses from polymarketanalytics.com")
        
        for addr in analytics_addresses[:limit]:
            addr_lower = addr.lower()
            if addr_lower not in all_wallets:
                all_wallets[addr_lower] = {
                    "display": addr_lower,
                    "source": "polymarket_analytics_batch"
                }
        
        # If we need more, try leaderboards
        if len(all_wallets) < limit:
            remaining = limit - len(all_wallets)
            logger.info(f"Collecting {remaining} more from Polymarket leaderboards...")
            
            try:
                from fetch_leaderboards import scrape_polymarket_leaderboards
                
                leaderboard_urls = [
                    "https://data-api.polymarket.com/leaderboard?period=weekly",
                    "https://data-api.polymarket.com/leaderboard?period=monthly",
                ]
                
                leaderboard_wallets = await scrape_polymarket_leaderboards(
                    leaderboard_urls,
                    headless=True
                )
                
                for addr, meta in leaderboard_wallets.items():
                    if len(all_wallets) >= limit:
                        break
                    if addr.lower() not in all_wallets:
                        all_wallets[addr.lower()] = {
                            "display": meta.get("display", addr),
                            "source": meta.get("source", "polymarket_leaderboard_batch")
                        }
            except Exception as e:
                logger.warning(f"Could not collect from leaderboards: {e}")
        
        logger.info(f"✅ Collected {len(all_wallets)} total unique wallets")
        return all_wallets
        
    except Exception as e:
        logger.error(f"Error collecting wallets: {e}", exc_info=True)
        return all_wallets


def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("🚀 Starting batch wallet analysis (1200 wallets)")
    logger.info("=" * 60)
    
    # Initialize database
    db = PolymarketDB("polymarket_notifier.db")
    
    # Initialize analyzer
    config = AnalysisConfig(
        api_max_workers=7,  # Use 7 workers for faster processing
        api_timeout_sec=20,
        api_retry_max=6
    )
    analyzer = WalletAnalyzer(db, config)
    
    # Check existing wallets in queue
    queue_status = analyzer.get_queue_status()
    logger.info(f"Current queue status: {queue_status}")
    
    # Collect wallets
    wallets = asyncio.run(collect_wallets(limit=1200))
    
    if not wallets:
        logger.error("No wallets collected!")
        return
    
    # Filter out wallets already in database or queue
    new_wallets = {}
    existing_count = 0
    
    for addr, meta in wallets.items():
        addr_lower = addr.lower()
        
        # Check if already in wallets table
        existing = db.get_wallet(addr_lower)
        if existing:
            existing_count += 1
            continue
        
        # Check if already in queue
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM wallet_analysis_jobs WHERE address = ?",
                (addr_lower,)
            )
            in_queue = cursor.fetchone()[0] > 0
        
        if in_queue:
            existing_count += 1
            continue
        
        new_wallets[addr_lower] = meta
    
    logger.info(f"📊 Wallet summary:")
    logger.info(f"   - Total collected: {len(wallets)}")
    logger.info(f"   - Already exists: {existing_count}")
    logger.info(f"   - New to analyze: {len(new_wallets)}")
    
    if not new_wallets:
        logger.info("No new wallets to add to queue")
        return
    
    # Add to queue
    logger.info(f"➕ Adding {len(new_wallets)} wallets to analysis queue...")
    added_count = analyzer.add_wallets_to_queue(new_wallets)
    
    logger.info(f"✅ Added {added_count} wallets to queue")
    
    # Get final queue status
    final_status = analyzer.get_queue_status()
    logger.info(f"📊 Final queue status: {final_status}")
    
    logger.info("=" * 60)
    logger.info("✅ Batch wallet collection complete!")
    logger.info(f"   Workers will process {final_status.get('pending_jobs', 0)} jobs in the background")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

