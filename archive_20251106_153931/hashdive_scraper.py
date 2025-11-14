#!/usr/bin/env python3
"""
HashDive Insiders Scraper with command line arguments
Usage: python3 hashdive_scraper.py --email your@email.com --password yourpass
"""

import asyncio
import json
import sys
import argparse
from playwright.async_api import async_playwright
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()


async def scrape_hashdive(email: str, password: str):
    """Scrape HashDive Insiders page"""
    
    print("=" * 60)
    print("HashDive Insiders Scraper")
    print("=" * 60)
    print(f"\nEmail: {email}")
    print("Password: ***\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        try:
            print("Loading HashDive...")
            await page.goto("https://hashdive.com", wait_until="networkidle", timeout=60000)
            await asyncio.sleep(3)
            
            await page.screenshot(path="01_before_login.png")
            print("✓ Screenshot: 01_before_login.png")
            
            # Find and click login
            print("\nLooking for login...")
            try:
                login_btn = await page.wait_for_selector('text="Log in"', timeout=5000)
                await login_btn.click()
                print("✓ Clicked 'Log in'")
                await asyncio.sleep(2)
            except:
                print("⚠ Couldn't find 'Log in', trying other methods...")
            
            await page.screenshot(path="02_login_form.png")
            
            # Fill email
            for selector in ['input[type="email"]', 'input[name="email"]']:
                try:
                    email_input = await page.wait_for_selector(selector, timeout=2000)
                    await email_input.fill(email)
                    print("✓ Entered email")
                    await asyncio.sleep(1)
                    break
                except:
                    continue
            
            # Fill password
            for selector in ['input[type="password"]', 'input[name="password"]']:
                try:
                    pwd_input = await page.wait_for_selector(selector, timeout=2000)
                    await pwd_input.fill(password)
                    print("✓ Entered password")
                    await asyncio.sleep(1)
                    break
                except:
                    continue
            
            await page.screenshot(path="03_form_filled.png")
            
            # Click submit
            for selector in ['button[type="submit"]', 'button:has-text("Login")', 'button:has-text("Sign in")']:
                try:
                    submit = await page.wait_for_selector(selector, timeout=2000)
                    await submit.click()
                    print("✓ Clicked submit")
                    await asyncio.sleep(5)
                    break
                except:
                    continue
            
            await page.screenshot(path="04_after_submit.png")
            
            print("\n⏳ Waiting 5 seconds, then navigating to Insiders...")
            await asyncio.sleep(5)
            
            await page.goto("https://hashdive.com/Insiders", wait_until="networkidle", timeout=60000)
            await asyncio.sleep(5)
            
            await page.screenshot(path="05_insiders_page.png")
            
            # Extract data
            print("\nExtracting data...")
            data = await page.evaluate("""
                () => {
                    const result = {tables: [], text: document.body.innerText.substring(0, 2000)};
                    
                    document.querySelectorAll('table').forEach((table, idx) => {
                        const headers = Array.from(table.querySelectorAll('thead th, thead tr th, tbody th'))
                            .map(h => h.innerText.trim());
                        
                        const rows = Array.from(table.querySelectorAll('tbody tr')).map(row => {
                            const cells = Array.from(row.querySelectorAll('td, th'));
                            return cells.map(cell => cell.innerText.trim());
                        });
                        
                        result.tables.push({index: idx, headers: headers, rows: rows.slice(0, 50)});
                    });
                    
                    return result;
                }
            """)
            
            await page.screenshot(path="06_final.png")
            
            print(f"\n✅ Found {len(data['tables'])} tables")
            return data
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            await page.screenshot(path="error.png")
            raise
        finally:
            print("\n⏳ Browser will stay open for 20 seconds for inspection...")
            await asyncio.sleep(20)
            await browser.close()


def main():
    parser = argparse.ArgumentParser(description='HashDive Insiders Scraper')
    parser.add_argument('--email', help='HashDive email', default=os.getenv('HASHDIVE_EMAIL'))
    parser.add_argument('--password', help='HashDive password', default=os.getenv('HASHDIVE_PASSWORD'))
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    
    args = parser.parse_args()
    
    if not args.email or not args.password:
        print("❌ Email and password required!")
        print("\nUsage:")
        print("  python3 hashdive_scraper.py --email your@email.com --password yourpass")
        print("\nOr set in .env file:")
        print("  HASHDIVE_EMAIL=your@email.com")
        print("  HASHDIVE_PASSWORD=yourpass")
        sys.exit(1)
    
    data = asyncio.run(scrape_hashdive(args.email, args.password))
    
    if data:
        with open("hashdive_data.json", "w") as f:
            json.dump(data, f, indent=2)
        
        print("\n✅ Data saved to hashdive_data.json")
        print(f"✅ Tables: {len(data['tables'])}")
        
        if data['tables']:
            for table in data['tables']:
                print(f"\nTable {table['index']}: {len(table['rows'])} rows")
                if table['rows']:
                    print(f"First row: {table['rows'][0]}")


if __name__ == "__main__":
    main()

