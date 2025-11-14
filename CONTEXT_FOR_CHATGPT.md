# Контекст для ChatGPT - Проблема с зависанием мониторинга

## Проблема

Бот Polymarket Signal Bot не запускает мониторинг кошельков, потому что процесс зависает на этапе сбора кошельков из API `polymarketanalytics.com` из-за таймаутов.

### Симптомы:
- Бот запускается успешно
- Начинается сбор кошельков: `Starting wallet collection from leaderboards...`
- API запросы к `polymarketanalytics.com` падают с таймаутами: `Read timed out. (read timeout=25)`
- Мониторинг никогда не запускается (нет записи `Starting wallet monitoring loop...`)
- В результате сигналы не приходят, хотя бот работает

### Текущая конфигурация:
- `MIN_CONSENSUS=4` - требуется 4+ кошелька для сигнала
- `ALERT_WINDOW_MIN=15` - окно консенсуса 15 минут
- `MAX_WALLETS=9000` - отслеживается 8329 кошельков
- Таймаут сбора кошельков: 2 минуты (было 5 минут)

## Ключевые файлы для анализа

### 1. `polymarket_notifier.py` (ГЛАВНЫЙ ФАЙЛ)
**Строки 2543-2605** - метод `run()` где происходит запуск:
- Строка 2583: `await asyncio.wait_for(self.collect_wallets_from_leaderboards(), timeout=120.0)`
- Строка 2597-2600: Запуск мониторинга (не достигается из-за зависания сбора)
- Строка 2300-2510: Метод `monitor_wallets()` - основной цикл мониторинга

**Строки 664-808** - метод `collect_wallets_from_leaderboards()`:
- Вызывает сбор из разных источников
- Может зависать на API запросах

### 2. `fetch_polymarket_analytics_api.py`
**Проблемный файл** - здесь происходят таймауты:
- Функция `fetch_traders_from_api()` делает запросы к `polymarketanalytics.com`
- Таймаут запросов: 25 секунд
- При множественных таймаутах процесс зависает

### 3. `db.py`
- Методы работы с БД для отслеживания кошельков
- Метод `get_tracked_wallets()` - получение списка отслеживаемых кошельков

### 4. `env.example` или `.env`
- Конфигурация переменных окружения
- `POLL_INTERVAL_SEC=7`
- `MIN_CONSENSUS=4`
- `ALERT_WINDOW_MIN=15`
- `MAX_WALLETS=9000`

## Что нужно исправить

1. **Сбор кошельков не должен блокировать запуск мониторинга**
   - Мониторинг должен запускаться независимо от успеха сбора
   - Сбор кошельков может работать в фоне

2. **Обработка таймаутов API**
   - Нужна лучшая обработка таймаутов при сборе кошельков
   - Не должно зависать на одном источнике

3. **Приоритет мониторинга**
   - Мониторинг - критическая функция, должна запускаться всегда
   - Сбор кошельков - вспомогательная функция, может быть отложена

## Вопросы для ChatGPT

1. Почему `asyncio.wait_for()` с таймаутом не срабатывает и процесс зависает?
2. Как сделать сбор кошельков неблокирующим для мониторинга?
3. Как улучшить обработку таймаутов в `fetch_polymarket_analytics_api.py`?
4. Можно ли запустить мониторинг параллельно со сбором кошельков?

## Логи для справки

```
2025-11-13 09:47:19,199 - __main__ - INFO - Starting wallet collection from leaderboards...
2025-11-13 09:47:19,200 - __main__ - INFO - [COLLECTION] Starting wallet collection from all sources...
2025-11-13 09:47:19,200 - __main__ - INFO - [COLLECTION] Step 1: Collecting from polymarketanalytics.com...
2025-11-13 09:45:45,718 - fetch_polymarket_analytics_api - ERROR - Request error: HTTPSConnectionPool(host='polymarketanalytics.com', port=443): Read timed out. (read timeout=25)
```

**НЕТ записи:**
```
Starting wallet monitoring loop...
[MONITOR] Starting wallet monitoring...
```

