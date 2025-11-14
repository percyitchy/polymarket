#!/usr/bin/env python3
"""
Restore accepted wallets from cache to wallets table
"""

import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import PolymarketDB

load_dotenv()

def main():
    db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)
    
    print("=" * 60)
    print("📊 ВОССТАНОВЛЕНИЕ ACCEPTED КОШЕЛЬКОВ")
    print("=" * 60)
    print(f"DB_PATH: {db_path}")
    
    db = PolymarketDB(db_path)
    
    # Находим accepted кошельки, которых нет в wallets
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.address, c.traded_total, c.win_rate, c.realized_pnl_total, 
                   c.daily_trading_frequency, c.last_trade_at, c.source
            FROM wallet_analysis_cache c
            LEFT JOIN wallets w ON c.address = w.address
            WHERE c.analysis_result = 'accepted'
            AND w.address IS NULL
        """)
        missing = cursor.fetchall()
        print(f"\nНайдено {len(missing)} accepted кошельков, которых нет в wallets")
        
        if missing:
            print("\nВосстанавливаем их...")
            restored = 0
            failed = 0
            for addr, traded, win_rate, pnl, freq, last_trade, source in missing:
                display = addr  # Use address as display name
                source_val = source or "cache_recovery"
                success = db.upsert_wallet(
                    addr, display, traded, win_rate, pnl, freq, source_val, last_trade
                )
                if success:
                    restored += 1
                    print(f"  ✅ {addr[:20]}... | trades={traded}, win_rate={win_rate:.2%}")
                else:
                    failed += 1
                    print(f"  ❌ {addr[:20]}... | FAILED to save")
            
            print(f"\nВосстановлено: {restored} кошельков")
            if failed > 0:
                print(f"Ошибок: {failed}")
            
            # Проверяем новую статистику
            stats = db.get_wallet_stats()
            print(f"\nНовая статистика:")
            print(f"  Total wallets: {stats.get('total_wallets', 0)}")
            print(f"  Tracked wallets: {stats.get('tracked_wallets', 0)}")
        else:
            print("\n✅ Все accepted кошельки уже в wallets")
    
    print("\n" + "=" * 60)
    print("✅ Восстановление завершено")
    print("=" * 60)

if __name__ == "__main__":
    main()

