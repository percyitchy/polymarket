#!/bin/bash
# Скрипт для добавления MIN_TOTAL_POSITION_USD в .env файл на сервере

ENV_FILE="/opt/polymarket-bot/.env"
BACKUP_FILE="${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"

echo "=========================================="
echo "🔧 Добавление MIN_TOTAL_POSITION_USD в .env"
echo "=========================================="
echo ""

# Проверка существования файла
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Ошибка: Файл $ENV_FILE не найден!"
    exit 1
fi

# Создание резервной копии
echo "📋 Создание резервной копии..."
cp "$ENV_FILE" "$BACKUP_FILE"
echo "✅ Резервная копия создана: $BACKUP_FILE"
echo ""

# Проверка, существует ли уже переменная
if grep -q "^MIN_TOTAL_POSITION_USD=" "$ENV_FILE"; then
    echo "⚠️  Переменная MIN_TOTAL_POSITION_USD уже существует в .env"
    echo "📝 Обновляю значение до 2000..."
    
    # Обновляем существующее значение
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' 's/^MIN_TOTAL_POSITION_USD=.*/MIN_TOTAL_POSITION_USD=2000/' "$ENV_FILE"
    else
        # Linux
        sed -i 's/^MIN_TOTAL_POSITION_USD=.*/MIN_TOTAL_POSITION_USD=2000/' "$ENV_FILE"
    fi
    echo "✅ Значение обновлено"
else
    echo "➕ Добавляю MIN_TOTAL_POSITION_USD=2000 в секцию Monitoring Configuration..."
    
    # Ищем секцию "# Monitoring Configuration"
    if grep -q "# Monitoring Configuration" "$ENV_FILE"; then
        # Добавляем после MIN_CONSENSUS или MAX_WALLETS
        if grep -q "^MIN_CONSENSUS=" "$ENV_FILE"; then
            # Добавляем после MIN_CONSENSUS
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                sed -i '' '/^MIN_CONSENSUS=/a\
MIN_TOTAL_POSITION_USD=2000            # Minimum total position size in USDC to send alert' "$ENV_FILE"
            else
                # Linux
                sed -i '/^MIN_CONSENSUS=/a MIN_TOTAL_POSITION_USD=2000            # Minimum total position size in USDC to send alert' "$ENV_FILE"
            fi
        elif grep -q "^MAX_WALLETS=" "$ENV_FILE"; then
            # Добавляем перед MAX_WALLETS
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                sed -i '' '/^MAX_WALLETS=/i\
MIN_TOTAL_POSITION_USD=2000            # Minimum total position size in USDC to send alert' "$ENV_FILE"
            else
                # Linux
                sed -i '/^MAX_WALLETS=/i MIN_TOTAL_POSITION_USD=2000            # Minimum total position size in USDC to send alert' "$ENV_FILE"
            fi
        else
            # Добавляем в конец секции Monitoring Configuration
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                sed -i '' '/# Monitoring Configuration/,/^$/a\
MIN_TOTAL_POSITION_USD=2000            # Minimum total position size in USDC to send alert' "$ENV_FILE"
            else
                # Linux
                sed -i '/# Monitoring Configuration/,/^$/a MIN_TOTAL_POSITION_USD=2000            # Minimum total position size in USDC to send alert' "$ENV_FILE"
            fi
        fi
        echo "✅ Переменная добавлена"
    else
        # Если секции нет, добавляем в начало файла
        echo "" >> "$ENV_FILE"
        echo "# Monitoring Configuration" >> "$ENV_FILE"
        echo "MIN_TOTAL_POSITION_USD=2000            # Minimum total position size in USDC to send alert" >> "$ENV_FILE"
        echo "✅ Секция и переменная добавлены"
    fi
fi

echo ""
echo "=========================================="
echo "✅ Готово!"
echo "=========================================="
echo ""
echo "📋 Проверка добавленной переменной:"
grep "^MIN_TOTAL_POSITION_USD=" "$ENV_FILE" || echo "⚠️  Переменная не найдена (проверьте файл вручную)"
echo ""
echo "📝 Следующий шаг: перезапустите сервис"
echo "   sudo systemctl restart polymarket-bot"
echo ""

