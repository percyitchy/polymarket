#!/usr/bin/env python3
"""
HashDive Insiders Scraper
Scrapes whale trades and holder data from https://hashdive.com/Insiders
"""

import asyncio
import json
from playwright.async_api import async_playwright
from typing import List, Dict, Any
import time
from datetime import datetime


class HashDiveInsidersScraper:
    def __init__(self):
        self.url = "https://hashdive.com/Insiders"
        self.data = {
            "whale_trades": [],
            "whale_holders": []
        }
    
    async def scrape_page(self, page, page_type="trades"):
        """Scrape data from the page after it's loaded"""
        try:
            # Wait for the table to load
            await page.wait_for_selector("table", timeout=30000)
            
            # Wait a bit more for data to populate
            await asyncio.sleep(3)
            
            # Try to get the table data
            table_data = await page.evaluate("""
                () => {
                    const tables = document.querySelectorAll('table');
                    const results = [];
                    
                    tables.forEach((table, index) => {
                        const rows = Array.from(table.querySelectorAll('tbody tr'));
                        const rowsData = rows.map(row => {
                            const cells = Array.from(row.querySelectorAll('td, th'));
                            return cells.map(cell => cell.innerText.trim());
                        });
                        results.push({tableIndex: index, rows: rowsData});
                    });
                    
                    return results;
                }
            """)
            
            return table_data
            
        except Exception as e:
            print(f"Error scraping page: {e}")
            # Try to get screenshot for debugging
            await page.screenshot(path="hashdive_debug.png")
            return None
    
    async def scrape_insiders(self):
        """Main scraping function"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()
            
            print(f"Loading page: {self.url}")
            try:
                await page.goto(self.url, wait_until="networkidle", timeout=60000)
                print("Page loaded, extracting data...")
                
                # Wait for Streamlit to fully render
                await asyncio.sleep(5)
                
                # Take screenshot to see what's rendered
                await page.screenshot(path="hashdive_insiders_screenshot.png")
                print("Screenshot saved to hashdive_insiders_screenshot.png")
                
                # Try to get all text content
                content = await page.evaluate("""
                    () => {
                        return {
                            title: document.title,
                            text: document.body.innerText,
                            tables: document.querySelectorAll('table').length
                        };
                    }
                """)
                print(f"Page title: {content['title']}")
                print(f"Number of tables: {content['tables']}")
                print(f"Text content (first 1000 chars):\n{content['text'][:1000]}")
                
                # Try to find specific elements
                elements = await page.evaluate("""
                    () => {
                        const result = {};
                        
                        // Find all data-testid attributes
                        const testIds = Array.from(document.querySelectorAll('[data-testid]'));
                        result.testIds = testIds.map(el => ({
                            testid: el.getAttribute('data-testid'),
                            text: el.innerText,
                            tag: el.tagName
                        }));
                        
                        // Find all tables
                        const tables = Array.from(document.querySelectorAll('table'));
                        result.tables = [];
                        tables.forEach((table, idx) => {
                            const headers = Array.from(table.querySelectorAll('th')).map(h => h.innerText);
                            const rows = Array.from(table.querySelectorAll('tbody tr'));
                            const rowsData = rows.slice(0, 5).map(row => {
                                return Array.from(row.querySelectorAll('td')).map(cell => cell.innerText.trim());
                            });
                            result.tables.push({
                                index: idx,
                                headers: headers,
                                sampleRows: rowsData
                            });
                        });
                        
                        return result;
                    }
                """)
                
                print("\nFound elements:")
                print(json.dumps(elements, indent=2))
                
                # Try to scroll to load more data
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                
                # Get final screenshot
                await page.screenshot(path="hashdive_insiders_full.png")
                
            except Exception as e:
                print(f"Error loading page: {e}")
            
            finally:
                await browser.close()
        
        return self.data
    
    def parse_whale_data(self, raw_data):
        """Parse and structure the whale data"""
        # This will be customized based on actual page structure
        parsed = {
            "whale_trades": [],
            "whale_holders": [],
            "timestamp": datetime.now().isoformat()
        }
        
        # TODO: Add parsing logic based on actual page structure
        return parsed


async def main():
    print("=" * 60)
    print("HashDive Insiders Scraper")
    print("=" * 60)
    
    scraper = HashDiveInsidersScraper()
    data = await scraper.scrape_insiders()
    
    print("\n" + "=" * 60)
    print("Scraping completed!")
    print("=" * 60)
    print(f"\nData structure:")
    print(json.dumps(data, indent=2))
    
    # Save to file
    with open("hashdive_insiders_data.json", "w") as f:
        json.dump(data, f, indent=2)
    print("\n✅ Data saved to hashdive_insiders_data.json")
    print("✅ Screenshots saved to:")
    print("   - hashdive_insiders_screenshot.png")
    print("   - hashdive_insiders_full.png")


if __name__ == "__main__":
    asyncio.run(main())

