#!/usr/bin/env python3
"""
Interactive HashDive Insiders Scraper
Allows login via command line or env file
"""

import asyncio
import json
import sys
from playwright.async_api import async_playwright
from datetime import datetime


async def scrape_hashdive(email: str, password: str):
    """Scrape HashDive Insiders page"""
    
    print("=" * 60)
    print("HashDive Insiders Scraper")
    print("=" * 60)
    print(f"\nEmail: {email}")
    print("Password: ***\n")
    
    async with async_playwright() as p:
        # Launch browser in visible mode so you can see what's happening
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        try:
            print("Loading HashDive login page...")
            await page.goto("https://hashdive.com", wait_until="networkidle", timeout=60000)
            await asyncio.sleep(2)
            
            # Look for login link/button
            print("\nLooking for login button...")
            await page.screenshot(path="01_before_login.png")
            
            # Try to find and click login
            login_found = False
            try:
                # Common login selectors
                login_button = await page.wait_for_selector('text="Log in"', timeout=5000)
                if login_button:
                    await login_button.click()
                    print("✓ Found and clicked 'Log in' button")
                    login_found = True
                    await asyncio.sleep(3)
            except:
                print("Could not find 'Log in' text, trying other selectors...")
            
            if not login_found:
                try:
                    account_dropdown = await page.wait_for_selector('button', timeout=3000)
                    await account_dropdown.click()
                    print("✓ Clicked account dropdown")
                    await asyncio.sleep(2)
                except:
                    pass
            
            await page.screenshot(path="02_login_form.png")
            
            print("\nAttempting to fill login form...")
            
            # Try to find and fill email field
            email_filled = False
            for selector in ['input[type="email"]', 'input[name="email"]', 'input[placeholder*="email" i]', 'input[id*="email"]']:
                try:
                    email_input = await page.wait_for_selector(selector, timeout=2000)
                    if email_input:
                        await email_input.fill(email)
                        print(f"✓ Entered email using selector: {selector}")
                        email_filled = True
                        await asyncio.sleep(1)
                        break
                except:
                    continue
            
            # Try to find and fill password field
            password_filled = False
            for selector in ['input[type="password"]', 'input[name="password"]', 'input[placeholder*="password" i]', 'input[id*="password"]']:
                try:
                    password_input = await page.wait_for_selector(selector, timeout=2000)
                    if password_input:
                        await password_input.fill(password)
                        print(f"✓ Entered password using selector: {selector}")
                        password_filled = True
                        await asyncio.sleep(1)
                        break
                except:
                    continue
            
            await page.screenshot(path="03_form_filled.png")
            
            # Try to find and click submit button
            submit_found = False
            for selector in [
                'button[type="submit"]',
                'button:has-text("Login")',
                'button:has-text("Sign in")',
                'button:has-text("Continue")',
                'button:has-text("Submit")',
                'input[type="submit"]'
            ]:
                try:
                    submit_btn = await page.wait_for_selector(selector, timeout=2000)
                    if submit_btn:
                        await submit_btn.click()
                        print(f"✓ Clicked submit button using selector: {selector}")
                        submit_found = True
                        await asyncio.sleep(5)
                        break
                except:
                    continue
            
            await page.screenshot(path="04_after_submit.png")
            
            if not submit_found:
                print("\n⚠️ Could not find submit button automatically")
                print("Please manually click the login/submit button in the browser")
                print("Waiting 30 seconds for manual login...")
                await asyncio.sleep(30)
            
            # Navigate to Insiders page
            print("\nNavigating to Insiders page...")
            await page.goto("https://hashdive.com/Insiders", wait_until="networkidle", timeout=60000)
            await asyncio.sleep(5)
            
            await page.screenshot(path="05_insiders_page.png")
            
            # Extract data
            print("\nExtracting data...")
            data = await page.evaluate("""
                () => {
                    const result = {
                        tables: [],
                        text: document.body.innerText.substring(0, 2000),
                        elements: []
                    };
                    
                    // Find all tables
                    document.querySelectorAll('table').forEach((table, idx) => {
                        const headers = Array.from(table.querySelectorAll('thead th, thead tr th, tbody th'))
                            .map(h => h.innerText.trim());
                        
                        const rows = Array.from(table.querySelectorAll('tbody tr')).map(row => {
                            const cells = Array.from(row.querySelectorAll('td, th'));
                            return cells.map(cell => cell.innerText.trim());
                        });
                        
                        result.tables.push({
                            index: idx,
                            headers: headers,
                            rows: rows.slice(0, 50) // First 50 rows
                        });
                    });
                    
                    return result;
                }
            """)
            
            await page.screenshot(path="06_final.png")
            
            print("\n✅ Scraping completed!")
            print(f"\nFound {len(data['tables'])} tables")
            
            return data
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            await page.screenshot(path="error.png")
            raise
        finally:
            print("\nClosing browser in 10 seconds...")
            await asyncio.sleep(10)
            await browser.close()


def main():
    print("\n🚀 HashDive Insiders Scraper\n")
    
    # Get credentials
    email = input("Enter your HashDive email: ").strip()
    password = input("Enter your HashDive password: ").strip()
    
    if not email or not password:
        print("❌ Email and password are required!")
        sys.exit(1)
    
    # Run the scraper
    data = asyncio.run(scrape_hashdive(email, password))
    
    if data:
        # Save data
        with open("hashdive_data.json", "w") as f:
            json.dump(data, f, indent=2)
        
        print("\n✅ Data saved to hashdive_data.json")
        print(f"✅ Screenshots saved as 01_*.png, 02_*.png, etc.")
        
        # Print summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Text content (first 500 chars):")
        print(data['text'][:500])
        print(f"\nTables found: {len(data['tables'])}")
        
        for table in data['tables']:
            print(f"\nTable {table['index']}: {len(table['rows'])} rows")
            if table['rows']:
                print(f"Sample row: {table['rows'][0]}")


if __name__ == "__main__":
    main()

