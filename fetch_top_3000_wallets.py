#!/usr/bin/env python3
"""
Скрипт для парсинга топ 3000 кошельков с polymarketanalytics.com/traders
и добавления их в очередь анализа
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
    ]
)
logger = logging.getLogger(__name__)


def fetch_top_wallets_by_rank(limit: int = 3000):
    """
    Fetch top wallets from polymarketanalytics.com sorted by rank (overall PnL)
    
    API ограничивает до 2500 кошельков за один запрос, поэтому делаем несколько запросов
    с разными параметрами сортировки для получения большего количества уникальных кошельков.
    
    Args:
        limit: Number of wallets to fetch (default 3000)
    
    Returns:
        Dictionary of wallets {address: {display, source}}
    """
    logger.info(f"📊 Fetching top {limit} wallets from polymarketanalytics.com/traders...")
    
    try:
        from fetch_polymarket_analytics_api import fetch_traders_from_api
        
        all_addresses = set()
        
        # Стратегия 1: Топ по overall_gain (PnL) - первые 2500
        logger.info("📊 Strategy 1: Fetching top traders by overall_gain (PnL)...")
        addresses1 = fetch_traders_from_api(
            target=2500,
            period="all",
            sort_by="overall_gain"
        )
        all_addresses.update(addresses1)
        logger.info(f"   Got {len(addresses1)} addresses (total unique: {len(all_addresses)})")
        
        # Стратегия 2: Топ по totalPositions (объем торгов) - если нужно больше
        if len(all_addresses) < limit:
            remaining = limit - len(all_addresses)
            logger.info(f"📊 Strategy 2: Fetching {remaining} more traders by totalPositions (volume)...")
            addresses2 = fetch_traders_from_api(
                target=min(remaining + 500, 2500),  # Берем немного больше для учета дубликатов
                period="all",
                sort_by="totalPositions"
            )
            all_addresses.update(addresses2)
            logger.info(f"   Got {len(addresses2)} addresses (total unique: {len(all_addresses)})")
        
        # Стратегия 3: Топ по winRate - если все еще нужно больше
        if len(all_addresses) < limit:
            remaining = limit - len(all_addresses)
            logger.info(f"📊 Strategy 3: Fetching {remaining} more traders by winRate...")
            addresses3 = fetch_traders_from_api(
                target=min(remaining + 500, 2500),
                period="all",
                sort_by="winRate"
            )
            all_addresses.update(addresses3)
            logger.info(f"   Got {len(addresses3)} addresses (total unique: {len(all_addresses)})")
        
        # Ограничиваем до запрошенного количества
        final_addresses = list(all_addresses)[:limit]
        
        logger.info(f"✅ Fetched {len(final_addresses)} unique addresses from polymarketanalytics.com (requested: {limit})")
        
        # Convert to wallet dictionary format
        wallets = {}
        for addr in final_addresses:
            addr_lower = addr.lower()
            wallets[addr_lower] = {
                "display": addr_lower,
                "source": "polymarket_analytics_top_3000"
            }
        
        return wallets
        
    except Exception as e:
        logger.error(f"❌ Error fetching wallets from polymarketanalytics.com: {e}", exc_info=True)
        return {}


def main():
    """Main function"""
    logger.info("=" * 80)
    logger.info("🚀 Fetching Top 3000 Wallets from polymarketanalytics.com")
    logger.info("=" * 80)
    
    # Initialize database
    db = PolymarketDB("polymarket_notifier.db")
    
    # Get current stats
    initial_stats = db.get_wallet_stats()
    logger.info(f"📊 Current database state:")
    logger.info(f"   - Total wallets: {initial_stats.get('total_wallets', 0)}")
    logger.info(f"   - Tracked wallets: {initial_stats.get('tracked_wallets', 0)}")
    
    # Initialize analyzer
    config = AnalysisConfig(
        api_max_workers=6,  # Use 6 workers for processing
        api_timeout_sec=20,
        api_retry_max=6
    )
    analyzer = WalletAnalyzer(db, config)
    
    # Check existing wallets in queue
    queue_status = analyzer.get_queue_status()
    logger.info(f"📋 Current queue status: {queue_status}")
    
    # Fetch top 3000 wallets
    wallets = fetch_top_wallets_by_rank(limit=3000)
    
    if not wallets:
        logger.error("❌ No wallets collected!")
        return
    
    logger.info(f"📊 Collected {len(wallets)} wallets from polymarketanalytics.com")
    
    # Filter out wallets already in database or queue
    new_wallets = {}
    existing_in_db = 0
    existing_in_queue = 0
    
    for addr, meta in wallets.items():
        addr_lower = addr.lower()
        
        # Check if already in wallets table
        existing = db.get_wallet(addr_lower)
        if existing:
            existing_in_db += 1
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
            existing_in_queue += 1
            continue
        
        new_wallets[addr_lower] = meta
    
    logger.info(f"📊 Wallet summary:")
    logger.info(f"   - Total collected: {len(wallets)}")
    logger.info(f"   - Already in database: {existing_in_db}")
    logger.info(f"   - Already in queue: {existing_in_queue}")
    logger.info(f"   - New to analyze: {len(new_wallets)}")
    
    if not new_wallets:
        logger.info("ℹ️  No new wallets to add to queue")
        return
    
    # Add to queue
    logger.info(f"➕ Adding {len(new_wallets)} wallets to analysis queue...")
    added_count = analyzer.add_wallets_to_queue(new_wallets)
    
    logger.info(f"✅ Added {added_count} wallets to queue")
    
    # Get final queue status
    final_status = analyzer.get_queue_status()
    logger.info(f"📊 Final queue status: {final_status}")
    
    logger.info("=" * 80)
    logger.info("✅ Wallet collection complete!")
    logger.info(f"   Workers will process {final_status.get('pending_jobs', 0)} jobs in the background")
    logger.info("=" * 80)
    
    # Start workers to process the queue
    logger.info("🚀 Starting wallet analyzer workers...")
    analyzer.start_workers()
    
    logger.info("✅ Workers started. They will process wallets in the background.")
    logger.info("   Wallets that pass filters will be automatically added to tracking.")


if __name__ == "__main__":
    main()

