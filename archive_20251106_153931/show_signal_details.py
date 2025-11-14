#!/usr/bin/env python3
"""Show details of the last sent signal"""
import sqlite3
import json
from datetime import datetime, timedelta

db_path = "polymarket_notifier.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Найдем последние алерты за последние 24 часа
cursor.execute("""
    SELECT alert_key, condition_id, outcome_index, wallet_count, price, wallets_csv, sent_at, side
    FROM alerts_sent
    WHERE sent_at > datetime('now', '-24 hours')
    ORDER BY sent_at DESC
    LIMIT 10
""")

alerts = cursor.fetchall()
print(f"Найдено {len(alerts)} алертов за последние 24 часа:\n")

for idx, alert in enumerate(alerts, 1):
    condition_id = alert['condition_id']
    outcome_index = alert['outcome_index']
    wallet_count = alert['wallet_count']
    side = alert.get('side', 'BUY')
    
    print(f"{idx}. Condition: {condition_id[:50]}...")
    print(f"   Outcome: {outcome_index} ({side})")
    print(f"   Wallets: {wallet_count}")
    print(f"   Sent at: {alert['sent_at']}")
    
    # Найдем детали в rolling_buys
    cursor.execute("SELECT k, data, updated_at FROM rolling_buys")
    windows = cursor.fetchall()
    
    best_match = None
    best_events = None
    
    for window in windows:
        try:
            data_json = json.loads(window['data'])
            events = data_json.get('events', [])
            
            # Проверим, есть ли событие с нужным condition_id и outcome_index
            matching_events = [
                e for e in events 
                if e.get('conditionId') == condition_id and 
                   e.get('outcomeIndex') == outcome_index
            ]
            
            if matching_events and len(matching_events) >= wallet_count:
                if best_match is None or len(matching_events) > len(best_events):
                    best_match = window
                    best_events = matching_events
        except Exception:
            continue
    
    if best_match and best_events:
        print(f"   ✅ Найдены детали!")
        
        wallets_info = {}
        total_usd = 0
        
        for event in best_events:
            wallet = event.get('wallet', '')
            usd = float(event.get('usd_amount', 0) or 0)
            quantity = float(event.get('quantity', 0) or 0)
            price = float(event.get('price', 0) or 0)
            
            # Если usd_amount нет, считаем из quantity * price
            if usd == 0 and quantity > 0 and price > 0:
                usd = quantity * price
            
            if wallet:
                if wallet not in wallets_info:
                    wallets_info[wallet] = {
                        'total_usd': 0,
                        'price': price,
                        'events': 0
                    }
                wallets_info[wallet]['total_usd'] += usd
                wallets_info[wallet]['events'] += 1
                total_usd += usd
        
        print(f"\n   📊 Общая сумма позиции: ${total_usd:,.2f} USDC\n")
        print("   👤 Детали по кошелькам:")
        
        # Получим win_rate и trades из таблицы wallets
        for wallet, info in sorted(wallets_info.items(), key=lambda x: x[1]['total_usd'], reverse=True):
            cursor.execute("SELECT win_rate, traded_total FROM wallets WHERE address = ?", (wallet,))
            wallet_data = cursor.fetchone()
            
            wr = wallet_data['win_rate'] if wallet_data else None
            trades = wallet_data['traded_total'] if wallet_data else None
            
            wr_str = f"WR: {wr*100:.1f}% ({trades} trades)" if wr and trades else "WR: N/A"
            
            print(f"      {wallet}")
            print(f"         💰 Позиция: ${info['total_usd']:,.2f} USDC")
            print(f"         📈 Цена входа: ${info['price']:.3f}")
            print(f"         ⭐ {wr_str}")
            print()
        
        break  # Показываем только первый найденный
    else:
        print(f"   ❌ Детали не найдены в rolling_buys")
    print()

conn.close()

