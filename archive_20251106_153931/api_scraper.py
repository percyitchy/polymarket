#!/usr/bin/env python3
"""
Official Polymarket API scraper
Use official APIs instead of HTML scraping to get maximum wallets
"""

import asyncio
import aiohttp
import logging
import time
from typing import Dict, Set, List
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PolymarketAPIScraper:
    def __init__(self):
        self.all_wallets: Set[str] = set()
        self.session = None
        
        # API endpoints
        self.data_api_base = "https://data-api.polymarket.com"
        self.clob_api_base = "https://clob.polymarket.com"
        
        # Rate limiting
        self.data_api_rate_limit = 200  # requests per 10s
        self.clob_api_rate_limit = 5000  # requests per 10s
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def scrape_all_wallets(self) -> List[str]:
        """Scrape wallets from all available API endpoints"""
        logger.info("Starting Polymarket API wallet scraping...")
        
        # Strategy 1: Explore Data API endpoints
        await self._explore_data_api()
        
        # Strategy 2: Get active traders from CLOB
        await self._get_clob_traders()
        
        # Strategy 3: Get recent trades data
        await self._get_recent_trades()
        
        # Strategy 4: Try different API patterns
        await self._try_api_patterns()
        
        wallets_list = list(self.all_wallets)
        logger.info(f"🎉 FINAL RESULT: {len(wallets_list)} unique wallets found via API!")
        
        return wallets_list
    
    async def _explore_data_api(self):
        """Explore Data API endpoints to find trader data"""
        logger.info("Strategy 1: Exploring Data API endpoints...")
        
        # Common API endpoints to try
        endpoints_to_try = [
            "/users",
            "/traders", 
            "/leaderboard",
            "/leaderboards",
            "/profiles",
            "/accounts",
            "/wallets",
            "/addresses",
            "/stats",
            "/metrics",
            "/top-traders",
            "/best-traders",
            "/active-traders",
            "/recent-traders",
            "/volume-leaders",
            "/profit-leaders",
            "/trade-leaders",
            "/pnl-leaders",
            "/performance",
            "/rankings",
            "/scores",
            "/analytics",
            "/data",
            "/core",
            "/misc"
        ]
        
        for endpoint in endpoints_to_try:
            try:
                url = f"{self.data_api_base}{endpoint}"
                logger.info(f"Trying Data API: {url}")
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        wallets = self._extract_wallets_from_json(data)
                        if wallets:
                            logger.info(f"  Found {len(wallets)} wallets in {endpoint}")
                            self.all_wallets.update(wallets)
                    elif response.status == 404:
                        logger.debug(f"  Endpoint not found: {endpoint}")
                    else:
                        logger.debug(f"  Status {response.status} for {endpoint}")
                        
            except Exception as e:
                logger.debug(f"  Error with {endpoint}: {e}")
            
            # Rate limiting
            await asyncio.sleep(0.1)
    
    async def _get_clob_traders(self):
        """Get trader data from CLOB API"""
        logger.info("Strategy 2: Getting CLOB trader data...")
        
        # CLOB endpoints to try
        clob_endpoints = [
            "/trades",
            "/orders", 
            "/notifications",
            "/markets",
            "/book",
            "/price",
            "/midprice",
            "/spreads",
            "/ledger",
            "/data/orders",
            "/data/trades",
            "/users",
            "/accounts",
            "/profiles"
        ]
        
        for endpoint in clob_endpoints:
            try:
                url = f"{self.clob_api_base}{endpoint}"
                logger.info(f"Trying CLOB API: {url}")
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        wallets = self._extract_wallets_from_json(data)
                        if wallets:
                            logger.info(f"  Found {len(wallets)} wallets in CLOB {endpoint}")
                            self.all_wallets.update(wallets)
                    elif response.status == 404:
                        logger.debug(f"  CLOB endpoint not found: {endpoint}")
                    else:
                        logger.debug(f"  CLOB status {response.status} for {endpoint}")
                        
            except Exception as e:
                logger.debug(f"  Error with CLOB {endpoint}: {e}")
            
            # Rate limiting
            await asyncio.sleep(0.1)
    
    async def _get_recent_trades(self):
        """Get recent trades to extract trader addresses"""
        logger.info("Strategy 3: Getting recent trades data...")
        
        # Try different trade endpoints
        trade_endpoints = [
            f"{self.data_api_base}/trades",
            f"{self.clob_api_base}/trades",
            f"{self.data_api_base}/trades?limit=1000",
            f"{self.clob_api_base}/trades?limit=1000",
            f"{self.data_api_base}/trades?limit=5000",
            f"{self.clob_api_base}/trades?limit=5000",
        ]
        
        for url in trade_endpoints:
            try:
                logger.info(f"Trying trades: {url}")
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        wallets = self._extract_wallets_from_json(data)
                        if wallets:
                            logger.info(f"  Found {len(wallets)} wallets in trades")
                            self.all_wallets.update(wallets)
                    else:
                        logger.debug(f"  Trades status {response.status}")
                        
            except Exception as e:
                logger.debug(f"  Error with trades {url}: {e}")
            
            # Rate limiting
            await asyncio.sleep(0.2)
    
    async def _try_api_patterns(self):
        """Try different API patterns and parameters"""
        logger.info("Strategy 4: Trying API patterns...")
        
        # Try different parameter combinations
        patterns = [
            # Data API patterns
            f"{self.data_api_base}/trades?sort=volume&limit=1000",
            f"{self.data_api_base}/trades?sort=profit&limit=1000", 
            f"{self.data_api_base}/trades?sort=trades&limit=1000",
            f"{self.data_api_base}/trades?timeframe=week&limit=1000",
            f"{self.data_api_base}/trades?timeframe=month&limit=1000",
            f"{self.data_api_base}/trades?timeframe=all&limit=1000",
            
            # CLOB patterns
            f"{self.clob_api_base}/trades?sort=volume&limit=1000",
            f"{self.clob_api_base}/trades?sort=profit&limit=1000",
            f"{self.clob_api_base}/trades?sort=trades&limit=1000",
            
            # Market-specific patterns
            f"{self.data_api_base}/markets?limit=1000",
            f"{self.clob_api_base}/markets?limit=1000",
        ]
        
        for url in patterns:
            try:
                logger.info(f"Trying pattern: {url}")
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        wallets = self._extract_wallets_from_json(data)
                        if wallets:
                            logger.info(f"  Found {len(wallets)} wallets in pattern")
                            self.all_wallets.update(wallets)
                    else:
                        logger.debug(f"  Pattern status {response.status}")
                        
            except Exception as e:
                logger.debug(f"  Error with pattern {url}: {e}")
            
            # Rate limiting
            await asyncio.sleep(0.2)
    
    def _extract_wallets_from_json(self, data) -> Set[str]:
        """Extract wallet addresses from JSON response"""
        wallets = set()
        
        try:
            # Convert to string and search for Ethereum addresses
            json_str = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
            
            import re
            # Find all Ethereum addresses
            wallet_pattern = r'0x[a-fA-F0-9]{40}'
            matches = re.findall(wallet_pattern, json_str)
            
            for match in matches:
                if self._is_valid_address(match):
                    wallets.add(match.lower())
                    
        except Exception as e:
            logger.debug(f"Error extracting wallets from JSON: {e}")
            
        return wallets
    
    def _is_valid_address(self, address: str) -> bool:
        """Check if string is a valid Ethereum address"""
        if not address.startswith('0x'):
            return False
        if len(address) != 42:
            return False
        try:
            int(address[2:], 16)
            return True
        except ValueError:
            return False

async def main():
    """Main function to run API scraping"""
    logger.info("Starting Polymarket API wallet scraping...")
    
    async with PolymarketAPIScraper() as scraper:
        wallets = await scraper.scrape_all_wallets()
    
    logger.info(f"🎉 FINAL RESULT: {len(wallets)} unique wallets found!")
    
    if len(wallets) >= 120:
        logger.info("✅ SUCCESS: Found 120+ wallets as requested!")
    else:
        logger.info(f"⚠️  Found {len(wallets)} wallets (target was 120+)")
    
    # Show sample
    logger.info("Sample wallets:")
    for i, wallet in enumerate(list(wallets)[:20]):
        logger.info(f"  {i+1}. {wallet}")
    
    if len(wallets) > 20:
        logger.info(f"  ... and {len(wallets) - 20} more")
    
    return wallets

if __name__ == "__main__":
    wallets = asyncio.run(main())
