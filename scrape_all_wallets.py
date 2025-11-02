#!/usr/bin/env python3
"""
Test script to scrape ALL wallets from Polymarket leaderboards
Try to get 120+ wallets from 40+ pages without filtering
"""

import asyncio
import logging
from fetch_leaderboards import scrape_polymarket_leaderboards

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def scrape_all_wallets():
    """Scrape all possible wallets from leaderboards"""
    logger.info("Starting comprehensive wallet scraping...")
    
    # Try different leaderboard URLs to maximize coverage
    leaderboard_urls = [
        "https://polymarket.com/leaderboard/overall/today/profit",
        "https://polymarket.com/leaderboard/overall/weekly/profit",
        "https://polymarket.com/leaderboard/overall/monthly/profit",
        "https://polymarket.com/leaderboard/overall/alltime/profit",
        "https://polymarket.com/leaderboard/overall/today/volume",
        "https://polymarket.com/leaderboard/overall/weekly/volume",
        "https://polymarket.com/leaderboard/overall/monthly/volume"
    ]
    
    all_wallets = {}
    
    for url in leaderboard_urls:
        try:
            logger.info(f"Scraping {url}...")
            wallets = await scrape_polymarket_leaderboards([url], headless=True)
            
            logger.info(f"Found {len(wallets)} wallets from {url}")
            
            # Add to collection
            for addr, info in wallets.items():
                if addr not in all_wallets:
                    all_wallets[addr] = info
                else:
                    # Update source to include multiple sources
                    existing_sources = all_wallets[addr]['source']
                    if url not in existing_sources:
                        all_wallets[addr]['source'] = f"{existing_sources}, {url}"
            
            logger.info(f"Total unique wallets so far: {len(all_wallets)}")
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            continue
    
    logger.info(f"Scraping complete! Total unique wallets: {len(all_wallets)}")
    
    # Show sample of wallets
    logger.info("Sample wallets found:")
    for i, (addr, info) in enumerate(list(all_wallets.items())[:10]):
        logger.info(f"  {i+1}. {addr} - {info['display']} (from {info['source']})")
    
    if len(all_wallets) > 10:
        logger.info(f"  ... and {len(all_wallets) - 10} more")
    
    return all_wallets

if __name__ == "__main__":
    wallets = asyncio.run(scrape_all_wallets())
    print(f"\n🎉 FINAL RESULT: {len(wallets)} unique wallets found!")
    
    if len(wallets) >= 120:
        print("✅ SUCCESS: Found 120+ wallets as requested!")
    else:
        print(f"⚠️  Found {len(wallets)} wallets (target was 120+)")
