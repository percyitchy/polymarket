#!/bin/bash
# Скрипт для проверки инстанций на сервере (выполнять через SSH)

echo "🔍 Проверка инстанций бота на СЕРВЕРЕ"
echo "====================================="
echo ""
echo "⚠️  ВНИМАНИЕ: Этот скрипт нужно выполнять на СЕРВЕРЕ через SSH!"
echo ""
echo "Для подключения к серверу выполните:"
echo "  ssh ubuntu@YOUR_SERVER_IP"
echo ""
echo "Затем на сервере выполните команды ниже:"
echo ""
echo "=========================================="
echo ""

# Команды для выполнения на сервере
cat << 'EOF'
# 1. Проверка всех процессов polymarket_notifier
echo "📊 Все процессы polymarket_notifier.py:"
ps aux | grep "[p]olymarket_notifier.py"
echo ""

# 2. Подсчет количества процессов
PROCESS_COUNT=$(ps aux | grep "[p]olymarket_notifier.py" | wc -l)
echo "Количество процессов: $PROCESS_COUNT"
echo ""

# 3. Проверка systemd сервиса
echo "⚙️  Статус systemd сервиса:"
if systemctl list-units --type=service --all 2>/dev/null | grep -q "polymarket-bot.service"; then
    sudo systemctl status polymarket-bot.service --no-pager -l | head -n 15
else
    echo "❌ polymarket-bot.service не найден"
fi
echo ""

# 4. Проверка PID процессов
echo "🔢 PID процессов:"
pgrep -f "polymarket_notifier.py" || echo "Процессы не найдены"
echo ""

# 5. Проверка директорий
echo "📁 Директории процессов:"
ps aux | grep "[p]olymarket_notifier.py" | awk '{print $11}' | sort | uniq
echo ""

# 6. Рекомендации
PROCESS_COUNT=$(ps aux | grep "[p]olymarket_notifier.py" | wc -l)
if [ "$PROCESS_COUNT" -eq 0 ]; then
    echo "✅ Нет запущенных процессов (бот остановлен)"
elif [ "$PROCESS_COUNT" -eq 1 ]; then
    echo "✅ Бот запущен в 1 инстанции (нормально)"
else
    echo "⚠️  ПРОБЛЕМА: Бот запущен в $PROCESS_COUNT инстанциях!"
    echo "   Это может вызывать дублирование сигналов!"
    echo ""
    echo "   Для исправления выполните:"
    echo "   sudo systemctl stop polymarket-bot"
    echo "   pkill -f polymarket_notifier.py"
    echo "   sudo systemctl start polymarket-bot"
fi
EOF

echo ""
echo "=========================================="
echo ""
echo "💡 Быстрая команда для копирования на сервер:"
echo ""
echo "ssh ubuntu@YOUR_SERVER_IP 'ps aux | grep \"[p]olymarket_notifier.py\"; echo \"---\"; pgrep -f \"polymarket_notifier.py\" | wc -l'"

