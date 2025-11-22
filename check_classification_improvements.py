#!/usr/bin/env python3
"""
Проверка улучшений классификации после оптимизации
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

def check_classification_stats():
    """Проверить статистику классификации"""
    db_path = os.getenv('DB_PATH', 'polymarket_notifier.db')
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)
    
    db = PolymarketDB(db_path)
    
    print("=" * 80)
    print("📊 ПРОВЕРКА УЛУЧШЕНИЙ КЛАССИФИКАЦИИ")
    print("=" * 80)
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Общая статистика
        cursor.execute("""
            SELECT 
                category,
                COUNT(*) as wallets,
                SUM(markets) as total_markets,
                AVG(winrate) as avg_winrate,
                SUM(pnl) as total_pnl
            FROM wallet_category_stats
            GROUP BY category
            ORDER BY total_markets DESC
        """)
        
        results = cursor.fetchall()
        
        total_markets = sum(r[2] for r in results)
        unknown_markets = next((r[2] for r in results if r[0] == "other/Unknown"), 0)
        unknown_pct = (unknown_markets / total_markets * 100) if total_markets > 0 else 0
        
        print(f"\n📈 Общая статистика:")
        print(f"   Всего рынков: {total_markets:,}")
        print(f"   Unknown: {unknown_markets:,} ({unknown_pct:.2f}%)")
        print(f"   Классифицировано: {total_markets - unknown_markets:,} ({100 - unknown_pct:.2f}%)")
        
        print(f"\n📋 Распределение по категориям:")
        print(f"{'Категория':<30} {'Рынков':>12} {'%':>8} {'Кошельков':>12}")
        print("-" * 80)
        
        for category, wallets, markets, avg_wr, total_pnl in results[:20]:
            pct = (markets / total_markets * 100) if total_markets > 0 else 0
            print(f"{category:<30} {markets:>12,} {pct:>7.2f}% {wallets:>12,}")
        
        # Проверка кэша
        cache_db_path = "polymarket_market_cache.db"
        cache_size = 0
        if os.path.exists(cache_db_path):
            try:
                import sqlite3
                cache_conn = sqlite3.connect(cache_db_path)
                cache_cursor = cache_conn.cursor()
                cache_cursor.execute("SELECT COUNT(*) FROM market_cache")
                cache_size = cache_cursor.fetchone()[0]
                cache_conn.close()
            except:
                pass
        
        print(f"\n💾 Кэш:")
        print(f"   Записей в кэше: {cache_size:,}")
        
        # Проверка ML классификатора
        print(f"\n🤖 ML Классификатор:")
        try:
            from ml_classifier import SKLEARN_AVAILABLE, TRAINING_DATA
            if SKLEARN_AVAILABLE:
                print(f"   ✅ Доступен")
                print(f"   Обучение на {len(TRAINING_DATA)} примерах")
            else:
                print(f"   ⚠️  Недоступен (scikit-learn не установлен)")
        except:
            print(f"   ⚠️  Ошибка при проверке")
        
        # Сравнение с предыдущими результатами
        print(f"\n📊 Сравнение:")
        baseline_unknown_pct = 63.59  # Из предыдущего анализа
        improvement = baseline_unknown_pct - unknown_pct
        print(f"   Baseline (Фаза 5): {baseline_unknown_pct:.2f}% Unknown")
        print(f"   Текущий: {unknown_pct:.2f}% Unknown")
        if improvement > 0:
            print(f"   ✅ Улучшение: -{improvement:.2f} п.п.")
        elif improvement < 0:
            print(f"   ⚠️  Ухудшение: +{abs(improvement):.2f} п.п.")
        else:
            print(f"   ➡️  Без изменений")
        
        print("\n" + "=" * 80)
        
        return {
            "total_markets": total_markets,
            "unknown_markets": unknown_markets,
            "unknown_pct": unknown_pct,
            "improvement": improvement,
            "cache_size": cache_size
        }

if __name__ == "__main__":
    results = check_classification_stats()
    print(f"\n✅ Проверка завершена.")
    if results["improvement"] > 0:
        print(f"🎉 Unknown снизился на {results['improvement']:.2f} п.п.!")

