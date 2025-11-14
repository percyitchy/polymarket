#!/usr/bin/env python3
"""
Fetch trader addresses from Polymarket trades API
This module collects wallet addresses from recent trades on active markets.

Note: This is a preparation module for future use. Set ENABLE_TRADES_API=false in .env
to keep it disabled until ready to integrate.
"""

import os
import time
import requests
import logging
from typing import List, Set, Optional, Dict, Any
from dotenv import load_dotenv

# Try to import ProxyManager
try:
    from proxy_manager import ProxyManager
    PROXY_MANAGER_AVAILABLE = True
except ImportError:
    PROXY_MANAGER_AVAILABLE = False
    ProxyManager = None

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
ENABLE_TRADES_API = os.getenv("ENABLE_TRADES_API", "false").lower() == "true"
MARKETS_LIMIT = int(os.getenv("TRADES_API_MARKETS_LIMIT", "100"))  # Number of markets to process
TRADES_PER_MARKET = int(os.getenv("TRADES_API_TRADES_PER_MARKET", "200"))  # Trades to fetch per market
API_TIMEOUT = int(os.getenv("TRADES_API_TIMEOUT", "15"))  # Request timeout in seconds
MAX_RETRIES = int(os.getenv("TRADES_API_MAX_RETRIES", "3"))  # Max retry attempts

# Polymarket API endpoints
MARKETS_API_URL = "https://clob.polymarket.com/markets"
TRADES_API_URL = "https://clob.polymarket.com/trades"  # May need adjustment based on actual API

# Initialize proxy manager
_proxy_manager = None
if PROXY_MANAGER_AVAILABLE:
    try:
        _proxy_manager = ProxyManager()
        if _proxy_manager.proxy_enabled:
            logger.info(f"[TradesAPI] Proxy manager initialized with {len(_proxy_manager.proxies)} proxies")
    except Exception as e:
        logger.warning(f"[TradesAPI] Failed to initialize proxy manager: {e}")


def _get_proxy() -> Optional[Dict[str, str]]:
    """Get proxy for requests if available"""
    if _proxy_manager and _proxy_manager.proxy_enabled:
        return _proxy_manager.get_proxy(rotate=True)
    return None


def _make_request(url: str, params: Optional[Dict[str, Any]] = None, method: str = "GET") -> Optional[requests.Response]:
    """
    Make HTTP request with retry logic and proxy support
    
    Args:
        url: Request URL
        params: Query parameters
        method: HTTP method (GET or POST)
    
    Returns:
        Response object or None if failed
    """
    proxy = _get_proxy()
    
    for attempt in range(MAX_RETRIES):
        try:
            if method.upper() == "GET":
                response = requests.get(url, params=params, timeout=API_TIMEOUT, proxies=proxy, verify=False)
            else:
                response = requests.post(url, json=params, timeout=API_TIMEOUT, proxies=proxy, verify=False)
            
            if response.status_code == 200:
                return response
            elif response.status_code == 429:  # Rate limit
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(f"[TradesAPI] Rate limited, waiting {retry_after}s before retry {attempt + 1}/{MAX_RETRIES}")
                time.sleep(retry_after)
                continue
            else:
                logger.warning(f"[TradesAPI] Non-200 status {response.status_code} on attempt {attempt + 1}/{MAX_RETRIES}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"[TradesAPI] Request error on attempt {attempt + 1}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
    
    return None


def get_active_markets(limit: int = MARKETS_LIMIT) -> List[Dict[str, Any]]:
    """
    Get list of active markets from Polymarket API
    
    Args:
        limit: Maximum number of markets to return
    
    Returns:
        List of market dictionaries
    """
    logger.info(f"[TradesAPI] Fetching active markets (limit: {limit})")
    
    params = {
        "limit": limit,
        "active": "true",  # Only active markets
        "sort": "volume",  # Sort by volume to get most liquid markets
        "order": "desc"
    }
    
    response = _make_request(MARKETS_API_URL, params=params)
    if not response:
        logger.error("[TradesAPI] Failed to fetch active markets")
        return []
    
    try:
        data = response.json()
        markets = data if isinstance(data, list) else data.get("markets", data.get("data", []))
        
        if not markets:
            logger.warning("[TradesAPI] No markets returned from API")
            return []
        
        logger.info(f"[TradesAPI] Found {len(markets)} active markets")
        return markets[:limit]
        
    except Exception as e:
        logger.error(f"[TradesAPI] Error parsing markets response: {e}")
        return []


def get_market_trades(condition_id: str, limit: int = TRADES_PER_MARKET) -> List[Dict[str, Any]]:
    """
    Get recent trades for a specific market
    
    Args:
        condition_id: Market condition ID
        limit: Maximum number of trades to fetch
    
    Returns:
        List of trade dictionaries
    """
    # Note: Actual API endpoint may differ - adjust based on Polymarket API documentation
    url = f"{TRADES_API_URL}/{condition_id}"
    
    params = {
        "limit": limit,
        "sort": "timestamp",
        "order": "desc"
    }
    
    response = _make_request(url, params=params)
    if not response:
        return []
    
    try:
        data = response.json()
        trades = data if isinstance(data, list) else data.get("trades", data.get("data", []))
        return trades[:limit] if trades else []
        
    except Exception as e:
        logger.debug(f"[TradesAPI] Error parsing trades for {condition_id}: {e}")
        return []


def extract_addresses_from_trades(trades: List[Dict[str, Any]]) -> Set[str]:
    """
    Extract unique wallet addresses from trades
    
    Args:
        trades: List of trade dictionaries
    
    Returns:
        Set of unique wallet addresses
    """
    addresses = set()
    
    for trade in trades:
        # Try common field names for maker/taker addresses
        for field in ["maker", "taker", "user", "trader", "address", "wallet"]:
            if field in trade:
                value = trade[field]
                if isinstance(value, str) and value.startswith("0x") and len(value) == 42:
                    addresses.add(value.lower())
        
        # Also check nested structures
        if "user" in trade and isinstance(trade["user"], dict):
            for field in ["address", "wallet", "id"]:
                if field in trade["user"]:
                    value = trade["user"][field]
                    if isinstance(value, str) and value.startswith("0x") and len(value) == 42:
                        addresses.add(value.lower())
    
    return addresses


def fetch_trader_addresses_from_trades(markets_limit: int = MARKETS_LIMIT, 
                                       trades_per_market: int = TRADES_PER_MARKET) -> List[str]:
    """
    Fetch trader addresses from recent trades on active Polymarket markets
    
    This function:
    1. Gets list of active markets (sorted by volume)
    2. For each market, fetches recent trades
    3. Extracts maker/taker addresses from trades
    4. Returns deduplicated list of addresses
    
    Args:
        markets_limit: Number of markets to process (default: from env or 100)
        trades_per_market: Number of trades to fetch per market (default: from env or 200)
    
    Returns:
        List of unique wallet addresses
    """
    if not ENABLE_TRADES_API:
        logger.info("[TradesAPI] Trades API collection is disabled (ENABLE_TRADES_API=false)")
        return []
    
    logger.info("=" * 80)
    logger.info(f"[TradesAPI] Starting trader address collection from trades")
    logger.info(f"[TradesAPI] Markets limit: {markets_limit}, Trades per market: {trades_per_market}")
    logger.info("=" * 80)
    
    all_addresses = set()
    
    # Step 1: Get active markets
    markets = get_active_markets(limit=markets_limit)
    if not markets:
        logger.warning("[TradesAPI] No markets available, returning empty list")
        return []
    
    # Step 2: Process each market
    successful_markets = 0
    failed_markets = 0
    
    for idx, market in enumerate(markets, 1):
        condition_id = market.get("condition_id") or market.get("id") or market.get("market_id")
        if not condition_id:
            logger.warning(f"[TradesAPI] Market {idx} has no condition_id, skipping")
            failed_markets += 1
            continue
        
        market_title = market.get("title") or market.get("question") or condition_id[:20]
        logger.info(f"[TradesAPI] Processing market {idx}/{len(markets)}: {market_title[:50]}...")
        
        # Get trades for this market
        trades = get_market_trades(condition_id, limit=trades_per_market)
        if not trades:
            logger.debug(f"[TradesAPI] No trades found for market {condition_id}")
            failed_markets += 1
            continue
        
        # Extract addresses
        market_addresses = extract_addresses_from_trades(trades)
        new_addresses = market_addresses - all_addresses
        all_addresses.update(market_addresses)
        
        logger.info(f"[TradesAPI] Market {idx}: {len(trades)} trades, {len(market_addresses)} addresses "
                   f"({len(new_addresses)} new, total: {len(all_addresses)})")
        
        successful_markets += 1
        
        # Rate limiting - small delay between markets
        if idx < len(markets):
            time.sleep(0.5)
    
    # Summary
    logger.info("=" * 80)
    logger.info(f"[TradesAPI] Collection Summary:")
    logger.info(f"  Markets processed: {successful_markets} successful, {failed_markets} failed")
    logger.info(f"  Total unique addresses collected: {len(all_addresses)}")
    logger.info("=" * 80)
    
    return list(all_addresses)


if __name__ == "__main__":
    # Test the module
    print("Testing Polymarket Trades API module...")
    print(f"ENABLE_TRADES_API = {ENABLE_TRADES_API}")
    
    if ENABLE_TRADES_API:
        addresses = fetch_trader_addresses_from_trades()
        print(f"\n✅ Success! Found {len(addresses)} unique addresses")
        if addresses:
            print(f"\nFirst 10 addresses:")
            for addr in addresses[:10]:
                print(f"  {addr}")
            if len(addresses) > 10:
                print(f"  ... and {len(addresses) - 10} more")
    else:
        print("\n⚠️  Trades API collection is disabled. Set ENABLE_TRADES_API=true in .env to enable.")

