# Проверка структуры события FIFA Brazil-Tunisia в логах

## Проблема
Событие не найдено по slug через API (возможно, уже закрыто). Нужно проверить логи бота на сервере, где должна быть залогирована структура события при отправке сигнала.

## Способ 1: Проверка логов по времени сигнала

Время сигнала: **2025-11-18 22:14:37 UTC**

### На сервере выполните:

```bash
ssh -l ubuntu YOUR_SERVER_IP
cd /opt/polymarket-bot

# 1. Поиск структуры события в логах
sudo journalctl -u polymarket-bot --since '2025-11-18 22:00:00' --until '2025-11-18 23:00:00' | grep -A 30 'SPORTS_DETECT\|GAMMA.*DEBUG\|Event structure'

# 2. Поиск по ключевым словам FIFA/Brazil/Tunisia
sudo journalctl -u polymarket-bot --since '2025-11-18 22:00:00' --until '2025-11-18 23:00:00' | grep -i -A 20 'fif\|bra\|tun\|sports'

# 3. Поиск категории для этого события
sudo journalctl -u polymarket-bot --since '2025-11-18 22:00:00' --until '2025-11-18 23:00:00' | grep -A 10 'Category for condition'

# 4. Поиск URL-related полей
sudo journalctl -u polymarket-bot --since '2025-11-18 22:00:00' --until '2025-11-18 23:00:00' | grep -A 5 'URL-related fields'
```

## Способ 2: Проверка базы данных

Если сигнал был отправлен, condition_id есть в базе данных:

```bash
ssh -l ubuntu YOUR_SERVER_IP
cd /opt/polymarket-bot

python3 << 'EOF'
import sqlite3
from datetime import datetime, timezone, timedelta

db = sqlite3.connect('polymarket_notifier.db')
cursor = db.cursor()

# Ищем недавние алерты с ключевыми словами
week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

cursor.execute('''
    SELECT condition_id, sent_at, wallets_csv, total_usd
    FROM alerts_sent
    WHERE sent_at >= ?
    ORDER BY sent_at DESC
    LIMIT 100
''', (week_ago,))

print("Недавние сигналы:")
found = False
for condition_id, sent_at, wallets, total_usd in cursor.fetchall():
    # Проверяем по времени (около 22:14:37 UTC)
    if '2025-11-18 22:14' in sent_at or (total_usd and float(total_usd) < 1000):
        print(f"\n✅ Возможный сигнал:")
        print(f"   Condition ID: {condition_id}")
        print(f"   Время: {sent_at}")
        print(f"   Total USD: {total_usd}")
        print(f"   Wallets: {wallets[:100] if wallets else 'N/A'}...")
        found = True

if not found:
    print("Сигнал не найден в базе данных")

db.close()
EOF
```

Если найден condition_id, используйте его для проверки структуры:

```bash
python3 check_event_structure.py --condition-id <найденный_condition_id>
```

## Способ 3: Поиск в последних логах

```bash
# Поиск в последних 5000 строк логов
sudo journalctl -u polymarket-bot -n 5000 | grep -i -E 'fif|bra|tun|sports' -A 20 | head -100

# Поиск структуры события
sudo journalctl -u polymarket-bot -n 5000 | grep -A 30 'SPORTS_DETECT\|GAMMA.*DEBUG\|Event structure' | head -200
```

## Что искать в логах

### 1. Структура события (из gamma_client.py):
```
[GAMMA] [DEBUG] Event structure:
[GAMMA] [DEBUG]   - Event keys: [...]
[GAMMA] [DEBUG]   - Event category: ...
[GAMMA] [DEBUG]   - Event type: ...
[GAMMA] [DEBUG]   - Event groupType: ...
[GAMMA] [DEBUG]   - Event tags: ...
[GAMMA] [DEBUG]   - Matching market keys: [...]
[GAMMA] [DEBUG]   - Matching market slug: ...
[GAMMA] [DEBUG]   - URL-related fields in market: {...}
```

### 2. Категорийные поля (из notify.py):
```
[SPORTS_DETECT] Analyzing event for sports detection:
[SPORTS_DETECT]   - event_slug: ...
[SPORTS_DETECT]   - market_slug: ...
[SPORTS_DETECT]   - event_id: ...
[SPORTS_DETECT]   - category: ...
[SPORTS_DETECT]   - groupType: ...
[SPORTS_DETECT]   - type: ...
[SPORTS_DETECT]   - eventType: ...
[SPORTS_DETECT]   - group: ...
[SPORTS_DETECT]   - tags: ...
```

### 3. Классификация:
```
[CONSENSUS] Category for condition=... → category=sports/Soccer
```

## Ожидаемые поля для проверки

1. **category** - должно быть "sports" или содержать спортивные ключевые слова
2. **tags** - массив тегов, может содержать спортивные теги
3. **groupType**, **type**, **eventType** - могут содержать категорию
4. **URL-related fields** в market - проверить наличие `/sports/` пути
5. **markets[].slug** - slug рынка
6. **markets[].conditionId** - condition_id рынка

## Если ничего не найдено

Если событие не найдено в логах, возможно:
1. Логи ротируются (проверьте старые логи)
2. Событие обрабатывалось до добавления детального логирования
3. Нужно проверить логи на момент отправки сигнала (22:14:37 UTC)

Попробуйте расширить временной диапазон:
```bash
sudo journalctl -u polymarket-bot --since '2025-11-18 21:00:00' --until '2025-11-18 23:00:00' | grep -A 30 'SPORTS_DETECT\|GAMMA.*DEBUG'
```


