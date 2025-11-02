#!/usr/bin/env python3
"""Get signal summary from database"""
import sqlite3
import json
import re

db_path = "polymarket_notifier.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Поищем кошельки по частичным адресам
partial_addrs = {
    "0x220": None,
    "0xb74": None,
    "0xc3c": None
}

print("Поиск кошельков из сигнала:\n")

for partial in partial_addrs.keys():
    cursor.execute("SELECT address, win_rate, traded_total FROM wallets WHERE address LIKE ?", (f"{partial}%",))
    wallet = cursor.fetchone()
    if wallet:
        partial_addrs[partial] = wallet
        print(f"✅ {wallet['address']}")
        print(f"   WR: {wallet['win_rate']*100:.1f}% ({wallet['traded_total']} trades)")
    else:
        print(f"❌ Кошелек с префиксом {partial} не найден")

print("\n" + "="*70 + "\n")

# Попробуем найти в rolling_buys окна с этими кошельками
found_addresses = [w['address'] for w in partial_addrs.values() if w]

if found_addresses:
    print(f"Ищем позиции этих кошельков в последних окнах...\n")
    
    cursor.execute("SELECT k, data, updated_at FROM rolling_buys ORDER BY updated_at DESC LIMIT 50")
    windows = cursor.fetchall()
    
    for window in windows:
        try:
            data_json = json.loads(window['data'])
            events = data_json.get('events', [])
            
            # Проверим, есть ли среди событий наши кошельки
            matching_events = [
                e for e in events 
                if e.get('wallet') in found_addresses
            ]
            
            if len(matching_events) >= 2:  # Если найдено минимум 2 из 3
                print(f"📊 Найдено окно с позициями:")
                print(f"   Updated: {window['updated_at']}\n")
                
                wallets_info = {}
                total_usd = 0
                
                for event in matching_events:
                    wallet = event.get('wallet', '')
                    usd = float(event.get('usd_amount', 0) or 0)
                    quantity = float(event.get('quantity', 0) or 0)
                    price = float(event.get('price', 0) or 0)
                    
                    if usd == 0 and quantity > 0 and price > 0:
                        usd = quantity * price
                    
                    if wallet and wallet in found_addresses:
                        if wallet not in wallets_info:
                            wallets_info[wallet] = {
                                'total_usd': 0,
                                'price': price,
                                'count': 0
                            }
                        wallets_info[wallet]['total_usd'] += usd
                        wallets_info[wallet]['count'] += 1
                        total_usd += usd
                
                if total_usd > 10000:
                    print(f"💰 Общая сумма: ${total_usd:,.2f} USDC\n")
                    print("📋 Детали по кошелькам:")
                    
                    for wallet_addr, info in sorted(wallets_info.items(), key=lambda x: x[1]['total_usd'], reverse=True):
                        wallet_data = partial_addrs.get(wallet_addr[:6])
                        wr_info = ""
                        if wallet_data:
                            wr_info = f" • WR: {wallet_data['win_rate']*100:.1f}% ({wallet_data['traded_total']} trades)"
                        
                        print(f"   {wallet_addr}")
                        print(f"      💵 Позиция: ${info['total_usd']:,.2f} USDC")
                        print(f"      📈 Цена входа: ${info['price']:.3f}{wr_info}")
                        print()
                    
                    break
        except Exception:
            continue

conn.close()

