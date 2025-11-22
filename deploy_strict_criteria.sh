#!/bin/bash

# Скрипт для загрузки обновлений строгих критериев на сервер
# Usage: ./deploy_strict_criteria.sh

SERVER="YOUR_SERVER_IP"
USER="ubuntu"
REMOTE_DIR="/opt/polymarket-bot"

# Проверяем, существует ли альтернативный путь
if [ -z "$REMOTE_DIR" ]; then
    REMOTE_DIR="~/polymarket"
fi

echo "=" | tr -d '\n' | head -c 70
echo ""
echo "📤 ЗАГРУЗКА ОБНОВЛЕНИЙ СТРОГИХ КРИТЕРИЕВ НА СЕРВЕР"
echo "=" | tr -d '\n' | head -c 70
echo ""
echo ""

# Файлы для загрузки (обновленные для строгих критериев)
FILES=(
    "db.py"
    "wallet_analyzer.py"
    "polymarket_notifier.py"
    "reanalyze_completed_wallets.py"
)

# Проверяем наличие файлов
MISSING_FILES=()
for file in "${FILES[@]}"; do
    if [ ! -f "$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo "❌ Отсутствуют файлы:"
    for file in "${MISSING_FILES[@]}"; do
        echo "   - $file"
    done
    exit 1
fi

# Загружаем каждый файл
UPLOADED=0
FAILED=0

for file in "${FILES[@]}"; do
    echo "📁 Загружаю $file..."
    scp "$file" "$USER@$SERVER:$REMOTE_DIR/"
    if [ $? -eq 0 ]; then
        echo "   ✅ $file загружен успешно"
        UPLOADED=$((UPLOADED + 1))
    else
        echo "   ❌ Ошибка при загрузке $file"
        FAILED=$((FAILED + 1))
    fi
    echo ""
done

echo "=" | tr -d '\n' | head -c 70
echo ""
echo "📊 РЕЗУЛЬТАТЫ ЗАГРУЗКИ:"
echo "=" | tr -d '\n' | head -c 70
echo ""
echo "   ✅ Загружено успешно: $UPLOADED"
echo "   ❌ Ошибок: $FAILED"
echo ""

if [ $FAILED -gt 0 ]; then
    echo "⚠️  Некоторые файлы не были загружены!"
    exit 1
fi

echo "🔄 Следующие шаги на сервере:"
echo ""
echo "1. Подключитесь к серверу:"
echo "   ssh $USER@$SERVER"
echo ""
echo "2. Перейдите в директорию проекта:"
echo "   cd $REMOTE_DIR"
echo ""
echo "3. Запустите переанализ кошельков (опционально):"
echo "   python3 reanalyze_completed_wallets.py"
echo ""
echo "4. Перезапустите сервисы:"
echo "   sudo systemctl restart polymarket-bot.service"
echo ""
echo "5. Проверьте статус:"
echo "   sudo systemctl status polymarket-bot.service"
echo ""
echo "=" | tr -d '\n' | head -c 70
echo ""
echo "✅ Загрузка завершена!"
echo "=" | tr -d '\n' | head -c 70
echo ""

