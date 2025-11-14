# SQL-запросы для анализа raw_collected_wallets

Эта таблица содержит все "сырые" адреса кошельков, собранные из разных источников, до фильтрации.

## Структура таблицы

```sql
CREATE TABLE raw_collected_wallets(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT NOT NULL,
    source TEXT NOT NULL,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Источники (source):**
- `polymarket_analytics` - кошельки с polymarketanalytics.com
- `leaderboards_html` - кошельки с HTML-страниц leaderboards (weekly + monthly)
- `polymarket_api` - кошельки с Polymarket API scraper

## Примеры SQL-запросов

### 1. Сколько уникальных адресов дал каждый источник за сегодня

```sql
SELECT 
    source,
    COUNT(DISTINCT address) as unique_addresses
FROM raw_collected_wallets
WHERE date(collected_at) = DATE('now')
GROUP BY source
ORDER BY unique_addresses DESC;
```

### 2. Сколько всего уникальных адресов собрали за сегодня (по всем источникам)

```sql
SELECT COUNT(DISTINCT address) as total_unique_addresses
FROM raw_collected_wallets
WHERE date(collected_at) = DATE('now');
```

### 3. Статистика по источникам за последние 7 дней

```sql
SELECT 
    date(collected_at) as collection_date,
    source,
    COUNT(DISTINCT address) as unique_addresses
FROM raw_collected_wallets
WHERE date(collected_at) >= DATE('now', '-7 days')
GROUP BY date(collected_at), source
ORDER BY collection_date DESC, source;
```

### 4. Общая статистика по источникам за последние 7 дней

```sql
SELECT 
    source,
    COUNT(DISTINCT address) as unique_addresses,
    COUNT(*) as total_records
FROM raw_collected_wallets
WHERE date(collected_at) >= DATE('now', '-7 days')
GROUP BY source
ORDER BY unique_addresses DESC;
```

### 5. Сколько раз один и тот же адрес был собран из разных источников за сегодня

```sql
SELECT 
    address,
    COUNT(DISTINCT source) as source_count,
    GROUP_CONCAT(DISTINCT source) as sources
FROM raw_collected_wallets
WHERE date(collected_at) = DATE('now')
GROUP BY address
HAVING source_count > 1
ORDER BY source_count DESC;
```

### 6. Топ-10 адресов, которые чаще всего встречаются в разных источниках

```sql
SELECT 
    address,
    COUNT(DISTINCT source) as source_count,
    COUNT(*) as total_collections,
    GROUP_CONCAT(DISTINCT source) as sources
FROM raw_collected_wallets
GROUP BY address
HAVING source_count > 1
ORDER BY source_count DESC, total_collections DESC
LIMIT 10;
```

### 7. Статистика по дням (сколько уникальных адресов собрано каждый день)

```sql
SELECT 
    date(collected_at) as collection_date,
    COUNT(DISTINCT address) as unique_addresses,
    COUNT(*) as total_records
FROM raw_collected_wallets
GROUP BY date(collected_at)
ORDER BY collection_date DESC
LIMIT 30;
```

### 8. Сравнение эффективности источников (сколько уникальных адресов дает каждый источник)

```sql
SELECT 
    source,
    COUNT(DISTINCT address) as unique_addresses,
    COUNT(*) as total_records,
    ROUND(COUNT(DISTINCT address) * 100.0 / (SELECT COUNT(DISTINCT address) FROM raw_collected_wallets), 2) as percentage_of_total
FROM raw_collected_wallets
GROUP BY source
ORDER BY unique_addresses DESC;
```

### 9. Адреса, которые есть только в одном источнике (за сегодня)

```sql
-- Адреса только из polymarket_analytics
SELECT address, 'polymarket_analytics' as source
FROM raw_collected_wallets
WHERE date(collected_at) = DATE('now')
  AND source = 'polymarket_analytics'
  AND address NOT IN (
      SELECT address 
      FROM raw_collected_wallets 
      WHERE date(collected_at) = DATE('now') 
        AND source != 'polymarket_analytics'
  )
LIMIT 10;
```

### 10. Общая статистика за все время

```sql
SELECT 
    source,
    COUNT(DISTINCT address) as unique_addresses,
    COUNT(*) as total_records,
    MIN(collected_at) as first_collection,
    MAX(collected_at) as last_collection
FROM raw_collected_wallets
GROUP BY source
ORDER BY unique_addresses DESC;
```

## Использование

Эти запросы помогут понять:
- **Качество парсинга**: сколько адресов реально собирается из каждого источника
- **Эффективность источников**: какой источник дает больше уникальных адресов
- **Дубликаты**: сколько адресов встречается в нескольких источниках
- **Динамику**: как меняется количество собранных адресов со временем

## Примечания

- Таблица `raw_collected_wallets` содержит **все** собранные адреса, включая дубликаты
- Для получения уникальных адресов используйте `COUNT(DISTINCT address)`
- Поле `collected_at` хранится в формате ISO (TEXT), используйте `date(collected_at)` для фильтрации по дням
- Индексы на `address`, `source` и `collected_at` ускоряют запросы

