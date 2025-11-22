# Как найти condition_id для рынка

## Способ 1: Через скрипт поиска (самый простой)

Используйте созданный скрипт `find_condition_id.py`:

```bash
python3 find_condition_id.py "Warriors Pelicans"
```

Или с полным названием:
```bash
python3 find_condition_id.py "Warriors vs Pelicans"
```

Скрипт будет искать:
- В базе данных (alerts_sent, rolling_buys)
- Через CLOB API (активные рынки)
- С различными вариантами названия

## Способ 2: Из базы данных (если был сигнал)

Если по этому рынку уже был отправлен сигнал, condition_id есть в базе:

```bash
python3 -c "
import sqlite3
from datetime import datetime, timezone, timedelta
import requests

db = sqlite3.connect('polymarket_notifier.db')
cursor = db.cursor()

# Ищем недавние алерты
week_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
cursor.execute('''
    SELECT DISTINCT condition_id, sent_at
    FROM alerts_sent
    WHERE sent_at >= ?
    ORDER BY sent_at DESC
    LIMIT 50
''', (week_ago,))

print('Проверяю недавние алерты...')
for condition_id, sent_at in cursor.fetchall():
    try:
        url = f'https://clob.polymarket.com/markets/{condition_id}'
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            title = (data.get('question') or data.get('title') or '').lower()
            if 'warriors' in title or 'pelicans' in title:
                print(f'✅ Найден: {data.get(\"question\") or data.get(\"title\")}')
                print(f'   Condition ID: {condition_id}')
                print(f'   Дата алерта: {sent_at}')
                print()
    except:
        pass

db.close()
"
```

## Способ 3: Через Polymarket.com (вручную)

1. Откройте рынок на polymarket.com
2. Откройте DevTools (F12)
3. Перейдите на вкладку Network
4. Обновите страницу
5. Найдите запрос к API (например, к `clob.polymarket.com/markets/...`)
6. В ответе будет `conditionId` или `id`

Или:
1. Откройте исходный код страницы (Ctrl+U)
2. Найдите `conditionId` или `condition_id` в тексте
3. Скопируйте значение

## Способ 4: Из URL (если есть slug)

Если у вас есть slug рынка (например, `warriors-pelicans`), можно попробовать:

```bash
python3 -c "
import requests

slug = 'warriors-pelicans'  # Замените на ваш slug
url = f'https://clob.polymarket.com/markets/{slug}'

try:
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        data = response.json()
        condition_id = data.get('conditionId') or data.get('id')
        print(f'Condition ID: {condition_id}')
        print(f'Название: {data.get(\"question\") or data.get(\"title\")}')
    else:
        print(f'Рынок не найден (статус: {response.status_code})')
except Exception as e:
    print(f'Ошибка: {e}')
"
```

## Способ 5: Через поиск всех активных рынков

```bash
python3 -c "
import requests

keywords = ['warriors', 'pelicans']

url = 'https://clob.polymarket.com/markets'
params = {'limit': 500, 'sort': 'volume'}

response = requests.get(url, params=params, timeout=20)
if response.status_code == 200:
    markets = response.json()
    if isinstance(markets, list):
        for market in markets:
            title = (market.get('question') or market.get('title') or '').lower()
            if all(kw.lower() in title for kw in keywords):
                condition_id = market.get('conditionId') or market.get('id')
                print(f'✅ Найден: {market.get(\"question\") or market.get(\"title\")}')
                print(f'   Condition ID: {condition_id}')
                print(f'   Активен: {market.get(\"active\", False)}')
                print()
"
```

## Способ 6: Из логов бота

Если бот логировал condition_id:

```bash
grep -i "warriors\|pelicans" polymarket_notifier.log | grep -i "condition"
```

Или:
```bash
grep "condition_id" polymarket_notifier.log | tail -20
```

## Быстрый поиск через скрипт

Самый простой способ - использовать созданный скрипт:

```bash
# Базовый поиск
python3 find_condition_id.py "Warriors Pelicans"

# С полным названием
python3 find_condition_id.py "Warriors vs Pelicans"

# С другими вариантами
python3 find_condition_id.py "Golden State Pelicans"
```

Скрипт автоматически:
- Ищет в базе данных
- Ищет через API
- Пробует различные варианты названия
- Сохраняет результаты в файл
- Показывает команду для сохранения кошельков

## После нахождения condition_id

Когда найдете condition_id, используйте его для сохранения кошельков:

```bash
python3 save_wallets_from_market.py <condition_id>
```

Это сохранит все кошельки с этого рынка в файл и в БД.

