# 📊 Список API для получения цен маркетов Polymarket

## 🎯 Основные источники цен (в порядке приоритета)

### 1. **Polymarket CLOB API** (Primary)
- **Endpoint**: `https://clob.polymarket.com/price`
- **Метод**: `GET`
- **Аутентификация**: Требуется (X-API-KEY, X-API-SECRET, X-API-PASSPHRASE)
- **Параметры**: 
  - `token_id` (обязательный)
  - `side` (BUY/SELL, по умолчанию BUY)
- **Файл**: `price_fetcher.py` → `get_price_from_polymarket_clob()`
- **Использование**: Основной источник актуальных цен
- **Fallback**: Нет (первый в цепочке)

---

### 2. **Gamma API** (Fallback #1)
- **Endpoint**: `https://gamma-api.polymarket.com/slug/{slug}` или `/events`
- **Метод**: `GET`
- **Аутентификация**: Не требуется (публичный API)
- **Параметры**: 
  - `slug` (для `/slug/{slug}` endpoint) - опционально, ускоряет запрос
  - `conditionId` (для `/events` endpoint) - поиск события по condition_id
- **Файл**: `price_fetcher.py` → `_get_price_from_gamma()`, `gamma_client.py`
- **Использование**: Публичный источник цен из поля `outcomePrices`
- **Данные**: `outcomePrices[0]` = Yes (outcome_index=0), `outcomePrices[1]` = No (outcome_index=1)
- **Ограничение**: Возможно, кэшированный фронтовый источник (может немного отставать от orderbook)
- **Fallback**: После CLOB API, перед trades/HashiDive/FinFeed

---

### 3. **HashiDive API** (Fallback #2)
- **Endpoint**: `https://hashdive.com/api/get_last_price`
- **Метод**: `GET`
- **Аутентификация**: Требуется (x-api-key в заголовках)
- **Параметры**: 
  - `asset_id` (token_id в формате `condition_id:outcome_index`)
- **Файл**: `price_fetcher.py` → `get_price_from_hashdive()`
- **Использование**: Fallback когда CLOB API недоступен
- **Legacy метод**: Также используется через `hashdive_client.py` в `polymarket_notifier.py` и `notify.py`

---

### 4. **Polymarket Data API - История сделок** (Fallback #3)
- **Endpoint**: `https://data-api.polymarket.com/trades`
- **Метод**: `GET`
- **Аутентификация**: Не требуется (публичный API)
- **Параметры**: 
  - `token_id` (обязательный)
  - `market` / `condition_id` (опционально, для фильтрации)
  - `limit` (количество сделок, по умолчанию 10)
- **Файл**: `price_fetcher.py` → `get_price_from_trades_history()`
- **Использование**: Вычисляет среднюю цену из последних N сделок
- **Fallback**: Если первые два источника недоступны

---

### 5. **Polymarket CLOB API - История сделок** (Fallback #3.1)
- **Endpoint**: `https://clob.polymarket.com/data/trades`
- **Метод**: `GET`
- **Аутентификация**: Не требуется (публичный endpoint)
- **Параметры**: 
  - `token_id` (обязательный)
  - `limit` (количество сделок)
- **Файл**: `price_fetcher.py` → `get_price_from_trades_history()` (внутренний fallback)
- **Использование**: Альтернативный источник истории сделок, если Data API недоступен
- **Fallback**: Внутри функции `get_price_from_trades_history()`

---

### 6. **FinFeed API** (Fallback #4)
- **Endpoint**: `https://api.finfeedapi.com/v1/prediction-markets/last-price`
- **Метод**: `GET`
- **Аутентификация**: Требуется (Bearer token в заголовке Authorization)
- **Параметры**: 
  - `market` (token_id)
- **Файл**: `price_fetcher.py` → `get_price_from_finfeed()`
- **Использование**: Дополнительный источник, если все остальные недоступны
- **Конфигурация**: `FINFEED_API_KEY` в `.env`

---

## 🔄 Legacy методы (используются как fallback в старом коде)

### 6. **Polymarket CLOB API - /markets endpoint** (Legacy)
- **Endpoint**: `https://clob.polymarket.com/markets/{condition_id}`
- **Метод**: `GET`
- **Аутентификация**: Не требуется (публичный endpoint)
- **Параметры**: `condition_id` в URL
- **Файлы**: 
  - `polymarket_notifier.py` → `_get_current_price()` (Step 1)
  - `notify.py` → `_get_current_price()` (Step 1)
- **Использование**: Legacy метод, используется если `price_fetcher` модуль недоступен
- **Данные**: Извлекает цену из поля `tokens[outcome_index].price` или `market.price`

---

### 7. **Polymarket Data API - /markets endpoint** (Legacy Fallback)
- **Endpoint**: `https://data-api.polymarket.com/markets/{condition_id}`
- **Метод**: `GET`
- **Аутентификация**: Не требуется (публичный API)
- **Параметры**: `condition_id` в URL
- **Файлы**: 
  - `polymarket_notifier.py` → `_get_current_price()` (Step 4)
  - `notify.py` → `_get_current_price()` (Step 3)
- **Использование**: Последний fallback в legacy методах
- **Данные**: Извлекает цену из структуры ответа API

---

### 8. **HashiDive API - Legacy метод** (Legacy Fallback)
- **Endpoint**: Через `hashdive_client.py` → `get_last_price()`
- **Метод**: Внутренний метод HashiDive клиента
- **Аутентификация**: Требуется (HashiDive API key)
- **Файлы**: 
  - `polymarket_notifier.py` → `_get_current_price()` (Step 2)
  - `notify.py` → `_get_current_price()` (Step 2)
- **Использование**: Legacy fallback через HashiDive клиент
- **Формат**: Использует `asset_id` в формате `condition_id:outcome_index`

---

### 9. **Средняя цена из wallet_prices** (Fallback из данных)
- **Источник**: Не API, а данные из уже полученных сделок кошельков
- **Метод**: Вычисление среднего значения из словаря `wallet_prices`
- **Файлы**: 
  - `polymarket_notifier.py` → `_get_current_price()` (Step 3)
  - `notify.py` → `_get_current_price()` (Step 2.5, если доступно)
- **Использование**: Используется если API недоступны, но есть данные из сделок кошельков
- **Логика**: `sum(wallet_prices.values()) / len(wallet_prices)` если `wallet_prices` не пустой

---

## 📋 Порядок вызова (приоритет)

### Новый код (через `price_fetcher.py`):
1. ✅ **Polymarket CLOB API /price** (с авторизацией)
2. ✅ **Gamma API** (`gamma-api.polymarket.com/slug/{slug}` или `/events`)
3. ✅ **История сделок** (среднее из последних N сделок):
   - 3.1. `data-api.polymarket.com/trades`
   - 3.2. `clob.polymarket.com/data/trades` (fallback)
4. ✅ **HashiDive API** (`hashdive.com/api/get_last_price`)
5. ✅ **FinFeed API** (`api.finfeedapi.com`)
6. ✅ **Средняя цена из wallet_prices** (если предоставлена)

### Legacy код (если `price_fetcher` недоступен):
1. ✅ **Polymarket CLOB API /markets** (`clob.polymarket.com/markets/{condition_id}`)
2. ✅ **HashiDive API** (через `hashdive_client.py`)
3. ✅ **Средняя цена из wallet_prices** (если доступно)
4. ✅ **Polymarket Data API /markets** (`data-api.polymarket.com/markets/{condition_id}`)

---

## 🔑 Требуемые API ключи

Для работы всех источников нужны следующие ключи в `.env`:

```bash
# Polymarket CLOB API (обязательно для основного источника)
PM_API_KEY=your_key
PM_API_SECRET=your_secret
PM_API_PASSPHRASE=your_passphrase

# HashiDive API (для fallback)
HASHDIVE_API_KEY=your_key
# или
HASHIDIVE_API_KEY=your_key

# FinFeed API (опционально, для дополнительного fallback)
FINFEED_API_KEY=your_key
```

---

## 📁 Файлы, использующие API цен

1. **`price_fetcher.py`** - Основной модуль с многоуровневым fallback
2. **`polymarket_notifier.py`** - Использует `price_fetcher` + legacy методы
3. **`notify.py`** - Использует `price_fetcher` + legacy методы для Telegram уведомлений
4. **`hashdive_client.py`** - Клиент для HashiDive API (legacy)

---

## 🎯 Итоговая статистика

**Всего API источников**: 10
- **Основных (новый код)**: 5
- **Legacy методов**: 4
- **Вспомогательных (не API)**: 1 (средняя из wallet_prices)

**Публичные API** (не требуют авторизации): 4
- `gamma-api.polymarket.com/slug/{slug}` или `/events`
- `data-api.polymarket.com/trades`
- `clob.polymarket.com/data/trades`
- `clob.polymarket.com/markets/{condition_id}`
- `data-api.polymarket.com/markets/{condition_id}`

**Приватные API** (требуют авторизации): 3
- `clob.polymarket.com/price` (PM_API_KEY)
- `hashdive.com/api/get_last_price` (HASHDIVE_API_KEY)
- `api.finfeedapi.com` (FINFEED_API_KEY)

---

## 📝 Примечания

- Все API используют fail-open логику: если один источник недоступен, система автоматически переключается на следующий
- Таймаут запросов: 5 секунд (настраивается через `REQUEST_TIMEOUT` в `price_fetcher.py`)
- Retry механизм: до 2 попыток для каждого источника
- Логирование: все попытки и результаты логируются с уровнем DEBUG/INFO

