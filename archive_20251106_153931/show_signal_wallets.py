#!/usr/bin/env python3
"""Show wallet details from the last signal"""
import sqlite3
import json

db_path = "polymarket_notifier.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Найдем последний алерт с деталями
cursor.execute("""
    SELECT condition_id, outcome_index, wallet_count, side, price, wallet_details_json, sent_at
    FROM alerts_sent
    WHERE wallet_details_json IS NOT NULL AND wallet_details_json != ''
    ORDER BY sent_at DESC
    LIMIT 5
""")

alerts = cursor.fetchall()

if not alerts:
    print("❌ Не найдено алертов с деталями кошельков")
else:
    print(f"✅ Найдено {len(alerts)} алертов с деталями:\n")
    
    for idx, alert in enumerate(alerts, 1):
        print(f"{'='*70}")
        print(f"Сигнал #{idx}")
        print(f"{'='*70}")
        print(f"Condition ID: {alert['condition_id'][:50]}...")
        print(f"Outcome: {alert['outcome_index']} ({alert['side']})")
        print(f"Wallet count: {alert['wallet_count']}")
        print(f"Current price: ${alert['price']:.4f}" if alert['price'] else "Current price: N/A")
        print(f"Sent at: {alert['sent_at']}")
        print()
        
        try:
            wallet_details = json.loads(alert['wallet_details_json'])
            
            print("📋 Детали по кошелькам:\n")
            
            total_usd = 0
            for i, detail in enumerate(wallet_details, 1):
                wallet = detail.get('wallet', '')
                usd_amount = detail.get('usd_amount', 0)
                price = detail.get('price', 0)
                
                total_usd += usd_amount
                
                # Получим WR и trades из таблицы wallets
                cursor.execute("SELECT win_rate, traded_total FROM wallets WHERE address = ?", (wallet,))
                wallet_data = cursor.fetchone()
                
                wr_info = ""
                if wallet_data:
                    wr = wallet_data['win_rate'] * 100 if wallet_data['win_rate'] else None
                    trades = wallet_data['traded_total']
                    wr_info = f" • WR: {wr:.1f}% ({trades} trades)" if wr else ""
                
                print(f"{i}. {wallet}")
                print(f"   💵 Позиция: ${usd_amount:,.2f} USDC")
                print(f"   📈 Цена входа: ${price:.4f}{wr_info}")
                print()
            
            print(f"💰 Общая сумма позиции: ${total_usd:,.2f} USDC")
            print()
        except Exception as e:
            print(f"❌ Ошибка парсинга деталей: {e}")
            print(f"Raw JSON: {alert['wallet_details_json'][:200]}...")
            print()

conn.close()

