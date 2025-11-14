#!/usr/bin/env python3
"""
Check and update wallets without last_trade_at timestamp
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import PolymarketDB
from datetime import datetime, timezone, timedelta
from typing import Optional
import requests
import time
from dotenv import load_dotenv

load_dotenv()

def get_last_trade_timestamp(address: str) -> Optional[str]:
    """Fetch last trade timestamp from Polymarket API"""
    try:
        url = "https://data-api.polymarket.com/trades"
        response = requests.get(url, params={"user": address, "limit": 1}, timeout=10)
        
        if response.ok:
            trades = response.json()
            if trades and len(trades) > 0:
                trade = trades[0]
                timestamp = trade.get("timestamp")
                return timestamp
        return None
    except requests.exceptions.Timeout:
        return None
    except Exception as e:
        print(f"   ⚠️  Ошибка API для {address[:20]}...: {e}")
        return None

def check_missing_last_trade():
    """Check and update wallets without last_trade_at"""
    db = PolymarketDB()
    three_months_ago = datetime.now(timezone.utc) - timedelta(days=90)
    
    # Get wallets without last_trade_at
    wallets = []
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT address FROM wallets WHERE last_trade_at IS NULL")
        wallets = [row[0] for row in cursor.fetchall()]
    
    print(f"📊 Найдено {len(wallets)} кошельков без last_trade_at")
    print()
    
    updated_count = 0
    deleted_count = 0
    no_trades_count = 0
    error_count = 0
    
    # Process all wallets within a single connection context
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        for i, address in enumerate(wallets, 1):
            if i % 10 == 0:
                print(f"   Обработано {i}/{len(wallets)}...")
            
            try:
                # Fetch last trade timestamp
                last_trade_at = get_last_trade_timestamp(address)
                
                if last_trade_at:
                    try:
                        dt = datetime.fromisoformat(last_trade_at.replace("Z", "+00:00"))
                        age_days = (datetime.now(timezone.utc) - dt).days
                        
                        # Update last_trade_at in database
                        cursor.execute("UPDATE wallets SET last_trade_at = ? WHERE address = ?", 
                                     (last_trade_at, address))
                        updated_count += 1
                        
                        if dt < three_months_ago:
                            # Delete inactive wallet
                            cursor.execute("DELETE FROM wallets WHERE address = ?", (address,))
                            deleted_count += 1
                            print(f"   ❌ Удален {address[:20]}... (последняя сделка: {dt.strftime('%Y-%m-%d')}, {age_days} дней назад)")
                        else:
                            print(f"   ✅ Обновлен {address[:20]}... (последняя сделка: {dt.strftime('%Y-%m-%d')}, {age_days} дней назад)")
                    except Exception as e:
                        print(f"   ⚠️  Ошибка обработки {address[:20]}...: {e}")
                        error_count += 1
                else:
                    # No trades found - delete wallet
                    cursor.execute("DELETE FROM wallets WHERE address = ?", (address,))
                    no_trades_count += 1
                    deleted_count += 1
                    print(f"   🗑️  Удален {address[:20]}... (нет сделок)")
                
                # Commit every 20 wallets
                if i % 20 == 0:
                    conn.commit()
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                print(f"   ❌ Критическая ошибка для {address[:20]}...: {e}")
                error_count += 1
        
        conn.commit()
        
        # Final stats
        cursor.execute("SELECT COUNT(*) FROM wallets WHERE last_trade_at IS NULL")
        remaining_null = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM wallets")
        total_wallets = cursor.fetchone()[0]
    
    print()
    print(f"✅ Проверка завершена:")
    print(f"   Обновлено last_trade_at: {updated_count}")
    print(f"   Удалено (нет сделок): {no_trades_count}")
    print(f"   Удалено (неактивных): {deleted_count - no_trades_count}")
    print(f"   Всего удалено: {deleted_count}")
    print(f"   Ошибок: {error_count}")
    
    print()
    print(f"📊 Итоговая статистика:")
    print(f"   Осталось без last_trade_at: {remaining_null}")
    print(f"   Всего кошельков в базе: {total_wallets}")

if __name__ == "__main__":
    check_missing_last_trade()

