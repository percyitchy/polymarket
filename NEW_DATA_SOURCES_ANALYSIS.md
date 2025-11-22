# 🔍 Анализ новых источников данных для Polymarket

## 📊 Обзор найденных источников

### 1. **CryptoHouse (ClickHouse Database)**
**URL**: https://crypto.clickhouse.com/

**Что это:**
- Публичная база данных ClickHouse с данными Polymarket
- Доступна через веб-интерфейс и SQL запросы
- Содержит исторические и актуальные данные о рынках

**Доступные таблицы (из скриншота):**
1. `assets` - активы/токены
2. `assets_mv` - материализованное представление активов
3. `block_times` - временные метки блоков
4. `global_open_interest` - глобальный открытый интерес
5. `market_open_interest` - открытый интерес по рынкам
6. `orders_filled` - исполненные ордера
7. `orders_filled_old` - архив исполненных ордеров
8. `orders_matched` - совпавшие ордера
9. `orders_matched_old` - архив совпавших ордеров
10. `slugs` - слаги рынков
11. `token_id_condition` - связь токенов и условий
12. `user_balances` - балансы пользователей
13. `user_positions` - позиции пользователей

**Преимущества:**
- ✅ Публичный доступ (не требует API ключей)
- ✅ Быстрые SQL запросы (ClickHouse оптимизирован для аналитики)
- ✅ Исторические данные
- ✅ Агрегированные данные (open interest, balances, positions)
- ✅ Данные о пользователях и их позициях

**Недостатки:**
- ⚠️ Может быть задержка данных (нужно проверить актуальность)
- ⚠️ Rate limiting (нужно проверить лимиты)
- ⚠️ Требует знания SQL
- ⚠️ Может быть нестабильным (публичный сервис)

**Потенциальное использование:**
1. **Получение цен** - из таблицы `orders_filled` или `orders_matched`
2. **Открытый интерес** - из `market_open_interest` или `global_open_interest`
3. **Позиции пользователей** - из `user_positions` для анализа крупных игроков
4. **Балансы** - из `user_balances` для фильтрации кошельков
5. **Исторические данные** - для анализа трендов

---

### 2. **Goldsky Subgraphs**
**URL**: 
- https://docs.goldsky.com/subgraphs/introduction
- https://docs.goldsky.com/introduction

**Что это:**
- Сервис для индексации данных блокчейна через subgraphs
- Полная совместимость с The Graph Protocol
- Альтернатива The Graph с улучшенной производительностью

**Возможности:**
- ✅ Индексация on-chain данных Polymarket
- ✅ GraphQL API для запросов
- ✅ Webhooks для real-time уведомлений
- ✅ Поддержка кастомных EVM цепей
- ✅ До 6x быстрее чем The Graph
- ✅ 99.9%+ uptime

**Преимущества:**
- ✅ Real-time данные (меньше задержка чем у публичных API)
- ✅ GraphQL интерфейс (удобно для запросов)
- ✅ Webhooks (push уведомления вместо polling)
- ✅ Высокая надежность
- ✅ Поддержка миграции с The Graph

**Недостатки:**
- ⚠️ Требует настройки subgraph (если нет готового)
- ⚠️ Может требовать API ключ (нужно проверить)
- ⚠️ Нужно разобраться с миграцией или созданием subgraph

**Потенциальное использование:**
1. **Real-time события** - через webhooks получать новые сделки
2. **GraphQL запросы** - для получения данных о рынках и сделках
3. **Исторические данные** - через GraphQL запросы с фильтрами
4. **Агрегированные данные** - через кастомные запросы

---

## 🎯 Интеграция в существующую систему

### Текущая архитектура источников данных

**Для цен:**
1. Polymarket CLOB API `/price` (primary)
2. Gamma API (fallback #1)
3. История сделок (fallback #2)
4. HashiDive API (fallback #3)
5. ClickHouse database (fallback #4) ← NEW
6. FinFeed API (fallback #5)
7. Средняя цена из wallet_prices (fallback #6)

**Для метаданных рынков:**
1. Closed positions API
2. Gamma API
3. CLOB API
4. Data API
5. GraphQL API (enhanced_market_data.py)
6. Web Scraping (enhanced_market_data.py)

### Рекомендуемая интеграция

#### **CryptoHouse (ClickHouse)**

**Приоритет:** Средний (fallback для цен и метаданных)

**Интеграция в `price_fetcher.py`:**
✅ **Completed**: Implemented `get_price_from_clickhouse()` function using `ClickHouseClient` class.

```python
from clickhouse_client import ClickHouseClient, RateLimitExceeded

def get_price_from_clickhouse(token_id: str) -> Optional[float]:
    """
    Get price from ClickHouse database
    
    Uses ClickHouseClient class with:
    - Rate limiting (60 queries/hour)
    - Retry logic with exponential backoff
    - Error handling for timeouts and connection errors
    - SQL injection prevention
    """
    client = ClickHouseClient()
    return client.get_latest_price(token_id)
```

**Rate limit**: 60 queries/hour (1 query per minute) - tracked in-memory with deque

**Интеграция для метаданных:**
- Использовать таблицу `slugs` для получения слагов
- Использовать `token_id_condition` для связи токенов и условий

**Порядок в fallback chain:**
- ✅ Integrated into `price_fetcher.py` as fallback #4 (after HashDive, before FinFeed)
- Fallback order:
  1. Polymarket CLOB API `/price` (primary)
  2. Gamma API (fallback #1)
  3. Trades history average (fallback #2)
  4. HashDive API (fallback #3)
  5. **ClickHouse** (fallback #4) ← NEW
  6. FinFeed API (fallback #5)
  7. Wallet prices average (fallback #6)

---

#### **Goldsky Subgraphs**

**Приоритет:** Высокий (для real-time событий и GraphQL запросов)

**Вариант 1: Использование готового Polymarket subgraph**
- Проверить есть ли готовый Polymarket subgraph на Goldsky
- Если есть - использовать его GraphQL endpoint
- Интегрировать в `enhanced_market_data.py` как альтернативу GraphQL

**Вариант 2: Создание кастомного subgraph**
- Создать subgraph для индексации событий Polymarket
- Настроить webhooks для real-time уведомлений о новых сделках
- Использовать для получения данных о крупных позициях

**Интеграция в `enhanced_market_data.py`:**
```python
GOLDSKY_GRAPHQL_ENDPOINT = "https://api.goldsky.com/api/public/project/<project-id>/subgraph/<subgraph-name>/<version>/graphql"

def get_market_data_from_goldsky(condition_id: str) -> Optional[Dict[str, Any]]:
    """
    Get market data from Goldsky subgraph GraphQL API
    """
    try:
        query = """
        query GetMarket($conditionId: String!) {
            market(id: $conditionId) {
                id
                slug
                question
                endDate
                active
                ...
            }
        }
        """
        
        variables = {"conditionId": condition_id}
        
        response = requests.post(
            GOLDSKY_GRAPHQL_ENDPOINT,
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return parse_goldsky_response(data)
            
    except Exception as e:
        logger.debug(f"[Goldsky] Error getting market data: {e}")
        return None
```

**Webhooks интеграция:**
- Создать endpoint для приема webhooks от Goldsky
- Использовать для real-time уведомлений о новых крупных сделках
- Может заменить или дополнить polling механизм

---

## 📋 План действий

### Фаза 1: Исследование и тестирование

1. **CryptoHouse:**
   - [x] Проверить доступность и формат API
   - [x] Протестировать SQL запросы через веб-интерфейс
   - [x] Проверить актуальность данных (задержка)
   - [x] Проверить rate limits
   - [x] Создать тестовый скрипт для получения цен
   - ✅ **Completed**: ClickHouse client implemented in `clickhouse_client.py`

2. **Goldsky:**
   - [ ] Проверить есть ли готовый Polymarket subgraph
   - [ ] Изучить документацию по миграции с The Graph
   - [ ] Протестировать GraphQL запросы
   - [ ] Проверить требования к API ключам
   - [ ] Изучить возможности webhooks

### Фаза 2: Интеграция

1. **CryptoHouse:**
   - [x] Создать модуль `clickhouse_client.py`
   - [x] Интегрировать в `price_fetcher.py` как fallback
   - [x] Добавить поддержку получения метаданных
   - [ ] Добавить кэширование запросов (опционально, для будущей оптимизации)
   - ✅ **Completed**: ClickHouse integrated into `price_fetcher.py` as fallback #4 (after HashDive, before FinFeed)
   - ✅ **Rate limit**: 60 queries/hour (1 query per minute) - implemented with in-memory tracking

2. **Goldsky:**
   - [ ] Настроить subgraph (или использовать готовый)
   - [ ] Интегрировать GraphQL в `enhanced_market_data.py`
   - [ ] Опционально: настроить webhooks для real-time событий
   - [ ] Добавить fallback в цепочку источников

### Фаза 3: Оптимизация

1. Мониторинг эффективности новых источников
2. Оптимизация запросов (batch, кэширование)
3. Обработка ошибок и retry логика
4. Документация и тесты

---

## 🔧 Технические детали

### ClickHouse HTTP Interface

ClickHouse предоставляет HTTP интерфейс для SQL запросов:

```bash
# Пример запроса через curl
curl "https://crypto.clickhouse.com/?query=SELECT%20*%20FROM%20orders_filled%20LIMIT%2010"
```

**Формат запроса:**
- GET или POST запрос
- SQL в параметре `query` или в теле запроса
- Результат в формате JSON, CSV или других форматах

**Примеры полезных запросов:**

```sql
-- Получить последнюю цену для токена
SELECT price, timestamp
FROM orders_filled
WHERE token_id = '0x123...:0'
ORDER BY timestamp DESC
LIMIT 1

-- Получить открытый интерес для рынка
SELECT SUM(amount) as open_interest
FROM market_open_interest
WHERE condition_id = '0x123...'

-- Получить позиции пользователя
SELECT condition_id, outcome_index, amount
FROM user_positions
WHERE user_address = '0xabc...'
```

### Goldsky Subgraph

**Миграция с The Graph:**
```bash
# Установка CLI
curl https://goldsky.com | sh

# Логин
goldsky login

# Миграция существующего subgraph
goldsky subgraph deploy <name>/<version> --from-url <thegraph-query-url>
```

**Создание нового subgraph:**
- Использует тот же формат что и The Graph
- Поддержка TypeScript для обработки событий
- GraphQL schema для определения данных

---

## 📊 Ожидаемые преимущества

### CryptoHouse:
- ✅ Дополнительный источник цен (fallback)
- ✅ Исторические данные для анализа
- ✅ Данные о позициях пользователей
- ✅ Открытый интерес по рынкам

### Goldsky:
- ✅ Real-time данные (меньше задержка)
- ✅ Webhooks (push вместо polling)
- ✅ Высокая надежность (99.9%+)
- ✅ GraphQL интерфейс (удобные запросы)

---

## ⚠️ Риски и ограничения

### CryptoHouse:
- ⚠️ Публичный сервис (может быть нестабильным)
- ⚠️ Возможны rate limits
- ⚠️ Задержка данных (нужно проверить)
- ⚠️ Может измениться формат API

### Goldsky:
- ⚠️ Требует настройки (если нет готового subgraph)
- ⚠️ Может требовать платную подписку
- ⚠️ Нужно время на миграцию/настройку
- ⚠️ Зависимость от внешнего сервиса

---

## 🚀 Быстрый старт

### Тестирование CryptoHouse:

```python
# test_clickhouse.py
import requests

def test_clickhouse():
    url = "https://crypto.clickhouse.com/"
    
    # Простой запрос
    query = "SELECT COUNT(*) FROM orders_filled"
    
    response = requests.get(url, params={"query": query})
    print(response.text)

if __name__ == "__main__":
    test_clickhouse()
```

### Тестирование Goldsky:

1. Зарегистрироваться на Goldsky
2. Создать API ключ
3. Проверить есть ли готовый Polymarket subgraph
4. Протестировать GraphQL запросы через их интерфейс

---

## 📝 Следующие шаги

### ClickHouse (✅ Completed)

1. ✅ **Completed**: ClickHouse client implemented in `clickhouse_client.py`
2. ✅ **Completed**: Integrated into `price_fetcher.py` as fallback #4
3. ✅ **Completed**: Rate limiting implemented (60 queries/hour)
4. ✅ **Completed**: Error handling and retry logic implemented
5. ✅ **Completed**: Test script updated to use new client

**Future Enhancements:**
- [ ] Add caching for frequently accessed data
- [ ] Monitor ClickHouse query performance
- [ ] Integrate other ClickHouse tables (open interest, positions, balances) into main workflow
- [ ] Add batch query support for multiple token_ids
- [ ] Optimize queries for better performance

### Goldsky (Pending)

1. **Немедленно:**
   - Протестировать доступность Goldsky через веб-интерфейс
   - Проверить есть ли готовый Polymarket subgraph
   - Изучить документацию Goldsky

2. **Краткосрочно (1-2 дня):**
   - Создать тестовые скрипты для Goldsky
   - Определить формат API и требования
   - Оценить эффективность

3. **Среднесрочно (неделя):**
   - Настроить Goldsky subgraph или использовать готовый
   - Интегрировать GraphQL в `enhanced_market_data.py`
   - Добавить мониторинг и логирование

4. **Долгосрочно:**
   - Оптимизировать запросы
   - Настроить webhooks (если применимо)
   - Документировать использование

---

## 🔧 ClickHouse Client Usage

### ClickHouseClient Class

The `ClickHouseClient` class provides a clean interface to the ClickHouse database at `crypto.clickhouse.com`.

**Initialization:**
```python
from clickhouse_client import ClickHouseClient

client = ClickHouseClient(
    base_url="https://crypto.clickhouse.com/",
    database="polymarket",
    timeout=10
)
```

**Available Methods:**

1. **`test_connection() -> bool`**
   - Tests connection to ClickHouse database
   - Returns True if successful, False otherwise
   - Example: `client.test_connection()`

2. **`get_latest_price(token_id: str) -> Optional[float]`**
   - Gets latest price for a token from `orders_filled` table
   - Returns price as float or None if no data found
   - Example: `price = client.get_latest_price("0x123...:0")`

3. **`get_market_open_interest(condition_id: str) -> Optional[Dict[str, Any]]`**
   - Gets market open interest for a condition
   - Returns dict with open interest data or None
   - Example: `oi = client.get_market_open_interest("0x123...")`

4. **`get_user_positions(user_address: str, condition_id: Optional[str] = None) -> List[Dict[str, Any]]`**
   - Gets user positions from `user_positions` table
   - Returns list of positions or empty list
   - Example: `positions = client.get_user_positions("0xabc...")`

5. **`get_user_balances(user_address: str) -> Optional[Dict[str, Any]]`**
   - Gets user balances from `user_balances` table
   - Returns dict with balance data or None
   - Example: `balances = client.get_user_balances("0xabc...")`

6. **`get_recent_trades(token_id: str, limit: int = 10) -> List[Dict[str, Any]]`**
   - Gets recent trades for a token
   - Returns list of trades or empty list
   - Example: `trades = client.get_recent_trades("0x123...:0", limit=5)`

7. **`get_rate_limit_status() -> Dict[str, Any]`**
   - Gets current rate limit status
   - Returns dict with queries_used, queries_remaining, reset_time
   - Example: `status = client.get_rate_limit_status()`

**Error Handling:**

- `ClickHouseError`: Base exception for ClickHouse errors
- `RateLimitExceeded`: Raised when rate limit is exceeded (includes wait_time)
- All methods return None/empty list on error (never raise exceptions to caller)

**Rate Limiting:**

- Rate limit: 60 queries per hour (1 query per minute)
- Tracked in-memory using `collections.deque` with maxlen=60
- Automatically removes timestamps older than 1 hour
- Raises `RateLimitExceeded` exception when limit exceeded
- `get_rate_limit_status()` provides current status

**SQL Injection Prevention:**

- Input sanitization: Escapes single quotes in user input
- Input validation: Validates token_id and condition_id formats
- Parameterized queries: Uses proper SQL escaping

**Response Format Handling:**

- Supports JSONEachRow (one JSON object per line) - most common
- Supports JSON (single JSON object with data array)
- Supports TabSeparated (tab-separated values) - fallback
- Handles empty responses gracefully

**Retry Logic:**

- Uses `tenacity` library for retry logic
- 3 attempts with exponential backoff
- Retries on timeout and connection errors
- Logs all retry attempts

**Logging:**

- Uses Python `logging` module
- Logs queries at DEBUG level
- Logs errors at WARNING level
- Logs rate limit status at INFO level
- Logs connection tests at INFO level

**Example Usage:**

```python
from clickhouse_client import ClickHouseClient, RateLimitExceeded

client = ClickHouseClient()

# Test connection
if client.test_connection():
    print("✅ Connected to ClickHouse")

# Check rate limit
status = client.get_rate_limit_status()
print(f"Queries remaining: {status['queries_remaining']}")

# Get latest price
try:
    price = client.get_latest_price("0x123...:0")
    if price:
        print(f"Latest price: {price}")
except RateLimitExceeded as e:
    print(f"Rate limit exceeded, wait {e.wait_time:.1f}s")
```

**Troubleshooting:**

1. **Connection errors**: Check if `crypto.clickhouse.com` is accessible
2. **Rate limit errors**: Wait for rate limit window to reset (1 hour)
3. **Empty results**: Verify token_id/condition_id format and data availability
4. **Timeout errors**: Increase timeout parameter (default: 10s)
5. **SQL errors**: Check query syntax and table names

---

## 📊 Rate Limiting Details

### How Rate Limiting Works

- **Limit**: 60 queries per hour (1 query per minute)
- **Tracking**: In-memory `deque` with maxlen=60 stores query timestamps
- **Window**: 1 hour (3600 seconds)
- **Behavior**: Before each query, removes timestamps older than 1 hour, then checks if limit exceeded

### What Happens When Rate Limit is Exceeded

- Raises `RateLimitExceeded` exception with `wait_time` (seconds until oldest query expires)
- Logs warning message with queries used and wait time
- In `price_fetcher.py`, rate limit errors are caught and logged, then continues to next fallback

### Managing Rate Limits

- **Monitor usage**: Use `get_rate_limit_status()` to check current usage
- **Batch queries**: Group multiple queries together when possible
- **Cache results**: Cache frequently accessed data to reduce queries
- **Respect limits**: Don't make rapid successive queries

### Rate Limit Status Example

```python
status = client.get_rate_limit_status()
# Returns:
# {
#     'queries_used': 45,
#     'queries_remaining': 15,
#     'queries_per_hour': 60,
#     'reset_time': '2025-01-15T10:00:00',
#     'reset_timestamp': 1705312800.0
# }
```

---

## 📚 Полезные ссылки

- **CryptoHouse**: https://crypto.clickhouse.com/
- **Goldsky Docs**: https://docs.goldsky.com/
- **Goldsky Subgraphs**: https://docs.goldsky.com/subgraphs/introduction
- **ClickHouse Docs**: https://clickhouse.com/docs/en/

---

*Документ создан: 2025-01-XX*
*Последнее обновление: 2025-01-15*
*ClickHouse integration completed: 2025-01-15*

