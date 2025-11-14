"""
Клиент для работы с Gamma API Polymarket
"""

import os
import logging
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Базовый URL Gamma API
GAMMA_BASE_URL = os.getenv("GAMMA_BASE_URL", "https://gamma-api.polymarket.com")
# Альтернативный вариант (если первый не работает)
GAMMA_BASE_URL_ALT = "https://gamma.polymarket.com/api"

# Конфигурация таймаутов
REQUEST_TIMEOUT = 5  # секунды


def get_event_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """
    Возвращает объект события Gamma по slug через endpoint /events.
    
    Структура Gamma API:
    - /events возвращает список событий
    - Каждое событие имеет поле "markets" (массив)
    - Каждый market имеет "slug" и "outcomePrices" (строка JSON)
    
    Args:
        slug: Slug рынка (например, "will-trump-win-2024-election")
        
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
            for event in events:
                markets = event.get("markets", [])
                for market in markets:
                    market_slug = market.get("slug", "")
                    # Точное совпадение или частичное (на случай различий в формате)
                    if market_slug == slug or market_slug.endswith(slug) or slug in market_slug:
                        logger.debug(f"[GAMMA] ✅ Found event with market slug={market_slug[:50]}...")
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
                        if market_slug == slug or market_slug.endswith(slug) or slug in market_slug:
                            logger.debug(f"[GAMMA] ✅ Found event with market slug={market_slug[:50]}... in trending events")
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
                        if market_slug == slug or market_slug.endswith(slug) or slug in market_slug:
                            logger.debug(f"[GAMMA] ✅ Found event with market slug={market_slug[:50]}... in regular events")
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
    Использует /events endpoint с фильтрацией по conditionId.
    
    Args:
        condition_id: ID условия рынка (hex string)
        
    Returns:
        dict: Объект события с полями outcomePrices и другими данными, или None при ошибке
    """
    # Пробуем несколько вариантов endpoints
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

