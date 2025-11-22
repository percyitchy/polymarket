#!/bin/bash
# Скрипт для проверки сколько инстанций бота запущено

echo "🔍 Проверка запущенных инстанций Polymarket бота"
echo "================================================"
echo ""

# Проверка процессов Python с polymarket_notifier
echo "📊 Процессы Python с polymarket_notifier.py:"
ps aux | grep "[p]olymarket_notifier.py" | wc -l | xargs echo "   Количество:"
ps aux | grep "[p]olymarket_notifier.py" || echo "   Нет запущенных процессов"
echo ""

# Проверка systemd сервисов
echo "⚙️  Systemd сервисы:"
if systemctl list-units --type=service --all 2>/dev/null | grep -q "polymarket-bot.service"; then
    echo "   ✅ polymarket-bot.service найден"
    systemctl status polymarket-bot.service --no-pager -l 2>/dev/null | head -n 15 || echo "   ⚠️  Не удалось получить статус"
else
    echo "   ❌ polymarket-bot.service не найден"
fi
echo ""

# Проверка процессов через pgrep
echo "🔎 Детальная информация о процессах:"
POLYMARKET_PIDS=$(pgrep -f "polymarket_notifier.py" 2>/dev/null)
if [ -z "$POLYMARKET_PIDS" ]; then
    echo "   ❌ Нет запущенных процессов polymarket_notifier.py"
else
    echo "   Найдено процессов: $(echo $POLYMARKET_PIDS | wc -w)"
    for pid in $POLYMARKET_PIDS; do
        echo ""
        echo "   PID: $pid"
        ps -p $pid -o pid,ppid,user,cmd,etime,start 2>/dev/null || echo "   Процесс не найден"
    done
fi
echo ""

# Проверка systemd таймеров
echo "⏰ Systemd таймеры:"
systemctl list-timers polymarket-*.timer --no-pager 2>/dev/null || echo "   Нет активных таймеров"
echo ""

# Проверка портов (если бот использует порты)
echo "🌐 Проверка сетевых подключений:"
netstat -tulpn 2>/dev/null | grep -i python || echo "   Нет активных сетевых подключений Python"
echo ""

# Проверка .env файла
echo "📝 Информация о .env файле:"
if [ -f "/opt/polymarket-bot/.env" ]; then
    echo "   ✅ Файл существует: /opt/polymarket-bot/.env"
    echo "   Последнее изменение: $(stat -c %y /opt/polymarket-bot/.env 2>/dev/null || stat -f %Sm /opt/polymarket-bot/.env 2>/dev/null)"
else
    echo "   ⚠️  Файл не найден: /opt/polymarket-bot/.env"
fi
echo ""

# Итоговая сводка
echo "📋 ИТОГОВАЯ СВОДКА:"
echo "==================="
PROCESS_COUNT=$(ps aux | grep "[p]olymarket_notifier.py" | wc -l)
if [ "$PROCESS_COUNT" -eq 0 ]; then
    echo "   ❌ Бот НЕ запущен"
elif [ "$PROCESS_COUNT" -eq 1 ]; then
    echo "   ✅ Бот запущен в 1 инстанции (нормально)"
else
    echo "   ⚠️  Бот запущен в $PROCESS_COUNT инстанциях (возможна проблема!)"
fi

if systemctl is-active --quiet polymarket-bot.service 2>/dev/null; then
    echo "   ✅ Systemd сервис активен"
else
    echo "   ⚠️  Systemd сервис не активен (возможно запущен вручную)"
fi
echo ""

echo "💡 Рекомендации:"
echo "   - Если бот запущен в нескольких инстанциях, остановите лишние:"
echo "     sudo systemctl stop polymarket-bot"
echo "     pkill -f polymarket_notifier.py"
echo "   - После изменения .env файла перезапустите сервис:"
echo "     sudo systemctl restart polymarket-bot"
echo "   - Или используйте скрипт: ./restart_services.sh"

