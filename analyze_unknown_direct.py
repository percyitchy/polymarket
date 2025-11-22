#!/usr/bin/env python3
"""
Прямой анализ Unknown рынков через API
"""

import os
import sys
import logging
from collections import Counter
from dotenv import load_dotenv
from db import PolymarketDB
from market_utils import classify_market

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def analyze_unknown_from_api():
    """Анализировать Unknown рынки через API"""
    import requests
    
    print("=" * 80)
    print("📊 АНАЛИЗ UNKNOWN РЫНКОВ ЧЕРЕЗ API")
    print("=" * 80)
    
    # Получаем события через Gamma API
    print("\n📥 Получение событий через Gamma API...")
    try:
        url = "https://gamma-api.polymarket.com/events"
        params = {"limit": 200, "featured": "true"}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Ошибка API: {response.status_code}")
            return
        
        data = response.json()
        events = []
        if isinstance(data, list):
            events = data
        elif isinstance(data, dict):
            events = data.get("data") or data.get("events") or []
        
        logger.info(f"Получено {len(events)} событий")
        
        # Извлекаем все рынки из событий
        markets = []
        for event in events:
            event_markets = event.get("markets", [])
            for market in event_markets:
                market["event"] = event  # Сохраняем event для классификации
                markets.append(market)
        
        logger.info(f"Извлечено {len(markets)} рынков из событий")
    except Exception as e:
        logger.error(f"Ошибка при получении рынков: {e}")
        return
    
    # Классифицируем каждый рынок
    unknown_markets = []
    classified_markets = []
    
    print("\n🔍 Классификация рынков...")
    for i, market in enumerate(markets):
        if i % 50 == 0:
            print(f"   Обработано {i}/{len(markets)}...")
        
        condition_id = market.get("conditionId") or market.get("condition_id")
        slug = market.get("slug") or market.get("marketSlug") or ""
        question = market.get("question") or market.get("title") or ""
        description = market.get("description") or ""
        
        # Используем event из market (уже сохранён выше)
        event = market.get("event", {})
        
        # Классифицируем
        category = classify_market(event, slug, question or description)
        
        market_info = {
            "condition_id": condition_id,
            "slug": slug,
            "question": question,
            "description": description,
            "category": category,
            "full_text": f"{slug} {question} {description}".lower()
        }
        
        if category == "other/Unknown":
            unknown_markets.append(market_info)
        else:
            classified_markets.append(market_info)
    
    print(f"\n✅ Классифицировано: {len(classified_markets)}")
    print(f"❓ Unknown: {len(unknown_markets)}")
    print(f"📊 Процент Unknown: {len(unknown_markets) / len(markets) * 100:.2f}%")
    
    if not unknown_markets:
        print("\n✅ Все рынки классифицированы!")
        return
    
    # Анализ паттернов Unknown рынков
    print("\n" + "=" * 80)
    print("🔍 АНАЛИЗ ПАТТЕРНОВ UNKNOWN РЫНКОВ")
    print("=" * 80)
    
    # Извлекаем ключевые слова
    keywords = Counter()
    stop_words = {
        "will", "the", "be", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "are", "was", "were", "been", "being",
        "have", "has", "had", "do", "does", "did", "this", "that", "these", "those",
        "what", "which", "who", "when", "where", "why", "how", "if", "than", "then",
        "more", "most", "some", "any", "all", "each", "every", "other", "another"
    }
    
    for market in unknown_markets:
        text = market["full_text"]
        words = text.split()
        
        for word in words:
            word_clean = word.strip(".,!?;:()[]{}'\"-").lower()
            if len(word_clean) > 3 and word_clean not in stop_words:
                keywords[word_clean] += 1
    
    print("\n🔤 Топ-30 ключевых слов в Unknown рынках:")
    for word, count in keywords.most_common(30):
        print(f"   {word:<25} {count:>4}")
    
    # Анализ по паттернам
    import re
    
    patterns = {
        "dates": [],
        "numbers": [],
        "questions": [],
        "short_text": [],
        "empty_data": [],
        "specific_keywords": []
    }
    
    for market in unknown_markets:
        text = market["full_text"]
        question = market["question"]
        slug = market["slug"]
        
        # Даты
        if re.search(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec', text, re.IGNORECASE):
            patterns["dates"].append(market)
        
        # Числа/цены
        if re.search(r'\$[\d,]+|\d+%|\d+\.\d+%|\d+[km]?', text):
            patterns["numbers"].append(market)
        
        # Вопросы
        if question and '?' in question:
            patterns["questions"].append(market)
        
        # Короткий текст
        if len(text) < 20:
            patterns["short_text"].append(market)
        
        # Пустые данные
        if not text or text.strip() == "":
            patterns["empty_data"].append(market)
    
    print("\n📋 Статистика по паттернам:")
    print(f"   Рынки с датами: {len(patterns['dates'])} ({len(patterns['dates'])/len(unknown_markets)*100:.1f}%)")
    print(f"   Рынки с числами/ценами: {len(patterns['numbers'])} ({len(patterns['numbers'])/len(unknown_markets)*100:.1f}%)")
    print(f"   Рынки-вопросы: {len(patterns['questions'])} ({len(patterns['questions'])/len(unknown_markets)*100:.1f}%)")
    print(f"   Короткий текст (<20 символов): {len(patterns['short_text'])} ({len(patterns['short_text'])/len(unknown_markets)*100:.1f}%)")
    print(f"   Пустые данные: {len(patterns['empty_data'])} ({len(patterns['empty_data'])/len(unknown_markets)*100:.1f}%)")
    
    # Примеры
    print("\n📝 Примеры Unknown рынков:")
    
    if patterns["dates"]:
        print("\n1. Рынки с датами:")
        for market in patterns["dates"][:5]:
            print(f"   • {market['question'][:100] or market['slug'][:100]}")
    
    if patterns["numbers"]:
        print("\n2. Рынки с числами/ценами:")
        for market in patterns["numbers"][:5]:
            print(f"   • {market['question'][:100] or market['slug'][:100]}")
    
    if patterns["short_text"]:
        print("\n3. Короткий текст:")
        for market in patterns["short_text"][:5]:
            print(f"   • {market['question'][:100] or market['slug'][:100]}")
    
    if patterns["empty_data"]:
        print("\n4. Пустые данные:")
        for market in patterns["empty_data"][:5]:
            print(f"   • condition_id: {market['condition_id'][:40] if market['condition_id'] else 'N/A'}...")
    
    # Рекомендации
    print("\n" + "=" * 80)
    print("💡 РЕКОМЕНДАЦИИ:")
    print("=" * 80)
    
    recommendations = []
    
    if len(patterns["empty_data"]) > len(unknown_markets) * 0.3:
        recommendations.append("⚠️  Много рынков с пустыми данными - улучшить получение данных через GraphQL/web scraping")
    
    if len(patterns["short_text"]) > len(unknown_markets) * 0.2:
        recommendations.append("⚠️  Много рынков с коротким текстом - использовать description из API")
    
    # Анализ ключевых слов для новых категорий
    top_keywords = [w for w, c in keywords.most_common(50) if c >= 2]
    
    # Проверяем, какие ключевые слова не покрыты
    from market_utils import (
        NFL_TEAMS, NBA_TEAMS, NHL_TEAMS, MLB_TEAMS,
        CRYPTO_KEYWORDS, POLITICS_KEYWORDS, MACRO_KEYWORDS,
        STOCKS_KEYWORDS, ENTERTAINMENT_KEYWORDS, TECH_KEYWORDS
    )
    
    all_known_keywords = set()
    for kw_list in [NFL_TEAMS, NBA_TEAMS, NHL_TEAMS, MLB_TEAMS,
                    CRYPTO_KEYWORDS, POLITICS_KEYWORDS, MACRO_KEYWORDS,
                    STOCKS_KEYWORDS, ENTERTAINMENT_KEYWORDS, TECH_KEYWORDS]:
        all_known_keywords.update([k.lower() for k in kw_list])
    
    unknown_keywords = [kw for kw in top_keywords if kw not in all_known_keywords]
    
    if unknown_keywords:
        recommendations.append(f"📝 Новые ключевые слова для добавления: {', '.join(unknown_keywords[:20])}")
    
    for rec in recommendations:
        print(f"   {rec}")
    
    print("\n" + "=" * 80)
    
    return {
        "total": len(markets),
        "unknown": len(unknown_markets),
        "unknown_pct": len(unknown_markets) / len(markets) * 100 if markets else 0,
        "patterns": patterns,
        "top_keywords": dict(keywords.most_common(30)),
        "unknown_keywords": unknown_keywords[:20]
    }

if __name__ == "__main__":
    results = analyze_unknown_from_api()
    if results:
        print(f"\n✅ Анализ завершён.")
        print(f"   Всего рынков: {results['total']}")
        print(f"   Unknown: {results['unknown']} ({results['unknown_pct']:.2f}%)")

