# 🚀 Деплой HashDive Telegram на сервер

## 📋 Что нужно

1. ✅ Ubuntu сервер (у вас уже есть)
2. ✅ Python 3, venv (уже настроено)
3. ✅ Telegram Bot Token (в .env)
4. ✅ Файлы скрипта

## 🔧 Подготовка сервера

### Шаг 1: Загрузить файлы

**На LOCAL машине:**
```bash
# Загрузить файлы на сервер
scp hashdive_telegram_server.py ubuntu@YOUR_SERVER_IP:/home/ubuntu/
scp .env ubuntu@YOUR_SERVER_IP:/home/ubuntu/
```

### Шаг 2: SSH на сервер
```bash
ssh ubuntu@YOUR_SERVER_IP
```

### Шаг 3: Установить зависимости

```bash
cd /opt/polymarket-bot
source venv/bin/activate

# Install undetected-chromedriver
pip install undetected-chromedriver

# Move files
mv /home/ubuntu/hashdive_telegram_server.py .
mv /home/ubuntu/.env .

# Make executable
chmod +x hashdive_telegram_server.py
```

### Шаг 4: Первый запуск (с браузером для логина)

```bash
# Запустить с видимым браузером
python3 hashdive_telegram_server.py --no-headless
```

**Что делать:**
1. Откроется браузер (если X11 forwarding включен)
2. Или нужно настроить remote debugging
3. Войдите в HashDive через Google
4. Нажмите Ctrl+C

**Альтернатива (без GUI):**

Если нет графики, используйте VNC или другой метод:
```bash
# Установить xvfb (виртуальный дисплей)
sudo apt install xvfb -y

# Запустить через xvfb
xvfb-run -a python3 hashdive_telegram_server.py --no-headless &
```

### Шаг 5: Запуск в headless режиме

**После логина:**

```bash
# Запустить в фоновом режиме
nohup python3 hashdive_telegram_server.py > hashdive.log 2>&1 &
```

### Шаг 6: Проверка

```bash
# Смотреть логи
tail -f hashdive.log

# Проверить процесс
ps aux | grep hashdive

# Остановить
pkill -f hashdive_telegram_server
```

## ⚙️ Автозапуск (systemd)

Создайте service файл:

```bash
sudo tee /etc/systemd/system/hashdive-bot.service > /dev/null <<EOF
[Unit]
Description=HashDive Insiders Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/polymarket-bot
Environment=PATH=/opt/polymarket-bot/venv/bin
ExecStart=/opt/polymarket-bot/venv/bin/python hashdive_telegram_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable hashdive-bot
sudo systemctl start hashdive-bot

# Check status
sudo systemctl status hashdive-bot
sudo journalctl -u hashdive-bot -f
```

## 📊 Управление сервисом

```bash
# Статус
sudo systemctl status hashdive-bot

# Логи
sudo journalctl -u hashdive-bot -f

# Перезапуск
sudo systemctl restart hashdive-bot

# Остановка
sudo systemctl stop hashdive-bot
```

## 🐛 Отладка

### Проблема: Браузер не запускается на сервере

**Решение 1:** Добавить зависимости:
```bash
sudo apt install -y chromium-browser chromium-chromedriver
```

**Решение 2:** Использовать remote debugging:
```bash
# Запустить Chrome с удаленным доступом
google-chrome --headless --remote-debugging-port=9222

# В другом терминале подключиться
python3 hashdive_telegram_server.py
```

### Проблема: Нет X11 для GUI браузера

**Решение:** Использовать xvfb:
```bash
sudo apt install xvfb -y
export DISPLAY=:99
Xvfb :99 &
xvfb-run -a python3 hashdive_telegram_server.py --no-headless
```

## 🎯 Готово!

После деплоя:
- ✅ Скрипт работает на сервере 24/7
- ✅ Проверка каждые 15 минут
- ✅ Алерты в Telegram канал: -1003285149330
- ✅ Headless режим (без GUI)

## 📝 Проверка работы

```bash
# SSH на сервер
ssh ubuntu@YOUR_SERVER_IP

# Смотреть логи
tail -f /opt/polymarket-bot/hashdive.log

# Или systemd logs
sudo journalctl -u hashdive-bot -f

# Проверить процесс
ps aux | grep hashdive
```

## 🔄 Обновление скрипта

```bash
# На локальной машине
scp hashdive_telegram_server.py ubuntu@YOUR_SERVER_IP:/opt/polymarket-bot/

# На сервере
sudo systemctl restart hashdive-bot
```

## 💡 Советы

1. **Первый запуск** - с `--no-headless` для логина
2. **Дальше** - headless режим (по умолчанию)
3. **Логи** - смотреть в `hashdive.log` или systemd
4. **Обновления** - перезапускать service после изменений

Удачи! 🚀

