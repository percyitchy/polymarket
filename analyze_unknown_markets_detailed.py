#!/usr/bin/env python3
"""
Детальный анализ Unknown рынков для выявления паттернов
"""

import os
import sys
import logging
from collections import Counter, defaultdict
from typing import List, Dict, Any, Optional
import re
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from db import PolymarketDB
from wallet_analyzer import WalletAnalyzer
from market_utils import classify_market
from enhanced_market_data import enhance_market_data_for_classification

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def analyze_unknown_markets():
    """Анализировать Unknown рынки из базы данных"""
    
    db = PolymarketDB()
    analyzer = WalletAnalyzer(db)
    
    print("=" * 80)
    print("🔍 ДЕТАЛЬНЫЙ АНАЛИЗ UNKNOWN РЫНКОВ")
    print("=" * 80)
    
    # Получаем кошельки с Unknown категориями
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT wallet_address
            FROM wallet_category_stats
            WHERE category = 'other/Unknown'
            LIMIT 500
        """)
        
        unknown_wallets = [row[0] for row in cursor.fetchall()]
        print(f"\n📊 Найдено {len(unknown_wallets)} кошельков с Unknown категориями")
    
    # Собираем данные о Unknown рынках
    all_unknown_markets = []
    processed_condition_ids = set()
    
    print(f"\n📥 Сбор данных о Unknown рынках...")
    
    for i, wallet_address in enumerate(unknown_wallets):
        if i % 50 == 0:
            print(f"   Обработано {i}/{len(unknown_wallets)} кошельков...")
        
        try:
            closed_positions = analyzer._get_closed_positions(wallet_address)
            
            for position in closed_positions:
                condition_id = position.get("conditionId")
                if not condition_id or condition_id in processed_condition_ids:
                    continue
                
                # Проверяем, что категория действительно Unknown
                category_stats = db.get_wallet_category_stats(wallet_address, condition_id)
                if category_stats and category_stats.get("category") != "other/Unknown":
                    continue
                
                # Извлекаем данные рынка
                slug = position.get("slug") or position.get("marketSlug") or position.get("eventSlug")
                question = position.get("title") or position.get("question") or position.get("marketTitle")
                description = position.get("description") or position.get("marketDescription")
                
                # Используем enhanced_market_data для получения более полных данных
                try:
                    enhanced_data = enhance_market_data_for_classification(
                        condition_id=condition_id,
                        existing_slug=slug,
                        existing_question=question,
                        existing_description=description
                    )
                    
                    final_slug = enhanced_data.get("slug") or slug
                    final_question = enhanced_data.get("question") or question
                    final_description = enhanced_data.get("description") or description
                except Exception as e:
                    logger.debug(f"Error enhancing data for {condition_id[:20]}...: {e}")
                    final_slug = slug
                    final_question = question
                    final_description = description
                
                # Комбинируем текст для анализа
                combined_text = f"{final_question or ''} {final_description or ''} {final_slug or ''}".strip()
                
                # Повторно классифицируем, чтобы убедиться, что это Unknown
                re_classified_category = classify_market({}, final_slug, combined_text)
                
                if re_classified_category == "other/Unknown":
                    all_unknown_markets.append({
                        "condition_id": condition_id,
                        "slug": final_slug,
                        "question": final_question,
                        "description": final_description,
                        "combined_text": combined_text,
                        "has_slug": bool(final_slug),
                        "has_question": bool(final_question),
                        "has_description": bool(final_description),
                        "text_length": len(combined_text)
                    })
                    processed_condition_ids.add(condition_id)
        except Exception as e:
            logger.debug(f"Error processing wallet {wallet_address[:20]}...: {e}")
            continue
    
    print(f"\n✅ Собрано {len(all_unknown_markets)} уникальных Unknown рынков")
    
    if not all_unknown_markets:
        print("\n✅ Все рынки успешно классифицированы!")
        return
    
    # Анализ паттернов
    print("\n" + "=" * 80)
    print("📊 АНАЛИЗ ПАТТЕРНОВ")
    print("=" * 80)
    
    # 1. Наличие данных
    has_slug_count = sum(1 for m in all_unknown_markets if m["has_slug"])
    has_question_count = sum(1 for m in all_unknown_markets if m["has_question"])
    has_description_count = sum(1 for m in all_unknown_markets if m["has_description"])
    has_any_count = sum(1 for m in all_unknown_markets if m["has_slug"] or m["has_question"] or m["has_description"])
    empty_count = len(all_unknown_markets) - has_any_count
    
    print(f"\n📋 Наличие данных:")
    print(f"   Есть slug: {has_slug_count} ({has_slug_count/len(all_unknown_markets)*100:.1f}%)")
    print(f"   Есть question: {has_question_count} ({has_question_count/len(all_unknown_markets)*100:.1f}%)")
    print(f"   Есть description: {has_description_count} ({has_description_count/len(all_unknown_markets)*100:.1f}%)")
    print(f"   Есть любые данные: {has_any_count} ({has_any_count/len(all_unknown_markets)*100:.1f}%)")
    print(f"   Пустые данные: {empty_count} ({empty_count/len(all_unknown_markets)*100:.1f}%)")
    
    # 2. Длина текста
    text_lengths = [m["text_length"] for m in all_unknown_markets]
    avg_length = sum(text_lengths) / len(text_lengths) if text_lengths else 0
    short_texts = [m for m in all_unknown_markets if m["text_length"] < 20]
    medium_texts = [m for m in all_unknown_markets if 20 <= m["text_length"] < 50]
    long_texts = [m for m in all_unknown_markets if m["text_length"] >= 50]
    
    print(f"\n📏 Длина текста:")
    print(f"   Средняя длина: {avg_length:.1f} символов")
    print(f"   Короткий текст (<20): {len(short_texts)} ({len(short_texts)/len(all_unknown_markets)*100:.1f}%)")
    print(f"   Средний текст (20-50): {len(medium_texts)} ({len(medium_texts)/len(all_unknown_markets)*100:.1f}%)")
    print(f"   Длинный текст (>=50): {len(long_texts)} ({len(long_texts)/len(all_unknown_markets)*100:.1f}%)")
    
    # 3. Паттерны в тексте
    date_patterns_count = 0
    price_patterns_count = 0
    question_patterns_count = 0
    number_patterns_count = 0
    
    keywords = Counter()
    stop_words = {
        "will", "the", "be", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "are", "was", "were", "been", "being",
        "this", "that", "it", "not", "no", "yes", "can", "do", "get", "has", "have", "had"
    }
    
    for market in all_unknown_markets:
        text = market["combined_text"].lower()
        
        # Даты
        if re.search(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|january|february|march|april|may|june|july|august|september|october|november|december', text, re.IGNORECASE):
            date_patterns_count += 1
        
        # Цены
        if re.search(r'\$[\d,]+|\d+\.\d+%|\d+%|\d+[km]', text):
            price_patterns_count += 1
        
        # Вопросы
        if re.search(r'\b(will|is|are|does|can)\b.*\?', text):
            question_patterns_count += 1
        
        # Числа
        if re.search(r'\d+', text):
            number_patterns_count += 1
        
        # Ключевые слова
        words = re.findall(r'\b\w+\b', text)
        for word in words:
            word_clean = word.strip(".,!?;:()[]{}'\"-").lower()
            if len(word_clean) > 2 and word_clean not in stop_words:
                keywords[word_clean] += 1
    
    print(f"\n🔤 Паттерны в тексте:")
    print(f"   С датами: {date_patterns_count} ({date_patterns_count/len(all_unknown_markets)*100:.1f}%)")
    print(f"   С ценами: {price_patterns_count} ({price_patterns_count/len(all_unknown_markets)*100:.1f}%)")
    print(f"   Вопросы: {question_patterns_count} ({question_patterns_count/len(all_unknown_markets)*100:.1f}%)")
    print(f"   С числами: {number_patterns_count} ({number_patterns_count/len(all_unknown_markets)*100:.1f}%)")
    
    print(f"\n📝 Топ-30 ключевых слов в Unknown рынках:")
    for word, count in keywords.most_common(30):
        print(f"   {word:<25} {count:>4}")
    
    # 4. Примеры для анализа
    print(f"\n📋 Примеры Unknown рынков:")
    
    markets_with_data = [m for m in all_unknown_markets if m['has_question'] or m['has_slug']]
    print(f"\n1. Рынки с данными но Unknown ({len(markets_with_data)}):")
    samples_with_data = markets_with_data[:10]
    for i, market in enumerate(samples_with_data[:5], 1):
        print(f"   {i}. Slug: {market['slug'][:60] if market['slug'] else 'N/A'}")
        print(f"      Question: {market['question'][:80] if market['question'] else 'N/A'}")
        print(f"      Text length: {market['text_length']}")
    
    print(f"\n2. Рынки с датами ({date_patterns_count}):")
    date_samples = [m for m in all_unknown_markets if re.search(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|january|february|march|april|may|june|july|august|september|october|november|december', m['combined_text'].lower(), re.IGNORECASE)][:5]
    for i, market in enumerate(date_samples, 1):
        print(f"   {i}. {market['question'][:80] or market['slug'][:80]}")
    
    print(f"\n3. Рынки с ценами ({price_patterns_count}):")
    price_samples = [m for m in all_unknown_markets if re.search(r'\$[\d,]+|\d+\.\d+%|\d+%|\d+[km]', m['combined_text'])][:5]
    for i, market in enumerate(price_samples, 1):
        print(f"   {i}. {market['question'][:80] or market['slug'][:80]}")
    
    print(f"\n4. Короткий текст ({len(short_texts)}):")
    for i, market in enumerate(short_texts[:5], 1):
        print(f"   {i}. {market['question'][:80] or market['slug'][:80] or 'N/A'} (length: {market['text_length']})")
    
    print(f"\n5. Пустые данные ({empty_count}):")
    empty_samples = [m for m in all_unknown_markets if not (m["has_slug"] or m["has_question"] or m["has_description"])][:5]
    for i, market in enumerate(empty_samples, 1):
        print(f"   {i}. Condition ID: {market['condition_id'][:20]}... (no data)")
    
    # Сохраняем результаты для дальнейшего использования
    print(f"\n💾 Сохранение результатов...")
    import json
    with open("unknown_markets_analysis.json", "w") as f:
        json.dump({
            "total": len(all_unknown_markets),
            "patterns": {
                "dates": date_patterns_count,
                "prices": price_patterns_count,
                "questions": question_patterns_count,
                "numbers": number_patterns_count
            },
            "data_availability": {
                "has_slug": has_slug_count,
                "has_question": has_question_count,
                "has_description": has_description_count,
                "empty": empty_count
            },
            "text_lengths": {
                "avg": avg_length,
                "short": len(short_texts),
                "medium": len(medium_texts),
                "long": len(long_texts)
            },
            "top_keywords": dict(keywords.most_common(50)),
            "samples": all_unknown_markets[:100]  # Сохраняем первые 100 для анализа
        }, f, indent=2)
    
    print(f"✅ Результаты сохранены в unknown_markets_analysis.json")
    
    print("\n" + "=" * 80)
    print("💡 РЕКОМЕНДАЦИИ:")
    print("=" * 80)
    
    recommendations = []
    
    if empty_count > len(all_unknown_markets) * 0.3:
        recommendations.append("1. ⚠️  КРИТИЧНО: Много пустых данных - улучшить получение данных через все API")
    
    if date_patterns_count > 0:
        recommendations.append("2. ✅ Добавить более агрессивную классификацию по датам")
    
    if price_patterns_count > 0:
        recommendations.append("3. ✅ Добавить более агрессивную классификацию по ценам")
    
    if len(short_texts) > len(all_unknown_markets) * 0.2:
        recommendations.append("4. ✅ Использовать ML для коротких текстов (более агрессивно)")
    
    top_keywords_list = [w for w, c in keywords.most_common(30) if c >= 2]
    if top_keywords_list:
        recommendations.append(f"5. 📝 Добавить ключевые слова в классификацию: {', '.join(top_keywords_list[:15])}")
    
    for rec in recommendations:
        print(f"   {rec}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    analyze_unknown_markets()

