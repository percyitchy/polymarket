#!/usr/bin/env python3
"""
Экспорт списка всех отслеживаемых кошельков в текстовый файл
"""

import os
import sys
from datetime import datetime
from db import PolymarketDB
from dotenv import load_dotenv

load_dotenv()

def main():
    db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)
    
    db = PolymarketDB()
    
    # Получаем отслеживаемые кошельки (используем те же критерии, что и бот)
    max_wallets = int(os.getenv("MAX_WALLETS", "9000"))
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Получаем отслеживаемые кошельки (те же критерии, что использует get_tracked_wallets)
        cursor.execute("""
            SELECT address, display, traded_total, win_rate, realized_pnl_total, 
                   daily_trading_frequency, source, last_trade_at
            FROM wallets
            WHERE traded_total >= 6 
            AND traded_total <= 2000
            AND win_rate >= 0.65 
            AND win_rate <= 1.0
            AND (daily_trading_frequency IS NULL OR daily_trading_frequency <= 40.0)
            ORDER BY realized_pnl_total DESC, traded_total DESC
            LIMIT ?
        """, (max_wallets,))
        
        wallets = cursor.fetchall()
        
        # Создаем имя файла с timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"tracked_wallets_{timestamp}.txt"
        
        # Записываем в файл
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("Список отслеживаемых кошельков\n")
            f.write("=" * 80 + "\n")
            f.write(f"Дата экспорта: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Всего кошельков: {len(wallets)}\n")
            f.write(f"MAX_WALLETS: {max_wallets}\n")
            f.write("=" * 80 + "\n\n")
            
            for i, (address, display, traded, win_rate, pnl, daily_freq, source, last_trade) in enumerate(wallets, 1):
                f.write(f"{i}. {address}\n")
                f.write(f"   Display: {display}\n")
                f.write(f"   Trades: {traded}, Win Rate: {win_rate:.2%}, PnL: ${pnl:,.2f}\n")
                daily_freq_str = f"{daily_freq:.2f}" if daily_freq is not None else "N/A"
                f.write(f"   Daily Freq: {daily_freq_str}, Source: {source}\n")
                if last_trade:
                    f.write(f"   Last Trade: {last_trade}\n")
                f.write("\n")
        
        print("=" * 80)
        print(f"✅ Экспорт завершен")
        print("=" * 80)
        print(f"Файл: {output_file}")
        print(f"Всего кошельков: {len(wallets)}")
        print("=" * 80)
        
        # Также создаем простой список только адресов
        addresses_file = f"tracked_wallets_addresses_{timestamp}.txt"
        with open(addresses_file, 'w', encoding='utf-8') as f:
            for address, _, _, _, _, _, _, _ in wallets:
                f.write(f"{address}\n")
        
        print(f"\nТакже создан файл только с адресами: {addresses_file}")
        print(f"Всего адресов: {len(wallets)}")

if __name__ == "__main__":
    main()

