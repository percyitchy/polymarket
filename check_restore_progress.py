#!/usr/bin/env python3
"""
Быстрая проверка прогресса восстановления кошельков
"""

import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import PolymarketDB

load_dotenv()

db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
if not os.path.isabs(db_path):
    db_path = os.path.abspath(db_path)

db = PolymarketDB(db_path)

# Статистика кошельков
stats = db.get_wallet_stats()
queue_stats = db.get_queue_stats()

# Детальная статистика очереди
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
    
    # Кошельки с данными (проанализированные)
    cursor.execute("SELECT COUNT(*) FROM wallets WHERE traded_total > 0")
    analyzed_wallets = cursor.fetchone()[0]
    
    # Кошельки без данных (ожидают анализа)
    cursor.execute("SELECT COUNT(*) FROM wallets WHERE traded_total = 0")
    unanalyzed_wallets = cursor.fetchone()[0]

print("=" * 80)
print("📊 ПРОГРЕСС ВОССТАНОВЛЕНИЯ И АНАЛИЗА КОШЕЛЬКОВ")
print("=" * 80)
print()

print("📁 КОШЕЛЬКИ В БАЗЕ:")
print(f"   Всего кошельков: {stats.get('total_wallets', 0):,}")
print(f"   Отслеживаемых: {stats.get('tracked_wallets', 0):,}")
print(f"   Проанализированных (с данными): {analyzed_wallets:,}")
print(f"   Ожидают анализа: {unanalyzed_wallets:,}")
print()

print("🔄 ОЧЕРЕДЬ АНАЛИЗА:")
print(f"   ✅ Завершено (completed): {completed:,}")
print(f"   ⏳ В обработке (processing): {processing:,}")
print(f"   📋 Ожидают (pending): {pending:,}")
if failed > 0:
    print(f"   ❌ Ошибки (failed): {failed:,}")
print(f"   📊 Всего заданий: {total_jobs:,}")
print()

# Процент выполнения
if total_jobs > 0:
    progress_pct = (completed / total_jobs) * 100
    print(f"📈 ПРОГРЕСС ОЧЕРЕДИ: {progress_pct:.1f}% ({completed:,}/{total_jobs:,})")
    
    # Оценка времени до завершения (если есть активность)
    if processing > 0 and last_5min > 0:
        rate_per_min = last_5min / 5
        if rate_per_min > 0:
            remaining = pending
            eta_minutes = remaining / rate_per_min
            eta_hours = eta_minutes / 60
            print(f"⏱️  ОЦЕНКА ВРЕМЕНИ: ~{eta_minutes:.0f} минут (~{eta_hours:.1f} часов)")
else:
    print("📈 ПРОГРЕСС: Нет данных")
print()

print("⚡ АКТИВНОСТЬ (обновления кошельков):")
print(f"   За последнюю минуту: {last_min:,}")
print(f"   За последние 5 минут: {last_5min:,}")
print(f"   За последний час: {last_hour:,}")
print()

print("=" * 80)
print("💡 КАК СЛЕДИТЬ ЗА ПРОГРЕССОМ:")
print("=" * 80)
print("1. Запустите эту команду: python3 check_restore_progress.py")
print("2. Проверьте логи: tail -f polymarket_notifier.log | grep -E '[MONITOR]|[HB]'")
print("3. Если включен heartbeat в Telegram, проверяйте сообщения там")
print("=" * 80)

