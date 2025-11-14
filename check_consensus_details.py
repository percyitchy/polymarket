#!/usr/bin/env python3
"""
Detailed check of consensus cases
"""

import requests
from datetime import datetime, timezone, timedelta
from db import PolymarketDB

six_hours_ago = datetime.now(timezone.utc) - timedelta(hours=6)

# Консенсус #1
market1 = "0xa74676c5c145b66b8c280b4ef37d34f635c34e"
wallets1 = [
    "0xb744f56635b537e859152d14b022af5afe485210",
    "0x3657862e57070b82a289b5887ec943a7c2166d14",
    "0xd38b71f3e8ed1af7198b5a7da2fdf239b51b5e9c"
]

print("=== КОНСЕНСУС #1 ===")
print(f"Маркет: {market1}")
print()

for wallet in wallets1:
    try:
        url = "https://data-api.polymarket.com/trades"
        response = requests.get(url, params={"user": wallet, "limit": 10}, timeout=10)
        
        if response.ok:
            trades = response.json()
            for trade in trades:
                condition_id = trade.get("conditionId", "")
                if market1.lower() in condition_id.lower():
                    timestamp = trade.get("timestamp")
                    if timestamp:
                        if isinstance(timestamp, str):
                            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        elif isinstance(timestamp, (int, float)):
                            dt = datetime.fromtimestamp(timestamp / 1000 if timestamp > 1e10 else timestamp, tz=timezone.utc)
                        else:
                            continue
                        
                        if dt >= six_hours_ago:
                            print(f"{wallet[:20]}...:")
                            print(f"   Время: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                            print(f"   Исход: {trade.get('outcomeIndex')} | Сторона: {trade.get('side')}")
                            print(f"   Цена: ${trade.get('price', 0)}")
                            print(f"   Trade ID: {trade.get('tradeId', 'N/A')[:20]}...")
                            print()
                            break
    except Exception as e:
        print(f"Ошибка для {wallet[:20]}...: {e}")

# Проверяю статус маркета
try:
    url = f"https://clob.polymarket.com/markets/{market1}"
    response = requests.get(url, timeout=10)
    if response.ok:
        data = response.json()
        print(f"Статус маркета:")
        print(f"   Active: {data.get('active', True)}")
        print(f"   Closed: {data.get('closed', False)}")
        print(f"   Resolved: {data.get('resolved', False)}")
        outcomes = data.get("outcomes", [])
        for i, outcome in enumerate(outcomes):
            print(f"   Исход {i}: ${outcome.get('price', 0):.3f}")
        
        # Проверяю, был ли алерт
        db = PolymarketDB()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sent_at, wallet_count, side FROM alerts_sent
                WHERE condition_id LIKE ?
                ORDER BY sent_at DESC
                LIMIT 1
            """, (f"{market1}%",))
            alert = cursor.fetchone()
            if alert:
                print(f"   ✅ Алерт отправлен: {alert[0]} | Кошельков: {alert[1]} | Сторона: {alert[2]}")
            else:
                print(f"   ❌ Алерт НЕ отправлен")
except Exception as e:
    print(f"Ошибка проверки маркета: {e}")

