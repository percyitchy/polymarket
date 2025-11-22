#!/usr/bin/env python3
"""
Analyze unknown markets to find patterns and expand keywords
"""

import os
import requests
from db import PolymarketDB
from dotenv import load_dotenv
from collections import Counter
import json

load_dotenv()

db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
if not os.path.isabs(db_path):
    db_path = os.path.abspath(db_path)

db = PolymarketDB(db_path)

print("=" * 100)
print("ANALYZING UNKNOWN MARKETS")
print("=" * 100)

# Get wallets with Unknown category
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT wallet_address, category, markets
        FROM wallet_category_stats
        WHERE category = 'other/Unknown' AND markets > 20
        ORDER BY markets DESC
        LIMIT 10
    """)
    sample_wallets = cursor.fetchall()

print(f"\n📊 Analyzing {len(sample_wallets)} sample wallets with 'other/Unknown' category\n")

all_titles = []
all_slugs = []
all_keywords = []

for wallet_addr, category, markets in sample_wallets:
    print(f"\n{'='*100}")
    print(f"Wallet: {wallet_addr}")
    print(f"Category: {category}, Markets: {markets}")
    print(f"{'='*100}")
    
    # Get closed positions
    try:
        closed_positions_url = "https://data-api.polymarket.com/closed-positions"
        params = {"user": wallet_addr, "limit": 50}
        response = requests.get(closed_positions_url, params=params, timeout=10)
        
        if response.status_code == 200:
            positions = response.json()
            print(f"   ✅ Got {len(positions)} closed positions")
            
            for pos in positions[:20]:  # Analyze first 20
                title = pos.get("title")
                slug = pos.get("slug")
                
                if title:
                    all_titles.append(title.lower())
                    # Extract words
                    words = title.lower().replace('-', ' ').replace('_', ' ').split()
                    all_keywords.extend([w for w in words if len(w) > 2])
                
                if slug:
                    all_slugs.append(slug.lower())
                    words = slug.lower().replace('-', ' ').replace('_', ' ').split()
                    all_keywords.extend([w for w in words if len(w) > 2])
        else:
            print(f"   ❌ API returned status {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

# Analyze keywords
print("\n" + "=" * 100)
print("KEYWORD ANALYSIS")
print("=" * 100)

keyword_counts = Counter(all_keywords)

# Filter out common stop words
stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
              'of', 'with', 'by', 'will', 'be', 'is', 'are', 'was', 'were', 'vs',
              'vs.', 'v', 'v.', 'up', 'down', 'above', 'below', 'over', 'under',
              'this', 'that', 'these', 'those', 'from', 'into', 'onto', 'upon',
              'about', 'across', 'after', 'against', 'along', 'among', 'around',
              'before', 'behind', 'below', 'beneath', 'beside', 'between', 'beyond',
              'during', 'except', 'inside', 'outside', 'through', 'throughout',
              'toward', 'towards', 'under', 'underneath', 'until', 'within', 'without'}

filtered_keywords = {kw: count for kw, count in keyword_counts.items() 
                     if kw not in stop_words and len(kw) > 2}

print(f"\n📝 Total unique keywords found: {len(filtered_keywords)}")
print(f"\n{'Keyword':<30} {'Count':<10}")
print("-" * 40)
for keyword, count in Counter(filtered_keywords).most_common(50):
    print(f"{keyword:<30} {count:<10}")

# Sample titles
print("\n" + "=" * 100)
print("SAMPLE TITLES FROM UNKNOWN MARKETS")
print("=" * 100)
for i, title in enumerate(all_titles[:30], 1):
    print(f"{i}. {title[:80]}")

# Save results
results = {
    'top_keywords': dict(Counter(filtered_keywords).most_common(100)),
    'sample_titles': all_titles[:50],
    'sample_slugs': all_slugs[:50]
}

with open("unknown_markets_analysis.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n✅ Analysis complete! Results saved to unknown_markets_analysis.json")

