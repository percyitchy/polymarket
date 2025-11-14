# 🚀 Инструкция по настройке бота на сервере

## ✅ Файлы загружены

Все файлы проекта успешно загружены на сервер:
- **Сервер**: YOUR_SERVER_IP
- **Директория**: `/opt/polymarket-bot`
- **Файлов загружено**: 141

## 📋 Следующие шаги на сервере

### 1. Подключитесь к серверу
```bash
ssh -l ubuntu YOUR_SERVER_IP
```

### 2. Перейдите в директорию проекта
```bash
cd /opt/polymarket-bot
```

### 3. Проверьте и настройте .env файл
```bash
nano .env
```

**Важные настройки:**
- `TELEGRAM_BOT_TOKEN` - токен вашего Telegram бота
- `TELEGRAM_CHAT_ID` - ID чата для уведомлений
- `ENABLE_PROXIES=false` - прокси отключены по умолчанию
- `DB_PATH=polymarket_notifier.db` - путь к базе данных

### 4. Установите зависимости
```bash
# Проверьте Python версию
python3 --version

# Установите зависимости
pip3 install -r requirements.txt

# Или используйте venv (рекомендуется)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Проверьте структуру файлов
```bash
ls -la
# Должны быть видны:
# - polymarket_notifier.py (главный файл)
# - db.py
# - notify.py
# - utils/http_client.py (новый модуль)
# - requirements.txt
```

### 6. Настройте systemd сервисы (опционально)

Если нужно запускать бота как сервис:

```bash
# Скопируйте service файлы
sudo cp polymarket-daily-analysis.service /etc/systemd/system/
sudo cp polymarket-daily-analysis.timer /etc/systemd/system/
sudo cp polymarket-daily-refresh.service /etc/systemd/system/
sudo cp polymarket-daily-refresh.timer /etc/systemd/system/
sudo cp polymarket-daily-report.service /etc/systemd/system/
sudo cp polymarket-daily-report.timer /etc/systemd/system/

# Перезагрузите systemd
sudo systemctl daemon-reload

# Включите таймеры
sudo systemctl enable polymarket-daily-analysis.timer
sudo systemctl enable polymarket-daily-refresh.timer
sudo systemctl enable polymarket-daily-report.timer

# Запустите таймеры
sudo systemctl start polymarket-daily-analysis.timer
sudo systemctl start polymarket-daily-refresh.timer
sudo systemctl start polymarket-daily-report.timer
```

### 7. Запустите бота

**Вариант A: Ручной запуск (для тестирования)**
```bash
cd /opt/polymarket-bot
python3 polymarket_notifier.py
```

**Вариант B: Фоновый режим**
```bash
cd /opt/polymarket-bot
nohup python3 polymarket_notifier.py > polymarket_notifier.log 2>&1 &
```

**Вариант C: Systemd сервис (если настроен)**
```bash
sudo systemctl start polymarket-bot
sudo systemctl status polymarket-bot
```

### 8. Проверьте логи
```bash
# Если запущен в фоне
tail -f polymarket_notifier.log

# Если через systemd
sudo journalctl -u polymarket-bot -f
```

## 🔍 Проверка работоспособности

### 1. Проверьте подключение к Telegram
```bash
cd /opt/polymarket-bot
python3 -c "from notify import TelegramNotifier; TelegramNotifier().test_connection()"
```

### 2. Проверьте базу данных
```bash
python3 -c "from db import PolymarketDB; db = PolymarketDB(); print(f'Кошельков в БД: {len(db.get_all_wallets())}')"
```

### 3. Проверьте HTTP клиент (новый модуль)
```bash
python3 test_http_fallback.py
```

## ⚙️ Важные настройки

### Прокси отключены по умолчанию
В `.env` файле:
```env
ENABLE_PROXIES=false
```

Если нужно включить прокси:
```env
ENABLE_PROXIES=true
POLYMARKET_PROXIES=socks5://...
```

### База данных
База данных создается автоматически при первом запуске:
- Файл: `polymarket_notifier.db`
- Расположение: `/opt/polymarket-bot/polymarket_notifier.db`

## 🛠️ Управление ботом

### Остановить бота
```bash
# Если запущен вручную
pkill -f polymarket_notifier.py

# Если через systemd
sudo systemctl stop polymarket-bot
```

### Перезапустить бота
```bash
# Если через systemd
sudo systemctl restart polymarket-bot

# Если вручную
pkill -f polymarket_notifier.py
nohup python3 polymarket_notifier.py > polymarket_notifier.log 2>&1 &
```

### Обновить код с локальной машины
```bash
# На локальной машине
cd /Users/johnbravo/polymarket
./deploy_to_server.sh
```

## 📊 Мониторинг

### Проверить статус
```bash
ps aux | grep polymarket_notifier
```

### Просмотр логов
```bash
tail -f /opt/polymarket-bot/polymarket_notifier.log
```

### Статистика кошельков
```bash
cd /opt/polymarket-bot
python3 -c "from db import PolymarketDB; db = PolymarketDB(); wallets = db.get_all_wallets(); print(f'Всего кошельков: {len(wallets)}')"
```

## ✅ Готово!

После выполнения всех шагов бот должен работать на сервере 24/7.

---

**Последнее обновление**: 12 ноября 2025
**Версия**: с поддержкой ENABLE_PROXIES и utils/http_client.py

