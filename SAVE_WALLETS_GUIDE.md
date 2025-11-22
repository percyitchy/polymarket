# Руководство по сохранению кошельков с рынков

## Проблема

Адреса кошельков из сигналов должны сохраняться в базе данных, но иногда их сложно найти. Это может происходить по следующим причинам:
- Тестовые сигналы не сохраняются в БД
- Данные были очищены
- Адреса находятся в другом формате

## Решение

Созданы скрипты для поиска и сохранения всех кошельков с конкретного рынка по `condition_id`.

## Скрипты

### 1. `save_wallets_from_market.py` - Сохранение всех кошельков

**Использование:**
```bash
python3 save_wallets_from_market.py <condition_id>
```

**Что делает:**
- Получает информацию о рынке через CLOB API
- Загружает все транзакции через Data API и CLOB API (до 1000 транзакций)
- Извлекает все уникальные адреса кошельков из транзакций
- Сохраняет в файл: `wallets_<название_рынка>_<timestamp>.txt`
- Сохраняет в БД в таблицу `market_wallets`

**Пример:**
```bash
python3 save_wallets_from_market.py 0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
```

**Результат:**
- Файл с адресами кошельков
- Запись в таблице `market_wallets` в БД

### 2. `find_wallets_by_condition_id.py` - Поиск по паттернам

**Использование:**
```bash
python3 find_wallets_by_condition_id.py <condition_id>
python3 find_wallets_by_condition_id.py --search "Warriors Pelicans"
```

**Что делает:**
- Получает транзакции с рынка
- Ищет адреса по паттернам из сигнала:
  - `0x4e7...823`
  - `0x97e...a30`
  - `0xdb2...56e`
- Показывает информацию о найденных кошельках из БД

### 3. `check_alert_wallets.py` - Проверка сохранения

**Использование:**
```bash
python3 check_alert_wallets.py
python3 check_alert_wallets.py <condition_id>
```

**Что делает:**
- Проверяет последние алерты на наличие сохраненных адресов
- Показывает статистику сохранения
- Выявляет проблемы (пустые wallets_csv, несоответствия)

## Как найти condition_id

### Вариант 1: Из URL Polymarket
1. Откройте рынок на polymarket.com
2. URL будет вида: `https://polymarket.com/market/warriors-pelicans`
3. `condition_id` можно найти в исходном коде страницы или через DevTools

### Вариант 2: Из базы данных
```bash
python3 -c "
import sqlite3
from datetime import datetime, timezone, timedelta

db = sqlite3.connect('polymarket_notifier.db')
cursor = db.cursor()
week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

cursor.execute('''
    SELECT condition_id, sent_at FROM alerts_sent
    WHERE sent_at >= ?
    ORDER BY sent_at DESC
    LIMIT 20
''', (week_ago,))

for condition_id, sent_at in cursor.fetchall():
    print(f'{sent_at}: {condition_id}')
"
```

### Вариант 3: Через поиск по названию
```bash
python3 find_wallets_by_condition_id.py --search "Warriors Pelicans"
```

## Структура таблицы market_wallets

После использования `save_wallets_from_market.py` создается таблица:

```sql
CREATE TABLE IF NOT EXISTS market_wallets (
    condition_id TEXT,
    wallet_address TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    trade_count INTEGER DEFAULT 1,
    PRIMARY KEY (condition_id, wallet_address)
)
```

## Примеры использования

### Сохранение кошельков с рынка Warriors vs Pelicans

```bash
# 1. Найти condition_id
python3 find_wallets_by_condition_id.py --search "Warriors Pelicans"

# 2. Сохранить все кошельки
python3 save_wallets_from_market.py <найденный_condition_id>

# 3. Проверить сохранение
python3 check_alert_wallets.py <condition_id>
```

### Поиск конкретных адресов из сигнала

```bash
# Если знаете condition_id
python3 find_wallets_by_condition_id.py <condition_id>

# Или поиск по названию
python3 find_wallets_by_condition_id.py --search "Warriors Pelicans"
```

## Важные замечания

1. **Сохранение адресов в алертах**: Адреса автоматически сохраняются в `alerts_sent` через `wallets_csv` и `wallet_details_json`
2. **Очистка данных**: Старые данные могут быть очищены через `cleanup_old_data()`
3. **Тестовые сигналы**: Тестовые сигналы могут не сохраняться в БД
4. **Лимиты API**: API может ограничивать количество транзакций (обычно до 500-1000)

## Улучшения в будущем

- Автоматическое сохранение всех кошельков при отправке сигнала
- Логирование всех адресов в отдельную таблицу для отслеживания
- Улучшенная дедупликация адресов
- Интеграция с HashDive API для получения дополнительной информации

