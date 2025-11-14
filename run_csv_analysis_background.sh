#!/bin/bash
# Запуск анализа CSV в фоновом режиме с логированием

CSV_FILE="/Users/johnbravo/Downloads/filtered_wallets_subset (1).csv"
LOG_FILE="/Users/johnbravo/polymarket/csv_analysis.log"
SCRIPT_DIR="/Users/johnbravo/polymarket"

cd "$SCRIPT_DIR"

echo "🚀 Запуск анализа CSV в фоновом режиме..."
echo "Логи: $LOG_FILE"

nohup python3 analyze_csv_wallets.py "$CSV_FILE" > "$LOG_FILE" 2>&1 &

PID=$!
echo "✅ Процесс запущен с PID: $PID"
echo ""
echo "Для мониторинга:"
echo "  tail -f $LOG_FILE"
echo ""
echo "Для остановки:"
echo "  kill $PID"


