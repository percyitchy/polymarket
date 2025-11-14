#!/bin/bash
# Скрипт для запуска бота с виртуальным окружением

cd "$(dirname "$0")"

# Активируем виртуальное окружение
if [ ! -d "venv" ]; then
    echo "❌ Виртуальное окружение не найдено!"
    echo "Создайте его командой: python3 -m venv venv"
    exit 1
fi

source venv/bin/activate

# Запускаем бота
exec python polymarket_notifier.py

