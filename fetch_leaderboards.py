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
from dotenv import load_dotenv

load_dotenv()

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

# Leaderboard URLs configuration
# Format: list of tuples (name, url)
LEADERBOARD_URLS = [
    ("weekly_profit", "https://polymarket.com/leaderboard/overall/weekly/profit"),
    ("monthly_profit", "https://polymarket.com/leaderboard/overall/monthly/profit"),
    ("weekly_volume", "https://polymarket.com/leaderboard/overall/weekly/volume"),
    ("monthly_volume", "https://polymarket.com/leaderboard/overall/monthly/volume"),
    ("alltime_profit", "https://polymarket.com/leaderboard/overall/all/profit"),
    # NOTE: alltime_volume URL often times out and is disabled by default
    # It can be enabled via environment variable LEADERBOARD_URLS if needed
]

# Optional URLs that are known to be problematic (disabled by default)
# TODO: overall/all/volume often times out and needs separate debugging
OPTIONAL_LEADERBOARD_URLS = [
    ("alltime_volume", "https://polymarket.com/leaderboard/overall/all/volume"),
]

# Flag to enable/disable alltime_volume leaderboard
ENABLE_ALLTIME_VOLUME_LEADERBOARD = os.getenv("ENABLE_ALLTIME_VOLUME_LEADERBOARD", "false").strip().lower() in ("true", "1", "yes", "on")

# Allow override from environment variable (comma-separated URLs)
env_urls = os.getenv("LEADERBOARD_URLS")
if env_urls:
    # Parse comma-separated URLs and create named entries
    urls_list = [url.strip() for url in env_urls.split(",") if url.strip()]
    if urls_list:
        LEADERBOARD_URLS = [(f"custom_{i}", url) for i, url in enumerate(urls_list)]

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
        
        # Add proxy if available (only HTTP/HTTPS, not SOCKS5)
        if self.proxy_manager and self.proxy_manager.proxy_enabled:
            proxy = self.proxy_manager.get_proxy(rotate=True)
            if proxy:
                # Extract proxy URL from proxy dict (it's the same for http/https)
                proxy_url = proxy.get("http") or proxy.get("https")
                if proxy_url:
                    parsed = urlparse(proxy_url)
                    scheme = (parsed.scheme or "").lower()
                    
                    if scheme in ("http", "https"):
                        # Playwright supports HTTP/HTTPS proxies with authentication
                        context_options["proxy"] = {
                            "server": f"{scheme}://{parsed.hostname}:{parsed.port}",
                            "username": parsed.username,
                            "password": parsed.password,
                        }
                        logger.info(
                            f"[Leaderboards HTML] Using HTTP proxy for Playwright: "
                            f"{parsed.hostname}:{parsed.port}"
                        )
                    else:
                        # SOCKS5 or other unsupported scheme - skip proxy for Playwright
                        logger.warning(
                            f"[Leaderboards HTML] Unsupported proxy scheme for Playwright "
                            f"({scheme}) in URL {proxy_url}, running without proxy"
                        )
        else:
            logger.info("[Leaderboards HTML] No proxy manager or proxies disabled, running without proxy")
        
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

    async def scrape_leaderboard_url(self, url: str, max_pages: int = 30) -> Dict[str, Dict[str, str]]:
        """
        Scrape a single leaderboard URL, paginating through pages
        Returns dict of {address: {display, source}}
        
        Args:
            url: Leaderboard URL to scrape
            max_pages: Maximum number of pages to scrape (default: 30)
        """
        logger.info(f"[Leaderboards HTML] Starting to scrape leaderboard: {url} (max {max_pages} pages)")
        wallets = {}
        
        # Special handling for problematic all/volume URL
        is_all_volume = "overall/all/volume" in url
        
        # Configuration constants
        if is_all_volume:
            PAGE_LOAD_WAIT_MS = 5000  # Longer wait for all/volume
            NAVIGATION_TIMEOUT_MS = 90000  # Longer timeout for all/volume (90 seconds)
            SELECTOR_TIMEOUT_MS = 30000  # Selector wait timeout
            MAX_TOTAL_TIME_MS = 90000  # Maximum total time for all/volume (90 seconds)
            logger.info("[Leaderboards HTML] all/volume: using custom parser (reason: known timeout issues, extended timeouts)")
        else:
            PAGE_LOAD_WAIT_MS = 3000  # Wait time after domcontentloaded (3 seconds)
            NAVIGATION_TIMEOUT_MS = 60000  # Navigation timeout
            SELECTOR_TIMEOUT_MS = 60000  # Selector wait timeout
            MAX_TOTAL_TIME_MS = None  # No time limit for other URLs
        
        page = await self.context.new_page()
        start_time = asyncio.get_event_loop().time()
        
        # Track response status for all/volume debugging
        response_status = None
        response_received = False
        
        def handle_response(response):
            nonlocal response_status, response_received
            if url in response.url or response.url.startswith("https://polymarket.com/leaderboard"):
                response_status = response.status
                response_received = True
                if is_all_volume:
                    logger.info(f"[Leaderboards HTML] all/volume: Response status={response_status}, url={response.url}")
        
        page.on("response", handle_response)
        
        try:
            # Navigate to the leaderboard with retry mechanism
            # Use lighter wait strategy: domcontentloaded instead of networkidle
            max_retries = 2
            navigation_success = False
            navigation_start_time = None
            navigation_end_time = None
            
            for attempt in range(max_retries + 1):
                try:
                    navigation_start_time = asyncio.get_event_loop().time()
                    await page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
                    navigation_end_time = asyncio.get_event_loop().time()
                    navigation_duration = navigation_end_time - navigation_start_time
                    logger.info(f"[Leaderboards HTML] page.goto completed in {navigation_duration:.2f}s")
                    
                    # Wait additional time for dynamic content
                    await page.wait_for_timeout(PAGE_LOAD_WAIT_MS)
                    
                    # Check for Cloudflare/Captcha/Access denied (especially for all/volume)
                    if is_all_volume:
                        page_content_lower = (await page.content()).lower()
                        cloudflare_indicators = ["cloudflare", "checking your browser", "ddos protection"]
                        captcha_indicators = ["captcha", "recaptcha", "hcaptcha"]
                        access_denied_indicators = ["access denied", "forbidden", "403", "blocked"]
                        
                        for indicator in cloudflare_indicators:
                            if indicator in page_content_lower:
                                logger.warning(f"[Leaderboards HTML] all/volume: Cloudflare protection detected")
                                break
                        
                        for indicator in captcha_indicators:
                            if indicator in page_content_lower:
                                logger.warning(f"[Leaderboards HTML] all/volume: Captcha challenge detected")
                                break
                        
                        for indicator in access_denied_indicators:
                            if indicator in page_content_lower:
                                logger.warning(f"[Leaderboards HTML] all/volume: Access denied detected (status: {response_status or 'N/A'})")
                                break
                    
                    # Wait for leaderboard table selector
                    try:
                        await page.wait_for_selector('[data-testid="leaderboard-table"]', timeout=SELECTOR_TIMEOUT_MS)
                        logger.info(f"[Leaderboards HTML] wait_for_selector successful: leaderboard table found")
                        navigation_success = True
                        break
                    except Exception as selector_error:
                        logger.warning(f"[Leaderboards HTML] wait_for_selector timeout: {selector_error}")
                        # Try to continue anyway - maybe table is there but selector is different
                        navigation_success = True
                        break
                        
                except Exception as e:
                    if attempt < max_retries:
                        logger.warning(f"[Leaderboards HTML] Navigation attempt {attempt + 1} failed: {e}, retrying...")
                        await asyncio.sleep(2)
                    else:
                        # Enhanced error logging for all/volume
                        if is_all_volume:
                            error_details = f"status={response_status or 'N/A'}, response_received={response_received}"
                            logger.warning(f"[Leaderboards HTML] Skipping overall/all/volume after {max_retries + 1} failed attempts ({error_details})")
                        else:
                            logger.error(f"[Leaderboards HTML] Failed to navigate to {url} after {max_retries + 1} attempts: {e}")
                        return wallets  # Return empty dict if navigation fails
            
            if not navigation_success:
                return wallets
            
            # For all/volume, try scrolling to load more data (infinite scroll)
            if is_all_volume:
                logger.info("[Leaderboards HTML] all/volume: Attempting scroll-based loading...")
                previous_row_count = 0
                no_change_count = 0
                
                for scroll_attempt in range(10):
                    # Check current time limit
                    elapsed_time = (asyncio.get_event_loop().time() - start_time) * 1000
                    if MAX_TOTAL_TIME_MS and elapsed_time > MAX_TOTAL_TIME_MS:
                        logger.warning(f"[Leaderboards HTML] all/volume: Reached time limit ({MAX_TOTAL_TIME_MS}ms), stopping scroll")
                        break
                    
                    # Scroll down
                    await page.mouse.wheel(0, 2000)
                    await page.wait_for_timeout(1000)
                    
                    # Check if table rows increased
                    try:
                        rows = await page.query_selector_all('[data-testid="leaderboard-table"] tr, .leaderboard-table tr, table tr')
                        current_row_count = len(rows)
                        
                        if current_row_count > previous_row_count:
                            logger.info(f"[Leaderboards HTML] all/volume: Scroll {scroll_attempt + 1}: rows increased from {previous_row_count} to {current_row_count}")
                            previous_row_count = current_row_count
                            no_change_count = 0
                        else:
                            no_change_count += 1
                            if no_change_count >= 3:
                                logger.info(f"[Leaderboards HTML] all/volume: No new rows after {no_change_count} scrolls, stopping")
                                break
                    except Exception as e:
                        logger.debug(f"[Leaderboards HTML] all/volume: Error checking rows after scroll: {e}")
                        no_change_count += 1
                        if no_change_count >= 3:
                            break
            
            page_num = 1
            consecutive_empty_pages = 0
            
            while page_num <= max_pages:
                # Check time limit for all/volume
                if is_all_volume and MAX_TOTAL_TIME_MS:
                    elapsed_time = (asyncio.get_event_loop().time() - start_time) * 1000
                    if elapsed_time > MAX_TOTAL_TIME_MS:
                        logger.warning(f"[Leaderboards HTML] all/volume: Reached time limit ({MAX_TOTAL_TIME_MS}ms), stopping pagination at page {page_num}")
                        break
                logger.info(f"[Leaderboards HTML] Scraping page {page_num}/{max_pages} ({url})")
                
                # Wait for the leaderboard content to load with retry mechanism
                selector_found = False
                for attempt in range(max_retries + 1):
                    try:
                        await page.wait_for_selector('[data-testid="leaderboard-table"]', timeout=SELECTOR_TIMEOUT_MS)
                        selector_found = True
                        break
                    except Exception as e:
                        if attempt < max_retries:
                            logger.warning(f"[Leaderboards HTML] Selector wait attempt {attempt + 1} failed on page {page_num}: {e}, retrying...")
                            await asyncio.sleep(2)
                        else:
                            logger.warning(f"[Leaderboards HTML] Timeout on page {page_num}/{max_pages} ({url}) - could not find leaderboard table")
                            # Continue to next page instead of breaking
                            break
                
                # Extract wallet addresses from current page
                page_wallets = await self._extract_wallets_from_page(page)
                
                if not page_wallets:
                    consecutive_empty_pages += 1
                    logger.info(f"[Leaderboards HTML] No wallets found on page {page_num}")
                    
                    if consecutive_empty_pages >= 2:
                        logger.info(f"[Leaderboards HTML] Stopping pagination after {consecutive_empty_pages} empty pages")
                        break
                else:
                    consecutive_empty_pages = 0
                    logger.info(f"[Leaderboards HTML] Found {len(page_wallets)} wallets on page {page_num}")
                    
                    # Add wallets to collection
                    for addr, display in page_wallets.items():
                        wallets[addr.lower()] = {
                            "display": display,
                            "source": url
                        }
                    
                    logger.info(f"[Leaderboards HTML] Total wallets collected so far: {len(wallets)}")
                
                # Check if we've reached max pages
                if page_num >= max_pages:
                    logger.info(f"[Leaderboards HTML] Reached maximum page limit ({max_pages}) for {url}")
                    break
                
                # Try to click next page button
                next_clicked = await self._click_next_page(page)
                if not next_clicked:
                    logger.info(f"[Leaderboards HTML] No more pages available after page {page_num}")
                    break
                
                # Wait for page to load (lighter strategy)
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_timeout(1000)  # Additional wait
                
                page_num += 1
                    
        except Exception as e:
            logger.error(f"[Leaderboards HTML] Error scraping {url}: {e}")
        finally:
            await page.close()
            
        logger.info(f"[Leaderboards HTML] Completed scraping {url}: found {len(wallets)} unique wallets")
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

    async def scrape_all_leaderboards(self, urls: List[str], max_pages_per_url: int = 30, url_names: Optional[List[str]] = None) -> Dict[str, Dict[str, str]]:
        """
        Scrape multiple leaderboard URLs
        
        Guarantees partial success: if one URL fails, others continue processing.
        The all_wallets dict is never reset, ensuring collected wallets are preserved.
        
        Args:
            urls: List of leaderboard URLs to scrape
            max_pages_per_url: Maximum pages to scrape per URL (default: 30)
            url_names: Optional list of names for each URL (for logging)
        """
        all_wallets = {}  # Shared collection - never reset, only updated
        url_names = url_names or [f"url_{i}" for i in range(len(urls))]
        
        logger.info("=" * 80)
        logger.info(f"[Leaderboards HTML] Starting scraping {len(urls)} leaderboard(s) (max {max_pages_per_url} pages each)")
        logger.info("=" * 80)
        
        for idx, url in enumerate(urls):
            name = url_names[idx] if idx < len(url_names) else f"url_{idx}"
            logger.info(f"[Leaderboards HTML] Start scraping {name} ... (max {max_pages_per_url} pages)")
            logger.info(f"[Leaderboards HTML] URL: {url}")
            
            try:
                wallets = await self.scrape_leaderboard_url(url, max_pages=max_pages_per_url)
                unique_new = len([addr for addr in wallets if addr not in all_wallets])
                # Update shared collection - never reset it
                all_wallets.update(wallets)
                
                logger.info(f"[Leaderboards HTML] url_{name}: found {len(wallets)} wallets ({unique_new} new unique, total: {len(all_wallets)})")
            except Exception as e:
                # Log error but continue to next URL - don't break the entire process
                import traceback
                logger.warning(f"[Leaderboards HTML] Failed to scrape {name} ({url}): {e}")
                logger.debug(f"[Leaderboards HTML] Traceback: {traceback.format_exc()}")
                # Continue to next URL - all_wallets is preserved
                continue
        
        logger.info("=" * 80)
        logger.info(f"[Leaderboards HTML] Scraping complete. Total unique wallets: {len(all_wallets)}")
        logger.info("=" * 80)
        return all_wallets

async def scrape_polymarket_leaderboards(urls: Optional[List[str]] = None, headless: bool = True, max_pages_per_url: int = 30, use_proxy: bool = True) -> Dict[str, Dict[str, str]]:
    """
    Main function to scrape Polymarket leaderboards
    
    Args:
        urls: Optional list of leaderboard URLs to scrape (defaults to LEADERBOARD_URLS)
        headless: Whether to run browser in headless mode
        max_pages_per_url: Maximum pages to scrape per URL (default: 30)
        use_proxy: Whether to use proxy rotation (default: True)
        
    Returns:
        Dict of {address: {display, source}}
    """
    # Use default URLs if not provided
    if urls is None:
        urls = [url for _, url in LEADERBOARD_URLS]
        url_names = [name for name, _ in LEADERBOARD_URLS]
        
        # Add alltime_volume if enabled via flag
        if ENABLE_ALLTIME_VOLUME_LEADERBOARD:
            alltime_volume_url = "https://polymarket.com/leaderboard/overall/all/volume"
            if alltime_volume_url not in urls:
                urls.append(alltime_volume_url)
                url_names.append("alltime_volume")
                logger.info("[Leaderboards HTML] alltime_volume leaderboard enabled via ENABLE_ALLTIME_VOLUME_LEADERBOARD flag")
        else:
            logger.info("[Leaderboards HTML] alltime_volume leaderboard disabled (set ENABLE_ALLTIME_VOLUME_LEADERBOARD=true to enable)")
    else:
        url_names = None
    
    async with PolymarketLeaderboardScraper(headless=headless, use_proxy=use_proxy) as scraper:
        return await scraper.scrape_all_leaderboards(urls, max_pages_per_url=max_pages_per_url, url_names=url_names)

# Example usage
if __name__ == "__main__":
    async def main():
        # Use default LEADERBOARD_URLS configuration
        wallets = await scrape_polymarket_leaderboards()
        print(f"\nScraped {len(wallets)} unique wallets:")
        for addr, info in list(wallets.items())[:10]:  # Show first 10
            print(f"  {addr} - {info['display']} (from {info['source']})")
        if len(wallets) > 10:
            print(f"  ... and {len(wallets) - 10} more")
    
    asyncio.run(main())
