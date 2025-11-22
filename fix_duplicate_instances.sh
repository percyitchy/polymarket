#!/bin/bash
# Скрипт для остановки всех инстанций бота и запуска только одной правильной

echo "🔧 Исправление дублирующихся инстанций бота"
echo "=========================================="
echo ""

# Найти все процессы
echo "📊 Найденные процессы:"
ps aux | grep "[p]olymarket_notifier.py"
echo ""

# Остановить systemd сервис (если есть)
if systemctl list-units --type=service --all 2>/dev/null | grep -q "polymarket-bot.service"; then
    echo "🛑 Останавливаю systemd сервис..."
    sudo systemctl stop polymarket-bot.service 2>/dev/null || true
    echo "✅ Systemd сервис остановлен"
else
    echo "ℹ️  Systemd сервис не найден"
fi
echo ""

# Остановить все процессы polymarket_notifier
echo "🛑 Останавливаю все процессы polymarket_notifier.py..."
PIDS=$(pgrep -f "polymarket_notifier.py" 2>/dev/null)
if [ -n "$PIDS" ]; then
    for pid in $PIDS; do
        echo "   Останавливаю PID: $pid"
        kill -TERM $pid 2>/dev/null || true
    done
    
    # Подождать немного
    sleep 3
    
    # Проверить что процессы остановились
    REMAINING=$(pgrep -f "polymarket_notifier.py" 2>/dev/null)
    if [ -n "$REMAINING" ]; then
        echo "⚠️  Некоторые процессы не остановились, принудительно завершаю..."
        for pid in $REMAINING; do
            kill -9 $pid 2>/dev/null || true
        done
    fi
    echo "✅ Все процессы остановлены"
else
    echo "ℹ️  Процессы не найдены"
fi
echo ""

# Проверка что ничего не осталось
echo "🔍 Проверка что все остановлено:"
REMAINING=$(pgrep -f "polymarket_notifier.py" 2>/dev/null)
if [ -z "$REMAINING" ]; then
    echo "✅ Все процессы остановлены"
else
    echo "⚠️  Остались процессы: $REMAINING"
    echo "   Попробуйте вручную: kill -9 $REMAINING"
fi
echo ""

# Определить правильную директорию для запуска
if [ -f "/opt/polymarket-bot/polymarket_notifier.py" ]; then
    CORRECT_DIR="/opt/polymarket-bot"
    echo "✅ Найдена правильная директория: $CORRECT_DIR"
elif [ -f "/home/ubuntu/polymarket/polymarket_notifier.py" ]; then
    CORRECT_DIR="/home/ubuntu/polymarket"
    echo "✅ Найдена директория: $CORRECT_DIR"
else
    echo "❌ Не найдена директория с ботом!"
    exit 1
fi
echo ""

# Предложить запуск
echo "📋 Следующие шаги:"
echo "=================="
echo ""
echo "1. Проверьте что все процессы остановлены:"
echo "   ps aux | grep '[p]olymarket_notifier.py'"
echo ""
echo "2. Запустите бота правильно:"
if [ -f "/etc/systemd/system/polymarket-bot.service" ]; then
    echo "   sudo systemctl start polymarket-bot"
    echo "   sudo systemctl status polymarket-bot"
else
    echo "   cd $CORRECT_DIR"
    echo "   # Если есть systemd сервис, настройте его"
    echo "   # Или запустите вручную (не рекомендуется для продакшена)"
fi
echo ""
echo "3. Проверьте что запущена только 1 инстанция:"
echo "   ps aux | grep '[p]olymarket_notifier.py' | wc -l"
echo "   # Должно быть: 1"
echo ""

