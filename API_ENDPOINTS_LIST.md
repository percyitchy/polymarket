# 🔗 Список всех API Endpoints системы Polymarket Notifier

## 📊 Получение цен маркетов (price_fetcher.py)

### 1. Polymarket CLOB API /price
**URL**: `https://clob.polymarket.com/price`  
**Метод**: `GET`  
**Аутентификация**: ✅ Требуется (X-API-KEY, X-API-SECRET, X-API-PASSPHRASE)  
**Параметры**: 
- `token_id` (обязательный)
- `side` (BUY/SELL, по умолчанию BUY)

**Пример запроса**:
```
GET https://clob.polymarket.com/price?token_id=0x123...:0&side=BUY
Headers:
  X-API-KEY: your_key
  X-API-SECRET: your_secret
  X-API-PASSPHRASE: your_passphrase
```

---

### 2. Gamma API - по slug
**URL**: `https://gamma-api.polymarket.com/slug/{slug}`  
**Альтернативный**: `https://gamma.polymarket.com/api/slug/{slug}`  
**Метод**: `GET`  
**Аутентификация**: ❌ Не требуется (публичный)  
**Параметры**: `slug` в URL

**Пример запроса**:
```
GET https://gamma-api.polymarket.com/slug/will-trump-win-2024-election
```

---

### 3. Gamma API - по condition_id
**URL**: `https://gamma-api.polymarket.com/events`  
**Альтернативный**: `https://gamma.polymarket.com/api/events`  
**Метод**: `GET`  
**Аутентификация**: ❌ Не требуется (публичный)  
**Параметры**: 
- `conditionId` (query parameter)

**Пример запроса**:
```
GET https://gamma-api.polymarket.com/events?conditionId=0x123...
```

---

### 4. HashiDive API
**URL**: `https://hashdive.com/api/get_last_price`  
**Метод**: `GET`  
**Аутентификация**: ✅ Требуется (x-api-key в заголовках)  
**Параметры**: 
- `asset_id` (token_id в формате `condition_id:outcome_index`)

**Пример запроса**:
```
GET https://hashdive.com/api/get_last_price?asset_id=0x123...:0
Headers:
  x-api-key: your_api_key
```

---

### 5. Polymarket Data API - История сделок
**URL**: `https://data-api.polymarket.com/trades`  
**Метод**: `GET`  
**Аутентификация**: ❌ Не требуется (публичный)  
**Параметры**: 
- `token_id` (обязательный)
- `market` / `condition_id` (опционально)
- `limit` (количество сделок, по умолчанию 10)

**Пример запроса**:
```
GET https://data-api.polymarket.com/trades?token_id=0x123...:0&limit=10&market=0x123...
```

---

### 6. Polymarket CLOB API - История сделок
**URL**: `https://clob.polymarket.com/data/trades`  
**Метод**: `GET`  
**Аутентификация**: ❌ Не требуется (публичный)  
**Параметры**: 
- `token_id` (обязательный)
- `limit` (количество сделок)

**Пример запроса**:
```
GET https://clob.polymarket.com/data/trades?token_id=0x123...:0&limit=10
```

---

### 7. FinFeed API
**URL**: `https://api.finfeedapi.com/v1/prediction-markets/last-price`  
**Метод**: `GET`  
**Аутентификация**: ✅ Требуется (Bearer token)  
**Параметры**: 
- `market` (token_id)

**Пример запроса**:
```
GET https://api.finfeedapi.com/v1/prediction-markets/last-price?market=0x123...:0
Headers:
  Authorization: Bearer your_api_key
```

---

## 🔄 Legacy методы (polymarket_notifier.py, notify.py)

### 8. Polymarket CLOB API - /markets endpoint
**URL**: `https://clob.polymarket.com/markets/{condition_id}`  
**Метод**: `GET`  
**Аутентификация**: ❌ Не требуется (публичный)  
**Параметры**: `condition_id` в URL

**Пример запроса**:
```
GET https://clob.polymarket.com/markets/0x23e6e6f8a327a41bad1282fdc34e846f52e73e390d44b004ac92a329766e2848
```

---

### 9. Polymarket Data API - /markets endpoint
**URL**: `https://data-api.polymarket.com/markets/{condition_id}`  
**Метод**: `GET`  
**Аутентификация**: ❌ Не требуется (публичный)  
**Параметры**: `condition_id` в URL

**Пример запроса**:
```
GET https://data-api.polymarket.com/markets/0x23e6e6f8a327a41bad1282fdc34e846f52e73e390d44b004ac92a329766e2848
```

---

### 10. Polymarket Data API - /condition endpoint
**URL**: `https://data-api.polymarket.com/condition/{condition_id}`  
**Метод**: `GET`  
**Аутентификация**: ❌ Не требуется (публичный)  
**Параметры**: `condition_id` в URL

**Пример запроса**:
```
GET https://data-api.polymarket.com/condition/0x23e6e6f8a327a41bad1282fdc34e846f52e73e390d44b004ac92a329766e2848
```

---

## 📈 Получение данных о сделках и кошельках

### 11. Polymarket Data API - /traded endpoint
**URL**: `https://data-api.polymarket.com/traded`  
**Метод**: `GET`  
**Аутентификация**: ❌ Не требуется (публичный)  
**Параметры**: 
- `user` (wallet address)

**Пример запроса**:
```
GET https://data-api.polymarket.com/traded?user=0x123...
```

---

### 12. Polymarket Data API - /closed-positions endpoint
**URL**: `https://data-api.polymarket.com/closed-positions`  
**Метод**: `GET`  
**Аутентификация**: ❌ Не требуется (публичный)  
**Параметры**: 
- `user` (wallet address)

**Пример запроса**:
```
GET https://data-api.polymarket.com/closed-positions?user=0x123...
```

---

## 🏆 Получение лидербордов

### 13. Polymarket Leaderboard - Today Profit
**URL**: `https://polymarket.com/leaderboard/overall/today/profit`  
**Метод**: `GET` (скрапинг HTML)  
**Аутентификация**: ❌ Не требуется  
**Использование**: Парсинг HTML для получения списка кошельков

---

### 14. Polymarket Leaderboard - Weekly Profit
**URL**: `https://polymarket.com/leaderboard/overall/weekly/profit`  
**Метод**: `GET` (скрапинг HTML)  
**Аутентификация**: ❌ Не требуется  
**Использование**: Парсинг HTML для получения списка кошельков

---

### 15. Polymarket Leaderboard - Monthly Profit
**URL**: `https://polymarket.com/leaderboard/overall/monthly/profit`  
**Метод**: `GET` (скрапинг HTML)  
**Аутентификация**: ❌ Не требуется  
**Использование**: Парсинг HTML для получения списка кошельков

---

### 16. Polymarket Leaderboard - All Volume
**URL**: `https://polymarket.com/leaderboard/overall/all/volume`  
**Метод**: `GET` (скрапинг HTML)  
**Аутентификация**: ❌ Не требуется  
**Использование**: Парсинг HTML для получения списка кошельков

---

## 🌐 HashiDive Trader Explorer

### 17. HashiDive Trader Explorer (скрапинг)
**URL**: `https://hashdive.com/Trader_explorer`  
**Метод**: `GET` (скрапинг HTML)  
**Аутентификация**: ❌ Не требуется  
**Использование**: Парсинг HTML для получения списка кошельков

**Пример с пагинацией**:
```
GET https://hashdive.com/Trader_explorer?page=1
GET https://hashdive.com/Trader_explorer?page=2
```

---

## 📱 Telegram Bot API

### 18. Telegram Bot API - Send Message
**URL**: `https://api.telegram.org/bot{bot_token}/sendMessage`  
**Метод**: `POST`  
**Аутентификация**: ✅ Требуется (bot_token в URL)  
**Параметры**: JSON body с `chat_id`, `text`, `parse_mode` и т.д.

**Пример запроса**:
```
POST https://api.telegram.org/bot123456:ABC-DEF/sendMessage
Content-Type: application/json

{
  "chat_id": 123456789,
  "text": "Alert message",
  "parse_mode": "Markdown"
}
```

---

## 🔍 Polymarket Frontend (для получения slug и метаданных)

### 19. Polymarket Event Page
**URL**: `https://polymarket.com/event/{slug}`  
**Метод**: `GET` (скрапинг HTML)  
**Аутентификация**: ❌ Не требуется  
**Использование**: Получение метаданных рынка по slug

**Пример**:
```
GET https://polymarket.com/event/will-trump-win-2024-election
```

---

### 20. Polymarket Search
**URL**: `https://polymarket.com/search?q={query}`  
**Метод**: `GET` (скрапинг HTML)  
**Аутентификация**: ❌ Не требуется  
**Использование**: Поиск рынка по названию или condition_id

**Пример**:
```
GET https://polymarket.com/search?q=trump%20election
GET https://polymarket.com/search?q=0x23e6e6f8a327a41bad1282fdc34e846f52e73e390d44b004ac92a329766e2848
```

---

## 🧪 Тестовые endpoints (test_random_market_prices.py)

### 21. Polymarket Data API - /events (тест)
**URL**: `https://data-api.polymarket.com/events`  
**Метод**: `GET`  
**Аутентификация**: ❌ Не требуется  
**Параметры**: 
- `limit` (количество событий)

**Пример запроса**:
```
GET https://data-api.polymarket.com/events?limit=20
```

---

### 22. Polymarket Data API - /markets (тест)
**URL**: `https://data-api.polymarket.com/markets`  
**Метод**: `GET`  
**Аутентификация**: ❌ Не требуется  
**Параметры**: 
- `limit` (количество рынков)
- `sort` (сортировка)
- `order` (порядок: desc/asc)

**Пример запроса**:
```
GET https://data-api.polymarket.com/markets?limit=10&sort=volume&order=desc
```

---

## 📋 Сводная таблица

| # | Endpoint | Метод | Аутентификация | Назначение | Файл |
|---|----------|-------|-----------------|------------|------|
| 1 | `clob.polymarket.com/price` | GET | ✅ API Keys | Получение цены | `price_fetcher.py` |
| 2 | `gamma-api.polymarket.com/slug/{slug}` | GET | ❌ Публичный | Получение цены (Gamma) | `gamma_client.py` |
| 3 | `gamma-api.polymarket.com/events` | GET | ❌ Публичный | Поиск события (Gamma) | `gamma_client.py` |
| 4 | `hashdive.com/api/get_last_price` | GET | ✅ API Key | Получение цены | `price_fetcher.py` |
| 5 | `data-api.polymarket.com/trades` | GET | ❌ Публичный | История сделок | `price_fetcher.py` |
| 6 | `clob.polymarket.com/data/trades` | GET | ❌ Публичный | История сделок (fallback) | `price_fetcher.py` |
| 7 | `api.finfeedapi.com/v1/prediction-markets/last-price` | GET | ✅ Bearer Token | Получение цены | `price_fetcher.py` |
| 8 | `clob.polymarket.com/markets/{condition_id}` | GET | ❌ Публичный | Legacy: получение цены | `polymarket_notifier.py`, `notify.py` |
| 9 | `data-api.polymarket.com/markets/{condition_id}` | GET | ❌ Публичный | Legacy: получение цены | `polymarket_notifier.py`, `notify.py` |
| 10 | `data-api.polymarket.com/condition/{condition_id}` | GET | ❌ Публичный | Получение метаданных | `notify.py` |
| 11 | `data-api.polymarket.com/traded` | GET | ❌ Публичный | Сделки кошелька | `wallet_analyzer.py` |
| 12 | `data-api.polymarket.com/closed-positions` | GET | ❌ Публичный | Закрытые позиции | `wallet_analyzer.py` |
| 13 | `polymarket.com/leaderboard/overall/today/profit` | GET | ❌ Публичный | Лидерборд (скрапинг) | `polymarket_notifier.py` |
| 14 | `polymarket.com/leaderboard/overall/weekly/profit` | GET | ❌ Публичный | Лидерборд (скрапинг) | `polymarket_notifier.py` |
| 15 | `polymarket.com/leaderboard/overall/monthly/profit` | GET | ❌ Публичный | Лидерборд (скрапинг) | `polymarket_notifier.py` |
| 16 | `polymarket.com/leaderboard/overall/all/volume` | GET | ❌ Публичный | Лидерборд (скрапинг) | `polymarket_notifier.py` |
| 17 | `hashdive.com/Trader_explorer` | GET | ❌ Публичный | Скрапинг кошельков | `fetch_hashdive_trader_explorer.py` |
| 18 | `api.telegram.org/bot{token}/sendMessage` | POST | ✅ Bot Token | Отправка уведомлений | `notify.py` |
| 19 | `polymarket.com/event/{slug}` | GET | ❌ Публичный | Получение метаданных | `notify.py` |
| 20 | `polymarket.com/search?q={query}` | GET | ❌ Публичный | Поиск рынка | `notify.py` |
| 21 | `data-api.polymarket.com/events` | GET | ❌ Публичный | Тест: список событий | `test_random_market_prices.py` |
| 22 | `data-api.polymarket.com/markets` | GET | ❌ Публичный | Тест: список рынков | `test_random_market_prices.py` |

---

## 🔑 Требуемые API ключи

### Polymarket CLOB API
- `PM_API_KEY`
- `PM_API_SECRET`
- `PM_API_PASSPHRASE`
- Получить: https://polymarket.com/settings/api-keys

### HashiDive API
- `HASHDIVE_API_KEY` или `HASHIDIVE_API_KEY`
- Получить: https://hashdive.com

### FinFeed API
- `FINFEED_API_KEY`
- Получить: https://api.finfeedapi.com

### Telegram Bot API
- `TELEGRAM_BOT_TOKEN`
- Получить: @BotFather в Telegram

### Gamma API
- ❌ Не требуется (публичный API)
- Опционально: `GAMMA_BASE_URL` (по умолчанию: `https://gamma-api.polymarket.com`)

---

## 📊 Статистика

**Всего endpoints**: 22
- **API для получения цен**: 7
- **Legacy методы**: 3
- **API для данных кошельков**: 2
- **Лидерборды (скрапинг)**: 4
- **Telegram API**: 1
- **Frontend (скрапинг)**: 2
- **Тестовые**: 2
- **HashiDive скрапинг**: 1

**Публичные (без авторизации)**: 19
**Приватные (требуют авторизации)**: 3

---

## 🔄 Порядок приоритета для получения цен

1. `clob.polymarket.com/price` (требует API ключи)
2. `gamma-api.polymarket.com/slug/{slug}` или `/events` (публичный)
3. `data-api.polymarket.com/trades` → `clob.polymarket.com/data/trades` (публичный)
4. `hashdive.com/api/get_last_price` (требует API ключ)
5. `api.finfeedapi.com/v1/prediction-markets/last-price` (требует API ключ)
6. Средняя цена из `wallet_prices` (не API, вычисление)

---

## 📝 Примечания

- Все публичные endpoints доступны без авторизации
- Приватные endpoints требуют соответствующие API ключи в `.env`
- Таймаут запросов: 5 секунд (настраивается через `REQUEST_TIMEOUT`)
- Retry механизм: до 2 попыток для каждого источника
- Все запросы логируются с уровнем DEBUG/INFO

