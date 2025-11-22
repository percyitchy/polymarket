#!/usr/bin/env python3
"""
Enhanced Market Data Sources
Provides additional data sources for market classification:
1. GraphQL API Polymarket
2. Web scraping (polymarket.com)
3. Additional REST API endpoints
"""

import logging
import requests
import re
import sqlite3
import json
import time
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Try to import Playwright for dynamic content
try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.debug("[Enhanced Data] Playwright not available. Install with: pip install playwright && playwright install")

# Cache for market data (in-memory + SQLite)
_market_cache = {}
_cache_db_path = None
_cache_ttl_seconds = 86400  # 24 hours cache (increased for historical markets)

# GraphQL endpoint (if available)
GRAPHQL_ENDPOINT = "https://gamma-api.polymarket.com/graphql"
# Alternative GraphQL endpoint
GRAPHQL_ENDPOINT_ALT = "https://polymarket.com/graphql"

# Web scraping endpoints
POLYMARKET_BASE_URL = "https://polymarket.com"
POLYMARKET_EVENT_URL = f"{POLYMARKET_BASE_URL}/event"
POLYMARKET_MARKET_URL = f"{POLYMARKET_BASE_URL}/market"


def _init_cache_db(db_path: str = "polymarket_market_cache.db"):
    """Initialize cache database"""
    global _cache_db_path
    _cache_db_path = db_path
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_cache (
                condition_id TEXT PRIMARY KEY,
                data TEXT,
                cached_at REAL
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"[Cache] Failed to init cache DB: {e}")

def _get_from_cache(condition_id: str) -> Optional[Dict[str, Any]]:
    """Get market data from cache"""
    # Check in-memory cache first
    if condition_id in _market_cache:
        cached_data, cached_at = _market_cache[condition_id]
        if time.time() - cached_at < _cache_ttl_seconds:
            return cached_data
    
    # Check SQLite cache
    if _cache_db_path:
        try:
            conn = sqlite3.connect(_cache_db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT data, cached_at FROM market_cache
                WHERE condition_id = ? AND (cached_at + ?) > ?
            """, (condition_id, _cache_ttl_seconds, time.time()))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                data_str, cached_at = row
                data = json.loads(data_str)
                # Update in-memory cache
                _market_cache[condition_id] = (data, cached_at)
                return data
        except Exception as e:
            logger.debug(f"[Cache] Failed to read from cache: {e}")
    
    return None

def _save_to_cache(condition_id: str, data: Dict[str, Any]):
    """Save market data to cache"""
    current_time = time.time()
    
    # Update in-memory cache
    _market_cache[condition_id] = (data, current_time)
    
    # Save to SQLite cache
    if _cache_db_path:
        try:
            conn = sqlite3.connect(_cache_db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO market_cache (condition_id, data, cached_at)
                VALUES (?, ?, ?)
            """, (condition_id, json.dumps(data), current_time))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"[Cache] Failed to save to cache: {e}")

def get_market_data_from_graphql(condition_id: str, retry: bool = True) -> Optional[Dict[str, Any]]:
    """
    Get market data from GraphQL API (with caching and retry)
    
    Args:
        condition_id: Market condition ID
        retry: Whether to retry on failure
        
    Returns:
        Dict with market data or None if failed
    """
    # Check cache first
    cached_data = _get_from_cache(condition_id)
    if cached_data:
        logger.debug(f"[GraphQL] Using cached data for condition {condition_id[:20]}...")
        return cached_data
    
    # GraphQL query to get market data
    query = """
    query GetMarket($conditionId: String!) {
        market(conditionId: $conditionId) {
            id
            slug
            question
            description
            title
            category
            tags
            endDate
            resolutionSource
        }
    }
    """
    
    variables = {
        "conditionId": condition_id
    }
    
    payload = {
        "query": query,
        "variables": variables
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; PolymarketNotifier/1.0)"
    }
    
    # Try primary endpoint
    try:
        response = requests.post(GRAPHQL_ENDPOINT, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "data" in data and data["data"] and "market" in data["data"]:
                market_data = data["data"]["market"]
                if market_data:
                    logger.debug(f"[GraphQL] Got market data for condition {condition_id[:20]}...")
                    _save_to_cache(condition_id, market_data)
                    return market_data
    except Exception as e:
        logger.debug(f"[GraphQL] Primary endpoint failed: {e}")
    
    # Try alternative endpoint
    try:
        response = requests.post(GRAPHQL_ENDPOINT_ALT, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if "data" in data and data["data"] and "market" in data["data"]:
                market_data = data["data"]["market"]
                if market_data:
                    logger.debug(f"[GraphQL] Got market data from alt endpoint for condition {condition_id[:20]}...")
                    _save_to_cache(condition_id, market_data)
                    return market_data
    except Exception as e:
        logger.debug(f"[GraphQL] Alternative endpoint failed: {e}")
    
    # Retry with longer timeout for historical markets
    if retry:
        try:
            response = requests.post(GRAPHQL_ENDPOINT, json=payload, headers=headers, timeout=20)
            if response.status_code == 200:
                data = response.json()
                if "data" in data and data["data"] and "market" in data["data"]:
                    market_data = data["data"]["market"]
                    if market_data:
                        logger.debug(f"[GraphQL] Got market data on retry for condition {condition_id[:20]}...")
                        _save_to_cache(condition_id, market_data)
                        return market_data
        except Exception as e:
            logger.debug(f"[GraphQL] Retry failed: {e}")
    
    return None


def get_market_data_from_web(condition_id: str, slug: Optional[str] = None, retry: bool = True) -> Optional[Dict[str, Any]]:
    """
    Get market data by scraping polymarket.com (with caching and retry)
    
    Args:
        condition_id: Market condition ID
        slug: Optional market slug (if available, speeds up lookup)
        retry: Whether to retry on failure
        
    Returns:
        Dict with market data or None if failed
    """
    # Check cache first
    cached_data = _get_from_cache(f"web_{condition_id}")
    if cached_data:
        logger.debug(f"[Web] Using cached data for condition {condition_id[:20]}...")
        return cached_data
    
    # Try to get data from market page
    if slug:
        url = f"{POLYMARKET_MARKET_URL}/{slug}"
    else:
        # Try to search by condition_id
        url = f"{POLYMARKET_BASE_URL}/search?q={condition_id}"
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try to extract market data from page
            market_data = {}
            
            # Look for JSON-LD structured data (may contain market info)
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            for json_ld in json_ld_scripts:
                try:
                    import json
                    data = json.loads(json_ld.string)
                    if isinstance(data, dict):
                        # Extract relevant fields
                        if 'name' in data:
                            market_data['question'] = market_data.get('question') or data['name']
                        if 'description' in data:
                            market_data['description'] = market_data.get('description') or data['description']
                except Exception:
                    pass
            
            # Look for meta tags (Open Graph)
            meta_title = soup.find('meta', property='og:title')
            if meta_title:
                title_content = meta_title.get('content', '').strip()
                if title_content:
                    market_data['title'] = title_content
                    # If question not set, use title
                    if not market_data.get('question'):
                        market_data['question'] = title_content
            
            meta_description = soup.find('meta', property='og:description')
            if meta_description:
                desc_content = meta_description.get('content', '').strip()
                if desc_content:
                    market_data['description'] = desc_content
            
            # Look for page title
            title_tag = soup.find('title')
            if title_tag:
                title_text = title_tag.get_text(strip=True)
                if title_text:
                    market_data['title'] = market_data.get('title') or title_text
                    if not market_data.get('question'):
                        market_data['question'] = title_text
            
            # Look for question in h1 or main heading
            h1 = soup.find('h1')
            if h1:
                h1_text = h1.get_text(strip=True)
                if h1_text:
                    market_data['question'] = market_data.get('question') or h1_text
            
            # Look for description in meta or paragraph
            if not market_data.get('description'):
                desc_tag = soup.find('meta', {'name': 'description'})
                if desc_tag:
                    desc_content = desc_tag.get('content', '').strip()
                    if desc_content:
                        market_data['description'] = desc_content
            
            # Try to find question in data attributes or script tags
            if not market_data.get('question'):
                # Look for data-question attribute
                question_elem = soup.find(attrs={'data-question': True})
                if question_elem:
                    market_data['question'] = question_elem.get('data-question')
            
            # Extract slug from URL
            if slug:
                market_data['slug'] = slug
            else:
                # Try to extract from canonical URL
                canonical = soup.find('link', rel='canonical')
                if canonical:
                    href = canonical.get('href', '')
                    # Try /market/ pattern
                    slug_match = re.search(r'/market/([^/?]+)', href)
                    if slug_match:
                        market_data['slug'] = slug_match.group(1)
                    else:
                        # Try /event/ pattern
                        slug_match = re.search(r'/event/([^/?]+)', href)
                        if slug_match:
                            market_data['slug'] = slug_match.group(1)
            
            # Clean up question (remove common prefixes)
            if market_data.get('question'):
                question = market_data['question']
                # Remove "Polymarket - " prefix if present
                question = re.sub(r'^Polymarket\s*-\s*', '', question, flags=re.IGNORECASE)
                market_data['question'] = question.strip()
            
            if market_data.get('question') or market_data.get('slug'):
                logger.debug(f"[Web] Got market data for condition {condition_id[:20]}...")
                _save_to_cache(f"web_{condition_id}", market_data)
                return market_data
            
    except Exception as e:
        logger.debug(f"[Web] Failed to scrape market data: {e}")
    
    # Retry with different URL if failed
    if retry and not slug:
        try:
            # Try direct market URL with condition_id
            url = f"{POLYMARKET_BASE_URL}/market/{condition_id}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5"
            }
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                market_data = {}
                
                # Extract data (same logic as above)
                title_tag = soup.find('title')
                if title_tag:
                    title_text = title_tag.get_text(strip=True)
                    if title_text:
                        market_data['question'] = title_text.replace("Polymarket - ", "").strip()
                
                h1 = soup.find('h1')
                if h1:
                    h1_text = h1.get_text(strip=True)
                    if h1_text:
                        market_data['question'] = market_data.get('question') or h1_text.strip()
                
                if market_data.get('question'):
                    logger.debug(f"[Web] Got market data on retry for condition {condition_id[:20]}...")
                    _save_to_cache(f"web_{condition_id}", market_data)
                    return market_data
        except Exception as e:
            logger.debug(f"[Web] Retry failed: {e}")
    
    return None


async def get_market_data_from_playwright(condition_id: str, slug: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get market data using Playwright for JavaScript-rendered content (with caching)
    
    Args:
        condition_id: Market condition ID
        slug: Optional market slug
        
    Returns:
        Dict with market data or None if failed
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None
    
    # Check cache first
    cached_data = _get_from_cache(f"playwright_{condition_id}")
    if cached_data:
        logger.debug(f"[Playwright] Using cached data for condition {condition_id[:20]}...")
        return cached_data
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # Try to get data from market page
            if slug:
                url = f"{POLYMARKET_MARKET_URL}/{slug}"
            else:
                url = f"{POLYMARKET_BASE_URL}/search?q={condition_id}"
            
            await page.goto(url, wait_until="networkidle", timeout=15000)
            
            # Wait for content to load
            await page.wait_for_timeout(2000)
            
            # Extract market data from page
            market_data = {}
            
            # Try to get question from page title or h1
            try:
                title = await page.title()
                if title and "Polymarket" not in title:
                    market_data['question'] = title.replace("Polymarket - ", "").strip()
            except:
                pass
            
            # Try to get question from h1
            try:
                h1 = await page.query_selector('h1')
                if h1:
                    h1_text = await h1.inner_text()
                    if h1_text:
                        market_data['question'] = market_data.get('question') or h1_text.strip()
            except:
                pass
            
            # Try to get description from meta tags
            try:
                meta_desc = await page.query_selector('meta[property="og:description"]')
                if meta_desc:
                    desc = await meta_desc.get_attribute('content')
                    if desc:
                        market_data['description'] = desc.strip()
            except:
                pass
            
            # Try to get slug from URL
            current_url = page.url
            slug_match = re.search(r'/market/([^/?]+)', current_url)
            if slug_match:
                market_data['slug'] = slug_match.group(1)
            elif slug:
                market_data['slug'] = slug
            
            await browser.close()
            
            if market_data.get('question') or market_data.get('slug'):
                logger.debug(f"[Playwright] Got market data for condition {condition_id[:20]}...")
                _save_to_cache(f"playwright_{condition_id}", market_data)
                return market_data
            
    except Exception as e:
        logger.debug(f"[Playwright] Failed to scrape market data: {e}")
    
    return None


def get_market_data_enhanced(condition_id: str, slug: Optional[str] = None, question: Optional[str] = None) -> Dict[str, Any]:
    """
    Get market data from multiple sources (enhanced fallback chain)
    
    Priority:
    1. GraphQL API
    2. Web scraping (polymarket.com)
    3. Return empty dict (fallback to existing sources)
    
    Args:
        condition_id: Market condition ID
        slug: Optional market slug
        question: Optional market question
        
    Returns:
        Dict with market data (may be empty if all sources fail)
    """
    result = {}
    
    # Try GraphQL API first
    graphql_data = get_market_data_from_graphql(condition_id)
    if graphql_data:
        result.update(graphql_data)
        # If we got everything we need, return early
        if result.get('slug') and result.get('question'):
            return result
    
    # Try web scraping (BeautifulSoup)
    web_data = get_market_data_from_web(condition_id, slug)
    if web_data:
        # Merge web data (don't overwrite GraphQL data if present)
        for key, value in web_data.items():
            if key not in result or not result[key]:
                result[key] = value
    
    # Try Playwright if still missing data (for JavaScript-rendered content)
    if not result.get('question') or not result.get('slug'):
        if PLAYWRIGHT_AVAILABLE:
            try:
                import asyncio
                playwright_data = asyncio.run(get_market_data_from_playwright(condition_id, slug))
                if playwright_data:
                    # Merge Playwright data
                    for key, value in playwright_data.items():
                        if key not in result or not result[key]:
                            result[key] = value
            except Exception as e:
                logger.debug(f"[Enhanced] Playwright fallback failed: {e}")
    
    # Fill in provided data if missing
    if slug and not result.get('slug'):
        result['slug'] = slug
    if question and not result.get('question'):
        result['question'] = question
    
    return result


def enhance_market_data_for_classification(
    condition_id: str,
    existing_slug: Optional[str] = None,
    existing_question: Optional[str] = None,
    existing_description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Enhance market data for classification by trying additional sources
    
    This function tries to fill in missing data (slug, question, description)
    from enhanced sources if they're not available in existing data.
    
    Args:
        condition_id: Market condition ID
        existing_slug: Existing slug (if available)
        existing_question: Existing question (if available)
        existing_description: Existing description (if available)
        
    Returns:
        Dict with enhanced market data
    """
    # Initialize cache DB on first call
    if _cache_db_path is None:
        _init_cache_db()
    
    result = {
        'slug': existing_slug,
        'question': existing_question,
        'description': existing_description
    }
    
    # More aggressive: try enhanced sources even if we have some data
    # This helps with historical markets where data might be incomplete
    enhanced_data = get_market_data_enhanced(condition_id, existing_slug, existing_question)
    
    # Fill in missing fields (prefer enhanced data if existing is empty)
    if not result['slug'] and enhanced_data.get('slug'):
        result['slug'] = enhanced_data['slug']
    elif enhanced_data.get('slug') and len(enhanced_data['slug']) > len(result.get('slug', '')):
        # Use enhanced slug if it's more complete
        result['slug'] = enhanced_data['slug']
    
    if not result['question'] and enhanced_data.get('question'):
        result['question'] = enhanced_data['question']
    elif enhanced_data.get('question') and len(enhanced_data['question']) > len(result.get('question', '')):
        # Use enhanced question if it's more complete
        result['question'] = enhanced_data['question']
    
    if not result['description'] and enhanced_data.get('description'):
        result['description'] = enhanced_data.get('description')
    elif enhanced_data.get('description') and len(enhanced_data.get('description', '')) > len(result.get('description', '')):
        # Use enhanced description if it's more complete
        result['description'] = enhanced_data.get('description')
    
    # If still missing critical data, try Playwright directly (more aggressive)
    if (not result.get('slug') or not result.get('question')) and PLAYWRIGHT_AVAILABLE:
        try:
            import asyncio
            playwright_data = asyncio.run(get_market_data_from_playwright(condition_id, result.get('slug')))
            if playwright_data:
                # Merge Playwright data (prefer if more complete)
                for key, value in playwright_data.items():
                    if value and (not result.get(key) or len(str(value)) > len(str(result.get(key, '')))):
                        result[key] = value
        except Exception as e:
            logger.debug(f"[Enhanced] Direct Playwright attempt failed: {e}")
    
    return result

