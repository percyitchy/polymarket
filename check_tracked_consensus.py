#!/usr/bin/env python3
"""
Check consensus only among tracked wallets
"""

from db import PolymarketDB
from datetime import datetime, timezone, timedelta
import requests
from collections import defaultdict
import json

db = PolymarketDB()
six_hours_ago = datetime.now(timezone.utc) - timedelta(hours=6)

# Get tracked wallets
tracked_wallets = db.get_tracked_wallets(
    min_trades=6, max_trades=1000, 
    min_win_rate=0.75, max_win_rate=1.0, 
    max_daily_freq=20.0, limit=2000
)

print(f"📊 Отслеживаемых кошельков: {len(tracked_wallets)}")
print(f"⏰ Проверяю сделки ТОЛЬКО от отслеживаемых кошельков за последние 6 часов...")
print()

market_trades = defaultdict(list)
checked = 0

for wallet in tracked_wallets[:100]:  # Check first 100
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
                            market_trades[condition_id].append({
                                "wallet": wallet,
                                "timestamp": dt,
                                "outcome_index": outcome_index,
                                "side": side,
                                "price": trade.get("price", 0)
                            })
        checked += 1
        if checked % 20 == 0:
            print(f"   Проверено {checked}/100...")
    except:
        pass

print()
print(f"✅ Проверено кошельков: {checked}")
print(f"📈 Найдено сделок: {sum(len(trades) for trades in market_trades.values())}")
print(f"📊 Маркетов с сделками: {len(market_trades)}")
print()

# Find consensus (2+ tracked wallets on same market)
consensus_found = False
for condition_id, trades in market_trades.items():
    by_outcome_side = defaultdict(list)
    for trade in trades:
        key = (trade["outcome_index"], trade["side"])
        by_outcome_side[key].append(trade)
    
    for (outcome_index, side), trade_list in by_outcome_side.items():
        if len(trade_list) >= 2:
            trade_list.sort(key=lambda x: x["timestamp"])
            first_time = trade_list[0]["timestamp"]
            last_time = trade_list[-1]["timestamp"]
            window_minutes = (last_time - first_time).total_seconds() / 60
            
            if window_minutes <= 15:
                consensus_found = True
                print(f"🎯 НАЙДЕН КОНСЕНСУС СРЕДИ ОТСЛЕЖИВАЕМЫХ!")
                print(f"   Маркет: {condition_id[:40]}...")
                print(f"   Исход: {outcome_index} | Сторона: {side}")
                print(f"   Кошельков: {len(trade_list)}")
                print(f"   Окно: {window_minutes:.1f} минут")
                print(f"   Кошельки:")
                for t in trade_list:
                    print(f"      - {t['wallet'][:20]}... @ {t['timestamp'].strftime('%H:%M:%S')}")
                print()
                
                # Check if bot processed this
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Check rolling window
                    key_hash = db.sha(f"{condition_id}:{outcome_index}:{side}")
                    cursor.execute("SELECT data, updated_at FROM rolling_buys WHERE k = ?", (key_hash,))
                    window_row = cursor.fetchone()
                    
                    if window_row:
                        print(f"   ✅ Rolling window существует (обновлено: {window_row[1]})")
                        try:
                            window_data = json.loads(window_row[0])
                            wallets_in_window = {e.get("wallet") for e in window_data.get("events", [])}
                            print(f"   Кошельков в окне бота: {len(wallets_in_window)}")
                        except:
                            pass
                    else:
                        print(f"   ❌ Rolling window НЕ существует")
                    
                    # Check alerts
                    cursor.execute("""
                        SELECT sent_at, wallet_count FROM alerts_sent
                        WHERE condition_id LIKE ? AND outcome_index = ?
                        ORDER BY sent_at DESC LIMIT 1
                    """, (f"{condition_id}%", outcome_index))
                    alert_row = cursor.fetchone()
                    
                    if alert_row:
                        print(f"   ✅ Алерт отправлен: {alert_row[0]} | Кошельков: {alert_row[1]}")
                    else:
                        print(f"   ❌ Алерт НЕ отправлен")
                print()

if not consensus_found:
    print("❌ Консенсус НЕ найден среди отслеживаемых кошельков")

