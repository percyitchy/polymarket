#!/usr/bin/env python3
"""
Debug script for problematic all/volume leaderboard page
Analyzes why https://polymarket.com/leaderboard/overall/all/volume times out
"""

import asyncio
import logging
import os
from datetime import datetime
from playwright.async_api import async_playwright
from urllib.parse import urlparse
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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TARGET_URL = "https://polymarket.com/leaderboard/overall/all/volume"
OUTPUT_HTML = "debug_all_volume.html"
OUTPUT_SCREENSHOT = "debug_all_volume.png"

async def debug_all_volume_leaderboard():
    """Debug the problematic all/volume leaderboard page"""
    
    logger.info("=" * 80)
    logger.info("[Debug] Starting debug script for all/volume leaderboard")
    logger.info(f"[Debug] Target URL: {TARGET_URL}")
    logger.info("=" * 80)
    
    # Initialize proxy manager if available
    proxy_manager = None
    proxy_info = "No proxy"
    
    if PROXY_MANAGER_AVAILABLE:
        try:
            proxy_manager = ProxyManager()
            if proxy_manager.proxy_enabled:
                proxy = proxy_manager.get_proxy(rotate=True)
                if proxy:
                    proxy_url = proxy.get("http") or proxy.get("https")
                    parsed = urlparse(proxy_url)
                    proxy_info = f"{parsed.hostname}:{parsed.port}"
                    logger.info(f"[Debug] Using proxy: {proxy_info}")
                else:
                    logger.info("[Debug] Proxy manager enabled but no proxy available")
            else:
                logger.info("[Debug] Proxy manager disabled")
        except Exception as e:
            logger.warning(f"[Debug] Failed to initialize proxy manager: {e}")
    
    if not proxy_info.startswith("No proxy"):
        logger.info(f"[Debug] Proxy: {proxy_info}")
    else:
        logger.info("[Debug] Running without proxy")
    
    playwright = await async_playwright().start()
    
    try:
        # Configure browser launch options
        launch_options = {
            "headless": False  # Run visible for debugging
        }
        
        # Configure browser context with proxy if available
        context_options = {
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # Add proxy if available (only HTTP/HTTPS, not SOCKS5)
        if proxy_manager and proxy_manager.proxy_enabled:
            proxy = proxy_manager.get_proxy(rotate=True)
            if proxy:
                proxy_url = proxy.get("http") or proxy.get("https")
                if proxy_url:
                    parsed = urlparse(proxy_url)
                    scheme = (parsed.scheme or "").lower()
                    
                    if scheme in ("http", "https"):
                        context_options["proxy"] = {
                            "server": f"{scheme}://{parsed.hostname}:{parsed.port}",
                            "username": parsed.username,
                            "password": parsed.password,
                        }
                        logger.info(f"[Debug] Configured HTTP proxy: {parsed.hostname}:{parsed.port}")
                    else:
                        logger.warning(f"[Debug] Unsupported proxy scheme: {scheme}")
        
        browser = await playwright.chromium.launch(**launch_options)
        context = await browser.new_context(**context_options)
        page = await context.new_page()
        
        # Track response status
        response_status = None
        response_url = None
        
        def handle_response(response):
            nonlocal response_status, response_url
            if response.url == TARGET_URL or TARGET_URL in response.url:
                response_status = response.status
                response_url = response.url
                logger.info(f"[Debug] Response received: status={response_status}, url={response_url}")
        
        page.on("response", handle_response)
        
        try:
            # Navigate to the page
            logger.info("[Debug] Starting page.goto()...")
            goto_start = asyncio.get_event_loop().time()
            
            try:
                await page.goto(TARGET_URL, timeout=90000, wait_until="domcontentloaded")
                goto_end = asyncio.get_event_loop().time()
                goto_duration = goto_end - goto_start
                logger.info(f"[Debug] page.goto() completed in {goto_duration:.2f}s")
            except Exception as e:
                goto_end = asyncio.get_event_loop().time()
                goto_duration = goto_end - goto_start
                logger.error(f"[Debug] page.goto() failed after {goto_duration:.2f}s: {e}")
                raise
            
            # Get final URL after redirects
            final_url = page.url
            logger.info(f"[Debug] Final URL after redirects: {final_url}")
            
            # Wait additional time for dynamic content
            logger.info("[Debug] Waiting 5 seconds for dynamic content...")
            await page.wait_for_timeout(5000)
            
            # Try to find leaderboard table
            logger.info("[Debug] Looking for leaderboard table selector...")
            selector_found = False
            try:
                await page.wait_for_selector('[data-testid="leaderboard-table"]', timeout=30000)
                selector_found = True
                logger.info("[Debug] ✓ Found selector '[data-testid=\"leaderboard-table\"]'")
            except Exception as e:
                logger.warning(f"[Debug] ✗ Selector '[data-testid=\"leaderboard-table\"]' not found: {e}")
                
                # Try alternative selectors
                alternative_selectors = [
                    '.leaderboard-table',
                    'table',
                    '[data-testid*="leaderboard"]',
                    '[data-testid*="table"]',
                ]
                
                for alt_selector in alternative_selectors:
                    try:
                        element = await page.query_selector(alt_selector)
                        if element:
                            logger.info(f"[Debug] ✓ Found alternative selector: {alt_selector}")
                            selector_found = True
                            break
                    except Exception:
                        continue
            
            # Count table rows
            row_count = 0
            if selector_found:
                try:
                    rows = await page.query_selector_all('[data-testid="leaderboard-table"] tr, .leaderboard-table tr, table tr')
                    row_count = len(rows)
                    logger.info(f"[Debug] Found {row_count} rows in table")
                except Exception as e:
                    logger.warning(f"[Debug] Could not count rows: {e}")
            
            # Check for Cloudflare/Captcha/Access denied
            page_content_lower = (await page.content()).lower()
            
            cloudflare_indicators = ["cloudflare", "checking your browser", "ddos protection"]
            captcha_indicators = ["captcha", "recaptcha", "hcaptcha"]
            access_denied_indicators = ["access denied", "forbidden", "403", "blocked"]
            error_indicators = ["error", "something went wrong", "failed to load"]
            
            detected_issues = []
            
            for indicator in cloudflare_indicators:
                if indicator in page_content_lower:
                    detected_issues.append("Cloudflare protection")
                    break
            
            for indicator in captcha_indicators:
                if indicator in page_content_lower:
                    detected_issues.append("Captcha challenge")
                    break
            
            for indicator in access_denied_indicators:
                if indicator in page_content_lower:
                    detected_issues.append("Access denied")
                    break
            
            if detected_issues:
                logger.warning(f"[Debug] ⚠ Detected issues: {', '.join(detected_issues)}")
            else:
                logger.info("[Debug] ✓ No Cloudflare/Captcha/Access denied detected")
            
            # Save HTML
            html_content = await page.content()
            with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"[Debug] Saved HTML to {OUTPUT_HTML}")
            
            # Save screenshot
            await page.screenshot(path=OUTPUT_SCREENSHOT, full_page=True)
            logger.info(f"[Debug] Saved screenshot to {OUTPUT_SCREENSHOT}")
            
            # Summary
            logger.info("=" * 80)
            logger.info("[Debug] SUMMARY:")
            logger.info(f"  URL: {TARGET_URL}")
            logger.info(f"  Final URL: {final_url}")
            logger.info(f"  Response status: {response_status or 'N/A'}")
            logger.info(f"  Proxy: {proxy_info}")
            logger.info(f"  page.goto() duration: {goto_duration:.2f}s")
            logger.info(f"  Table selector found: {selector_found}")
            logger.info(f"  Table rows: {row_count}")
            if detected_issues:
                logger.info(f"  Issues detected: {', '.join(detected_issues)}")
            logger.info("=" * 80)
            
        finally:
            await page.close()
            await context.close()
            await browser.close()
            
    finally:
        await playwright.stop()

if __name__ == "__main__":
    asyncio.run(debug_all_volume_leaderboard())

