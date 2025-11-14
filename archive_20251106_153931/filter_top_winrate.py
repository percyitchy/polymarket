#!/usr/bin/env python3
"""
Filter existing wallet analysis data to find top 200 by winrate
Use data from wallet_analysis_cache table
"""

import sqlite3
import logging
from typing import List, Dict, Tuple
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

class TopWinrateFilter:
    def __init__(self, db_path: str = "polymarket_notifier.db"):
        self.db_path = db_path
    
    def get_top_winrate_wallets(self, 
                               min_winrate: float = 65.0,
                               max_winrate: float = 90.0,
                               max_trades: int = 1000,
                               max_daily_trades: float = 10.0,
                               limit: int = 200) -> List[WalletData]:
        """Get top wallets by winrate with specified criteria"""
        
        logger.info(f"Searching for top {limit} wallets with criteria:")
        logger.info(f"  Winrate: {min_winrate}% - {max_winrate}%")
        logger.info(f"  Max trades: {max_trades}")
        logger.info(f"  Max daily trades: {max_daily_trades}")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Query wallets from analysis cache
            # Note: win_rate is stored as decimal (0.65-0.90), not percentage
            query = """
            SELECT address, win_rate, traded_total, daily_trading_frequency, 
                   realized_pnl_total, analysis_result
            FROM wallet_analysis_cache
            WHERE win_rate >= ? AND win_rate <= ?
            AND traded_total <= ?
            AND daily_trading_frequency <= ?
            AND analysis_result = 'accepted'
            ORDER BY win_rate DESC
            LIMIT ?
            """
            
            # Convert percentage to decimal for comparison
            min_winrate_decimal = min_winrate / 100.0
            max_winrate_decimal = max_winrate / 100.0
            
            cursor.execute(query, (min_winrate_decimal, max_winrate_decimal, max_trades, max_daily_trades, limit))
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
            
            logger.info(f"Found {len(wallets)} wallets meeting criteria")
            return wallets
            
        except Exception as e:
            logger.error(f"Error querying database: {e}")
            return []
    
    def get_all_analyzed_wallets(self) -> List[WalletData]:
        """Get all analyzed wallets for overview"""
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = """
            SELECT address, win_rate, traded_total, daily_trading_frequency, 
                   realized_pnl_total, analysis_result
            FROM wallet_analysis_cache
            ORDER BY win_rate DESC
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
            
            logger.info(f"Found {len(wallets)} total analyzed wallets")
            return wallets
            
        except Exception as e:
            logger.error(f"Error querying database: {e}")
            return []
    
    def get_wallet_statistics(self) -> Dict:
        """Get statistics about analyzed wallets"""
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get basic stats
            cursor.execute("SELECT COUNT(*) FROM wallet_analysis_cache")
            total_wallets = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM wallet_analysis_cache WHERE analysis_result = 'accepted'")
            accepted_wallets = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM wallet_analysis_cache WHERE analysis_result = 'rejected'")
            rejected_wallets = cursor.fetchone()[0]
            
            # Get winrate stats
            cursor.execute("SELECT MIN(win_rate), MAX(win_rate), AVG(win_rate) FROM wallet_analysis_cache")
            winrate_stats = cursor.fetchone()
            
            # Get trades stats
            cursor.execute("SELECT MIN(traded_total), MAX(traded_total), AVG(traded_total) FROM wallet_analysis_cache")
            trades_stats = cursor.fetchone()
            
            # Get daily frequency stats
            cursor.execute("SELECT MIN(daily_trading_frequency), MAX(daily_trading_frequency), AVG(daily_trading_frequency) FROM wallet_analysis_cache")
            daily_stats = cursor.fetchone()
            
            conn.close()
            
            stats = {
                'total_wallets': total_wallets,
                'accepted_wallets': accepted_wallets,
                'rejected_wallets': rejected_wallets,
                'winrate_min': winrate_stats[0],
                'winrate_max': winrate_stats[1],
                'winrate_avg': winrate_stats[2],
                'trades_min': trades_stats[0],
                'trades_max': trades_stats[1],
                'trades_avg': trades_stats[2],
                'daily_min': daily_stats[0],
                'daily_max': daily_stats[1],
                'daily_avg': daily_stats[2]
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

def main():
    """Main function to find top winrate wallets"""
    logger.info("Starting top winrate wallet search from database...")
    
    filter_tool = TopWinrateFilter()
    
    # First, show statistics
    stats = filter_tool.get_wallet_statistics()
    if stats:
        logger.info("Database Statistics:")
        logger.info(f"  Total analyzed wallets: {stats['total_wallets']}")
        logger.info(f"  Accepted wallets: {stats['accepted_wallets']}")
        logger.info(f"  Rejected wallets: {stats['rejected_wallets']}")
        logger.info(f"  Winrate range: {stats['winrate_min']*100:.2f}% - {stats['winrate_max']*100:.2f}%")
        logger.info(f"  Winrate average: {stats['winrate_avg']*100:.2f}%")
        logger.info(f"  Trades range: {stats['trades_min']} - {stats['trades_max']}")
        logger.info(f"  Daily frequency range: {stats['daily_min']:.2f} - {stats['daily_max']:.2f}")
    
    # Get top winrate wallets
    top_wallets = filter_tool.get_top_winrate_wallets(
        min_winrate=65.0,
        max_winrate=90.0,
        max_trades=1000,
        max_daily_trades=10.0,
        limit=200
    )
    
    logger.info(f"🎉 Found {len(top_wallets)} wallets meeting criteria!")
    
    if len(top_wallets) >= 200:
        logger.info("✅ SUCCESS: Found 200+ wallets as requested!")
    else:
        logger.info(f"⚠️  Found {len(top_wallets)} wallets (target was 200)")
    
    # Show top wallets
    logger.info("Top winrate wallets:")
    for i, wallet in enumerate(top_wallets[:20]):
        logger.info(f"  {i+1}. {wallet.address} - Winrate: {wallet.winrate*100:.2f}%, "
                   f"Trades: {wallet.traded_total}, Daily: {wallet.daily_trading_frequency:.2f}, "
                   f"PnL: {wallet.realized_pnl_total:.2f}")
    
    if len(top_wallets) > 20:
        logger.info(f"  ... and {len(top_wallets) - 20} more")
    
    # If we don't have enough, show what we have
    if len(top_wallets) < 200:
        logger.info("\nShowing all accepted wallets:")
        all_wallets = filter_tool.get_all_analyzed_wallets()
        accepted_wallets = [w for w in all_wallets if w.analysis_result == 'accepted']
        
        logger.info(f"Total accepted wallets: {len(accepted_wallets)}")
        for i, wallet in enumerate(accepted_wallets[:20]):
            logger.info(f"  {i+1}. {wallet.address} - Winrate: {wallet.winrate*100:.2f}%, "
                       f"Trades: {wallet.traded_total}, Daily: {wallet.daily_trading_frequency:.2f}")
    
    return top_wallets

if __name__ == "__main__":
    wallets = main()
