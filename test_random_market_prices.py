#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работоспособности всех источников цен
(CLOB, HashiDive, FinFeed, trades, wallet fallback)
"""

import os
import sys
import requests
import json
import time
import random
import argparse
from typing import Optional, Dict, List, Tuple
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from price_fetcher import get_current_price


def check_clob_api_key() -> None:
    """
    Проверка конфигурации и доступности CLOB API ключа.
    
    Выполняет тестовый запрос к CLOB API для проверки авторизации.
    Не кидает исключения - только логирует результат.
    """
    api_key = os.getenv("PM_API_KEY")
    
    if not api_key or not api_key.strip():
        print("🔑 CLOB status: NOT CONFIGURED (PM_API_KEY is empty) — skipping CLOB tests")
        return
    
    try:
        # Делаем простой тестовый запрос к публичному endpoint /markets
        # Используем известный condition_id для проверки авторизации
        test_condition_id = "0x23e6e6f8a327a41bad1282fdc34e846f52e73e390d44b004ac92a329766e2848"  # Eagles vs Packers
        url = f"https://clob.polymarket.com/markets/{test_condition_id}"
        
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        
        # Делаем запрос с коротким таймаутом для быстрой проверки
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            print("🔑 CLOB status: OK (authorized, response 200)")
        elif response.status_code == 401:
            print(f"🔑 CLOB status: UNAUTHORIZED (HTTP 401) — check PM_API_KEY")
        elif response.status_code == 403:
            print(f"🔑 CLOB status: UNAUTHORIZED (HTTP 403) — check PM_API_KEY permissions")
        elif response.status_code >= 500:
            error_msg = response.text[:100] if response.text else "Server error"
            print(f"🔑 CLOB status: ERROR (HTTP {response.status_code}: {error_msg})")
        else:
            error_msg = response.text[:100] if response.text else "Unknown error"
            print(f"🔑 CLOB status: ERROR (HTTP {response.status_code}: {error_msg})")
            
    except requests.exceptions.Timeout:
        print("🔑 CLOB status: ERROR (timeout) — CLOB API not responding")
    except requests.exceptions.RequestException as e:
        error_msg = str(e)[:100] if str(e) else "Network error"
        print(f"🔑 CLOB status: ERROR (network error: {error_msg})")
    except Exception as e:
        error_msg = str(e)[:100] if str(e) else "Unknown error"
        print(f"🔑 CLOB status: ERROR (unexpected error: {error_msg})")


def get_active_markets(limit: int = 10) -> List[Dict]:
    """
    Получить список активных рынков из Polymarket Data API
    
    Args:
        limit: Количество рынков для получения
        
    Returns:
        List[Dict]: Список словарей с информацией о рынках
    """
    try:
        # Попробуем несколько вариантов endpoints
        endpoints = [
            "https://data-api.polymarket.com/events",
            "https://clob.polymarket.com/markets",
            "https://data-api.polymarket.com/markets"
        ]
        
        markets = []
        for url in endpoints:
            params = {
                "limit": limit * 2,
            }
            
            try:
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        markets = data
                    elif isinstance(data, dict):
                        markets = data.get("data") or data.get("markets") or data.get("events") or []
                    break
            except:
                continue
        
        if not markets:
            # Fallback: используем тестовые condition_id из известных рынков
            print(f"⚠️  API недоступен, используем тестовые condition_id...")
            return [
                {
                    "conditionId": "0x23e6e6f8a327a41bad1282fdc34e846f52e73e390d44b004ac92a329766e2848",
                    "question": "Eagles vs. Packers",
                    "slug": "nfl-phi-gb-2025-11-10"
                },
                {
                    "conditionId": "0x319a2f28b0de6794f3f951b7f4604d63caaeefe91a01659305189c3bc40a61be",
                    "question": "Lakers vs. Hornets",
                    "slug": "nba-lal-cha-2025-11-11"
                },
                {
                    "conditionId": "0x312342f1015274a3f9b1b691238266c14f008ff499f03701c2978fec441b50ee",
                    "question": "MicroStrategy announces >1000 BTC purchase",
                    "slug": "microstrategy-btc-purchase"
                }
            ][:limit]
        
        # Фильтруем только активные рынки
        active_markets = []
        for market in markets:
            status = market.get("status") or market.get("state")
            # Активные статусы: 'open', 'active', None (если не указан, считаем активным)
            if status in ('open', 'active', None) or status is None:
                active_markets.append(market)
                if len(active_markets) >= limit:
                    break
        
        print(f"✅ Got {len(active_markets)} active markets")
        return active_markets[:limit]
            
    except requests.exceptions.Timeout:
        print(f"❌ Error fetching markets: timeout")
        return []
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching markets: {type(e).__name__}: {str(e)[:100]}")
        return []
    except Exception as e:
        print(f"❌ Unexpected error: {type(e).__name__}: {str(e)[:100]}")
        return []


def test_market_price(market: Dict, outcome_index: int = 0, test_wallet_prices: Optional[Dict] = None) -> Dict:
    """
    Протестировать получение цены для рынка
    
    Args:
        market: Словарь с информацией о рынке
        outcome_index: Индекс исхода для тестирования
        test_wallet_prices: Тестовые wallet_prices для проверки fallback
        
    Returns:
        Dict: Результат теста с информацией о цене и источнике
    """
    condition_id = market.get("conditionId") or market.get("condition_id")
    question = market.get("question") or market.get("title") or "Unknown Market"
    slug = market.get("slug") or market.get("marketSlug") or "N/A"
    outcomes = market.get("outcomes") or []
    
    if not condition_id:
        return {
            "market": question,
            "condition_id": "N/A",
            "outcome": outcome_index,
            "price": None,
            "source": "ERROR",
            "error": "Missing condition_id",
            "time_ms": 0
        }
    
    # Подготовка wallet_prices для теста
    wallet_prices = test_wallet_prices
    if wallet_prices is None:
        # Используем тестовые данные для проверки fallback
        wallet_prices = {
            "0xabc123...": 0.51,
            "0xdef456...": 0.72
        }
    
    # Получаем цену с отслеживанием источника
    start_time = time.time()
    try:
        price, source = get_current_price(
            condition_id=condition_id,
            outcome_index=outcome_index,
            wallet_prices=wallet_prices,
            debug=True
        )
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        return {
            "market": question,
            "condition_id": condition_id[:20] + "..." if len(condition_id) > 20 else condition_id,
            "outcome": outcome_index,
            "price": price,
            "source": source or "N/A",
            "error": None,
            "time_ms": elapsed_ms
        }
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        error_msg = str(e).split('\n')[0] if '\n' in str(e) else str(e)
        return {
            "market": question,
            "condition_id": condition_id[:20] + "..." if len(condition_id) > 20 else condition_id,
            "outcome": outcome_index,
            "price": None,
            "source": "ERROR",
            "error": f"{type(e).__name__}: {error_msg[:100]}",
            "time_ms": elapsed_ms
        }


def format_result(result: Dict) -> str:
    """
    Форматировать результат для вывода
    
    Args:
        result: Результат теста
        
    Returns:
        str: Отформатированная строка
    """
    market = result["market"][:55] + "..." if len(result["market"]) > 58 else result["market"]
    condition_id = result["condition_id"]
    outcome = result["outcome"]
    price = f"{result['price']:.6f}" if result["price"] is not None else "N/A"
    source = result["source"]
    time_ms = result["time_ms"]
    
    # Определяем направление
    side = "BUY" if outcome == 0 else "SELL"
    
    # Форматируем источник
    source_display = source or "N/A"
    if source_display == "gamma":
        source_display = "Gamma"
    elif source_display == "wallet_fallback":
        source_display = "wallet_fallback"
    
    return f"Market: {market}\n" \
           f"Condition ID: {condition_id}\n" \
           f"Outcome: {outcome} ({side})\n" \
           f"→ Price: {price}  [Source: {source_display}] ({time_ms}ms)"


def main():
    """Основная функция тестирования"""
    parser = argparse.ArgumentParser(description="Test price fetching from all sources")
    parser.add_argument("--repeat", type=int, default=1, help="Number of times to repeat the test")
    parser.add_argument("--limit", type=int, default=10, help="Number of markets to test")
    args = parser.parse_args()
    
    print("=" * 80)
    print("🧪 Тест получения цен для случайных активных рынков")
    print("=" * 80)
    print()
    
    # Проверка CLOB API ключа в начале
    check_clob_api_key()
    print()
    
    all_results = []
    
    for iteration in range(args.repeat):
        if args.repeat > 1:
            print(f"\n{'=' * 80}")
            print(f"🔄 Итерация {iteration + 1}/{args.repeat}")
            print(f"{'=' * 80}\n")
        
        # Получаем список активных рынков
        markets = get_active_markets(limit=args.limit)
        
        if not markets:
            print("❌ Не удалось получить список рынков")
            if args.repeat > 1:
                continue
            else:
                return
        
        print(f"\n📊 Тестируем {len(markets)} рынков...\n")
        print("-" * 80)
        
        results = []
        for i, market in enumerate(markets, 1):
            print(f"\n[{i}/{len(markets)}] Testing market...")
            
            # Тестируем outcome 0
            result = test_market_price(market, outcome_index=0)
            results.append(result)
            all_results.append(result)
            
            # Выводим результат
            print(format_result(result))
            
            # Небольшая задержка между запросами
            if i < len(markets):
                time.sleep(0.3)
        
        print("\n" + "-" * 80)
        
        # Сводка для этой итерации
        successful = sum(1 for r in results if r["price"] is not None)
        no_price = sum(1 for r in results if r["price"] is None and r["source"] != "ERROR")
        errors = sum(1 for r in results if r["source"] == "ERROR")
        
        print(f"\n📈 Сводка (итерация {iteration + 1}):")
        print(f"✅ Успешно получено: {successful}")
        print(f"⚠️  Без цены: {no_price}")
        print(f"❌ Ошибки: {errors}")
        
        # Статистика по источникам
        sources = {}
        for r in results:
            if r["price"] is not None and r["source"]:
                sources[r["source"]] = sources.get(r["source"], 0) + 1
        
        if sources:
            print(f"\n📊 Источники цен:")
            for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
                print(f"   {source}: {count}")
        
        # Детальная информация
        if no_price > 0:
            print(f"\n⚠️  Рынки без цены:")
            for r in results:
                if r["price"] is None and r["source"] != "ERROR":
                    print(f"   - {r['market'][:60]} ({r['condition_id']})")
        
        if errors > 0:
            print(f"\n❌ Рынки с ошибками:")
            for r in results:
                if r["source"] == "ERROR":
                    print(f"   - {r['market'][:60]}: {r.get('error', 'Unknown error')}")
    
    # Итоговая сводка (если было несколько итераций)
    if args.repeat > 1:
        print(f"\n{'=' * 80}")
        print("📊 TEST SUMMARY (все итерации)")
        print(f"{'=' * 80}")
        
        total_successful = sum(1 for r in all_results if r["price"] is not None)
        total_no_price = sum(1 for r in all_results if r["price"] is None and r["source"] != "ERROR")
        total_errors = sum(1 for r in all_results if r["source"] == "ERROR")
        
        print(f"✅ Success: {total_successful}")
        print(f"⚠️  Missing price: {total_no_price}")
        print(f"❌ Errors: {total_errors}")
        
        # Общая статистика по источникам
        all_sources = {}
        for r in all_results:
            if r["price"] is not None and r["source"]:
                all_sources[r["source"]] = all_sources.get(r["source"], 0) + 1
        
        if all_sources:
            print(f"\n📊 Источники цен (всего):")
            for source, count in sorted(all_sources.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_successful * 100) if total_successful > 0 else 0
                print(f"   {source}: {count} ({percentage:.1f}%)")
        
        # Среднее время запроса
        avg_time = sum(r["time_ms"] for r in all_results) / len(all_results) if all_results else 0
        print(f"\n⏱️  Среднее время запроса: {avg_time:.0f}ms")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
