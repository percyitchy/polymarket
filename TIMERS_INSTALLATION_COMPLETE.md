# ✅ Timers установлены успешно

## Дата установки: 2025-11-07

---

## Расписание

### 📊 Daily Wallet Analysis
- **Сервис:** `polymarket-daily-analysis.service`
- **Таймер:** `polymarket-daily-analysis.timer`
- **Время запуска:** **03:00 UTC** ежедневно
- **Описание:** Сбор и анализ кошельков из всех источников

### 📈 Daily Report
- **Сервис:** `polymarket-daily-report.service`
- **Таймер:** `polymarket-daily-report.timer`
- **Время запуска:** **23:00 UTC** ежедневно
- **Описание:** Генерация ежедневного отчёта с алертами

---

## Проверка статуса

### Команда для проверки:
```bash
systemctl list-timers polymarket-daily-*.timer
```

### Ожидаемый вывод:
```
NEXT                         LEFT          LAST                         PASSED       UNIT
Thu 2025-11-08 03:00:00 UTC  3h 45min left n/a                          n/a          polymarket-daily-analysis.timer
Wed 2025-11-07 23:00:00 UTC  15min left    n/a                          n/a          polymarket-daily-report.timer
```

---

## Мониторинг

### Просмотр логов

#### В реальном времени:
```bash
# Логи анализа кошельков
journalctl -u polymarket-daily-analysis.service -f

# Логи отчёта
journalctl -u polymarket-daily-report.service -f
```

#### Последние записи:
```bash
# Последние 100 строк анализа
journalctl -u polymarket-daily-analysis.service -n 100

# Последние 100 строк отчёта
journalctl -u polymarket-daily-report.service -n 100
```

#### За период:
```bash
# За последний час
journalctl -u polymarket-daily-analysis.service --since "1 hour ago"

# За сегодня
journalctl -u polymarket-daily-analysis.service --since "today"

# За конкретную дату
journalctl -u polymarket-daily-analysis.service --since "2025-11-07" --until "2025-11-08"
```

---

## Ручной запуск (для тестирования)

### Запустить анализ:
```bash
sudo systemctl start polymarket-daily-analysis.service
```

### Запустить отчёт:
```bash
sudo systemctl start polymarket-daily-report.service
```

---

## Что должно происходить

### В 03:00 UTC (Daily Wallet Analysis):

1. **Запуск:**
   - Скрипт `daily_wallet_analysis.py` запускается
   - Инициализируются workers (10 workers)
   - Начинается сбор кошельков

2. **Процесс:**
   - Сбор с `polymarketanalytics.com` (до 2500 кошельков)
   - Сбор с Polymarket leaderboards (weekly/monthly, 20 страниц)
   - Добавление новых кошельков в очередь анализа
   - Обработка очереди workers

3. **Завершение:**
   - Workers останавливаются
   - Summary отправляется в Telegram

4. **Telegram сообщение:**
   ```
   📊 Daily Wallet Analysis Complete
   
   Duration: X minutes
   
   Wallets Added:
   • polymarketanalytics.com: N
   • Leaderboards: M
   • Total: K
   
   Queue Status:
   • Pending: P
   • Processing: R
   • Completed: C
   • Failed: F
   • Total: T
   
   Workers: 10 active
   ```

### В 23:00 UTC (Daily Report):

1. **Запуск:**
   - Скрипт `daily_report.py` запускается
   - Собирается статистика за день

2. **Процесс:**
   - Подсчёт wallets (total, tracked, added today)
   - Подсчёт jobs (completed, failed, pending)
   - Расчёт скорости обработки
   - Проверка условий для алертов

3. **Завершение:**
   - Отчёт отправляется в Telegram

4. **Telegram сообщение:**
   ```
   📊 Daily Report - YYYY-MM-DD
   
   📈 Wallet Statistics:
   • Total wallets: N
   • Tracked wallets: M
   • Added today: K
   • Updated today: L
   
   ⚙️ Queue Statistics:
   • Pending: P
   • Processing: R
   • Completed today: C
   • Failed today: F
   • Failed rate: X%
   • Processing speed: ~Y jobs/hour
   
   [Алерты, если есть]
   ```

---

## Алерты

Алерты срабатывают при превышении порогов из `.env`:

- **High failed rate:** `ALERT_FAILED_RATE_THRESHOLD` (по умолчанию 5%)
- **Queue stuck:** `ALERT_QUEUE_STUCK_THRESHOLD` (по умолчанию 1000 pending + 0 completed)
- **Queue slow:** `ALERT_QUEUE_SLOW_THRESHOLD` (по умолчанию 500 pending + <20 jobs/hour)
- **Low processing rate:** <10 jobs/day с pending jobs

---

## Управление timers

### Перезапуск timers:
```bash
sudo systemctl restart polymarket-daily-analysis.timer
sudo systemctl restart polymarket-daily-report.timer
```

### Остановка timers:
```bash
sudo systemctl stop polymarket-daily-analysis.timer
sudo systemctl stop polymarket-daily-report.timer
```

### Отключение timers:
```bash
sudo systemctl disable polymarket-daily-analysis.timer
sudo systemctl disable polymarket-daily-report.timer
```

### Включение timers:
```bash
sudo systemctl enable polymarket-daily-analysis.timer
sudo systemctl enable polymarket-daily-report.timer
```

---

## Изменение расписания

### Редактировать timer:
```bash
sudo nano /etc/systemd/system/polymarket-daily-analysis.timer
```

### Изменить время (например, на 04:00 UTC):
```ini
OnCalendar=*-*-* 04:00:00
```

### Применить изменения:
```bash
sudo systemctl daemon-reload
sudo systemctl restart polymarket-daily-analysis.timer
```

---

## Проверка работоспособности

### Еженедельная проверка:
```bash
# Проверить статус timers
systemctl list-timers polymarket-daily-*.timer

# Проверить последние логи
journalctl -u polymarket-daily-analysis.service --since "7 days ago" | tail -50
journalctl -u polymarket-daily-report.service --since "7 days ago" | tail -50
```

### При проблемах:
1. Проверить логи на ошибки
2. Проверить статус сервисов
3. Проверить `.env` файл
4. Проверить права доступа к файлам
5. Проверить Telegram credentials

---

## Файлы

- `/etc/systemd/system/polymarket-daily-analysis.service`
- `/etc/systemd/system/polymarket-daily-analysis.timer`
- `/etc/systemd/system/polymarket-daily-report.service`
- `/etc/systemd/system/polymarket-daily-report.timer`
- `/opt/polymarket-bot/daily_wallet_analysis.py`
- `/opt/polymarket-bot/daily_report.py`

---

## ✅ Система полностью автоматизирована

Теперь система будет:
- ✅ Ежедневно собирать и анализировать кошельки в 03:00 UTC
- ✅ Ежедневно генерировать отчёты в 23:00 UTC
- ✅ Отправлять уведомления в Telegram
- ✅ Срабатывать алерты при превышении порогов

**Следующая проверка:** После первого срабатывания таймеров (03:00 или 23:00 UTC)

