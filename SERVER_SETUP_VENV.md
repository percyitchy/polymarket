# 🐍 Настройка виртуального окружения на сервере

## Проблема
Ubuntu 24.04+ использует "externally managed" Python окружение, которое не позволяет устанавливать пакеты напрямую через `pip3 install`.

## ✅ Решение: Виртуальное окружение

### 1. Создайте виртуальное окружение
```bash
cd /opt/polymarket-bot
python3 -m venv venv
```

### 2. Активируйте виртуальное окружение
```bash
source venv/bin/activate
```

После активации в начале строки появится `(venv)`.

### 3. Обновите pip
```bash
pip install --upgrade pip
```

### 4. Установите зависимости
```bash
pip install -r requirements.txt
```

### 5. Проверьте установку
```bash
python --version
pip list
```

## 🚀 Запуск бота с виртуальным окружением

### Вариант A: Ручной запуск
```bash
cd /opt/polymarket-bot
source venv/bin/activate
python polymarket_notifier.py
```

### Вариант B: Фоновый режим
```bash
cd /opt/polymarket-bot
source venv/bin/activate
nohup python polymarket_notifier.py > polymarket_notifier.log 2>&1 &
```

### Вариант C: Через systemd (с venv)

Отредактируйте service файл, чтобы использовать venv:

```bash
sudo nano /etc/systemd/system/polymarket-bot.service
```

Добавьте в `[Service]`:
```ini
WorkingDirectory=/opt/polymarket-bot
ExecStart=/opt/polymarket-bot/venv/bin/python /opt/polymarket-bot/polymarket_notifier.py
```

Или создайте wrapper скрипт:

```bash
# Создайте /opt/polymarket-bot/run_bot.sh
#!/bin/bash
cd /opt/polymarket-bot
source venv/bin/activate
exec python polymarket_notifier.py
```

Сделайте исполняемым:
```bash
chmod +x /opt/polymarket-bot/run_bot.sh
```

## 📝 Полезные команды

### Деактивировать venv
```bash
deactivate
```

### Проверить, активирован ли venv
```bash
which python
# Должно показать: /opt/polymarket-bot/venv/bin/python
```

### Установить новый пакет
```bash
source venv/bin/activate
pip install package_name
```

### Обновить все пакеты
```bash
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

## ⚠️ Важно

- Всегда активируйте venv перед запуском бота
- При обновлении кода не нужно пересоздавать venv
- Venv находится в `/opt/polymarket-bot/venv/` и не должен попадать в git

