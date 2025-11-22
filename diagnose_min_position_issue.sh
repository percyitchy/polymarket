#!/bin/bash
# Диагностика проблемы с MIN_TOTAL_POSITION_USD

echo "🔍 Диагностика проблемы с минимальным порогом позиции"
echo "====================================================="
echo ""

# Проверка на сервере
echo "📋 Выполните эти команды на сервере:"
echo ""
echo "1️⃣  Проверка значения MIN_TOTAL_POSITION_USD в .env:"
echo "   grep MIN_TOTAL_POSITION_USD /opt/polymarket-bot/.env"
echo ""

echo "2️⃣  Проверка что значение загружено в процесс:"
echo "   sudo journalctl -u polymarket-bot -n 200 | grep 'MIN_TOTAL_POSITION_USD'"
echo "   Должно быть: [Config] MIN_TOTAL_POSITION_USD=\$2000"
echo ""

echo "3️⃣  Проверка логов для последних сигналов:"
echo "   sudo journalctl -u polymarket-bot --since '1 hour ago' | grep -E '(Step 10|MIN_TOTAL_POSITION_USD|Insufficient total position)'"
echo ""

echo "4️⃣  Проверка что сервис перезапущен:"
echo "   sudo systemctl status polymarket-bot | grep 'Active:'"
echo "   Должно быть: Active: active (running)"
echo ""

echo "5️⃣  Проверка времени последнего перезапуска:"
echo "   sudo systemctl show polymarket-bot -p ActiveEnterTimestamp"
echo ""

echo "6️⃣  Проверка базы данных на старые алерты:"
echo "   sqlite3 /opt/polymarket-bot/polymarket_notifier.db \"SELECT condition_id, outcome_index, side, total_usd, first_total_usd, sent_at FROM alerts_sent ORDER BY sent_at DESC LIMIT 10;\""
echo ""

echo "💡 Возможные причины:"
echo "===================="
echo ""
echo "1. ❌ Переменная MIN_TOTAL_POSITION_USD не установлена в .env"
echo "   Решение: Добавьте MIN_TOTAL_POSITION_USD=2000 в .env и перезапустите"
echo ""
echo "2. ❌ Сервис не был перезапущен после изменения .env"
echo "   Решение: sudo systemctl restart polymarket-bot"
echo ""
echo "3. ⚠️  Старые алерты в БД без first_total_usd"
echo "   Если первый алерт был отправлен до установки порога,"
echo "   последующие могут проходить как 'repeat alerts'"
echo ""
echo "4. ⚠️  Логика repeat alert обходит проверку"
echo "   Если total_usd >= 2 * first_total_usd, сигнал проходит"
echo "   даже если он меньше MIN_TOTAL_POSITION_USD"
echo ""

