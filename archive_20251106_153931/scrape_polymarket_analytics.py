#!/usr/bin/env python3
"""
Scraper for polymarketanalytics.com/traders
Extracts wallets matching our criteria:
- Min trades: 6
- Win rate: >= 75%
- Daily frequency: <= 20.0
- Max trades: <= 1000
"""

import requests
import json
import time
import logging
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import re
import asyncio

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PolymarketAnalyticsScraper:
    """Scraper for polymarketanalytics.com/traders leaderboard"""
    
    def __init__(self):
        self.base_url = "https://polymarketanalytics.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.wallets: Dict[str, Dict] = {}
    
    def scrape_traders(self, max_pages: int = 50, min_win_rate: float = 0.75, 
                      min_trades: int = 6, max_trades: int = 1000,
                      max_daily_freq: float = 20.0) -> Dict[str, Dict]:
        """
        Scrape traders from polymarketanalytics.com
        
        Args:
            max_pages: Maximum pages to scrape
            min_win_rate: Minimum win rate (0.75 = 75%)
            min_trades: Minimum total positions/trades
            max_trades: Maximum total positions/trades
            max_daily_freq: Maximum daily trading frequency (will be estimated)
        
        Returns:
            Dict of wallet addresses to metadata
        """
        logger.info(f"Starting scrape of polymarketanalytics.com/traders")
        logger.info(f"Criteria: WR>={min_win_rate*100}%, trades {min_trades}-{max_trades}, daily<={max_daily_freq}")
        
        # Try direct API fetch first (Вариант A)
        logger.info("Attempting direct API access (Вариант A)...")
        try:
            from fetch_polymarket_analytics_api import fetch_traders_from_api
            api_addresses = fetch_traders_from_api(target=2000)
            if api_addresses:
                logger.info(f"✅ Got {len(api_addresses)} addresses via direct API")
                # Add addresses to wallets (they will be analyzed later)
                for addr in api_addresses:
                    addr_lower = addr.lower()
                    if addr_lower not in self.wallets:
                        self.wallets[addr_lower] = {
                            'display': addr_lower,
                            'source': 'polymarket_analytics_api',
                            'total_positions': 0,
                            'win_rate': 0.0,
                            'daily_freq_estimate': 0.0
                        }
                # If we got addresses via API, we're done
                if api_addresses:
                    logger.info(f"✅ Found {len(self.wallets)} wallets via API")
                    return self.wallets
        except Exception as e:
            logger.debug(f"Direct API failed: {e}, trying Playwright...")
        
        # Fallback to Playwright if direct API didn't work
        if not self.wallets:
            # Fallback to HTML scraping (with Playwright if available)
            if PLAYWRIGHT_AVAILABLE:
                logger.info("No API found, using Playwright for JavaScript rendering...")
                asyncio.run(self._scrape_with_playwright(max_pages, min_win_rate, min_trades, max_trades, max_daily_freq))
            else:
                logger.info("No API found, falling back to HTML scraping...")
                self._scrape_html(max_pages, min_win_rate, min_trades, max_trades, max_daily_freq)
        
        logger.info(f"✅ Found {len(self.wallets)} wallets matching criteria")
        return self.wallets
    
    def _process_api_data(self, data: Dict, min_win_rate: float, min_trades: int, 
                         max_trades: int, max_daily_freq: float):
        """Process data from API response"""
        # Handle different possible API response structures
        traders = []
        if isinstance(data, list):
            traders = data
        elif isinstance(data, dict):
            traders = data.get('traders', data.get('data', data.get('results', [])))
        
        for trader in traders:
            try:
                address = self._extract_address(trader)
                if not address:
                    continue
                
                # Extract metrics
                total_positions = trader.get('totalPositions', trader.get('total_positions', 
                                trader.get('positions', trader.get('trades', 0))))
                win_rate = trader.get('winRate', trader.get('win_rate', 0))
                # Convert percentage to decimal if needed
                if isinstance(win_rate, str):
                    win_rate = float(win_rate.replace('%', '')) / 100.0
                elif win_rate > 1.0:
                    win_rate = win_rate / 100.0
                
                # Estimate daily frequency (rough estimate: assume trading started ~1 year ago)
                # This is a rough estimate since we don't have exact dates
                days_estimate = 365  # Assume 1 year of trading
                daily_freq = float(total_positions) / days_estimate if days_estimate > 0 else 0
                
                # Filter by criteria
                if (total_positions >= min_trades and 
                    total_positions <= max_trades and
                    win_rate >= min_win_rate and
                    daily_freq <= max_daily_freq):
                    
                    self.wallets[address.lower()] = {
                        'display': trader.get('username', trader.get('name', address)),
                        'total_positions': total_positions,
                        'win_rate': win_rate,
                        'daily_freq_estimate': daily_freq,
                        'pnl': trader.get('pnl', trader.get('overallPnL', 0)),
                        'source': 'polymarket_analytics_api'
                    }
                    
            except Exception as e:
                logger.debug(f"Error processing trader: {e}")
                continue
    
    async def _scrape_with_playwright(self, max_pages: int, min_win_rate: float, min_trades: int,
                                     max_trades: int, max_daily_freq: float):
        """Scrape using Playwright to render JavaScript"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            # Intercept network requests to find API endpoints
            api_responses = []
            
            async def handle_response(response):
                url = response.url
                # Capture any JSON responses from the domain
                if 'polymarketanalytics.com' in url:
                    try:
                        content_type = response.headers.get('content-type', '')
                        if 'json' in content_type.lower() and response.status == 200:
                            data = await response.json()
                            # Check if it looks like trader data
                            is_trader_data = False
                            if isinstance(data, list) and len(data) > 0:
                                sample = data[0] if isinstance(data[0], dict) else {}
                                if any(k in sample for k in ['address', 'wallet', 'trader', 'id']):
                                    is_trader_data = True
                            elif isinstance(data, dict):
                                for key in ['traders', 'data', 'results', 'items', 'leaderboard']:
                                    if key in data and isinstance(data[key], list) and len(data[key]) > 0:
                                        is_trader_data = True
                                        break
                            
                            if is_trader_data or 'trader' in url.lower() or '/api/' in url:
                                api_responses.append((url, data))
                                logger.info(f"  🔍 Found API response: {url}")
                    except Exception as e:
                        logger.debug(f"  Error reading response from {url}: {e}")
            
            page.on("response", handle_response)
            
            try:
                for page_num in range(1, max_pages + 1):
                    url = f"{self.base_url}/traders"
                    if page_num > 1:
                        url = f"{url}?page={page_num}"
                    
                    logger.info(f"Scraping page {page_num} with Playwright: {url}")
                    
                    try:
                        # Wait for page to load
                        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        await page.wait_for_timeout(5000)  # Wait for JS to load
                        
                        # Wait for table or data to appear
                        try:
                            await page.wait_for_selector('table, [data-testid*="trader"], .trader-row, a[href*="/traders/"]', timeout=10000)
                            logger.info("  ✓ Data loaded")
                        except:
                            logger.warning("  ⚠ No trader elements found, but continuing...")
                        
                        # Try to extract data from the rendered page
                        page_content = await page.content()
                        soup = BeautifulSoup(page_content, 'html.parser')
                        
                        # Extract __NEXT_DATA__
                        scripts = soup.find_all('script', id='__NEXT_DATA__')
                        if scripts:
                            try:
                                json_data = json.loads(scripts[0].string)
                                logger.info("  ✓ Found __NEXT_DATA__")
                                self._extract_from_nextjs_data(json_data, min_win_rate, min_trades, max_trades, max_daily_freq)
                            except Exception as e:
                                logger.debug(f"  Error parsing __NEXT_DATA__: {e}")
                        
                        # Extract all wallet addresses from the page
                        page_text = await page.content()
                        # Find all Ethereum addresses
                        addresses = set(re.findall(r'0x[a-fA-F0-9]{40}', page_text))
                        logger.info(f"  ✓ Found {len(addresses)} unique addresses on page")
                        
                        # Add addresses to wallets (they will be filtered later by our analyzer)
                        for addr in addresses:
                            addr_lower = addr.lower()
                            if addr_lower not in self.wallets:
                                self.wallets[addr_lower] = {
                                    'display': addr_lower,
                                    'source': 'polymarket_analytics_page',
                                    'total_positions': 0,  # Will be filled by analyzer
                                    'win_rate': 0.0,  # Will be filled by analyzer
                                    'daily_freq_estimate': 0.0  # Will be filled by analyzer
                                }
                        
                        # Also try to intercept network requests
                        # Look for API calls
                        try:
                            # Try to evaluate JavaScript to get data
                            traders_data = await page.evaluate("""
                                () => {
                                    // Try common data structures
                                    if (window.__NEXT_DATA__) {
                                        return window.__NEXT_DATA__.props.pageProps;
                                    }
                                    if (window.__DATA__) {
                                        return window.__DATA__;
                                    }
                                    if (window.traders) {
                                        return {traders: window.traders};
                                    }
                                    return null;
                                }
                            """)
                            
                            if traders_data:
                                self._extract_from_nextjs_data(traders_data, min_win_rate, min_trades, max_trades, max_daily_freq)
                        except Exception as e:
                            logger.debug(f"JavaScript evaluation failed: {e}")
                        
                        # Try to extract from table if visible
                        self._parse_html_table(soup, min_win_rate, min_trades, max_trades, max_daily_freq)
                        
                        # Process any API responses we intercepted
                        if api_responses:
                            logger.info(f"  📡 Processing {len(api_responses)} API responses...")
                            for api_url, api_data in api_responses:
                                try:
                                    self._process_api_data(api_data, min_win_rate, min_trades, max_trades, max_daily_freq)
                                except Exception as e:
                                    logger.debug(f"  Error processing API data from {api_url}: {e}")
                            api_responses.clear()  # Clear for next page
                        
                        # Check for pagination
                        if not await self._check_next_page_playwright(page):
                            logger.info("Reached last page")
                            break
                        
                        await asyncio.sleep(2)  # Rate limiting
                        
                    except PlaywrightTimeout:
                        logger.warning(f"Timeout loading page {page_num}")
                        break
                    except Exception as e:
                        logger.error(f"Error scraping page {page_num}: {e}")
                        break
                        
            finally:
                await browser.close()
    
    async def _check_next_page_playwright(self, page) -> bool:
        """Check if there's a next page using Playwright"""
        try:
            # Look for next button or pagination
            next_button = await page.query_selector('button:has-text("Next"), a:has-text("Next"), [aria-label*="next" i]')
            if next_button:
                return True
            return False
        except:
            return False
    
    def _scrape_html(self, max_pages: int, min_win_rate: float, min_trades: int,
                    max_trades: int, max_daily_freq: float):
        """Scrape trader data from HTML pages"""
        for page in range(1, max_pages + 1):
            try:
                url = f"{self.base_url}/traders"
                if page > 1:
                    url = f"{url}?page={page}"
                
                logger.info(f"Scraping page {page}: {url}")
                response = self.session.get(url, timeout=15)
                
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch page {page}: {response.status_code}")
                    break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Try to extract JSON data from script tags (common in React apps)
                scripts = soup.find_all('script')
                json_data = None
                for script in scripts:
                    if script.string and '__NEXT_DATA__' in script.string:
                        try:
                            json_data = json.loads(script.string)
                            break
                        except:
                            pass
                
                if json_data:
                    self._extract_from_nextjs_data(json_data, min_win_rate, min_trades, max_trades, max_daily_freq)
                
                # Also try to parse table HTML if it exists
                self._parse_html_table(soup, min_win_rate, min_trades, max_trades, max_daily_freq)
                
                # Check if we've reached the end
                if not self._has_more_pages(soup):
                    logger.info("Reached last page")
                    break
                
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error scraping page {page}: {e}")
                break
    
    def _extract_from_nextjs_data(self, data: Dict, min_win_rate: float, min_trades: int,
                                  max_trades: int, max_daily_freq: float):
        """Extract trader data from Next.js __NEXT_DATA__"""
        try:
            props = data.get('props', {})
            page_props = props.get('pageProps', {})
            
            # Common structures in Next.js apps
            traders = page_props.get('traders', page_props.get('data', page_props.get('leaderboard', [])))
            
            if traders:
                logger.info(f"Found {len(traders)} traders in Next.js data")
                self._process_traders_list(traders, min_win_rate, min_trades, max_trades, max_daily_freq)
        except Exception as e:
            logger.debug(f"Error extracting from Next.js data: {e}")
    
    def _parse_html_table(self, soup: BeautifulSoup, min_win_rate: float, min_trades: int,
                         max_trades: int, max_daily_freq: float):
        """Parse trader data from HTML table"""
        # Look for table with trader data
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')[1:]  # Skip header
            for row in rows:
                try:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) < 3:
                        continue
                    
                    # Find wallet address link
                    address = None
                    for cell in cells:
                        link = cell.find('a', href=True)
                        if link:
                            href = link.get('href', '')
                            # Extract address from /traders/0x... or /profile/0x...
                            match = re.search(r'0x[a-fA-F0-9]{40}', href)
                            if match:
                                address = match.group(0).lower()
                                break
                    
                    if not address:
                        continue
                    
                    # Try to extract metrics from cells
                    # This is fragile and depends on table structure
                    # Adjust based on actual HTML structure
                    total_positions = self._extract_number_from_cell(cells, 'Total Positions')
                    win_rate_pct = self._extract_number_from_cell(cells, 'Win Rate')
                    
                    if win_rate_pct:
                        win_rate = win_rate_pct / 100.0 if win_rate_pct > 1.0 else win_rate_pct
                    else:
                        continue
                    
                    # Estimate daily frequency
                    days_estimate = 365
                    daily_freq = float(total_positions) / days_estimate if total_positions else 0
                    
                    # Filter
                    if (total_positions and total_positions >= min_trades and 
                        total_positions <= max_trades and
                        win_rate >= min_win_rate and
                        daily_freq <= max_daily_freq):
                        
                        self.wallets[address] = {
                            'display': address,
                            'total_positions': total_positions,
                            'win_rate': win_rate,
                            'daily_freq_estimate': daily_freq,
                            'source': 'polymarket_analytics_html'
                        }
                        
                except Exception as e:
                    logger.debug(f"Error parsing table row: {e}")
                    continue
    
    def _process_traders_list(self, traders: List[Dict], min_win_rate: float, min_trades: int,
                             max_trades: int, max_daily_freq: float):
        """Process a list of trader objects"""
        for trader in traders:
            try:
                address = self._extract_address(trader)
                if not address:
                    continue
                
                total_positions = trader.get('totalPositions', trader.get('total_positions', 
                                trader.get('positions', trader.get('trades', 0))))
                
                win_rate = trader.get('winRate', trader.get('win_rate', 0))
                if isinstance(win_rate, str):
                    win_rate = float(win_rate.replace('%', '').replace(',', '')) / 100.0
                elif win_rate > 1.0:
                    win_rate = win_rate / 100.0
                
                days_estimate = 365
                daily_freq = float(total_positions) / days_estimate if total_positions else 0
                
                if (total_positions and total_positions >= min_trades and 
                    total_positions <= max_trades and
                    win_rate >= min_win_rate and
                    daily_freq <= max_daily_freq):
                    
                    self.wallets[address.lower()] = {
                        'display': trader.get('username', trader.get('name', trader.get('trader', address))),
                        'total_positions': total_positions,
                        'win_rate': win_rate,
                        'daily_freq_estimate': daily_freq,
                        'pnl': trader.get('pnl', trader.get('overallPnL', trader.get('overall_pnl', 0))),
                        'source': 'polymarket_analytics'
                    }
                    
            except Exception as e:
                logger.debug(f"Error processing trader: {e}")
                continue
    
    def _extract_address(self, trader: Dict) -> Optional[str]:
        """Extract wallet address from trader object"""
        # Try different possible field names
        for key in ['address', 'wallet', 'walletAddress', 'wallet_address', 
                   'id', 'trader', 'user', 'account']:
            value = trader.get(key)
            if value and isinstance(value, str) and re.match(r'^0x[a-fA-F0-9]{40}$', value):
                return value.lower()
        
        # Also check if it's in a nested structure
        if 'profile' in trader:
            return self._extract_address(trader['profile'])
        
        return None
    
    def _extract_number_from_cell(self, cells: List, label: str) -> Optional[int]:
        """Extract number from table cell (helper for HTML parsing)"""
        # This is a simple helper - adjust based on actual table structure
        for cell in cells:
            text = cell.get_text(strip=True)
            # Try to find number
            numbers = re.findall(r'[\d,]+', text)
            if numbers:
                try:
                    return int(numbers[0].replace(',', ''))
                except:
                    pass
        return None
    
    def _has_more_pages(self, soup: BeautifulSoup) -> bool:
        """Check if there are more pages to scrape"""
        # Look for pagination indicators
        pagination = soup.find_all(class_=re.compile(r'pagination|next|more', re.I))
        if pagination:
            return True
        return False


if __name__ == "__main__":
    scraper = PolymarketAnalyticsScraper()
    wallets = scraper.scrape_traders(
        max_pages=20,
        min_win_rate=0.75,
        min_trades=6,
        max_trades=1000,
        max_daily_freq=20.0
    )
    
    print(f"\n✅ Found {len(wallets)} wallets matching criteria:\n")
    for addr, data in list(wallets.items())[:10]:
        print(f"{addr[:10]}...{addr[-8:]}: WR={data['win_rate']:.1%}, "
              f"Trades={data['total_positions']}, Daily≈{data['daily_freq_estimate']:.1f}")

