#!/usr/bin/env python3
"""
Check for REAL consensus (different wallets) in last 6 hours
"""

from db import PolymarketDB
from datetime import datetime, timezone, timedelta
import requests
from collections import defaultdict

db = PolymarketDB()
six_hours_ago = datetime.now(timezone.utc) - timedelta(hours=6)

tracked_wallets = db.get_tracked_wallets(
    min_trades=6, max_trades=1000, 
    min_win_rate=0.75, max_win_rate=1.0, 
    max_daily_freq=20.0, limit=2000
)

print(f"📊 Проверяю РЕАЛЬНЫЙ консенсус (РАЗНЫЕ кошельки) за последние 6 часов...")
print(f"Отслеживаемых кошельков: {len(tracked_wallets)}")
print()

market_trades = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
checked = 0

for wallet in tracked_wallets[:200]:  # Check first 200
    try:
        url = "https://data-api.polymarket.com/trades"
        response = requests.get(url, params={"user": wallet, "limit": 10}, timeout=8)
        
        if response.ok:
            trades = response.json()
            for trade in trades:
                timestamp = trade.get("timestamp")
                if timestamp:
                    if isinstance(timestamp, str):
                        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    elif isinstance(timestamp, (int, float)):
                        dt = datetime.fromtimestamp(timestamp / 1000 if timestamp > 1e10 else timestamp, tz=timezone.utc)
                    else:
                        continue
                    
                    if dt >= six_hours_ago:
                        condition_id = trade.get("conditionId")
                        outcome_index = trade.get("outcomeIndex")
                        side = trade.get("side", "BUY")
                        
                        if condition_id and outcome_index is not None:
                            key = (condition_id, outcome_index, side)
                            market_trades[key]["wallets"].append({
                                "wallet": wallet,
                                "timestamp": dt,
                                "price": trade.get("price", 0)
                            })
        checked += 1
        if checked % 50 == 0:
            print(f"   Проверено {checked}/200...")
    except:
        pass

print()
print(f"✅ Проверено кошельков: {checked}")
print()

# Find REAL consensus (different wallets)
real_consensus = []
for (condition_id, outcome_index, side), data in market_trades.items():
    # Get unique wallets
    unique_wallets = {}
    for trade in data["wallets"]:
        wallet = trade["wallet"]
        if wallet not in unique_wallets:
            unique_wallets[wallet] = trade
        else:
            # Keep earliest trade per wallet
            if trade["timestamp"] < unique_wallets[wallet]["timestamp"]:
                unique_wallets[wallet] = trade
    
    if len(unique_wallets) >= 2:
        trades_list = list(unique_wallets.values())
        trades_list.sort(key=lambda x: x["timestamp"])
        first_time = trades_list[0]["timestamp"]
        last_time = trades_list[-1]["timestamp"]
        window_minutes = (last_time - first_time).total_seconds() / 60
        
        if window_minutes <= 15:
            real_consensus.append({
                "condition_id": condition_id,
                "outcome_index": outcome_index,
                "side": side,
                "wallet_count": len(unique_wallets),
                "window_minutes": window_minutes,
                "wallets": list(unique_wallets.keys()),
                "first_trade": first_time,
                "last_trade": last_time
            })

if real_consensus:
    print(f"🎯 НАЙДЕНО {len(real_consensus)} РЕАЛЬНЫХ КОНСЕНСУСОВ (разные кошельки):")
    print()
    for i, consensus in enumerate(real_consensus, 1):
        print(f"{i}. Маркет: {consensus['condition_id'][:40]}...")
        print(f"   Исход: {consensus['outcome_index']} | Сторона: {consensus['side']}")
        print(f"   Кошельков: {consensus['wallet_count']}")
        print(f"   Окно: {consensus['window_minutes']:.1f} минут")
        print(f"   Время: {consensus['first_trade'].strftime('%H:%M:%S')} - {consensus['last_trade'].strftime('%H:%M:%S')}")
        print(f"   Кошельки:")
        for w in consensus['wallets']:
            print(f"      - {w[:20]}...")
        
        # Check if bot processed
        with db.get_connection() as conn:
            cursor = conn.cursor()
            key_hash = db.sha(f"{consensus['condition_id']}:{consensus['outcome_index']}:{consensus['side']}")
            cursor.execute("SELECT data, updated_at FROM rolling_buys WHERE k = ?", (key_hash,))
            window_row = cursor.fetchone()
            
            if window_row:
                print(f"   ✅ Rolling window существует")
            else:
                print(f"   ❌ Rolling window НЕ существует - бот не обработал!")
            
            cursor.execute("""
                SELECT sent_at, wallet_count FROM alerts_sent
                WHERE condition_id LIKE ? AND outcome_index = ?
                ORDER BY sent_at DESC LIMIT 1
            """, (f"{consensus['condition_id']}%", consensus['outcome_index']))
            alert_row = cursor.fetchone()
            
            if alert_row:
                print(f"   ✅ Алерт отправлен: {alert_row[0]} | Кошельков: {alert_row[1]}")
            else:
                print(f"   ❌ Алерт НЕ отправлен")
        print()
else:
    print("❌ РЕАЛЬНЫЙ консенсус (разные кошельки) НЕ найден за последние 6 часов")

