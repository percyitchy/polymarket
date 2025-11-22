# Проверка структуры события FIFA Brazil-Tunisia

## Задача
Проверить структуру события для рынка FIFA Brazil-Tunisia и найти:
1. Какие поля присутствуют в объекте события
2. Есть ли поле с путем `/sports/`
3. Какая категория и теги определены для этого спортивного события

## Способ 1: Проверка через логи бота

На сервере проверьте логи бота для этого события:

```bash
ssh -l ubuntu YOUR_SERVER_IP
cd /opt/polymarket-bot

# Поиск логов для события FIFA Brazil-Tunisia
sudo journalctl -u polymarket-bot -f | grep -i "fif\|bra\|tun\|sports"

# Или поиск по condition_id (если известен)
sudo journalctl -u polymarket-bot -n 1000 | grep -A 20 "SPORTS_DETECT\|GAMMA.*DEBUG"

# Поиск структуры события
sudo journalctl -u polymarket-bot -n 1000 | grep -A 30 "Event structure\|Event keys\|Event category"
```

## Способ 2: Использование скрипта check_event_structure.py

### Локально:
```bash
python3 check_event_structure.py fif-bra-tun-2025-11-18-tun
```

### На сервере:
```bash
ssh -l ubuntu YOUR_SERVER_IP
cd /opt/polymarket-bot
python3 check_event_structure.py fif-bra-tun-2025-11-18-tun
```

## Способ 3: Прямой запрос к Gamma API

```bash
# Получить событие по slug
curl "https://gamma-api.polymarket.com/events?featured=true&limit=200" | jq '.[] | select(.markets[].slug | contains("fif-bra-tun"))'

# Или найти через поиск
curl "https://gamma-api.polymarket.com/events" | jq '.[] | select(.slug | contains("fif-bra-tun"))'
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
```

### 2. Категорийные поля (из notify.py):
```
[SPORTS_DETECT]   - event_id: ...
[SPORTS_DETECT]   - category: ...
[SPORTS_DETECT]   - groupType: ...
[SPORTS_DETECT]   - type: ...
[SPORTS_DETECT]   - eventType: ...
[SPORTS_DETECT]   - group: ...
[SPORTS_DETECT]   - tags: ...
```

### 3. URL-related поля в market:
```
[GAMMA] [DEBUG]   - URL-related fields in market: {...}
```

### 4. Классификация:
```
[CONSENSUS] Category for condition=... → category=sports/Soccer
```

## Ожидаемые поля события

Согласно коду, событие должно содержать:

### Основные поля:
- `id` / `eventId` / `event_id`
- `slug` / `eventSlug`
- `title` / `question`
- `category` - **важно для определения sports**
- `groupType`
- `type` / `eventType`
- `group`
- `tags` - массив тегов

### Поля рынков:
- `markets` - массив рынков
  - `conditionId` / `condition_id`
  - `slug` / `marketSlug`
  - `question` / `title`
  - `url`, `path`, `pagePath`, `webUrl`, `sportsUrl`, `link`, `permalink`, `canonicalUrl` - **проверить на наличие /sports/**

## Проверка категории

Код проверяет категорию в следующем порядке:
1. `event.category == "sports"` → sports event
2. `event.groupType`, `event.type`, `event.eventType`, `event.group` содержат спортивные ключевые слова
3. `event.tags` содержат спортивные теги
4. `slug` содержит спортивные паттерны (fif, fifa, uef, uefa, nfl, nba, etc.)

## Пример вывода скрипта

Скрипт `check_event_structure.py` выводит:
- Все ключи события
- Значения категорийных полей
- Найденные пути `/sports/`
- Структуру рынков
- Результат классификации
- Полную JSON структуру события

## Если событие не найдено

Если событие не найдено через slug, попробуйте:
1. Использовать condition_id вместо slug
2. Проверить логи бота на момент отправки сигнала (время: 2025-11-18 22:14:37 UTC)
3. Использовать прямой запрос к Gamma API


