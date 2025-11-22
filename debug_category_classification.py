#!/usr/bin/env python3
"""
Debug category classification - check why markets are classified as Unknown
"""

import os
import requests
from db import PolymarketDB
from dotenv import load_dotenv
from market_utils import classify_market

load_dotenv()

db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
if not os.path.isabs(db_path):
    db_path = os.path.abspath(db_path)

db = PolymarketDB(db_path)

print("=" * 100)
print("DEBUGGING CATEGORY CLASSIFICATION")
print("=" * 100)

# Get sample wallets with Unknown category
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT wallet_address, category, markets
        FROM wallet_category_stats
        WHERE category = 'other/Unknown' AND markets > 20
        ORDER BY markets DESC
        LIMIT 3
    """)
    sample_wallets = cursor.fetchall()

print(f"\n📊 Analyzing {len(sample_wallets)} sample wallets with 'other/Unknown' category\n")

for wallet_addr, category, markets in sample_wallets:
    print(f"\n{'='*100}")
    print(f"Wallet: {wallet_addr}")
    print(f"Category: {category}, Markets: {markets}")
    print(f"{'='*100}")
    
    # Try to get closed positions
    try:
        closed_positions_url = "https://data-api.polymarket.com/closed-positions"
        params = {"user": wallet_addr, "limit": 5}
        response = requests.get(closed_positions_url, params=params, timeout=10)
        
        if response.status_code == 200:
            positions = response.json()
            print(f"\n✅ Got {len(positions)} closed positions")
            
            for i, pos in enumerate(positions[:3], 1):
                condition_id = pos.get("conditionId") or pos.get("condition_id")
                if not condition_id:
                    continue
                
                print(f"\n📌 Market {i}:")
                print(f"   Condition ID: {condition_id[:40]}...")
                
                # Check what data we have in position
                print(f"\n   Data in closed position:")
                print(f"     Keys: {list(pos.keys())[:20]}")
                
                # Try CLOB API
                print(f"\n   Fetching from CLOB API...")
                try:
                    clob_url = f"https://clob.polymarket.com/markets/{condition_id}"
                    clob_response = requests.get(clob_url, timeout=10)
                    
                    if clob_response.status_code == 200:
                        clob_data = clob_response.json()
                        print(f"   ✅ Got CLOB data")
                        
                        slug = clob_data.get("slug") or clob_data.get("questionSlug")
                        question = clob_data.get("question") or clob_data.get("title")
                        
                        print(f"     slug: {slug}")
                        print(f"     question: {question[:100] if question else 'None'}")
                        
                        # Classify
                        classified = classify_market({}, slug, question)
                        print(f"\n   Classification: {classified}")
                        
                        # Show why it might be Unknown
                        all_text = f"{slug or ''} {question or ''}"
                        print(f"\n   Combined text: {all_text[:200]}")
                        
                        # Check keywords
                        keywords_found = []
                        if any(kw in all_text.lower() for kw in ["nfl", "football", "super bowl"]):
                            keywords_found.append("sports/NFL")
                        if any(kw in all_text.lower() for kw in ["election", "president"]):
                            keywords_found.append("politics")
                        if any(kw in all_text.lower() for kw in ["fed", "inflation", "interest rate"]):
                            keywords_found.append("macro")
                        if any(kw in all_text.lower() for kw in ["bitcoin", "crypto"]):
                            keywords_found.append("crypto")
                        
                        if keywords_found:
                            print(f"   ⚠️  Found keywords: {', '.join(keywords_found)}")
                        else:
                            print(f"   ℹ️  No recognizable keywords found")
                    else:
                        print(f"   ❌ CLOB API returned status {clob_response.status_code}")
                except Exception as e:
                    print(f"   ❌ Error fetching from CLOB API: {e}")
        else:
            print(f"   ❌ API returned status {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print("\n💡 If markets are still classified as Unknown, possible reasons:")
print("   1. CLOB API doesn't return slug/question for closed markets")
print("   2. Market slugs/questions don't contain recognizable keywords")
print("   3. Need to expand keyword list in classify_market()")
print("   4. Markets might be truly uncategorized (e.g., entertainment, weather)")

