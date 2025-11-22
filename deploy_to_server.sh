#!/bin/bash
# Скрипт для развертывания обновлений на сервере

echo "=========================================="
echo "Развертывание исправлений на сервере"
echo "=========================================="

# Настройки (измените под ваш сервер)
SERVER_USER="your_user"
SERVER_HOST="your_server_ip"
SERVER_PATH="/opt/polymarket-bot"
LOCAL_FILE="polymarket_notifier.py"

echo ""
echo "1. Проверка локального файла..."
if [ ! -f "$LOCAL_FILE" ]; then
    echo "❌ Файл $LOCAL_FILE не найден!"
    exit 1
fi
echo "✅ Файл найден"

echo ""
echo "2. Копирование файла на сервер..."
echo "   Команда: scp $LOCAL_FILE $SERVER_USER@$SERVER_HOST:$SERVER_PATH/"
read -p "Продолжить? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Отменено"
    exit 1
fi

scp "$LOCAL_FILE" "$SERVER_USER@$SERVER_HOST:$SERVER_PATH/"

if [ $? -eq 0 ]; then
    echo "✅ Файл скопирован"
else
    echo "❌ Ошибка копирования файла"
    exit 1
fi

echo ""
echo "3. Перезапуск бота на сервере..."
echo "   Команда: ssh $SERVER_USER@$SERVER_HOST 'sudo systemctl restart polymarket-bot'"
read -p "Продолжить? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Отменено"
    exit 1
fi

ssh "$SERVER_USER@$SERVER_HOST" "sudo systemctl restart polymarket-bot.service"

if [ $? -eq 0 ]; then
    echo "✅ Бот перезапущен"
else
    echo "❌ Ошибка перезапуска бота"
    exit 1
fi

echo ""
echo "4. Проверка статуса бота..."
ssh "$SERVER_USER@$SERVER_HOST" "sudo systemctl status polymarket-bot.service --no-pager | head -10"

echo ""
echo "=========================================="
echo "Развертывание завершено!"
echo "=========================================="
echo ""
echo "Проверьте логи на сервере:"
echo "  ssh $SERVER_USER@$SERVER_HOST 'tail -50 $SERVER_PATH/polymarket_notifier.log'"
