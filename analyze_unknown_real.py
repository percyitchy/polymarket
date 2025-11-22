#!/usr/bin/env python3
"""
Анализ реальных Unknown рынков из закрытых позиций
"""

import os
import sys
import logging
from collections import Counter
from typing import List, Dict, Any
import re
import json
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from db import PolymarketDB
from wallet_analyzer import WalletAnalyzer

load_dotenv()

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def analyze_unknown_real():
    """Анализ реальных Unknown рынков"""
    
    db = PolymarketDB()
    analyzer = WalletAnalyzer(db)
    
    print("=" * 80)
    print("🔍 АНАЛИЗ РЕАЛЬНЫХ UNKNOWN РЫНКОВ")
    print("=" * 80)
    
    # Получаем кошельки с Unknown категориями
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT wallet_address
            FROM wallet_category_stats
            WHERE category = 'other/Unknown'
            LIMIT 100
        """)
        
        unknown_wallets = [row[0] for row in cursor.fetchall()]
        print(f"\n📊 Найдено {len(unknown_wallets)} кошельков с Unknown")
    
    # Собираем данные о Unknown рынках
    all_markets = []
    processed_condition_ids = set()
    
    print(f"\n📥 Сбор данных из закрытых позиций...")
    
    for i, wallet_address in enumerate(unknown_wallets):
        if i % 10 == 0:
            print(f"   Обработано {i}/{len(unknown_wallets)} кошельков...")
        
        try:
            closed_positions = analyzer._get_closed_positions(wallet_address, max_positions=50)
            
            for position in closed_positions:
                condition_id = position.get("conditionId")
                if not condition_id or condition_id in processed_condition_ids:
                    continue
                
                # Проверяем, что категория Unknown
                category_stats = db.get_wallet_category_stats(wallet_address, condition_id)
                if category_stats and category_stats.get("category") != "other/Unknown":
                    continue
                
                # Извлекаем данные
                slug = position.get("slug") or position.get("marketSlug") or ""
                question = position.get("title") or position.get("question") or position.get("marketTitle") or ""
                description = position.get("description") or position.get("marketDescription") or ""
                
                combined_text = f"{question} {description} {slug}".strip().lower()
                
                if combined_text:
                    all_markets.append({
                        "condition_id": condition_id,
                        "slug": slug,
                        "question": question,
                        "description": description,
                        "combined_text": combined_text,
                        "text_length": len(combined_text)
                    })
                    processed_condition_ids.add(condition_id)
                    
                    if len(all_markets) >= 500:  # Ограничиваем для скорости
                        break
            
            if len(all_markets) >= 500:
                break
        except Exception as e:
            logger.debug(f"Error processing wallet {wallet_address[:20]}...: {e}")
            continue
    
    print(f"\n✅ Собрано {len(all_markets)} уникальных Unknown рынков")
    
    if not all_markets:
        print("\n⚠️  Не найдено рынков для анализа")
        return
    
    # Анализ паттернов
    print("\n" + "=" * 80)
    print("📊 АНАЛИЗ ПАТТЕРНОВ")
    print("=" * 80)
    
    patterns = {
        "dates": [],
        "prices": [],
        "updown": [],
        "vs": [],
        "nfl": [],
        "nba": [],
        "bitcoin": [],
        "ethereum": [],
        "short": [],
        "empty": []
    }
    
    keywords = Counter()
    stop_words = {
        "will", "the", "be", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "are", "was", "were", "been", "being"
    }
    
    for market in all_markets:
        text = market["combined_text"]
        
        # Даты
        if re.search(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|november|october|december|january|february|march|april|may|june|july|august|september', text, re.IGNORECASE):
            patterns["dates"].append(market)
        
        # Цены
        if re.search(r'\$[\d,]+|\d+\.\d+%|\d+%|\d+[km]', text):
            patterns["prices"].append(market)
        
        # Up or down
        if "up or down" in text or "updown" in text or "up-down" in text:
            patterns["updown"].append(market)
        
        # VS
        if " vs " in text or " versus " in text:
            patterns["vs"].append(market)
        
        # NFL
        if "nfl" in text or any(team in text for team in ["patriots", "cowboys", "packers", "chiefs", "rams", "bills"]):
            patterns["nfl"].append(market)
        
        # NBA
        if "nba" in text or any(team in text for team in ["lakers", "warriors", "celtics", "heat", "bulls"]):
            patterns["nba"].append(market)
        
        # Bitcoin
        if "bitcoin" in text or "btc" in text:
            patterns["bitcoin"].append(market)
        
        # Ethereum
        if "ethereum" in text or "eth" in text:
            patterns["ethereum"].append(market)
        
        # Короткий текст
        if len(text) < 30:
            patterns["short"].append(market)
        
        # Пустой
        if not text.strip():
            patterns["empty"].append(market)
        
        # Ключевые слова
        words = re.findall(r'\b\w+\b', text)
        for word in words:
            word_clean = word.strip(".,!?;:()[]{}'\"-").lower()
            if len(word_clean) > 2 and word_clean not in stop_words:
                keywords[word_clean] += 1
    
    print(f"\n📋 Статистика паттернов:")
    for pattern_name, markets_list in patterns.items():
        if markets_list:
            print(f"   {pattern_name:<15} {len(markets_list):>4} ({len(markets_list)/len(all_markets)*100:>5.1f}%)")
    
    print(f"\n📝 Топ-30 ключевых слов:")
    for word, count in keywords.most_common(30):
        print(f"   {word:<25} {count:>4}")
    
    # Примеры для каждой категории
    print(f"\n📋 Примеры по паттернам:")
    
    if patterns["updown"]:
        print(f"\n1. Up or down ({len(patterns['updown'])}):")
        for market in patterns["updown"][:5]:
            print(f"   - {market['question'][:80] or market['slug'][:80]}")
    
    if patterns["vs"]:
        print(f"\n2. VS ({len(patterns['vs'])}):")
        for market in patterns["vs"][:5]:
            print(f"   - {market['question'][:80] or market['slug'][:80]}")
    
    if patterns["bitcoin"]:
        print(f"\n3. Bitcoin ({len(patterns['bitcoin'])}):")
        for market in patterns["bitcoin"][:5]:
            print(f"   - {market['question'][:80] or market['slug'][:80]}")
    
    if patterns["nfl"]:
        print(f"\n4. NFL ({len(patterns['nfl'])}):")
        for market in patterns["nfl"][:5]:
            print(f"   - {market['question'][:80] or market['slug'][:80]}")
    
    if patterns["short"]:
        print(f"\n5. Короткий текст ({len(patterns['short'])}):")
        for market in patterns["short"][:5]:
            print(f"   - {market['question'][:80] or market['slug'][:80] or 'N/A'} (length: {market['text_length']})")
    
    # Сохраняем результаты
    results = {
        "total": len(all_markets),
        "patterns": {k: len(v) for k, v in patterns.items()},
        "top_keywords": dict(keywords.most_common(50)),
        "samples": {
            "updown": [{"question": m["question"], "slug": m["slug"]} for m in patterns["updown"][:20]],
            "vs": [{"question": m["question"], "slug": m["slug"]} for m in patterns["vs"][:20]],
            "bitcoin": [{"question": m["question"], "slug": m["slug"]} for m in patterns["bitcoin"][:20]],
            "nfl": [{"question": m["question"], "slug": m["slug"]} for m in patterns["nfl"][:20]],
            "short": [{"question": m["question"], "slug": m["slug"], "length": m["text_length"]} for m in patterns["short"][:20]]
        }
    }
    
    with open("unknown_real_analysis.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Результаты сохранены в unknown_real_analysis.json")
    print("\n" + "=" * 80)
    
    return results

if __name__ == "__main__":
    analyze_unknown_real()





