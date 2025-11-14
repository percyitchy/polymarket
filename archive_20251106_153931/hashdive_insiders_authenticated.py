#!/usr/bin/env python3
"""
HashDive Insiders Scraper with Authentication
Scrapes whale trades data from https://hashdive.com/Insiders after login
"""

import asyncio
import json
from playwright.async_api import async_playwright
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv
from datetime import datetime


# Load environment variables
load_dotenv()


class HashDiveAuthenticatedScraper:
    def __init__(self, email: Optional[str] = None, password: Optional[str] = None):
        self.url = "https://hashdive.com/Insiders"
        self.email = email or os.getenv("HASHDIVE_EMAIL")
        self.password = password or os.getenv("HASHDIVE_PASSWORD")
        self.data = {
            "whale_trades": [],
            "whale_holders": [],
            "timestamp": datetime.now().isoformat()
        }
    
    async def login(self, page):
        """Login to HashDive"""
        try:
            print("Attempting to login...")
            
            # Look for login button/link
            # Common Streamlit login button selectors
            login_selectors = [
                'a[href*="login"]',
                'button:has-text("Log in")',
                '[data-testid*="login"]',
                '.stButton button',
                'text="Log in"'
            ]
            
            for selector in login_selectors:
                try:
                    login_element = await page.wait_for_selector(selector, timeout=3000)
                    if login_element:
                        await login_element.click()
                        print(f"Clicked login with selector: {selector}")
                        await asyncio.sleep(2)
                        break
                except:
                    continue
            
            # Wait for login form and fill it
            try:
                # Common login form selectors
                email_selectors = ['input[type="email"]', 'input[name="email"]', 'input[placeholder*="email" i]']
                password_selectors = ['input[type="password"]', 'input[name="password"]']
                
                for email_sel in email_selectors:
                    try:
                        email_input = await page.wait_for_selector(email_sel, timeout=2000)
                        if email_input:
                            await email_input.fill(self.email)
                            print("Entered email")
                            break
                    except:
                        continue
                
                for pwd_sel in password_selectors:
                    try:
                        pwd_input = await page.wait_for_selector(pwd_sel, timeout=2000)
                        if pwd_input:
                            await pwd_input.fill(self.password)
                            print("Entered password")
                            break
                    except:
                        continue
                
                # Look for submit button
                submit_selectors = [
                    'button[type="submit"]',
                    'button:has-text("Login")',
                    'button:has-text("Sign in")',
                    'button:has-text("Continue")'
                ]
                
                for submit_sel in submit_selectors:
                    try:
                        submit_btn = await page.wait_for_selector(submit_sel, timeout=2000)
                        if submit_btn:
                            await submit_btn.click()
                            print("Clicked submit")
                            await asyncio.sleep(3)
                            return True
                    except:
                        continue
                        
            except Exception as e:
                print(f"Error during login form filling: {e}")
                return False
            
            # Check if we're logged in by looking for account/user info
            await asyncio.sleep(3)
            
            # Take screenshot
            await page.screenshot(path="hashdive_login_screenshot.png")
            print("Login screenshot saved")
            
            return True
            
        except Exception as e:
            print(f"Login error: {e}")
            await page.screenshot(path="hashdive_login_error.png")
            return False
    
    async def scrape_table_data(self, page):
        """Scrape table data from the page"""
        try:
            print("Extracting table data...")
            
            # Wait for table to load
            await asyncio.sleep(5)
            
            # Try multiple table extraction strategies
            data = await page.evaluate("""
                () => {
                    const result = {
                        tables: [],
                        divs: []
                    };
                    
                    // Find all tables
                    document.querySelectorAll('table').forEach((table, idx) => {
                        const headers = Array.from(table.querySelectorAll('thead th, tbody tr:first-child th, thead tr th'))
                            .map(h => h.innerText.trim())
                            .filter(h => h);
                        
                        const rows = Array.from(table.querySelectorAll('tbody tr, table tr')).map(row => {
                            const cells = Array.from(row.querySelectorAll('td, th'));
                            return cells.map(cell => cell.innerText.trim()).filter(c => c);
                        }).filter(row => row.length > 0);
                        
                        result.tables.push({
                            index: idx,
                            headers: headers,
                            rows: rows.slice(0, 20) // Limit to 20 rows for now
                        });
                    });
                    
                    // Also try to get all text from data-grid or similar components
                    document.querySelectorAll('[role="grid"], [data-testid*="table"], .dataframe').forEach((grid, idx) => {
                        result.divs.push({
                            index: idx,
                            tag: grid.tagName,
                            className: grid.className,
                            innerHTML: grid.innerHTML.substring(0, 1000)
                        });
                    });
                    
                    return result;
                }
            """)
            
            return data
            
        except Exception as e:
            print(f"Error extracting table data: {e}")
            return None
    
    async def scrape_with_auth(self):
        """Main scraping function with authentication"""
        if not self.email or not self.password:
            print("❌ Error: Email and password required!")
            print("Please set HASHDIVE_EMAIL and HASHDIVE_PASSWORD in .env file")
            return None
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)  # Set to True to hide browser
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            page = await context.new_page()
            
            try:
                print(f"Loading page: {self.url}")
                await page.goto(self.url, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(3)
                
                # Take initial screenshot
                await page.screenshot(path="hashdive_before_login.png")
                print("Screenshot saved: hashdive_before_login.png")
                
                # Check if already logged in
                page_text = await page.evaluate("document.body.innerText")
                if "Log in" in page_text or "Log in" in page_text:
                    print("Not logged in, attempting login...")
                    await self.login(page)
                    await asyncio.sleep(3)
                else:
                    print("Already logged in or login not needed")
                
                # Navigate to Insiders page again if needed
                await page.goto(self.url, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(5)
                
                # Take screenshot after login
                await page.screenshot(path="hashdive_after_login.png")
                print("Screenshot saved: hashdive_after_login.png")
                
                # Get table data
                table_data = await self.scrape_table_data(page)
                
                # Final screenshot
                await page.screenshot(path="hashdive_final_state.png")
                print("Final screenshot saved")
                
                return table_data
                
            except Exception as e:
                print(f"Error during scraping: {e}")
                await page.screenshot(path="hashdive_error.png")
                return None
            
            finally:
                # Keep browser open for manual inspection
                print("\nBrowser will stay open for 30 seconds for inspection...")
                await asyncio.sleep(30)
                await browser.close()


async def main():
    print("=" * 60)
    print("HashDive Insiders Authenticated Scraper")
    print("=" * 60)
    
    scraper = HashDiveAuthenticatedScraper()
    data = await scraper.scrape_with_auth()
    
    if data:
        print("\n" + "=" * 60)
        print("Scraping completed!")
        print("=" * 60)
        print(json.dumps(data, indent=2))
        
        with open("hashdive_authenticated_data.json", "w") as f:
            json.dump(data, f, indent=2)
        print("\n✅ Data saved to hashdive_authenticated_data.json")
    else:
        print("\n❌ Scraping failed")


if __name__ == "__main__":
    asyncio.run(main())

