#!/usr/bin/env python3
"""
Direct API fetch for polymarketanalytics.com/traders
Вариант A - если сайт предоставляет API (рекомендованный)
"""

import os
import time
import requests
from requests.exceptions import ReadTimeout, ConnectionError as RequestsConnectionError
import logging
from typing import List, Optional, Dict, Any, Union, Tuple
from dotenv import load_dotenv

load_dotenv()

# Try to import ProxyManager
try:
    from proxy_manager import ProxyManager
    PROXY_MANAGER_AVAILABLE = True
except ImportError:
    PROXY_MANAGER_AVAILABLE = False
    ProxyManager = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Filtering criteria constants (must match wallet_analyzer.py)
MIN_TRADES = 6  # Minimum number of trades required
MIN_WIN_RATE = float(os.getenv("WIN_RATE_THRESHOLD", "0.65"))  # Minimum win rate (65%, configurable via .env)
MAX_DAILY_FREQ = float(os.getenv("MAX_DAILY_FREQUENCY", "35.0"))  # Maximum daily trading frequency (configurable via .env)
ANALYTICS_LIMIT = int(os.getenv("ANALYTICS_LIMIT", "5000"))  # Maximum addresses to fetch from Analytics API (default 5000)

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

# Initialize proxy manager if available
_proxy_manager = None
if PROXY_MANAGER_AVAILABLE:
    try:
        _proxy_manager = ProxyManager()
        if _proxy_manager.proxy_enabled:
            logger.info(f"[Analytics API] Proxy manager initialized with {len(_proxy_manager.proxies)} proxies")
    except Exception as e:
        logger.warning(f"[Analytics API] Failed to initialize proxy manager: {e}")


def make_request_with_retry(method: str, url: str, segment_name: str = None, 
                           timeout: int = 15, max_retries: int = 2, 
                           **kwargs) -> requests.Response:
    """
    Make HTTP request with retry logic for polymarketanalytics.com
    
    Args:
        method: HTTP method ('GET' or 'POST')
        url: Request URL
        segment_name: Optional segment name for logging
        timeout: Request timeout in seconds (default 15, 10 for polymarketanalytics.com)
        max_retries: Maximum number of retries (default 2)
        **kwargs: Additional arguments to pass to requests.get/post
    
    Returns:
        requests.Response object
    
    Raises:
        requests.exceptions.RequestException: If all retries fail
    """
    is_analytics_api = "polymarketanalytics.com" in url
    request_timeout = 10 if is_analytics_api else timeout
    
    for attempt in range(max_retries + 1):
        try:
            if method.upper() == "POST":
                response = requests.post(url, timeout=request_timeout, **kwargs)
            else:
                response = requests.get(url, timeout=request_timeout, **kwargs)
            return response
        except (ReadTimeout, RequestsConnectionError) as e:
            if attempt < max_retries:
                # Log retry attempt
                if segment_name:
                    logger.warning(f"[Analytics API] Timeout on segment {segment_name}, retry {attempt+1}/{max_retries}")
                else:
                    logger.warning(f"[Analytics API] Timeout on {url}, retry {attempt+1}/{max_retries}")
                # Wait 2 seconds before retry
                time.sleep(2)
                continue
            else:
                # All retries exhausted
                if segment_name:
                    logger.error(f"[Analytics API] Failed after {max_retries+1} attempts on segment {segment_name}: {e}")
                else:
                    logger.error(f"[Analytics API] Failed after {max_retries+1} attempts: {e}")
                raise
        except requests.exceptions.RequestException as e:
            # For other request exceptions, don't retry
            raise


def try_endpoint(url: str, target: int = 2000, collect_stats: bool = False, 
                 period: Optional[str] = None, sort_by: Optional[str] = None,
                 segment_name: Optional[str] = None) -> Tuple[Optional[List[str]], Dict[str, int]]:
    """
    Try to fetch traders from API endpoint
    
    Args:
        url: API endpoint URL
        target: Maximum number of addresses to fetch
        collect_stats: If True, collect statistics about filtering
        period: Optional period filter (e.g., "24h", "7d", "30d", "all")
        sort_by: Optional sort column (e.g., "updatedAt", "overall_gain", "winRate")
        segment_name: Optional segment name for logging retry attempts
    
    Returns:
        Tuple of (list of addresses or None, stats dictionary)
    """
    traders = []
    limit = 500  # пробуем большие страницы, если API позволяет
    offset = 0
    
    # Statistics counters
    stats = {
        "total_traders": 0,
        "missing_stats": 0,
        "below_trades": 0,
        "below_winrate": 0,
        "above_freq": 0,
        "meets_all": 0
    }
    
    logger.info(f"[Analytics API] Trying endpoint: {url}")
    
    # Check if this is the real traders API (POST endpoint)
    is_post_api = "traders-tag-performance" in url
    
    # Determine sort column - prefer updatedAt for fresh data, fallback to overall_gain
    sort_column = sort_by or "updatedAt" if is_post_api else "overall_gain"
    
    # For the real API, try to get all in one request first
    if is_post_api and offset == 0:
        # Try getting all requested amount in one go
        # API may support up to 2500 per request, but use configured limit if lower
        initial_limit = min(target, min(ANALYTICS_LIMIT, 2500))
        try:
            payload = {
                "tag": "Overall",
                "sortColumn": sort_column,
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
            
            # Add period filter if provided
            if period:
                payload["period"] = period
            
            logger.info(f"[Analytics API] Using endpoint={url}, params=sortColumn={sort_column}, period={period}, limit={initial_limit}")
            headers_post = headers.copy()
            headers_post["Content-Type"] = "application/json"
            
            # Get proxy if available
            proxy = None
            if _proxy_manager and _proxy_manager.proxy_enabled:
                proxy = _proxy_manager.get_proxy(rotate=True)
                if proxy:
                    headers_post['Connection'] = 'close'
                    headers_post['Proxy-Connection'] = 'close'
            
            # Use retry function for polymarketanalytics.com requests
            try:
                r = make_request_with_retry(
                    "POST", url, 
                    segment_name=segment_name or period or "initial",
                    headers=headers_post, 
                    json=payload, 
                    proxies=proxy, 
                    verify=False
                )
            except (ReadTimeout, RequestsConnectionError) as e:
                logger.debug(f"  Single request failed after retry: {e}, falling back to pagination")
                # Continue to pagination below
                r = None
            
            if r and r.status_code == 200:
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
                        
                        # Collect statistics if requested
                        if collect_stats and isinstance(it, dict):
                            stats["total_traders"] += 1
                            
                            # Extract metrics from API response
                            trades = it.get("total_positions") or it.get("totalPositions") or it.get("positions") or it.get("trades")
                            win_rate = it.get("win_rate") or it.get("winRate")
                            # Daily frequency is not directly available, estimate from total_positions
                            # Assume average trading period of 365 days for estimation
                            daily_freq = None
                            if trades is not None:
                                # Rough estimate: trades / 365 days
                                daily_freq = float(trades) / 365.0 if trades > 0 else 0.0
                            
                            # Check if metrics are missing
                            if trades is None or win_rate is None:
                                stats["missing_stats"] += 1
                                if addr and addr not in traders:
                                    traders.append(addr)  # Still add address even without stats
                                continue
                            
                            # Convert win_rate to float if needed
                            try:
                                win_rate = float(win_rate)
                                if win_rate > 1.0:
                                    win_rate = win_rate / 100.0  # Convert percentage to decimal
                            except (ValueError, TypeError):
                                stats["missing_stats"] += 1
                                if addr and addr not in traders:
                                    traders.append(addr)
                                continue
                            
                            trades = int(trades) if trades is not None else 0
                            
                            # Apply filtering criteria and collect statistics
                            if trades < MIN_TRADES:
                                stats["below_trades"] += 1
                            elif win_rate < MIN_WIN_RATE:
                                stats["below_winrate"] += 1
                            elif daily_freq is not None and daily_freq > MAX_DAILY_FREQ:
                                stats["above_freq"] += 1
                            else:
                                stats["meets_all"] += 1
                                # This address meets all criteria
                                if addr and addr not in traders:
                                    traders.append(addr)
                        else:
                            # No stats collection, just add address
                            if addr and addr not in traders:
                                traders.append(addr)
                    
                    logger.info(f"[Analytics API] Extracted {len(traders)} unique addresses")
                    if len(traders) >= target:
                        if collect_stats:
                            logger.info(
                                "[Analytics Filtering stats] total=%d, meets_all=%d, "
                                "below_trades=%d, below_winrate=%d, above_freq=%d, missing_stats=%d "
                                "(MIN_TRADES=%d, MIN_WIN_RATE=%.2f, MAX_DAILY_FREQ=%.1f)",
                                stats["total_traders"], stats["meets_all"],
                                stats["below_trades"], stats["below_winrate"], stats["above_freq"], stats["missing_stats"],
                                MIN_TRADES, MIN_WIN_RATE, MAX_DAILY_FREQ
                            )
                        logger.info(f"[Analytics API] Returned {len(traders)} traders")
                        return traders[:target], stats
        except Exception as e:
            logger.debug(f"  Single request failed: {e}, falling back to pagination")
            # If we got some traders before the error, keep them
            # Continue to pagination below
    
    while len(traders) < target:
        try:
            if is_post_api:
                # Use POST with real parameters
                payload = {
                    "tag": "Overall",
                    "sortColumn": sort_column,
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
                
                # Add period filter if provided
                if period:
                    payload["period"] = period
                headers_post = headers.copy()
                headers_post["Content-Type"] = "application/json"
                
                # Get proxy if available
                proxy = None
                if _proxy_manager and _proxy_manager.proxy_enabled:
                    proxy = _proxy_manager.get_proxy(rotate=True)
                    if proxy:
                        headers_post['Connection'] = 'close'
                        headers_post['Proxy-Connection'] = 'close'
                
                # Use retry function for polymarketanalytics.com requests
                r = make_request_with_retry(
                    "POST", url,
                    segment_name=segment_name or period or f"page_{offset // limit + 1}",
                    headers=headers_post, 
                    json=payload, 
                    proxies=proxy, 
                    verify=False
                )
            else:
                # Try GET for other endpoints (not polymarketanalytics.com, no retry needed)
                request_headers = headers.copy()
                proxy = None
                if _proxy_manager and _proxy_manager.proxy_enabled:
                    proxy = _proxy_manager.get_proxy(rotate=True)
                    if proxy:
                        request_headers['Connection'] = 'close'
                        request_headers['Proxy-Connection'] = 'close'
                
                params = {"limit": limit, "offset": offset}
                r = requests.get(url, headers=request_headers, params=params, timeout=15, proxies=proxy, verify=False)
            
            logger.info(f"  Status: {r.status_code}")
            
            if r.status_code != 200:
                logger.warning(f"  Non-200 status: {r.status_code}")
                # Return what we have so far, even if it's partial
                if traders:
                    logger.info(f"  Returning {len(traders)} addresses collected before error")
                    if collect_stats:
                        logger.info(
                            "[Analytics Filtering stats] total=%d, meets_all=%d, "
                            "below_trades=%d, below_winrate=%d, above_freq=%d, missing_stats=%d "
                            "(MIN_TRADES=%d, MIN_WIN_RATE=%.2f, MAX_DAILY_FREQ=%.1f)",
                            stats["total_traders"], stats["meets_all"],
                            stats["below_trades"], stats["below_winrate"], stats["above_freq"], stats["missing_stats"],
                            MIN_TRADES, MIN_WIN_RATE, MAX_DAILY_FREQ
                        )
                    return traders[:target], stats
                return [], stats
            
            j = r.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"  Request error: {e}")
            # Return what we have so far, even if it's partial
            if traders:
                logger.info(f"  Returning {len(traders)} addresses collected before error")
                if collect_stats:
                    logger.info(
                        "[Analytics Filtering stats] total=%d, meets_all=%d, "
                        "below_trades=%d, below_winrate=%d, above_freq=%d, missing_stats=%d "
                        "(MIN_TRADES=%d, MIN_WIN_RATE=%.2f, MAX_DAILY_FREQ=%.1f)",
                        stats["total_traders"], stats["meets_all"],
                        stats["below_trades"], stats["below_winrate"], stats["above_freq"], stats["missing_stats"],
                        MIN_TRADES, MIN_WIN_RATE, MAX_DAILY_FREQ
                    )
                return traders[:target], stats
            return [], stats
        except ValueError as e:
            logger.error(f"  JSON decode error: {e}")
            # Return what we have so far, even if it's partial
            if traders:
                logger.info(f"  Returning {len(traders)} addresses collected before error")
                if collect_stats:
                    logger.info(
                        "[Analytics Filtering stats] total=%d, meets_all=%d, "
                        "below_trades=%d, below_winrate=%d, above_freq=%d, missing_stats=%d "
                        "(MIN_TRADES=%d, MIN_WIN_RATE=%.2f, MAX_DAILY_FREQ=%.1f)",
                        stats["total_traders"], stats["meets_all"],
                        stats["below_trades"], stats["below_winrate"], stats["above_freq"], stats["missing_stats"],
                        MIN_TRADES, MIN_WIN_RATE, MAX_DAILY_FREQ
                    )
                return traders[:target], stats
            return [], stats
        
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
            # Return what we have so far, even if it's partial
            if traders:
                logger.info(f"  Returning {len(traders)} addresses collected before error")
                if collect_stats:
                    logger.info(
                        "[Analytics Filtering stats] total=%d, meets_all=%d, "
                        "below_trades=%d, below_winrate=%d, above_freq=%d, missing_stats=%d "
                        "(MIN_TRADES=%d, MIN_WIN_RATE=%.2f, MAX_DAILY_FREQ=%.1f)",
                        stats["total_traders"], stats["meets_all"],
                        stats["below_trades"], stats["below_winrate"], stats["above_freq"], stats["missing_stats"],
                        MIN_TRADES, MIN_WIN_RATE, MAX_DAILY_FREQ
                    )
                return traders[:target], stats
            return [], stats
        
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
            
            # Collect statistics if requested
            if collect_stats and isinstance(it, dict):
                stats["total_traders"] += 1
                
                # Extract metrics from API response
                trades = it.get("total_positions") or it.get("totalPositions") or it.get("positions") or it.get("trades")
                win_rate = it.get("win_rate") or it.get("winRate")
                # Daily frequency is not directly available, estimate from total_positions
                daily_freq = None
                if trades is not None:
                    # Rough estimate: trades / 365 days
                    daily_freq = float(trades) / 365.0 if trades > 0 else 0.0
                
                # Check if metrics are missing
                if trades is None or win_rate is None:
                    stats["missing_stats"] += 1
                    if addr and addr not in traders:
                        traders.append(addr)  # Still add address even without stats
                        found_in_batch += 1
                    continue
                
                # Convert win_rate to float if needed
                try:
                    win_rate = float(win_rate)
                    if win_rate > 1.0:
                        win_rate = win_rate / 100.0  # Convert percentage to decimal
                except (ValueError, TypeError):
                    stats["missing_stats"] += 1
                    if addr and addr not in traders:
                        traders.append(addr)
                        found_in_batch += 1
                    continue
                
                trades = int(trades) if trades is not None else 0
                
                # Apply filtering criteria and collect statistics
                if trades < MIN_TRADES:
                    stats["below_trades"] += 1
                elif win_rate < MIN_WIN_RATE:
                    stats["below_winrate"] += 1
                elif daily_freq is not None and daily_freq > MAX_DAILY_FREQ:
                    stats["above_freq"] += 1
                else:
                    stats["meets_all"] += 1
                    # This address meets all criteria
                    if addr and addr not in traders:
                        traders.append(addr)
                        found_in_batch += 1
            else:
                # No stats collection, just add address
                if addr and addr not in traders:  # Avoid duplicates
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
        logger.info(f"[Analytics API] Successfully fetched {len(traders)} addresses from {url}")
        if collect_stats:
            logger.info(
                "[Analytics Filtering stats] total=%d, meets_all=%d, "
                "below_trades=%d, below_winrate=%d, above_freq=%d, missing_stats=%d "
                "(MIN_TRADES=%d, MIN_WIN_RATE=%.2f, MAX_DAILY_FREQ=%.1f)",
                stats["total_traders"], stats["meets_all"],
                stats["below_trades"], stats["below_winrate"], stats["above_freq"], stats["missing_stats"],
                MIN_TRADES, MIN_WIN_RATE, MAX_DAILY_FREQ
            )
        return traders[:target], stats
    
    # Return empty list instead of None to avoid unpacking errors
    return [], stats


def fetch_traders_from_api(target: int = None, return_stats: bool = False, 
                           period: Optional[str] = None, sort_by: Optional[str] = None) -> Union[List[str], Tuple[List[str], Dict[str, int]]]:
    """
    Fetch traders from Polymarket Analytics API using multiple selection strategies
    
    Makes several API calls with different parameters (period, sort_by) to get diverse trader sets:
    - period=7d, sort_by=overall_gain (or pnl/profit) - top performers by PnL
    - period=30d, sort_by=volume (or totalPositions) - high volume traders
    - period=all, sort_by=totalPositions (or tradesCount) - all-time top traders by trade count
    - period=24h, sort_by=updatedAt - recent active traders
    
    Args:
        target: Maximum number of unique addresses to fetch (defaults to ANALYTICS_LIMIT)
        return_stats: If True, return tuple (addresses, stats_dict) instead of just addresses
        period: Optional period filter (if provided, only this period is used - for backward compatibility)
        sort_by: Optional sort column (if provided, only this sort is used - for backward compatibility)
    
    Returns:
        List of unique addresses, or tuple (addresses, stats_dict) if return_stats=True
    """
    if target is None:
        target = ANALYTICS_LIMIT
    
    # Multiple selection strategies for diverse trader collection
    # Each segment represents a different "slice" of the trader population:
    # - "24h updatedAt" - most recently active traders (fresh data)
    # - "7d overall_gain" - top performers by profit/loss over 7 days
    # - "30d totalPositions" - high volume traders over 30 days
    # - "all totalPositions" - all-time top traders by trade count (long-term grinders)
    selection_strategies = [
        {"period": "24h", "sort_by": "updatedAt", "name": "24h Recent", "description": "Most recently active traders"},
        {"period": "7d", "sort_by": "overall_gain", "name": "7d PnL", "description": "Top performers by profit/loss"},
        {"period": "30d", "sort_by": "totalPositions", "name": "30d Volume", "description": "High volume traders"},
        {"period": "all", "sort_by": "totalPositions", "name": "All-time Trades", "description": "All-time top traders by trade count"},
    ]
    
    # If period/sort_by provided explicitly, use single strategy (backward compatibility)
    if period is not None or sort_by is not None:
        selection_strategies = [{"period": period or "24h", "sort_by": sort_by or "updatedAt", "name": "Custom"}]
    
    all_addrs_set = set()  # Use set to deduplicate addresses
    all_stats = {
        "total_traders": 0,
        "missing_stats": 0,
        "below_trades": 0,
        "below_winrate": 0,
        "above_freq": 0,
        "meets_all": 0
    }
    
    strategy_results = []
    
    # Global time budget: don't spend more than 90 seconds on entire collection
    start_time = time.time()
    max_total_seconds = 90
    
    # Try each selection strategy
    for strategy in selection_strategies:
        # Check global time budget
        elapsed = time.time() - start_time
        if elapsed > max_total_seconds:
            logger.warning(f"[Analytics API] Global time budget exceeded ({elapsed:.1f}s > {max_total_seconds}s), returning partial result")
            break
        strategy_period = strategy["period"]
        strategy_sort = strategy["sort_by"]
        strategy_name = strategy["name"]
        
        strategy_desc = strategy.get("description", "")
        logger.info(f"[Analytics API] Segment: {strategy_name} ({strategy_desc})")
        logger.info(f"[Analytics API]   Parameters: period={strategy_period}, sort_by={strategy_sort}")
        
        # Calculate how many more addresses we need
        remaining_target = target - len(all_addrs_set)
        if remaining_target <= 0:
            logger.info(f"[Analytics API] Already collected {len(all_addrs_set)} addresses, target reached")
            break
        
        # Try the real API endpoint first (POST)
        logger.info(f"[Analytics API]   Calling endpoint: {TRADERS_API_URL}")
        res, endpoint_stats = try_endpoint(
            TRADERS_API_URL, 
            remaining_target, 
            collect_stats=return_stats, 
            period=strategy_period, 
            sort_by=strategy_sort,
            segment_name=strategy_name
        )
        
        if res:
            unique_new = [addr for addr in res if addr not in all_addrs_set]
            all_addrs_set.update(unique_new)
            
            # Merge stats
            for key in all_stats:
                all_stats[key] += endpoint_stats.get(key, 0)
            
            strategy_results.append({
                "name": strategy_name,
                "period": strategy_period,
                "sort_by": strategy_sort,
                "returned": len(res),
                "unique_new": len(unique_new),
                "total_unique": len(all_addrs_set)
            })
            
            logger.info(f"[Analytics API]   Segment {strategy_name}: fetched {len(res)} traders, {len(unique_new)} new unique (total: {len(all_addrs_set)})")
        else:
            logger.warning(f"[Analytics API] Request failed after retry, skipping segment {strategy_name}")
            strategy_results.append({
                "name": strategy_name,
                "period": strategy_period,
                "sort_by": strategy_sort,
                "returned": 0,
                "unique_new": 0,
                "total_unique": len(all_addrs_set)
            })
    
    # Convert set to list and limit to target
    all_addrs = list(all_addrs_set)[:target]
    
    # Log summary
    logger.info("=" * 80)
    logger.info(f"[Analytics API] Total unique addresses across all segments: {len(all_addrs)}")
    logger.info(f"[Analytics API] Segments processed: {len(strategy_results)}")
    for result in strategy_results:
        logger.info(f"[Analytics API]   segment={result['period']}/{result['sort_by']}, fetched {result['returned']} traders, "
                   f"{result['unique_new']} unique new")
    logger.info("=" * 80)
    
    if not all_addrs:
        logger.warning("[Analytics API] Could not fetch any addresses through API")
    
    if return_stats:
        return all_addrs, all_stats
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

