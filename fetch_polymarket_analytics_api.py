#!/usr/bin/env python3
"""
Direct API fetch for polymarketanalytics.com/traders
Вариант A - если сайт предоставляет API (рекомендованный)
"""

import time
import requests
import logging
from typing import List, Optional, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Реальный endpoint, найденный через перехват запросов
TRADERS_API_URL = "https://polymarketanalytics.com/api/traders-tag-performance"

# Варианты endpoint'ов (для обратной совместимости)
CANDIDATES = [
    "https://polymarketanalytics.com/api/traders",
    "https://polymarketanalytics.com/api/v1/traders",
    "https://polymarketanalytics.com/api/traders/list",
    "https://polymarketanalytics.com/api/leaderboard/traders",
]

headers = {
    "User-Agent": "Mozilla/5.0 (compatible; DataCollector/1.0; +https://polymarket.com/)",
    "Accept": "application/json",
}


def try_endpoint(url: str, target: int = 2000) -> Optional[List[str]]:
    """Try to fetch traders from API endpoint"""
    traders = []
    limit = 500  # пробуем большие страницы, если API позволяет
    offset = 0
    
    logger.info(f"Trying endpoint: {url}")
    
    # Check if this is the real traders API (POST endpoint)
    is_post_api = "traders-tag-performance" in url
    
    # For the real API, try to get all in one request first
    if is_post_api and offset == 0:
        # Try getting all requested amount in one go
        initial_limit = min(target, 2000)  # API supports up to 2000 per request
        try:
            payload = {
                "tag": "Overall",
                "sortColumn": "overall_gain",
                "sortDirection": "DESC",
                "minPnL": -999999999,
                "maxPnL": 999999999,
                "minActivePositions": 0,
                "maxActivePositions": 999999,
                "minWinAmount": 0,
                "maxWinAmount": 999999999,
                "minLossAmount": -999999999,
                "maxLossAmount": 0,
                "minWinRate": 0,
                "maxWinRate": 100,
                "minCurrentValue": 0,
                "maxCurrentValue": 999999999,
                "minTotalPositions": 1,
                "maxTotalPositions": 10000,
                "limit": initial_limit,
                "offset": 0
            }
            headers_post = headers.copy()
            headers_post["Content-Type"] = "application/json"
            r = requests.post(url, headers=headers_post, json=payload, timeout=15)
            
            if r.status_code == 200:
                j = r.json()
                items = j.get('data', []) if isinstance(j, dict) else []
                if items:
                    logger.info(f"  Got {len(items)} items in single request")
                    for it in items:
                        addr = None
                        if isinstance(it, dict):
                            for key in ("trader", "address", "wallet", "id"):
                                if key in it:
                                    val = it[key]
                                    if isinstance(val, str) and val.startswith("0x") and len(val) == 42:
                                        addr = val.lower()
                                        break
                        if addr and addr not in traders:
                            traders.append(addr)
                    logger.info(f"  Extracted {len(traders)} unique addresses")
                    if len(traders) >= target:
                        return traders[:target]
        except Exception as e:
            logger.debug(f"  Single request failed: {e}, falling back to pagination")
    
    while len(traders) < target:
        try:
            if is_post_api:
                # Use POST with real parameters
                payload = {
                    "tag": "Overall",
                    "sortColumn": "overall_gain",
                    "sortDirection": "DESC",
                    "minPnL": -999999999,
                    "maxPnL": 999999999,
                    "minActivePositions": 0,
                    "maxActivePositions": 999999,
                    "minWinAmount": 0,
                    "maxWinAmount": 999999999,
                    "minLossAmount": -999999999,
                    "maxLossAmount": 0,
                    "minWinRate": 0,
                    "maxWinRate": 100,
                    "minCurrentValue": 0,
                    "maxCurrentValue": 999999999,
                    "minTotalPositions": 1,  # Start from 1, filter later
                    "maxTotalPositions": 10000,
                    "limit": limit,
                    "offset": offset
                }
                headers_post = headers.copy()
                headers_post["Content-Type"] = "application/json"
                r = requests.post(url, headers=headers_post, json=payload, timeout=15)
            else:
                # Try GET for other endpoints
                params = {"limit": limit, "offset": offset}
                r = requests.get(url, headers=headers, params=params, timeout=15)
            
            logger.info(f"  Status: {r.status_code}")
            
            if r.status_code != 200:
                logger.warning(f"  Non-200 status: {r.status_code}")
                return None
            
            j = r.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"  Request error: {e}")
            return None
        except ValueError as e:
            logger.error(f"  JSON decode error: {e}")
            return None
        
        # Extract data from response
        items = None
        total_count = None
        
        if isinstance(j, list):
            items = j
            logger.info(f"  Got list with {len(items)} items")
        elif isinstance(j, dict):
            # Try common keys
            for k in ("data", "traders", "results", "items", "leaderboard"):
                if k in j and isinstance(j[k], list):
                    items = j[k]
                    logger.info(f"  Found key '{k}' with {len(items)} items")
                    break
            # Get total count if available
            total_count = j.get('totalCount', j.get('total', None))
        
        if not items:
            logger.warning(f"  No array found in response. Keys: {list(j.keys()) if isinstance(j, dict) else 'N/A'}")
            return None
        
        if not items:
            logger.info("  No more items, reached end")
            break
        
        # Extract addresses
        found_in_batch = 0
        for it in items:
            addr = None
            
            # Try different possible address fields
            if isinstance(it, dict):
                for key in ("trader", "address", "wallet", "id", "traderAddress", "walletAddress", "user"):
                    if key in it:
                        val = it[key]
                        if isinstance(val, str) and val.startswith("0x") and len(val) == 42:
                            addr = val.lower()
                            break
            elif isinstance(it, str) and it.startswith("0x") and len(it) == 42:
                addr = it.lower()
            
            if addr:
                if addr not in traders:  # Avoid duplicates
                    traders.append(addr)
                    found_in_batch += 1
        
        logger.info(f"  Extracted {found_in_batch} new addresses (total: {len(traders)})")
        
        if len(traders) >= target:
            break
        
        # Check if we've reached the end
        # Note: total_count seems to decrease with offset, so we use it as reference
        if total_count and total_count == 0:
            logger.info(f"  Reached end (totalCount=0)")
            break
        
        # If we got fewer items than requested, we've reached the end
        if len(items) < limit:
            logger.info(f"  Got {len(items)} items (less than limit {limit}), reached end")
            break
        
        offset += limit
        time.sleep(0.5)  # Rate limiting
    
    if traders:
        logger.info(f"✅ Successfully fetched {len(traders)} addresses from {url}")
        return traders[:target]
    
    return None


def fetch_traders_from_api(target: int = 2000) -> List[str]:
    """Try all candidate endpoints until one works"""
    all_addrs = []
    
    # Try the real API endpoint first (POST)
    logger.info(f"\nTrying real API endpoint: {TRADERS_API_URL}")
    res = try_endpoint(TRADERS_API_URL, target)
    
    if res:
        logger.info(f"✅ Found {len(res)} addresses through {TRADERS_API_URL}")
        return res
    
    # Fallback to other candidates (GET endpoints)
    for ep in CANDIDATES:
        logger.info(f"\nTrying: {ep}")
        res = try_endpoint(ep, target)
        
        if res:
            logger.info(f"✅ Found {len(res)} addresses through {ep}")
            all_addrs = res
            break
        else:
            logger.info(f"❌ Failed: {ep}")
    
    if not all_addrs:
        logger.warning("❌ Could not fetch through direct API. May need headless browser approach.")
    
    return all_addrs


if __name__ == "__main__":
    print("Testing direct API access to polymarketanalytics.com...")
    addresses = fetch_traders_from_api(target=2000)
    
    if addresses:
        print(f"\n✅ Success! Found {len(addresses)} addresses")
        print(f"\nFirst 10 addresses:")
        for addr in addresses[:10]:
            print(f"  {addr}")
    else:
        print("\n❌ Could not fetch addresses via API")

