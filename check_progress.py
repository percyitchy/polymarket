#!/usr/bin/env python3
"""
Скрипт для проверки прогресса обработки кошельков
Показывает текущий статус очереди, скорость обработки и оценку времени
"""

import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import PolymarketDB

load_dotenv()

def check_progress():
    """Проверить прогресс обработки кошельков"""
    db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
    db = PolymarketDB(db_path)
    
    # Получаем статистику
    stats = db.get_queue_stats()
    wallet_stats = db.get_wallet_stats()
    
    # Подсчитываем completed jobs
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Статусы заданий
        cursor.execute("SELECT status, COUNT(*) FROM wallet_analysis_jobs GROUP BY status")
        status_counts = dict(cursor.fetchall())
        
        completed = status_counts.get("completed", 0)
        pending = status_counts.get("pending", 0)
        processing = status_counts.get("processing", 0)
        failed = status_counts.get("failed", 0)
        total_jobs = completed + pending + processing + failed
        
        # Кошельки обработанные за последние периоды
        now = datetime.now()
        
        # За последнюю минуту
        one_min_ago = (now - timedelta(minutes=1)).isoformat()
        cursor.execute("SELECT COUNT(*) FROM wallets WHERE updated_at > ?", (one_min_ago,))
        last_min = cursor.fetchone()[0]
        
        # За последние 5 минут
        five_min_ago = (now - timedelta(minutes=5)).isoformat()
        cursor.execute("SELECT COUNT(*) FROM wallets WHERE updated_at > ?", (five_min_ago,))
        last_5min = cursor.fetchone()[0]
        
        # За последний час
        one_hour_ago = (now - timedelta(hours=1)).isoformat()
        cursor.execute("SELECT COUNT(*) FROM wallets WHERE updated_at > ?", (one_hour_ago,))
        last_hour = cursor.fetchone()[0]
        
        # Всего кошельков
        cursor.execute("SELECT COUNT(*) FROM wallets")
        total_wallets = cursor.fetchone()[0]
    
    # Выводим результаты
    print("=" * 80)
    print("📊 ПРОГРЕСС ОБРАБОТКИ КОШЕЛЬКОВ")
    print("=" * 80)
    print()
    
    print("📋 ОЧЕРЕДЬ АНАЛИЗА:")
    print(f"   ✅ Проверено (completed): {completed}")
    print(f"   ⏳ В обработке (processing): {processing}")
    print(f"   📋 Ожидают (pending): {pending}")
    if failed > 0:
        print(f"   ❌ Ошибки (failed): {failed}")
    print(f"   📊 Всего заданий: {total_jobs}")
    print()
    
    print("💾 БАЗА ДАННЫХ:")
    print(f"   Всего кошельков: {total_wallets}")
    print(f"   Отслеживаемых: {wallet_stats.get('tracked_wallets', 0)}")
    print()
    
    print("⚡ СКОРОСТЬ ОБРАБОТКИ:")
    if last_min > 0:
        print(f"   За последнюю минуту: {last_min} кошельков")
    if last_5min > 0:
        rate_5min = last_5min / 5
        print(f"   За последние 5 минут: {last_5min} кошельков (~{rate_5min:.1f}/мин)")
    if last_hour > 0:
        rate_hour = last_hour / 60
        print(f"   За последний час: {last_hour} кошельков (~{rate_hour:.1f}/мин)")
    print()
    
    # Оценка времени
    if pending + processing > 0 and (last_5min > 0 or last_hour > 0):
        remaining = pending + processing
        
        # Используем скорость за последние 5 минут, если доступна, иначе за час
        if last_5min > 0:
            rate = last_5min / 5
        elif last_hour > 0:
            rate = last_hour / 60
        else:
            rate = 0
        
        if rate > 0:
            minutes_left = remaining / rate
            hours_left = minutes_left / 60
            
            print("⏱️  ОЦЕНКА ВРЕМЕНИ:")
            print(f"   Осталось обработать: {remaining} кошельков")
            if hours_left >= 1:
                print(f"   Примерно: {hours_left:.1f} часов ({minutes_left:.0f} минут)")
            else:
                print(f"   Примерно: {minutes_left:.0f} минут")
            print()
    
    # Прогресс в процентах
    if total_jobs > 0:
        progress = (completed / total_jobs) * 100
        print(f"📈 ПРОГРЕСС: {progress:.1f}% ({completed}/{total_jobs})")
        print()
    
    print("=" * 80)
    print("💡 Для повторной проверки запустите: python3 check_progress.py")
    print("=" * 80)

if __name__ == "__main__":
    check_progress()
