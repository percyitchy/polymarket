#!/bin/bash
# Скрипт для проверки блокировок сигналов на сервере

echo "======================================================================"
echo "ПРОВЕРКА БЛОКИРОВОК СИГНАЛОВ НА СЕРВЕРЕ"
echo "======================================================================"

LOG_FILE="/opt/polymarket-bot/polymarket_notifier.log"
DB_FILE="/opt/polymarket-bot/polymarket_notifier.db"

echo ""
echo "1. ПОСЛЕДНИЕ БЛОКИРОВКИ В ЛОГАХ:"
echo "======================================================================"
if [ -f "$LOG_FILE" ]; then
    grep -i "BLOCKED\|blocked\|suppress" "$LOG_FILE" | tail -30
else
    echo "⚠️  Лог файл не найден: $LOG_FILE"
fi

echo ""
echo "2. СТАТИСТИКА БЛОКИРОВОК:"
echo "======================================================================"
if [ -f "$LOG_FILE" ]; then
    echo "Блокировки по причинам:"
    grep -i "BLOCKED" "$LOG_FILE" | grep -oE "(below_threshold|market_inactive|price|cooldown|insufficient_position|no_trigger)" | sort | uniq -c | sort -rn
else
    echo "⚠️  Лог файл не найден"
fi

echo ""
echo "3. ПОСЛЕДНИЕ КОНСЕНСУСЫ:"
echo "======================================================================"
if [ -f "$DB_FILE" ]; then
    python3 << 'EOF'
import sqlite3
import json
from datetime import datetime, timezone

db = sqlite3.connect('/opt/polymarket-bot/polymarket_notifier.db')
cursor = db.cursor()

cursor.execute('SELECT k, data, updated_at FROM rolling_buys ORDER BY updated_at DESC LIMIT 10')
rows = cursor.fetchall()

for k, data_str, updated_at in rows:
    try:
        data = json.loads(data_str)
        events = data.get('events', [])
        wallets = {e.get('wallet') for e in events if e.get('wallet')}
        market_title = events[0].get('marketTitle', 'N/A') if events else 'N/A'
        condition_id = events[0].get('conditionId') if events and 'conditionId' in events[0] else None
        
        print(f"{updated_at[:19]}: {len(wallets)} кошельков - {market_title[:50]}")
        if condition_id:
            print(f"  Condition ID: {condition_id[:30]}...")
        else:
            print(f"  ⚠️  Condition ID отсутствует")
    except:
        pass

db.close()
EOF
else
    echo "⚠️  База данных не найдена: $DB_FILE"
fi

echo ""
echo "4. НАСТРОЙКИ ИЗ .ENV:"
echo "======================================================================"
if [ -f "/opt/polymarket-bot/.env" ]; then
    grep -E "MIN_CONSENSUS|ALERT_WINDOW_MIN|MIN_TOTAL_POSITION_USD|ALERT_COOLDOWN_MIN" /opt/polymarket-bot/.env | head -10
else
    echo "⚠️  .env файл не найден"
fi

echo ""
echo "5. СТАТУС СЕРВИСА:"
echo "======================================================================"
systemctl status polymarket-notifier --no-pager | head -15

echo ""
echo "======================================================================"
echo "РЕКОМЕНДАЦИИ:"
echo "======================================================================"
echo "1. Проверьте детальные логи блокировок выше"
echo "2. Убедитесь, что MIN_TOTAL_POSITION_USD не слишком высокий"
echo "3. Перезапустите бот после исправления кода:"
echo "   sudo systemctl restart polymarket-notifier"
echo "4. Проверьте, что новые события содержат condition_id"

