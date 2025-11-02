#!/usr/bin/env python3
"""Check last signal details"""
import sqlite3
import json

db = sqlite3.connect("polymarket_notifier.db")
cursor = db.cursor()

# Проверим все алерты с деталями
cursor.execute("""
    SELECT condition_id, outcome_index, wallet_count, sent_at, wallet_details_json
    FROM alerts_sent
    WHERE wallet_details_json IS NOT NULL AND wallet_details_json != ""
    ORDER BY sent_at DESC
    LIMIT 5
""")

alerts_with_details = cursor.fetchall()

if alerts_with_details:
    print(f"Найдено {len(alerts_with_details)} алертов с деталями:\n")
    
    for condition_id, outcome_index, wallet_count, sent_at, wallet_details_json in alerts_with_details:
        print(f"Sent: {sent_at}, Wallets: {wallet_count}")
        try:
            details = json.loads(wallet_details_json)
            print(f"  Детали: {len(details)} кошельков\n")
            
            total_usd = 0
            for i, d in enumerate(details, 1):
                wallet = d.get("wallet", "")
                usd_amount = d.get("usd_amount", 0)
                price = d.get("price", 0)
                total_usd += usd_amount
                
                # Получим WR и trades
                cursor.execute("SELECT win_rate, traded_total FROM wallets WHERE address = ?", (wallet,))
                wallet_data = cursor.fetchone()
                
                wr_info = ""
                if wallet_data:
                    wr = wallet_data[0] * 100 if wallet_data[0] else None
                    trades = wallet_data[1]
                    wr_info = f" • WR: {wr:.1f}% ({trades} trades)" if wr else ""
                
                wallet_short = f"{wallet[:5]}.......{wallet[-3:]}" if len(wallet) > 10 else wallet
                print(f"  {i}. {wallet_short}")
                print(f"     💵 Позиция: ${usd_amount:,.2f} USDC")
                print(f"     📈 Цена входа: ${price:.3f}{wr_info}")
                print()
            
            print(f"  📊 Общая сумма: ${total_usd:,.2f} USDC")
            print()
        except Exception as e:
            print(f"  Ошибка: {e}")
            print()
else:
    print("Нет алертов с сохраненными деталями кошельков")
    print("Новые алерты с момента добавления функции еще не отправлялись")

db.close()

