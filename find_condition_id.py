#!/usr/bin/env python3
"""
Поиск condition_id по названию рынка
Использование: python3 find_condition_id.py "Warriors vs Pelicans"
"""
import sys
import requests
import sqlite3
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

def search_in_database(keywords: List[str]) -> List[Dict]:
    """Поиск condition_id в базе данных по ключевым словам"""
    found = []
    db = sqlite3.connect('polymarket_notifier.db')
    cursor = db.cursor()
    
    # Ищем в alerts_sent
    week_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    cursor.execute('''
        SELECT DISTINCT condition_id, sent_at
        FROM alerts_sent
        WHERE sent_at >= ?
        ORDER BY sent_at DESC
        LIMIT 200
    ''', (week_ago,))
    
    condition_ids = cursor.fetchall()
    print(f"🔍 Проверяю {len(condition_ids)} condition_id из БД...")
    
    for condition_id, sent_at in condition_ids:
        try:
            url = f"https://clob.polymarket.com/markets/{condition_id}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                title = (data.get("question") or data.get("title") or "").lower()
                
                # Проверяем, содержатся ли все ключевые слова
                if all(kw.lower() in title for kw in keywords):
                    found.append({
                        "condition_id": condition_id,
                        "title": data.get("question") or data.get("title"),
                        "sent_at": sent_at,
                        "source": "DB alerts_sent",
                        "active": data.get("active", False)
                    })
                    print(f"   ✅ Найден: {data.get('question') or data.get('title')}")
        except:
            pass
    
    # Ищем в rolling_buys
    cursor.execute('SELECT k, data, updated_at FROM rolling_buys ORDER BY updated_at DESC LIMIT 100')
    rolling_rows = cursor.fetchall()
    
    print(f"🔍 Проверяю {len(rolling_rows)} записей из rolling_buys...")
    
    for k, data_str, updated_at in rolling_rows:
        try:
            data = json.loads(data_str)
            events = data.get('events', [])
            if events:
                market_title = events[0].get('marketTitle', '').lower()
                if all(kw.lower() in market_title for kw in keywords):
                    # Пытаемся извлечь condition_id из ключа или событий
                    condition_id = None
                    for event in events:
                        if 'conditionId' in event or 'condition_id' in event:
                            condition_id = event.get('conditionId') or event.get('condition_id')
                            break
                    
                    if condition_id:
                        found.append({
                            "condition_id": condition_id,
                            "title": events[0].get('marketTitle'),
                            "sent_at": updated_at,
                            "source": "DB rolling_buys",
                            "active": True
                        })
                        print(f"   ✅ Найден: {events[0].get('marketTitle')}")
        except:
            pass
    
    db.close()
    return found

def search_in_api(keywords: List[str], limit: int = 500) -> List[Dict]:
    """Поиск condition_id через API"""
    found = []
    
    try:
        print(f"🔍 Поиск через CLOB API (до {limit} рынков)...")
        url = "https://clob.polymarket.com/markets"
        params = {
            "limit": limit,
            "sort": "volume"
        }
        
        response = requests.get(url, params=params, timeout=20)
        if response.status_code == 200:
            markets = response.json()
            if isinstance(markets, list):
                for market in markets:
                    title = (market.get("question") or market.get("title") or "").lower()
                    if all(kw.lower() in title for kw in keywords):
                        condition_id = market.get("conditionId") or market.get("id")
                        found.append({
                            "condition_id": condition_id,
                            "title": market.get("question") or market.get("title"),
                            "sent_at": None,
                            "source": "CLOB API",
                            "active": market.get("active", False)
                        })
                        print(f"   ✅ Найден: {market.get('question') or market.get('title')}")
    except Exception as e:
        print(f"   ⚠️  Ошибка API: {e}")
    
    return found

def search_variations(keywords: List[str]) -> List[Dict]:
    """Поиск с различными вариантами названия"""
    all_found = []
    
    # Варианты поиска
    variations = [
        keywords,  # Оригинальные ключевые слова
        ["warriors", "pelicans"],
        ["warriors", "vs", "pelicans"],
        ["golden", "state", "pelicans"],
        ["gsw", "pelicans"],
        ["warriors", "new", "orleans"]
    ]
    
    for variation in variations:
        if variation == keywords:
            continue  # Уже проверили
        
        print(f"\n🔍 Поиск варианта: {' '.join(variation)}")
        
        # Поиск в БД
        db_results = search_in_database(variation)
        for result in db_results:
            # Проверяем, не добавлен ли уже
            if not any(f["condition_id"] == result["condition_id"] for f in all_found):
                all_found.append(result)
        
        # Поиск через API
        api_results = search_in_api(variation, limit=200)
        for result in api_results:
            if not any(f["condition_id"] == result["condition_id"] for f in all_found):
                all_found.append(result)
    
    return all_found

def main():
    if len(sys.argv) < 2:
        print("Использование: python3 find_condition_id.py \"Warriors vs Pelicans\"")
        print("\nПримеры:")
        print('  python3 find_condition_id.py "Warriors Pelicans"')
        print('  python3 find_condition_id.py "Warriors vs Pelicans"')
        sys.exit(1)
    
    search_query = sys.argv[1]
    keywords = search_query.split()
    
    print("="*70)
    print("ПОИСК CONDITION_ID ПО НАЗВАНИЮ РЫНКА")
    print("="*70)
    print(f"\nПоиск: '{search_query}'")
    print(f"Ключевые слова: {keywords}\n")
    
    all_found = []
    
    # 1. Поиск в БД
    print("\n1. Поиск в базе данных...")
    db_results = search_in_database(keywords)
    all_found.extend(db_results)
    
    # 2. Поиск через API
    print("\n2. Поиск через API...")
    api_results = search_in_api(keywords)
    for result in api_results:
        if not any(f["condition_id"] == result["condition_id"] for f in all_found):
            all_found.append(result)
    
    # 3. Поиск с вариациями
    if not all_found:
        print("\n3. Поиск с вариациями названия...")
        variation_results = search_variations(keywords)
        all_found.extend(variation_results)
    
    # Результаты
    print("\n" + "="*70)
    print("РЕЗУЛЬТАТЫ:")
    print("="*70)
    
    if all_found:
        # Удаляем дубликаты
        unique_found = []
        seen_ids = set()
        for result in all_found:
            if result["condition_id"] not in seen_ids:
                unique_found.append(result)
                seen_ids.add(result["condition_id"])
        
        print(f"\n✅ Найдено {len(unique_found)} рынков:\n")
        
        for i, result in enumerate(unique_found, 1):
            print(f"{i}. {result['title']}")
            print(f"   Condition ID: {result['condition_id']}")
            print(f"   Источник: {result['source']}")
            if result.get('sent_at'):
                print(f"   Дата: {result['sent_at']}")
            print(f"   Активен: {result.get('active', 'N/A')}")
            print()
        
        # Сохраняем в файл
        output_file = f"condition_ids_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
        with open(output_file, 'w') as f:
            f.write(f"Condition IDs для: {search_query}\n")
            f.write(f"Дата поиска: {datetime.now(timezone.utc).isoformat()}\n\n")
            for result in unique_found:
                f.write(f"{result['title']}\n")
                f.write(f"Condition ID: {result['condition_id']}\n")
                f.write(f"Источник: {result['source']}\n")
                if result.get('sent_at'):
                    f.write(f"Дата: {result['sent_at']}\n")
                f.write("\n")
        
        print(f"✅ Результаты сохранены в файл: {output_file}")
        
        # Показываем команду для сохранения кошельков
        if unique_found:
            print("\n" + "="*70)
            print("СЛЕДУЮЩИЕ ШАГИ:")
            print("="*70)
            print(f"\nДля сохранения всех кошельков с первого найденного рынка:")
            print(f"python3 save_wallets_from_market.py {unique_found[0]['condition_id']}")
    else:
        print("\n⚠️  Рынок не найден")
        print("\nВозможные причины:")
        print("  - Рынок уже закрыт и удален")
        print("  - Название рынка отличается")
        print("  - Рынок еще не создан")
        print("\nПопробуйте:")
        print("  - Проверить точное название на polymarket.com")
        print("  - Использовать другие ключевые слова")
        print("  - Проверить логи бота на наличие condition_id")

if __name__ == "__main__":
    main()

