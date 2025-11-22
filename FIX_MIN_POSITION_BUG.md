# 🐛 Исправление проблемы с MIN_TOTAL_POSITION_USD

## Проблема

Сигналы с позицией меньше $2000 все еще проходят:
- Ethereum: 1,511 USDC ❌
- Bitcoin: 25 USDC ❌

## 🔍 Анализ кода

### Проверка происходит в STEP 10 (строка 2305-2317):

```python
# STEP 10: Check minimum total position size
logger.info(f"[CONSENSUS] Step 10/10: Checking minimum total position size: ${total_usd:.2f} >= ${self.min_total_position_usd:.2f}")
if total_usd < self.min_total_position_usd:
    logger.info(f"[CONSENSUS] ⏭️  BLOCKED: Insufficient total position size - ${total_usd:.2f} < ${self.min_total_position_usd:.2f}")
    return
```

### Возможные причины:

1. **Переменная не установлена в .env на сервере**
   - Значение по умолчанию: `2000.0` (строка 125)
   - Но если сервис не перезапущен, используется старое значение

2. **Сервис не был перезапущен после изменения .env**
   - `.env` загружается только при старте процесса
   - Изменения не применяются автоматически

3. **Логика repeat alert НЕ обходит проверку**
   - STEP 10 проверяет порог ДО STEP 11 (repeat alert)
   - Это правильно - проверка должна работать

## 🔧 Решение

### Шаг 1: Проверка на сервере

Выполните на сервере:

```bash
# 1. Проверьте значение в .env
grep MIN_TOTAL_POSITION_USD /opt/polymarket-bot/.env

# 2. Если отсутствует, добавьте:
echo "MIN_TOTAL_POSITION_USD=2000" >> /opt/polymarket-bot/.env

# 3. Проверьте что значение загружено в процесс
sudo journalctl -u polymarket-bot -n 200 | grep "MIN_TOTAL_POSITION_USD"
# Должно быть: [Config] MIN_TOTAL_POSITION_USD=$2000

# 4. Если значение не загружено, перезапустите сервис
sudo systemctl restart polymarket-bot

# 5. Проверьте логи последних сигналов
sudo journalctl -u polymarket-bot --since '1 hour ago' | grep -E '(Step 10|Insufficient total position)'
```

### Шаг 2: Проверка логов для конкретных сигналов

Найдите в логах записи для этих рынков:

```bash
# Для Ethereum сигнала (1,511 USDC)
sudo journalctl -u polymarket-bot --since '2025-11-19 09:28:00' --until '2025-11-19 09:29:00' | grep -E '(Step 10|1511|Insufficient)'

# Для Bitcoin сигнала (25 USDC)
sudo journalctl -u polymarket-bot --since '2025-11-19 09:54:00' --until '2025-11-19 09:55:00' | grep -E '(Step 10|25|Insufficient)'
```

### Шаг 3: Проверка базы данных

Проверьте есть ли старые алерты для этих рынков:

```bash
sqlite3 /opt/polymarket-bot/polymarket_notifier.db "
SELECT condition_id, outcome_index, side, total_usd, first_total_usd, sent_at 
FROM alerts_sent 
WHERE sent_at >= '2025-11-19 09:00:00'
ORDER BY sent_at DESC 
LIMIT 20;
"
```

## 🚨 Критическая проверка

**ВАЖНО**: Проверка MIN_TOTAL_POSITION_USD должна происходить **ДО** отправки алерта.

Если в логах вы видите:
- `Step 10/10: Checking minimum total position size: $1511.00 >= $2000.00`
- Но НЕТ строки `BLOCKED: Insufficient total position size`

То значит проверка не срабатывает или обходится где-то.

## 💡 Дополнительная диагностика

Создайте скрипт для проверки:

```python
# check_recent_alerts.py
import sqlite3
from datetime import datetime, timedelta

db = sqlite3.connect('polymarket_notifier.db')
cursor = db.cursor()

# Найти алерты за последний час с total_usd < 2000
one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()

cursor.execute("""
    SELECT condition_id, outcome_index, side, total_usd, first_total_usd, sent_at
    FROM alerts_sent
    WHERE sent_at >= ? AND total_usd < 2000
    ORDER BY sent_at DESC
""", (one_hour_ago,))

alerts = cursor.fetchall()
print(f"Найдено {len(alerts)} алертов с total_usd < 2000 за последний час:")
for alert in alerts:
    print(f"  {alert[3]:.2f} USDC - {alert[5]}")
```

## 🔄 Исправление (если проблема подтвердится)

Если проверка не работает, нужно убедиться что:

1. **Переменная установлена и загружена**:
   ```bash
   # На сервере
   grep MIN_TOTAL_POSITION_USD /opt/polymarket-bot/.env
   sudo systemctl restart polymarket-bot
   sudo journalctl -u polymarket-bot -n 50 | grep "MIN_TOTAL_POSITION_USD"
   ```

2. **Проверка выполняется**:
   - В логах должны быть строки `Step 10/10: Checking minimum total position size`
   - Для сигналов < $2000 должна быть строка `BLOCKED: Insufficient total position size`

3. **Нет обхода проверки**:
   - Проверка происходит в STEP 10, ДО STEP 11 (repeat alert)
   - Это правильно

## 📊 Ожидаемое поведение

После исправления, сигналы с total_usd < $2000 должны блокироваться:

```
[CONSENSUS] Step 10/10: Checking minimum total position size: $1511.00 >= $2000.00
[CONSENSUS] ⏭️  BLOCKED: Insufficient total position size - $1511.00 < $2000.00 condition=... outcome=... side=... wallets=3
```

