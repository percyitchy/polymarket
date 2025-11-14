#!/usr/bin/env python3
"""
Добавление кошельков из CSV напрямую в БД
Использует данные из CSV без повторного анализа через API
"""

import csv
import os
import sys
from datetime import datetime, timezone
from db import PolymarketDB
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = "/Users/johnbravo/Downloads/filtered_wallets_subset (1).csv"
    
    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found: {csv_path}")
        logger.error(f"Usage: python3 add_csv_wallets_direct.py <csv_file_path>")
        sys.exit(1)
    
    db = PolymarketDB()
    added_count = 0
    skipped_count = 0
    
    logger.info(f"Reading CSV file: {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        # Пропускаем пустую первую строку
        first_line = f.readline()
        if not first_line.strip():
            pass
        
        reader = csv.DictReader(f)
        
        logger.info(f"CSV columns: {reader.fieldnames}")
        
        for row in reader:
            address = row.get('TRADER_ADDRESS', '').strip()
            if not address or not address.startswith('0x'):
                continue
            
            address = address.lower()
            
            # Проверяем, не добавлен ли уже
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT address FROM wallets WHERE address = ?", (address,))
                if cursor.fetchone():
                    skipped_count += 1
                    continue
            
            # Используем данные из CSV
            try:
                total_trades = int(row.get('TOTAL_TRADES', 0))
                avg_trades_per_day = float(row.get('avg_trades_per_active_day', 0))
                last_trade_date = row.get('LAST_TRADE_DATE', '')
                
                # Для winrate и PnL используем значения по умолчанию
                # (они будут обновлены при следующем анализе)
                win_rate = 0.70  # Консервативная оценка, будет обновлено
                pnl_total = 0.0
                daily_freq = avg_trades_per_day
                
                # Парсим дату последней сделки
                last_trade_at = None
                if last_trade_date:
                    try:
                        # Формат: 2025-10-08 15:01:28+00:00
                        dt = datetime.fromisoformat(last_trade_date.replace('+00:00', ''))
                        last_trade_at = dt.isoformat()
                    except Exception:
                        pass
                
                # Добавляем в БД
                success = db.upsert_wallet(
                    address=address,
                    display=address[:10] + "...",
                    traded=total_trades,
                    win_rate=win_rate,
                    pnl_total=pnl_total,
                    daily_freq=daily_freq,
                    source="csv_filtered_import",
                    last_trade_at=last_trade_at
                )
                
                if success:
                    added_count += 1
                    if added_count % 100 == 0:
                        logger.info(f"Added {added_count} wallets...")
                else:
                    skipped_count += 1
                    
            except Exception as e:
                logger.error(f"Error processing {address}: {e}")
                skipped_count += 1
                continue
    
    logger.info(f"\n{'='*70}")
    logger.info(f"✅ Добавлено: {added_count} кошельков")
    logger.info(f"⏭️  Пропущено: {skipped_count} кошельков")
    logger.info(f"{'='*70}")

if __name__ == "__main__":
    main()

