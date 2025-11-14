#!/usr/bin/env python3
"""
Collect 250 best wallets including rejected ones, sorted by winrate
"""

import sqlite3
import logging
from typing import List, Dict
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class WalletData:
    address: str
    winrate: float
    traded_total: int
    daily_trading_frequency: float
    realized_pnl_total: float
    analysis_result: str

class WalletCollectorAll:
    def __init__(self, db_path: str = "polymarket_notifier.db"):
        self.db_path = db_path
    
    def get_250_best_wallets_all(self) -> List[WalletData]:
        """Get 250 best wallets including rejected ones, sorted by winrate"""
        
        logger.info("Collecting 250 best wallets (including rejected ones)...")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all wallets, ordered by winrate DESC, then by PnL DESC
            query = """
            SELECT address, win_rate, traded_total, daily_trading_frequency, 
                   realized_pnl_total, analysis_result
            FROM wallet_analysis_cache
            ORDER BY win_rate DESC, realized_pnl_total DESC
            LIMIT 250
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            
            wallets = []
            for row in results:
                wallet = WalletData(
                    address=row[0],
                    winrate=row[1],
                    traded_total=row[2],
                    daily_trading_frequency=row[3],
                    realized_pnl_total=row[4],
                    analysis_result=row[5]
                )
                wallets.append(wallet)
            
            conn.close()
            
            logger.info(f"Found {len(wallets)} best wallets")
            return wallets
            
        except Exception as e:
            logger.error(f"Error querying database: {e}")
            return []
    
    def get_winrate_distribution_all(self) -> Dict:
        """Get distribution of all winrates in database"""
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get winrate distribution for all wallets
            query = """
            SELECT 
                CASE 
                    WHEN win_rate = 1.0 THEN '100%'
                    WHEN win_rate >= 0.9 THEN '90-99%'
                    WHEN win_rate >= 0.8 THEN '80-89%'
                    WHEN win_rate >= 0.7 THEN '70-79%'
                    WHEN win_rate >= 0.6 THEN '60-69%'
                    WHEN win_rate >= 0.5 THEN '50-59%'
                    WHEN win_rate >= 0.4 THEN '40-49%'
                    WHEN win_rate >= 0.3 THEN '30-39%'
                    WHEN win_rate >= 0.2 THEN '20-29%'
                    WHEN win_rate >= 0.1 THEN '10-19%'
                    ELSE 'Below 10%'
                END as winrate_range,
                COUNT(*) as count,
                SUM(realized_pnl_total) as total_pnl,
                AVG(win_rate) as avg_winrate
            FROM wallet_analysis_cache 
            GROUP BY 
                CASE 
                    WHEN win_rate = 1.0 THEN '100%'
                    WHEN win_rate >= 0.9 THEN '90-99%'
                    WHEN win_rate >= 0.8 THEN '80-89%'
                    WHEN win_rate >= 0.7 THEN '70-79%'
                    WHEN win_rate >= 0.6 THEN '60-69%'
                    WHEN win_rate >= 0.5 THEN '50-59%'
                    WHEN win_rate >= 0.4 THEN '40-49%'
                    WHEN win_rate >= 0.3 THEN '30-39%'
                    WHEN win_rate >= 0.2 THEN '20-29%'
                    WHEN win_rate >= 0.1 THEN '10-19%'
                    ELSE 'Below 10%'
                END
            ORDER BY avg_winrate DESC
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            
            distribution = {}
            for row in results:
                distribution[row[0]] = {
                    'count': row[1],
                    'total_pnl': row[2] or 0,
                    'avg_winrate': row[3] or 0
                }
            
            conn.close()
            
            return distribution
            
        except Exception as e:
            logger.error(f"Error getting distribution: {e}")
            return {}
    
    def save_all_250_to_txt(self, wallets: List[WalletData], filename: str = "wallets_250_all_best.txt"):
        """Save all 250 best wallets to .txt file"""
        
        logger.info(f"Saving {len(wallets)} wallets to {filename}...")
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # Write header
                f.write("# Polymarket Wallets - Top 250 Best (All Wallets)\n")
                f.write("# Format: address,winrate%,trades,daily_frequency,pnl_total,status\n")
                f.write("# Generated by Polymarket Notifier\n")
                f.write("# Includes: All wallets sorted by winrate (accepted + rejected)\n\n")
                
                # Group wallets by winrate ranges
                wallets_100 = [w for w in wallets if w.winrate == 1.0]
                wallets_90_99 = [w for w in wallets if w.winrate >= 0.9 and w.winrate < 1.0]
                wallets_80_89 = [w for w in wallets if w.winrate >= 0.8 and w.winrate < 0.9]
                wallets_70_79 = [w for w in wallets if w.winrate >= 0.7 and w.winrate < 0.8]
                wallets_60_69 = [w for w in wallets if w.winrate >= 0.6 and w.winrate < 0.7]
                wallets_50_59 = [w for w in wallets if w.winrate >= 0.5 and w.winrate < 0.6]
                wallets_below_50 = [w for w in wallets if w.winrate < 0.5]
                
                # Write 100% winrate section
                if wallets_100:
                    f.write("# === 100% WINRATE WALLETS ===\n")
                    for i, wallet in enumerate(wallets_100, 1):
                        f.write(f"{i:3d}. {wallet.address} | "
                               f"Winrate: {wallet.winrate*100:.1f}% | "
                               f"Trades: {wallet.traded_total} | "
                               f"Daily: {wallet.daily_trading_frequency:.2f} | "
                               f"PnL: ${wallet.realized_pnl_total:,.2f} | "
                               f"Status: {wallet.analysis_result}\n")
                
                # Write 90-99% winrate section
                if wallets_90_99:
                    f.write(f"\n# === 90-99% WINRATE WALLETS ===\n")
                    start_num = len(wallets_100) + 1
                    for i, wallet in enumerate(wallets_90_99, start_num):
                        f.write(f"{i:3d}. {wallet.address} | "
                               f"Winrate: {wallet.winrate*100:.1f}% | "
                               f"Trades: {wallet.traded_total} | "
                               f"Daily: {wallet.daily_trading_frequency:.2f} | "
                               f"PnL: ${wallet.realized_pnl_total:,.2f} | "
                               f"Status: {wallet.analysis_result}\n")
                
                # Write 80-89% winrate section
                if wallets_80_89:
                    f.write(f"\n# === 80-89% WINRATE WALLETS ===\n")
                    start_num = len(wallets_100) + len(wallets_90_99) + 1
                    for i, wallet in enumerate(wallets_80_89, start_num):
                        f.write(f"{i:3d}. {wallet.address} | "
                               f"Winrate: {wallet.winrate*100:.1f}% | "
                               f"Trades: {wallet.traded_total} | "
                               f"Daily: {wallet.daily_trading_frequency:.2f} | "
                               f"PnL: ${wallet.realized_pnl_total:,.2f} | "
                               f"Status: {wallet.analysis_result}\n")
                
                # Write 70-79% winrate section
                if wallets_70_79:
                    f.write(f"\n# === 70-79% WINRATE WALLETS ===\n")
                    start_num = len(wallets_100) + len(wallets_90_99) + len(wallets_80_89) + 1
                    for i, wallet in enumerate(wallets_70_79, start_num):
                        f.write(f"{i:3d}. {wallet.address} | "
                               f"Winrate: {wallet.winrate*100:.1f}% | "
                               f"Trades: {wallet.traded_total} | "
                               f"Daily: {wallet.daily_trading_frequency:.2f} | "
                               f"PnL: ${wallet.realized_pnl_total:,.2f} | "
                               f"Status: {wallet.analysis_result}\n")
                
                # Write 60-69% winrate section
                if wallets_60_69:
                    f.write(f"\n# === 60-69% WINRATE WALLETS ===\n")
                    start_num = len(wallets_100) + len(wallets_90_99) + len(wallets_80_89) + len(wallets_70_79) + 1
                    for i, wallet in enumerate(wallets_60_69, start_num):
                        f.write(f"{i:3d}. {wallet.address} | "
                               f"Winrate: {wallet.winrate*100:.1f}% | "
                               f"Trades: {wallet.traded_total} | "
                               f"Daily: {wallet.daily_trading_frequency:.2f} | "
                               f"PnL: ${wallet.realized_pnl_total:,.2f} | "
                               f"Status: {wallet.analysis_result}\n")
                
                # Write 50-59% winrate section
                if wallets_50_59:
                    f.write(f"\n# === 50-59% WINRATE WALLETS ===\n")
                    start_num = len(wallets_100) + len(wallets_90_99) + len(wallets_80_89) + len(wallets_70_79) + len(wallets_60_69) + 1
                    for i, wallet in enumerate(wallets_50_59, start_num):
                        f.write(f"{i:3d}. {wallet.address} | "
                               f"Winrate: {wallet.winrate*100:.1f}% | "
                               f"Trades: {wallet.traded_total} | "
                               f"Daily: {wallet.daily_trading_frequency:.2f} | "
                               f"PnL: ${wallet.realized_pnl_total:,.2f} | "
                               f"Status: {wallet.analysis_result}\n")
                
                # Write below 50% winrate section
                if wallets_below_50:
                    f.write(f"\n# === BELOW 50% WINRATE WALLETS ===\n")
                    start_num = len(wallets_100) + len(wallets_90_99) + len(wallets_80_89) + len(wallets_70_79) + len(wallets_60_69) + len(wallets_50_59) + 1
                    for i, wallet in enumerate(wallets_below_50, start_num):
                        f.write(f"{i:3d}. {wallet.address} | "
                               f"Winrate: {wallet.winrate*100:.1f}% | "
                               f"Trades: {wallet.traded_total} | "
                               f"Daily: {wallet.daily_trading_frequency:.2f} | "
                               f"PnL: ${wallet.realized_pnl_total:,.2f} | "
                               f"Status: {wallet.analysis_result}\n")
                
                # Write summary
                f.write(f"\n# Summary:\n")
                f.write(f"# Total wallets: {len(wallets)}\n")
                f.write(f"# 100% winrate: {len(wallets_100)}\n")
                f.write(f"# 90-99% winrate: {len(wallets_90_99)}\n")
                f.write(f"# 80-89% winrate: {len(wallets_80_89)}\n")
                f.write(f"# 70-79% winrate: {len(wallets_70_79)}\n")
                f.write(f"# 60-69% winrate: {len(wallets_60_69)}\n")
                f.write(f"# 50-59% winrate: {len(wallets_50_59)}\n")
                f.write(f"# Below 50% winrate: {len(wallets_below_50)}\n")
                f.write(f"# Total PnL: ${sum(w.realized_pnl_total for w in wallets):,.2f}\n")
                f.write(f"# Average trades per wallet: {sum(w.traded_total for w in wallets) / len(wallets):.1f}\n")
                f.write(f"# Average daily frequency: {sum(w.daily_trading_frequency for w in wallets) / len(wallets):.2f}\n")
                f.write(f"# Average winrate: {sum(w.winrate for w in wallets) / len(wallets)*100:.2f}%\n")
            
            logger.info(f"✅ Successfully saved to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving to file: {e}")
            return False

def main():
    """Main function to collect all 250 best wallets"""
    logger.info("Starting collection of all 250 best wallets...")
    
    collector = WalletCollectorAll()
    
    # Get winrate distribution first
    distribution = collector.get_winrate_distribution_all()
    if distribution:
        logger.info("Winrate Distribution (All Wallets):")
        for range_name, data in distribution.items():
            logger.info(f"  {range_name}: {data['count']} wallets, "
                       f"Avg Winrate: {data['avg_winrate']*100:.1f}%, "
                       f"PnL: ${data['total_pnl']:,.2f}")
    
    # Collect all best wallets
    all_wallets = collector.get_250_best_wallets_all()
    
    if all_wallets:
        logger.info(f"🎉 Collected {len(all_wallets)} wallets total!")
        
        # Show breakdown by winrate ranges
        wallets_100 = [w for w in all_wallets if w.winrate == 1.0]
        wallets_90_99 = [w for w in all_wallets if w.winrate >= 0.9 and w.winrate < 1.0]
        wallets_80_89 = [w for w in all_wallets if w.winrate >= 0.8 and w.winrate < 0.9]
        wallets_70_79 = [w for w in all_wallets if w.winrate >= 0.7 and w.winrate < 0.8]
        wallets_60_69 = [w for w in all_wallets if w.winrate >= 0.6 and w.winrate < 0.7]
        wallets_50_59 = [w for w in all_wallets if w.winrate >= 0.5 and w.winrate < 0.6]
        wallets_below_50 = [w for w in all_wallets if w.winrate < 0.5]
        
        logger.info(f"  - 100% winrate: {len(wallets_100)} wallets")
        logger.info(f"  - 90-99% winrate: {len(wallets_90_99)} wallets")
        logger.info(f"  - 80-89% winrate: {len(wallets_80_89)} wallets")
        logger.info(f"  - 70-79% winrate: {len(wallets_70_79)} wallets")
        logger.info(f"  - 60-69% winrate: {len(wallets_60_69)} wallets")
        logger.info(f"  - 50-59% winrate: {len(wallets_50_59)} wallets")
        logger.info(f"  - Below 50% winrate: {len(wallets_below_50)} wallets")
        
        # Show top 10 overall
        logger.info("Top 10 wallets by Winrate:")
        for i, wallet in enumerate(all_wallets[:10], 1):
            logger.info(f"  {i:2d}. {wallet.address} - "
                       f"Winrate: {wallet.winrate*100:.1f}%, "
                       f"PnL: ${wallet.realized_pnl_total:,.2f}, "
                       f"Trades: {wallet.traded_total}, "
                       f"Status: {wallet.analysis_result}")
        
        # Save to file
        success = collector.save_all_250_to_txt(all_wallets)
        
        if success:
            logger.info("✅ All wallets file saved successfully!")
        else:
            logger.error("❌ Failed to save file!")
    else:
        logger.warning("⚠️  No wallets found!")
    
    return all_wallets

if __name__ == "__main__":
    wallets = main()
