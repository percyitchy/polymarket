#!/usr/bin/env python3
"""
ClickHouse Client for Polymarket Data
A clean client for accessing ClickHouse database at crypto.clickhouse.com
"""

import requests
import logging
import time
from typing import Optional, Dict, Any, List
from collections import deque
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ClickHouseError(Exception):
    """Base exception for ClickHouse client errors"""
    pass


class RateLimitExceeded(ClickHouseError):
    """Raised when rate limit is exceeded"""
    def __init__(self, wait_time: float):
        self.wait_time = wait_time
        super().__init__(f"Rate limit exceeded. Wait {wait_time:.1f} seconds")


class ClickHouseClient:
    """Client for ClickHouse database at crypto.clickhouse.com"""
    
    def __init__(self, base_url: str = "https://crypto.clickhouse.com/", database: str = "polymarket", timeout: int = 10):
        """
        Initialize ClickHouse client
        
        Args:
            base_url: Base URL for ClickHouse HTTP interface
            database: Database name (default: polymarket)
            timeout: Request timeout in seconds (default: 10)
        """
        self.base_url = base_url.rstrip('/')
        self.database = database
        self.timeout = timeout
        
        # Rate limiting: 60 queries per hour (1 query per minute)
        self.rate_limit_queries_per_hour = 60
        self.rate_limit_window_seconds = 3600  # 1 hour
        self.query_timestamps = deque(maxlen=self.rate_limit_queries_per_hour)
        
        logger.debug(f"[ClickHouse] Initialized client: base_url={self.base_url}, database={self.database}, timeout={self.timeout}s")
    
    def _check_rate_limit(self) -> None:
        """
        Check if rate limit is exceeded
        
        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        now = time.time()
        
        # Remove timestamps older than 1 hour
        while self.query_timestamps and (now - self.query_timestamps[0]) > self.rate_limit_window_seconds:
            self.query_timestamps.popleft()
        
        # Check if we've exceeded the limit
        if len(self.query_timestamps) >= self.rate_limit_queries_per_hour:
            oldest_timestamp = self.query_timestamps[0]
            wait_time = self.rate_limit_window_seconds - (now - oldest_timestamp)
            if wait_time > 0:
                logger.warning(f"[ClickHouse] Rate limit exceeded: {len(self.query_timestamps)}/{self.rate_limit_queries_per_hour} queries in last hour. Wait {wait_time:.1f}s")
                raise RateLimitExceeded(wait_time)
        
        # Record this query
        self.query_timestamps.append(now)
    
    def _sanitize_input(self, value: str) -> str:
        """
        Sanitize input to prevent SQL injection
        
        Args:
            value: Input string to sanitize
            
        Returns:
            Sanitized string with single quotes escaped
        """
        if not isinstance(value, str):
            raise ValueError(f"Expected string, got {type(value)}")
        # Escape single quotes
        return value.replace("'", "''")
    
    def _validate_token_id(self, token_id: str) -> None:
        """
        Validate token_id format (hex string with optional :outcome_index)
        
        Args:
            token_id: Token ID to validate
            
        Raises:
            ValueError: If token_id format is invalid
        """
        if not token_id or not isinstance(token_id, str):
            raise ValueError("token_id must be a non-empty string")
        
        # Token ID format: hex_string or hex_string:number
        parts = token_id.split(':')
        if len(parts) > 2:
            raise ValueError(f"Invalid token_id format: {token_id}")
        
        # Validate hex part
        hex_part = parts[0]
        if not hex_part.startswith('0x') or len(hex_part) < 3:
            raise ValueError(f"Invalid token_id hex format: {hex_part}")
    
    def _validate_condition_id(self, condition_id: str) -> None:
        """
        Validate condition_id format (hex string)
        
        Args:
            condition_id: Condition ID to validate
            
        Raises:
            ValueError: If condition_id format is invalid
        """
        if not condition_id or not isinstance(condition_id, str):
            raise ValueError("condition_id must be a non-empty string")
        
        if not condition_id.startswith('0x') or len(condition_id) < 3:
            raise ValueError(f"Invalid condition_id format: {condition_id}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.exceptions.Timeout, requests.exceptions.ConnectionError))
    )
    def _make_request(self, query: str, format: str = 'JSONEachRow', method: str = 'POST') -> Dict[str, Any]:
        """
        Execute SQL query via HTTP interface
        
        Args:
            query: SQL query string
            format: Response format (JSONEachRow, JSON, TabSeparated)
            method: HTTP method (GET or POST)
            
        Returns:
            Parsed response data
            
        Raises:
            ClickHouseError: On query execution error
            RateLimitExceeded: If rate limit is exceeded
        """
        # Check rate limit before making request
        self._check_rate_limit()
        
        start_time = time.time()
        
        try:
            # Build URL with database parameter
            url = f"{self.base_url}/?database={self.database}"
            
            # Prepare request based on method
            if method.upper() == 'GET':
                params = {'query': query}
                response = requests.get(url, params=params, timeout=self.timeout)
            else:  # POST
                headers = {'Content-Type': 'text/plain'}
                response = requests.post(url, data=query, headers=headers, timeout=self.timeout)
            
            elapsed = time.time() - start_time
            
            # Log query execution
            logger.debug(f"[ClickHouse] Query executed in {elapsed:.2f}s: {query[:100]}...")
            
            # Check response status
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(f"[ClickHouse] Query failed: {error_msg}")
                raise ClickHouseError(error_msg)
            
            # Parse response based on format
            response_text = response.text.strip()
            
            if not response_text:
                logger.debug(f"[ClickHouse] Empty response for query: {query[:100]}...")
                return {'data': []}
            
            if format == 'JSONEachRow':
                # JSONEachRow: One JSON object per line
                lines = [line.strip() for line in response_text.split('\n') if line.strip()]
                data = []
                for line in lines:
                    try:
                        import json
                        data.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.warning(f"[ClickHouse] Failed to parse JSON line: {line[:100]}..., error: {e}")
                        continue
                return {'data': data}
            
            elif format == 'JSON':
                # JSON: Single JSON object with data array
                import json
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError as e:
                    logger.warning(f"[ClickHouse] Failed to parse JSON response: {e}")
                    raise ClickHouseError(f"Invalid JSON response: {e}")
            
            elif format == 'TabSeparated':
                # TabSeparated: Tab-separated values (fallback)
                lines = [line.split('\t') for line in response_text.split('\n') if line.strip()]
                return {'data': lines}
            
            else:
                # Default: return as text
                return {'data': response_text}
                
        except requests.exceptions.Timeout:
            elapsed = time.time() - start_time
            logger.warning(f"[ClickHouse] Query timeout after {elapsed:.2f}s: {query[:100]}...")
            raise ClickHouseError(f"Query timeout after {self.timeout}s")
        
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"[ClickHouse] Connection error: {e}")
            raise ClickHouseError(f"Connection error: {e}")
        
        except requests.exceptions.RequestException as e:
            logger.warning(f"[ClickHouse] Request error: {type(e).__name__}: {e}")
            raise ClickHouseError(f"Request error: {e}")
        
        except Exception as e:
            logger.error(f"[ClickHouse] Unexpected error: {type(e).__name__}: {e}")
            raise ClickHouseError(f"Unexpected error: {e}")
    
    def test_connection(self) -> bool:
        """
        Test connection to ClickHouse database
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Use a simple query that doesn't count against rate limit
            # We'll use a separate tracking for connection tests
            query = "SELECT 1 FORMAT JSONEachRow"
            result = self._make_request(query)
            
            if result.get('data') and len(result['data']) > 0:
                logger.info("[ClickHouse] ✅ Connection test successful")
                return True
            else:
                logger.warning("[ClickHouse] ❌ Connection test returned empty result")
                return False
                
        except Exception as e:
            logger.warning(f"[ClickHouse] ❌ Connection test failed: {type(e).__name__}: {e}")
            return False
    
    def get_latest_price(self, token_id: str) -> Optional[float]:
        """
        Get latest price for a token from orders_filled table
        
        Args:
            token_id: Token ID in format 'condition_id:outcome_index' or hex string
            
        Returns:
            Latest price or None if no data found
        """
        try:
            # Validate and sanitize token_id
            self._validate_token_id(token_id)
            sanitized_token_id = self._sanitize_input(token_id)
            
            # Build SQL query
            query = f"""
            SELECT price, timestamp
            FROM orders_filled
            WHERE token_id = '{sanitized_token_id}'
            ORDER BY timestamp DESC
            LIMIT 1
            FORMAT JSONEachRow
            """
            
            logger.debug(f"[ClickHouse] Getting latest price for token_id={token_id[:30]}...")
            
            result = self._make_request(query)
            data = result.get('data', [])
            
            if data and len(data) > 0:
                price = data[0].get('price')
                timestamp = data[0].get('timestamp')
                
                if price is not None:
                    try:
                        price_float = float(price)
                        logger.info(f"[ClickHouse] ✅ Got latest price: {price_float:.6f} (timestamp: {timestamp})")
                        return price_float
                    except (ValueError, TypeError) as e:
                        logger.warning(f"[ClickHouse] Failed to parse price: {price}, error: {e}")
                        return None
                else:
                    logger.debug(f"[ClickHouse] No price field in response: {data[0]}")
                    return None
            else:
                logger.debug(f"[ClickHouse] No data found for token_id={token_id[:30]}...")
                return None
                
        except RateLimitExceeded as e:
            logger.warning(f"[ClickHouse] Rate limit exceeded: {e}")
            return None
        
        except ClickHouseError as e:
            logger.warning(f"[ClickHouse] Error getting latest price: {e}")
            return None
        
        except Exception as e:
            logger.warning(f"[ClickHouse] Unexpected error getting latest price: {type(e).__name__}: {e}")
            return None
    
    def get_market_open_interest(self, condition_id: str) -> Optional[Dict[str, Any]]:
        """
        Get market open interest for a condition
        
        Args:
            condition_id: Condition ID (hex string)
            
        Returns:
            Dict with open interest data or None if no data found
        """
        try:
            # Validate and sanitize condition_id
            self._validate_condition_id(condition_id)
            sanitized_condition_id = self._sanitize_input(condition_id)
            
            # Build SQL query
            query = f"""
            SELECT *
            FROM market_open_interest
            WHERE condition_id = '{sanitized_condition_id}'
            ORDER BY timestamp DESC
            LIMIT 1
            FORMAT JSONEachRow
            """
            
            logger.debug(f"[ClickHouse] Getting open interest for condition_id={condition_id[:30]}...")
            
            result = self._make_request(query)
            data = result.get('data', [])
            
            if data and len(data) > 0:
                logger.info(f"[ClickHouse] ✅ Got open interest data for condition_id={condition_id[:30]}...")
                return data[0]
            else:
                logger.debug(f"[ClickHouse] No open interest data found for condition_id={condition_id[:30]}...")
                return None
                
        except RateLimitExceeded as e:
            logger.warning(f"[ClickHouse] Rate limit exceeded: {e}")
            return None
        
        except ClickHouseError as e:
            logger.warning(f"[ClickHouse] Error getting open interest: {e}")
            return None
        
        except Exception as e:
            logger.warning(f"[ClickHouse] Unexpected error getting open interest: {type(e).__name__}: {e}")
            return None
    
    def get_user_positions(self, user_address: str, condition_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get user positions from user_positions table
        
        Args:
            user_address: User wallet address (hex string)
            condition_id: Optional condition ID filter
            
        Returns:
            List of position dictionaries or empty list if no positions found
        """
        try:
            # Validate and sanitize inputs
            if not user_address or not isinstance(user_address, str):
                raise ValueError("user_address must be a non-empty string")
            
            sanitized_address = self._sanitize_input(user_address)
            
            # Build SQL query
            query = f"""
            SELECT *
            FROM user_positions
            WHERE user_address = '{sanitized_address}'
            """
            
            if condition_id:
                self._validate_condition_id(condition_id)
                sanitized_condition_id = self._sanitize_input(condition_id)
                query += f" AND condition_id = '{sanitized_condition_id}'"
            
            query += " FORMAT JSONEachRow"
            
            logger.debug(f"[ClickHouse] Getting positions for user_address={user_address[:20]}...")
            
            result = self._make_request(query)
            data = result.get('data', [])
            
            if data:
                logger.info(f"[ClickHouse] ✅ Got {len(data)} positions for user_address={user_address[:20]}...")
                return data
            else:
                logger.debug(f"[ClickHouse] No positions found for user_address={user_address[:20]}...")
                return []
                
        except RateLimitExceeded as e:
            logger.warning(f"[ClickHouse] Rate limit exceeded: {e}")
            return []
        
        except ClickHouseError as e:
            logger.warning(f"[ClickHouse] Error getting user positions: {e}")
            return []
        
        except Exception as e:
            logger.warning(f"[ClickHouse] Unexpected error getting user positions: {type(e).__name__}: {e}")
            return []
    
    def get_user_balances(self, user_address: str) -> Optional[Dict[str, Any]]:
        """
        Get user balances from user_balances table
        
        Args:
            user_address: User wallet address (hex string)
            
        Returns:
            Dict with balance data or None if no data found
        """
        try:
            # Validate and sanitize inputs
            if not user_address or not isinstance(user_address, str):
                raise ValueError("user_address must be a non-empty string")
            
            sanitized_address = self._sanitize_input(user_address)
            
            # Build SQL query
            query = f"""
            SELECT *
            FROM user_balances
            WHERE user_address = '{sanitized_address}'
            LIMIT 1
            FORMAT JSONEachRow
            """
            
            logger.debug(f"[ClickHouse] Getting balances for user_address={user_address[:20]}...")
            
            result = self._make_request(query)
            data = result.get('data', [])
            
            if data and len(data) > 0:
                logger.info(f"[ClickHouse] ✅ Got balance data for user_address={user_address[:20]}...")
                return data[0]
            else:
                logger.debug(f"[ClickHouse] No balance data found for user_address={user_address[:20]}...")
                return None
                
        except RateLimitExceeded as e:
            logger.warning(f"[ClickHouse] Rate limit exceeded: {e}")
            return None
        
        except ClickHouseError as e:
            logger.warning(f"[ClickHouse] Error getting user balances: {e}")
            return None
        
        except Exception as e:
            logger.warning(f"[ClickHouse] Unexpected error getting user balances: {type(e).__name__}: {e}")
            return None
    
    def get_recent_trades(self, token_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent trades for a token from orders_filled table
        
        Args:
            token_id: Token ID in format 'condition_id:outcome_index' or hex string
            limit: Maximum number of trades to return (default: 10)
            
        Returns:
            List of trade dictionaries or empty list if no trades found
        """
        try:
            # Validate and sanitize inputs
            self._validate_token_id(token_id)
            sanitized_token_id = self._sanitize_input(token_id)
            
            if not isinstance(limit, int) or limit < 1:
                limit = 10
            
            # Build SQL query
            query = f"""
            SELECT *
            FROM orders_filled
            WHERE token_id = '{sanitized_token_id}'
            ORDER BY timestamp DESC
            LIMIT {limit}
            FORMAT JSONEachRow
            """
            
            logger.debug(f"[ClickHouse] Getting recent trades for token_id={token_id[:30]}..., limit={limit}")
            
            result = self._make_request(query)
            data = result.get('data', [])
            
            if data:
                logger.info(f"[ClickHouse] ✅ Got {len(data)} recent trades for token_id={token_id[:30]}...")
                return data
            else:
                logger.debug(f"[ClickHouse] No trades found for token_id={token_id[:30]}...")
                return []
                
        except RateLimitExceeded as e:
            logger.warning(f"[ClickHouse] Rate limit exceeded: {e}")
            return []
        
        except ClickHouseError as e:
            logger.warning(f"[ClickHouse] Error getting recent trades: {e}")
            return []
        
        except Exception as e:
            logger.warning(f"[ClickHouse] Unexpected error getting recent trades: {type(e).__name__}: {e}")
            return []
    
    def get_orders_matched(self, condition_id: str, outcome_index: Optional[int] = None, minutes_back: int = 15) -> List[Dict[str, Any]]:
        """
        Get recent matched orders from orders_matched table for order flow analysis
        
        Args:
            condition_id: Condition ID (hex string)
            outcome_index: Optional outcome index to filter by
            minutes_back: Time window in minutes to look back (default: 15)
            
        Returns:
            List of order dictionaries with fields: timestamp, side, size, price, maker_address, taker_address
        """
        try:
            # Validate and sanitize condition_id
            self._validate_condition_id(condition_id)
            sanitized_condition_id = self._sanitize_input(condition_id)
            
            # Build SQL query
            query = f"""
            SELECT timestamp, side, size, price, maker_address, taker_address
            FROM orders_matched
            WHERE condition_id = '{sanitized_condition_id}'
            """
            
            # Add outcome_index filter if provided
            if outcome_index is not None:
                query += f" AND outcome_index = {outcome_index}"
            
            # Add time window filter
            query += f" AND timestamp >= now() - INTERVAL {minutes_back} MINUTE"
            query += " ORDER BY timestamp DESC FORMAT JSONEachRow"
            
            logger.debug(f"[ClickHouse] Getting orders_matched for condition_id={condition_id[:30]}..., outcome_index={outcome_index}, minutes_back={minutes_back}")
            
            result = self._make_request(query)
            data = result.get('data', [])
            
            if data:
                logger.info(f"[ClickHouse] ✅ Got {len(data)} matched orders for condition_id={condition_id[:30]}...")
                return data
            else:
                logger.debug(f"[ClickHouse] No matched orders found for condition_id={condition_id[:30]}...")
                return []
                
        except RateLimitExceeded as e:
            logger.warning(f"[ClickHouse] Rate limit exceeded: {e}")
            return []
        
        except ClickHouseError as e:
            logger.warning(f"[ClickHouse] Error getting orders_matched: {e}")
            return []
        
        except Exception as e:
            logger.warning(f"[ClickHouse] Unexpected error getting orders_matched: {type(e).__name__}: {e}")
            return []
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Get current rate limit status
        
        Returns:
            Dict with rate limit information
        """
        now = time.time()
        
        # Remove old timestamps
        while self.query_timestamps and (now - self.query_timestamps[0]) > self.rate_limit_window_seconds:
            self.query_timestamps.popleft()
        
        queries_used = len(self.query_timestamps)
        queries_remaining = self.rate_limit_queries_per_hour - queries_used
        
        # Calculate reset time
        if self.query_timestamps:
            oldest_timestamp = self.query_timestamps[0]
            reset_time = datetime.fromtimestamp(oldest_timestamp + self.rate_limit_window_seconds)
        else:
            reset_time = datetime.now()
        
        return {
            'queries_used': queries_used,
            'queries_remaining': queries_remaining,
            'queries_per_hour': self.rate_limit_queries_per_hour,
            'reset_time': reset_time.isoformat(),
            'reset_timestamp': reset_time.timestamp()
        }


# Example usage
if __name__ == "__main__":
    client = ClickHouseClient()
    
    # Test connection
    if client.test_connection():
        print("✅ Connected to ClickHouse")
    
    # Test rate limit status
    status = client.get_rate_limit_status()
    print(f"Rate limit: {status}")
    
    # Test get latest price
    token_id = "example_token_id"
    price = client.get_latest_price(token_id)
    print(f"Latest price: {price}")
    
    # Test get open interest
    condition_id = "example_condition_id"
    oi = client.get_market_open_interest(condition_id)
    print(f"Open interest: {oi}")

