#!/usr/bin/env python3
"""
Diagnostic script to check database synchronization between collector and notifier
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import PolymarketDB

load_dotenv()

def main():
    db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)
    
    print("=" * 60)
    print("📊 ДИАГНОСТИКА СИНХРОНИЗАЦИИ БД")
    print("=" * 60)
    print(f"DB_PATH: {db_path}")
    print(f"File exists: {os.path.exists(db_path)}")
    if os.path.exists(db_path):
        size = os.path.getsize(db_path)
        print(f"File size: {size / 1024 / 1024:.2f} MB")
    
    db = PolymarketDB(db_path)
    
    # 1. Общая статистика
    stats = db.get_wallet_stats()
    print(f"\n1️⃣  Общая статистика:")
    print(f"   Total wallets: {stats.get('total_wallets', 0)}")
    print(f"   Tracked wallets: {stats.get('tracked_wallets', 0)}")
    
    # 2. Проверяем очередь
    queue_stats = db.get_queue_stats()
    print(f"\n2️⃣  Очередь:")
    print(f"   Completed: {queue_stats.get('completed_jobs', 0)}")
    print(f"   Failed: {queue_stats.get('failed_jobs', 0)}")
    print(f"   Pending: {queue_stats.get('pending_jobs', 0)}")
    print(f"   Processing: {queue_stats.get('processing_jobs', 0)}")
    
    # 3. Проверяем, сколько кошельков было обновлено недавно
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM wallets 
            WHERE datetime(updated_at) >= datetime(?)
        """, (one_hour_ago,))
        recent = cursor.fetchone()[0]
        print(f"\n3️⃣  Обновлено за последний час: {recent}")
    
    # 4. Проверяем критерии отслеживания
    three_months_ago = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        # Сколько кошельков НЕ проходят критерии
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN traded_total < 6 THEN 1 END) as low_trades,
                COUNT(CASE WHEN traded_total > 1200 THEN 1 END) as high_trades,
                COUNT(CASE WHEN win_rate < 0.70 THEN 1 END) as low_winrate,
                COUNT(CASE WHEN win_rate > 1.0 THEN 1 END) as high_winrate,
                COUNT(CASE WHEN daily_trading_frequency > 25.0 THEN 1 END) as high_freq,
                COUNT(CASE WHEN last_trade_at IS NULL THEN 1 END) as no_last_trade,
                COUNT(CASE WHEN last_trade_at IS NOT NULL AND datetime(last_trade_at) < datetime(?) THEN 1 END) as inactive
            FROM wallets
        """, (three_months_ago,))
        row = cursor.fetchone()
        total, low_trades, high_trades, low_winrate, high_winrate, high_freq, no_last_trade, inactive = row
        print(f"\n4️⃣  Причины исключения из отслеживания:")
        print(f"   Всего кошельков: {total}")
        print(f"   Мало трейдов (<6): {low_trades}")
        print(f"   Много трейдов (>1200): {high_trades}")
        print(f"   Низкий win_rate (<0.70): {low_winrate}")
        print(f"   Высокий win_rate (>1.0): {high_winrate}")
        print(f"   Высокая частота (>25.0): {high_freq}")
        print(f"   Нет last_trade_at: {no_last_trade}")
        print(f"   Неактивные (>90 дней): {inactive}")
    
    # 5. Проверяем, сколько кошельков добавлено сегодня
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_iso = today_start.isoformat()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM wallets 
            WHERE datetime(added_at) >= datetime(?)
        """, (today_start_iso,))
        added_today = cursor.fetchone()[0]
        print(f"\n5️⃣  Добавлено сегодня: {added_today}")
    
    print("\n" + "=" * 60)
    print("✅ Диагностика завершена")
    print("=" * 60)

if __name__ == "__main__":
    main()

