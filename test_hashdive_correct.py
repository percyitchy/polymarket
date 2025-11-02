#!/usr/bin/env python3
"""
Test script for HashDive API with correct parameters
"""

import requests
import json

API_KEY = "2fcbbb010f3ff15f84dc47ebb0d92917d6fee90771407f56174423b9b28e5c3c"
BASE_URL = "https://hashdive.com/api"

# Test API usage first
def test_api_usage():
    """Test the /get_api_usage endpoint"""
    print("=" * 60)
    print("Testing: API Usage Endpoint")
    print("=" * 60)
    
    url = f"{BASE_URL}/get_api_usage"
    headers = {
        "x-api-key": API_KEY
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ SUCCESS!")
            print(f"API Usage Data:")
            print(json.dumps(data, indent=2))
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_search_markets():
    """Test the /search_markets endpoint"""
    print("\n" + "=" * 60)
    print("Testing: Search Markets Endpoint")
    print("=" * 60)
    
    url = f"{BASE_URL}/search_markets"
    headers = {
        "x-api-key": API_KEY
    }
    params = {
        "query": "election",
        "format": "json",
        "page": 1,
        "page_size": 5
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ SUCCESS!")
            print(f"Found markets:")
            print(json.dumps(data, indent=2)[:1000])
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_get_trades():
    """Test the /get_trades endpoint"""
    print("\n" + "=" * 60)
    print("Testing: Get Trades Endpoint")
    print("=" * 60)
    
    # Using a sample wallet address from the documentation
    sample_wallet = "0x56687bf447db6ffa42ffe2204a05edaa20f55839"
    
    url = f"{BASE_URL}/get_trades"
    headers = {
        "x-api-key": API_KEY
    }
    params = {
        "user_address": sample_wallet,
        "format": "json",
        "page": 1,
        "page_size": 5
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ SUCCESS!")
            print(f"Trade Data:")
            print(json.dumps(data, indent=2)[:1000])
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def main():
    print("\n🚀 Testing HashDive API with correct configuration\n")
    
    # Test API usage (doesn't require parameters)
    success1 = test_api_usage()
    
    # Test search markets
    success2 = test_search_markets()
    
    # Test get trades
    success3 = test_get_trades()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"API Usage: {'✅ SUCCESS' if success1 else '❌ FAILED'}")
    print(f"Search Markets: {'✅ SUCCESS' if success2 else '❌ FAILED'}")
    print(f"Get Trades: {'✅ SUCCESS' if success3 else '❌ FAILED'}")
    
    if any([success1, success2, success3]):
        print("\n🎉 At least one endpoint is working!")
    else:
        print("\n⚠️  All endpoints failed. Please check your API key.")

if __name__ == "__main__":
    main()

