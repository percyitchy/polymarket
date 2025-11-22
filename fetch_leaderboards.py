"""
Polymarket Leaderboard Scraper using Playwright
Scrapes all pages from Polymarket leaderboards to extract wallet addresses
Supports proxy rotation via ProxyManager
"""

import asyncio
import logging
from typing import List, Dict, Set, Optional
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from urllib.parse import urljoin, urlparse
import re
import os

# Try to import ProxyManager
try:
    from proxy_manager import ProxyManager
    PROXY_MANAGER_AVAILABLE = True
except ImportError:
    PROXY_MANAGER_AVAILABLE = False
    ProxyManager = None

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PolymarketLeaderboardScraper:
    def __init__(self, headless: bool = True, use_proxy: bool = True):
        self.headless = headless
        self.browser = None
        self.context = None
        self.use_proxy = use_proxy
        self.proxy_manager = None
        
        # Initialize proxy manager if available
        if use_proxy and PROXY_MANAGER_AVAILABLE:
            try:
                self.proxy_manager = ProxyManager()
                if self.proxy_manager.proxy_enabled:
                    logger.info(f"Proxy manager initialized with {len(self.proxy_manager.proxies)} proxies")
            except Exception as e:
                logger.warning(f"Failed to initialize proxy manager: {e}")
        
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        
        # Configure browser launch options
        launch_options = {
            "headless": self.headless
        }
        
        # Configure browser context with proxy if available
        context_options = {
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # Add proxy if available
        if self.proxy_manager and self.proxy_manager.proxy_enabled:
            proxy = self.proxy_manager.get_proxy(rotate=True)
            if proxy:
                # Extract proxy URL from proxy dict (it's the same for http/https)
                proxy_url = proxy.get("http") or proxy.get("https")
                if proxy_url:
                    parsed = urlparse(proxy_url)
                    context_options["proxy"] = {
                        "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
                        "username": parsed.username,
                        "password": parsed.password
                    }
                    logger.info(f"Using proxy: {parsed.hostname}:{parsed.port}")
        
        self.browser = await self.playwright.chromium.launch(**launch_options)
        self.context = await self.browser.new_context(**context_options)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def scrape_leaderboard_url(self, url: str, max_pages: int = 20) -> Dict[str, Dict[str, str]]:
        """
        Scrape a single leaderboard URL, paginating through pages
        Returns dict of {address: {display, source}}
        
        Args:
            url: Leaderboard URL to scrape
            max_pages: Maximum number of pages to scrape (default: 20)
        """
        logger.info(f"Starting to scrape leaderboard: {url} (max {max_pages} pages)")
        wallets = {}
        
        page = await self.context.new_page()
        
        try:
            # Navigate to the leaderboard
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(2000)  # Additional wait for React to load
            
            page_num = 1
            consecutive_empty_pages = 0
            
            while page_num <= max_pages:
                logger.info(f"Scraping page {page_num}/{max_pages} of {url}")
                
                # Wait for the leaderboard content to load
                try:
                    await page.wait_for_selector('[data-testid="leaderboard-table"], .leaderboard-table, table', timeout=10000)
                except Exception as e:
                    logger.warning(f"Could not find leaderboard table on page {page_num}: {e}")
                
                # Extract wallet addresses from current page
                page_wallets = await self._extract_wallets_from_page(page)
                
                if not page_wallets:
                    consecutive_empty_pages += 1
                    logger.info(f"No wallets found on page {page_num}")
                    
                    if consecutive_empty_pages >= 2:
                        logger.info(f"Stopping pagination after {consecutive_empty_pages} empty pages")
                        break
                else:
                    consecutive_empty_pages = 0
                    logger.info(f"Found {len(page_wallets)} wallets on page {page_num}")
                    
                    # Add wallets to collection
                    for addr, display in page_wallets.items():
                        wallets[addr.lower()] = {
                            "display": display,
                            "source": url
                        }
                
                # Check if we've reached max pages
                if page_num >= max_pages:
                    logger.info(f"Reached maximum page limit ({max_pages}) for {url}")
                    break
                
                # Try to click next page button
                next_clicked = await self._click_next_page(page)
                if not next_clicked:
                    logger.info(f"No more pages available after page {page_num}")
                    break
                
                # Wait for page to load
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1000)  # Additional wait
                
                page_num += 1
                    
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
        finally:
            await page.close()
            
        logger.info(f"Completed scraping {url}: found {len(wallets)} unique wallets")
        return wallets

    async def _extract_wallets_from_page(self, page: Page) -> Dict[str, str]:
        """
        Extract wallet addresses and display names from current page
        """
        wallets = {}
        
        try:
            # Look for profile links in various possible selectors
            profile_links = await page.query_selector_all('a[href*="/profile/"]')
            
            for link in profile_links:
                try:
                    href = await link.get_attribute('href')
                    if not href:
                        continue
                        
                    # Extract address from href
                    if '/profile/' in href:
                        tail = href.split('/profile/')[-1]
                        tail = tail.split('?')[0].split('#')[0]  # Remove query params and fragments
                        
                        # Check if it's a valid Ethereum address
                        if self._is_valid_address(tail):
                            # Get display text
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
        """
        Check if string is a valid Ethereum address
        """
        if not address.startswith('0x'):
            return False
        if len(address) != 42:
            return False
        # Check if it's hex
        try:
            int(address[2:], 16)
            return True
        except ValueError:
            return False

    async def _click_next_page(self, page: Page) -> bool:
        """
        Try to click the next page button
        Returns True if successful, False if no next page available
        """
        # Common selectors for next page buttons
        next_selectors = [
            'button[aria-label*="next" i]',
            'button[aria-label*="Next" i]',
            'button:has-text("Next")',
            'button:has-text(">")',
            'button:has-text("→")',
            '[data-testid*="next"]',
            '[data-testid*="Next"]',
            '.next-page',
            '.pagination-next',
            'button[disabled=false]:has-text("Next")',
            'a[aria-label*="next" i]',
            'a[aria-label*="Next" i]'
        ]
        
        for selector in next_selectors:
            try:
                next_button = await page.query_selector(selector)
                if next_button:
                    # Check if button is disabled
                    is_disabled = await next_button.is_disabled()
                    if is_disabled:
                        logger.debug(f"Next button found but disabled: {selector}")
                        continue
                        
                    # Try to click
                    await next_button.click()
                    logger.debug(f"Successfully clicked next button: {selector}")
                    return True
                    
            except Exception as e:
                logger.debug(f"Failed to click next button with selector {selector}: {e}")
                continue
                
        logger.debug("No next page button found or clickable")
        return False

    async def scrape_all_leaderboards(self, urls: List[str], max_pages_per_url: int = 20) -> Dict[str, Dict[str, str]]:
        """
        Scrape multiple leaderboard URLs
        
        Args:
            urls: List of leaderboard URLs to scrape
            max_pages_per_url: Maximum pages to scrape per URL (default: 20)
        """
        all_wallets = {}
        
        for url in urls:
            try:
                wallets = await self.scrape_leaderboard_url(url, max_pages=max_pages_per_url)
                all_wallets.update(wallets)
                logger.info(f"Total wallets collected so far: {len(all_wallets)}")
            except Exception as e:
                logger.error(f"Failed to scrape {url}: {e}")
                continue
                
        logger.info(f"Scraping complete. Total unique wallets: {len(all_wallets)}")
        return all_wallets

async def scrape_polymarket_leaderboards(urls: List[str], headless: bool = True, max_pages_per_url: int = 20, use_proxy: bool = True) -> Dict[str, Dict[str, str]]:
    """
    Main function to scrape Polymarket leaderboards
    
    Args:
        urls: List of leaderboard URLs to scrape
        headless: Whether to run browser in headless mode
        max_pages_per_url: Maximum pages to scrape per URL (default: 20)
        use_proxy: Whether to use proxy rotation (default: True)
        
    Returns:
        Dict of {address: {display, source}}
    """
    async with PolymarketLeaderboardScraper(headless=headless, use_proxy=use_proxy) as scraper:
        return await scraper.scrape_all_leaderboards(urls, max_pages_per_url=max_pages_per_url)

# Example usage
if __name__ == "__main__":
    # Default leaderboard URLs
    leaderboard_urls = [
        "https://polymarket.com/leaderboard/overall/today/profit",
        "https://polymarket.com/leaderboard/overall/weekly/profit", 
        "https://polymarket.com/leaderboard/overall/monthly/profit"
    ]
    
    async def main():
        wallets = await scrape_polymarket_leaderboards(leaderboard_urls)
        print(f"\nScraped {len(wallets)} unique wallets:")
        for addr, info in list(wallets.items())[:10]:  # Show first 10
            print(f"  {addr} - {info['display']} (from {info['source']})")
        if len(wallets) > 10:
            print(f"  ... and {len(wallets) - 10} more")
    
    asyncio.run(main())
