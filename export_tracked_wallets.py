#!/usr/bin/env python3
"""
Export tracked wallets to text file
"""
from db import PolymarketDB
from datetime import datetime, timezone, timedelta

db = PolymarketDB()
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = f"tracked_wallets_{timestamp}.txt"

# Get tracked wallets (with 3-month filter)
tracked = db.get_tracked_wallets(
    min_trades=6, 
    max_trades=1500, 
    min_win_rate=0.70, 
    max_win_rate=1.0, 
    max_daily_freq=25.0, 
    limit=2000
)

three_months_ago = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()

with db.get_connection() as conn:
    cursor = conn.cursor()
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Polymarket Tracked Wallets Export\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
        f.write(f"Total tracked wallets: {len(tracked)}\n")
        f.write(f"Criteria: >=6 trades, >=70% win rate, <=25 daily freq, last trade < 3 months ago\n")
        f.write("=" * 100 + "\n\n")
        
        f.write(f"{'Address':<42} {'Display':<20} {'Trades':<8} {'Win Rate':<10} {'PnL':<15} {'Daily Freq':<12} {'Last Trade':<12} {'Source':<15}\n")
        f.write("-" * 100 + "\n")
        
        for addr in tracked:
            cursor.execute("""
                SELECT display, traded_total, win_rate, realized_pnl_total, 
                       daily_trading_frequency, source, last_trade_at
                FROM wallets 
                WHERE address = ?
            """, (addr,))
            
            row = cursor.fetchone()
            if row:
                display, trades, wr, pnl, freq, source, last_trade = row
                display_str = display or addr[:20] + "..."
                wr_str = f"{wr:.1%}" if wr else "N/A"
                pnl_str = f"${pnl:,.2f}" if pnl else "$0.00"
                freq_str = f"{freq:.2f}" if freq else "N/A"
                
                # Format last trade date
                if last_trade:
                    try:
                        dt = datetime.fromisoformat(last_trade.replace("Z", "+00:00"))
                        last_trade_str = dt.strftime("%Y-%m-%d")
                    except:
                        last_trade_str = "N/A"
                else:
                    last_trade_str = "N/A"
                
                f.write(f"{addr:<42} {display_str:<20} {trades or 0:<8} {wr_str:<10} {pnl_str:<15} {freq_str:<12} {last_trade_str:<12} {source or 'unknown':<15}\n")
    
    print(f"✅ Экспортировано {len(tracked)} отслеживаемых кошельков в {output_file}")
    print(f"📁 Файл: {output_file}")

