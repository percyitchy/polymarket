#!/bin/bash
# Скрипт для поиска что запускает бота автоматически

echo "🔍 Поиск автоматических запусков бота"
echo "====================================="
echo ""

# Проверка systemd сервисов
echo "1️⃣  Проверка systemd сервисов:"
echo "----------------------------"
systemctl list-units --type=service --all | grep -i polymarket || echo "   Не найдено"
echo ""

# Проверка systemd таймеров
echo "2️⃣  Проверка systemd таймеров:"
echo "----------------------------"
systemctl list-timers --all | grep -i polymarket || echo "   Не найдено"
echo ""

# Проверка cron jobs
echo "3️⃣  Проверка cron jobs:"
echo "---------------------"
crontab -l 2>/dev/null | grep -i polymarket || echo "   Нет в crontab текущего пользователя"
sudo crontab -l 2>/dev/null | grep -i polymarket || echo "   Нет в root crontab"
echo ""

# Проверка systemd timers
echo "4️⃣  Проверка всех systemd timers:"
echo "--------------------------------"
systemctl list-timers --all | head -20
echo ""

# Проверка автозапуска в .bashrc/.profile
echo "5️⃣  Проверка автозапуска в shell конфигах:"
echo "-------------------------------------------"
if [ -f ~/.bashrc ]; then
    echo "   Проверка ~/.bashrc:"
    grep -i "polymarket\|nohup\|screen\|tmux" ~/.bashrc || echo "   Не найдено"
fi
if [ -f ~/.profile ]; then
    echo "   Проверка ~/.profile:"
    grep -i "polymarket\|nohup\|screen\|tmux" ~/.profile || echo "   Не найдено"
fi
if [ -f ~/.bash_profile ]; then
    echo "   Проверка ~/.bash_profile:"
    grep -i "polymarket\|nohup\|screen\|tmux" ~/.bash_profile || echo "   Не найдено"
fi
echo ""

# Проверка systemd user units
echo "6️⃣  Проверка systemd user units:"
echo "-------------------------------"
systemctl --user list-units --all 2>/dev/null | grep -i polymarket || echo "   Не найдено"
echo ""

# Проверка процессов и их родительских процессов
echo "7️⃣  Проверка родительских процессов:"
echo "------------------------------------"
PIDS=$(pgrep -f "polymarket_notifier.py" 2>/dev/null)
if [ -n "$PIDS" ]; then
    for pid in $PIDS; do
        echo "   PID $pid:"
        ps -p $pid -o pid,ppid,cmd,etime
        PPID=$(ps -p $pid -o ppid= | tr -d ' ')
        if [ -n "$PPID" ] && [ "$PPID" != "1" ]; then
            echo "   Родительский процесс (PPID $PPID):"
            ps -p $PPID -o pid,cmd,etime 2>/dev/null || echo "   Родительский процесс не найден"
        fi
        echo ""
    done
else
    echo "   Процессы не найдены"
fi
echo ""

# Проверка systemd unit файлов
echo "8️⃣  Проверка systemd unit файлов:"
echo "--------------------------------"
find /etc/systemd/system /lib/systemd/system ~/.config/systemd/user 2>/dev/null -name "*polymarket*" -o -name "*bot*" | head -10
echo ""

# Проверка screen/tmux сессий
echo "9️⃣  Проверка screen/tmux сессий:"
echo "-------------------------------"
screen -ls 2>/dev/null | grep -i polymarket || echo "   Нет screen сессий"
tmux ls 2>/dev/null | grep -i polymarket || echo "   Нет tmux сессий"
echo ""

echo "✅ Проверка завершена"
echo ""
echo "💡 Рекомендации:"
echo "   - Если найдены дублирующиеся сервисы/timers, отключите их:"
echo "     sudo systemctl disable <service-name>"
echo "     sudo systemctl stop <service-name>"
echo "   - Если процесс запускается из /home/ubuntu/polymarket/,"
echo "     проверьте что там нет systemd сервиса или cron job"

