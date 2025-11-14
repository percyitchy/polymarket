#!/bin/bash
# Test script for daily scripts
# Tests both daily_wallet_analysis.py and daily_report.py

set -e

echo "=========================================="
echo "Testing Daily Scripts"
echo "=========================================="

cd /opt/polymarket-bot
source venv/bin/activate

echo ""
echo "1. Testing daily_report.py..."
echo "----------------------------------------"
python3 daily_report.py --date=today
echo ""
echo "✅ daily_report.py completed"
echo ""

echo "2. Testing daily_wallet_analysis.py (with 60s timeout)..."
echo "----------------------------------------"
timeout 60 python3 daily_wallet_analysis.py 2>&1 | tail -50 || echo "⚠️ Script timed out after 60s (this is expected if collection takes longer)"
echo ""

echo "3. Checking queue status..."
echo "----------------------------------------"
python3 -c "
from db import PolymarketDB
db = PolymarketDB('polymarket_notifier.db')
stats = db.get_queue_stats()
print(f'Queue status:')
print(f'  Pending: {stats.get(\"pending_jobs\", 0)}')
print(f'  Processing: {stats.get(\"processing_jobs\", 0)}')
print(f'  Completed: {stats.get(\"completed_jobs\", 0)}')
print(f'  Failed: {stats.get(\"failed_jobs\", 0)}')
print(f'  Total: {stats.get(\"total_jobs\", 0)}')
"

echo ""
echo "=========================================="
echo "Test complete"
echo "=========================================="
echo ""
echo "Check Telegram for messages:"
echo "  - Daily report should be sent"
echo "  - Daily analysis summary (if completed)"
echo ""

