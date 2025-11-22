#!/usr/bin/env python3
"""
Поиск адресов кошельков по condition_id рынка
Использование:
    python3 find_wallets_by_condition_id.py <condition_id>
    python3 find_wallets_by_condition_id.py --search "Warriors Pelicans"
"""
import sys
import requests
import json
from typing import List, Dict, Optional, Set
from datetime import datetime, timezone

def get_market_info(condition_id: str) -> Optional[Dict]:
    """Получить информацию о рынке по condition_id"""
    try:
        # Пробуем CLOB API
        url = f"https://clob.polymarket.com/markets/{condition_id}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                "title": data.get("question") or data.get("title") or "",
                "slug": data.get("slug") or data.get("marketSlug") or "",
                "active": data.get("active", False),
                "source": "CLOB"
            }
    except Exception as e:
        print(f"Ошибка при получении информации о рынке (CLOB): {e}")
    
    try:
        # Fallback на Data API
        url = f"https://data-api.polymarket.com/condition/{condition_id}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                "title": data.get("title") or data.get("question") or "",
                "slug": data.get("slug") or "",
                "active": True,
                "source": "Data API"
            }
    except Exception as e:
        print(f"Ошибка при получении информации о рынке (Data API): {e}")
    
    return None

def search_market_by_keywords(keywords: str) -> Optional[str]:
    """Поиск condition_id по ключевым словам в названии"""
    print(f"🔍 Поиск рынка по ключевым словам: '{keywords}'...")
    
    try:
        # Пробуем CLOB API
        url = "https://clob.polymarket.com/markets"
        params = {
            "limit": 200,
            "sort": "volume",
            "active": "true"
        }
        
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            markets = response.json()
            if isinstance(markets, list):
                keywords_lower = keywords.lower()
                for market in markets:
                    title = (market.get("question") or market.get("title") or "").lower()
                    if all(kw in title for kw in keywords_lower.split()):
                        condition_id = market.get("conditionId") or market.get("id")
                        print(f"✅ Найден рынок: {market.get('question') or market.get('title')}")
                        print(f"   Condition ID: {condition_id}")
                        return condition_id
    except Exception as e:
        print(f"Ошибка при поиске рынка: {e}")
    
    return None

def get_trades_from_data_api(condition_id: str, limit: int = 500) -> List[Dict]:
    """Получить транзакции через Data API"""
    try:
        url = "https://data-api.polymarket.com/trades"
        params = {
            "condition_id": condition_id,
            "limit": limit
        }
        
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("trades", []) or data.get("data", []) or []
    except Exception as e:
        print(f"Ошибка при получении транзакций (Data API): {e}")
    
    return []

def get_trades_from_clob_api(condition_id: str, limit: int = 500) -> List[Dict]:
    """Получить транзакции через CLOB API"""
    try:
        url = f"https://clob.polymarket.com/markets/{condition_id}/trades"
        params = {
            "limit": limit
        }
        
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("trades", []) or data.get("data", []) or []
    except Exception as e:
        print(f"Ошибка при получении транзакций (CLOB API): {e}")
    
    return []

def extract_wallet_addresses(trades: List[Dict]) -> Set[str]:
    """Извлечь уникальные адреса кошельков из транзакций"""
    addresses = set()
    
    for trade in trades:
        # Проверяем различные поля для адресов
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

def find_wallets_by_pattern(addresses: List[str], patterns: List[tuple]) -> Dict[str, List[str]]:
    """Найти адреса по паттернам (префикс...суффикс)"""
    found = {}
    
    for prefix, suffix in patterns:
        found[prefix] = []
        for addr in addresses:
            addr_lower = addr.lower()
            if addr_lower.startswith(prefix.lower()) and addr_lower.endswith(suffix.lower()):
                found[prefix].append(addr)
    
    return found

def get_wallet_info_from_db(address: str) -> Optional[Dict]:
    """Получить информацию о кошельке из базы данных"""
    try:
        import sqlite3
        db = sqlite3.connect('polymarket_notifier.db')
        cursor = db.cursor()
        cursor.execute('SELECT win_rate, traded_total, realized_pnl_total FROM wallets WHERE address = ?', (address.lower(),))
        result = cursor.fetchone()
        db.close()
        
        if result:
            return {
                "win_rate": result[0],
                "trades": result[1],
                "pnl": result[2]
            }
    except Exception:
        pass
    
    return None

def main():
    print("="*70)
    print("ПОИСК АДРЕСОВ КОШЕЛЬКОВ ПО CONDITION_ID")
    print("="*70)
    
    # Паттерны из сигнала Warriors vs Pelicans
    patterns = [
        ('0x4e7', '823'),
        ('0x97e', 'a30'),
        ('0xdb2', '56e')
    ]
    
    # Обработка аргументов командной строки
    if len(sys.argv) < 2:
        print("\nИспользование:")
        print("  python3 find_wallets_by_condition_id.py <condition_id>")
        print("  python3 find_wallets_by_condition_id.py --search \"Warriors Pelicans\"")
        print("\nПримеры:")
        print("  python3 find_wallets_by_condition_id.py 0x1234...")
        print("  python3 find_wallets_by_condition_id.py --search \"Warriors vs Pelicans\"")
        sys.exit(1)
    
    condition_id = None
    
    if sys.argv[1] == "--search":
        if len(sys.argv) < 3:
            print("❌ Укажите ключевые слова для поиска")
            sys.exit(1)
        keywords = sys.argv[2]
        condition_id = search_market_by_keywords(keywords)
        if not condition_id:
            print("❌ Рынок не найден")
            sys.exit(1)
    else:
        condition_id = sys.argv[1]
        if not condition_id.startswith("0x") or len(condition_id) < 10:
            print("❌ Неверный формат condition_id")
            sys.exit(1)
    
    # Получение информации о рынке
    print(f"\n1. Получение информации о рынке...")
    print(f"   Condition ID: {condition_id}")
    market_info = get_market_info(condition_id)
    
    if market_info:
        print(f"   ✅ Название: {market_info['title']}")
        print(f"   Slug: {market_info.get('slug', 'N/A')}")
        print(f"   Активен: {market_info.get('active', 'N/A')}")
        print(f"   Источник: {market_info['source']}")
    else:
        print("   ⚠️  Информация о рынке не найдена, продолжаем поиск транзакций...")
    
    # Получение транзакций
    print(f"\n2. Получение транзакций...")
    trades = []
    
    # Пробуем Data API
    print("   Пробуем Data API...")
    trades = get_trades_from_data_api(condition_id, limit=500)
    if trades:
        print(f"   ✅ Получено {len(trades)} транзакций через Data API")
    else:
        # Fallback на CLOB API
        print("   Data API не вернул данные, пробуем CLOB API...")
        trades = get_trades_from_clob_api(condition_id, limit=500)
        if trades:
            print(f"   ✅ Получено {len(trades)} транзакций через CLOB API")
    
    if not trades:
        print("   ❌ Транзакции не найдены")
        print("\nВозможные причины:")
        print("   - Рынок не существует или закрыт")
        print("   - На рынке еще нет транзакций")
        print("   - Проблемы с API")
        sys.exit(1)
    
    # Извлечение адресов
    print(f"\n3. Извлечение адресов кошельков...")
    addresses = extract_wallet_addresses(trades)
    print(f"   ✅ Найдено {len(addresses)} уникальных адресов")
    
    if len(addresses) == 0:
        print("   ⚠️  Адреса не найдены в транзакциях")
        print("   Проверьте формат данных транзакций")
        sys.exit(1)
    
    # Поиск по паттернам
    print(f"\n4. Поиск адресов по паттернам из сигнала...")
    found = find_wallets_by_pattern(list(addresses), patterns)
    
    print("\n" + "="*70)
    print("РЕЗУЛЬТАТЫ ПОИСКА:")
    print("="*70)
    
    all_found = []
    for prefix, suffix in patterns:
        if found[prefix]:
            all_found.extend(found[prefix])
            print(f"\n✅ {prefix}...{suffix}:")
            for addr in found[prefix]:
                print(f"   {addr}")
                # Показываем информацию из БД если есть
                db_info = get_wallet_info_from_db(addr)
                if db_info:
                    print(f"      БД: WR={db_info['win_rate']:.1%}, Trades={db_info['trades']}, PnL=${db_info['pnl']:.2f}")
        else:
            print(f"\n⚠️  {prefix}...{suffix}: не найдено")
    
    if all_found:
        print("\n" + "="*70)
        print("НАЙДЕННЫЕ АДРЕСА КОШЕЛЬКОВ:")
        print("="*70)
        for i, addr in enumerate(all_found, 1):
            print(f"{i}. {addr}")
        
        # Сохраняем в файл
        output_file = f"wallets_from_signal_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
        with open(output_file, 'w') as f:
            f.write("Адреса кошельков из сигнала:\n")
            f.write(f"Condition ID: {condition_id}\n")
            f.write(f"Дата поиска: {datetime.now(timezone.utc).isoformat()}\n\n")
            for addr in all_found:
                f.write(f"{addr}\n")
        print(f"\n✅ Адреса сохранены в файл: {output_file}")
    else:
        print("\n⚠️  Адреса с нужными паттернами не найдены в транзакциях.")
        print("\nВозможные причины:")
        print("   - Адреса еще не совершили транзакции на этом рынке")
        print("   - Транзакции не попали в выборку (попробуйте увеличить limit)")
        print("   - Это тестовый сигнал с несуществующими адресами")
        
        # Показываем первые несколько адресов для справки
        if addresses:
            print(f"\nПервые 10 адресов из транзакций (для справки):")
            for i, addr in enumerate(list(addresses)[:10], 1):
                print(f"   {i}. {addr}")

if __name__ == "__main__":
    main()

