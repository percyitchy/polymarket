#!/usr/bin/env python3
"""
Test script for Polymarket Notifier Bot
Verifies installation and basic functionality
"""

import sys
import os
import asyncio
from pathlib import Path

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    
    try:
        import requests
        print("✓ requests")
    except ImportError as e:
        print(f"✗ requests: {e}")
        return False
    
    try:
        import playwright
        print("✓ playwright")
    except ImportError as e:
        print(f"✗ playwright: {e}")
        return False
    
    try:
        from playwright.async_api import async_playwright
        print("✓ playwright.async_api")
    except ImportError as e:
        print(f"✗ playwright.async_api: {e}")
        return False
    
    try:
        import sqlite3
        print("✓ sqlite3")
    except ImportError as e:
        print(f"✗ sqlite3: {e}")
        return False
    
    try:
        from dotenv import load_dotenv
        print("✓ python-dotenv")
    except ImportError as e:
        print(f"✗ python-dotenv: {e}")
        return False
    
    try:
        from tenacity import retry
        print("✓ tenacity")
    except ImportError as e:
        print(f"✗ tenacity: {e}")
        return False
    
    try:
        from bs4 import BeautifulSoup
        print("✓ beautifulsoup4")
    except ImportError as e:
        print(f"✗ beautifulsoup4: {e}")
        return False
    
    return True

def test_local_modules():
    """Test that our local modules can be imported"""
    print("\nTesting local modules...")
    
    try:
        from fetch_leaderboards import PolymarketLeaderboardScraper
        print("✓ fetch_leaderboards")
    except ImportError as e:
        print(f"✗ fetch_leaderboards: {e}")
        return False
    
    try:
        from db import PolymarketDB
        print("✓ db")
    except ImportError as e:
        print(f"✗ db: {e}")
        return False
    
    try:
        from notify import TelegramNotifier
        print("✓ notify")
    except ImportError as e:
        print(f"✗ notify: {e}")
        return False
    
    try:
        from polymarket_notifier import PolymarketNotifier
        print("✓ polymarket_notifier")
    except ImportError as e:
        print(f"✗ polymarket_notifier: {e}")
        return False
    
    return True

def test_database():
    """Test database functionality"""
    print("\nTesting database...")
    
    try:
        from db import PolymarketDB
        
        # Create test database
        test_db = PolymarketDB("test_polymarket.db")
        
        # Test wallet operations
        success = test_db.upsert_wallet(
            "0x1234567890abcdef1234567890abcdef12345678",
            "Test Wallet",
            100,
            0.75,
            1000.0,
            2.5,
            "test"
        )
        
        if success:
            print("✓ Database operations")
        else:
            print("✗ Database operations failed")
            return False
        
        # Test stats
        stats = test_db.get_wallet_stats()
        if stats:
            print("✓ Database stats")
        else:
            print("✗ Database stats failed")
            return False
        
        # Cleanup
        os.remove("test_polymarket.db")
        print("✓ Database cleanup")
        
        return True
        
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        return False

async def test_playwright():
    """Test Playwright browser functionality"""
    print("\nTesting Playwright...")
    
    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Test basic navigation
            await page.goto("https://httpbin.org/get")
            content = await page.content()
            
            if "httpbin" in content.lower():
                print("✓ Playwright browser navigation")
            else:
                print("✗ Playwright browser navigation failed")
                return False
            
            await browser.close()
            print("✓ Playwright browser cleanup")
        
        return True
        
    except Exception as e:
        print(f"✗ Playwright test failed: {e}")
        return False

def test_configuration():
    """Test configuration file"""
    print("\nTesting configuration...")
    
    env_example = Path("env.example")
    if env_example.exists():
        print("✓ env.example exists")
    else:
        print("✗ env.example missing")
        return False
    
    requirements = Path("requirements.txt")
    if requirements.exists():
        print("✓ requirements.txt exists")
    else:
        print("✗ requirements.txt missing")
        return False
    
    readme = Path("README.md")
    if readme.exists():
        print("✓ README.md exists")
    else:
        print("✗ README.md missing")
        return False
    
    return True

def main():
    """Run all tests"""
    print("Polymarket Notifier Bot - Installation Test")
    print("=" * 50)
    
    all_passed = True
    
    # Test imports
    if not test_imports():
        all_passed = False
    
    # Test local modules
    if not test_local_modules():
        all_passed = False
    
    # Test database
    if not test_database():
        all_passed = False
    
    # Test Playwright
    try:
        if not asyncio.run(test_playwright()):
            all_passed = False
    except Exception as e:
        print(f"✗ Playwright test error: {e}")
        all_passed = False
    
    # Test configuration
    if not test_configuration():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All tests passed! Installation is complete.")
        print("\nNext steps:")
        print("1. Copy env.example to .env")
        print("2. Add your Telegram bot token and chat ID to .env")
        print("3. Run: python polymarket_notifier.py")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        print("\nCommon fixes:")
        print("- Run: pip install -r requirements.txt")
        print("- Run: playwright install chromium")
        print("- Check Python version (3.10+ required)")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
