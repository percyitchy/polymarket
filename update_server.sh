#!/bin/bash

# Upload updated files to server and restart services
# Usage: ./update_server.sh

SERVER="YOUR_SERVER_IP"
USER="ubuntu"
REMOTE_DIR="/opt/polymarket-bot"

echo "📤 Загружаю обновленные файлы на сервер..."

# Files to upload (only the ones we modified)
FILES=(
    "polymarket_notifier.py"
    "notify.py"
)

# Upload each file
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "📁 Загружаю $file..."
        scp "$file" "$USER@$SERVER:$REMOTE_DIR/"
        if [ $? -eq 0 ]; then
            echo "✅ $file загружен успешно"
        else
            echo "❌ Ошибка при загрузке $file"
            exit 1
        fi
    else
        echo "⚠️  Файл $file не найден, пропускаю..."
    fi
done

echo ""
echo "🔄 Перезапускаю сервисы на сервере..."

# Restart services on server
ssh "$USER@$SERVER" "cd $REMOTE_DIR && sudo systemctl restart polymarket-bot.service && sudo systemctl status polymarket-bot.service --no-pager -l | head -n 15"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Обновление завершено успешно!"
    echo ""
    echo "📊 Проверка статуса:"
    ssh "$USER@$SERVER" "sudo systemctl status polymarket-bot.service --no-pager | head -n 10"
else
    echo "❌ Ошибка при перезапуске сервисов"
    exit 1
fi

