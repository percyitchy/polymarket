#!/bin/bash
# Скрипт для загрузки бота на сервер

SERVER="ubuntu@YOUR_SERVER_IP"
REMOTE_DIR="/opt/polymarket-bot"
LOCAL_DIR="/Users/johnbravo/polymarket"

echo "=========================================="
echo "🚀 Загрузка Polymarket Bot на сервер"
echo "=========================================="
echo "Сервер: $SERVER"
echo "Удаленная директория: $REMOTE_DIR"
echo ""

# Проверка подключения
echo "📡 Проверка подключения к серверу..."
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes $SERVER "echo 'OK'" 2>/dev/null; then
    echo "❌ Не удалось подключиться к серверу"
    echo "Проверьте SSH ключи и доступность сервера"
    exit 1
fi
echo "✅ Подключение установлено"
echo ""

# Создание директории на сервере
echo "📁 Создание директории на сервере..."
ssh $SERVER "sudo mkdir -p $REMOTE_DIR && sudo chown ubuntu:ubuntu $REMOTE_DIR"
echo "✅ Директория создана"
echo ""

# Синхронизация файлов (исключая ненужное)
echo "📦 Синхронизация файлов..."
rsync -avz --progress \
    --exclude='.env' \
    --exclude='.env.*' \
    --exclude='*.db' \
    --exclude='*.db-*' \
    --exclude='*.log' \
    --exclude='*.out' \
    --exclude='*.err' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.git/' \
    --exclude='.DS_Store' \
    --exclude='*.xls' \
    --exclude='*.xlsx' \
    --exclude='*.csv' \
    --exclude='archive_*/' \
    --exclude='debug_*/' \
    --exclude='*.png' \
    --exclude='*.html' \
    --exclude='venv/' \
    --exclude='.venv/' \
    "$LOCAL_DIR/" "$SERVER:$REMOTE_DIR/"

if [ $? -eq 0 ]; then
    echo "✅ Файлы загружены успешно"
else
    echo "❌ Ошибка при загрузке файлов"
    exit 1
fi
echo ""

# Копирование .env.example как шаблон (если .env нет на сервере)
echo "📝 Проверка .env файла..."
if ssh $SERVER "test ! -f $REMOTE_DIR/.env"; then
    echo "⚠️  .env файл не найден на сервере"
    echo "Создаю .env из .env.example..."
    ssh $SERVER "cd $REMOTE_DIR && cp env.example .env 2>/dev/null || echo '# Создайте .env файл вручную' > .env"
    echo "✅ Шаблон .env создан"
    echo "⚠️  ВАЖНО: Отредактируйте .env на сервере с вашими настройками!"
else
    echo "✅ .env файл уже существует на сервере"
fi
echo ""

# Установка прав на исполняемые файлы
echo "🔧 Установка прав на исполняемые файлы..."
ssh $SERVER "cd $REMOTE_DIR && chmod +x *.sh *.py 2>/dev/null || true"
echo "✅ Права установлены"
echo ""

# Проверка requirements.txt
echo "📋 Проверка зависимостей..."
if ssh $SERVER "test -f $REMOTE_DIR/requirements.txt"; then
    echo "✅ requirements.txt найден"
    echo "💡 На сервере выполните: pip3 install -r requirements.txt"
else
    echo "⚠️  requirements.txt не найден"
fi
echo ""

echo "=========================================="
echo "✅ Загрузка завершена!"
echo "=========================================="
echo ""
echo "📝 Следующие шаги на сервере:"
echo "1. Подключитесь: ssh -l ubuntu YOUR_SERVER_IP"
echo "2. Перейдите: cd $REMOTE_DIR"
echo "3. Отредактируйте .env файл с вашими настройками"
echo "4. Установите зависимости: pip3 install -r requirements.txt"
echo "5. Настройте systemd сервисы (если нужно)"
echo ""

