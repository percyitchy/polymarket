#!/usr/bin/env python3
"""
Проверка структуры события для конкретного рынка
Показывает все поля события, категорию, теги и пути
"""
import os
import sys
import json
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import gamma_client
try:
    from gamma_client import get_event_by_condition_id, get_event_by_slug
    from market_utils import classify_market
except ImportError as e:
    logger.error(f"Failed to import modules: {e}")
    sys.exit(1)


def check_event_by_slug(event_slug: str):
    """Проверить событие по slug"""
    logger.info(f"🔍 Проверка события по slug: {event_slug}")
    
    try:
        event = get_event_by_slug(event_slug)
        if not event:
            logger.error(f"❌ Событие не найдено по slug: {event_slug}")
            return None
        
        return analyze_event(event, event_slug)
    except Exception as e:
        logger.error(f"❌ Ошибка при получении события: {e}", exc_info=True)
        return None


def check_event_by_condition_id(condition_id: str):
    """Проверить событие по condition_id"""
    logger.info(f"🔍 Проверка события по condition_id: {condition_id}")
    
    try:
        event = get_event_by_condition_id(condition_id)
        if not event:
            logger.error(f"❌ Событие не найдено по condition_id: {condition_id}")
            return None
        
        return analyze_event(event, None)
    except Exception as e:
        logger.error(f"❌ Ошибка при получении события: {e}", exc_info=True)
        return None


def analyze_event(event: Dict[str, Any], event_slug: Optional[str] = None):
    """Анализ структуры события"""
    print("\n" + "=" * 80)
    print("📊 СТРУКТУРА СОБЫТИЯ")
    print("=" * 80)
    
    # Основные поля события
    print("\n🔑 ОСНОВНЫЕ ПОЛЯ:")
    print(f"   id: {event.get('id')}")
    print(f"   eventId: {event.get('eventId')}")
    print(f"   slug: {event.get('slug')}")
    print(f"   eventSlug: {event.get('eventSlug')}")
    print(f"   title: {event.get('title')}")
    print(f"   question: {event.get('question')}")
    
    # Категорийные поля
    print("\n📂 КАТЕГОРИЙНЫЕ ПОЛЯ:")
    category = event.get("category")
    groupType = event.get("groupType")
    event_type = event.get("type")
    eventType = event.get("eventType")
    group = event.get("group")
    tags = event.get("tags", [])
    
    print(f"   category: {category}")
    print(f"   groupType: {groupType}")
    print(f"   type: {event_type}")
    print(f"   eventType: {eventType}")
    print(f"   group: {group}")
    print(f"   tags: {tags}")
    print(f"   tags (type): {type(tags)}")
    
    # Проверка на /sports/ путь
    print("\n🔍 ПРОВЕРКА ПУТЕЙ /sports/:")
    sports_paths_found = []
    
    # Проверка всех строковых полей
    for key, value in event.items():
        if isinstance(value, str) and '/sports/' in value.lower():
            sports_paths_found.append(f"{key}: {value}")
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and '/sports/' in item.lower():
                    sports_paths_found.append(f"{key}[{value.index(item)}]: {item}")
                elif isinstance(item, dict):
                    for sub_key, sub_value in item.items():
                        if isinstance(sub_value, str) and '/sports/' in sub_value.lower():
                            sports_paths_found.append(f"{key}[].{sub_key}: {sub_value}")
        elif isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, str) and '/sports/' in sub_value.lower():
                    sports_paths_found.append(f"{key}.{sub_key}: {sub_value}")
    
    if sports_paths_found:
        print("   ✅ Найдены пути /sports/:")
        for path in sports_paths_found:
            print(f"      - {path}")
    else:
        print("   ❌ Пути /sports/ не найдены")
    
    # Markets
    print("\n📈 РЫНКИ (markets):")
    markets = event.get("markets", [])
    print(f"   Количество рынков: {len(markets)}")
    
    if markets:
        print("\n   Первый рынок (пример):")
        first_market = markets[0]
        print(f"      conditionId: {first_market.get('conditionId')}")
        print(f"      condition_id: {first_market.get('condition_id')}")
        print(f"      slug: {first_market.get('slug')}")
        print(f"      marketSlug: {first_market.get('marketSlug')}")
        print(f"      question: {first_market.get('question')}")
        print(f"      title: {first_market.get('title')}")
        
        # URL-related fields в market
        url_fields = {}
        for key in ['url', 'path', 'pagePath', 'webUrl', 'sportsUrl', 'link', 'permalink', 'canonicalUrl']:
            if key in first_market:
                url_fields[key] = first_market[key]
        if url_fields:
            print(f"      URL-related fields: {url_fields}")
    
    # Все ключи события
    print("\n🔑 ВСЕ КЛЮЧИ СОБЫТИЯ:")
    all_keys = list(event.keys())
    print(f"   Всего ключей: {len(all_keys)}")
    print(f"   Ключи: {', '.join(sorted(all_keys))}")
    
    # Классификация
    print("\n🏷️  КЛАССИФИКАЦИЯ:")
    event_slug_for_classify = event.get("slug") or event.get("eventSlug") or event_slug
    markets_list = event.get("markets", [])
    
    # Попробуем классифицировать по первому рынку
    if markets_list:
        market = markets_list[0]
        market_slug = market.get("slug") or market.get("marketSlug")
        question = market.get("question") or market.get("title")
        classified = classify_market(event, market_slug, question)
        print(f"   Категория (по первому рынку): {classified}")
        print(f"   Использованные данные:")
        print(f"      - event.category: {category}")
        print(f"      - market.slug: {market_slug}")
        print(f"      - market.question: {question}")
    else:
        # Классификация по событию
        question = event.get("question") or event.get("title")
        classified = classify_market(event, event_slug_for_classify, question)
        print(f"   Категория (по событию): {classified}")
        print(f"   Использованные данные:")
        print(f"      - event.category: {category}")
        print(f"      - event.slug: {event_slug_for_classify}")
        print(f"      - event.question: {question}")
    
    # Полная структура (JSON)
    print("\n📄 ПОЛНАЯ СТРУКТУРА (JSON):")
    try:
        event_json = json.dumps(event, indent=2, default=str, ensure_ascii=False)
        # Ограничим вывод до 3000 символов
        if len(event_json) > 3000:
            print(event_json[:3000] + "\n   ... (обрезано)")
        else:
            print(event_json)
    except Exception as e:
        print(f"   ❌ Ошибка сериализации: {e}")
    
    print("\n" + "=" * 80)
    
    return {
        "event": event,
        "category": category,
        "tags": tags,
        "classified": classified if 'classified' in locals() else None,
        "sports_paths": sports_paths_found
    }


def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python3 check_event_structure.py <event_slug>")
        print("  python3 check_event_structure.py --condition-id <condition_id>")
        print("\nПримеры:")
        print("  python3 check_event_structure.py fif-bra-tun-2025-11-18-tun")
        print("  python3 check_event_structure.py --condition-id 0x123...")
        sys.exit(1)
    
    if sys.argv[1] == "--condition-id" and len(sys.argv) > 2:
        condition_id = sys.argv[2]
        result = check_event_by_condition_id(condition_id)
    else:
        event_slug = sys.argv[1]
        result = check_event_by_slug(event_slug)
    
    if result:
        print("\n✅ Анализ завершён успешно")
    else:
        print("\n❌ Не удалось получить данные о событии")
        sys.exit(1)


if __name__ == "__main__":
    main()


