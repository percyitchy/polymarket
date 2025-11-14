#!/usr/bin/env python3
from db import PolymarketDB

db = PolymarketDB()
stats = db.get_wallet_stats()

print("📊 СТАТИСТИКА КОШЕЛЬКОВ ДЛЯ СИГНАЛОВ:")
print(f"   Всего кошельков в базе: {stats.get('total_wallets', 0)}")
print(f"   Отслеживаемых кошельков: {stats.get('tracked_wallets', 0)}")

print("\n📋 Критерии для отслеживания:")
print("   - traded_total >= 6")
print("   - win_rate >= 0.75")
print("   - daily_trading_frequency <= 20.0 (или NULL)")

# Проверим детали
with db.get_connection() as conn:
    cursor = conn.cursor()
    
    # Общая статистика
    cursor.execute("SELECT COUNT(*) FROM wallets")
    total = cursor.fetchone()[0]
    
    # Отслеживаемые (соответствуют критериям)
    cursor.execute("""
        SELECT COUNT(*) FROM wallets
        WHERE traded_total >= 6 
        AND traded_total <= 1000
        AND win_rate >= 0.75
        AND (daily_trading_frequency <= 20.0 OR daily_trading_frequency IS NULL)
    """)
    tracked = cursor.fetchone()[0]
    
    print(f"\n📈 Детальная статистика:")
    print(f"   Всего в таблице wallets: {total}")
    print(f"   Отслеживаемых (по критериям): {tracked}")

