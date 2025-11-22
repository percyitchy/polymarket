"""
Клиент для работы с Gamma API Polymarket
"""

import os
import logging
import json
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Базовый URL Gamma API
GAMMA_BASE_URL = os.getenv("GAMMA_BASE_URL", "https://gamma-api.polymarket.com")
# Альтернативный вариант (если первый не работает)
GAMMA_BASE_URL_ALT = "https://gamma.polymarket.com/api"
# GraphQL endpoint для получения данных о рынках
GRAPHQL_ENDPOINT = "https://gamma-api.polymarket.com/graphql"
GRAPHQL_ENDPOINT_ALT = "https://polymarket.com/graphql"

# Конфигурация таймаутов
REQUEST_TIMEOUT = 5  # секунды
GRAPHQL_TIMEOUT = 10  # секунды для GraphQL запросов


def get_event_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """
    Возвращает объект события Gamma по slug через endpoint /events.
    
    Структура Gamma API:
    - /events возвращает список событий
    - Каждое событие имеет поле "markets" (массив)
    - Каждый market имеет "slug" и "outcomePrices" (строка JSON)
    
    Args:
        slug: Slug рынка (например, "will-trump-win-2024-election")
            Must be reasonably specific to avoid ambiguous matches. For short slugs,
            exact matches are prioritized. Partial matches (endswith) are only used
            when exact match fails and the slug appears to be a base slug with
            appended IDs.
        
    Returns:
        dict: Объект события с полями markets и другими данными, или None при ошибке
    """
    try:
        logger.info(f"[GAMMA] Requesting event by slug: {slug[:50]}...")
        
        # Gamma API: /events возвращает список событий, нужно искать по slug в markets
        # Приоритет поиска: featured (breaking) → trending → обычные события
        url = f"{GAMMA_BASE_URL}/events"
        
        # Шаг 1: Пробуем featured события (breaking/popular) - они более актуальные
        params = {"featured": "true", "limit": 200}
        
        logger.debug(f"[GAMMA] URL: {url}, searching for slug in markets...")
        
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT * 2)  # Увеличиваем таймаут для большого запроса
        logger.info(f"[GAMMA] Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Обработка разных форматов ответа
            events = []
            if isinstance(data, list):
                events = data
            elif isinstance(data, dict):
                events = data.get("data") or data.get("events") or []
            
            # Ищем событие, где в markets есть market с нужным slug
            # Normalize slug: strip common prefixes
            slug_normalized = slug.strip().strip('/')
            if slug_normalized.startswith('event/'):
                slug_normalized = slug_normalized[6:]
            if slug_normalized.startswith('market/'):
                slug_normalized = slug_normalized[7:]
            
            for event in events:
                markets = event.get("markets", [])
                for market in markets:
                    market_slug = market.get("slug", "")
                    if not market_slug:
                        continue
                    
                    # Normalize market_slug similarly
                    market_slug_normalized = market_slug.strip().strip('/')
                    if market_slug_normalized.startswith('event/'):
                        market_slug_normalized = market_slug_normalized[6:]
                    if market_slug_normalized.startswith('market/'):
                        market_slug_normalized = market_slug_normalized[7:]
                    
                    # Priority 1: Exact match (after normalization)
                    if market_slug_normalized == slug_normalized or market_slug == slug:
                        logger.debug(f"[GAMMA] ✅ Found event with exact market slug match: {market_slug[:50]}...")
                        
                        # Log event structure
                        logger.debug(f"[GAMMA] [DEBUG] Event structure:")
                        logger.debug(f"[GAMMA] [DEBUG]   - Event keys: {list(event.keys())}")
                        logger.debug(f"[GAMMA] [DEBUG]   - Event id: {event.get('id')}")
                        logger.debug(f"[GAMMA] [DEBUG]   - Event slug: {event.get('slug')}")
                        logger.debug(f"[GAMMA] [DEBUG]   - Event category: {event.get('category')}")
                        logger.debug(f"[GAMMA] [DEBUG]   - Event type: {event.get('type')}")
                        logger.debug(f"[GAMMA] [DEBUG]   - Event groupType: {event.get('groupType')}")
                        logger.debug(f"[GAMMA] [DEBUG]   - Event tags: {event.get('tags')}")
                        logger.debug(f"[GAMMA] [DEBUG]   - Number of markets: {len(markets)}")
                        if markets:
                            logger.debug(f"[GAMMA] [DEBUG]   - First market keys: {list(markets[0].keys())}")
                        
                        # Log sample event object as JSON (truncated)
                        try:
                            event_json = json.dumps(event, indent=2, default=str)
                            event_json_truncated = event_json[:1500]
                            logger.debug(f"[GAMMA] [DEBUG]   - Sample event object (first 1500 chars): {event_json_truncated}")
                        except Exception as e:
                            logger.debug(f"[GAMMA] [DEBUG]   - Failed to serialize event object: {e}")
                        
                        return event
                    
                    # Priority 2: endswith match (only if slug appears to be a base slug with appended ID)
                    # This handles cases where market_slug might be "base-slug-123" and slug is "base-slug"
                    # Only use if slug doesn't contain the market_slug (to avoid false positives)
                    if market_slug_normalized.endswith(slug_normalized) and slug_normalized not in market_slug_normalized[:-len(slug_normalized)]:
                        # Additional check: ensure slug is not too short to avoid wrong matches
                        if len(slug_normalized) >= 5:  # Minimum length to avoid ambiguous short matches
                            logger.debug(f"[GAMMA] ✅ Found event with market slug ending with slug: {market_slug[:50]}...")
                            
                            # Log event structure
                            logger.debug(f"[GAMMA] [DEBUG] Event structure:")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event keys: {list(event.keys())}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event id: {event.get('id')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event slug: {event.get('slug')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event category: {event.get('category')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event type: {event.get('type')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event groupType: {event.get('groupType')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event tags: {event.get('tags')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Number of markets: {len(markets)}")
                            if markets:
                                logger.debug(f"[GAMMA] [DEBUG]   - First market keys: {list(markets[0].keys())}")
                            
                            # Log sample event object as JSON (truncated)
                            try:
                                event_json = json.dumps(event, indent=2, default=str)
                                event_json_truncated = event_json[:1500]
                                logger.debug(f"[GAMMA] [DEBUG]   - Sample event object (first 1500 chars): {event_json_truncated}")
                            except Exception as e:
                                logger.debug(f"[GAMMA] [DEBUG]   - Failed to serialize event object: {e}")
                            
                            return event
            
            logger.debug(f"[GAMMA] Event with slug={slug[:50]}... not found in {len(events)} featured events, trying trending events...")
            
            # Шаг 2: Fallback - пробуем trending события
            params_trending = {"trending": "true", "limit": 200}
            response_trending = requests.get(url, params=params_trending, timeout=REQUEST_TIMEOUT * 2)
            
            if response_trending.status_code == 200:
                data_trending = response_trending.json()
                events_trending = []
                if isinstance(data_trending, list):
                    events_trending = data_trending
                elif isinstance(data_trending, dict):
                    events_trending = data_trending.get("data") or data_trending.get("events") or []
                
                # Ищем в trending событиях
                for event in events_trending:
                    markets = event.get("markets", [])
                    for market in markets:
                        market_slug = market.get("slug", "")
                        if not market_slug:
                            continue
                        
                        # Normalize market_slug similarly
                        market_slug_normalized = market_slug.strip().strip('/')
                        if market_slug_normalized.startswith('event/'):
                            market_slug_normalized = market_slug_normalized[6:]
                        if market_slug_normalized.startswith('market/'):
                            market_slug_normalized = market_slug_normalized[7:]
                        
                        # Priority 1: Exact match (after normalization)
                        if market_slug_normalized == slug_normalized or market_slug == slug:
                            logger.debug(f"[GAMMA] ✅ Found event with exact market slug match: {market_slug[:50]}... in trending events")
                            
                            # Log event structure
                            logger.debug(f"[GAMMA] [DEBUG] Event structure (trending):")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event keys: {list(event.keys())}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event id: {event.get('id')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event slug: {event.get('slug')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event category: {event.get('category')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event type: {event.get('type')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event groupType: {event.get('groupType')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event tags: {event.get('tags')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Number of markets: {len(markets)}")
                            if markets:
                                logger.debug(f"[GAMMA] [DEBUG]   - First market keys: {list(markets[0].keys())}")
                            
                            return event
                        
                        # Priority 2: endswith match (only if slug appears to be a base slug with appended ID)
                        if market_slug_normalized.endswith(slug_normalized) and slug_normalized not in market_slug_normalized[:-len(slug_normalized)]:
                            if len(slug_normalized) >= 5:
                                logger.debug(f"[GAMMA] ✅ Found event with market slug ending with slug: {market_slug[:50]}... in trending events")
                                
                                # Log event structure
                                logger.debug(f"[GAMMA] [DEBUG] Event structure (trending):")
                                logger.debug(f"[GAMMA] [DEBUG]   - Event keys: {list(event.keys())}")
                                logger.debug(f"[GAMMA] [DEBUG]   - Event id: {event.get('id')}")
                                logger.debug(f"[GAMMA] [DEBUG]   - Event slug: {event.get('slug')}")
                                logger.debug(f"[GAMMA] [DEBUG]   - Event category: {event.get('category')}")
                                logger.debug(f"[GAMMA] [DEBUG]   - Event type: {event.get('type')}")
                                logger.debug(f"[GAMMA] [DEBUG]   - Event groupType: {event.get('groupType')}")
                                logger.debug(f"[GAMMA] [DEBUG]   - Event tags: {event.get('tags')}")
                                logger.debug(f"[GAMMA] [DEBUG]   - Number of markets: {len(markets)}")
                                if markets:
                                    logger.debug(f"[GAMMA] [DEBUG]   - First market keys: {list(markets[0].keys())}")
                                
                                return event
                
                logger.debug(f"[GAMMA] Event with slug={slug[:50]}... not found in {len(events_trending)} trending events, trying regular events...")
            
            # Шаг 3: Fallback - пробуем обычные события (не featured/trending)
            params_regular = {"limit": 500}
            response_regular = requests.get(url, params=params_regular, timeout=REQUEST_TIMEOUT * 2)
            
            if response_regular.status_code == 200:
                data_regular = response_regular.json()
                events_regular = []
                if isinstance(data_regular, list):
                    events_regular = data_regular
                elif isinstance(data_regular, dict):
                    events_regular = data_regular.get("data") or data_regular.get("events") or []
                
                # Ищем в обычных событиях
                for event in events_regular:
                    markets = event.get("markets", [])
                    for market in markets:
                        market_slug = market.get("slug", "")
                        if not market_slug:
                            continue
                        
                        # Normalize market_slug similarly
                        market_slug_normalized = market_slug.strip().strip('/')
                        if market_slug_normalized.startswith('event/'):
                            market_slug_normalized = market_slug_normalized[6:]
                        if market_slug_normalized.startswith('market/'):
                            market_slug_normalized = market_slug_normalized[7:]
                        
                        # Priority 1: Exact match (after normalization)
                        if market_slug_normalized == slug_normalized or market_slug == slug:
                            logger.debug(f"[GAMMA] ✅ Found event with exact market slug match: {market_slug[:50]}... in regular events")
                            
                            # Log event structure
                            logger.debug(f"[GAMMA] [DEBUG] Event structure (regular):")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event keys: {list(event.keys())}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event id: {event.get('id')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event slug: {event.get('slug')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event category: {event.get('category')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event type: {event.get('type')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event groupType: {event.get('groupType')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event tags: {event.get('tags')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Number of markets: {len(markets)}")
                            if markets:
                                logger.debug(f"[GAMMA] [DEBUG]   - First market keys: {list(markets[0].keys())}")
                            
                            return event
                        
                        # Priority 2: endswith match (only if slug appears to be a base slug with appended ID)
                        if market_slug_normalized.endswith(slug_normalized) and slug_normalized not in market_slug_normalized[:-len(slug_normalized)]:
                            if len(slug_normalized) >= 5:
                                logger.debug(f"[GAMMA] ✅ Found event with market slug ending with slug: {market_slug[:50]}... in regular events")
                                
                                # Log event structure
                                logger.debug(f"[GAMMA] [DEBUG] Event structure (regular):")
                                logger.debug(f"[GAMMA] [DEBUG]   - Event keys: {list(event.keys())}")
                                logger.debug(f"[GAMMA] [DEBUG]   - Event id: {event.get('id')}")
                                logger.debug(f"[GAMMA] [DEBUG]   - Event slug: {event.get('slug')}")
                                logger.debug(f"[GAMMA] [DEBUG]   - Event category: {event.get('category')}")
                                logger.debug(f"[GAMMA] [DEBUG]   - Event type: {event.get('type')}")
                                logger.debug(f"[GAMMA] [DEBUG]   - Event groupType: {event.get('groupType')}")
                                logger.debug(f"[GAMMA] [DEBUG]   - Event tags: {event.get('tags')}")
                                logger.debug(f"[GAMMA] [DEBUG]   - Number of markets: {len(markets)}")
                                if markets:
                                    logger.debug(f"[GAMMA] [DEBUG]   - First market keys: {list(markets[0].keys())}")
                                
                                return event
                
                logger.debug(f"[GAMMA] Event with slug={slug[:50]}... not found in {len(events_regular)} regular events either")
            
            return None
        else:
            logger.warning(f"[GAMMA] ❌ Failed to get events: HTTP {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        logger.warning(f"[GAMMA] ❌ Timeout ({REQUEST_TIMEOUT * 2}s) getting event by slug={slug[:50]}...")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"[GAMMA] ❌ Request error getting event by slug: {type(e).__name__}: {e}")
        return None
    except Exception as e:
        logger.warning(f"[GAMMA] ❌ Unexpected error getting event by slug: {type(e).__name__}: {e}")
        return None


def get_event_by_condition_id(condition_id: str) -> Optional[Dict[str, Any]]:
    """
    Возвращает объект события Gamma по condition_id.
    Использует GraphQL API как приоритетный источник, затем /events endpoint с фильтрацией по conditionId.
    
    Args:
        condition_id: ID условия рынка (hex string)
        
    Returns:
        dict: Объект события с полями outcomePrices и другими данными, или None при ошибке
    """
    # Приоритет 1: Пробуем GraphQL API (более надежный для получения данных о рынках)
    try:
        graphql_query = """
        query GetMarket($conditionId: String!) {
            market(conditionId: $conditionId) {
                id
                slug
                question
                title
                description
                category
                tags
                endDate
                active
                event {
                    id
                    slug
                    title
                    category
                    tags
                    markets {
                        conditionId
                        slug
                        question
                        id
                    }
                }
            }
        }
        """
        
        variables = {"conditionId": condition_id}
        payload = {
            "query": graphql_query,
            "variables": variables
        }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; PolymarketNotifier/1.0)"
        }
        
        # Пробуем оба GraphQL endpoints
        for graphql_url in [GRAPHQL_ENDPOINT, GRAPHQL_ENDPOINT_ALT]:
            try:
                logger.info(f"[GAMMA] [GraphQL] Requesting market by condition_id: {condition_id[:20]}...")
                logger.debug(f"[GAMMA] [GraphQL] URL: {graphql_url}")
                
                response = requests.post(graphql_url, json=payload, headers=headers, timeout=GRAPHQL_TIMEOUT)
                logger.info(f"[GAMMA] [GraphQL] Response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    if "data" in data and data["data"] and "market" in data["data"]:
                        market_data = data["data"]["market"]
                        if market_data:
                            # Преобразуем GraphQL ответ в формат, совместимый с REST API
                            event_data = market_data.get("event")
                            if event_data:
                                # Создаем структуру события с рынками
                                event = {
                                    "id": event_data.get("id"),
                                    "slug": event_data.get("slug"),
                                    "title": event_data.get("title"),
                                    "category": event_data.get("category"),
                                    "tags": event_data.get("tags"),
                                    "markets": event_data.get("markets", [])
                                }
                                
                                # Добавляем текущий рынок в список markets если его там нет
                                market_found = False
                                for market in event["markets"]:
                                    if market.get("conditionId", "").lower() == condition_id.lower():
                                        market_found = True
                                        break
                                
                                if not market_found:
                                    event["markets"].append({
                                        "conditionId": condition_id,
                                        "slug": market_data.get("slug"),
                                        "question": market_data.get("question"),
                                        "id": market_data.get("id")
                                    })
                                
                                logger.info(f"[GAMMA] [GraphQL] ✅ Found event via GraphQL API: slug={event.get('slug', 'N/A')[:50]}...")
                                return event
                            else:
                                # Если нет event, создаем минимальную структуру из market данных
                                logger.debug(f"[GAMMA] [GraphQL] No event data, creating minimal structure from market")
                                event = {
                                    "id": market_data.get("id"),
                                    "slug": market_data.get("slug"),
                                    "title": market_data.get("title"),
                                    "category": market_data.get("category"),
                                    "tags": market_data.get("tags"),
                                    "markets": [{
                                        "conditionId": condition_id,
                                        "slug": market_data.get("slug"),
                                        "question": market_data.get("question"),
                                        "id": market_data.get("id")
                                    }]
                                }
                                logger.info(f"[GAMMA] [GraphQL] ✅ Created event structure from market data")
                                return event
            except requests.exceptions.Timeout:
                logger.debug(f"[GAMMA] [GraphQL] Timeout for {graphql_url}, trying next endpoint...")
                continue
            except requests.exceptions.RequestException as e:
                logger.debug(f"[GAMMA] [GraphQL] Request error for {graphql_url}: {type(e).__name__}, trying REST API...")
                continue
            except Exception as e:
                logger.debug(f"[GAMMA] [GraphQL] Unexpected error for {graphql_url}: {type(e).__name__}, trying REST API...")
                continue
    except Exception as e:
        logger.debug(f"[GAMMA] [GraphQL] Failed to use GraphQL API: {e}, falling back to REST API")
    
    # Приоритет 2: Пробуем REST API endpoints (fallback)
    endpoints = [
        f"{GAMMA_BASE_URL}/events",
        f"{GAMMA_BASE_URL}/events?conditionId={condition_id}",
        f"{GAMMA_BASE_URL_ALT}/events",
    ]
    
    for url in endpoints:
        try:
            params = {}
            if "conditionId=" not in url:
                params["conditionId"] = condition_id
            
            logger.info(f"[GAMMA] Requesting event by condition_id: {condition_id[:20]}...")
            logger.debug(f"[GAMMA] URL: {url}, params: {params}")
            
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            logger.info(f"[GAMMA] Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Обработка разных форматов ответа
                events = []
                if isinstance(data, list):
                    events = data
                elif isinstance(data, dict):
                    events = data.get("data") or data.get("events") or []
                
                # Ищем событие, где в markets есть market с нужным condition_id
                for event in events:
                    markets = event.get("markets", [])
                    for market in markets:
                        market_condition_id = market.get("conditionId") or market.get("condition_id")
                        if market_condition_id and market_condition_id.lower() == condition_id.lower():
                            logger.debug(f"[GAMMA] ✅ Found event with market condition_id={condition_id[:20]}...")
                            
                            # Log event structure
                            logger.debug(f"[GAMMA] [DEBUG] Event structure:")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event keys: {list(event.keys())}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event category: {event.get('category')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event type: {event.get('type')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event groupType: {event.get('groupType')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Event tags: {event.get('tags')}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Matching market keys: {list(market.keys())}")
                            logger.debug(f"[GAMMA] [DEBUG]   - Matching market slug: {market.get('slug')}")
                            
                            # Log URL-related fields in market
                            url_fields = {}
                            for key in ['url', 'path', 'pagePath', 'webUrl', 'sportsUrl', 'link', 'permalink', 'canonicalUrl']:
                                if key in market:
                                    url_fields[key] = market[key]
                            if url_fields:
                                logger.debug(f"[GAMMA] [DEBUG]   - URL-related fields in market: {url_fields}")
                            
                            # Log sample event object as JSON (truncated)
                            try:
                                event_json = json.dumps(event, indent=2, default=str)
                                event_json_truncated = event_json[:1500]
                                logger.debug(f"[GAMMA] [DEBUG]   - Sample event object (first 1500 chars): {event_json_truncated}")
                            except Exception as e:
                                logger.debug(f"[GAMMA] [DEBUG]   - Failed to serialize event object: {e}")
                            
                            return event
                
                logger.debug(f"[GAMMA] Event with condition_id={condition_id[:20]}... not found in response")
                return None
            elif response.status_code == 404:
                logger.debug(f"[GAMMA] Events endpoint not found (404)")
                continue  # Пробуем следующий endpoint
            else:
                logger.debug(f"[GAMMA] Failed with status {response.status_code}, trying next endpoint...")
                continue
                
        except requests.exceptions.Timeout:
            logger.debug(f"[GAMMA] Timeout for {url}, trying next endpoint...")
            continue
        except requests.exceptions.RequestException as e:
            logger.debug(f"[GAMMA] Request error for {url}: {type(e).__name__}, trying next endpoint...")
            continue
        except Exception as e:
            logger.debug(f"[GAMMA] Unexpected error for {url}: {type(e).__name__}, trying next endpoint...")
            continue
    
    logger.warning(f"[GAMMA] ❌ Failed to get event by condition_id={condition_id[:20]}... from all endpoints")
    return None


def get_event_by_id(event_id: str | int) -> Optional[Dict[str, Any]]:
    """
    Возвращает канонический объект события (event) по event_id из Gamma API.
    Использует endpoint /events/{event_id} для получения канонического event.
    
    Канонический event содержит правильный event slug (не market-specific),
    полный список markets, и другие метаданные события.
    
    Args:
        event_id: ID события (может быть строкой или числом)
        
    Returns:
        dict: Канонический объект события с полями slug, markets, url и другими данными, или None при ошибке
    """
    # Пробуем несколько вариантов endpoints
    endpoints = [
        f"{GAMMA_BASE_URL}/events/{event_id}",
        f"{GAMMA_BASE_URL_ALT}/events/{event_id}",
    ]
    
    for url in endpoints:
        try:
            logger.info(f"[GAMMA] Requesting canonical event by id: {event_id}")
            logger.debug(f"[GAMMA] URL: {url}")
            
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            logger.info(f"[GAMMA] Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Обработка разных форматов ответа
                event = None
                if isinstance(data, dict):
                    # Может быть обёрнут в data или быть напрямую event
                    event = data.get("data") or data.get("event") or data
                elif isinstance(data, list) and len(data) > 0:
                    # Если вернулся список, берём первый элемент
                    event = data[0]
                
                if event and isinstance(event, dict):
                    logger.debug(f"[GAMMA] ✅ Got canonical event by id={event_id}, slug={event.get('slug', 'N/A')[:50]}...")
                    
                    # Log canonical event structure
                    logger.debug(f"[GAMMA] [DEBUG] Canonical event structure:")
                    logger.debug(f"[GAMMA] [DEBUG]   - Event keys: {list(event.keys())}")
                    logger.debug(f"[GAMMA] [DEBUG]   - Event id: {event.get('id')}")
                    logger.debug(f"[GAMMA] [DEBUG]   - Event slug: {event.get('slug')}")
                    logger.debug(f"[GAMMA] [DEBUG]   - Event category: {event.get('category')}")
                    logger.debug(f"[GAMMA] [DEBUG]   - Event type: {event.get('type')}")
                    logger.debug(f"[GAMMA] [DEBUG]   - Event groupType: {event.get('groupType')}")
                    logger.debug(f"[GAMMA] [DEBUG]   - Event tags: {event.get('tags')}")
                    logger.debug(f"[GAMMA] [DEBUG]   - Number of markets: {len(event.get('markets', []))}")
                    
                    # Log URL-related fields at event level
                    url_fields = {}
                    for key in ['url', 'path', 'pagePath', 'webUrl', 'sportsUrl', 'link', 'permalink', 'canonicalUrl']:
                        if key in event:
                            url_fields[key] = event[key]
                    if url_fields:
                        logger.debug(f"[GAMMA] [DEBUG]   - URL-related fields: {url_fields}")
                    
                    # Log sample canonical event object as JSON (truncated)
                    try:
                        event_json = json.dumps(event, indent=2, default=str)
                        event_json_truncated = event_json[:1500]
                        logger.debug(f"[GAMMA] [DEBUG]   - Sample canonical event (first 1500 chars): {event_json_truncated}")
                    except Exception as e:
                        logger.debug(f"[GAMMA] [DEBUG]   - Failed to serialize event object: {e}")
                    
                    return event
                else:
                    logger.warning(f"[GAMMA] Invalid event format returned for id={event_id}")
                    continue
                    
            elif response.status_code == 404:
                logger.debug(f"[GAMMA] Event {event_id} not found (404)")
                continue  # Пробуем следующий endpoint
            else:
                logger.debug(f"[GAMMA] Failed with status {response.status_code} for event_id={event_id}, trying next endpoint...")
                continue
                
        except requests.exceptions.Timeout:
            logger.debug(f"[GAMMA] Timeout for {url}, trying next endpoint...")
            continue
        except requests.exceptions.RequestException as e:
            logger.debug(f"[GAMMA] Request error for {url}: {type(e).__name__}, trying next endpoint...")
            continue
        except Exception as e:
            logger.debug(f"[GAMMA] Unexpected error for {url}: {type(e).__name__}, trying next endpoint...")
            continue
    
    logger.warning(f"[GAMMA] ❌ Failed to get canonical event by id={event_id} from all endpoints")
    return None

