#!/usr/bin/env python3
"""
Analyze Polymarket markets to understand categories and keywords
"""

import requests
import json
from collections import Counter
from typing import List, Dict, Any
import time

def get_active_markets(limit: int = 100) -> List[Dict[str, Any]]:
    """Get active markets from Polymarket CLOB API"""
    try:
        url = "https://clob.polymarket.com/markets"
        params = {"limit": limit, "active": "true"}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Handle different response formats
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # Try common keys
                return data.get("data", data.get("markets", data.get("results", [])))
            return []
        return []
    except Exception as e:
        print(f"Error fetching markets: {e}")
        return []

def get_closed_positions_sample() -> List[Dict[str, Any]]:
    """Get sample closed positions to analyze"""
    # Use a known wallet with many trades
    wallet = "0x00113e75c6b045f3d21103008b908c047e3374f0"
    try:
        url = "https://data-api.polymarket.com/closed-positions"
        params = {"user": wallet, "limit": 100}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"Error fetching closed positions: {e}")
        return []

def extract_keywords(text: str) -> List[str]:
    """Extract potential keywords from text"""
    if not text:
        return []
    
    # Split by common separators
    words = text.lower().replace('-', ' ').replace('_', ' ').split()
    
    # Filter out common words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                  'of', 'with', 'by', 'will', 'be', 'is', 'are', 'was', 'were', 'vs',
                  'vs.', 'v', 'v.', 'up', 'down', 'above', 'below', 'over', 'under'}
    
    keywords = [w for w in words if len(w) > 2 and w not in stop_words]
    return keywords

def analyze_markets():
    """Analyze markets to find patterns and keywords"""
    print("=" * 100)
    print("ANALYZING POLYMARKET MARKETS")
    print("=" * 100)
    
    # Get active markets
    print("\n📊 Fetching active markets...")
    active_markets = get_active_markets(limit=200)
    print(f"   Got {len(active_markets)} active markets")
    
    # Get closed positions sample
    print("\n📊 Fetching closed positions sample...")
    closed_positions = get_closed_positions_sample()
    print(f"   Got {len(closed_positions)} closed positions")
    
    # Analyze questions/titles
    all_questions = []
    all_slugs = []
    
    # Handle active markets (could be list or dict)
    markets_to_analyze = active_markets if isinstance(active_markets, list) else []
    for market in markets_to_analyze[:100]:  # Analyze first 100
        if isinstance(market, dict):
            question = market.get("question") or market.get("title")
            slug = market.get("slug") or market.get("questionSlug")
            if question:
                all_questions.append(str(question).lower())
            if slug:
                all_slugs.append(str(slug).lower())
    
    for pos in closed_positions[:100]:  # Analyze first 100
        title = pos.get("title")
        slug = pos.get("slug")
        if title:
            all_questions.append(title.lower())
        if slug:
            all_slugs.append(slug.lower())
    
    print(f"\n📝 Analyzed {len(all_questions)} questions and {len(all_slugs)} slugs")
    
    # Extract keywords
    all_keywords = []
    for text in all_questions + all_slugs:
        keywords = extract_keywords(text)
        all_keywords.extend(keywords)
    
    # Count keywords
    keyword_counts = Counter(all_keywords)
    
    print("\n" + "=" * 100)
    print("TOP KEYWORDS FOUND")
    print("=" * 100)
    print(f"\n{'Keyword':<30} {'Count':<10}")
    print("-" * 40)
    for keyword, count in keyword_counts.most_common(50):
        print(f"{keyword:<30} {count:<10}")
    
    # Categorize by patterns
    print("\n" + "=" * 100)
    print("CATEGORY PATTERNS")
    print("=" * 100)
    
    # Sports patterns
    sports_keywords = ['nfl', 'nba', 'nhl', 'mlb', 'soccer', 'football', 'basketball', 
                       'hockey', 'baseball', 'tennis', 'golf', 'ufc', 'boxing', 'mma',
                       'championship', 'playoff', 'super', 'bowl', 'world', 'cup']
    sports_found = [kw for kw, count in keyword_counts.items() if any(sk in kw for sk in sports_keywords)]
    
    # Crypto patterns
    crypto_keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency',
                      'solana', 'sol', 'cardano', 'ada', 'price', 'above', 'below']
    crypto_found = [kw for kw, count in keyword_counts.items() if any(ck in kw for ck in crypto_keywords)]
    
    # Politics patterns
    politics_keywords = ['election', 'president', 'senate', 'congress', 'biden', 'trump',
                        'vote', 'voting', 'democrat', 'republican', 'primary']
    politics_found = [kw for kw, count in keyword_counts.items() if any(pk in kw for pk in politics_keywords)]
    
    print(f"\n🏈 Sports keywords found: {len(sports_found)}")
    print(f"   Top: {', '.join(sports_found[:20])}")
    
    print(f"\n💰 Crypto keywords found: {len(crypto_found)}")
    print(f"   Top: {', '.join(crypto_found[:20])}")
    
    print(f"\n🗳️  Politics keywords found: {len(politics_found)}")
    print(f"   Top: {', '.join(politics_found[:20])}")
    
    # Sample questions by category
    print("\n" + "=" * 100)
    print("SAMPLE QUESTIONS BY CATEGORY")
    print("=" * 100)
    
    sports_samples = [q for q in all_questions if any(sk in q for sk in sports_keywords)][:10]
    crypto_samples = [q for q in all_questions if any(ck in q for ck in crypto_keywords)][:10]
    politics_samples = [q for q in all_questions if any(pk in q for pk in politics_keywords)][:10]
    
    print(f"\n🏈 Sports samples ({len(sports_samples)}):")
    for i, q in enumerate(sports_samples[:5], 1):
        print(f"   {i}. {q[:80]}...")
    
    print(f"\n💰 Crypto samples ({len(crypto_samples)}):")
    for i, q in enumerate(crypto_samples[:5], 1):
        print(f"   {i}. {q[:80]}...")
    
    print(f"\n🗳️  Politics samples ({len(politics_samples)}):")
    for i, q in enumerate(politics_samples[:5], 1):
        print(f"   {i}. {q[:80]}...")
    
    return {
        'keyword_counts': keyword_counts,
        'sports_keywords': sports_found,
        'crypto_keywords': crypto_found,
        'politics_keywords': politics_found,
        'samples': {
            'sports': sports_samples,
            'crypto': crypto_samples,
            'politics': politics_samples
        }
    }

if __name__ == "__main__":
    results = analyze_markets()
    
    # Save results
    with open("polymarket_analysis_results.json", "w") as f:
        json.dump({
            'top_keywords': dict(results['keyword_counts'].most_common(100)),
            'sports_keywords': results['sports_keywords'],
            'crypto_keywords': results['crypto_keywords'],
            'politics_keywords': results['politics_keywords']
        }, f, indent=2)
    
    print("\n✅ Analysis complete! Results saved to polymarket_analysis_results.json")

