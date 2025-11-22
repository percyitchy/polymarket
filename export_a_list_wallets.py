#!/usr/bin/env python3
"""
Export A List traders with their categories and detailed analytics
"""

import os
from datetime import datetime
from db import PolymarketDB
from dotenv import load_dotenv

load_dotenv()

db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
if not os.path.isabs(db_path):
    db_path = os.path.abspath(db_path)

db = PolymarketDB(db_path)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = f"a_list_wallets_{timestamp}.txt"

with db.get_connection() as conn:
    cursor = conn.cursor()
    
    # Get all A List wallets with their category stats
    cursor.execute("""
        SELECT 
            wcs.wallet_address,
            wcs.category,
            wcs.markets,
            wcs.winrate,
            wcs.pnl,
            wcs.volume,
            wcs.roi,
            wcs.avg_pnl,
            w.display,
            w.win_rate as global_win_rate,
            w.traded_total as global_trades,
            w.realized_pnl_total as global_pnl
        FROM wallet_category_stats wcs
        LEFT JOIN wallets w ON wcs.wallet_address = w.address
        WHERE wcs.is_a_list_trader = 1
        ORDER BY wcs.category, wcs.winrate DESC, wcs.markets DESC
    """)
    
    a_list_wallets = cursor.fetchall()
    
    # Get category breakdown
    cursor.execute("""
        SELECT 
            category,
            COUNT(*) as wallet_count,
            SUM(markets) as total_markets,
            AVG(winrate) as avg_winrate,
            SUM(pnl) as total_pnl,
            SUM(volume) as total_volume,
            AVG(roi) as avg_roi
        FROM wallet_category_stats
        WHERE is_a_list_trader = 1
        GROUP BY category
        ORDER BY wallet_count DESC
    """)
    
    category_stats = cursor.fetchall()
    
    # Get overall stats
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT wallet_address) as total_a_list_wallets,
            COUNT(*) as total_category_records,
            SUM(markets) as total_markets,
            AVG(winrate) as avg_winrate,
            SUM(pnl) as total_pnl,
            SUM(volume) as total_volume
        FROM wallet_category_stats
        WHERE is_a_list_trader = 1
    """)
    
    overall_stats = cursor.fetchone()
    
    # Get sample of markets to analyze classification
    cursor.execute("""
        SELECT DISTINCT wallet_address, category
        FROM wallet_category_stats
        WHERE is_a_list_trader = 1
        LIMIT 10
    """)
    
    sample_wallets = cursor.fetchall()

# Write to file
with open(output_file, "w", encoding="utf-8") as f:
    f.write("=" * 100 + "\n")
    f.write("A LIST TRADERS EXPORT\n")
    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
    f.write("=" * 100 + "\n\n")
    
    # Overall statistics
    f.write("📊 OVERALL STATISTICS\n")
    f.write("-" * 100 + "\n")
    f.write(f"Total A List wallets: {overall_stats[0]}\n")
    f.write(f"Total category records: {overall_stats[1]}\n")
    f.write(f"Total markets analyzed: {overall_stats[2]}\n")
    f.write(f"Average winrate: {overall_stats[3]:.2%}\n")
    f.write(f"Total PnL: ${overall_stats[4]:,.2f}\n")
    f.write(f"Total volume: ${overall_stats[5]:,.2f}\n")
    f.write("\n")
    
    # Category breakdown
    f.write("📈 CATEGORY BREAKDOWN\n")
    f.write("-" * 100 + "\n")
    f.write(f"{'Category':<30} {'Wallets':<10} {'Markets':<12} {'Avg WR':<12} {'Total PnL':<15} {'Avg ROI':<12}\n")
    f.write("-" * 100 + "\n")
    
    for cat, count, markets, winrate, pnl, volume, roi in category_stats:
        f.write(f"{cat:<30} {count:<10} {markets:<12} {winrate:.2%} {pnl:>15,.2f} {roi:>12.4f}\n")
    
    f.write("\n\n")
    
    # Detailed wallet list
    f.write("=" * 100 + "\n")
    f.write("DETAILED A LIST WALLETS\n")
    f.write("=" * 100 + "\n\n")
    
    current_category = None
    for row in a_list_wallets:
        addr, cat, markets, winrate, pnl, volume, roi, avg_pnl, display, global_wr, global_trades, global_pnl = row
        
        if current_category != cat:
            f.write("\n" + "=" * 100 + "\n")
            f.write(f"CATEGORY: {cat}\n")
            f.write("=" * 100 + "\n\n")
            current_category = cat
        
        display_name = display or addr[:20] + "..."
        f.write(f"Wallet: {addr}\n")
        f.write(f"  Display: {display_name}\n")
        f.write(f"  Category: {cat}\n")
        f.write(f"  Category Stats:\n")
        f.write(f"    - Markets: {markets}\n")
        f.write(f"    - Winrate: {winrate:.2%}\n")
        f.write(f"    - PnL: ${pnl:,.2f}\n")
        f.write(f"    - Volume: ${volume:,.2f}\n")
        f.write(f"    - ROI: {roi:.4f} ({roi*100:.2f}%)\n")
        f.write(f"    - Avg PnL per market: ${avg_pnl:,.2f}\n")
        if global_wr:
            f.write(f"  Global Stats:\n")
            f.write(f"    - Global Winrate: {global_wr:.2%}\n")
            f.write(f"    - Global Trades: {global_trades}\n")
            f.write(f"    - Global PnL: ${global_pnl:,.2f}\n")
        f.write("\n")

print(f"✅ Экспортировано {len(a_list_wallets)} A List записей в {output_file}")
print(f"📁 Файл: {output_file}")
print(f"\n📊 Статистика:")
print(f"  - Уникальных A List кошельков: {overall_stats[0]}")
print(f"  - Всего категорийных записей: {overall_stats[1]}")
print(f"  - Категорий: {len(category_stats)}")

