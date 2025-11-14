#!/usr/bin/env python3
"""
Check consensus for 3 active wallets
"""

import requests
from datetime import datetime, timezone, timedelta
from collections import defaultdict

six_hours_ago = datetime.now(timezone.utc) - timedelta(hours=6)

# Три активных кошелька
active_wallets = [
    "0xb744f56635b537e859152d14b022af5afe485210",
    "0x3657862e57070b82a289b5887ec943a7c2166d14",
    "0xd38b71f3e8ed1af7198b5a7da2fdf239b51b5e9c"
]

market_trades = defaultdict(list)

print(f"Проверяю сделки от 3 активных кошельков за последние 6 часов...")
print()

for wallet in active_wallets:
    try:
        url = "https://data-api.polymarket.com/trades"
        response = requests.get(url, params={"user": wallet, "limit": 20}, timeout=10)
        
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
    except Exception as e:
        print(f"Ошибка для {wallet[:20]}...: {e}")

print(f"Найдено сделок: {sum(len(trades) for trades in market_trades.values())}")
print()

# Ищем консенсус
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
                print(f"🎯 НАЙДЕН КОНСЕНСУС!")
                print(f"   Маркет: {condition_id[:40]}...")
                print(f"   Исход: {outcome_index} | Сторона: {side}")
                print(f"   Кошельков: {len(trade_list)}")
                print(f"   Окно: {window_minutes:.1f} минут")
                print(f"   Время: {first_time.strftime('%Y-%m-%d %H:%M:%S')} - {last_time.strftime('%H:%M:%S')}")
                print(f"   Кошельки:")
                for t in trade_list:
                    print(f"      - {t['wallet'][:20]}... @ {t['timestamp'].strftime('%H:%M:%S')} (${t['price']:.3f})")
                print()

if not consensus_found:
    print("❌ Консенсус не найден")
    print()
    print("Детали по маркетам:")
    for condition_id, trades in market_trades.items():
        print(f"   Маркет {condition_id[:30]}...: {len(trades)} сделок")
        for trade in trades:
            print(f"      - {trade['wallet'][:20]}... | {trade['timestamp'].strftime('%H:%M:%S')} | Исход {trade['outcome_index']} | {trade['side']}")

