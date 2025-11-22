#!/usr/bin/env python3
"""
Diagnostic script to debug market URL construction issues.
Checks what data is available from Gamma API and CLOB API for specific markets.
"""

import sys
import json
import requests
from typing import Optional, Dict, Any

def get_gamma_event_by_condition_id(condition_id: str) -> Optional[Dict[str, Any]]:
    """Get event from Gamma API by condition_id"""
    try:
        url = "https://gamma-api.polymarket.com/events"
        params = {"conditionId": condition_id}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            events = []
            if isinstance(data, list):
                events = data
            elif isinstance(data, dict):
                events = data.get("data") or data.get("events") or []
            
            for event in events:
                markets = event.get("markets", [])
                for market in markets:
                    market_condition_id = market.get("conditionId") or market.get("condition_id")
                    if market_condition_id and market_condition_id.lower() == condition_id.lower():
                        return {"event": event, "matching_market": market}
        return None
    except Exception as e:
        print(f"Error getting Gamma event: {e}")
        return None

def get_clob_market(condition_id: str) -> Optional[Dict[str, Any]]:
    """Get market data from CLOB API"""
    try:
        url = f"https://clob.polymarket.com/markets/{condition_id}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error getting CLOB market: {e}")
        return None

def analyze_market(condition_id: str):
    """Analyze a market to see what data is available"""
    print(f"\n{'='*80}")
    print(f"Analyzing market: {condition_id}")
    print(f"{'='*80}\n")
    
    # Get Gamma API data
    print("1. GAMMA API DATA:")
    print("-" * 80)
    gamma_data = get_gamma_event_by_condition_id(condition_id)
    if gamma_data:
        event = gamma_data.get("event")
        market = gamma_data.get("matching_market")
        
        if event:
            print(f"✅ Event found")
            print(f"   Event ID: {event.get('id')}")
            print(f"   Event slug: {event.get('slug')}")
            print(f"   Event keys: {list(event.keys())[:20]}")
            
            if market:
                print(f"\n   ✅ Matching market found")
                print(f"   Market keys: {list(market.keys())}")
                print(f"\n   Market ID fields:")
                for field in ['id', 'marketId', 'market_id', 'tid', 'marketIdNum', 'tokenId', 'token_id']:
                    value = market.get(field)
                    if value is not None:
                        print(f"      - {field}: {value} (type: {type(value).__name__})")
                
                print(f"\n   Market slug fields:")
                for field in ['slug', 'marketSlug', 'market_slug', 'questionSlug', 'question_slug']:
                    value = market.get(field)
                    if value is not None:
                        print(f"      - {field}: {value}")
                
                print(f"\n   Full market object:")
                print(json.dumps(market, indent=2, default=str)[:2000])
        else:
            print("❌ Event not found")
    else:
        print("❌ No data from Gamma API")
    
    # Get CLOB API data
    print(f"\n\n2. CLOB API DATA:")
    print("-" * 80)
    clob_data = get_clob_market(condition_id)
    if clob_data:
        print(f"✅ Market found")
        print(f"   Market keys: {list(clob_data.keys())}")
        
        print(f"\n   Market ID fields:")
        for field in ['id', 'marketId', 'market_id', 'tid', 'marketIdNum']:
            value = clob_data.get(field)
            if value is not None:
                print(f"      - {field}: {value} (type: {type(value).__name__})")
        
        print(f"\n   Market slug fields:")
        for field in ['slug', 'marketSlug', 'market_slug', 'question_slug', 'event_slug', 'eventSlug']:
            value = clob_data.get(field)
            if value is not None:
                print(f"      - {field}: {value}")
        
        print(f"\n   Full CLOB response (first 2000 chars):")
        print(json.dumps(clob_data, indent=2, default=str)[:2000])
    else:
        print("❌ No data from CLOB API")
    
    # Summary
    print(f"\n\n3. SUMMARY:")
    print("-" * 80)
    if gamma_data and gamma_data.get("matching_market"):
        market = gamma_data["matching_market"]
        market_id = (market.get("id") or market.get("marketId") or market.get("tid") or 
                    market.get("marketIdNum"))
        event_slug = gamma_data["event"].get("slug")
        market_slug = (market.get("slug") or market.get("marketSlug") or 
                      market.get("market_slug"))
        
        print(f"   Event slug: {event_slug}")
        print(f"   Market slug: {market_slug}")
        print(f"   Market ID from Gamma: {market_id}")
        
        if clob_data:
            clob_market_id = (clob_data.get('id') or clob_data.get('marketId') or 
                            clob_data.get('tid'))
            print(f"   Market ID from CLOB: {clob_market_id}")
            
            if clob_market_id:
                print(f"\n   ✅ RECOMMENDED URL: https://polymarket.com/event/{event_slug}?tid={clob_market_id}")
            elif market_slug and event_slug:
                print(f"\n   ⚠️  FALLBACK URL: https://polymarket.com/event/{event_slug}/{market_slug}")
            elif event_slug:
                print(f"\n   ❌ INCOMPLETE URL (event only): https://polymarket.com/event/{event_slug}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 debug_market_url.py <condition_id>")
        print("\nExample:")
        print("  python3 debug_market_url.py 0x1234567890abcdef...")
        sys.exit(1)
    
    condition_id = sys.argv[1]
    analyze_market(condition_id)

