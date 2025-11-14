# Настройка ежедневного расписания

## Обзор

Система состоит из двух компонентов:
1. **Daily Wallet Refresh** - ежедневное обновление кошельков (02:00 UTC)
2. **Daily Report** - ежедневный отчёт (23:00 UTC)

## Установка

### 1. Скопировать файлы на сервер

```bash
scp daily_wallet_refresh.py daily_report.py ubuntu@YOUR_SERVER_IP:/opt/polymarket-bot/
scp polymarket-daily-refresh.service polymarket-daily-refresh.timer ubuntu@YOUR_SERVER_IP:/tmp/
scp polymarket-daily-report.service polymarket-daily-report.timer ubuntu@YOUR_SERVER_IP:/tmp/
```

### 2. Установить systemd units

```bash
ssh ubuntu@YOUR_SERVER_IP
sudo cp /tmp/polymarket-daily-refresh.service /etc/systemd/system/
sudo cp /tmp/polymarket-daily-refresh.timer /etc/systemd/system/
sudo cp /tmp/polymarket-daily-report.service /etc/systemd/system/
sudo cp /tmp/polymarket-daily-report.timer /etc/systemd/system/

sudo systemctl daemon-reload
```

### 3. Активировать timers

```bash
sudo systemctl enable polymarket-daily-refresh.timer
sudo systemctl enable polymarket-daily-report.timer
sudo systemctl start polymarket-daily-refresh.timer
sudo systemctl start polymarket-daily-report.timer
```

### 4. Проверить статус

```bash
# Проверить timers
sudo systemctl list-timers polymarket-daily-*

# Проверить последний запуск
sudo systemctl status polymarket-daily-refresh.service
sudo systemctl status polymarket-daily-report.service

# Посмотреть логи
sudo journalctl -u polymarket-daily-refresh.service
sudo journalctl -u polymarket-daily-report.service
```

## Ручной запуск (для тестирования)

```bash
# Запустить refresh вручную
sudo systemctl start polymarket-daily-refresh.service

# Запустить report вручную
sudo systemctl start polymarket-daily-report.service
```

## Настройка времени

Чтобы изменить время запуска, отредактируйте файлы `.timer`:

```bash
sudo nano /etc/systemd/system/polymarket-daily-refresh.timer
```

Измените строку:
```
OnCalendar=*-*-* 02:00:00
```

На нужное время (формат: `YYYY-MM-DD HH:MM:SS` или `*-*-* HH:MM:SS` для ежедневного запуска).

После изменения:
```bash
sudo systemctl daemon-reload
sudo systemctl restart polymarket-daily-refresh.timer
```

## Мониторинг

### Проверить следующее время запуска:
```bash
sudo systemctl list-timers polymarket-daily-*
```

### Посмотреть логи:
```bash
# Логи refresh
sudo journalctl -u polymarket-daily-refresh.service --since "1 day ago"

# Логи report
sudo journalctl -u polymarket-daily-report.service --since "1 day ago"
```

## Альтернатива: Cron

Если предпочитаете cron вместо systemd timers:

```bash
crontab -e
```

Добавить:
```
# Daily wallet refresh at 02:00 UTC
0 2 * * * cd /opt/polymarket-bot && /opt/polymarket-bot/venv/bin/python3 daily_wallet_refresh.py >> /opt/polymarket-bot/daily_refresh.log 2>&1

# Daily report at 23:00 UTC
0 23 * * * cd /opt/polymarket-bot && /opt/polymarket-bot/venv/bin/python3 daily_report.py >> /opt/polymarket-bot/daily_report.log 2>&1
```

