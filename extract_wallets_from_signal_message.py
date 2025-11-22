#!/usr/bin/env python3
"""
Извлечение полных адресов кошельков из текста сигнала Polymarket Alpha Bot
по сокращенным адресам (например, 0x498...04b)
"""
import re
import sqlite3
import sys
from typing import List, Set, Tuple, Optional
from db import PolymarketDB

def extract_truncated_addresses(text: str) -> List[Tuple[str, str]]:
    """
    Извлечь сокращенные адреса из текста сигнала
    Возвращает список кортежей (prefix, suffix)
    Например: ('0x498', '04b') для адреса 0x498...04b
    """
    # Паттерн для поиска сокращенных адресов: 0xXXX...XXX или 0xXXX.......XXX
    pattern = r'0x([0-9a-fA-F]{3,})\.{3,}([0-9a-fA-F]{3,})'
    matches = re.findall(pattern, text)
    
    addresses = []
    for prefix, suffix in matches:
        addresses.append((prefix.lower(), suffix.lower()))
    
    return addresses

def find_full_addresses_by_pattern(prefix: str, suffix: str, db_path: str = "polymarket_notifier.db") -> List[str]:
    """
    Найти полные адреса кошельков по префиксу и суффиксу
    Ищет в базе данных и в транзакциях через API
    """
    found_addresses = set()
    
    # Поиск в базе данных wallets
    try:
        db = sqlite3.connect(db_path)
        cursor = db.cursor()
        
        # Поиск в таблице wallets
        cursor.execute("SELECT address FROM wallets WHERE LOWER(address) LIKE ? AND LOWER(address) LIKE ?",
                      (f"{prefix}%", f"%{suffix}"))
        for row in cursor.fetchall():
            addr = row[0].lower()
            if addr.startswith(prefix.lower()) and addr.endswith(suffix.lower()):
                found_addresses.add(addr)
        
        # Поиск в таблице alerts_sent (wallets_csv)
        cursor.execute("SELECT wallets_csv FROM alerts_sent WHERE wallets_csv IS NOT NULL AND wallets_csv != ''")
        for row in cursor.fetchall():
            wallets_csv = row[0]
            if wallets_csv:
                for wallet in wallets_csv.split(','):
                    wallet = wallet.strip().lower()
                    if wallet.startswith(prefix.lower()) and wallet.endswith(suffix.lower()):
                        found_addresses.add(wallet)
        
        # Поиск в таблице market_wallets (если существует)
        try:
            cursor.execute("SELECT wallet_address FROM market_wallets WHERE LOWER(wallet_address) LIKE ? AND LOWER(wallet_address) LIKE ?",
                          (f"{prefix}%", f"%{suffix}"))
            for row in cursor.fetchall():
                addr = row[0].lower()
                if addr.startswith(prefix.lower()) and addr.endswith(suffix.lower()):
                    found_addresses.add(addr)
        except sqlite3.OperationalError:
            # Таблица может не существовать
            pass
        
        db.close()
    except Exception as e:
        print(f"⚠️  Ошибка при поиске в БД: {e}")
    
    return list(found_addresses)

def get_trades_from_api(condition_id: Optional[str] = None, market_title: Optional[str] = None) -> List[dict]:
    """
    Получить транзакции через API для поиска адресов
    """
    import requests
    
    trades = []
    
    # Если есть condition_id, получаем транзакции напрямую
    if condition_id:
        try:
            url = f"https://data-api.polymarket.com/trades"
            params = {"condition_id": condition_id, "limit": 500}
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    trades = data
                elif isinstance(data, dict):
                    trades = data.get("trades", []) or data.get("data", [])
        except Exception as e:
            print(f"⚠️  Ошибка при получении транзакций через API: {e}")
    
    return trades

def extract_addresses_from_trades(trades: List[dict], prefix: str, suffix: str) -> Set[str]:
    """Извлечь адреса из транзакций по паттерну"""
    addresses = set()
    
    for trade in trades:
        # Проверяем различные поля
        for field in ["maker", "taker", "user", "trader", "address", "wallet", "account"]:
            value = trade.get(field)
            if isinstance(value, str) and value.startswith("0x") and len(value) == 42:
                addr_lower = value.lower()
                if addr_lower.startswith(prefix.lower()) and addr_lower.endswith(suffix.lower()):
                    addresses.add(addr_lower)
        
        # Проверяем вложенные структуры
        if "user" in trade and isinstance(trade["user"], dict):
            for field in ["address", "wallet", "id"]:
                value = trade["user"].get(field)
                if isinstance(value, str) and value.startswith("0x") and len(value) == 42:
                    addr_lower = value.lower()
                    if addr_lower.startswith(prefix.lower()) and addr_lower.endswith(suffix.lower()):
                        addresses.add(addr_lower)
    
    return addresses

def save_wallets_to_db(wallets: Set[str], condition_id: Optional[str] = None, source: str = "signal_extraction"):
    """Сохранить кошельки в БД"""
    try:
        db = PolymarketDB()
        
        saved_count = 0
        for wallet in wallets:
            # Добавляем в raw_collected_wallets для дальнейшего анализа
            db.insert_raw_collected_wallet(wallet.lower(), source)
            saved_count += 1
        
        print(f"✅ Сохранено {saved_count} кошельков в БД (таблица raw_collected_wallets)")
        
        # Если есть condition_id, сохраняем также в market_wallets
        if condition_id:
            try:
                import sqlite3
                from datetime import datetime, timezone
                
                conn = sqlite3.connect(db.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS market_wallets (
                        condition_id TEXT,
                        wallet_address TEXT,
                        first_seen_at TEXT,
                        last_seen_at TEXT,
                        trade_count INTEGER DEFAULT 1,
                        PRIMARY KEY (condition_id, wallet_address)
                    )
                ''')
                
                now = datetime.now(timezone.utc).isoformat()
                for wallet in wallets:
                    cursor.execute('''
                        INSERT INTO market_wallets (condition_id, wallet_address, first_seen_at, last_seen_at, trade_count)
                        VALUES (?, ?, ?, ?, 1)
                        ON CONFLICT(condition_id, wallet_address) DO UPDATE SET
                            last_seen_at = excluded.last_seen_at,
                            trade_count = trade_count + 1
                    ''', (condition_id.lower(), wallet.lower(), now, now))
                
                conn.commit()
                conn.close()
                print(f"✅ Сохранено {len(wallets)} кошельков в таблицу market_wallets")
            except Exception as e:
                print(f"⚠️  Ошибка при сохранении в market_wallets: {e}")
        
    except Exception as e:
        print(f"⚠️  Ошибка при сохранении в БД: {e}")

def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python3 extract_wallets_from_signal_message.py '<текст сигнала>' [condition_id]")
        print("\nПример:")
        print("  python3 extract_wallets_from_signal_message.py '0x498...04b @ $0.120'")
        print("\nИли с condition_id:")
        print("  python3 extract_wallets_from_signal_message.py '<текст>' 0x1234...")
        return
    
    signal_text = sys.argv[1]
    condition_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    print("="*70)
    print("ИЗВЛЕЧЕНИЕ АДРЕСОВ КОШЕЛЬКОВ ИЗ СИГНАЛА")
    print("="*70)
    print(f"\nТекст сигнала:\n{signal_text}\n")
    
    # Извлечь сокращенные адреса
    truncated_addresses = extract_truncated_addresses(signal_text)
    
    if not truncated_addresses:
        print("⚠️  Сокращенные адреса не найдены в тексте.")
        print("Проверьте формат: адреса должны быть в формате 0xXXX...XXX")
        return
    
    print(f"✅ Найдено {len(truncated_addresses)} сокращенных адресов:")
    for prefix, suffix in truncated_addresses:
        print(f"   - 0x{prefix}...{suffix}")
    
    # Поиск полных адресов
    print("\n" + "="*70)
    print("ПОИСК ПОЛНЫХ АДРЕСОВ")
    print("="*70)
    
    all_found_addresses = set()
    
    for prefix, suffix in truncated_addresses:
        print(f"\n🔍 Поиск адресов для 0x{prefix}...{suffix}:")
        
        # Поиск в БД
        found_in_db = find_full_addresses_by_pattern(prefix, suffix)
        if found_in_db:
            print(f"   ✅ Найдено в БД: {len(found_in_db)} адресов")
            for addr in found_in_db:
                print(f"      {addr}")
                all_found_addresses.add(addr)
        else:
            print(f"   ⚠️  Не найдено в БД")
        
        # Поиск через API (если есть condition_id)
        if condition_id:
            print(f"   🔍 Поиск через API для condition_id: {condition_id[:20]}...")
            trades = get_trades_from_api(condition_id)
            if trades:
                found_in_api = extract_addresses_from_trades(trades, prefix, suffix)
                if found_in_api:
                    print(f"   ✅ Найдено через API: {len(found_in_api)} адресов")
                    for addr in found_in_api:
                        print(f"      {addr}")
                        all_found_addresses.add(addr)
                else:
                    print(f"   ⚠️  Не найдено через API")
            else:
                print(f"   ⚠️  Транзакции не получены через API")
    
    # Сохранение найденных адресов
    if all_found_addresses:
        print("\n" + "="*70)
        print("СОХРАНЕНИЕ АДРЕСОВ")
        print("="*70)
        print(f"\n✅ Найдено {len(all_found_addresses)} уникальных адресов:")
        for i, addr in enumerate(sorted(all_found_addresses), 1):
            print(f"   {i}. {addr}")
        
        save_wallets_to_db(all_found_addresses, condition_id)
    else:
        print("\n⚠️  Полные адреса не найдены.")
        print("\nВозможные причины:")
        print("1. Адреса еще не сохранены в БД")
        print("2. Транзакции еще не обработаны API")
        print("3. Необходимо указать condition_id для поиска через API")
        print("4. Это тестовый сигнал")

if __name__ == "__main__":
    main()

