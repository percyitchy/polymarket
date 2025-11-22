#!/usr/bin/env python3
"""
Проверка логов бота для поиска структуры события
Ищет логи по времени сигнала или ключевым словам
"""
import sys
import subprocess
import re
from datetime import datetime, timezone, timedelta

def check_logs_by_time(target_time_str: str = "2025-11-18 22:14:37"):
    """Проверка логов по времени сигнала"""
    print(f"🔍 Поиск логов для времени: {target_time_str} UTC")
    print("=" * 80)
    
    # Парсим время
    try:
        target_time = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M:%S")
        target_time = target_time.replace(tzinfo=timezone.utc)
        
        # Ищем логи за период ±30 минут
        start_time = target_time - timedelta(minutes=30)
        end_time = target_time + timedelta(minutes=30)
        
        start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
        end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"📅 Период поиска: {start_str} - {end_str} UTC")
        
    except Exception as e:
        print(f"❌ Ошибка парсинга времени: {e}")
        return
    
    # Команды для поиска в логах
    commands = [
        # Поиск структуры события
        f"sudo journalctl -u polymarket-bot --since '{start_str}' --until '{end_str}' | grep -A 30 'SPORTS_DETECT\\|GAMMA.*DEBUG\\|Event structure'",
        
        # Поиск по ключевым словам FIFA/Brazil/Tunisia
        f"sudo journalctl -u polymarket-bot --since '{start_str}' --until '{end_str}' | grep -i -A 20 'fif\\|bra\\|tun\\|sports'",
        
        # Поиск категории
        f"sudo journalctl -u polymarket-bot --since '{start_str}' --until '{end_str}' | grep -A 10 'Category for condition'",
        
        # Поиск URL-related полей
        f"sudo journalctl -u polymarket-bot --since '{start_str}' --until '{end_str}' | grep -A 5 'URL-related fields'",
    ]
    
    print("\n📋 Команды для выполнения на сервере:\n")
    for i, cmd in enumerate(commands, 1):
        print(f"{i}. {cmd}\n")


def check_logs_by_keywords(keywords: list):
    """Проверка логов по ключевым словам"""
    print(f"🔍 Поиск логов по ключевым словам: {', '.join(keywords)}")
    print("=" * 80)
    
    keywords_pattern = "|".join(keywords)
    
    commands = [
        # Общий поиск
        f"sudo journalctl -u polymarket-bot -n 5000 | grep -i -E '{keywords_pattern}' | head -50",
        
        # С контекстом
        f"sudo journalctl -u polymarket-bot -n 5000 | grep -i -E '{keywords_pattern}' -A 20 | head -100",
        
        # Структура события
        f"sudo journalctl -u polymarket-bot -n 5000 | grep -i -E '{keywords_pattern}' -B 5 -A 30 | grep -A 30 'SPORTS_DETECT\\|GAMMA.*DEBUG'",
    ]
    
    print("\n📋 Команды для выполнения на сервере:\n")
    for i, cmd in enumerate(commands, 1):
        print(f"{i}. {cmd}\n")


def check_database_for_event():
    """Проверка базы данных на наличие события"""
    print("🔍 Проверка базы данных")
    print("=" * 80)
    
    script = """
import sqlite3
from datetime import datetime, timezone, timedelta

db_path = 'polymarket_notifier.db'
try:
    db = sqlite3.connect(db_path)
    cursor = db.cursor()
    
    # Ищем недавние алерты с ключевыми словами
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    
    cursor.execute('''
        SELECT condition_id, sent_at, market_title, total_usd
        FROM alerts_sent
        WHERE sent_at >= ?
        ORDER BY sent_at DESC
        LIMIT 100
    ''', (week_ago,))
    
    print("Недавние сигналы:")
    for condition_id, sent_at, title, total_usd in cursor.fetchall():
        if title and ('fif' in title.lower() or 'bra' in title.lower() or 'tun' in title.lower() or 'sports' in title.lower()):
            print(f"\\n✅ Найден сигнал:")
            print(f"   Condition ID: {condition_id}")
            print(f"   Время: {sent_at}")
            print(f"   Название: {title}")
            print(f"   Total USD: {total_usd}")
            print(f"\\nДля проверки структуры:")
            print(f"   python3 check_event_structure.py --condition-id {condition_id}")
    
    db.close()
except Exception as e:
    print(f"Ошибка: {e}")
"""
    
    print("📋 Скрипт для проверки базы данных:")
    print("=" * 80)
    print(script)
    print("\nИли выполните на сервере:")
    print("cd /opt/polymarket-bot")
    print("python3 -c \"...\"  # (вставьте скрипт выше)")


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--time":
            time_str = sys.argv[2] if len(sys.argv) > 2 else "2025-11-18 22:14:37"
            check_logs_by_time(time_str)
        elif sys.argv[1] == "--keywords":
            keywords = sys.argv[2:] if len(sys.argv) > 2 else ["fif", "bra", "tun", "sports"]
            check_logs_by_keywords(keywords)
        elif sys.argv[1] == "--db":
            check_database_for_event()
        else:
            print("Использование:")
            print("  python3 check_logs_for_event.py --time [YYYY-MM-DD HH:MM:SS]")
            print("  python3 check_logs_for_event.py --keywords [keyword1] [keyword2] ...")
            print("  python3 check_logs_for_event.py --db")
            print("\nПримеры:")
            print("  python3 check_logs_for_event.py --time '2025-11-18 22:14:37'")
            print("  python3 check_logs_for_event.py --keywords fif bra tun")
            print("  python3 check_logs_for_event.py --db")
    else:
        # По умолчанию проверяем по времени сигнала
        check_logs_by_time()
        print("\n" + "=" * 80)
        check_database_for_event()


if __name__ == "__main__":
    main()


