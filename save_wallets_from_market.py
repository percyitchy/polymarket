#!/usr/bin/env python3
"""
Сохранение всех кошельков с рынка по condition_id
Использование: python3 save_wallets_from_market.py <condition_id>
"""
import sys
import requests
import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Set, Dict

def get_market_info(condition_id: str) -> Dict:
    """Получить информацию о рынке"""
    info = {
        "title": "Unknown",
        "slug": "",
        "active": False,
        "condition_id": condition_id
    }
    
    try:
        url = f"https://clob.polymarket.com/markets/{condition_id}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            info["title"] = data.get("question") or data.get("title") or "Unknown"
            info["slug"] = data.get("slug") or data.get("marketSlug") or ""
            info["active"] = data.get("active", False)
    except Exception as e:
        print(f"⚠️  Ошибка при получении информации о рынке: {e}")
    
    return info

def get_trades_from_apis(condition_id: str) -> List[Dict]:
    """Получить транзакции из всех доступных API"""
    all_trades = []
    
    # 1. Data API
    try:
        print("📡 Получение транзакций через Data API...")
        url = "https://data-api.polymarket.com/trades"
        params = {"condition_id": condition_id, "limit": 1000}
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                all_trades.extend(data)
                print(f"   ✅ Получено {len(data)} транзакций")
            elif isinstance(data, dict):
                trades = data.get("trades", []) or data.get("data", [])
                all_trades.extend(trades)
                print(f"   ✅ Получено {len(trades)} транзакций")
    except Exception as e:
        print(f"   ⚠️  Ошибка Data API: {e}")
    
    # 2. CLOB API
    try:
        print("📡 Получение транзакций через CLOB API...")
        url = f"https://clob.polymarket.com/markets/{condition_id}/trades"
        params = {"limit": 1000}
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                # Дедупликация по trade_id если есть
                existing_ids = {t.get("trade_id") or t.get("id") for t in all_trades if t.get("trade_id") or t.get("id")}
                new_trades = [t for t in data if (t.get("trade_id") or t.get("id")) not in existing_ids]
                all_trades.extend(new_trades)
                print(f"   ✅ Добавлено {len(new_trades)} новых транзакций")
            elif isinstance(data, dict):
                trades = data.get("trades", []) or data.get("data", [])
                existing_ids = {t.get("trade_id") or t.get("id") for t in all_trades if t.get("trade_id") or t.get("id")}
                new_trades = [t for t in trades if (t.get("trade_id") or t.get("id")) not in existing_ids]
                all_trades.extend(new_trades)
                print(f"   ✅ Добавлено {len(new_trades)} новых транзакций")
    except Exception as e:
        print(f"   ⚠️  Ошибка CLOB API: {e}")
    
    return all_trades

def extract_wallet_addresses(trades: List[Dict]) -> Set[str]:
    """Извлечь все уникальные адреса кошельков из транзакций"""
    addresses = set()
    
    for trade in trades:
        # Проверяем различные поля
        for field in ["maker", "taker", "user", "trader", "address", "wallet", "account", "creator"]:
            value = trade.get(field)
            if isinstance(value, str) and value.startswith("0x") and len(value) == 42:
                addresses.add(value.lower())
        
        # Проверяем вложенные структуры
        if "user" in trade and isinstance(trade["user"], dict):
            for field in ["address", "wallet", "id"]:
                value = trade["user"].get(field)
                if isinstance(value, str) and value.startswith("0x") and len(value) == 42:
                    addresses.add(value.lower())
        
        # Проверяем maker/taker объекты
        for side in ["maker", "taker"]:
            if side in trade and isinstance(trade[side], dict):
                for field in ["address", "wallet", "id", "user"]:
                    value = trade[side].get(field)
                    if isinstance(value, str) and value.startswith("0x") and len(value) == 42:
                        addresses.add(value.lower())
    
    return addresses

def save_wallets_to_file(wallets: Set[str], market_info: Dict, output_file: str):
    """Сохранить кошельки в файл"""
    with open(output_file, 'w') as f:
        f.write(f"Кошельки с рынка: {market_info['title']}\n")
        f.write(f"Condition ID: {market_info['condition_id']}\n")
        f.write(f"Slug: {market_info.get('slug', 'N/A')}\n")
        f.write(f"Активен: {market_info.get('active', 'N/A')}\n")
        f.write(f"Дата сохранения: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"Всего кошельков: {len(wallets)}\n")
        f.write("\n" + "="*70 + "\n\n")
        
        for i, wallet in enumerate(sorted(wallets), 1):
            f.write(f"{i}. {wallet}\n")
    
    print(f"✅ Кошельки сохранены в файл: {output_file}")

def save_wallets_to_db(wallets: Set[str], condition_id: str):
    """Сохранить информацию о кошельках в БД (в таблицу для отслеживания)"""
    try:
        db = sqlite3.connect('polymarket_notifier.db')
        cursor = db.cursor()
        
        # Создаем таблицу для хранения кошельков по рынкам, если её нет
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
        saved_count = 0
        
        for wallet in wallets:
            try:
                cursor.execute('''
                    INSERT INTO market_wallets (condition_id, wallet_address, first_seen_at, last_seen_at, trade_count)
                    VALUES (?, ?, ?, ?, 1)
                    ON CONFLICT(condition_id, wallet_address) DO UPDATE SET
                        last_seen_at = excluded.last_seen_at,
                        trade_count = trade_count + 1
                ''', (condition_id.lower(), wallet.lower(), now, now))
                saved_count += 1
            except Exception as e:
                print(f"⚠️  Ошибка при сохранении {wallet}: {e}")
        
        db.commit()
        db.close()
        print(f"✅ Сохранено {saved_count} кошельков в БД (таблица market_wallets)")
    except Exception as e:
        print(f"⚠️  Ошибка при сохранении в БД: {e}")

def main():
    if len(sys.argv) < 2:
        print("Использование: python3 save_wallets_from_market.py <condition_id>")
        print("\nПример:")
        print("  python3 save_wallets_from_market.py 0x1234567890abcdef...")
        sys.exit(1)
    
    condition_id = sys.argv[1].strip()
    
    if not condition_id.startswith("0x") or len(condition_id) < 10:
        print("❌ Неверный формат condition_id")
        sys.exit(1)
    
    print("="*70)
    print("СОХРАНЕНИЕ КОШЕЛЬКОВ С РЫНКА")
    print("="*70)
    print(f"\nCondition ID: {condition_id}")
    
    # Получаем информацию о рынке
    print("\n1. Получение информации о рынке...")
    market_info = get_market_info(condition_id)
    print(f"   Название: {market_info['title']}")
    print(f"   Slug: {market_info.get('slug', 'N/A')}")
    print(f"   Активен: {market_info.get('active', 'N/A')}")
    
    # Получаем транзакции
    print("\n2. Получение транзакций...")
    trades = get_trades_from_apis(condition_id)
    
    if not trades:
        print("❌ Транзакции не найдены")
        print("\nВозможные причины:")
        print("  - Рынок не существует")
        print("  - На рынке еще нет транзакций")
        print("  - Проблемы с API")
        sys.exit(1)
    
    print(f"   Всего транзакций: {len(trades)}")
    
    # Извлекаем адреса
    print("\n3. Извлечение адресов кошельков...")
    wallets = extract_wallet_addresses(trades)
    print(f"   ✅ Найдено {len(wallets)} уникальных адресов")
    
    if not wallets:
        print("❌ Адреса не найдены в транзакциях")
        sys.exit(1)
    
    # Сохраняем в файл
    print("\n4. Сохранение кошельков...")
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in market_info['title'][:50])
    output_file = f"wallets_{safe_title}_{timestamp}.txt"
    save_wallets_to_file(wallets, market_info, output_file)
    
    # Сохраняем в БД
    save_wallets_to_db(wallets, condition_id)
    
    # Показываем первые несколько адресов
    print("\n" + "="*70)
    print("ПЕРВЫЕ 10 АДРЕСОВ:")
    print("="*70)
    for i, wallet in enumerate(sorted(wallets)[:10], 1):
        print(f"{i}. {wallet}")
    
    if len(wallets) > 10:
        print(f"\n... и еще {len(wallets) - 10} адресов")
    
    print(f"\n✅ Всего сохранено {len(wallets)} кошельков")

if __name__ == "__main__":
    main()

