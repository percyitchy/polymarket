#!/bin/bash
# Скрипт для проверки что MIN_TOTAL_POSITION_USD работает правильно

echo "✅ Проверка что MIN_TOTAL_POSITION_USD работает"
echo "=============================================="
echo ""

echo "1️⃣  Текущая конфигурация:"
grep MIN_TOTAL_POSITION_USD /opt/polymarket-bot/.env
echo ""

echo "2️⃣  Значение загружено в процесс:"
sudo journalctl -u polymarket-bot --since "$(sudo systemctl show polymarket-bot -p ActiveEnterTimestamp --value)" | grep "MIN_TOTAL_POSITION_USD"
echo ""

echo "3️⃣  Мониторинг блокировок (последние 30 минут):"
echo "   Ищем сигналы которые были заблокированы из-за недостаточного размера позиции..."
sudo journalctl -u polymarket-bot --since '30 minutes ago' | grep -E "(Step 10|Insufficient total position)" | tail -10
echo ""

echo "4️⃣  Проверка что сервис работает:"
sudo systemctl is-active polymarket-bot && echo "   ✅ Сервис активен" || echo "   ❌ Сервис не активен"
echo ""

echo "5️⃣  Мониторинг в реальном времени (нажмите Ctrl+C для выхода):"
echo "   Следующие сигналы с total_usd < \$2000 должны блокироваться..."
echo ""
sudo journalctl -u polymarket-bot -f | grep --line-buffered -E "(Step 10|Insufficient total position|total_usd.*<.*2000)"

