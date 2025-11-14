#!/usr/bin/env python3
"""Show details of the last signal"""
import sqlite3
import json

db_path = "polymarket_notifier.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Найдем последний алерт
cursor.execute("""
    SELECT alert_key, condition_id, outcome_index, wallet_count, price, wallets_csv, sent_at
    FROM alerts_sent
    ORDER BY sent_at DESC
    LIMIT 1
""")

alert = cursor.fetchone()
if alert:
    print("Последний сигнал:")
    print(f"Condition ID: {alert['condition_id']}")
    print(f"Outcome: {alert['outcome_index']}")
    print(f"Wallet count: {alert['wallet_count']}")
    print(f"Price: {alert['price']}")
    print(f"Wallets CSV: {alert['wallets_csv']}")
    print(f"Sent at: {alert['sent_at']}")
    print()
    
    # Теперь найдем детали из rolling_buys
    condition_id = alert['condition_id']
    outcome_index = alert['outcome_index']
    
    # Найдем все окна с этим condition_id
    cursor.execute("SELECT k, data, updated_at FROM rolling_buys")
    windows = cursor.fetchall()
    
    best_match = None
    best_event_count = 0
    
    for window in windows:
        try:
            data_json = json.loads(window['data'])
            events = data_json.get('events', [])
            
            # Проверим, есть ли событие с нужным condition_id и outcome_index
            for event in events:
                if event.get('conditionId') == condition_id and event.get('outcomeIndex') == outcome_index:
                    if len(events) > best_event_count:
                        best_event_count = len(events)
                        best_match = (window, data_json)
                    break
        except Exception:
            continue
    
    if best_match:
        window, data_json = best_match
        events = data_json.get('events', [])
        
        print(f"Найдено окно с {len(events)} событиями:")
        print(f"Updated at: {window['updated_at']}")
        print()
        
        wallets_info = {}
        total_usd = 0
        
        for event in events:
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
        
        print(f"Общая сумма позиции: ${total_usd:,.2f} USDC\n")
        print("Детали по кошелькам:")
        
        # Получим win_rate и trades из таблицы wallets
        for wallet, info in wallets_info.items():
            cursor.execute("SELECT win_rate, traded_total FROM wallets WHERE address = ?", (wallet,))
            wallet_data = cursor.fetchone()
            
            wr = wallet_data['win_rate'] if wallet_data else None
            trades = wallet_data['traded_total'] if wallet_data else None
            
            wr_str = f"WR: {wr*100:.1f}% ({trades} trades)" if wr and trades else "WR: N/A"
            
            print(f"  {wallet}")
            print(f"    Позиция: ${info['total_usd']:,.2f} USDC")
            print(f"    Цена входа: ${info['price']:.3f}")
            print(f"    {wr_str}")
            print()
    else:
        print("Не найдено деталей в rolling_buys")
else:
    print("Не найдено алертов в базе")

conn.close()

