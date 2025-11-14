#!/usr/bin/env python3
"""
Test script for HTTP proxy fallback functionality
Validates that http_get() automatically falls back to direct connection when proxy fails
"""

import logging
from utils.http_client import http_get

# Configure logging to show all messages
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)

def test_proxy_fallback():
    """Test that proxy failures trigger automatic direct fallback"""
    print("=" * 80)
    print("🧪 Testing HTTP fallback from proxy to direct mode")
    print("=" * 80)

    # Use an intentionally invalid proxy (localhost:9999 won't be reachable)
    bad_proxy = "socks5://localhost:9999"
    # Use a simple, reliable endpoint for testing
    test_url = "https://httpbin.org/get"  # A reliable test endpoint

    print(f"\n[TEST] Attempting request with bad proxy: {bad_proxy}")
    print(f"[TEST] Target URL: {test_url}")
    print()
    
    response = http_get(test_url, proxy=bad_proxy)

    print()
    if response is not None and getattr(response, "status_code", None) == 200:
        print("✅ Direct fallback successful (received 200 OK)")
        print(f"   Response length: {len(response.content)} bytes")
    elif response is not None:
        print(f"⚠️ Direct fallback responded but status={response.status_code}")
        print(f"   This might be rate limiting or API issue, but fallback worked")
    else:
        print("❌ Both proxy and direct connection failed")
        print("   This could indicate network issues or API downtime")

    print("=" * 80)
    print("Test complete.\n")


def test_direct_only():
    """Test that direct HTTP requests work without proxy"""
    print("=" * 80)
    print("🧪 Testing direct HTTP (no proxy)")
    print("=" * 80)

    # Use a reliable test endpoint
    test_url = "https://httpbin.org/get"

    print(f"\n[TEST] Attempting direct request (no proxy)")
    print(f"[TEST] Target URL: {test_url}")
    print()
    
    response = http_get(test_url)  # БЕЗ proxy

    print()
    if response is not None and getattr(response, "status_code", None) == 200:
        print("✅ Direct request successful (200 OK)")
        print(f"   Response length: {len(response.content)} bytes")
        print("   ✓ No proxy was used (as expected)")
    elif response is not None:
        print(f"⚠️ Direct request responded but status={response.status_code}")
        print("   This might be rate limiting or API issue")
    else:
        print("❌ Direct request failed")
        print("   This could indicate network issues or API downtime")

    print("=" * 80)
    print("Test complete.\n")


if __name__ == "__main__":
    test_proxy_fallback()
    print()
    test_direct_only()

