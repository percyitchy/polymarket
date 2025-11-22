# Анализ логирования и проблемных slug

## Вопрос 1: Видно ли новое логирование в логах?

### Текущая ситуация:

**Да, но частично.** В логах видно только `logger.info()` выводы, но не `logger.debug()` выводы.

### Что видно в логах (из примера FIFA Brazil-Tunisia):

```
[SPORTS_DETECT] event_id=None, slug=None, market_slug=fif-bra-tun-2025-11-18-tun, is_sports=True, category=None, tags=None
```

Это вывод из строки 1982 в `notify.py`:
```python
logger.info(f"[SPORTS_DETECT] event_id={event_id}, slug={event_slug}, market_slug={market_slug}, is_sports={is_sports}, category={category}, tags={tags}, reason={detection_reason}")
```

### Что НЕ видно (потому что это `logger.debug()`):

Детальное логирование из `gamma_client.py` (строки 237-263):
- `[GAMMA] [DEBUG] Event structure:`
- `[GAMMA] [DEBUG]   - Event keys: [...]`
- `[GAMMA] [DEBUG]   - Event category: ...`
- `[GAMMA] [DEBUG]   - Event tags: ...`
- `[GAMMA] [DEBUG]   - URL-related fields in market: {...}`

Детальное логирование из `notify.py` (строки 1904-1910):
- `[SPORTS_DETECT]   - event_id: ...`
- `[SPORTS_DETECT]   - category: ...`
- `[SPORTS_DETECT]   - groupType: ...`
- `[SPORTS_DETECT]   - tags: ...`

### Почему не видно:

Уровень логирования на сервере, вероятно, установлен на `INFO`, а не `DEBUG`. Поэтому `logger.debug()` выводы не попадают в логи.

### Решение:

Чтобы видеть детальное логирование, нужно:
1. Изменить уровень логирования на `DEBUG` в `.env` или конфигурации
2. Или изменить `logger.debug()` на `logger.info()` для критических полей

## Вопрос 2: Проблема со slug (Solomon example)

### Что искать:

Нужно проверить логи на наличие slug с числами или неправильными форматами, например:
- `solomon-123456` (с числами)
- `solomon-islands-2025-11-18-123` (с лишними числами)
- Другие malformed slug

### Команды для проверки:

```bash
# Поиск проблемных slug в недавних логах
sudo journalctl -u polymarket-bot -n 5000 | grep -E 'SPORTS_DETECT.*market_slug|URL.*Final market URL' | grep -E '[0-9]{6,}|-[0-9]{4,}-[0-9]'

# Поиск slug с числами в конце
sudo journalctl -u polymarket-bot -n 5000 | grep 'market_slug=' | grep -E '[a-z]+-[0-9]{6,}'

# Поиск всех slug для анализа
sudo journalctl -u polymarket-bot -n 5000 | grep 'market_slug=' | tail -50
```

### Пример правильного slug:
```
market_slug=fif-bra-tun-2025-11-18-tun  ✅ (дата в формате YYYY-MM-DD)
```

### Пример проблемного slug:
```
market_slug=solomon-123456789  ❌ (числа без даты)
market_slug=solomon-islands-2025-11-18-123456  ❌ (лишние числа)
```

## Рекомендации

### 1. Для видимости детального логирования:

Изменить уровень логирования на DEBUG в `.env`:
```env
TASKMASTER_LOG_LEVEL=DEBUG
```

Или изменить критичные `logger.debug()` на `logger.info()` в коде.

### 2. Для проверки проблемных slug:

Выполнить команды выше на сервере и проанализировать результаты.


