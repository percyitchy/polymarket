#!/usr/bin/env python3
"""
Collect additional wallets with 80%+ winrate to reach 250 total wallets
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

class WalletCollectorExtended:
    def __init__(self, db_path: str = "polymarket_notifier.db"):
        self.db_path = db_path
    
    def get_additional_wallets(self, target_total: int = 250) -> List[WalletData]:
        """Get additional wallets with 80%+ winrate to reach target total"""
        
        logger.info(f"Collecting additional wallets to reach {target_total} total...")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # First, count how many 100% winrate wallets we have
            cursor.execute("SELECT COUNT(*) FROM wallet_analysis_cache WHERE win_rate = 1.0 AND analysis_result = 'accepted'")
            count_100_percent = cursor.fetchone()[0]
            
            logger.info(f"Current 100% winrate wallets: {count_100_percent}")
            
            # Calculate how many more we need
            needed = target_total - count_100_percent
            logger.info(f"Need {needed} more wallets")
            
            if needed <= 0:
                logger.info("Already have enough wallets!")
                conn.close()
                return []
            
            # Get additional wallets with 80%+ winrate (excluding 100%)
            query = """
            SELECT address, win_rate, traded_total, daily_trading_frequency, 
                   realized_pnl_total, analysis_result
            FROM wallet_analysis_cache
            WHERE win_rate >= 0.8 AND win_rate < 1.0
            AND analysis_result = 'accepted'
            ORDER BY win_rate DESC, realized_pnl_total DESC
            LIMIT ?
            """
            
            cursor.execute(query, (needed,))
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
            
            logger.info(f"Found {len(wallets)} additional wallets with 80%+ winrate")
            return wallets
            
        except Exception as e:
            logger.error(f"Error querying database: {e}")
            return []
    
    def get_all_wallets_for_250(self) -> List[WalletData]:
        """Get all wallets (100% + 80%+) to reach 250 total"""
        
        logger.info("Collecting complete set of 250 wallets...")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get 100% winrate wallets first
            query_100 = """
            SELECT address, win_rate, traded_total, daily_trading_frequency, 
                   realized_pnl_total, analysis_result
            FROM wallet_analysis_cache
            WHERE win_rate = 1.0
            AND analysis_result = 'accepted'
            ORDER BY realized_pnl_total DESC
            """
            
            cursor.execute(query_100)
            wallets_100 = []
            for row in cursor.fetchall():
                wallet = WalletData(
                    address=row[0],
                    winrate=row[1],
                    traded_total=row[2],
                    daily_trading_frequency=row[3],
                    realized_pnl_total=row[4],
                    analysis_result=row[5]
                )
                wallets_100.append(wallet)
            
            logger.info(f"Found {len(wallets_100)} wallets with 100% winrate")
            
            # Calculate how many more we need
            needed = 250 - len(wallets_100)
            logger.info(f"Need {needed} more wallets with 80%+ winrate")
            
            if needed <= 0:
                logger.info("Already have 250+ wallets with 100% winrate!")
                conn.close()
                return wallets_100[:250]
            
            # Get additional wallets with 80%+ winrate (excluding 100%)
            query_80_plus = """
            SELECT address, win_rate, traded_total, daily_trading_frequency, 
                   realized_pnl_total, analysis_result
            FROM wallet_analysis_cache
            WHERE win_rate >= 0.8 AND win_rate < 1.0
            AND analysis_result = 'accepted'
            ORDER BY win_rate DESC, realized_pnl_total DESC
            LIMIT ?
            """
            
            cursor.execute(query_80_plus, (needed,))
            wallets_80_plus = []
            for row in cursor.fetchall():
                wallet = WalletData(
                    address=row[0],
                    winrate=row[1],
                    traded_total=row[2],
                    daily_trading_frequency=row[3],
                    realized_pnl_total=row[4],
                    analysis_result=row[5]
                )
                wallets_80_plus.append(wallet)
            
            logger.info(f"Found {len(wallets_80_plus)} additional wallets with 80%+ winrate")
            
            # Combine both lists
            all_wallets = wallets_100 + wallets_80_plus
            
            conn.close()
            
            logger.info(f"Total wallets collected: {len(all_wallets)}")
            return all_wallets
            
        except Exception as e:
            logger.error(f"Error querying database: {e}")
            return []
    
    def save_complete_250_to_txt(self, wallets: List[WalletData], filename: str = "wallets_250_complete.txt"):
        """Save complete set of 250 wallets to .txt file"""
        
        logger.info(f"Saving {len(wallets)} wallets to {filename}...")
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # Write header
                f.write("# Polymarket Wallets - Complete Set of 250\n")
                f.write("# Format: address,winrate%,trades,daily_frequency,pnl_total\n")
                f.write("# Generated by Polymarket Notifier\n")
                f.write("# Includes: 100% winrate + 80%+ winrate wallets\n\n")
                
                # Separate 100% and 80%+ wallets
                wallets_100 = [w for w in wallets if w.winrate == 1.0]
                wallets_80_plus = [w for w in wallets if w.winrate >= 0.8 and w.winrate < 1.0]
                
                # Write 100% winrate section
                f.write("# === 100% WINRATE WALLETS ===\n")
                for i, wallet in enumerate(wallets_100, 1):
                    f.write(f"{i:3d}. {wallet.address} | "
                           f"Winrate: {wallet.winrate*100:.1f}% | "
                           f"Trades: {wallet.traded_total} | "
                           f"Daily: {wallet.daily_trading_frequency:.2f} | "
                           f"PnL: ${wallet.realized_pnl_total:,.2f}\n")
                
                # Write 80%+ winrate section
                f.write(f"\n# === 80%+ WINRATE WALLETS ===\n")
                start_num = len(wallets_100) + 1
                for i, wallet in enumerate(wallets_80_plus, start_num):
                    f.write(f"{i:3d}. {wallet.address} | "
                           f"Winrate: {wallet.winrate*100:.1f}% | "
                           f"Trades: {wallet.traded_total} | "
                           f"Daily: {wallet.daily_trading_frequency:.2f} | "
                           f"PnL: ${wallet.realized_pnl_total:,.2f}\n")
                
                # Write summary
                f.write(f"\n# Summary:\n")
                f.write(f"# Total wallets: {len(wallets)}\n")
                f.write(f"# 100% winrate wallets: {len(wallets_100)}\n")
                f.write(f"# 80%+ winrate wallets: {len(wallets_80_plus)}\n")
                f.write(f"# Total PnL: ${sum(w.realized_pnl_total for w in wallets):,.2f}\n")
                f.write(f"# Average trades per wallet: {sum(w.traded_total for w in wallets) / len(wallets):.1f}\n")
                f.write(f"# Average daily frequency: {sum(w.daily_trading_frequency for w in wallets) / len(wallets):.2f}\n")
                f.write(f"# Average winrate: {sum(w.winrate for w in wallets) / len(wallets)*100:.2f}%\n")
            
            logger.info(f"✅ Successfully saved to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving to file: {e}")
            return False
    
    def get_statistics(self) -> Dict:
        """Get statistics about available wallets"""
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get count of 100% winrate wallets
            cursor.execute("SELECT COUNT(*) FROM wallet_analysis_cache WHERE win_rate = 1.0 AND analysis_result = 'accepted'")
            count_100_percent = cursor.fetchone()[0]
            
            # Get count of 80%+ winrate wallets (excluding 100%)
            cursor.execute("SELECT COUNT(*) FROM wallet_analysis_cache WHERE win_rate >= 0.8 AND win_rate < 1.0 AND analysis_result = 'accepted'")
            count_80_plus = cursor.fetchone()[0]
            
            # Get total PnL for 100%
            cursor.execute("SELECT SUM(realized_pnl_total) FROM wallet_analysis_cache WHERE win_rate = 1.0 AND analysis_result = 'accepted'")
            total_pnl_100 = cursor.fetchone()[0] or 0
            
            # Get total PnL for 80%+
            cursor.execute("SELECT SUM(realized_pnl_total) FROM wallet_analysis_cache WHERE win_rate >= 0.8 AND win_rate < 1.0 AND analysis_result = 'accepted'")
            total_pnl_80_plus = cursor.fetchone()[0] or 0
            
            conn.close()
            
            return {
                'count_100_percent': count_100_percent,
                'count_80_plus': count_80_plus,
                'total_available': count_100_percent + count_80_plus,
                'total_pnl_100': total_pnl_100,
                'total_pnl_80_plus': total_pnl_80_plus,
                'total_pnl_all': total_pnl_100 + total_pnl_80_plus
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

def main():
    """Main function to collect complete set of 250 wallets"""
    logger.info("Starting collection of complete 250 wallet set...")
    
    collector = WalletCollectorExtended()
    
    # Get statistics first
    stats = collector.get_statistics()
    if stats:
        logger.info("Available Statistics:")
        logger.info(f"  100% winrate wallets: {stats['count_100_percent']}")
        logger.info(f"  80%+ winrate wallets: {stats['count_80_plus']}")
        logger.info(f"  Total available: {stats['total_available']}")
        logger.info(f"  Total PnL (100%): ${stats['total_pnl_100']:,.2f}")
        logger.info(f"  Total PnL (80%+): ${stats['total_pnl_80_plus']:,.2f}")
        logger.info(f"  Total PnL (all): ${stats['total_pnl_all']:,.2f}")
    
    # Collect complete set
    all_wallets = collector.get_all_wallets_for_250()
    
    if all_wallets:
        logger.info(f"🎉 Collected {len(all_wallets)} wallets total!")
        
        # Show breakdown
        wallets_100 = [w for w in all_wallets if w.winrate == 1.0]
        wallets_80_plus = [w for w in all_wallets if w.winrate >= 0.8 and w.winrate < 1.0]
        
        logger.info(f"  - 100% winrate: {len(wallets_100)} wallets")
        logger.info(f"  - 80%+ winrate: {len(wallets_80_plus)} wallets")
        
        # Show top 10 overall
        logger.info("Top 10 wallets by PnL:")
        for i, wallet in enumerate(all_wallets[:10], 1):
            logger.info(f"  {i:2d}. {wallet.address} - "
                       f"Winrate: {wallet.winrate*100:.1f}%, "
                       f"PnL: ${wallet.realized_pnl_total:,.2f}, "
                       f"Trades: {wallet.traded_total}")
        
        # Save to file
        success = collector.save_complete_250_to_txt(all_wallets)
        
        if success:
            logger.info("✅ Complete file saved successfully!")
        else:
            logger.error("❌ Failed to save file!")
    else:
        logger.warning("⚠️  No wallets found!")
    
    return all_wallets

if __name__ == "__main__":
    wallets = main()
