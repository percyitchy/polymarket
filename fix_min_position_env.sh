#!/bin/bash
# Скрипт для исправления MIN_TOTAL_POSITION_USD в .env на сервере

echo "🔧 Исправление MIN_TOTAL_POSITION_USD в .env"
echo "==========================================="
echo ""

ENV_FILE="/opt/polymarket-bot/.env"

# Проверка что файл существует
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Файл $ENV_FILE не найден!"
    exit 1
fi

echo "📝 Текущее значение:"
grep MIN_TOTAL_POSITION_USD "$ENV_FILE" || echo "   Переменная не найдена"

echo ""
echo "🔧 Обновляю значение на 2000..."

# Обновить значение (работает на Linux и macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' 's/^MIN_TOTAL_POSITION_USD=.*/MIN_TOTAL_POSITION_USD=2000/' "$ENV_FILE"
else
    # Linux
    sed -i 's/^MIN_TOTAL_POSITION_USD=.*/MIN_TOTAL_POSITION_USD=2000/' "$ENV_FILE"
fi

echo "✅ Значение обновлено"
echo ""
echo "📝 Новое значение:"
grep MIN_TOTAL_POSITION_USD "$ENV_FILE"

echo ""
echo "🔄 Перезапускаю сервис..."
sudo systemctl restart polymarket-bot.service

echo ""
echo "⏳ Жду 3 секунды..."
sleep 3

echo ""
echo "✅ Проверка что значение загружено:"
sudo journalctl -u polymarket-bot -n 50 | grep "MIN_TOTAL_POSITION_USD" || echo "   Не найдено в логах (возможно еще не загрузилось)"

echo ""
echo "📊 Статус сервиса:"
sudo systemctl status polymarket-bot.service --no-pager -l | head -n 15

echo ""
echo "✅ Готово! Теперь сигналы с total_usd < \$2000 будут блокироваться."

