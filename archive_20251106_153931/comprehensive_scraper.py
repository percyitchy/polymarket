#!/usr/bin/env python3
"""
Comprehensive scraper to find ALL possible wallets from Polymarket
Try different leaderboards, timeframes, and sorting options
"""

import asyncio
import logging
from playwright.async_api import async_playwright
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ComprehensivePolymarketScraper:
    def __init__(self):
        self.all_wallets = {}
        
    async def scrape_all_possible_wallets(self):
        """Scrape wallets from all possible Polymarket leaderboards"""
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # Try different leaderboard combinations
            leaderboard_configs = [
                # Different timeframes
                {"timeframe": "today", "metric": "profit"},
                {"timeframe": "today", "metric": "volume"},
                {"timeframe": "today", "metric": "trades"},
                {"timeframe": "weekly", "metric": "profit"},
                {"timeframe": "weekly", "metric": "volume"},
                {"timeframe": "weekly", "metric": "trades"},
                {"timeframe": "monthly", "metric": "profit"},
                {"timeframe": "monthly", "metric": "volume"},
                {"timeframe": "monthly", "metric": "trades"},
                {"timeframe": "alltime", "metric": "profit"},
                {"timeframe": "alltime", "metric": "volume"},
                {"timeframe": "alltime", "metric": "trades"},
                
                # Different sorting options
                {"timeframe": "weekly", "metric": "profit", "sort": "profit"},
                {"timeframe": "weekly", "metric": "profit", "sort": "volume"},
                {"timeframe": "weekly", "metric": "profit", "sort": "trades"},
                {"timeframe": "monthly", "metric": "profit", "sort": "profit"},
                {"timeframe": "monthly", "metric": "profit", "sort": "volume"},
                {"timeframe": "monthly", "metric": "profit", "sort": "trades"},
            ]
            
            for config in leaderboard_configs:
                await self._scrape_leaderboard_config(context, config)
            
            # Try different URL patterns
            await self._scrape_alternative_urls(context)
            
            await browser.close()
            
        return self.all_wallets
    
    async def _scrape_leaderboard_config(self, context, config):
        """Scrape a specific leaderboard configuration"""
        timeframe = config["timeframe"]
        metric = config["metric"]
        sort = config.get("sort", metric)
        
        # Build URL
        base_url = f"https://polymarket.com/leaderboard/overall/{timeframe}/{metric}"
        if sort != metric:
            url = f"{base_url}?sort={sort}"
        else:
            url = base_url
        
        logger.info(f"Scraping: {url}")
        
        try:
            page = await context.new_page()
            
            # Try multiple pages
            for page_num in range(1, 6):  # Try first 5 pages
                if page_num == 1:
                    page_url = url
                else:
                    page_url = f"{url}?page={page_num}"
                
                logger.info(f"  Page {page_num}: {page_url}")
                
                try:
                    await page.goto(page_url, wait_until="domcontentloaded", timeout=10000)
                    await page.wait_for_timeout(2000)
                    
                    wallets = await self._extract_wallets_from_page(page)
                    
                    if wallets:
                        logger.info(f"    Found {len(wallets)} wallets")
                        
                        for addr, display in wallets.items():
                            if addr not in self.all_wallets:
                                self.all_wallets[addr] = {
                                    "display": display,
                                    "source": f"{timeframe}_{metric}_{sort}_page_{page_num}"
                                }
                    else:
                        logger.info(f"    No wallets found")
                        break  # Stop if no wallets found
                        
                except Exception as e:
                    logger.debug(f"    Error with page {page_num}: {e}")
                    break
            
            await page.close()
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
    
    async def _scrape_alternative_urls(self, context):
        """Try alternative URL patterns"""
        logger.info("Trying alternative URL patterns...")
        
        alternative_urls = [
            # Different leaderboard paths
            "https://polymarket.com/leaderboard/traders/weekly/profit",
            "https://polymarket.com/leaderboard/traders/monthly/profit",
            "https://polymarket.com/leaderboard/traders/alltime/profit",
            "https://polymarket.com/leaderboard/users/weekly/profit",
            "https://polymarket.com/leaderboard/users/monthly/profit",
            "https://polymarket.com/leaderboard/users/alltime/profit",
            
            # Different sorting parameters
            "https://polymarket.com/leaderboard/overall/weekly/profit?sort=profit&order=desc",
            "https://polymarket.com/leaderboard/overall/weekly/profit?sort=volume&order=desc",
            "https://polymarket.com/leaderboard/overall/weekly/profit?sort=trades&order=desc",
            "https://polymarket.com/leaderboard/overall/monthly/profit?sort=profit&order=desc",
            "https://polymarket.com/leaderboard/overall/monthly/profit?sort=volume&order=desc",
            "https://polymarket.com/leaderboard/overall/monthly/profit?sort=trades&order=desc",
            
            # Different time parameters
            "https://polymarket.com/leaderboard/overall/weekly/profit?timeframe=7d",
            "https://polymarket.com/leaderboard/overall/weekly/profit?period=week",
            "https://polymarket.com/leaderboard/overall/monthly/profit?timeframe=30d",
            "https://polymarket.com/leaderboard/overall/monthly/profit?period=month",
        ]
        
        for url in alternative_urls:
            try:
                page = await context.new_page()
                
                logger.info(f"Trying alternative: {url}")
                
                await page.goto(url, wait_until="domcontentloaded", timeout=10000)
                await page.wait_for_timeout(2000)
                
                wallets = await self._extract_wallets_from_page(page)
                
                if wallets:
                    logger.info(f"  Found {len(wallets)} wallets")
                    
                    for addr, display in wallets.items():
                        if addr not in self.all_wallets:
                            self.all_wallets[addr] = {
                                "display": display,
                                "source": f"alternative_{url}"
                            }
                else:
                    logger.info(f"  No wallets found")
                
                await page.close()
                
            except Exception as e:
                logger.error(f"Error with alternative URL {url}: {e}")
    
    async def _extract_wallets_from_page(self, page):
        """Extract wallet addresses from current page"""
        wallets = {}
        
        try:
            # Look for profile links
            profile_links = await page.query_selector_all('a[href*="/profile/"]')
            
            for link in profile_links:
                try:
                    href = await link.get_attribute('href')
                    if not href:
                        continue
                        
                    # Extract address from href
                    if '/profile/' in href:
                        tail = href.split('/profile/')[-1]
                        tail = tail.split('?')[0].split('#')[0]
                        
                        # Check if it's a valid Ethereum address
                        if self._is_valid_address(tail):
                            display_text = await link.inner_text()
                            display_text = display_text.strip() if display_text else tail
                            
                            wallets[tail.lower()] = display_text
                            
                except Exception as e:
                    logger.debug(f"Error processing profile link: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Error extracting wallets from page: {e}")
            
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
    """Main function to run comprehensive scraping"""
    logger.info("Starting comprehensive Polymarket wallet scraping...")
    
    scraper = ComprehensivePolymarketScraper()
    wallets = await scraper.scrape_all_possible_wallets()
    
    logger.info(f"🎉 FINAL RESULT: {len(wallets)} unique wallets found!")
    
    if len(wallets) >= 120:
        logger.info("✅ SUCCESS: Found 120+ wallets as requested!")
    else:
        logger.info(f"⚠️  Found {len(wallets)} wallets (target was 120+)")
    
    # Show sample
    logger.info("Sample wallets:")
    for i, (addr, info) in enumerate(list(wallets.items())[:20]):
        logger.info(f"  {i+1}. {addr} - {info['display']}")
    
    if len(wallets) > 20:
        logger.info(f"  ... and {len(wallets) - 20} more")
    
    return wallets

if __name__ == "__main__":
    wallets = asyncio.run(main())
