# 🔑 Интеграция Builder API Key для Polymarket CLOB API

## 📋 Резюме изменений

Адаптирован код для работы с **Builder API Key** (одна строка UUID) вместо трёх ключей (KEY + SECRET + PASSPHRASE).

---

## 🔧 Изменённые файлы

### 1. `price_fetcher.py`

**Функция**: `get_price_from_polymarket_clob()`

**Изменения**:
- ✅ Теперь требует **только** `PM_API_KEY` (обязательный)
- ✅ `PM_API_SECRET` и `PM_API_PASSPHRASE` стали **опциональными**
- ✅ Поддержка двух форматов авторизации:
  1. **Builder API Key** (только `PM_API_KEY`) → заголовок `X-API-KEY`
  2. **Полная авторизация** (все три ключа) → для обратной совместимости
- ✅ Улучшенное логирование ошибок (401, 403, 5xx)
- ✅ Корректные сообщения при отсутствии ключа

**Логика определения формата**:
```python
use_builder_key = bool(api_key) and not (api_secret and api_passphrase)
use_full_auth = bool(api_key and api_secret and api_passphrase)
```

**Формат авторизации**:
- **Builder API Key**: `X-API-KEY: {api_key}`
- **Полная авторизация**: `X-API-KEY`, `X-API-SECRET`, `X-API-PASSPHRASE`

---

### 2. `test_random_market_prices.py`

**Новая функция**: `check_clob_api_key()`

**Функциональность**:
- ✅ Проверяет наличие `PM_API_KEY` в переменных окружения
- ✅ Выполняет тестовый запрос к CLOB API (`/markets/{condition_id}`)
- ✅ Определяет статус авторизации (OK / UNAUTHORIZED / ERROR)
- ✅ Не кидает исключения — только логирует результат

**Вызов**: Автоматически вызывается в начале `main()` перед тестированием рынков

**Примеры вывода**:
```
🔑 CLOB status: OK (authorized, response 200)
🔑 CLOB status: NOT CONFIGURED (PM_API_KEY is empty) — skipping CLOB tests
🔑 CLOB status: UNAUTHORIZED (HTTP 401) — check PM_API_KEY
🔑 CLOB status: ERROR (HTTP 500: Server error)
```

---

## 📝 Формат авторизации CLOB API

### Builder API Key (новый формат)

**Заголовки**:
```
X-API-KEY: {PM_API_KEY}
Content-Type: application/json
```

**Пример запроса**:
```python
headers = {
    "X-API-KEY": "your-builder-api-key-uuid",
    "Content-Type": "application/json"
}
response = requests.get("https://clob.polymarket.com/price", headers=headers, params={"token_id": "..."})
```

### Полная авторизация (legacy, для обратной совместимости)

**Заголовки**:
```
X-API-KEY: {PM_API_KEY}
X-API-SECRET: {PM_API_SECRET}
X-API-PASSPHRASE: {PM_API_PASSPHRASE}
Content-Type: application/json
```

---

## 🔄 Логика работы

### Проверка конфигурации

1. **Если `PM_API_KEY` отсутствует**:
   ```
   [PRICE_FETCH] [CLOB] API key not configured (PM_API_KEY missing) — skipping CLOB price step
   ```
   → Пропускает CLOB API, переходит к следующему источнику (Gamma API)

2. **Если есть только `PM_API_KEY`**:
   ```
   [PRICE_FETCH] [CLOB] Using Builder API Key format (PM_API_KEY only)
   ```
   → Использует простую авторизацию через `X-API-KEY`

3. **Если есть все три ключа**:
   ```
   [PRICE_FETCH] [CLOB] Using full authentication (PM_API_KEY + SECRET + PASSPHRASE)
   ```
   → Использует полную авторизацию (для обратной совместимости)

### Обработка ошибок

- **401 Unauthorized**: Логируется и переходит к следующему источнику
- **403 Forbidden**: Логируется и переходит к следующему источнику
- **5xx Server Error**: Логируется и переходит к следующему источнику
- **Timeout / Network Error**: Логируется и переходит к следующему источнику

**Все ошибки не прерывают выполнение** — система продолжает попытки через fallback источники (Gamma, trades, HashiDive, FinFeed, wallet_prices).

---

## ✅ Тестирование

### Локальный тест

```bash
# Без ключа
python3 test_random_market_prices.py --limit 2
# Вывод: 🔑 CLOB status: NOT CONFIGURED (PM_API_KEY is empty) — skipping CLOB tests

# С ключом (добавить PM_API_KEY в .env)
python3 test_random_market_prices.py --limit 2
# Вывод: 🔑 CLOB status: OK (authorized, response 200)
```

### Проверка в логах

После добавления `PM_API_KEY` в `.env`:

1. **При успешной авторизации**:
   ```
   [PRICE_FETCH] [CLOB] Using Builder API Key format (PM_API_KEY only)
   [PRICE_FETCH] [1/6] Requesting Polymarket CLOB API /price: token_id=...
   [PRICE_FETCH] [1/6] Response status: 200
   [PRICE_FETCH] ✅ Got price=0.512345 from Polymarket CLOB API
   ```

2. **При ошибке авторизации**:
   ```
   [PRICE_FETCH] [CLOB] Using Builder API Key format (PM_API_KEY only)
   [PRICE_FETCH] [1/6] Requesting Polymarket CLOB API /price: token_id=...
   [PRICE_FETCH] [1/6] Response status: 401
   [PRICE_FETCH] [CLOB] Unauthorized (401): Invalid API key
   [PRICE_FETCH] Step 2/6: Gamma API
   ```

---

## 📦 Конфигурация

### Переменные окружения

**Минимальная конфигурация** (Builder API Key):
```bash
PM_API_KEY=your-builder-api-key-uuid
```

**Полная конфигурация** (legacy, для обратной совместимости):
```bash
PM_API_KEY=your-api-key
PM_API_SECRET=your-secret
PM_API_PASSPHRASE=your-passphrase
```

### Где получить Builder API Key

1. Зайти на https://polymarket.com/settings/api-keys
2. Создать новый Builder API Key
3. Скопировать UUID ключа
4. Добавить в `.env`: `PM_API_KEY=your-uuid-key`

---

## 🎯 Итоговый формат авторизации

**Используется**: Простая авторизация через заголовок `X-API-KEY`

**Запрос**:
```http
GET https://clob.polymarket.com/price?token_id=0x123...:0&side=BUY
Headers:
  X-API-KEY: {PM_API_KEY}
  Content-Type: application/json
```

**Без HMAC-подписи, без таймстемпов** — только API ключ в заголовке.

---

## 📊 Статус

✅ **Готово к использованию**

- Код адаптирован под Builder API Key
- Авто-проверка ключа в тестах
- Обратная совместимость с полной авторизацией
- Улучшенное логирование
- Корректная обработка ошибок

**Следующий шаг**: Добавить `PM_API_KEY` в `.env` на сервере и перезапустить сервис.

