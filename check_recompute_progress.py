#!/usr/bin/env python3
"""
Quick script to check recompute progress
"""

import os
from db import PolymarketDB
from dotenv import load_dotenv

load_dotenv()

db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
if not os.path.isabs(db_path):
    db_path = os.path.abspath(db_path)

db = PolymarketDB(db_path)

# Get queue stats
with db.get_connection() as conn:
    cursor = conn.cursor()
    
    # Get job counts
    cursor.execute("""
        SELECT status, COUNT(*) 
        FROM wallet_analysis_jobs 
        GROUP BY status
    """)
    status_counts = dict(cursor.fetchall())
    
    pending = status_counts.get('pending', 0)
    processing = status_counts.get('processing', 0)
    completed = status_counts.get('completed', 0)
    failed = status_counts.get('failed', 0)
    total = pending + processing + completed + failed
    
    # Get category stats
    cursor.execute("""
        SELECT COUNT(DISTINCT wallet_address) 
        FROM wallet_category_stats
    """)
    wallets_with_categories = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(DISTINCT wallet_address) 
        FROM wallet_category_stats
        WHERE is_a_list_trader = 1
    """)
    wallets_with_a_list = cursor.fetchone()[0]
    
    # Get category breakdown
    cursor.execute("""
        SELECT category, COUNT(*) as count,
               SUM(CASE WHEN is_a_list_trader = 1 THEN 1 ELSE 0 END) as a_list_count
        FROM wallet_category_stats
        GROUP BY category
        ORDER BY count DESC
        LIMIT 10
    """)
    category_breakdown = cursor.fetchall()

print("=" * 80)
print("📊 RECOMPUTE PROGRESS")
print("=" * 80)
print(f"\n📋 Queue Status:")
print(f"  Total jobs: {total}")
print(f"  ✅ Completed: {completed}")
print(f"  ⏳ Pending: {pending}")
print(f"  🔄 Processing: {processing}")
print(f"  ❌ Failed: {failed}")

if total > 0:
    progress_pct = (completed / total) * 100
    remaining = pending + processing
    print(f"\n📈 Progress: {completed}/{total} ({progress_pct:.1f}%)")
    print(f"  Remaining: {remaining} wallets")
    
    if completed > 0:
        # Estimate time remaining (rough estimate)
        print(f"\n⏱️  Estimated completion:")
        if remaining > 0:
            # Assume ~2-3 wallets per second average
            rate = 2.5  # wallets/sec
            eta_seconds = remaining / rate
            eta_minutes = eta_seconds / 60
            eta_hours = eta_minutes / 60
            if eta_hours >= 1:
                print(f"  ~{eta_hours:.1f} hours ({eta_minutes:.0f} minutes)")
            else:
                print(f"  ~{eta_minutes:.0f} minutes")

print(f"\n📊 Category Statistics:")
print(f"  Wallets with categories: {wallets_with_categories}")
print(f"  Wallets with A List status: {wallets_with_a_list}")

if category_breakdown:
    print(f"\n📈 Top Categories:")
    for category, count, a_list_count in category_breakdown:
        print(f"  {category}: {count} wallets ({a_list_count} A List)")

print("=" * 80)

