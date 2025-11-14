"""
Enhanced Polymarket Leaderboard Scraper
Uses requests + BeautifulSoup with pagination simulation
Scrapes multiple pages by simulating page requests
"""

import asyncio
import logging
import time
import requests
from typing import List, Dict, Set
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedPolymarketScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
    def scrape_leaderboard_pages(self, base_url: str, max_pages: int = 40) -> Dict[str, Dict[str, str]]:
        """
        Scrape multiple pages of leaderboard by simulating page requests
        """
        logger.info(f"Starting to scrape up to {max_pages} pages from: {base_url}")
        wallets = {}
        
        for page_num in range(1, max_pages + 1):
            try:
                # Try different URL patterns for pagination
                page_urls = [
                    f"{base_url}?page={page_num}",
                    f"{base_url}&page={page_num}",
                    f"{base_url}/page/{page_num}",
                    f"{base_url}?offset={(page_num-1)*20}",
                    f"{base_url}?offset={(page_num-1)*50}",
                ]
                
                page_wallets = {}
                for page_url in page_urls:
                    try:
                        logger.info(f"Trying page {page_num} with URL: {page_url}")
                        response = self.session.get(page_url, timeout=10)
                        response.raise_for_status()
                        
                        # Extract wallets from this page
                        page_wallets = self._extract_wallets_from_html(response.text)
                        
                        if page_wallets:
                            logger.info(f"Found {len(page_wallets)} wallets on page {page_num}")
                            break
                        else:
                            logger.debug(f"No wallets found with URL pattern: {page_url}")
                            
                    except Exception as e:
                        logger.debug(f"Failed to scrape {page_url}: {e}")
                        continue
                
                if not page_wallets:
                    logger.info(f"No wallets found on page {page_num}, stopping pagination")
                    break
                
                # Add wallets to collection
                for addr, display in page_wallets.items():
                    wallets[addr.lower()] = {
                        "display": display,
                        "source": base_url
                    }
                
                # Add delay between requests
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error scraping page {page_num}: {e}")
                continue
        
        logger.info(f"Completed scraping: found {len(wallets)} unique wallets")
        return wallets
    
    def _extract_wallets_from_html(self, html: str) -> Dict[str, str]:
        """Extract wallet addresses from HTML content"""
        wallets = {}
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for profile links
            profile_links = soup.find_all('a', href=True)
            
            for link in profile_links:
                href = link.get('href', '')
                if '/profile/' in href:
                    # Extract address from href
                    tail = href.split('/profile/')[-1]
                    tail = tail.split('?')[0].split('#')[0]  # Remove query params
                    
                    # Check if it's a valid Ethereum address
                    if self._is_valid_address(tail):
                        display_text = link.get_text(strip=True) or tail
                        wallets[tail.lower()] = display_text
            
            # Also look for wallet addresses in data attributes or other patterns
            # Some React apps might store data differently
            for element in soup.find_all(attrs={'data-wallet': True}):
                addr = element.get('data-wallet')
                if self._is_valid_address(addr):
                    display_text = element.get_text(strip=True) or addr
                    wallets[addr.lower()] = display_text
            
            # Look for wallet addresses in text content
            text_content = soup.get_text()
            wallet_pattern = r'0x[a-fA-F0-9]{40}'
            matches = re.findall(wallet_pattern, text_content)
            
            for match in matches:
                if self._is_valid_address(match):
                    wallets[match.lower()] = match
            
        except Exception as e:
            logger.warning(f"Error extracting wallets from HTML: {e}")
        
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
    
    def scrape_all_leaderboards(self, urls: List[str], max_pages_per_url: int = 40) -> Dict[str, Dict[str, str]]:
        """Scrape multiple leaderboard URLs"""
        all_wallets = {}
        
        for url in urls:
            try:
                wallets = self.scrape_leaderboard_pages(url, max_pages_per_url)
                all_wallets.update(wallets)
                logger.info(f"Total wallets collected so far: {len(all_wallets)}")
            except Exception as e:
                logger.error(f"Failed to scrape {url}: {e}")
                continue
        
        logger.info(f"Scraping complete. Total unique wallets: {len(all_wallets)}")
        return all_wallets

def scrape_polymarket_leaderboards_enhanced(urls: List[str], max_pages_per_url: int = 40) -> Dict[str, Dict[str, str]]:
    """
    Enhanced leaderboard scraping function
    
    Args:
        urls: List of leaderboard URLs to scrape
        max_pages_per_url: Maximum pages to scrape per URL
        
    Returns:
        Dict of {address: {display, source}}
    """
    scraper = EnhancedPolymarketScraper()
    return scraper.scrape_all_leaderboards(urls, max_pages_per_url)

# Example usage
if __name__ == "__main__":
    # Default leaderboard URLs
    leaderboard_urls = [
        "https://polymarket.com/leaderboard/overall/monthly/profit",
        "https://polymarket.com/leaderboard/overall/weekly/profit", 
        "https://polymarket.com/leaderboard/overall/today/profit"
    ]
    
    wallets = scrape_polymarket_leaderboards_enhanced(leaderboard_urls, max_pages_per_url=30)
    print(f"\nScraped {len(wallets)} unique wallets:")
    for addr, info in list(wallets.items())[:10]:  # Show first 10
        print(f"  {addr} - {info['display']} (from {info['source']})")
    if len(wallets) > 10:
        print(f"  ... and {len(wallets) - 10} more")
