#!/usr/bin/env python3
"""
HashDive API Client
A clean client for accessing HashDive API endpoints
"""

import requests
import json
from typing import Optional, Dict, Any


class HashDiveClient:
    """Client for HashDive API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://hashdive.com/api"
        self.headers = {
            "x-api-key": api_key
        }
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[Any, Any]:
        """
        Make a request to the HashDive API
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            JSON response from API
        """
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()  # Raise exception for bad status codes
            return response.json()
        except requests.exceptions.HTTPError as e:
            raise Exception(f"API Error {response.status_code}: {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Request failed: {e}")
    
    def get_api_usage(self) -> Dict[str, Any]:
        """Get API usage statistics"""
        return self._make_request("get_api_usage")
    
    def get_trades(
        self, 
        user_address: str,
        asset_id: Optional[str] = None,
        timestamp_gte: Optional[str] = None,
        timestamp_lte: Optional[str] = None,
        format: str = "json",
        page: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        Get trades for a given user
        
        Args:
            user_address: Wallet address (required)
            asset_id: Filter by market token ID
            timestamp_gte: Start time (ISO format)
            timestamp_lte: End time (ISO format)
            format: Output format (json or csv)
            page: Page number
            page_size: Results per page (max 1000)
        """
        params = {
            "user_address": user_address,
            "format": format,
            "page": page,
            "page_size": page_size
        }
        
        if asset_id:
            params["asset_id"] = asset_id
        if timestamp_gte:
            params["timestamp_gte"] = timestamp_gte
        if timestamp_lte:
            params["timestamp_lte"] = timestamp_lte
            
        return self._make_request("get_trades", params)
    
    def get_positions(
        self,
        user_address: str,
        asset_id: Optional[str] = None,
        format: str = "json",
        page: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        Get current positions for a given user
        
        Args:
            user_address: Wallet address (required)
            asset_id: Filter by token ID
            format: Output format (json or csv)
            page: Page number
            page_size: Results per page (max 1000)
        """
        params = {
            "user_address": user_address,
            "format": format,
            "page": page,
            "page_size": page_size
        }
        
        if asset_id:
            params["asset_id"] = asset_id
            
        return self._make_request("get_positions", params)
    
    def get_last_price(self, asset_id: str) -> Dict[str, Any]:
        """
        Get last price for a given asset
        
        Args:
            asset_id: Token ID (required)
        """
        params = {"asset_id": asset_id}
        return self._make_request("get_last_price", params)
    
    def get_ohlcv(
        self,
        asset_id: str,
        resolution: str,
        timestamp_gte: Optional[str] = None,
        timestamp_lte: Optional[str] = None,
        format: str = "json",
        page: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        Get OHLCV data for a token
        
        Args:
            asset_id: Token ID (required)
            resolution: Time resolution (1m, 5m, 15m, 1h, 4h, 1d)
            timestamp_gte: Start time (ISO format)
            timestamp_lte: End time (ISO format)
            format: Output format (json or csv)
            page: Page number
            page_size: Results per page (max 1000)
        """
        params = {
            "asset_id": asset_id,
            "resolution": resolution,
            "format": format,
            "page": page,
            "page_size": page_size
        }
        
        if timestamp_gte:
            params["timestamp_gte"] = timestamp_gte
        if timestamp_lte:
            params["timestamp_lte"] = timestamp_lte
            
        return self._make_request("get_ohlcv", params)
    
    def search_markets(
        self,
        query: str,
        format: str = "json",
        page: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        Search markets by question name
        
        Args:
            query: Free-text search string (required)
            format: Output format (json or csv)
            page: Page number
            page_size: Results per page (max 1000)
        """
        params = {
            "query": query,
            "format": format,
            "page": page,
            "page_size": page_size
        }
        return self._make_request("search_markets", params)
    
    def get_latest_whale_trades(
        self,
        min_usd: int = 10000,
        limit: int = 100,
        format: str = "json"
    ) -> Dict[str, Any]:
        """
        Get latest whale trades (large volume trades)
        
        Args:
            min_usd: Minimum USD value for trade (default: 10000)
            limit: Maximum number of trades to return (default: 100, max: 1000)
            format: Output format (json or csv)
        """
        params = {
            "min_usd": min_usd,
            "limit": limit,
            "format": format
        }
        return self._make_request("get_latest_whale_trades", params)


# Example usage
if __name__ == "__main__":
    # Initialize client with API key
    API_KEY = "2fcbbb010f3ff15f84dc47ebb0d92917d6fee90771407f56174423b9b28e5c3c"
    client = HashDiveClient(API_KEY)
    
    print("HashDive API Client Test")
    print("=" * 60)
    
    try:
        # Test 1: Check API usage
        print("\n1. Checking API usage...")
        usage = client.get_api_usage()
        print(json.dumps(usage, indent=2))
        
        # Test 2: Search for markets
        print("\n2. Searching for 'election' markets...")
        markets = client.search_markets("election", page_size=3)
        print(f"Found {len(markets.get('results', []))} markets")
        
        # Test 3: Get whale trades
        print("\n3. Getting latest whale trades...")
        whale_trades = client.get_latest_whale_trades(limit=5)
        print(f"Found {len(whale_trades.get('results', []))} whale trades")
        
        print("\n✅ All tests passed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nNote: If you see 502 errors, the HashDive API server")
        print("may be temporarily unavailable. Try again later.")

