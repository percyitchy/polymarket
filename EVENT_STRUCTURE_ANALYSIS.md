# Анализ структуры события FIFA Brazil-Tunisia

## Найденные данные из логов

### Время сигнала
- **Время**: 2025-11-18 22:14:37 UTC
- **Condition ID**: `0x075f60e50fb5b8f65c...`
- **Market Slug**: `fif-bra-tun-2025-11-18-tun`
- **Total USD**: $775.50

### Данные из логов (строка 146):
```
[SPORTS_DETECT] event_id=None, slug=None, market_slug=fif-bra-tun-2025-11-18-tun, is_sports=True, category=None, tags=None
```

## Проблема

**Событие не было получено из Gamma API**, поэтому:
- ❌ `event_id=None` - событие не найдено в API
- ❌ `category=None` - категория не определена
- ❌ `tags=None` - теги не определены
- ✅ `is_sports=True` - определено только по паттерну slug (fif-bra-tun)

## Причина

Событие было определено как спортивное **только по паттерну slug**, а не по полям события из API, потому что:
1. Gamma API не вернул событие (возможно, рынок уже закрыт)
2. Функция `_get_event_slug_and_market_id()` не смогла получить event объект
3. Функция `_detect_sports_event()` получила `event=None`, поэтому использовала fallback проверку по slug

## Что нужно проверить

### 1. Попробовать получить событие по condition_id:

```bash
python3 check_event_structure.py --condition-id 0x075f60e50fb5b8f65c
```

### 2. Проверить логи Gamma API для этого condition_id:

```bash
sudo journalctl -u polymarket-bot --since '2025-11-18 22:14:00' --until '2025-11-18 22:15:00' | grep -A 20 'GAMMA.*0x075f60e50fb5b8f65c'
```

### 3. Проверить, почему событие не было получено:

В коде `notify.py`, функция `_get_event_slug_and_market_id()` должна получать событие через `get_event_by_condition_id()`, но, судя по логам, событие не было найдено.

## Ожидаемые поля (если событие было бы получено)

Если событие было бы получено из Gamma API, мы бы увидели:

```python
{
    "id": "...",
    "slug": "...",
    "category": "sports",  # или другое значение
    "groupType": "...",
    "type": "...",
    "eventType": "...",
    "group": "...",
    "tags": ["soccer", "fifa", ...],  # массив тегов
    "markets": [
        {
            "conditionId": "0x075f60e50fb5b8f65c...",
            "slug": "fif-bra-tun-2025-11-18-tun",
            "question": "Will Tunisia win on 2025-11-18?",
            "url": "...",  # возможно содержит /sports/
            "path": "...",  # возможно содержит /sports/
            ...
        }
    ]
}
```

## Вывод

**Для события FIFA Brazil-Tunisia:**
- ✅ Определено как спортивное по паттерну slug (`fif-bra-tun`)
- ❌ Категория из API не получена (`category=None`)
- ❌ Теги из API не получены (`tags=None`)
- ❌ Путь `/sports/` не проверен (нет данных о URL полях)

**Рекомендация:** Нужно улучшить логирование в `_get_event_slug_and_market_id()` и `_detect_sports_event()`, чтобы логировать попытки получения события и причины неудач.


