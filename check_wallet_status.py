#!/usr/bin/env python3
"""
Quick script to check current wallet tracking status
"""

import sqlite3
import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
if not os.path.isabs(db_path):
    db_path = os.path.abspath(db_path)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Total wallets
cursor.execute('SELECT COUNT(*) FROM wallets')
total_wallets = cursor.fetchone()[0]

# Tracked wallets (meeting criteria: >=6 trades, >=70% win rate, <=25 daily freq)
cursor.execute('''
    SELECT COUNT(*) FROM wallets 
    WHERE traded_total >= 6 
    AND win_rate >= 0.70
    AND (daily_trading_frequency IS NULL OR daily_trading_frequency <= 25.0)
''')
tracked_wallets = cursor.fetchone()[0]

# Win rate breakdown
cursor.execute('SELECT COUNT(*) FROM wallets WHERE win_rate >= 0.90')
wr_90plus = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM wallets WHERE win_rate >= 0.80 AND win_rate < 0.90')
wr_80_90 = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM wallets WHERE win_rate >= 0.70 AND win_rate < 0.80')
wr_70_80 = cursor.fetchone()[0]

# Average stats for tracked wallets
cursor.execute('''
    SELECT 
        AVG(traded_total),
        AVG(win_rate),
        AVG(realized_pnl_total),
        AVG(daily_trading_frequency)
    FROM wallets 
    WHERE traded_total >= 6 
    AND win_rate >= 0.70
    AND (daily_trading_frequency IS NULL OR daily_trading_frequency <= 25.0)
''')
avg_stats = cursor.fetchone()

print('=' * 70)
print('📊 Current Wallet Tracking Status')
print('=' * 70)
print(f'✅ Tracked wallets (meeting criteria): {tracked_wallets}')
print(f'📁 Total wallets in database: {total_wallets}')
print('')
print('Win Rate Distribution:')
print(f'  • 90%+ win rate: {wr_90plus}')
print(f'  • 80-90% win rate: {wr_80_90}')
print(f'  • 70-80% win rate: {wr_70_80}')
print('')
if avg_stats[0]:
    print('Average Stats (Tracked Wallets):')
    print(f'  • Avg trades: {avg_stats[0]:.1f}')
    print(f'  • Avg win rate: {avg_stats[1]:.1%}')
    print(f'  • Avg PnL: ${avg_stats[2]:.2f}')
    if avg_stats[3]:
        print(f'  • Avg daily frequency: {avg_stats[3]:.2f}')

conn.close()

