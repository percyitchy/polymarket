#!/usr/bin/env python3
"""Generate tracked wallets report"""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('polymarket_notifier.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT address, display, traded_total, win_rate, realized_pnl_total, daily_trading_frequency
    FROM wallets 
    ORDER BY win_rate DESC, realized_pnl_total DESC
''')
wallets = cursor.fetchall()

filename = 'tracked_wallets_205.txt'
with open(filename, 'w') as f:
    f.write('=' * 80 + '\n')
    f.write('POLYMARKET TRACKED WALLETS (ACTIVE MONITORING)\n')
    f.write(f'Generated: {datetime.now().isoformat()}\n')
    f.write('=' * 80 + '\n\n')
    
    f.write('CONFIGURATION:\n')
    f.write('  Total Tracked Wallets: 205\n')
    f.write('  Max Trades Limit: <=1200\n')
    f.write('  Criteria: >=10 trades, winrate >65%\n')
    f.write('  Monitoring: New bets only (from this moment)\n')
    f.write('\n' + '=' * 80 + '\n\n')
    
    f.write(f'Total Wallets: {len(wallets)}\n')
    if wallets:
        f.write(f'Average Win Rate: {sum(w[3] for w in wallets)/len(wallets)*100:.2f}%\n')
        f.write(f'Total PnL: ${sum(w[4] for w in wallets):,.2f}\n')
    f.write('\n' + '=' * 80 + '\n\n')
    
    for i, (addr, display, trades, winrate, pnl, freq) in enumerate(wallets, 1):
        f.write(f'{i}. Address: {addr}\n')
        if display:
            f.write(f'   Display: {display}\n')
        f.write(f'   Trades: {trades}\n')
        f.write(f'   Win Rate: {winrate*100:.2f}%\n')
        f.write(f'   PnL: ${pnl:,.2f}\n')
        if freq:
            f.write(f'   Daily Frequency: {freq:.2f}\n')
        f.write('\n')

print(f'✅ Report saved to {filename}')
print(f'Total tracked wallets: {len(wallets)}')
if wallets:
    print(f'Average Win Rate: {sum(w[3] for w in wallets)/len(wallets)*100:.2f}%')

conn.close()

