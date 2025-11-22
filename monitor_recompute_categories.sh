#!/bin/bash
# Скрипт для мониторинга прогресса пересчёта категорий

echo "=========================================="
echo "📊 МОНИТОРИНГ ПЕРЕСЧЁТА КАТЕГОРИЙ"
echo "=========================================="
echo ""

# Проверка процесса
if pgrep -f "daily_wallet_analysis.py --recompute-all-categories" > /dev/null; then
    echo "✅ Процесс запущен"
    PID=$(pgrep -f "daily_wallet_analysis.py --recompute-all-categories")
    echo "   PID: $PID"
else
    echo "❌ Процесс не найден"
fi

echo ""

# Проверка лога
if [ -f "recompute_categories.log" ]; then
    echo "📝 Последние строки лога:"
    echo "----------------------------------------"
    tail -20 recompute_categories.log
    echo "----------------------------------------"
    echo ""
    echo "📊 Размер лога: $(du -h recompute_categories.log | cut -f1)"
    echo "📈 Строк в логе: $(wc -l < recompute_categories.log)"
else
    echo "⚠️  Лог-файл не найден"
fi

echo ""

# Проверка прогресса в базе данных
echo "📊 Текущая статистика Unknown:"
python3 << 'EOF'
from db import PolymarketDB
db = PolymarketDB()
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM wallet_category_stats WHERE category = 'other/Unknown'")
    unknown = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM wallet_category_stats")
    total = cursor.fetchone()[0]
    if total > 0:
        pct = (unknown / total * 100)
        print(f"   Unknown: {unknown:,} ({pct:.2f}%)")
        print(f"   Всего: {total:,}")
    else:
        print("   База данных пуста")
EOF

echo ""
echo "=========================================="
echo "💡 Для просмотра лога в реальном времени:"
echo "   tail -f recompute_categories.log"
echo "=========================================="

