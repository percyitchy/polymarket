# Daily Schedule - Quick Start Guide

## Что было создано

### 1. Скрипты
- **`daily_wallet_analysis.py`** - Ежедневный сбор и анализ кошельков
- **`daily_report.py`** - Ежедневный отчёт с алертами (улучшен)
- **`get_daily_stats.py`** - Утилита для получения статистики

### 2. Systemd файлы
- **`polymarket-daily-analysis.service`** - Сервис для ежедневного анализа
- **`polymarket-daily-analysis.timer`** - Таймер (запуск в 03:00 UTC)
- **`polymarket-daily-report.service`** - Сервис для ежедневного отчёта
- **`polymarket-daily-report.timer`** - Таймер (запуск в 23:00 UTC)

### 3. Утилиты
- **`setup_daily_schedule.sh`** - Автоматическая установка
- **`DAILY_SCHEDULE_README.md`** - Полная документация

## Быстрая установка

### На сервере:

```bash
cd /opt/polymarket-bot

# 1. Добавить alert thresholds в .env (если еще не добавлены)
cat >> .env << 'EOF'

# Alert Thresholds
ALERT_FAILED_RATE_THRESHOLD=0.05
ALERT_QUEUE_STUCK_THRESHOLD=1000
ALERT_QUEUE_SLOW_THRESHOLD=500
ALERT_MIN_JOBS_PER_HOUR=20.0
EOF

# 2. Установить systemd timers
sudo ./setup_daily_schedule.sh

# 3. Проверить статус
systemctl list-timers polymarket-daily-*.timer
```

## Что делает каждый компонент

### Daily Analysis (03:00 UTC)
1. Собирает кошельки с `polymarketanalytics.com` (до 2500)
2. Собирает кошельки с Polymarket leaderboards (weekly/monthly, 20 страниц)
3. Добавляет все в очередь анализа
4. Запускает workers для обработки
5. Отправляет summary в Telegram

### Daily Report (23:00 UTC)
1. Собирает статистику за день
2. Проверяет условия для алертов
3. Формирует отчёт
4. Отправляет в Telegram reports channel

## Мониторинг

```bash
# Статус таймеров
systemctl list-timers polymarket-daily-*.timer

# Логи анализа
journalctl -u polymarket-daily-analysis.service -f

# Логи отчёта
journalctl -u polymarket-daily-report.service -f

# Последние 50 строк
journalctl -u polymarket-daily-analysis.service -n 50
```

## Ручной запуск (для тестирования)

```bash
# Запустить анализ
sudo systemctl start polymarket-daily-analysis.service

# Запустить отчёт
sudo systemctl start polymarket-daily-report.service
```

## Настройка времени запуска

Отредактируйте timer файлы:

```bash
sudo nano /etc/systemd/system/polymarket-daily-analysis.timer
# Измените: OnCalendar=*-*-* 03:00:00

sudo systemctl daemon-reload
sudo systemctl restart polymarket-daily-analysis.timer
```

## SQL запросы для проверки статистики

См. `DAILY_SCHEDULE_README.md` раздел "SQL Queries for Daily Statistics"

