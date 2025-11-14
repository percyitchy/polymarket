#!/usr/bin/env python3
"""
Inspect analysis_result values in wallet_analysis_cache
Shows distribution of all analysis_result values to understand legacy data
"""

import os
import sys
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import PolymarketDB

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def inspect_analysis_results(db_path: str = None):
    """
    Inspect all analysis_result values in wallet_analysis_cache
    
    Args:
        db_path: Path to database file (defaults to DB_PATH from env or "polymarket_notifier.db")
    """
    load_dotenv()
    
    if db_path is None:
        db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
    
    # Resolve absolute path
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)
    
    logger.info(f"[InspectFilters] Connecting to database: {db_path}")
    
    db = PolymarketDB(db_path)
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM wallet_analysis_cache")
        total_count = cursor.fetchone()[0]
        logger.info(f"[InspectFilters] Total records in wallet_analysis_cache: {total_count}")
        
        # Get distribution of analysis_result values
        cursor.execute("""
            SELECT 
                analysis_result,
                COUNT(*) as count,
                MIN(analyzed_at) as oldest,
                MAX(analyzed_at) as newest
            FROM wallet_analysis_cache 
            GROUP BY analysis_result
            ORDER BY COUNT(*) DESC
        """)
        
        results = cursor.fetchall()
        
        if not results:
            logger.warning("[InspectFilters] No records found in wallet_analysis_cache")
            return
        
        logger.info("=" * 80)
        logger.info("[InspectFilters] Analysis Result Distribution:")
        logger.info("=" * 80)
        
        # Known categories (from wallet_analyzer.py)
        known_categories = {
            'accepted',
            'rejected_low_trades',
            'rejected_low_winrate',
            'rejected_high_frequency',
            'rejected_inactive',
            'rejected_no_stats',
            'rejected_api_error',
            'rejected_invalid_data',
            'rejected_legacy'
        }
        
        legacy_values = []
        known_values = []
        
        for result, count, oldest, newest in results:
            # Handle NULL values
            if result is None:
                result_str = "NULL"
                category = "legacy"
            else:
                result_str = str(result)
                if result_str in known_categories:
                    category = "known"
                else:
                    category = "legacy"
            
            # Format dates
            oldest_str = oldest[:10] if oldest else "N/A"
            newest_str = newest[:10] if newest else "N/A"
            
            log_line = f"[InspectFilters] analysis_result='{result_str}' count={count} (oldest: {oldest_str}, newest: {newest_str})"
            
            if category == "legacy":
                logger.warning(log_line + " ⚠️ LEGACY")
                legacy_values.append((result_str, count, oldest, newest))
            else:
                logger.info(log_line)
                known_values.append((result_str, count, oldest, newest))
        
        logger.info("=" * 80)
        
        # Summary
        total_known = sum(count for _, count, _, _ in known_values)
        total_legacy = sum(count for _, count, _, _ in legacy_values)
        
        logger.info(f"[InspectFilters] Summary:")
        logger.info(f"  Total records: {total_count}")
        logger.info(f"  Known categories: {total_known} ({total_known/total_count*100:.1f}%)")
        logger.info(f"  Legacy values: {total_legacy} ({total_legacy/total_count*100:.1f}%)")
        
        if legacy_values:
            logger.info("")
            logger.info("[InspectFilters] Legacy values breakdown:")
            for result_str, count, oldest, newest in legacy_values:
                logger.info(f"  '{result_str}': {count} records (oldest: {oldest[:10] if oldest else 'N/A'}, newest: {newest[:10] if newest else 'N/A'})")
        
        # Check for created_at field (for future cleanup)
        cursor.execute("PRAGMA table_info(wallet_analysis_cache)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'created_at' in columns:
            logger.info("")
            logger.info("[InspectFilters] ✅ Table has 'created_at' field - ready for cleanup operations")
        elif 'analyzed_at' in columns:
            logger.info("")
            logger.info("[InspectFilters] ℹ️  Table has 'analyzed_at' field (can be used for cleanup)")
        else:
            logger.warning("")
            logger.warning("[InspectFilters] ⚠️  Table has no timestamp field for cleanup operations")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Inspect analysis_result values in wallet_analysis_cache")
    parser.add_argument("--db", type=str, help="Path to database file (default: from DB_PATH env or polymarket_notifier.db)")
    args = parser.parse_args()
    
    inspect_analysis_results(db_path=args.db)

