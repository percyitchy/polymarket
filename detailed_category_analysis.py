#!/usr/bin/env python3
"""
Detailed analysis of category classification problem
"""

import os
import requests
from db import PolymarketDB
from dotenv import load_dotenv
from gamma_client import get_event_by_condition_id
from market_utils import classify_market

load_dotenv()

db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
if not os.path.isabs(db_path):
    db_path = os.path.abspath(db_path)

db = PolymarketDB(db_path)

print("=" * 100)
print("DETAILED CATEGORY CLASSIFICATION ANALYSIS")
print("=" * 100)

# Get a sample wallet with A List status
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT wallet_address, category, markets
        FROM wallet_category_stats
        WHERE is_a_list_trader = 1
        ORDER BY markets DESC
        LIMIT 1
    """)
    sample = cursor.fetchone()

if not sample:
    print("No A List wallets found")
    exit(1)

wallet_addr, category, markets = sample
print(f"\n📊 Analyzing wallet: {wallet_addr}")
print(f"   Category: {category}")
print(f"   Markets: {markets}")

# Try to get closed positions for this wallet
print("\n🔍 Fetching closed positions from API...")
try:
    closed_positions_url = "https://data-api.polymarket.com/closed-positions"
    params = {"user": wallet_addr, "limit": 10}
    response = requests.get(closed_positions_url, params=params, timeout=10)
    
    if response.status_code == 200:
        positions = response.json()
        print(f"   ✅ Got {len(positions)} closed positions")
        
        print("\n" + "=" * 100)
        print("ANALYZING FIRST 5 MARKETS")
        print("=" * 100)
        
        for i, pos in enumerate(positions[:5], 1):
            condition_id = pos.get("conditionId") or pos.get("condition_id")
            if not condition_id:
                continue
            
            print(f"\n📌 Market {i}:")
            print(f"   Condition ID: {condition_id[:30]}...")
            
            # Get event from Gamma API
            print(f"   Fetching event data from Gamma API...")
            event = get_event_by_condition_id(condition_id)
            
            if event:
                print(f"   ✅ Got event data")
                
                # Extract fields
                event_category = event.get("category")
                event_group_type = event.get("groupType")
                event_tags = event.get("tags", [])
                event_slug = event.get("slug") or event.get("eventSlug")
                
                # Get market-specific data
                market_slug = None
                market_question = None
                
                markets_list = event.get("markets", [])
                for market in markets_list:
                    market_condition_id = market.get("conditionId") or market.get("condition_id")
                    if market_condition_id and market_condition_id.lower() == condition_id.lower():
                        market_slug = market.get("slug") or market.get("marketSlug")
                        market_question = market.get("question") or market.get("title")
                        break
                
                print(f"\n   Event Data:")
                print(f"     category: {event_category}")
                print(f"     groupType: {event_group_type}")
                print(f"     tags: {event_tags}")
                print(f"     event_slug: {event_slug}")
                print(f"     market_slug: {market_slug}")
                print(f"     market_question: {market_question}")
                
                # Classify
                classified = classify_market(event, market_slug, market_question)
                print(f"\n   Classification Result: {classified}")
                
                # Analyze why it might be "other/Unknown"
                all_text = f"{market_slug or ''} {market_question or ''} {event_category or ''} {event_group_type or ''} {' '.join([str(t) for t in event_tags])}"
                print(f"\n   Combined text for analysis:")
                print(f"     {all_text[:200]}...")
                
                # Check if any keywords match
                keywords_found = []
                if "nfl" in all_text.lower() or "football" in all_text.lower():
                    keywords_found.append("sports")
                if "election" in all_text.lower() or "president" in all_text.lower():
                    keywords_found.append("politics")
                if "fed" in all_text.lower() or "inflation" in all_text.lower():
                    keywords_found.append("macro")
                if "bitcoin" in all_text.lower() or "crypto" in all_text.lower():
                    keywords_found.append("crypto")
                
                if keywords_found:
                    print(f"   ⚠️  Found keywords: {', '.join(keywords_found)} but still classified as '{classified}'")
                else:
                    print(f"   ℹ️  No recognizable keywords found in text")
            else:
                print(f"   ❌ Failed to get event data")
                # Try classification with empty event
                classified = classify_market({}, None, None)
                print(f"   Classification with empty data: {classified}")
    else:
        print(f"   ❌ API returned status {response.status_code}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "=" * 100)
print("PROBLEM ANALYSIS")
print("=" * 100)

print("\n🔍 Root Cause Analysis:")
print("\n1. POSSIBLE ISSUES:")
print("   a) Event data from Gamma API might not contain category/tags fields")
print("   b) Market slugs/questions might not contain recognizable keywords")
print("   c) classify_market() function might need more keywords")
print("   d) Event structure from Gamma API might be different than expected")

print("\n2. RECOMMENDATIONS:")
print("   a) Check actual structure of event objects from Gamma API")
print("   b) Add more keywords and patterns to classify_market()")
print("   c) Use event.category field if available")
print("   d) Improve fallback classification logic")
print("   e) Consider using machine learning for better classification")

print("\n3. IMMEDIATE FIX:")
print("   - Review market_utils.py classify_market() function")
print("   - Add logging to see what data is actually being passed")
print("   - Test with real market data from Polymarket")

print("\n" + "=" * 100)

