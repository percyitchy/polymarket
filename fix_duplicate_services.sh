#!/bin/bash
# Скрипт для исправления дублирующихся systemd сервисов

echo "🔧 Исправление дублирующихся systemd сервисов"
echo "============================================="
echo ""

# Проверка содержимого сервисов
echo "1️⃣  Проверка содержимого polymarket-notifier.service:"
echo "---------------------------------------------------"
sudo cat /etc/systemd/system/polymarket-notifier.service
echo ""

echo "2️⃣  Проверка содержимого polymarket-bot.service:"
echo "----------------------------------------------"
sudo cat /etc/systemd/system/polymarket-bot.service
echo ""

# Остановка и отключение старого сервиса
echo "3️⃣  Остановка и отключение polymarket-notifier.service:"
echo "------------------------------------------------------"
sudo systemctl stop polymarket-notifier.service
sudo systemctl disable polymarket-notifier.service
echo "✅ polymarket-notifier.service остановлен и отключен"
echo ""

# Остановка всех процессов
echo "4️⃣  Остановка всех процессов:"
echo "----------------------------"
sudo systemctl stop polymarket-bot.service
pkill -f polymarket_notifier.py
sleep 2
echo "✅ Все процессы остановлены"
echo ""

# Проверка что все остановлено
echo "5️⃣  Проверка что все остановлено:"
echo "--------------------------------"
REMAINING=$(pgrep -f "polymarket_notifier.py" 2>/dev/null)
if [ -z "$REMAINING" ]; then
    echo "✅ Все процессы остановлены"
else
    echo "⚠️  Остались процессы: $REMAINING"
    echo "   Принудительно завершаю..."
    sudo kill -9 $REMAINING 2>/dev/null
fi
echo ""

# Запуск только правильного сервиса
echo "6️⃣  Запуск только polymarket-bot.service:"
echo "----------------------------------------"
sudo systemctl start polymarket-bot.service
sleep 2
echo "✅ polymarket-bot.service запущен"
echo ""

# Финальная проверка
echo "7️⃣  Финальная проверка:"
echo "---------------------"
PROCESS_COUNT=$(ps aux | grep "[p]olymarket_notifier.py" | wc -l)
echo "Количество процессов: $PROCESS_COUNT"

if [ "$PROCESS_COUNT" -eq 1 ]; then
    echo "✅ УСПЕХ: Запущена только 1 инстанция!"
    ps aux | grep "[p]olymarket_notifier.py"
elif [ "$PROCESS_COUNT" -eq 0 ]; then
    echo "⚠️  Процессы не найдены (возможно еще запускаются)"
else
    echo "❌ ПРОБЛЕМА: Все еще запущено $PROCESS_COUNT инстанций"
    ps aux | grep "[p]olymarket_notifier.py"
fi
echo ""

# Проверка статуса сервисов
echo "8️⃣  Статус systemd сервисов:"
echo "---------------------------"
systemctl status polymarket-bot.service --no-pager -l | head -n 10
echo ""
systemctl status polymarket-notifier.service --no-pager -l | head -n 10 || echo "polymarket-notifier.service остановлен (хорошо)"
echo ""

echo "✅ Готово!"
echo ""
echo "💡 Рекомендации:"
echo "   - Если polymarket-notifier.service больше не нужен, можно удалить:"
echo "     sudo rm /etc/systemd/system/polymarket-notifier.service"
echo "     sudo systemctl daemon-reload"
echo "   - Проверьте что только polymarket-bot.service включен:"
echo "     sudo systemctl is-enabled polymarket-bot.service"
echo "     sudo systemctl is-enabled polymarket-notifier.service"

