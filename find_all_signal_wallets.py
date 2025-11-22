#!/usr/bin/env python3
"""
Комплексный поиск всех кошельков из сигнала Warriors vs Pelicans
Ищет по всем возможным источникам и вариантам
"""
import sqlite3
import json
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Set

def search_in_database() -> Set[str]:
    """Поиск во всех таблицах базы данных"""
    patterns = [
        ('0x4e7', '823'),
        ('0x97e', 'a30'),
        ('0xdb2', '56e')
    ]
    
    found = set()
    db = sqlite3.connect('polymarket_notifier.db')
    cursor = db.cursor()
    
    # 1. alerts_sent
    cursor.execute('SELECT wallets_csv, wallet_details_json FROM alerts_sent')
    for wallets_csv, wallet_details_json in cursor.fetchall():
        if wallets_csv:
            for wallet in wallets_csv.split(','):
                wallet = wallet.strip().lower()
                for prefix, suffix in patterns:
                    if wallet.startswith(prefix.lower()) and wallet.endswith(suffix.lower()):
                        found.add(wallet)
        
        if wallet_details_json:
            try:
                details = json.loads(wallet_details_json)
                for detail in details:
                    wallet = detail.get('wallet', '').lower().strip()
                    if wallet:
                        for prefix, suffix in patterns:
                            if wallet.startswith(prefix.lower()) and wallet.endswith(suffix.lower()):
                                found.add(wallet)
            except:
                pass
    
    # 2. rolling_buys
    cursor.execute('SELECT data FROM rolling_buys')
    for (data_str,) in cursor.fetchall():
        try:
            data = json.loads(data_str)
            events = data.get('events', [])
            for event in events:
                wallet = event.get('wallet', '').lower().strip()
                if wallet:
                    for prefix, suffix in patterns:
                        if wallet.startswith(prefix.lower()) and wallet.endswith(suffix.lower()):
                            found.add(wallet)
        except:
            pass
    
    # 3. wallets table
    cursor.execute('SELECT address FROM wallets')
    for (address,) in cursor.fetchall():
        wallet = address.lower().strip()
        for prefix, suffix in patterns:
            if wallet.startswith(prefix.lower()) and wallet.endswith(suffix.lower()):
                found.add(wallet)
    
    db.close()
    return found

def search_in_files() -> Set[str]:
    """Поиск в текстовых файлах"""
    import os
    import re
    
    patterns = [
        ('0x4e7', '823'),
        ('0x97e', 'a30'),
        ('0xdb2', '56e')
    ]
    
    found = set()
    
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'archive_20251106_153931']]
        
        for file in files:
            if file.endswith(('.txt', '.log', '.csv')):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            addresses = re.findall(r'0x[a-fA-F0-9]{40}', line)
                            for addr in addresses:
                                addr_lower = addr.lower()
                                for prefix, suffix in patterns:
                                    if addr_lower.startswith(prefix.lower()) and addr_lower.endswith(suffix.lower()):
                                        found.add(addr_lower)
                except:
                    pass
    
    return found

def get_recent_alerts_with_market_info() -> List[dict]:
    """Получить недавние алерты и попытаться найти Warriors/Pelicans"""
    db = sqlite3.connect('polymarket_notifier.db')
    cursor = db.cursor()
    
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    cursor.execute('''
        SELECT condition_id, sent_at, wallets_csv, wallet_details_json
        FROM alerts_sent
        WHERE sent_at >= ?
        ORDER BY sent_at DESC
        LIMIT 100
    ''', (week_ago,))
    
    alerts = []
    for condition_id, sent_at, wallets_csv, wallet_details_json in cursor.fetchall():
        # Пробуем получить название рынка
        try:
            url = f'https://clob.polymarket.com/markets/{condition_id}'
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                title = (data.get('question') or data.get('title') or '').lower()
                if 'warriors' in title or 'pelicans' in title:
                    alerts.append({
                        'condition_id': condition_id,
                        'title': data.get('question') or data.get('title'),
                        'sent_at': sent_at,
                        'wallets_csv': wallets_csv,
                        'wallet_details_json': wallet_details_json
                    })
        except:
            pass
    
    db.close()
    return alerts

def main():
    print("="*70)
    print("КОМПЛЕКСНЫЙ ПОИСК КОШЕЛЬКОВ ИЗ СИГНАЛА WARRIORS VS PELICANS")
    print("="*70)
    
    patterns = [
        ('0x4e7', '823'),
        ('0x97e', 'a30'),
        ('0xdb2', '56e')
    ]
    
    all_found = set()
    
    # 1. Поиск в базе данных
    print("\n1. Поиск в базе данных...")
    db_found = search_in_database()
    if db_found:
        print(f"   ✅ Найдено {len(db_found)} адресов в БД")
        all_found.update(db_found)
    else:
        print("   ⚠️  Не найдено в БД")
    
    # 2. Поиск в файлах
    print("\n2. Поиск в файлах проекта...")
    file_found = search_in_files()
    if file_found:
        print(f"   ✅ Найдено {len(file_found)} адресов в файлах")
        all_found.update(file_found)
    else:
        print("   ⚠️  Не найдено в файлах")
    
    # 3. Поиск через недавние алерты
    print("\n3. Поиск через недавние алерты...")
    alerts = get_recent_alerts_with_market_info()
    if alerts:
        print(f"   ✅ Найдено {len(alerts)} алертов с Warriors/Pelicans")
        for alert in alerts:
            print(f"   Рынок: {alert['title']}")
            print(f"   Condition ID: {alert['condition_id']}")
            if alert['wallets_csv']:
                wallets = alert['wallets_csv'].split(',')
                print(f"   Кошельки: {len(wallets)}")
                for wallet in wallets:
                    wallet = wallet.strip().lower()
                    for prefix, suffix in patterns:
                        if wallet.startswith(prefix.lower()) and wallet.endswith(suffix.lower()):
                            all_found.add(wallet)
    else:
        print("   ⚠️  Не найдено алертов с Warriors/Pelicans")
    
    # Итоги
    print("\n" + "="*70)
    print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ:")
    print("="*70)
    
    if all_found:
        print(f"\n✅ Найдено {len(all_found)} адресов:")
        for i, addr in enumerate(sorted(all_found), 1):
            print(f"{i}. {addr}")
        
        # Группируем по паттернам
        print("\n" + "="*70)
        print("ГРУППИРОВКА ПО ПАТТЕРНАМ:")
        print("="*70)
        
        for prefix, suffix in patterns:
            matching = [addr for addr in all_found if addr.startswith(prefix.lower()) and addr.endswith(suffix.lower())]
            if matching:
                print(f"\n✅ {prefix}...{suffix}:")
                for addr in matching:
                    print(f"   {addr}")
            else:
                print(f"\n⚠️  {prefix}...{suffix}: не найдено")
        
        # Сохраняем в файл
        output_file = f"warriors_pelicans_wallets_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
        with open(output_file, 'w') as f:
            f.write("Адреса кошельков из сигнала Warriors vs Pelicans:\n")
            f.write(f"Дата поиска: {datetime.now(timezone.utc).isoformat()}\n\n")
            for addr in sorted(all_found):
                f.write(f"{addr}\n")
        print(f"\n✅ Адреса сохранены в файл: {output_file}")
    else:
        print("\n⚠️  Адреса с нужными паттернами не найдены")
        print("\nВывод:")
        print("  - Это был тестовый сигнал, адреса не сохранялись")
        print("  - Или адреса находятся в другом источнике данных")
        print("  - Или данные были очищены/удалены")

if __name__ == "__main__":
    main()

