#!/usr/bin/env python3
"""
Adjacent News API Client
A clean client for accessing Adjacent News (adj.news) API endpoints with dual rate limiting and caching
"""

import os
import requests
import json
import logging
import time
import hashlib
from typing import Optional, Dict, Any, List
from collections import deque
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AdjNewsError(Exception):
    """Base exception for Adjacent News client errors"""
    pass


class RateLimitExceeded(AdjNewsError):
    """Raised when rate limit is exceeded"""
    def __init__(self, wait_time: float, limit_type: str = "daily"):
        self.wait_time = wait_time
        self.limit_type = limit_type
        super().__init__(f"{limit_type.capitalize()} rate limit exceeded. Wait {wait_time:.1f} seconds")


class AdjNewsClient:
    """Client for Adjacent News API (adj.news)"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.data.adj.news", timeout: int = 10):
        """
        Initialize Adjacent News client
        
        Args:
            api_key: Optional API key for authenticated requests (higher rate limits)
            base_url: Base URL for API (default: https://api.data.adj.news)
            timeout: Request timeout in seconds (default: 10)
        """
        self.api_key = api_key or os.getenv("ADJ_NEWS_API_KEY")
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
        # Setup headers
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
        
        # Rate limiting: Daily limit (33 requests per day)
        self.daily_limit_queries = 33
        self.daily_limit_window_seconds = 86400  # 24 hours
        self.daily_query_timestamps = deque(maxlen=self.daily_limit_queries)
        
        # Rate limiting: Per-minute limit (300 requests per minute unauthenticated, 1000 authenticated)
        self.minute_limit_queries = 1000 if self.api_key else 300
        self.minute_limit_window_seconds = 60  # 1 minute
        self.minute_query_timestamps = deque(maxlen=self.minute_limit_queries)
        
        # Caching with TTL
        self._cache = {}
        self.cache_ttl_seconds = 3600  # Default 1 hour TTL
        self._cache_hits = 0
        self._cache_misses = 0
        
        logger.debug(f"[AdjNews] Initialized client: base_url={self.base_url}, timeout={self.timeout}s, authenticated={bool(self.api_key)}")
    
    def _check_rate_limit(self) -> None:
        """
        Check if rate limit is exceeded for both daily and per-minute limits
        
        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        now = time.time()
        
        # Check daily limit
        while self.daily_query_timestamps and (now - self.daily_query_timestamps[0]) > self.daily_limit_window_seconds:
            self.daily_query_timestamps.popleft()
        
        if len(self.daily_query_timestamps) >= self.daily_limit_queries:
            oldest_timestamp = self.daily_query_timestamps[0]
            wait_time = self.daily_limit_window_seconds - (now - oldest_timestamp)
            if wait_time > 0:
                logger.warning(f"[AdjNews] Daily rate limit exceeded: {len(self.daily_query_timestamps)}/{self.daily_limit_queries} queries in last 24h. Wait {wait_time:.1f}s")
                raise RateLimitExceeded(wait_time, "daily")
        
        # Check per-minute limit
        while self.minute_query_timestamps and (now - self.minute_query_timestamps[0]) > self.minute_limit_window_seconds:
            self.minute_query_timestamps.popleft()
        
        if len(self.minute_query_timestamps) >= self.minute_limit_queries:
            oldest_timestamp = self.minute_query_timestamps[0]
            wait_time = self.minute_limit_window_seconds - (now - oldest_timestamp)
            if wait_time > 0:
                logger.warning(f"[AdjNews] Per-minute rate limit exceeded: {len(self.minute_query_timestamps)}/{self.minute_limit_queries} queries in last minute. Wait {wait_time:.1f}s")
                raise RateLimitExceeded(wait_time, "minute")
        
        # Record this query
        self.daily_query_timestamps.append(now)
        self.minute_query_timestamps.append(now)
    
    def _get_cache_key(self, endpoint: str, params: Optional[Dict] = None) -> str:
        """
        Generate cache key from endpoint and parameters
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            SHA256 hash of endpoint + sorted params
        """
        key_parts = [endpoint]
        if params:
            # Sort params for consistent keys
            sorted_params = sorted(params.items())
            key_parts.append(json.dumps(sorted_params, sort_keys=True))
        
        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve data from cache if not expired
        
        Args:
            cache_key: Cache key to look up
            
        Returns:
            Cached data or None if not found/expired
        """
        if cache_key not in self._cache:
            self._cache_misses += 1
            logger.debug(f"[AdjNews] Cache miss for key: {cache_key[:16]}...")
            return None
        
        cache_entry = self._cache[cache_key]
        expires_at = cache_entry.get('expires_at', 0)
        
        if time.time() > expires_at:
            # Expired, remove from cache
            del self._cache[cache_key]
            self._cache_misses += 1
            logger.debug(f"[AdjNews] Cache expired for key: {cache_key[:16]}...")
            return None
        
        self._cache_hits += 1
        logger.debug(f"[AdjNews] Cache hit for key: {cache_key[:16]}...")
        return cache_entry.get('data')
    
    def _set_cache(self, cache_key: str, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """
        Store data in cache with expiry timestamp
        
        Args:
            cache_key: Cache key
            data: Data to cache
            ttl: Time-to-live in seconds (defaults to self.cache_ttl_seconds)
        """
        if ttl is None:
            ttl = self.cache_ttl_seconds
        
        expires_at = time.time() + ttl
        self._cache[cache_key] = {
            'data': data,
            'expires_at': expires_at
        }
        logger.debug(f"[AdjNews] Cached data with key: {cache_key[:16]}..., TTL: {ttl}s")
    
    def _cleanup_expired_cache(self) -> None:
        """Remove expired entries from cache"""
        now = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.get('expires_at', 0) < now
        ]
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"[AdjNews] Cleaned up {len(expired_keys)} expired cache entries")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Dict with cache statistics
        """
        self._cleanup_expired_cache()
        
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_size': len(self._cache),
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'hit_rate_percent': round(hit_rate, 2),
            'total_requests': total_requests
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.exceptions.Timeout, requests.exceptions.ConnectionError))
    )
    def _make_request(self, endpoint: str, params: Optional[Dict] = None, method: str = 'GET', use_cache: bool = True, ttl: Optional[int] = None) -> Dict[str, Any]:
        """
        Make a request to the Adjacent News API
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            method: HTTP method (GET or POST)
            use_cache: Whether to use cache for this request
            ttl: Optional time-to-live in seconds for cache entry (defaults to self.cache_ttl_seconds)
            
        Returns:
            Parsed JSON response
            
        Raises:
            AdjNewsError: On API error
            RateLimitExceeded: If rate limit is exceeded
            requests.exceptions.Timeout: On request timeout (will be retried by decorator)
            requests.exceptions.ConnectionError: On connection error (will be retried by decorator)
        """
        # Check cache first if enabled
        if use_cache:
            cache_key = self._get_cache_key(endpoint, params)
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                return cached_data
        
        # Check rate limits
        self._check_rate_limit()
        
        # Build full URL
        url = f"{self.base_url}{endpoint}"
        
        start_time = time.time()
        
        try:
            # Make HTTP request
            if method.upper() == 'POST':
                response = requests.post(url, headers=self.headers, json=params, timeout=self.timeout)
            else:  # GET
                response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)
            
            elapsed = time.time() - start_time
            
            # Log query execution
            logger.debug(f"[AdjNews] Request executed in {elapsed:.2f}s: {method} {endpoint}")
            
            # Check response status
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(f"[AdjNews] API error: {error_msg}")
                raise AdjNewsError(error_msg)
            
            # Parse JSON response
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                logger.warning(f"[AdjNews] Failed to parse JSON response: {e}")
                raise AdjNewsError(f"Invalid JSON response: {e}")
            
            # Store in cache if successful and caching enabled
            if use_cache:
                self._set_cache(cache_key, data, ttl=ttl)
            
            logger.info(f"[AdjNews] ✅ Successfully fetched {endpoint} ({elapsed:.2f}s)")
            return data
            
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            # Let these propagate so tenacity retry decorator can handle them
            elapsed = time.time() - start_time
            logger.debug(f"[AdjNews] Request failed after {elapsed:.2f}s: {method} {endpoint} (will retry)")
            raise
        
        except requests.exceptions.RequestException as e:
            logger.warning(f"[AdjNews] Request error: {type(e).__name__}: {e}")
            raise AdjNewsError(f"Request error: {e}")
        
        except RateLimitExceeded:
            raise  # Re-raise rate limit errors
        
        except AdjNewsError:
            raise  # Re-raise API errors
        
        except Exception as e:
            logger.error(f"[AdjNews] Unexpected error: {type(e).__name__}: {e}")
            raise AdjNewsError(f"Unexpected error: {e}")
    
    def search_markets(self, query: str, platform: Optional[str] = 'polymarket', limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search markets using semantic search
        
        Args:
            query: Search query string (required)
            platform: Filter by platform (default: 'polymarket')
            limit: Maximum number of results (default: 10)
            
        Returns:
            List of market dictionaries or empty list on error
        """
        try:
            # Input validation
            if not query or not isinstance(query, str) or not query.strip():
                logger.warning("[AdjNews] Invalid query: must be non-empty string")
                return []
            
            if not isinstance(limit, int) or limit < 1:
                limit = 10
            
            # Build parameters
            params = {
                'q': query.strip(),
                'limit': min(limit, 100)  # Clamp to API max
            }
            if platform:
                params['platform'] = platform
            
            # Make request with 1-hour cache TTL
            response = self._make_request('/api/search/query', params=params, use_cache=True, ttl=3600)
            
            # Extract results
            if isinstance(response, dict):
                results = response.get('results', response.get('data', []))
            elif isinstance(response, list):
                results = response
            else:
                results = []
            
            logger.info(f"[AdjNews] ✅ Found {len(results)} markets for query: {query[:50]}...")
            return results if isinstance(results, list) else []
            
        except RateLimitExceeded as e:
            logger.warning(f"[AdjNews] Rate limit exceeded in search_markets: {e}")
            return []
        
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logger.warning(f"[AdjNews] Connection/timeout error in search_markets after retries: {type(e).__name__}: {e}")
            return []
        
        except AdjNewsError as e:
            logger.warning(f"[AdjNews] API error in search_markets: {e}")
            return []
        
        except Exception as e:
            logger.error(f"[AdjNews] Unexpected error in search_markets: {type(e).__name__}: {e}")
            return []
    
    def list_markets(self, platform: Optional[str] = 'polymarket', status: Optional[str] = None, sort: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List markets with filtering and sorting
        
        Args:
            platform: Filter by platform (default: 'polymarket')
            status: Filter by status (e.g., 'active', 'closed')
            sort: Sort order (e.g., 'volume:desc')
            limit: Maximum number of results (default: 100)
            offset: Pagination offset (default: 0)
            
        Returns:
            List of market dictionaries or empty list on error
        """
        try:
            # Input validation
            if not isinstance(limit, int) or limit < 1:
                limit = 100
            if not isinstance(offset, int) or offset < 0:
                offset = 0
            
            # Build parameters
            params = {
                'limit': min(limit, 1000),  # Clamp to API max
                'offset': offset
            }
            if platform:
                params['platform'] = platform
            if status:
                params['status'] = status
            if sort:
                params['sort'] = sort
            
            # Make request with 30-minute cache TTL
            response = self._make_request('/api/markets', params=params, use_cache=True, ttl=1800)
            
            # Extract results
            if isinstance(response, dict):
                results = response.get('results', response.get('data', response.get('markets', [])))
            elif isinstance(response, list):
                results = response
            else:
                results = []
            
            logger.info(f"[AdjNews] ✅ Found {len(results)} markets")
            return results if isinstance(results, list) else []
            
        except RateLimitExceeded as e:
            logger.warning(f"[AdjNews] Rate limit exceeded in list_markets: {e}")
            return []
        
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logger.warning(f"[AdjNews] Connection/timeout error in list_markets after retries: {type(e).__name__}: {e}")
            return []
        
        except AdjNewsError as e:
            logger.warning(f"[AdjNews] API error in list_markets: {e}")
            return []
        
        except Exception as e:
            logger.error(f"[AdjNews] Unexpected error in list_markets: {type(e).__name__}: {e}")
            return []
    
    def get_market_trades(self, market_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get trades for a specific market
        
        Args:
            market_id: Adjacent News market ID (required)
            limit: Maximum number of trades (default: 100)
            
        Returns:
            List of trade dictionaries or empty list on error
        """
        try:
            # Input validation
            if not market_id or not isinstance(market_id, str) or not market_id.strip():
                logger.warning("[AdjNews] Invalid market_id: must be non-empty string")
                return []
            
            if not isinstance(limit, int) or limit < 1:
                limit = 100
            
            # Build parameters
            params = {
                'limit': min(limit, 1000)  # Clamp to API max
            }
            
            # Make request with 5-minute cache TTL
            response = self._make_request(f'/api/trade/market/{market_id.strip()}', params=params, use_cache=True, ttl=300)
            
            # Extract results
            if isinstance(response, dict):
                results = response.get('results', response.get('data', response.get('trades', [])))
            elif isinstance(response, list):
                results = response
            else:
                results = []
            
            logger.info(f"[AdjNews] ✅ Found {len(results)} trades for market_id: {market_id[:30]}...")
            return results if isinstance(results, list) else []
            
        except RateLimitExceeded as e:
            logger.warning(f"[AdjNews] Rate limit exceeded in get_market_trades: {e}")
            return []
        
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logger.warning(f"[AdjNews] Connection/timeout error in get_market_trades after retries: {type(e).__name__}: {e}")
            return []
        
        except AdjNewsError as e:
            logger.warning(f"[AdjNews] API error in get_market_trades: {e}")
            return []
        
        except Exception as e:
            logger.error(f"[AdjNews] Unexpected error in get_market_trades: {type(e).__name__}: {e}")
            return []
    
    def get_market_news(self, market: str, days: int = 7, limit: int = 10, exclude_domains: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get news articles correlated with a market
        
        Args:
            market: Market ticker or topic (required)
            days: Lookback window in days (1-30, default: 7)
            limit: Maximum number of articles (default: 10, max: 50)
            exclude_domains: Comma-separated domain blacklist (default includes 'polymarket.com')
            
        Returns:
            List of news article dictionaries or empty list on error
        """
        try:
            # Input validation
            if not market or not isinstance(market, str) or not market.strip():
                logger.warning("[AdjNews] Invalid market: must be non-empty string")
                return []
            
            if not isinstance(days, int) or days < 1:
                days = 7
            elif days > 30:
                days = 30
            
            if not isinstance(limit, int) or limit < 1:
                limit = 10
            elif limit > 50:
                limit = 50
            
            # Build parameters
            params = {
                'days': days,
                'limit': limit
            }
            
            # Default exclude_domains includes polymarket.com
            if exclude_domains is None:
                exclude_domains = 'polymarket.com'
            if exclude_domains:
                params['exclude_domains'] = exclude_domains
            
            # Make request with 15-minute cache TTL
            response = self._make_request(f'/api/news/{market.strip()}', params=params, use_cache=True, ttl=900)
            
            # Extract results
            if isinstance(response, dict):
                results = response.get('results', response.get('data', response.get('articles', [])))
            elif isinstance(response, list):
                results = response
            else:
                results = []
            
            logger.info(f"[AdjNews] ✅ Found {len(results)} news articles for market: {market[:50]}...")
            return results if isinstance(results, list) else []
            
        except RateLimitExceeded as e:
            logger.warning(f"[AdjNews] Rate limit exceeded in get_market_news: {e}")
            return []
        
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logger.warning(f"[AdjNews] Connection/timeout error in get_market_news after retries: {type(e).__name__}: {e}")
            return []
        
        except AdjNewsError as e:
            logger.warning(f"[AdjNews] API error in get_market_news: {e}")
            return []
        
        except Exception as e:
            logger.error(f"[AdjNews] Unexpected error in get_market_news: {type(e).__name__}: {e}")
            return []
    
    def test_connection(self) -> bool:
        """
        Test API connectivity
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = self._make_request('/api/markets', params={'limit': 1}, use_cache=False)
            
            if response is not None:
                logger.info("[AdjNews] ✅ Connection test successful")
                return True
            else:
                logger.warning("[AdjNews] ❌ Connection test returned empty result")
                return False
                
        except Exception as e:
            logger.warning(f"[AdjNews] ❌ Connection test failed: {type(e).__name__}: {e}")
            return False
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Get current rate limit status for both daily and per-minute limits
        
        Returns:
            Dict with rate limit information
        """
        now = time.time()
        
        # Clean up daily timestamps
        while self.daily_query_timestamps and (now - self.daily_query_timestamps[0]) > self.daily_limit_window_seconds:
            self.daily_query_timestamps.popleft()
        
        daily_queries_used = len(self.daily_query_timestamps)
        daily_queries_remaining = self.daily_limit_queries - daily_queries_used
        
        if self.daily_query_timestamps:
            oldest_daily = self.daily_query_timestamps[0]
            daily_reset_time = datetime.fromtimestamp(oldest_daily + self.daily_limit_window_seconds)
        else:
            daily_reset_time = datetime.now()
        
        # Clean up minute timestamps
        while self.minute_query_timestamps and (now - self.minute_query_timestamps[0]) > self.minute_limit_window_seconds:
            self.minute_query_timestamps.popleft()
        
        minute_queries_used = len(self.minute_query_timestamps)
        minute_queries_remaining = self.minute_limit_queries - minute_queries_used
        
        if self.minute_query_timestamps:
            oldest_minute = self.minute_query_timestamps[0]
            minute_reset_time = datetime.fromtimestamp(oldest_minute + self.minute_limit_window_seconds)
        else:
            minute_reset_time = datetime.now()
        
        return {
            'daily_queries_used': daily_queries_used,
            'daily_queries_remaining': daily_queries_remaining,
            'daily_queries_limit': self.daily_limit_queries,
            'daily_reset_time': daily_reset_time.isoformat(),
            'minute_queries_used': minute_queries_used,
            'minute_queries_remaining': minute_queries_remaining,
            'minute_queries_limit': self.minute_limit_queries,
            'minute_reset_time': minute_reset_time.isoformat(),
            'authenticated': bool(self.api_key)
        }


# Example usage
if __name__ == "__main__":
    import logging
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize client with optional API key from environment
    client = AdjNewsClient()
    
    print("Adjacent News API Client Test")
    print("=" * 60)
    
    # Test connection
    print("\n1. Testing connection...")
    if client.test_connection():
        print("✅ Connection successful")
    else:
        print("❌ Connection failed")
    
    # Check rate limit status
    print("\n2. Rate limit status:")
    status = client.get_rate_limit_status()
    print(json.dumps(status, indent=2))
    
    # Search for markets
    print("\n3. Searching for markets with query 'trump 2024'...")
    markets = client.search_markets("trump 2024", limit=5)
    print(f"Found {len(markets)} markets")
    if markets:
        print(f"First market: {markets[0].get('title', markets[0].get('name', 'N/A'))[:50]}...")
    
    # Get trades for a sample market (if we have one)
    if markets:
        market_id = markets[0].get('id') or markets[0].get('market_id')
        if market_id:
            print(f"\n4. Getting trades for market_id: {market_id[:30]}...")
            trades = client.get_market_trades(str(market_id), limit=5)
            print(f"Found {len(trades)} trades")
    
    # Get news for a sample market
    print("\n5. Getting news for market 'trump'...")
    news = client.get_market_news("trump", days=7, limit=5)
    print(f"Found {len(news)} news articles")
    if news:
        print(f"First article: {news[0].get('title', news[0].get('headline', 'N/A'))[:50]}...")
    
    # Display cache statistics
    print("\n6. Cache statistics:")
    cache_stats = client.get_cache_stats()
    print(json.dumps(cache_stats, indent=2))
    
    print("\n✅ All tests completed!")

