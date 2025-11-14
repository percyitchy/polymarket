#!/usr/bin/env python3
"""
Aggressive scraper to get maximum wallets from Polymarket
Try different approaches to get 120+ wallets
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

class AggressivePolymarketScraper:
    def __init__(self):
        self.all_wallets = {}
        
    async def scrape_with_different_strategies(self):
        """Try different scraping strategies to maximize wallet collection"""
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # Strategy 1: Try weekly profit with aggressive pagination
            await self._scrape_weekly_profit_aggressive(context)
            
            # Strategy 2: Try monthly profit with aggressive pagination  
            await self._scrape_monthly_profit_aggressive(context)
            
            # Strategy 3: Try different URL patterns
            await self._scrape_different_urls(context)
            
            await browser.close()
            
        return self.all_wallets
    
    async def _scrape_weekly_profit_aggressive(self, context):
        """Aggressively scrape weekly profit leaderboard"""
        logger.info("Strategy 1: Aggressive weekly profit scraping...")
        
        url = "https://polymarket.com/leaderboard/overall/weekly/profit"
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)
            
            page_num = 1
            consecutive_empty = 0
            
            while page_num <= 50:  # Try up to 50 pages
                logger.info(f"Scraping page {page_num} of weekly profit...")
                
                # Extract wallets from current page
                wallets = await self._extract_wallets_from_page(page)
                
                if wallets:
                    consecutive_empty = 0
                    logger.info(f"Found {len(wallets)} wallets on page {page_num}")
                    
                    # Add to collection
                    for addr, display in wallets.items():
                        if addr not in self.all_wallets:
                            self.all_wallets[addr] = {
                                "display": display,
                                "source": f"weekly_profit_page_{page_num}"
                            }
                else:
                    consecutive_empty += 1
                    logger.info(f"No wallets found on page {page_num} (empty count: {consecutive_empty})")
                    
                    if consecutive_empty >= 3:
                        logger.info("Stopping after 3 consecutive empty pages")
                        break
                
                # Try to go to next page
                next_clicked = await self._try_next_page(page)
                if not next_clicked:
                    logger.info(f"No more pages available after page {page_num}")
                    break
                
                await page.wait_for_timeout(2000)
                page_num += 1
            
            logger.info(f"Weekly profit scraping complete: {len(self.all_wallets)} total wallets")
            
        except Exception as e:
            logger.error(f"Error in weekly profit scraping: {e}")
        finally:
            await page.close()
    
    async def _scrape_monthly_profit_aggressive(self, context):
        """Aggressively scrape monthly profit leaderboard"""
        logger.info("Strategy 2: Aggressive monthly profit scraping...")
        
        url = "https://polymarket.com/leaderboard/overall/monthly/profit"
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)
            
            page_num = 1
            consecutive_empty = 0
            
            while page_num <= 50:  # Try up to 50 pages
                logger.info(f"Scraping page {page_num} of monthly profit...")
                
                # Extract wallets from current page
                wallets = await self._extract_wallets_from_page(page)
                
                if wallets:
                    consecutive_empty = 0
                    logger.info(f"Found {len(wallets)} wallets on page {page_num}")
                    
                    # Add to collection
                    for addr, display in wallets.items():
                        if addr not in self.all_wallets:
                            self.all_wallets[addr] = {
                                "display": display,
                                "source": f"monthly_profit_page_{page_num}"
                            }
                else:
                    consecutive_empty += 1
                    logger.info(f"No wallets found on page {page_num} (empty count: {consecutive_empty})")
                    
                    if consecutive_empty >= 3:
                        logger.info("Stopping after 3 consecutive empty pages")
                        break
                
                # Try to go to next page
                next_clicked = await self._try_next_page(page)
                if not next_clicked:
                    logger.info(f"No more pages available after page {page_num}")
                    break
                
                await page.wait_for_timeout(2000)
                page_num += 1
            
            logger.info(f"Monthly profit scraping complete: {len(self.all_wallets)} total wallets")
            
        except Exception as e:
            logger.error(f"Error in monthly profit scraping: {e}")
        finally:
            await page.close()
    
    async def _scrape_different_urls(self, context):
        """Try different URL patterns"""
        logger.info("Strategy 3: Trying different URL patterns...")
        
        # Different URL patterns to try
        url_patterns = [
            "https://polymarket.com/leaderboard/overall/weekly/profit?page={}",
            "https://polymarket.com/leaderboard/overall/monthly/profit?page={}",
            "https://polymarket.com/leaderboard/overall/weekly/profit&page={}",
            "https://polymarket.com/leaderboard/overall/monthly/profit&page={}",
        ]
        
        for pattern in url_patterns:
            try:
                page = await context.new_page()
                
                for page_num in range(1, 21):  # Try first 20 pages
                    url = pattern.format(page_num)
                    logger.info(f"Trying URL: {url}")
                    
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=10000)
                        await page.wait_for_timeout(2000)
                        
                        wallets = await self._extract_wallets_from_page(page)
                        
                        if wallets:
                            logger.info(f"Found {len(wallets)} wallets with URL pattern")
                            
                            for addr, display in wallets.items():
                                if addr not in self.all_wallets:
                                    self.all_wallets[addr] = {
                                        "display": display,
                                        "source": f"url_pattern_{pattern}"
                                    }
                        else:
                            logger.info(f"No wallets found with URL pattern")
                            break  # Stop if no wallets found
                            
                    except Exception as e:
                        logger.debug(f"Error with URL {url}: {e}")
                        break
                
                await page.close()
                
            except Exception as e:
                logger.error(f"Error with pattern {pattern}: {e}")
    
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
    
    async def _try_next_page(self, page):
        """Try to click the next page button"""
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
                    is_disabled = await next_button.is_disabled()
                    if is_disabled:
                        continue
                        
                    await next_button.click()
                    return True
                    
            except Exception as e:
                logger.debug(f"Failed to click next button with selector {selector}: {e}")
                continue
                
        return False

async def main():
    """Main function to run aggressive scraping"""
    logger.info("Starting aggressive Polymarket wallet scraping...")
    
    scraper = AggressivePolymarketScraper()
    wallets = await scraper.scrape_with_different_strategies()
    
    logger.info(f"🎉 FINAL RESULT: {len(wallets)} unique wallets found!")
    
    if len(wallets) >= 120:
        logger.info("✅ SUCCESS: Found 120+ wallets as requested!")
    else:
        logger.info(f"⚠️  Found {len(wallets)} wallets (target was 120+)")
    
    # Show sample
    logger.info("Sample wallets:")
    for i, (addr, info) in enumerate(list(wallets.items())[:10]):
        logger.info(f"  {i+1}. {addr} - {info['display']}")
    
    if len(wallets) > 10:
        logger.info(f"  ... and {len(wallets) - 10} more")
    
    return wallets

if __name__ == "__main__":
    wallets = asyncio.run(main())
