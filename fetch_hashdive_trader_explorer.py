#!/usr/bin/env python3
"""
HashDive Trader Explorer Scraper
Scrapes wallet addresses from https://hashdive.com/Trader_explorer
Uses Playwright to handle JavaScript-rendered content and pagination
"""

import asyncio
import re
import logging
from typing import Set, List, Optional
from datetime import datetime
import os
from dotenv import load_dotenv

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright not available. Install with: pip install playwright && playwright install")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Regex for Ethereum addresses
ADDRESS_RE = re.compile(r'0x[a-fA-F0-9]{40}')

# Proxy configuration (if available)
def get_proxy_config():
    """Get proxy configuration from environment"""
    load_dotenv()
    
    # Check global proxy enable flag (default: False - proxies disabled)
    enable_proxies = os.getenv("ENABLE_PROXIES", "false").lower() in ("true", "1", "yes")
    if not enable_proxies:
        return None
    
    proxy_str = os.getenv("POLYMARKET_PROXIES", "")
    if proxy_str:
        proxies = [p.strip() for p in proxy_str.split(",") if p.strip()]
        if proxies:
            # Use first proxy
            proxy_url = proxies[0]
            # Extract host:port from http://user:pass@host:port format
            if "@" in proxy_url:
                proxy_part = proxy_url.split("@")[-1]
            else:
                proxy_part = proxy_url.replace("http://", "").replace("https://", "")
            
            if ":" in proxy_part:
                host, port = proxy_part.rsplit(":", 1)
                return {
                    "server": f"http://{host}:{port}",
                    "username": proxy_url.split("@")[0].split("://")[-1].split(":")[0] if "@" in proxy_url else None,
                    "password": proxy_url.split("@")[0].split("://")[-1].split(":")[1] if "@" in proxy_url and ":" in proxy_url.split("@")[0] else None
                }
    return None


async def extract_addresses_from_table(page) -> Set[str]:
    """
    Extract wallet addresses from the User column in the table
    
    Returns:
        Set of unique wallet addresses found in the table
    """
    addresses: Set[str] = set()
    
    try:
        # Wait for table to be visible
        # Try multiple selectors for the table
        table_selectors = [
            "table",
            "[role='table']",
            ".table",
            "[data-testid*='table']",
            "table tbody",
            "table[class*='table']"
        ]
        
        table_element = None
        for selector in table_selectors:
            try:
                table_element = await page.wait_for_selector(selector, timeout=5000, state="visible")
                if table_element:
                    logger.debug(f"Found table with selector: {selector}")
                    break
            except PlaywrightTimeoutError:
                continue
        
        if not table_element:
            logger.warning("Table not found, trying to extract from page text")
            # Fallback: extract from page text
            page_text = await page.inner_text("body")
            found_addresses = ADDRESS_RE.findall(page_text)
            addresses.update(addr.lower() for addr in found_addresses)
            return addresses
        
        # Find all table rows
        rows = await table_element.query_selector_all("tr")
        logger.debug(f"Found {len(rows)} table rows")
        
        # Extract addresses from each row
        # Look for the User column (usually first or second column)
        for i, row in enumerate(rows):
            try:
                # Get all cells in the row
                cells = await row.query_selector_all("td, th")
                
                # Try to find the User column (contains Ethereum address)
                for cell in cells:
                    cell_text = await cell.inner_text()
                    # Check if cell contains an Ethereum address
                    cell_addresses = ADDRESS_RE.findall(cell_text)
                    if cell_addresses:
                        addresses.update(addr.lower() for addr in cell_addresses)
                        logger.debug(f"Row {i+1}: Found address {cell_addresses[0][:12]}...")
                        break  # Found address in this row, move to next row
                
            except Exception as e:
                logger.debug(f"Error processing row {i+1}: {e}")
                continue
        
        # If no addresses found in table cells, try extracting from row text
        if not addresses:
            logger.debug("No addresses in table cells, trying row text extraction")
            for i, row in enumerate(rows):
                try:
                    row_text = await row.inner_text()
                    row_addresses = ADDRESS_RE.findall(row_text)
                    if row_addresses:
                        addresses.update(addr.lower() for addr in row_addresses)
                        logger.debug(f"Row {i+1}: Found address {row_addresses[0][:12]}... in row text")
                except Exception:
                    continue
        
    except Exception as e:
        logger.error(f"Error extracting addresses from table: {e}")
        # Fallback: extract from page text
        try:
            page_text = await page.inner_text("body")
            found_addresses = ADDRESS_RE.findall(page_text)
            addresses.update(addr.lower() for addr in found_addresses)
            logger.info(f"Fallback: Found {len(found_addresses)} addresses in page text")
        except Exception:
            pass
    
    return addresses


async def get_total_pages(page) -> Optional[int]:
    """
    Get total number of pages from pagination info
    
    Returns:
        Total number of pages, or None if not found
    """
    try:
        # Look for pagination info that shows total pages
        # Common patterns: "Page 1 of 100", "1 / 100", "Total: 100 pages", etc.
        page_text = await page.inner_text("body")
        
        # Try to find patterns like "Page X of Y" or "X / Y" or "of Y"
        patterns = [
            r'page\s+\d+\s+of\s+(\d+)',
            r'(\d+)\s+pages?',
            r'of\s+(\d+)',
            r'/\s*(\d+)',
            r'total[:\s]+(\d+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            if matches:
                try:
                    total = int(matches[-1])  # Take last match (most likely total)
                    logger.info(f"Found total pages: {total}")
                    return total
                except ValueError:
                    continue
        
        # Try to find pagination element with total pages
        pagination_selectors = [
            ".pagination",
            "[class*='pagination']",
            "[data-testid*='pagination']",
            "[aria-label*='pagination']"
        ]
        
        for selector in pagination_selectors:
            try:
                pagination = await page.query_selector(selector)
                if pagination:
                    pagination_text = await pagination.inner_text()
                    # Look for numbers in pagination text
                    numbers = re.findall(r'\d+', pagination_text)
                    if numbers:
                        # Usually the largest number is total pages
                        total = max(int(n) for n in numbers)
                        logger.info(f"Found total pages from pagination: {total}")
                        return total
            except Exception:
                continue
        
        logger.warning("Could not determine total pages")
        return None
        
    except Exception as e:
        logger.debug(f"Error getting total pages: {e}")
        return None


async def go_to_page(page, page_number: int) -> bool:
    """
    Navigate to a specific page number
    
    Args:
        page: Playwright page object
        page_number: Page number to navigate to
    
    Returns:
        True if navigation successful, False otherwise
    """
    try:
        # Strategy 1: Find "Page number" input field and set value
        page_input_selectors = [
            "input[type='number']",
            "input[placeholder*='page']",
            "input[placeholder*='Page']",
            "input[name*='page']",
            "input[id*='page']",
            "[data-testid*='page-input']",
            "input[aria-label*='page']"
        ]
        
        page_input = None
        for selector in page_input_selectors:
            try:
                page_input = await page.query_selector(selector)
                if page_input:
                    # Check if it's visible and editable
                    is_visible = await page_input.is_visible()
                    is_enabled = await page_input.is_enabled()
                    if is_visible and is_enabled:
                        logger.debug(f"Found page input with selector: {selector}")
                        break
            except Exception:
                continue
        
        if page_input:
            # Clear and set page number
            await page_input.click()
            await page_input.fill("")  # Clear
            await page_input.fill(str(page_number))
            await page_input.press("Enter")  # Press Enter to submit
            logger.info(f"Set page number to {page_number} via input field")
            await page.wait_for_timeout(2000)  # Wait for page to load
            return True
        
        # Strategy 2: Use + button to increment pages
        # First, find current page number
        current_page = await get_current_page_number(page)
        if current_page is None:
            current_page = 1
        
        if page_number > current_page:
            # Click + button multiple times
            plus_button = None
            plus_selectors = [
                "button:has-text('+')",
                "button[aria-label*='next']",
                "button[aria-label*='increment']",
                "[data-testid*='next']",
                "[data-testid*='increment']",
                "button:has([class*='plus'])",
                "button:has([class*='add'])"
            ]
            
            for selector in plus_selectors:
                try:
                    plus_button = await page.query_selector(selector)
                    if plus_button and await plus_button.is_visible():
                        logger.debug(f"Found + button with selector: {selector}")
                        break
                except Exception:
                    continue
            
            if plus_button:
                clicks_needed = page_number - current_page
                for _ in range(clicks_needed):
                    await plus_button.click()
                    await page.wait_for_timeout(1000)  # Wait between clicks
                logger.info(f"Clicked + button {clicks_needed} times to reach page {page_number}")
                await page.wait_for_timeout(2000)  # Wait for page to load
                return True
        
        # Strategy 3: Direct navigation via URL (if page parameter exists)
        current_url = page.url
        if "page=" in current_url or "p=" in current_url:
            # Replace page parameter in URL
            import re
            new_url = re.sub(r'[?&](page|p)=\d+', f'\\1={page_number}', current_url)
            if new_url == current_url:
                # Add page parameter if it doesn't exist
                separator = "&" if "?" in current_url else "?"
                new_url = f"{current_url}{separator}page={page_number}"
            
            await page.goto(new_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)
            logger.info(f"Navigated to page {page_number} via URL")
            return True
        
        logger.warning(f"Could not navigate to page {page_number}")
        return False
        
    except Exception as e:
        logger.error(f"Error navigating to page {page_number}: {e}")
        return False


async def get_current_page_number(page) -> Optional[int]:
    """
    Get current page number from pagination
    
    Returns:
        Current page number, or None if not found
    """
    try:
        # Look for page number input field
        page_input_selectors = [
            "input[type='number']",
            "input[placeholder*='page']",
            "input[name*='page']"
        ]
        
        for selector in page_input_selectors:
            try:
                page_input = await page.query_selector(selector)
                if page_input:
                    value = await page_input.input_value()
                    if value:
                        return int(value)
            except Exception:
                continue
        
        # Look for pagination text
        page_text = await page.inner_text("body")
        # Try patterns like "Page 5 of 100" or "5 / 100"
        patterns = [
            r'page\s+(\d+)',
            r'(\d+)\s*/\s*\d+',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            if matches:
                try:
                    return int(matches[0])
                except ValueError:
                    continue
        
        return None
        
    except Exception as e:
        logger.debug(f"Error getting current page number: {e}")
        return None


async def scrape_trader_explorer(
    url: str = "https://hashdive.com/Trader_explorer",
    max_pages: Optional[int] = None,
    use_proxy: bool = True,
    headless: bool = True,
    delay_between_pages: float = 2.0
) -> Set[str]:
    """
    Scrape wallet addresses from HashDive Trader Explorer
    
    Args:
        url: URL to scrape
        max_pages: Maximum number of pages to scrape (None = all pages)
        use_proxy: Whether to use proxy from environment
        headless: Run browser in headless mode
        delay_between_pages: Delay in seconds between page navigations
    
    Returns:
        Set of unique wallet addresses
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Playwright not available. Cannot scrape JavaScript-rendered page.")
        return set()
    
    addresses: Set[str] = set()
    proxy_config = get_proxy_config() if use_proxy else None
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        if proxy_config:
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                proxy=proxy_config
            )
            logger.info(f"Using proxy: {proxy_config.get('server', 'N/A')}")
        
        page = await context.new_page()
        
        try:
            logger.info(f"Navigating to {url}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            logger.info("Page loaded, waiting for table to render...")
            
            # Wait for table to load
            await page.wait_for_timeout(5000)  # Initial wait for JavaScript
            
            # Wait for table selector
            try:
                await page.wait_for_selector("table, [role='table']", timeout=30000, state="visible")
                logger.info("Table found and visible")
            except PlaywrightTimeoutError:
                logger.warning("Table selector not found, continuing anyway...")
            
            # Get total pages (if available)
            total_pages = await get_total_pages(page)
            if total_pages:
                logger.info(f"Total pages available: {total_pages}")
                if max_pages is None:
                    max_pages = total_pages
                else:
                    max_pages = min(max_pages, total_pages)
            else:
                logger.info("Could not determine total pages, will use max_pages limit")
                if max_pages is None:
                    max_pages = 100  # Default limit if total not found
            
            logger.info(f"Will scrape up to {max_pages} pages")
            
            # Process pages
            current_page = 1
            pages_with_no_new_addresses = 0
            max_empty_pages = 3  # Stop if 3 consecutive pages have no new addresses
            
            while current_page <= max_pages:
                logger.info(f"=" * 80)
                logger.info(f"Processing page {current_page}/{max_pages if max_pages else '?'}")
                
                # Wait for table to be ready
                try:
                    await page.wait_for_selector("table, [role='table']", timeout=10000, state="visible")
                except PlaywrightTimeoutError:
                    logger.warning(f"Table not found on page {current_page}, skipping...")
                    current_page += 1
                    continue
                
                # Extract addresses from current page
                page_addresses = await extract_addresses_from_table(page)
                before_count = len(addresses)
                addresses.update(page_addresses)
                new_count = len(addresses) - before_count
                
                logger.info(f"Page {current_page}: Found {new_count} new addresses (total unique: {len(addresses)})")
                
                if new_count == 0:
                    pages_with_no_new_addresses += 1
                    if pages_with_no_new_addresses >= max_empty_pages:
                        logger.info(f"Stopping: {max_empty_pages} consecutive pages with no new addresses")
                        break
                else:
                    pages_with_no_new_addresses = 0
                
                # Check if we've reached the last page
                if current_page >= max_pages:
                    break
                
                # Navigate to next page
                next_page = current_page + 1
                logger.info(f"Navigating to page {next_page}...")
                
                success = await go_to_page(page, next_page)
                if not success:
                    logger.warning(f"Failed to navigate to page {next_page}, stopping")
                    break
                
                # Wait for page to load
                await page.wait_for_timeout(int(delay_between_pages * 1000))
                
                # Verify we're on the correct page
                actual_page = await get_current_page_number(page)
                if actual_page and actual_page != next_page:
                    logger.warning(f"Expected page {next_page}, but on page {actual_page}")
                    # Try to correct
                    await go_to_page(page, next_page)
                    await page.wait_for_timeout(int(delay_between_pages * 1000))
                
                current_page = next_page
            
            logger.info("=" * 80)
            logger.info(f"✅ Scraping complete! Processed {current_page} pages")
            logger.info(f"📊 Total unique addresses collected: {len(addresses)}")
            
            # Save screenshot for debugging
            screenshot_path = f"hashdive_trader_explorer_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"Screenshot saved to {screenshot_path}")
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}", exc_info=True)
        finally:
            await browser.close()
    
    return addresses


async def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape wallet addresses from HashiDive Trader Explorer")
    parser.add_argument("--url", default="https://hashdive.com/Trader_explorer", help="URL to scrape")
    parser.add_argument("--max-pages", type=int, default=None, help="Maximum number of pages to scrape (default: all)")
    parser.add_argument("--no-proxy", action="store_true", help="Don't use proxy")
    parser.add_argument("--headless", action="store_true", default=True, help="Run in headless mode (default: True)")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between pages in seconds (default: 2.0)")
    parser.add_argument("--output", type=str, default=None, help="Output file path (default: auto-generated)")
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("HashDive Trader Explorer Scraper")
    logger.info("=" * 80)
    
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Playwright not available. Please install: pip install playwright && playwright install")
        return
    
    addresses = await scrape_trader_explorer(
        url=args.url,
        max_pages=args.max_pages,
        use_proxy=not args.no_proxy,
        headless=args.headless,
        delay_between_pages=args.delay
    )
    
    logger.info("=" * 80)
    logger.info(f"✅ Scraping complete!")
    logger.info(f"📊 Total unique addresses found: {len(addresses)}")
    
    if addresses:
        # Save to file
        if args.output:
            output_file = args.output
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"hashdive_trader_explorer_wallets_{timestamp}.txt"
        
        with open(output_file, "w") as f:
            for addr in sorted(addresses):
                f.write(f"{addr}\n")
        
        logger.info(f"💾 Addresses saved to {output_file}")
        logger.info(f"\n📋 Sample addresses (first 10):")
        for addr in list(sorted(addresses))[:10]:
            logger.info(f"   {addr}")
    else:
        logger.warning("⚠️ No addresses found. The page structure might have changed or require authentication.")
        logger.info("💡 Try running with --headless=False to see what's happening")


if __name__ == "__main__":
    asyncio.run(main())
