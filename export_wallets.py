#!/usr/bin/env python3
"""
Export wallets database to text file
"""
from db import PolymarketDB
from datetime import datetime

db = PolymarketDB()
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = f"wallets_export_{timestamp}.txt"

with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT address, display, traded_total, win_rate, realized_pnl_total, 
               daily_trading_frequency, source, added_at, updated_at
        FROM wallets
        ORDER BY realized_pnl_total DESC, win_rate DESC, traded_total DESC
    """)
    
    wallets = cursor.fetchall()
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Polymarket Wallets Export\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
        f.write(f"Total wallets: {len(wallets)}\n")
        f.write("=" * 100 + "\n\n")
        
        f.write(f"{'Address':<42} {'Display':<20} {'Trades':<8} {'Win Rate':<10} {'PnL':<15} {'Daily Freq':<12} {'Source':<15}\n")
        f.write("-" * 100 + "\n")
        
        for wallet in wallets:
            addr, display, trades, wr, pnl, freq, source, added, updated = wallet
            display_str = display or addr[:20] + "..."
            wr_str = f"{wr:.1%}" if wr else "N/A"
            pnl_str = f"${pnl:,.2f}" if pnl else "$0.00"
            freq_str = f"{freq:.2f}" if freq else "N/A"
            
            f.write(f"{addr:<42} {display_str:<20} {trades or 0:<8} {wr_str:<10} {pnl_str:<15} {freq_str:<12} {source or 'unknown':<15}\n")
    
    print(f"✅ Экспортировано {len(wallets)} кошельков в {output_file}")
    print(f"📁 Файл: {output_file}")
