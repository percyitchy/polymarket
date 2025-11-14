#!/usr/bin/env python3
"""
Clean up inactive wallets (last trade > 3 months ago)
"""
from db import PolymarketDB
from datetime import datetime, timezone, timedelta
import requests

db = PolymarketDB()

def get_last_trade_timestamp(address: str) -> str:
    """Get timestamp of the most recent trade for a wallet"""
    try:
        url = "https://data-api.polymarket.com/trades"
        # Use shorter timeout and retry logic
        response = requests.get(url, params={"user": address, "limit": 1}, timeout=5)
        trades = response.json() if response.ok else []
        
        if not trades:
            return None
        
        trade = trades[0]
        timestamp = trade.get("timestamp")
        
        if timestamp:
            if isinstance(timestamp, str):
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    return dt.isoformat()
                except Exception:
                    return None
            elif isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
                return dt.isoformat()
        
        return None
    except requests.exceptions.Timeout:
        print(f"   ⚠️ Timeout для {address[:20]}...")
        return None
    except Exception as e:
        print(f"   ⚠️ Ошибка для {address[:20]}...: {type(e).__name__}")
        return None

def cleanup_inactive_wallets():
    """Remove wallets with last trade > 3 months ago"""
    three_months_ago = datetime.now(timezone.utc) - timedelta(days=90)
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Get all wallets
        cursor.execute("SELECT address FROM wallets")
        all_wallets = [row[0] for row in cursor.fetchall()]
        
        print(f"📊 Проверяю {len(all_wallets)} кошельков...")
        
        inactive_count = 0
        updated_count = 0
        
        for i, address in enumerate(all_wallets, 1):
            if i % 50 == 0:
                print(f"   Обработано {i}/{len(all_wallets)}...")
            
            # Check if we already have last_trade_at
            cursor.execute("SELECT last_trade_at FROM wallets WHERE address = ?", (address,))
            row = cursor.fetchone()
            existing_last_trade = row[0] if row else None
            
            if existing_last_trade:
                try:
                    last_trade_dt = datetime.fromisoformat(existing_last_trade.replace("Z", "+00:00"))
                    if last_trade_dt < three_months_ago:
                        # Delete inactive wallet
                        cursor.execute("DELETE FROM wallets WHERE address = ?", (address,))
                        inactive_count += 1
                        print(f"   ❌ Удален {address[:20]}... (последняя сделка: {last_trade_dt.strftime('%Y-%m-%d')})")
                    continue
                except Exception:
                    pass
            
            # Fetch last trade timestamp from API
            last_trade_at = get_last_trade_timestamp(address)
            
            if last_trade_at:
                try:
                    last_trade_dt = datetime.fromisoformat(last_trade_at.replace("Z", "+00:00"))
                    
                    # Update last_trade_at in database
                    cursor.execute("UPDATE wallets SET last_trade_at = ? WHERE address = ?", 
                                 (last_trade_at, address))
                    updated_count += 1
                    
                    if last_trade_dt < three_months_ago:
                        # Delete inactive wallet
                        cursor.execute("DELETE FROM wallets WHERE address = ?", (address,))
                        inactive_count += 1
                        print(f"   ❌ Удален {address[:20]}... (последняя сделка: {last_trade_dt.strftime('%Y-%m-%d')})")
                except Exception as e:
                    print(f"   ⚠️ Ошибка обработки {address[:20]}...: {e}")
        
            # Commit every 50 wallets to avoid losing progress
            if i % 50 == 0:
                conn.commit()
        
        conn.commit()
        
        # Final count
        cursor.execute("SELECT COUNT(*) FROM wallets")
        remaining = cursor.fetchone()[0]
        
        print(f"\n✅ Очистка завершена:")
        print(f"   Удалено неактивных кошельков: {inactive_count}")
        print(f"   Обновлено last_trade_at: {updated_count}")
        print(f"   Осталось кошельков: {remaining}")

if __name__ == "__main__":
    cleanup_inactive_wallets()

