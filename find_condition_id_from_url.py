#!/usr/bin/env python3
"""
Поиск condition_id по URL рынка Polymarket
"""
import sys
import requests
import re
from typing import Optional

def extract_slug_from_url(url: str) -> Optional[str]:
    """Извлечь slug из URL Polymarket"""
    # Пример: https://polymarket.com/event/fif-bra-tun-2025-11-18-tun
    patterns = [
        r'polymarket\.com/event/([^/?]+)',
        r'polymarket\.com/market/([^/?]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def find_condition_id_by_slug(slug: str) -> Optional[str]:
    """Найти condition_id по slug через Gamma API"""
    GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
    
    print(f"🔍 Поиск события по slug: {slug}")
    
    # Пробуем разные endpoints
    endpoints = [
        f"{GAMMA_BASE_URL}/events?featured=true&limit=500",
        f"{GAMMA_BASE_URL}/events?trending=true&limit=500",
        f"{GAMMA_BASE_URL}/events?limit=500",
    ]
    
    for url in endpoints:
        try:
            print(f"   Проверка: {url}")
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Обработка разных форматов ответа
                events = []
                if isinstance(data, list):
                    events = data
                elif isinstance(data, dict):
                    events = data.get("data") or data.get("events") or []
                
                print(f"   Найдено событий: {len(events)}")
                
                # Ищем событие по slug
                for event in events:
                    event_slug = event.get("slug") or event.get("eventSlug")
                    markets = event.get("markets", [])
                    
                    # Проверяем event slug
                    if event_slug and (slug in event_slug or event_slug in slug):
                        print(f"\n✅ Найдено событие по event slug: {event_slug}")
                        print(f"   Event ID: {event.get('id')}")
                        print(f"   Category: {event.get('category')}")
                        print(f"   Tags: {event.get('tags')}")
                        
                        if markets:
                            print(f"\n   Рынки ({len(markets)}):")
                            for i, market in enumerate(markets[:5]):  # Показываем первые 5
                                market_slug = market.get("slug") or market.get("marketSlug")
                                condition_id = market.get("conditionId") or market.get("condition_id")
                                question = market.get("question") or market.get("title")
                                print(f"      {i+1}. slug: {market_slug}")
                                print(f"         conditionId: {condition_id}")
                                print(f"         question: {question[:60]}...")
                        
                        return event
                    
                    # Проверяем markets slugs
                    for market in markets:
                        market_slug = market.get("slug") or market.get("marketSlug")
                        if market_slug and (slug in market_slug or market_slug in slug):
                            condition_id = market.get("conditionId") or market.get("condition_id")
                            print(f"\n✅ Найдено событие по market slug: {market_slug}")
                            print(f"   conditionId: {condition_id}")
                            print(f"   Event category: {event.get('category')}")
                            print(f"   Event tags: {event.get('tags')}")
                            return event
                
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            continue
    
    return None

def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python3 find_condition_id_from_url.py <slug или URL>")
        print("\nПримеры:")
        print("  python3 find_condition_id_from_url.py fif-bra-tun-2025-11-18-tun")
        print("  python3 find_condition_id_from_url.py https://polymarket.com/event/fif-bra-tun-2025-11-18-tun")
        sys.exit(1)
    
    input_str = sys.argv[1]
    
    # Извлечь slug из URL если нужно
    if "polymarket.com" in input_str:
        slug = extract_slug_from_url(input_str)
        if not slug:
            print(f"❌ Не удалось извлечь slug из URL: {input_str}")
            sys.exit(1)
        print(f"📋 Извлечен slug из URL: {slug}")
    else:
        slug = input_str
    
    event = find_condition_id_by_slug(slug)
    
    if event:
        print("\n✅ Событие найдено!")
        print("\nДля проверки структуры используйте:")
        if event.get("markets"):
            condition_id = event["markets"][0].get("conditionId") or event["markets"][0].get("condition_id")
            if condition_id:
                print(f"  python3 check_event_structure.py --condition-id {condition_id}")
    else:
        print("\n❌ Событие не найдено")
        print("\nВозможные причины:")
        print("  - Событие уже закрыто и удалено из API")
        print("  - Неверный slug")
        print("  - Событие находится в другом endpoint")
        print("\nПопробуйте проверить логи бота на сервере:")
        print("  sudo journalctl -u polymarket-bot --since '2025-11-18 22:00:00' | grep -A 30 'SPORTS_DETECT\\|GAMMA.*DEBUG'")

if __name__ == "__main__":
    main()


