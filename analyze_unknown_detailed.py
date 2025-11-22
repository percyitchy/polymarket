#!/usr/bin/env python3
"""
Детальный анализ Unknown рынков для снижения до 20%
"""

import os
import sys
import logging
from collections import Counter, defaultdict
from dotenv import load_dotenv
from db import PolymarketDB
import requests

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def analyze_unknown_detailed():
    """Детальный анализ Unknown рынков"""
    db_path = os.getenv('DB_PATH', 'polymarket_notifier.db')
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)
    
    db = PolymarketDB(db_path)
    
    print("=" * 80)
    print("🔍 ДЕТАЛЬНЫЙ АНАЛИЗ UNKNOWN РЫНКОВ")
    print("=" * 80)
    
    # Получаем Unknown рынки из базы
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Получаем кошельки с Unknown категориями
        cursor.execute("""
            SELECT DISTINCT wallet_address
            FROM wallet_category_stats
            WHERE category = 'other/Unknown'
            LIMIT 200
        """)
        
        unknown_wallets = [row[0] for row in cursor.fetchall()]
        print(f"\n📊 Найдено {len(unknown_wallets)} кошельков с Unknown категориями")
        
        # Получаем примеры Unknown рынков через API
        print("\n📥 Получение примеров рынков через API...")
        
        # Получаем события
        url = "https://gamma-api.polymarket.com/events"
        params = {"limit": 300, "featured": "true"}
        
        try:
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                events = []
                if isinstance(data, list):
                    events = data
                elif isinstance(data, dict):
                    events = data.get("data") or data.get("events") or []
                
                print(f"✅ Получено {len(events)} событий")
                
                # Извлекаем все рынки
                all_markets = []
                for event in events:
                    markets = event.get("markets", [])
                    for market in markets:
                        market["event"] = event
                        all_markets.append(market)
                
                print(f"✅ Извлечено {len(all_markets)} рынков")
                
                # Классифицируем и находим Unknown
                from market_utils import classify_market
                
                unknown_samples = []
                classified_samples = []
                
                for market in all_markets[:500]:  # Ограничиваем для скорости
                    condition_id = market.get("conditionId") or market.get("condition_id")
                    slug = market.get("slug") or market.get("marketSlug") or ""
                    question = market.get("question") or market.get("title") or ""
                    description = market.get("description") or ""
                    
                    event = market.get("event", {})
                    
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
                        unknown_samples.append(market_info)
                    else:
                        classified_samples.append(market_info)
                
                print(f"\n📊 Результаты классификации:")
                print(f"   Классифицировано: {len(classified_samples)}")
                print(f"   Unknown: {len(unknown_samples)}")
                print(f"   Процент Unknown: {len(unknown_samples) / len(all_markets[:500]) * 100:.2f}%")
                
                if unknown_samples:
                    print(f"\n🔍 Анализ {len(unknown_samples)} Unknown рынков:")
                    
                    # Анализ по наличию данных
                    has_slug = sum(1 for m in unknown_samples if m["slug"])
                    has_question = sum(1 for m in unknown_samples if m["question"])
                    has_description = sum(1 for m in unknown_samples if m["description"])
                    has_any = sum(1 for m in unknown_samples if m["slug"] or m["question"] or m["description"])
                    empty = len(unknown_samples) - has_any
                    
                    print(f"\n📋 Наличие данных:")
                    print(f"   Есть slug: {has_slug} ({has_slug/len(unknown_samples)*100:.1f}%)")
                    print(f"   Есть question: {has_question} ({has_question/len(unknown_samples)*100:.1f}%)")
                    print(f"   Есть description: {has_description} ({has_description/len(unknown_samples)*100:.1f}%)")
                    print(f"   Есть любые данные: {has_any} ({has_any/len(unknown_samples)*100:.1f}%)")
                    print(f"   Пустые данные: {empty} ({empty/len(unknown_samples)*100:.1f}%)")
                    
                    # Анализ паттернов в тексте
                    import re
                    
                    patterns_analysis = {
                        "dates": [],
                        "numbers": [],
                        "short_text": [],
                        "common_words": []
                    }
                    
                    keywords = Counter()
                    stop_words = {
                        "will", "the", "be", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
                        "of", "with", "by", "from", "as", "is", "are", "was", "were", "been", "being"
                    }
                    
                    for market in unknown_samples:
                        text = market["full_text"]
                        
                        # Даты
                        if re.search(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|january|february|march|april|may|june|july|august|september|october|november|december', text, re.IGNORECASE):
                            patterns_analysis["dates"].append(market)
                        
                        # Числа
                        if re.search(r'\$[\d,]+|\d+%|\d+\.\d+%|\d+[km]?', text):
                            patterns_analysis["numbers"].append(market)
                        
                        # Короткий текст
                        if len(text) < 30:
                            patterns_analysis["short_text"].append(market)
                        
                        # Ключевые слова
                        words = text.split()
                        for word in words:
                            word_clean = word.strip(".,!?;:()[]{}'\"-").lower()
                            if len(word_clean) > 3 and word_clean not in stop_words:
                                keywords[word_clean] += 1
                    
                    print(f"\n🔤 Паттерны в Unknown:")
                    print(f"   С датами: {len(patterns_analysis['dates'])} ({len(patterns_analysis['dates'])/len(unknown_samples)*100:.1f}%)")
                    print(f"   С числами: {len(patterns_analysis['numbers'])} ({len(patterns_analysis['numbers'])/len(unknown_samples)*100:.1f}%)")
                    print(f"   Короткий текст: {len(patterns_analysis['short_text'])} ({len(patterns_analysis['short_text'])/len(unknown_samples)*100:.1f}%)")
                    
                    print(f"\n📝 Топ-20 ключевых слов в Unknown:")
                    for word, count in keywords.most_common(20):
                        print(f"   {word:<25} {count:>4}")
                    
                    # Примеры для анализа
                    print(f"\n📋 Примеры Unknown рынков:")
                    print(f"\n1. Рынки с данными но Unknown:")
                    samples_with_data = [m for m in unknown_samples if m["slug"] or m["question"]][:10]
                    for i, market in enumerate(samples_with_data[:5], 1):
                        print(f"   {i}. Slug: {market['slug'][:60] if market['slug'] else 'N/A'}")
                        print(f"      Question: {market['question'][:80] if market['question'] else 'N/A'}")
                    
                    print(f"\n2. Рынки с датами:")
                    for i, market in enumerate(patterns_analysis["dates"][:5], 1):
                        print(f"   {i}. {market['question'][:80] or market['slug'][:80]}")
                    
                    print(f"\n3. Рынки с числами:")
                    for i, market in enumerate(patterns_analysis["numbers"][:5], 1):
                        print(f"   {i}. {market['question'][:80] or market['slug'][:80]}")
                    
                    # Рекомендации
                    print("\n" + "=" * 80)
                    print("💡 РЕКОМЕНДАЦИИ ДЛЯ СНИЖЕНИЯ UNKNOWN ДО 20%:")
                    print("=" * 80)
                    
                    recommendations = []
                    
                    if empty > len(unknown_samples) * 0.3:
                        recommendations.append("1. ⚠️  КРИТИЧНО: Много пустых данных - улучшить получение данных через все API")
                    
                    if len(patterns_analysis["dates"]) > 0:
                        recommendations.append("2. ✅ Добавить классификацию по датам (события, дедлайны → macro/Events)")
                    
                    if len(patterns_analysis["numbers"]) > 0:
                        recommendations.append("3. ✅ Добавить классификацию по ценам/процентам (макро, крипто)")
                    
                    if len(patterns_analysis["short_text"]) > len(unknown_samples) * 0.2:
                        recommendations.append("4. ✅ Использовать ML для коротких текстов (более агрессивно)")
                    
                    # Анализ ключевых слов
                    top_keywords_list = [w for w, c in keywords.most_common(30) if c >= 2]
                    if top_keywords_list:
                        recommendations.append(f"5. 📝 Добавить ключевые слова: {', '.join(top_keywords_list[:15])}")
                    
                    recommendations.append("6. 🤖 Снизить ML порог до 0.05 для очень агрессивной классификации")
                    recommendations.append("7. 🔄 Добавить fallback классификацию по контексту (даты → macro, числа → crypto/macro)")
                    recommendations.append("8. 📊 Использовать event.category из API если доступно")
                    recommendations.append("9. 🎯 Добавить эвристики для классификации по минимальным данным")
                    recommendations.append("10. 💾 Улучшить кэширование для исторических рынков")
                    
                    for rec in recommendations:
                        print(f"   {rec}")
                    
                    print("\n" + "=" * 80)
                    
                    return {
                        "total": len(all_markets[:500]),
                        "unknown": len(unknown_samples),
                        "unknown_pct": len(unknown_samples) / len(all_markets[:500]) * 100 if all_markets else 0,
                        "empty_data": empty,
                        "empty_pct": empty / len(unknown_samples) * 100 if unknown_samples else 0,
                        "patterns": patterns_analysis,
                        "top_keywords": dict(keywords.most_common(30))
                    }
                else:
                    print("✅ Все рынки классифицированы!")
                    return None
            else:
                print(f"❌ Ошибка API: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            return None

if __name__ == "__main__":
    results = analyze_unknown_detailed()
    if results:
        print(f"\n✅ Анализ завершён.")
        print(f"   Unknown: {results['unknown']} ({results['unknown_pct']:.2f}%)")
        print(f"   Пустые данные: {results['empty_data']} ({results['empty_pct']:.1f}%)")

