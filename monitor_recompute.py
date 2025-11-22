#!/usr/bin/env python3
"""
Мониторинг прогресса пересчёта категорий
"""

import os
import time
from db import PolymarketDB
from dotenv import load_dotenv

load_dotenv()

db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
if not os.path.isabs(db_path):
    db_path = os.path.abspath(db_path)

db = PolymarketDB(db_path)

def get_status():
    """Получить текущий статус пересчёта"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Статусы в очереди
        cursor.execute('''
            SELECT status, COUNT(*) 
            FROM wallet_analysis_jobs 
            GROUP BY status
        ''')
        
        jobs_by_status = {}
        for status, count in cursor.fetchall():
            jobs_by_status[status] = count
        
        total_jobs = sum(jobs_by_status.values())
        completed = jobs_by_status.get('completed', 0)
        pending = jobs_by_status.get('pending', 0)
        processing = jobs_by_status.get('processing', 0)
        failed = jobs_by_status.get('failed', 0)
        
        # Статистика по категориям
        cursor.execute('SELECT SUM(markets) FROM wallet_category_stats')
        total_markets = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT SUM(markets) FROM wallet_category_stats WHERE category != "other/Unknown"')
        classified_markets = cursor.fetchone()[0] or 0
        
        return {
            'total_jobs': total_jobs,
            'completed': completed,
            'pending': pending,
            'processing': processing,
            'failed': failed,
            'total_markets': total_markets,
            'classified_markets': classified_markets,
            'unknown_markets': total_markets - classified_markets
        }

def main():
    print("=" * 100)
    print("МОНИТОРИНГ ПЕРЕСЧЁТА КАТЕГОРИЙ")
    print("=" * 100)
    print()
    
    last_completed = 0
    start_time = time.time()
    
    while True:
        status = get_status()
        
        total = status['total_jobs']
        completed = status['completed']
        pending = status['pending']
        processing = status['processing']
        failed = status['failed']
        
        if total == 0:
            print("Очередь пуста. Пересчёт не запущен или завершён.")
            break
        
        progress_pct = (completed / total) * 100
        remaining = pending + processing
        
        # Рассчитать скорость
        elapsed = time.time() - start_time
        if elapsed > 0 and completed > last_completed:
            rate = (completed - last_completed) / elapsed if elapsed > 0 else 0
            if rate > 0 and remaining > 0:
                eta_seconds = remaining / rate
                eta_minutes = eta_seconds / 60
                eta_str = f"{eta_minutes:.1f} мин"
            else:
                eta_str = "рассчитывается..."
        else:
            rate = 0
            eta_str = "рассчитывается..."
        
        # Очистить экран (опционально)
        print("\033[2J\033[H", end="")  # Очистить экран
        
        print("=" * 100)
        print("СТАТУС ПЕРЕСЧЁТА")
        print("=" * 100)
        print(f"Всего jobs: {total:,}")
        print(f"  ✅ Завершено: {completed:,}")
        print(f"  ⏳ Ожидают: {pending:,}")
        print(f"  🔄 Обрабатываются: {processing:,}")
        print(f"  ❌ Ошибок: {failed:,}")
        print()
        print(f"Прогресс: {progress_pct:.1f}%")
        print(f"Осталось: {remaining:,} кошельков")
        if rate > 0:
            print(f"Скорость: {rate:.2f} кошельков/сек")
            print(f"⏱️  Примерное время до завершения: {eta_str}")
        print()
        
        # Статистика по категориям
        total_markets = status['total_markets']
        classified = status['classified_markets']
        unknown = status['unknown_markets']
        
        print("=" * 100)
        print("СТАТИСТИКА КАТЕГОРИЙ")
        print("=" * 100)
        print(f"Всего рынков: {total_markets:,}")
        print(f"Классифицировано: {classified:,} ({classified/total_markets*100:.2f}%)")
        print(f"Unknown: {unknown:,} ({unknown/total_markets*100:.2f}%)")
        print("=" * 100)
        
        # Проверка завершения
        if pending == 0 and processing == 0:
            print()
            print("✅ ПЕРЕСЧЁТ ЗАВЕРШЁН!")
            print()
            break
        
        last_completed = completed
        start_time = time.time()
        time.sleep(10)  # Обновление каждые 10 секунд

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nМониторинг остановлен пользователем.")

