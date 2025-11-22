#!/usr/bin/env python3
"""
Analyze category classification issues
"""

import os
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
print("CATEGORY CLASSIFICATION ANALYSIS")
print("=" * 100)

# Get sample of closed positions to analyze
with db.get_connection() as conn:
    cursor = conn.cursor()
    
    # Get wallets with category stats
    cursor.execute("""
        SELECT DISTINCT wallet_address, category, markets
        FROM wallet_category_stats
        WHERE category = 'other/Unknown'
        ORDER BY markets DESC
        LIMIT 5
    """)
    
    sample_wallets = cursor.fetchall()

print(f"\n📊 Found {len(sample_wallets)} sample wallets with 'other/Unknown' category")
print("\nAnalyzing why markets are classified as 'other/Unknown'...\n")

# For each wallet, try to get some closed positions and classify them
for wallet_addr, category, markets in sample_wallets:
    print(f"\n{'='*100}")
    print(f"Wallet: {wallet_addr}")
    print(f"Category: {category} ({markets} markets)")
    print(f"{'='*100}")
    
    # Try to get closed positions from API (we'll need to simulate this)
    # For now, let's check what we can learn from the database
    
    # Get some condition IDs from wallet_category_stats if we had them stored
    # Since we don't store condition_ids, we'll need to analyze the classification logic
    
    print(f"\n⚠️  This wallet has {markets} markets classified as 'other/Unknown'")
    print(f"   Possible reasons:")
    print(f"   1. Markets don't match keywords in classify_market()")
    print(f"   2. Event data from Gamma API doesn't contain category/tags")
    print(f"   3. Slug/question text doesn't contain recognizable keywords")
    print(f"   4. Markets are truly in uncategorized domains")

print("\n" + "=" * 100)
print("CLASSIFICATION KEYWORDS CHECK")
print("=" * 100)

print("\n📋 Current classification keywords:")
print("\nSports:")
print("  - NFL: nfl, national football league, super bowl, chiefs, packers, etc.")
print("  - Soccer: uefa, fifa, soccer, football, world cup, champions league")
print("  - Other: nba, basketball, nhl, hockey, mlb, baseball, tennis, golf")

print("\nPolitics:")
print("  - US: election, president, senate, biden, trump, us, usa, america")
print("  - Global: election, president (without US context)")

print("\nMacro:")
print("  - Fed: fed, federal reserve, interest rate, cpi, inflation, fomc")

print("\nCrypto:")
print("  - BTC: bitcoin, btc")
print("  - Altcoins: ethereum, eth, solana, sol, cardano, etc.")

print("\n" + "=" * 100)
print("RECOMMENDATIONS")
print("=" * 100)

print("\n💡 To improve classification:")
print("  1. Check actual market slugs/questions from Gamma API")
print("  2. Add more keywords to classify_market() function")
print("  3. Use event.category and event.tags fields more effectively")
print("  4. Consider using market titles/questions for better classification")
print("  5. Add fallback classification based on market patterns")

print("\n" + "=" * 100)

