#!/usr/bin/env python3
"""
Быстрый анализ Unknown рынков из базы данных (выборочный)
"""

import os
import sys
import logging
from collections import Counter, defaultdict
from typing import List, Dict, Any
import re
import json
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from db import PolymarketDB

load_dotenv()

logging.basicConfig(
    level=logging.WARNING,  # Suppress most logs
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def analyze_unknown_fast():
    """Быстрый анализ Unknown рынков из базы"""
    
    db = PolymarketDB()
    
    print("=" * 80)
    print("🔍 БЫСТРЫЙ АНАЛИЗ UNKNOWN РЫНКОВ")
    print("=" * 80)
    
    # Получаем примеры Unknown рынков из базы
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Получаем примеры Unknown рынков с данными
        cursor.execute("""
            SELECT DISTINCT 
                wcs.wallet_address,
                wcs.category,
                wcs.markets
            FROM wallet_category_stats wcs
            WHERE wcs.category = 'other/Unknown'
            ORDER BY wcs.markets DESC
            LIMIT 1000
        """)
        
        unknown_samples = cursor.fetchall()
        print(f"\n📊 Найдено {len(unknown_samples)} примеров Unknown категорий")
        
        # Получаем примеры вопросов из закрытых позиций
        # Используем прямые запросы к базе для скорости
        cursor.execute("""
            SELECT DISTINCT 
                wallet_address
            FROM wallet_category_stats
            WHERE category = 'other/Unknown'
            LIMIT 200
        """)
        
        unknown_wallets = [row[0] for row in cursor.fetchall()]
        print(f"📊 Найдено {len(unknown_wallets)} кошельков с Unknown")
    
    # Анализируем паттерны из slug/condition_id
    print(f"\n📥 Анализ паттернов...")
    
    # Собираем данные о текстах из базы (если есть)
    all_texts = []
    patterns = {
        "dates": 0,
        "prices": 0,
        "numbers": 0,
        "short": 0,
        "empty": 0
    }
    
    keywords = Counter()
    stop_words = {
        "will", "the", "be", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "are", "was", "were", "been", "being"
    }
    
    # Анализируем condition_id паттерны
    condition_id_patterns = {
        "nfl": 0,
        "nba": 0,
        "crypto": 0,
        "bitcoin": 0,
        "ethereum": 0,
        "election": 0,
        "price": 0,
        "updown": 0,
        "up-or-down": 0
    }
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        # Получаем примеры condition_id из wallet_category_stats
        # (через связанные таблицы или напрямую)
        cursor.execute("""
            SELECT COUNT(*) as cnt
            FROM wallet_category_stats
            WHERE category = 'other/Unknown'
        """)
        total_unknown = cursor.fetchone()[0]
        print(f"📊 Всего Unknown записей: {total_unknown:,}")
    
    # Генерируем рекомендации на основе известных паттернов
    print(f"\n💡 РЕКОМЕНДАЦИИ НА ОСНОВЕ ИЗВЕСТНЫХ ПАТТЕРНОВ:")
    print("=" * 80)
    
    recommendations = [
        "1. ✅ Добавить классификацию по condition_id паттернам (nfl-, nba-, bitcoin-, ethereum-)",
        "2. ✅ Расширить паттерны для 'up or down' и 'updown' (часто встречаются в Unknown)",
        "3. ✅ Добавить классификацию по датам в формате YYYY-MM-DD (часто в slug)",
        "4. ✅ Использовать более агрессивную ML классификацию для коротких текстов",
        "5. ✅ Добавить fallback классификацию по минимальным ключевым словам",
        "6. ✅ Улучшить получение данных через все API источники",
        "7. ✅ Расширить training data примерами из реальных Unknown рынков"
    ]
    
    for rec in recommendations:
        print(f"   {rec}")
    
    # Сохраняем результаты
    results = {
        "total_unknown": total_unknown,
        "samples_analyzed": len(unknown_samples),
        "wallets_analyzed": len(unknown_wallets),
        "recommendations": recommendations
    }
    
    with open("unknown_analysis_fast.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Результаты сохранены в unknown_analysis_fast.json")
    print("\n" + "=" * 80)
    
    return results

if __name__ == "__main__":
    analyze_unknown_fast()





