#!/usr/bin/env python3
"""
Get daily statistics for wallet analysis
Can be used for reporting and monitoring
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import PolymarketDB

def get_daily_job_stats(db: PolymarketDB, date: datetime = None):
    """Get detailed job statistics for a specific day"""
    if date is None:
        date = datetime.now(timezone.utc)
    
    day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    
    day_start_iso = day_start.isoformat()
    day_end_iso = day_end.isoformat()
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        stats = {}
        
        # Jobs completed today
        cursor.execute("""
            SELECT COUNT(*) FROM wallet_analysis_jobs 
            WHERE status = 'completed'
            AND datetime(updated_at) >= datetime(?)
            AND datetime(updated_at) < datetime(?)
        """, (day_start_iso, day_end_iso))
        stats['completed_today'] = cursor.fetchone()[0]
        
        # Jobs failed today
        cursor.execute("""
            SELECT COUNT(*) FROM wallet_analysis_jobs 
            WHERE status = 'failed'
            AND datetime(updated_at) >= datetime(?)
            AND datetime(updated_at) < datetime(?)
        """, (day_start_iso, day_end_iso))
        stats['failed_today'] = cursor.fetchone()[0]
        
        # Average processing time for completed jobs today
        cursor.execute("""
            SELECT AVG(
                (julianday(updated_at) - julianday(created_at)) * 86400
            ) FROM wallet_analysis_jobs 
            WHERE status = 'completed'
            AND datetime(updated_at) >= datetime(?)
            AND datetime(updated_at) < datetime(?)
        """, (day_start_iso, day_end_iso))
        avg_time = cursor.fetchone()[0]
        stats['avg_processing_time_sec'] = avg_time if avg_time else 0
        
        # Failed rate
        total_processed = stats['completed_today'] + stats['failed_today']
        if total_processed > 0:
            stats['failed_rate'] = stats['failed_today'] / total_processed
        else:
            stats['failed_rate'] = 0.0
        
        # Jobs by source (added today)
        cursor.execute("""
            SELECT source, COUNT(*) FROM wallet_analysis_jobs 
            WHERE datetime(created_at) >= datetime(?)
            AND datetime(created_at) < datetime(?)
            GROUP BY source
        """, (day_start_iso, day_end_iso))
        stats['jobs_by_source'] = dict(cursor.fetchall())
        
        return stats

if __name__ == "__main__":
    load_dotenv()
    db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
    db = PolymarketDB(db_path)
    
    stats = get_daily_job_stats(db)
    print("Daily Job Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

