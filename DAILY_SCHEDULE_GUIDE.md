# 📅 Руководство по ежедневному расписанию и мониторингу

## 🎯 Обзор

Система автоматически выполняет два ежедневных задания:

1. **Daily Wallet Refresh** (02:00 UTC) - Сбор новых кошельков из всех источников
2. **Daily Report** (23:00 UTC) - Генерация отчёта и проверка алертов

## 📋 Настроенные задачи

### 1. Daily Wallet Refresh (`daily_wallet_refresh.py`)

**Когда:** Ежедневно в 02:00 UTC  
**Что делает:**
- Собирает кошельки из `polymarketanalytics.com` (до 2500)
- Собирает кошельки из Polymarket leaderboards (weekly/monthly, по 20 страниц)
- Добавляет новые кошельки в очередь анализа
- Отправляет сводку в Telegram

**Systemd Timer:** `polymarket-daily-refresh.timer`  
**Systemd Service:** `polymarket-daily-refresh.service`

### 2. Daily Report (`daily_report.py`)

**Когда:** Ежедневно в 23:00 UTC  
**Что делает:**
- Генерирует статистику за день
- Проверяет условия для алертов
- Отправляет отчёт в Telegram

**Systemd Timer:** `polymarket-daily-report.timer`  
**Systemd Service:** `polymarket-daily-report.service`

## 🔧 Установка и настройка

### Шаг 1: Копирование systemd файлов на сервер

```bash
# На локальной машине
scp polymarket-daily-refresh.service polymarket-daily-refresh.timer \
    polymarket-daily-report.service polymarket-daily-report.timer \
    ubuntu@YOUR_SERVER_IP:/tmp/

# На сервере
sudo mv /tmp/polymarket-daily-*.{service,timer} /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/polymarket-daily-*.{service,timer}
```

### Шаг 2: Активация timers

```bash
# Перезагрузить systemd
sudo systemctl daemon-reload

# Включить и запустить timers
sudo systemctl enable polymarket-daily-refresh.timer
sudo systemctl enable polymarket-daily-report.timer
sudo systemctl start polymarket-daily-refresh.timer
sudo systemctl start polymarket-daily-report.timer
```

### Шаг 3: Проверка статуса

```bash
# Проверить статус timers
sudo systemctl list-timers polymarket-daily-*

# Проверить следующее время запуска
sudo systemctl status polymarket-daily-refresh.timer
sudo systemctl status polymarket-daily-report.timer
```

## 📊 SQL-запросы для статистики

### Статистика кошельков за день

```sql
-- Кошельки добавленные сегодня
SELECT COUNT(*) FROM wallets 
WHERE datetime(added_at) >= datetime('now', 'start of day')
AND datetime(added_at) < datetime('now', 'start of day', '+1 day');

-- Кошельки обновленные сегодня
SELECT COUNT(*) FROM wallets 
WHERE datetime(updated_at) >= datetime('now', 'start of day')
AND datetime(updated_at) < datetime('now', 'start of day', '+1 day');

-- Кошельки по источнику (сегодня)
SELECT source, COUNT(*) FROM wallets 
WHERE datetime(added_at) >= datetime('now', 'start of day')
AND datetime(added_at) < datetime('now', 'start of day', '+1 day')
GROUP BY source;
```

### Статистика очереди за день

```sql
-- Jobs завершенные сегодня
SELECT COUNT(*) FROM wallet_analysis_jobs 
WHERE status = 'completed'
AND datetime(updated_at) >= datetime('now', 'start of day')
AND datetime(updated_at) < datetime('now', 'start of day', '+1 day');

-- Jobs failed сегодня
SELECT COUNT(*) FROM wallet_analysis_jobs 
WHERE status = 'failed'
AND datetime(updated_at) >= datetime('now', 'start of day')
AND datetime(updated_at) < datetime('now', 'start of day', '+1 day');

-- Среднее время обработки (сегодня)
SELECT AVG(
    (julianday(updated_at) - julianday(created_at)) * 86400
) FROM wallet_analysis_jobs 
WHERE status = 'completed'
AND datetime(updated_at) >= datetime('now', 'start of day')
AND datetime(updated_at) < datetime('now', 'start of day', '+1 day');
```

### Текущее состояние очереди

```sql
-- Статусы jobs
SELECT status, COUNT(*) FROM wallet_analysis_jobs
GROUP BY status;

-- Ready jobs (готовы к обработке)
SELECT COUNT(*) FROM wallet_analysis_jobs 
WHERE status = 'pending' 
AND (next_retry_at IS NULL OR next_retry_at <= datetime('now'));
```

## ⚠️ Система алертинга

### Типы алертов

1. **Critical (🚨)** - Требуют немедленного внимания
   - Queue stuck: очередь не обрабатывается (pending > 1000, completed = 0)

2. **Warning (⚠️)** - Потенциальные проблемы
   - High failed rate: >5% jobs failed
   - Queue slow: очередь обрабатывается медленно (<20 jobs/hour при pending > 500)
   - Low processing rate: <10 jobs/day при наличии pending jobs

3. **Info (ℹ️)** - Информационные сообщения
   - No new wallets: не добавлено новых кошельков за день
   - Database large: база данных растёт (>5000 кошельков)

### Настройка порогов

Пороги можно изменить в `daily_report.py`:

```python
# В функции check_alerts()
FAILED_RATE_THRESHOLD = 0.05  # 5% - порог для failed rate
QUEUE_SLOW_THRESHOLD = 20     # jobs/hour - минимальная скорость обработки
LOW_PROCESSING_THRESHOLD = 10 # jobs/day - минимальное количество обработанных jobs
```

## 🔍 Мониторинг и отладка

### Просмотр логов

```bash
# Логи refresh (последние 24 часа)
sudo journalctl -u polymarket-daily-refresh.service --since "1 day ago"

# Логи report (последние 24 часа)
sudo journalctl -u polymarket-daily-report.service --since "1 day ago"

# Логи в реальном времени
sudo journalctl -u polymarket-daily-refresh.service -f
sudo journalctl -u polymarket-daily-report.service -f
```

### Ручной запуск

```bash
# Запустить refresh вручную
sudo systemctl start polymarket-daily-refresh.service

# Запустить report вручную
sudo systemctl start polymarket-daily-report.service

# Или напрямую через Python
cd /opt/polymarket-bot
venv/bin/python3 daily_wallet_refresh.py
venv/bin/python3 daily_report.py
```

### Проверка следующего запуска

```bash
# Когда запустится следующий раз
sudo systemctl list-timers polymarket-daily-* --no-pager

# Детальная информация
sudo systemctl status polymarket-daily-refresh.timer
sudo systemctl status polymarket-daily-report.timer
```

## ⏰ Изменение времени запуска

### Для Daily Refresh

```bash
sudo nano /etc/systemd/system/polymarket-daily-refresh.timer
```

Изменить строку:
```
OnCalendar=*-*-* 02:00:00
```

На нужное время (формат: `*-*-* HH:MM:SS` для ежедневного запуска).

### Для Daily Report

```bash
sudo nano /etc/systemd/system/polymarket-daily-report.timer
```

Изменить строку:
```
OnCalendar=*-*-* 23:00:00
```

### После изменения

```bash
sudo systemctl daemon-reload
sudo systemctl restart polymarket-daily-refresh.timer
sudo systemctl restart polymarket-daily-report.timer
```

## 📈 Формат отчёта

Daily Report включает:

1. **Wallet Statistics:**
   - Total wallets
   - Tracked wallets
   - Added today
   - Updated today
   - By source (breakdown)

2. **Queue Statistics:**
   - Pending jobs
   - Processing jobs
   - Completed today
   - Failed today
   - Failed rate
   - Avg processing time
   - Processing speed (jobs/hour)
   - Estimated time to clear queue

3. **Current Job Status:**
   - Breakdown по статусам (pending, processing, completed, failed)

4. **Alerts:**
   - Critical alerts (🚨)
   - Warnings (⚠️)
   - Info messages (ℹ️)

## 🔄 Альтернатива: Cron

Если предпочитаете cron вместо systemd timers:

```bash
crontab -e
```

Добавить:

```cron
# Daily wallet refresh at 02:00 UTC
0 2 * * * cd /opt/polymarket-bot && /opt/polymarket-bot/venv/bin/python3 daily_wallet_refresh.py >> /opt/polymarket-bot/logs/daily_refresh.log 2>&1

# Daily report at 23:00 UTC
0 23 * * * cd /opt/polymarket-bot && /opt/polymarket-bot/venv/bin/python3 daily_report.py >> /opt/polymarket-bot/logs/daily_report.log 2>&1
```

## ✅ Чеклист настройки

- [ ] Systemd файлы скопированы на сервер
- [ ] Timers активированы и запущены
- [ ] Проверено следующее время запуска
- [ ] Протестирован ручной запуск обоих скриптов
- [ ] Проверены логи после первого автоматического запуска
- [ ] Настроены пороги алертинга (если нужно)
- [ ] Telegram уведомления приходят корректно

## 🐛 Решение проблем

### Timer не запускается

```bash
# Проверить статус
sudo systemctl status polymarket-daily-refresh.timer

# Проверить логи
sudo journalctl -u polymarket-daily-refresh.timer

# Перезагрузить systemd
sudo systemctl daemon-reload
sudo systemctl restart polymarket-daily-refresh.timer
```

### Скрипт падает с ошибкой

```bash
# Проверить логи service
sudo journalctl -u polymarket-daily-refresh.service -n 50

# Запустить вручную для отладки
cd /opt/polymarket-bot
venv/bin/python3 daily_wallet_refresh.py
```

### Отчёты не приходят в Telegram

1. Проверить `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID` в `.env`
2. Проверить `reports_chat_id` в `notify.py`
3. Запустить report вручную и проверить ошибки

## 📝 Примечания

- Все времена указаны в UTC
- Логи сохраняются в systemd journal и в файлы (если настроено)
- Timers используют `Persistent=true`, поэтому пропущенные запуски будут выполнены при следующем старте системы
- Для изменения времени запуска нужно перезагрузить systemd daemon

