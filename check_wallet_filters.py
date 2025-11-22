#!/usr/bin/env python3
"""
Проверка новых фильтров кошельков:
- Минимум 25,000$ overall volume
- Максимум 25 трейдов в день
- Средний PnL на рынок > 150$
"""

import os
import sys
import logging
from dotenv import load_dotenv
from db import PolymarketDB

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_wallet_filters():
    """Проверить применение новых фильтров"""
    db_path = os.getenv('DB_PATH', 'polymarket_notifier.db')
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)
    
    db = PolymarketDB(db_path)
    
    print("=" * 80)
    print("📊 ПРОВЕРКА НОВЫХ ФИЛЬТРОВ КОШЕЛЬКОВ")
    print("=" * 80)
    
    # Параметры фильтров
    MIN_VOLUME = 25000.0
    MAX_DAILY_FREQUENCY = 25.0
    MIN_AVG_PNL = 150.0
    
    print(f"\n📋 Критерии фильтрации:")
    print(f"   • Минимум volume: ${MIN_VOLUME:,.0f}")
    print(f"   • Максимум трейдов/день: {MAX_DAILY_FREQUENCY}")
    print(f"   • Минимум средний PnL/рынок: ${MIN_AVG_PNL:.0f}")
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Получаем все кошельки
        cursor.execute("""
            SELECT 
                address,
                traded_total,
                daily_trading_frequency,
                realized_pnl_total
            FROM wallets
            WHERE traded_total > 0
        """)
        
        wallets = cursor.fetchall()
        
        print(f"\n📈 Анализ кошельков:")
        print(f"   Всего кошельков: {len(wallets):,}")
        
        # Проверяем каждый критерий
        passed_volume = []
        passed_frequency = []
        passed_avg_pnl = []
        passed_all = []
        
        # Для проверки avg_pnl нужно получить данные из wallet_category_stats
        cursor.execute("""
            SELECT 
                wallet_address,
                SUM(markets) as total_markets,
                SUM(pnl) as total_pnl
            FROM wallet_category_stats
            GROUP BY wallet_address
        """)
        
        category_stats = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
        
        for wallet in wallets:
            address, traded_total, daily_freq, pnl_total = wallet
            
            # Проверка volume (нужно получить из category_stats или использовать pnl_total как proxy)
            # Для точной проверки нужны данные из closed positions, но используем приближение
            volume_ok = True  # Будет проверено через category_stats
            
            # Проверка frequency
            if daily_freq and daily_freq <= MAX_DAILY_FREQUENCY:
                passed_frequency.append(address)
            
            # Проверка avg_pnl
            if address in category_stats:
                total_markets, total_pnl = category_stats[address]
                if total_markets > 0:
                    avg_pnl = total_pnl / total_markets
                    if avg_pnl >= MIN_AVG_PNL:
                        passed_avg_pnl.append(address)
            
            # Проверка volume через category_stats
            if address in category_stats:
                total_markets, total_pnl = category_stats[address]
                # Приблизительный volume (используем pnl как proxy или получаем из category_stats)
                cursor.execute("""
                    SELECT SUM(volume) FROM wallet_category_stats
                    WHERE wallet_address = ?
                """, (address,))
                volume_result = cursor.fetchone()
                if volume_result and volume_result[0]:
                    volume = volume_result[0]
                    if volume >= MIN_VOLUME:
                        passed_volume.append(address)
            
            # Проверка всех критериев
            if (address in passed_frequency and 
                address in passed_avg_pnl and 
                address in passed_volume):
                passed_all.append(address)
        
        print(f"\n✅ Результаты фильтрации:")
        print(f"   Прошли фильтр volume (>= ${MIN_VOLUME:,.0f}): {len(passed_volume):,}")
        print(f"   Прошли фильтр frequency (<= {MAX_DAILY_FREQUENCY}): {len(passed_frequency):,}")
        print(f"   Прошли фильтр avg_pnl (>= ${MIN_AVG_PNL:.0f}): {len(passed_avg_pnl):,}")
        print(f"   Прошли ВСЕ фильтры: {len(passed_all):,}")
        
        # Проверка A-list трейдеров
        cursor.execute("""
            SELECT COUNT(DISTINCT wallet_address)
            FROM wallet_category_stats
            WHERE is_a_list_trader = 1
        """)
        
        a_list_count = cursor.fetchone()[0] or 0
        
        print(f"\n⭐ A-list трейдеры:")
        print(f"   Всего A-list трейдеров: {a_list_count:,}")
        
        # Статистика по категориям для A-list
        cursor.execute("""
            SELECT 
                category,
                COUNT(DISTINCT wallet_address) as wallets,
                SUM(markets) as markets
            FROM wallet_category_stats
            WHERE is_a_list_trader = 1
            GROUP BY category
            ORDER BY markets DESC
            LIMIT 10
        """)
        
        a_list_categories = cursor.fetchall()
        
        if a_list_categories:
            print(f"\n📊 A-list трейдеры по категориям:")
            print(f"{'Категория':<30} {'Трейдеров':>12} {'Рынков':>12}")
            print("-" * 60)
            for cat, wallets, markets in a_list_categories:
                print(f"{cat:<30} {wallets:>12,} {markets:>12,}")
        
        print("\n" + "=" * 80)
        
        total_wallets_count = len(wallets) if isinstance(wallets, list) else 0
        
        return {
            "total_wallets": total_wallets_count,
            "passed_volume": len(passed_volume),
            "passed_frequency": len(passed_frequency),
            "passed_avg_pnl": len(passed_avg_pnl),
            "passed_all": len(passed_all),
            "a_list_count": a_list_count
        }

if __name__ == "__main__":
    results = check_wallet_filters()
    print(f"\n✅ Проверка завершена.")
    print(f"   Из {results['total_wallets']:,} кошельков {results['passed_all']:,} проходят все фильтры")

