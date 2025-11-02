#!/usr/bin/env python3
"""
Specialized scraper for top 200 wallets by winrate
Criteria: 65-90% winrate, max 1000 trades, max 10 trades/day
Sources: monthly/weekly/today leaderboards
"""

import asyncio
import aiohttp
import logging
import time
from typing import Dict, Set, List, Tuple
import json
import re
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class WalletMetrics:
    address: str
    winrate: float
    total_trades: int
    daily_trades: float
    profit: float
    volume: float
    source: str

class TopWinrateScraper:
    def __init__(self):
        self.wallet_metrics: Dict[str, WalletMetrics] = {}
        self.session = None
        
        # API endpoints
        self.data_api_base = "https://data-api.polymarket.com"
        
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
    
    async def find_top_winrate_wallets(self) -> List[WalletMetrics]:
        """Find top 200 wallets by winrate with specified criteria"""
        logger.info("Starting top winrate wallet search...")
        
        # Strategy 1: Get leaderboard data from different timeframes
        await self._scrape_leaderboards()
        
        # Strategy 2: Get detailed metrics for each wallet
        await self._analyze_wallet_metrics()
        
        # Strategy 3: Filter by criteria and rank by winrate
        filtered_wallets = self._filter_and_rank_wallets()
        
        logger.info(f"🎉 Found {len(filtered_wallets)} wallets meeting criteria!")
        
        return filtered_wallets
    
    async def _scrape_leaderboards(self):
        """Scrape leaderboards from different timeframes"""
        logger.info("Strategy 1: Scraping leaderboards...")
        
        # Different leaderboard endpoints to try
        leaderboard_endpoints = [
            "/leaderboard",
            "/leaderboards",
            "/leaderboard?timeframe=today",
            "/leaderboard?timeframe=week", 
            "/leaderboard?timeframe=month",
            "/leaderboard?sort=winrate",
            "/leaderboard?sort=profit",
            "/leaderboard?sort=volume",
            "/leaderboard?sort=trades",
            "/leaderboard?limit=1000",
            "/leaderboard?limit=2000",
            "/leaderboard?limit=5000",
        ]
        
        for endpoint in leaderboard_endpoints:
            try:
                url = f"{self.data_api_base}{endpoint}"
                logger.info(f"Trying leaderboard: {url}")
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        wallets = self._extract_wallets_from_leaderboard(data, endpoint)
                        if wallets:
                            logger.info(f"  Found {len(wallets)} wallets in {endpoint}")
                            self.wallet_metrics.update(wallets)
                    else:
                        logger.debug(f"  Status {response.status} for {endpoint}")
                        
            except Exception as e:
                logger.debug(f"  Error with {endpoint}: {e}")
            
            # Rate limiting
            await asyncio.sleep(0.1)
    
    async def _analyze_wallet_metrics(self):
        """Get detailed metrics for each wallet"""
        logger.info("Strategy 2: Analyzing wallet metrics...")
        
        # Get detailed data for each wallet
        wallet_addresses = list(self.wallet_metrics.keys())
        
        # Process in batches to respect rate limits
        batch_size = 50
        for i in range(0, len(wallet_addresses), batch_size):
            batch = wallet_addresses[i:i + batch_size]
            await self._process_wallet_batch(batch)
            
            # Rate limiting between batches
            await asyncio.sleep(1)
    
    async def _process_wallet_batch(self, wallet_addresses: List[str]):
        """Process a batch of wallet addresses"""
        for address in wallet_addresses:
            try:
                # Try different API endpoints for wallet data
                endpoints = [
                    f"/user/{address}",
                    f"/profile/{address}",
                    f"/wallet/{address}",
                    f"/account/{address}",
                    f"/trades?user={address}",
                    f"/trades?wallet={address}",
                    f"/trades?address={address}",
                    f"/stats/{address}",
                    f"/metrics/{address}",
                    f"/performance/{address}",
                ]
                
                for endpoint in endpoints:
                    try:
                        url = f"{self.data_api_base}{endpoint}"
                        
                        async with self.session.get(url) as response:
                            if response.status == 200:
                                data = await response.json()
                                metrics = self._extract_metrics_from_data(data, address, endpoint)
                                if metrics:
                                    self.wallet_metrics[address] = metrics
                                    break
                                    
                    except Exception as e:
                        logger.debug(f"    Error with {endpoint} for {address}: {e}")
                    
                    # Small delay between requests
                    await asyncio.sleep(0.05)
                    
            except Exception as e:
                logger.debug(f"  Error processing {address}: {e}")
    
    def _extract_wallets_from_leaderboard(self, data, source: str) -> Dict[str, WalletMetrics]:
        """Extract wallet addresses from leaderboard data"""
        wallets = {}
        
        try:
            # Convert to string and search for wallet data
            json_str = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
            
            # Find wallet addresses
            wallet_pattern = r'0x[a-fA-F0-9]{40}'
            addresses = re.findall(wallet_pattern, json_str)
            
            for addr in addresses:
                if self._is_valid_address(addr):
                    addr_lower = addr.lower()
                    if addr_lower not in wallets:
                        wallets[addr_lower] = WalletMetrics(
                            address=addr_lower,
                            winrate=0.0,
                            total_trades=0,
                            daily_trades=0.0,
                            profit=0.0,
                            volume=0.0,
                            source=source
                        )
                        
        except Exception as e:
            logger.debug(f"Error extracting wallets from leaderboard: {e}")
            
        return wallets
    
    def _extract_metrics_from_data(self, data, address: str, source: str) -> WalletMetrics:
        """Extract detailed metrics from wallet data"""
        try:
            json_str = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
            
            # Extract metrics using regex patterns
            winrate = self._extract_float_pattern(json_str, r'"winrate":\s*([0-9.]+)')
            total_trades = self._extract_int_pattern(json_str, r'"total_trades":\s*([0-9]+)')
            daily_trades = self._extract_float_pattern(json_str, r'"daily_trades":\s*([0-9.]+)')
            profit = self._extract_float_pattern(json_str, r'"profit":\s*([0-9.-]+)')
            volume = self._extract_float_pattern(json_str, r'"volume":\s*([0-9.]+)')
            
            # Also try alternative field names
            if winrate == 0.0:
                winrate = self._extract_float_pattern(json_str, r'"win_rate":\s*([0-9.]+)')
            if total_trades == 0:
                total_trades = self._extract_int_pattern(json_str, r'"trades":\s*([0-9]+)')
            if daily_trades == 0.0:
                daily_trades = self._extract_float_pattern(json_str, r'"trades_per_day":\s*([0-9.]+)')
            
            return WalletMetrics(
                address=address,
                winrate=winrate,
                total_trades=total_trades,
                daily_trades=daily_trades,
                profit=profit,
                volume=volume,
                source=source
            )
            
        except Exception as e:
            logger.debug(f"Error extracting metrics for {address}: {e}")
            return None
    
    def _extract_float_pattern(self, text: str, pattern: str) -> float:
        """Extract float value using regex pattern"""
        try:
            match = re.search(pattern, text)
            if match:
                return float(match.group(1))
        except (ValueError, AttributeError):
            pass
        return 0.0
    
    def _extract_int_pattern(self, text: str, pattern: str) -> int:
        """Extract int value using regex pattern"""
        try:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))
        except (ValueError, AttributeError):
            pass
        return 0
    
    def _filter_and_rank_wallets(self) -> List[WalletMetrics]:
        """Filter wallets by criteria and rank by winrate"""
        logger.info("Strategy 3: Filtering and ranking wallets...")
        
        filtered_wallets = []
        
        for wallet in self.wallet_metrics.values():
            # Apply criteria
            if (65.0 <= wallet.winrate <= 90.0 and  # Winrate 65-90%
                wallet.total_trades <= 1000 and      # Max 1000 trades
                wallet.daily_trades <= 10.0):        # Max 10 trades/day
                
                filtered_wallets.append(wallet)
        
        # Sort by winrate (descending)
        filtered_wallets.sort(key=lambda x: x.winrate, reverse=True)
        
        # Take top 200
        top_200 = filtered_wallets[:200]
        
        logger.info(f"Filtered {len(filtered_wallets)} wallets, taking top {len(top_200)}")
        
        return top_200
    
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
    """Main function to find top winrate wallets"""
    logger.info("Starting top winrate wallet search...")
    
    async with TopWinrateScraper() as scraper:
        top_wallets = await scraper.find_top_winrate_wallets()
    
    logger.info(f"🎉 FINAL RESULT: {len(top_wallets)} top winrate wallets found!")
    
    if len(top_wallets) >= 200:
        logger.info("✅ SUCCESS: Found 200+ wallets as requested!")
    else:
        logger.info(f"⚠️  Found {len(top_wallets)} wallets (target was 200)")
    
    # Show top wallets
    logger.info("Top winrate wallets:")
    for i, wallet in enumerate(top_wallets[:20]):
        logger.info(f"  {i+1}. {wallet.address} - Winrate: {wallet.winrate:.2f}%, "
                   f"Trades: {wallet.total_trades}, Daily: {wallet.daily_trades:.2f}, "
                   f"Profit: {wallet.profit:.2f}")
    
    if len(top_wallets) > 20:
        logger.info(f"  ... and {len(top_wallets) - 20} more")
    
    return top_wallets

if __name__ == "__main__":
    wallets = asyncio.run(main())
