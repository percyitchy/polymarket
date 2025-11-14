#!/usr/bin/env python3
"""
Cleanup legacy analysis_result values from wallet_analysis_cache
Safely removes old records with legacy values (rejected, etc.)
"""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta
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

def cleanup_legacy_cache(db_path: str = None, days_old: int = 7, dry_run: bool = True):
    """
    Cleanup legacy analysis_result values from wallet_analysis_cache
    
    Args:
        db_path: Path to database file (defaults to DB_PATH from env)
        days_old: Delete records older than this many days (default: 7)
        dry_run: If True, only show what would be deleted without actually deleting
    """
    load_dotenv()
    
    if db_path is None:
        db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
    
    # Resolve absolute path
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)
    
    logger.info(f"[CleanupLegacy] Connecting to database: {db_path}")
    logger.info(f"[CleanupLegacy] Mode: {'DRY RUN' if dry_run else 'LIVE DELETE'}")
    logger.info(f"[CleanupLegacy] Will {'delete' if not dry_run else 'show'} records older than {days_old} days")
    
    db = PolymarketDB(db_path)
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
    cutoff_iso = cutoff_date.isoformat()
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Legacy values to clean up
        legacy_values = ['rejected', 'error', 'failed', '']
        
        # Check what would be deleted
        placeholders = ','.join(['?' for _ in legacy_values])
        query = f"""
            SELECT 
                analysis_result,
                COUNT(*) as count,
                MIN(created_at) as oldest,
                MAX(created_at) as newest
            FROM wallet_analysis_cache 
            WHERE analysis_result IN ({placeholders})
            AND (created_at IS NULL OR created_at < ?)
            GROUP BY analysis_result
        """
        
        cursor.execute(query, (*legacy_values, cutoff_iso))
        results = cursor.fetchall()
        
        if not results:
            logger.info("[CleanupLegacy] No legacy records found to clean up")
            return
        
        logger.info("=" * 80)
        logger.info("[CleanupLegacy] Records that would be deleted:")
        logger.info("=" * 80)
        
        total_to_delete = 0
        for result, count, oldest, newest in results:
            logger.info(f"[CleanupLegacy] analysis_result='{result}' count={count} (oldest: {oldest[:10] if oldest else 'N/A'}, newest: {newest[:10] if newest else 'N/A'})")
            total_to_delete += count
        
        logger.info("=" * 80)
        logger.info(f"[CleanupLegacy] Total records to delete: {total_to_delete}")
        
        if dry_run:
            logger.info("[CleanupLegacy] DRY RUN - no records were actually deleted")
            logger.info("[CleanupLegacy] Run with --execute to actually delete these records")
        else:
            # Actually delete
            delete_query = f"""
                DELETE FROM wallet_analysis_cache 
                WHERE analysis_result IN ({placeholders})
                AND (created_at IS NULL OR created_at < ?)
            """
            
            cursor.execute(delete_query, (*legacy_values, cutoff_iso))
            deleted_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"[CleanupLegacy] ✅ Deleted {deleted_count} legacy records")
            
            # Show remaining distribution
            cursor.execute("""
                SELECT analysis_result, COUNT(*) 
                FROM wallet_analysis_cache 
                GROUP BY analysis_result
                ORDER BY COUNT(*) DESC
            """)
            remaining = cursor.fetchall()
            
            logger.info("")
            logger.info("[CleanupLegacy] Remaining records after cleanup:")
            for result, count in remaining:
                result_str = result if result else "NULL"
                logger.info(f"[CleanupLegacy]   '{result_str}': {count}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Cleanup legacy analysis_result values from wallet_analysis_cache")
    parser.add_argument("--db", type=str, help="Path to database file (default: from DB_PATH env)")
    parser.add_argument("--days", type=int, default=7, help="Delete records older than N days (default: 7)")
    parser.add_argument("--execute", action="store_true", help="Actually delete records (default: dry run)")
    args = parser.parse_args()
    
    cleanup_legacy_cache(db_path=args.db, days_old=args.days, dry_run=not args.execute)

