#!/usr/bin/env python3
"""
Тестовый скрипт для проверки Gamma API
- Прямое тестирование через gamma_client.py
- Тестирование через price_fetcher.get_current_price (чтобы Source="gamma" использовался)
"""

import os
import sys
import json
import argparse
import logging
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

# Настройка логирования (только WARNING и выше, чтобы не засорять вывод)
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

from gamma_client import get_event_by_slug, get_event_by_condition_id
from price_fetcher import get_current_price

# Конфигурация
GAMMA_BASE_URL = os.getenv("GAMMA_BASE_URL", "https://gamma-api.polymarket.com")
REQUEST_TIMEOUT = 10


def get_events_page(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Получить список событий из Gamma API /events endpoint.
    
    Args:
        limit: Максимальное количество событий для получения
        
    Returns:
        List[Dict]: Список событий
    """
    import requests
    
    try:
        url = f"{GAMMA_BASE_URL}/events"
        params = {"limit": limit}
        
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            
            # Обработка разных форматов ответа
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("data") or data.get("events") or []
        
        return []
    except Exception as e:
        logger.error(f"Failed to get events: {type(e).__name__}: {e}")
        return []


def filter_events_with_prices(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Отфильтровать события, у которых есть markets с outcomePrices.
    
    Args:
        events: Список событий из Gamma API
        
    Returns:
        List[Dict]: Отфильтрованный список событий
    """
    filtered = []
    
    for event in events:
        markets = event.get("markets", [])
        if not markets:
            continue
        
        # Проверяем, есть ли хотя бы один market с outcomePrices
        for market in markets:
            outcome_prices_str = market.get("outcomePrices") or market.get("outcome_prices")
            if outcome_prices_str and outcome_prices_str.strip():
                filtered.append(event)
                break
    
    return filtered


def parse_outcome_prices(outcome_prices_str: str) -> Optional[List[float]]:
    """
    Распарсить outcomePrices из строки JSON в список float.
    
    Args:
        outcome_prices_str: Строка JSON с ценами
        
    Returns:
        List[float]: Список цен или None при ошибке
    """
    if not outcome_prices_str:
        return None
    
    try:
        if isinstance(outcome_prices_str, str):
            prices_list = json.loads(outcome_prices_str)
        elif isinstance(outcome_prices_str, list):
            prices_list = outcome_prices_str
        else:
            return None
        
        # Конвертируем в float
        return [float(p) for p in prices_list]
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.debug(f"Failed to parse outcomePrices: {e}")
        return None


def test_single_event(event: Dict[str, Any], outcome_index: int = 0, use_wallet_prices: bool = False) -> Dict[str, Any]:
    """
    Протестировать одно событие через Gamma API и price_fetcher.
    
    Args:
        event: Объект события из Gamma API
        outcome_index: Индекс исхода (0 = Yes, 1 = No)
        use_wallet_prices: Использовать ли тестовые wallet_prices
        
    Returns:
        Dict: Результаты теста
    """
    markets = event.get("markets", [])
    if not markets:
        return {"error": "No markets in event"}
    
    market = markets[0]
    
    # Извлекаем данные
    question = market.get("question") or event.get("title") or "N/A"
    slug = market.get("slug", "")
    condition_id = market.get("conditionId") or market.get("condition_id", "")
    outcome_prices_str = market.get("outcomePrices") or market.get("outcome_prices", "")
    
    # Парсим outcomePrices из Gamma
    gamma_prices = parse_outcome_prices(outcome_prices_str)
    gamma_price = gamma_prices[outcome_index] if gamma_prices and len(gamma_prices) > outcome_index else None
    
    # Тестируем через price_fetcher
    wallet_prices = None
    if use_wallet_prices:
        wallet_prices = {"0xtest1": 0.51, "0xtest2": 0.72}
    
    price, source = get_current_price(
        condition_id=condition_id if condition_id else None,
        outcome_index=outcome_index,
        slug=slug if slug else None,
        wallet_prices=wallet_prices
    )
    
    return {
        "question": question,
        "slug": slug,
        "condition_id": condition_id,
        "gamma_price": gamma_price,
        "gamma_prices": gamma_prices,
        "price": price,
        "source": source,
        "outcome_index": outcome_index
    }


def run_auto_mode(limit: int = 10):
    """
    Авто-режим: тестируем N событий из Gamma API.
    
    Args:
        limit: Количество событий для тестирования
    """
    print("=" * 80)
    print("🧪 Gamma API Auto Test Mode")
    print("=" * 80)
    print()
    
    print(f"📥 Fetching events from Gamma API (limit={limit * 2})...")
    events = get_events_page(limit=limit * 2)
    
    if not events:
        print("❌ Failed to fetch events from Gamma API")
        return
    
    print(f"✅ Got {len(events)} events")
    
    print(f"🔍 Filtering events with outcomePrices...")
    filtered_events = filter_events_with_prices(events)
    
    if not filtered_events:
        print("❌ No events with outcomePrices found")
        return
    
    print(f"✅ Found {len(filtered_events)} events with outcomePrices")
    
    # Берем первые limit событий
    test_events = filtered_events[:limit]
    print(f"📊 Testing {len(test_events)} events...")
    print()
    
    results = []
    success_count = 0
    gamma_source_count = 0
    
    for i, event in enumerate(test_events, 1):
        print(f"{'─' * 80}")
        print(f"[{i}/{len(test_events)}] Testing event...")
        
        result = test_single_event(event, outcome_index=0, use_wallet_prices=False)
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
            results.append(result)
            continue
        
        # Выводим результаты
        print(f"Event: {result['question'][:80]}")
        print(f"Slug: {result['slug'][:80] if result['slug'] else 'N/A'}")
        print(f"Condition ID: {result['condition_id'][:50] if result['condition_id'] else 'N/A'}")
        
        if result['gamma_price'] is not None:
            print(f"Gamma outcomePrices[0]: {result['gamma_price']:.6f}")
        else:
            print(f"Gamma outcomePrices[0]: N/A")
        
        print()
        print(f"get_current_price():")
        if result['price'] is not None:
            print(f"  → price: {result['price']:.6f}")
            success_count += 1
        else:
            print(f"  → price: N/A")
        
        if result['source']:
            print(f"  → source: {result['source']}")
            if result['source'] == "gamma":
                gamma_source_count += 1
        else:
            print(f"  → source: none")
        
        results.append(result)
        print()
    
    # Сводка
    print("=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print(f"Total events tested: {len(results)}")
    print(f"✅ Success (price found): {success_count}")
    print(f"🔗 Gamma source used: {gamma_source_count}")
    print(f"⚠️  No price: {len(results) - success_count}")
    print()


def run_manual_mode(slug: Optional[str] = None, 
                   condition_id: Optional[str] = None,
                   outcome_index: int = 0,
                   use_wallet_prices: bool = False):
    """
    Ручной режим: тестируем конкретный slug или condition_id.
    
    Args:
        slug: Slug рынка
        condition_id: Condition ID рынка
        outcome_index: Индекс исхода (0 = Yes, 1 = No)
        use_wallet_prices: Использовать ли тестовые wallet_prices
    """
    print("=" * 80)
    print("🧪 Gamma API Manual Test Mode")
    print("=" * 80)
    print()
    
    event = None
    
    # Получаем событие через gamma_client
    if slug:
        print(f"📥 Fetching event by slug: {slug[:80]}...")
        event = get_event_by_slug(slug)
        if event:
            print("✅ Got event by slug")
        else:
            print("❌ Failed to get event by slug")
            return
    elif condition_id:
        print(f"📥 Fetching event by condition_id: {condition_id[:50]}...")
        event = get_event_by_condition_id(condition_id)
        if event:
            print("✅ Got event by condition_id")
        else:
            print("❌ Failed to get event by condition_id")
            return
    else:
        print("❌ No slug or condition_id provided")
        return
    
    print()
    
    # Тестируем событие
    result = test_single_event(event, outcome_index=outcome_index, use_wallet_prices=use_wallet_prices)
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return
    
    # Выводим результаты
    print(f"{'─' * 80}")
    print(f"Event: {result['question'][:80]}")
    print(f"Slug: {result['slug'][:80] if result['slug'] else 'N/A'}")
    print(f"Condition ID: {result['condition_id'][:50] if result['condition_id'] else 'N/A'}")
    print(f"Outcome index: {result['outcome_index']}")
    
    if result['gamma_prices']:
        print(f"Gamma outcomePrices: {result['gamma_prices']}")
        if result['gamma_price'] is not None:
            print(f"Gamma outcomePrices[{result['outcome_index']}]: {result['gamma_price']:.6f}")
    else:
        print(f"Gamma outcomePrices: N/A")
    
    print()
    print(f"get_current_price():")
    if result['price'] is not None:
        print(f"  → price: {result['price']:.6f}")
    else:
        print(f"  → price: N/A")
    
    if result['source']:
        print(f"  → source: {result['source']}")
        if result['source'] == "gamma":
            print(f"  ✅ SUCCESS: Gamma API is being used!")
        else:
            print(f"  ⚠️  WARNING: Gamma API not used (source: {result['source']})")
    else:
        print(f"  → source: none")
        print(f"  ❌ ERROR: No source returned")
    
    print()


def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(
        description="Test Gamma API integration (gamma_client.py and price_fetcher.get_current_price)"
    )
    
    # Режимы работы
    parser.add_argument(
        "--auto",
        action="store_true",
        default=True,
        help="Auto mode: test N events from Gamma API (default)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of events to test in auto mode (default: 10)"
    )
    
    # Ручной режим
    parser.add_argument(
        "--slug",
        type=str,
        help="Market slug for manual test (e.g., 'will-gemini-3pt0-be-released-by-november-15')"
    )
    parser.add_argument(
        "--condition-id",
        type=str,
        help="Market condition ID for manual test (e.g., '0xabc123...')"
    )
    parser.add_argument(
        "--outcome-index",
        type=int,
        default=0,
        help="Outcome index (0=Yes, 1=No). Default: 0"
    )
    parser.add_argument(
        "--use-wallet-prices",
        action="store_true",
        help="If set, pass test wallet_prices fallback [0.51, 0.72]"
    )
    
    args = parser.parse_args()
    
    # Определяем режим работы
    if args.slug or args.condition_id:
        # Ручной режим
        run_manual_mode(
            slug=args.slug,
            condition_id=args.condition_id,
            outcome_index=args.outcome_index,
            use_wallet_prices=args.use_wallet_prices
        )
    else:
        # Авто-режим
        run_auto_mode(limit=args.limit)


if __name__ == "__main__":
    main()

