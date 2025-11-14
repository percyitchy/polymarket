# Ежедневное расписание - Резюме

## ✅ Что создано

### 1. Скрипты

**`daily_wallet_refresh.py`** - Ежедневное обновление кошельков
- Собирает кошельки из `polymarketanalytics.com` (до 2500)
- Собирает кошельки из Polymarket leaderboards (weekly/monthly, по 20 страниц)
- Добавляет новые кошельки в очередь анализа
- Отправляет сводку в Telegram

**`daily_report.py`** - Ежедневный отчёт
- Генерирует статистику за день
- Проверяет условия для алертов
- Отправляет отчёт в Telegram

### 2. Systemd Timers

**`polymarket-daily-refresh.timer`**
- Запускается ежедневно в 02:00 UTC
- Вызывает `polymarket-daily-refresh.service`

**`polymarket-daily-report.timer`**
- Запускается ежедневно в 23:00 UTC
- Вызывает `polymarket-daily-report.service`

## 📊 SQL-запросы для статистики

### Статистика кошельков за день:
```sql
-- Кошельки добавленные сегодня
SELECT COUNT(*) FROM wallets 
WHERE datetime(added_at) >= datetime('2025-11-07T00:00:00')
AND datetime(added_at) < datetime('2025-11-08T00:00:00');

-- Кошельки обновленные сегодня
SELECT COUNT(*) FROM wallets 
WHERE datetime(updated_at) >= datetime('2025-11-07T00:00:00')
AND datetime(updated_at) < datetime('2025-11-08T00:00:00');
```

### Статистика очереди за день:
```sql
-- Jobs завершенные сегодня
SELECT COUNT(*) FROM wallet_analysis_jobs 
WHERE status = 'completed'
AND datetime(updated_at) >= datetime('2025-11-07T00:00:00')
AND datetime(updated_at) < datetime('2025-11-08T00:00:00');

-- Jobs failed сегодня
SELECT COUNT(*) FROM wallet_analysis_jobs 
WHERE status = 'failed'
AND datetime(updated_at) >= datetime('2025-11-07T00:00:00')
AND datetime(updated_at) < datetime('2025-11-08T00:00:00');

-- Среднее время обработки
SELECT AVG(
    (julianday(updated_at) - julianday(created_at)) * 86400
) FROM wallet_analysis_jobs 
WHERE status = 'completed'
AND datetime(updated_at) >= datetime('2025-11-07T00:00:00')
AND datetime(updated_at) < datetime('2025-11-08T00:00:00');
```

## ⚠️ Условия для алертов

1. **Высокий процент failed (>5%)**
   - `failed_rate > 0.05`

2. **Очередь застряла (pending > 1000 и 0 completed сегодня)**
   - `queue_pending > 1000 AND jobs_completed_today == 0`

3. **Низкая скорость обработки (<10 jobs/день)**
   - `jobs_completed_today < 10 AND queue_pending > 0`

4. **Нет новых кошельков (информационное)**
   - `wallets_added_today == 0`

## 🔧 Управление

### Проверить статус timers:
```bash
sudo systemctl list-timers polymarket-daily-*
```

### Запустить вручную:
```bash
# Refresh
sudo systemctl start polymarket-daily-refresh.service

# Report
sudo systemctl start polymarket-daily-report.service
```

### Посмотреть логи:
```bash
# Refresh
sudo journalctl -u polymarket-daily-refresh.service --since "1 day ago"

# Report
sudo journalctl -u polymarket-daily-report.service --since "1 day ago"
```

### Изменить время запуска:
```bash
sudo nano /etc/systemd/system/polymarket-daily-refresh.timer
# Изменить OnCalendar=*-*-* 02:00:00 на нужное время
sudo systemctl daemon-reload
sudo systemctl restart polymarket-daily-refresh.timer
```

## 📝 Формат отчёта

Отчёт включает:
- Общее количество кошельков
- Отслеживаемые кошельки
- Добавленные сегодня
- Обновленные сегодня
- Статистика очереди (pending, processing, completed, failed)
- Процент failed
- Среднее время обработки
- Алерты (если есть)

Отправляется в Telegram reports channel.

