#!/usr/bin/env python3
"""
robust_all_volume_leaderboard.py

Robust debug + extraction script for Polymarket leaderboard "overall/all/volume".
Uses Playwright (sync API). Requires playwright installed and browsers:
    pip install playwright
    playwright install

Usage:
    python3 robust_all_volume_leaderboard.py --url "<URL>" [--proxy-file "proxies.txt"] [--out-dir "./debug"] [--try-all] [--nav-timeout-ms 90000]
"""

import re
import time
import argparse
import logging
import json
import os
from pathlib import Path
from typing import List, Set, Optional, Dict, Any
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

# --- Configuration ---
DEFAULT_NAV_TIMEOUT_MS = 90000         # navigation timeout for problematic pages
SELECTOR_WAIT_MS = 30000       # wait_for_selector timeout
SCROLL_ATTEMPTS = 10
SCROLL_PAUSE = 1.0             # seconds between scrolls
SCROLL_STEP = 2000             # pixels to wheel each scroll
RETRY_ATTEMPTS = 3
RETRY_PAUSE = 2.0              # seconds between retry attempts
FALLBACK_WAIT_MS = 5000        # wait before fallback extraction

ADDRESS_RE = re.compile(r'0x[a-fA-F0-9]{40}')

# Candidate selectors to look for the leaderboard table
TABLE_SELECTORS = [
    '[data-testid="leaderboard-table"]',
    'table[data-testid="leaderboard-table"]',   # defensive
    '[role="table"]',
    '.leaderboard',   # fallback class name candidate
    '.leaderboard-table',
    'div[class*="leaderboard"]'
]

# Cloudflare / block detection snippets
BLOCK_SNIPPETS = [
    'Checking your browser',
    'One more step',
    'cloudflare',
    'Access denied',
    'not available in your region',
    'blocked',
    'captcha',
    'Please enable cookies'
]

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("robust_lb_debug")


def extract_addresses_from_text(text: str) -> Set[str]:
    return set(m.group(0).lower() for m in ADDRESS_RE.finditer(text))


def detect_block_by_html(html: str) -> Optional[str]:
    low = html.lower()
    for snippet in BLOCK_SNIPPETS:
        if snippet.lower() in low:
            return snippet
    return None


def get_block_snippet_text(html: str, snippet: str) -> str:
    """Extract ~200 chars around the detected block snippet"""
    low = html.lower()
    snippet_low = snippet.lower()
    idx = low.find(snippet_low)
    if idx >= 0:
        start = max(0, idx - 100)
        end = min(len(html), idx + len(snippet) + 100)
        return html[start:end].strip()
    return ""


def parse_proxy(proxy_str: str) -> Dict[str, str]:
    """Parse proxy string like 'username:password@host:port' or 'http://username:password@host:port'"""
    if not proxy_str:
        return {}
    
    # Remove http:// if present
    if proxy_str.startswith("http://"):
        proxy_str = proxy_str[7:]
    elif proxy_str.startswith("https://"):
        proxy_str = proxy_str[8:]
    
    # Check for auth
    if "@" in proxy_str:
        auth_part, server_part = proxy_str.rsplit("@", 1)
        if ":" in auth_part:
            username, password = auth_part.split(":", 1)
        else:
            username = auth_part
            password = ""
        
        if ":" in server_part:
            host, port = server_part.rsplit(":", 1)
        else:
            host = server_part
            port = "80"
        
        return {
            "server": f"http://{host}:{port}",
            "username": username,
            "password": password
        }
    else:
        # No auth, just host:port
        if ":" in proxy_str:
            host, port = proxy_str.rsplit(":", 1)
        else:
            host = proxy_str
            port = "80"
        return {
            "server": f"http://{host}:{port}"
        }


def load_proxies_from_file(proxy_file: str) -> List[str]:
    """Load proxy list from file (one per line)"""
    proxies = []
    with open(proxy_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                proxies.append(line)
    return proxies


def try_fetch_with_proxy(url: str, proxy_str: str, proxy_index: int, nav_timeout_ms: int, out_dir: Path, log_file: Optional[logging.FileHandler] = None) -> Dict[str, Any]:
    """
    Try to open page with specific proxy, look for leaderboard table by selectors, scroll if needed,
    and fallback to regex extraction of addresses.
    Returns dict with detailed results.
    """
    result = {
        "proxy_index": proxy_index,
        "proxy": proxy_str,
        "attempts": [],
        "final_status": "fail",
        "response_status": None,
        "selectors_found": [],
        "addresses_count": 0,
        "addresses_file": None,
        "html_file": None,
        "screenshot_file": None,
        "notes": []
    }
    
    addresses: Set[str] = set()
    navigation_success = False
    last_response_status = None
    last_response_url = None
    block_detected = None
    
    proxy_config = parse_proxy(proxy_str)
    
    logger.info(f"[Proxy {proxy_index}] Starting with proxy: {proxy_str}")
    if log_file:
        logger.info(f"[Proxy {proxy_index}] Proxy config: {proxy_config}")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context_args = {}
            if proxy_config:
                context_args["proxy"] = proxy_config
            
            context = browser.new_context(**context_args)
            page = context.new_page()
            
            # register listener for responses to capture final status
            def on_response(response):
                nonlocal last_response_status, last_response_url
                try:
                    if url in response.url or response.url.startswith("https://polymarket.com/leaderboard"):
                        last_response_status = response.status
                        last_response_url = response.url
                        logger.info(f"[Proxy {proxy_index}] Response: status={last_response_status}, url={last_response_url}")
                except Exception:
                    pass
            
            page.on("response", on_response)
            
            # Try retries for heavy pages
            for attempt in range(1, RETRY_ATTEMPTS + 1):
                attempt_info = {
                    "attempt": attempt,
                    "duration_s": None,
                    "status": None,
                    "response_status": None
                }
                
                logger.info(f"[Proxy {proxy_index}] Attempt {attempt}/{RETRY_ATTEMPTS}: navigating to {url} (timeout {nav_timeout_ms} ms)")
                try:
                    start = time.time()
                    page.goto(url, timeout=nav_timeout_ms, wait_until="domcontentloaded")
                    nav_dur = time.time() - start
                    attempt_info["duration_s"] = round(nav_dur, 2)
                    attempt_info["status"] = "success"
                    attempt_info["response_status"] = last_response_status
                    logger.info(f"[Proxy {proxy_index}] page.goto() completed in {nav_dur:.2f}s; response status={last_response_status}")
                    navigation_success = True
                    result["response_status"] = last_response_status
                    result["attempts"].append(attempt_info)
                    break
                except PlaywrightTimeoutError as e:
                    nav_dur = time.time() - start if 'start' in locals() else 0
                    attempt_info["duration_s"] = round(nav_dur, 2) if nav_dur > 0 else None
                    attempt_info["status"] = "timeout"
                    attempt_info["response_status"] = last_response_status
                    logger.warning(f"[Proxy {proxy_index}] page.goto() timeout on attempt {attempt}: {e}")
                    result["attempts"].append(attempt_info)
                    if attempt < RETRY_ATTEMPTS:
                        logger.info(f"[Proxy {proxy_index}] sleeping {RETRY_PAUSE}s before retry...")
                        time.sleep(RETRY_PAUSE)
                    else:
                        logger.error(f"[Proxy {proxy_index}] navigation failed after {RETRY_ATTEMPTS} attempts")
                except Exception as e:
                    nav_dur = time.time() - start if 'start' in locals() else 0
                    attempt_info["duration_s"] = round(nav_dur, 2) if nav_dur > 0 else None
                    attempt_info["status"] = "error"
                    attempt_info["response_status"] = last_response_status
                    attempt_info["error"] = str(e)
                    logger.error(f"[Proxy {proxy_index}] page.goto() error on attempt {attempt}: {e}")
                    result["attempts"].append(attempt_info)
                    if attempt < RETRY_ATTEMPTS:
                        time.sleep(RETRY_PAUSE)
            
            # Even if navigation failed, try to get current DOM for fallback
            if not navigation_success:
                logger.info(f"[Proxy {proxy_index}] Navigation failed, waiting {FALLBACK_WAIT_MS/1000}s and trying fallback extraction...")
                time.sleep(FALLBACK_WAIT_MS / 1000)
            
            # Give some time for dynamic content
            if navigation_success:
                logger.info(f"[Proxy {proxy_index}] Waiting for dynamic content to render...")
                time.sleep(2.5)
            
            # Try finding table by selectors
            table_found = False
            for sel in TABLE_SELECTORS:
                try:
                    logger.info(f"[Proxy {proxy_index}] Waiting for selector: {sel} (timeout {SELECTOR_WAIT_MS} ms)")
                    locator = page.wait_for_selector(sel, timeout=SELECTOR_WAIT_MS)
                    if locator:
                        logger.info(f"[Proxy {proxy_index}] Selector matched: {sel}")
                        table_found = True
                        result["selectors_found"].append(sel)
                        break
                except PlaywrightTimeoutError:
                    logger.info(f"[Proxy {proxy_index}] Selector not found: {sel}")
                except PlaywrightError as e:
                    logger.warning(f"[Proxy {proxy_index}] Playwright error waiting for {sel}: {e}")
            
            # If not found, try scrolling and re-checking
            if not table_found:
                logger.info(f"[Proxy {proxy_index}] Table selector not found — trying incremental scrolling to load rows...")
                previous_count = 0
                no_change_streak = 0
                for i in range(SCROLL_ATTEMPTS):
                    # perform wheel scroll
                    try:
                        page.mouse.wheel(0, SCROLL_STEP)
                    except Exception:
                        try:
                            page.evaluate(f"window.scrollBy(0, {SCROLL_STEP})")
                        except Exception:
                            pass
                    time.sleep(SCROLL_PAUSE)
                    
                    # after scroll, try to count occurrences of wallet rows via regex
                    try:
                        content = page.content()
                        found = len(ADDRESS_RE.findall(content))
                        logger.info(f"[Proxy {proxy_index}] After scroll {i+1}: found {found} address-like strings in HTML")
                        if found > previous_count:
                            previous_count = found
                            no_change_streak = 0
                        else:
                            no_change_streak += 1
                    except Exception:
                        no_change_streak += 1
                    
                    # try to re-query selectors quickly
                    for sel in TABLE_SELECTORS:
                        try:
                            if page.query_selector(sel):
                                logger.info(f"[Proxy {proxy_index}] Selector matched after scrolling: {sel}")
                                table_found = True
                                result["selectors_found"].append(sel)
                                break
                        except Exception:
                            pass
                    if table_found:
                        break
                    if no_change_streak >= 3:
                        logger.info(f"[Proxy {proxy_index}] No new rows after 3 scrolls — stop scrolling")
                        break
            
            # Grab full HTML and screenshot for diagnostics
            try:
                html = page.content()
            except Exception as e:
                logger.error(f"[Proxy {proxy_index}] Failed to get page content: {e}")
                html = ""
            
            try:
                screenshot = page.screenshot(full_page=True)
            except Exception as e:
                logger.warning(f"[Proxy {proxy_index}] Failed to take screenshot: {e}")
                screenshot = None
            
            # Save files
            html_file = out_dir / f"debug_proxy_{proxy_index}.html"
            screenshot_file = out_dir / f"debug_proxy_{proxy_index}.png"
            
            with open(html_file, "w", encoding="utf-8") as fh:
                fh.write(html)
            logger.info(f"[Proxy {proxy_index}] Saved HTML to {html_file}")
            result["html_file"] = str(html_file)
            
            if screenshot:
                with open(screenshot_file, "wb") as fh:
                    fh.write(screenshot)
                logger.info(f"[Proxy {proxy_index}] Saved screenshot to {screenshot_file}")
                result["screenshot_file"] = str(screenshot_file)
            
            # Detect possible block
            block_snip = detect_block_by_html(html)
            if block_snip:
                block_text = get_block_snippet_text(html, block_snip)
                logger.warning(f"[Proxy {proxy_index}] Block snippet detected: '{block_snip}'")
                logger.warning(f"[Proxy {proxy_index}] Block text snippet: {block_text[:200]}")
                result["notes"].append(f"Block detected: {block_snip}")
                block_detected = block_snip
                # Don't try multiple times if blocked
                if "Access denied" in block_snip or "blocked" in block_snip.lower():
                    result["notes"].append("Marked as blocked - skipping further attempts")
            
            # If table found, try to extract addresses from table rows
            row_selectors = [
                '[data-testid="leaderboard-table"] tr',
                'table tr',
                '[role="row"]',
                'div[class*="leaderboard"] li',
                'div[class*="leaderboard-row"]'
            ]
            extracted = set()
            if table_found:
                logger.info(f"[Proxy {proxy_index}] Attempt extracting addresses by DOM row selectors...")
                for rsel in row_selectors:
                    try:
                        nodes = page.query_selector_all(rsel)
                        if not nodes:
                            continue
                        logger.info(f"[Proxy {proxy_index}] Found {len(nodes)} nodes for row selector: {rsel}")
                        for n in nodes:
                            try:
                                text = n.inner_text()
                            except Exception:
                                try:
                                    text = n.text_content() or ""
                                except Exception:
                                    text = ""
                            if not text:
                                continue
                            for a in ADDRESS_RE.findall(text):
                                extracted.add(a.lower())
                        if extracted:
                            logger.info(f"[Proxy {proxy_index}] Extracted {len(extracted)} addresses via {rsel}")
                            result["notes"].append(f"Extracted via DOM selector: {rsel}")
                            break
                    except Exception as e:
                        logger.debug(f"[Proxy {proxy_index}] Error iterating nodes for {rsel}: {e}")
            
            # 2) Fallback: regex over full HTML
            if not extracted and html:
                logger.info(f"[Proxy {proxy_index}] Fallback: extracting addresses via regex over full HTML")
                extracted = extract_addresses_from_text(html)
                logger.info(f"[Proxy {proxy_index}] Regex extracted {len(extracted)} addresses from HTML")
                if extracted:
                    result["notes"].append("Extracted via regex fallback from HTML")
            
            # 3) Another fallback: inner_text of body
            if not extracted:
                try:
                    body_text = page.inner_text("body")
                    extracted = extract_addresses_from_text(body_text)
                    logger.info(f"[Proxy {proxy_index}] Extracted {len(extracted)} addresses from body text")
                    if extracted:
                        result["notes"].append("Extracted via regex fallback from body text")
                except Exception as e:
                    logger.debug(f"[Proxy {proxy_index}] Failed to get body text: {e}")
            
            addresses = {a.lower() for a in extracted}
            result["addresses_count"] = len(addresses)
            logger.info(f"[Proxy {proxy_index}] Final unique addresses count: {len(addresses)}")
            
            # Save addresses if any found
            if addresses:
                addresses_file = out_dir / f"addresses_proxy_{proxy_index}.txt"
                with open(addresses_file, "w") as fh:
                    for a in sorted(addresses):
                        fh.write(a + "\n")
                logger.info(f"[Proxy {proxy_index}] Saved addresses to {addresses_file}")
                result["addresses_file"] = str(addresses_file)
            
            # Determine final status
            if table_found and addresses:
                result["final_status"] = "success"
            elif addresses:
                result["final_status"] = "partial"  # Got addresses but no table selector
                result["notes"].append("Addresses extracted via fallback (no table selector found)")
            else:
                result["final_status"] = "fail"
                if block_detected:
                    result["notes"].append(f"Blocked: {block_detected}")
                else:
                    result["notes"].append("No addresses extracted")
            
            # cleanup
            try:
                context.close()
                browser.close()
            except Exception:
                pass
    
    except Exception as e:
        logger.exception(f"[Proxy {proxy_index}] Unhandled exception: {e}")
        result["notes"].append(f"Exception: {str(e)}")
        result["final_status"] = "error"
    
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Target leaderboard URL")
    parser.add_argument("--proxy", required=False, help="Single HTTP proxy like host:port or username:password@host:port")
    parser.add_argument("--proxy-file", required=False, help="File with proxy list (one per line)")
    parser.add_argument("--out-dir", default="./debug_all_volume_run", help="Directory to save debug HTML and screenshots")
    parser.add_argument("--try-all", action="store_true", help="Try all proxies even if one succeeds")
    parser.add_argument("--nav-timeout-ms", type=int, default=DEFAULT_NAV_TIMEOUT_MS, help=f"Navigation timeout in ms (default: {DEFAULT_NAV_TIMEOUT_MS})")
    args = parser.parse_args()
    
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Setup file logging
    log_file_path = out_dir / "debug.log"
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(file_handler)
    
    # Load proxies
    proxies = []
    if args.proxy_file:
        proxies = load_proxies_from_file(args.proxy_file)
        logger.info(f"Loaded {len(proxies)} proxies from {args.proxy_file}")
    elif args.proxy:
        proxies = [args.proxy]
        logger.info(f"Using single proxy: {args.proxy}")
    else:
        logger.error("Either --proxy or --proxy-file must be provided")
        return
    
    logger.info("=" * 80)
    logger.info("[Debug] Starting robust_all_volume_leaderboard script")
    logger.info(f"[Debug] Target URL: {args.url}")
    logger.info(f"[Debug] Proxies: {len(proxies)}")
    logger.info(f"[Debug] Navigation timeout: {args.nav_timeout_ms} ms")
    logger.info(f"[Debug] Try all: {args.try_all}")
    logger.info("=" * 80)
    
    results = []
    
    for i, proxy_str in enumerate(proxies, 1):
        logger.info("=" * 80)
        logger.info(f"[Proxy {i}/{len(proxies)}] Testing proxy: {proxy_str}")
        logger.info("=" * 80)
        
        result = try_fetch_with_proxy(
            args.url, 
            proxy_str, 
            i, 
            args.nav_timeout_ms, 
            out_dir,
            file_handler
        )
        results.append(result)
        
        # Check if successful and should stop
        if result["final_status"] == "success" and not args.try_all:
            logger.info(f"[Proxy {i}] SUCCESS! Stopping at first successful proxy.")
            break
        elif result["final_status"] == "partial" and not args.try_all:
            logger.info(f"[Proxy {i}] PARTIAL SUCCESS (addresses found but no table). Stopping.")
            break
    
    # Generate summary
    summary_json = out_dir / "summary.json"
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved summary JSON to {summary_json}")
    
    # Generate text summary
    summary_txt = out_dir / "summary.txt"
    with open(summary_txt, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("SUMMARY OF PROXY TESTS\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"URL: {args.url}\n")
        f.write(f"Total proxies tested: {len(results)}\n")
        f.write(f"Navigation timeout: {args.nav_timeout_ms} ms\n\n")
        
        f.write("-" * 80 + "\n")
        f.write(f"{'Proxy':<5} {'Status':<12} {'Response':<10} {'Selectors':<10} {'Addresses':<10} {'Notes'}\n")
        f.write("-" * 80 + "\n")
        
        for r in results:
            status = r["final_status"]
            resp = str(r["response_status"]) if r["response_status"] else "N/A"
            selectors = len(r["selectors_found"])
            addresses = r["addresses_count"]
            notes = "; ".join(r["notes"][:2]) if r["notes"] else ""
            proxy_display = r["proxy"][:40] + "..." if len(r["proxy"]) > 40 else r["proxy"]
            
            f.write(f"{r['proxy_index']:<5} {status:<12} {resp:<10} {selectors:<10} {addresses:<10} {notes}\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("DETAILED RESULTS\n")
        f.write("=" * 80 + "\n\n")
        
        for r in results:
            f.write(f"\nProxy {r['proxy_index']}: {r['proxy']}\n")
            f.write(f"  Status: {r['final_status']}\n")
            f.write(f"  Response: {r['response_status']}\n")
            f.write(f"  Attempts: {len(r['attempts'])}\n")
            for att in r['attempts']:
                f.write(f"    Attempt {att['attempt']}: {att['status']} ({att['duration_s']}s, status={att['response_status']})\n")
            f.write(f"  Selectors found: {r['selectors_found']}\n")
            f.write(f"  Addresses: {r['addresses_count']}\n")
            f.write(f"  Files: {r['html_file']}, {r['screenshot_file']}, {r['addresses_file']}\n")
            f.write(f"  Notes: {'; '.join(r['notes'])}\n")
    
    logger.info(f"Saved summary TXT to {summary_txt}")
    
    # Final summary
    logger.info("=" * 80)
    logger.info("FINAL SUMMARY:")
    successful = [r for r in results if r["final_status"] == "success"]
    partial = [r for r in results if r["final_status"] == "partial"]
    failed = [r for r in results if r["final_status"] == "fail"]
    
    logger.info(f"  Successful: {len(successful)}")
    logger.info(f"  Partial: {len(partial)}")
    logger.info(f"  Failed: {len(failed)}")
    
    if successful:
        logger.info(f"  First successful proxy: {successful[0]['proxy_index']} - {successful[0]['proxy']}")
        logger.info(f"    Addresses found: {successful[0]['addresses_count']}")
    elif partial:
        logger.info(f"  First partial success: {partial[0]['proxy_index']} - {partial[0]['proxy']}")
        logger.info(f"    Addresses found: {partial[0]['addresses_count']}")
    else:
        logger.warning("  No successful proxies found")
    
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
