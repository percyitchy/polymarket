# 📊 Мониторинг прогресса восстановления кошельков

## Быстрая проверка статуса

### 1. Команда для проверки прогресса:
```bash
python3 check_restore_progress.py
```

Или используйте существующий скрипт:
```bash
python3 check_progress.py
```

### 2. Проверка через Python напрямую:
```python
python3 -c "
import sys
sys.path.insert(0, '.')
from db import PolymarketDB
db = PolymarketDB('polymarket_notifier.db')
stats = db.get_wallet_stats()
queue_stats = db.get_queue_stats()
print(f'Total wallets: {stats.get(\"total_wallets\", 0):,}')
print(f'Tracked: {stats.get(\"tracked_wallets\", 0):,}')
print(f'Pending jobs: {queue_stats.get(\"pending_jobs\", 0):,}')
print(f'Completed: {queue_stats.get(\"completed_jobs\", 0):,}')
"
```

## Мониторинг в реальном времени

### 1. Логи мониторинга:
```bash
# Последние записи о мониторинге
tail -f polymarket_notifier.log | grep -E "\[MONITOR\]|\[HB\]"

# Или только heartbeat (каждые 30 секунд)
tail -f polymarket_notifier.log | grep "\[HB\]"

# Статистика очереди
tail -f polymarket_notifier.log | grep "Queue status"
```

### 2. Heartbeat в Telegram (если включен):
Если в `.env` установлено `TELEGRAM_HEARTBEAT=1`, бот будет отправлять статус каждые ~70 секунд.

### 3. Проверка активности workers:
```bash
# Логи анализа кошельков
tail -f polymarket_notifier.log | grep -E "WalletAnalyzer|analyzed|completed"
```

## Что смотреть

### Ключевые метрики:

1. **Total wallets** - общее количество кошельков в базе
2. **Tracked wallets** - количество отслеживаемых кошельков (для мониторинга)
3. **Pending jobs** - кошельки, ожидающие анализа
4. **Completed jobs** - проанализированные кошельки
5. **Progress %** - процент завершения анализа

### Ожидаемые значения:

- ✅ **Total wallets**: ~19,000+ (после восстановления)
- ✅ **Tracked wallets**: должно быть близко к Total wallets
- ✅ **Pending jobs**: должно уменьшаться со временем
- ✅ **Completed jobs**: должно увеличиваться

## Текущий статус

Запустите `python3 check_restore_progress.py` для актуальной информации.

