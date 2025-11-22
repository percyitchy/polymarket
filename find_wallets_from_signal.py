#!/usr/bin/env python3
"""
Поиск адресов кошельков из сигнала Warriors vs Pelicans
через API транзакций
"""
import requests
import json
from typing import List, Dict, Optional

def search_market_by_title(title_keywords: str) -> Optional[str]:
    """Поиск condition_id рынка по ключевым словам в названии"""
    try:
        # Пробуем через CLOB API - получить активные рынки
        url = "https://clob.polymarket.com/markets"
        params = {
            "limit": 100,
            "sort": "volume",
            "active": "true"
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            markets = response.json()
            if isinstance(markets, list):
                for market in markets:
                    market_title = market.get("question") or market.get("title") or ""
                    if title_keywords.lower() in market_title.lower():
                        condition_id = market.get("conditionId") or market.get("id")
                        print(f"✅ Найден рынок: {market_title}")
                        print(f"   Condition ID: {condition_id}")
                        return condition_id
    except Exception as e:
        print(f"Ошибка при поиске рынка: {e}")
    
    return None

def get_trades_for_market(condition_id: str, limit: int = 100) -> List[Dict]:
    """Получить транзакции для рынка"""
    try:
        # Пробуем через Data API
        url = f"https://data-api.polymarket.com/trades"
        params = {
            "condition_id": condition_id,
            "limit": limit
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("trades", []) or data.get("data", [])
    except Exception as e:
        print(f"Ошибка при получении транзакций: {e}")
    
    return []

def extract_wallet_addresses(trades: List[Dict]) -> List[str]:
    """Извлечь адреса кошельков из транзакций"""
    addresses = set()
    
    for trade in trades:
        # Проверяем различные поля
        for field in ["maker", "taker", "user", "trader", "address", "wallet", "account"]:
            value = trade.get(field)
            if isinstance(value, str) and value.startswith("0x") and len(value) == 42:
                addresses.add(value.lower())
        
        # Проверяем вложенные структуры
        if "user" in trade and isinstance(trade["user"], dict):
            for field in ["address", "wallet", "id"]:
                value = trade["user"].get(field)
                if isinstance(value, str) and value.startswith("0x") and len(value) == 42:
                    addresses.add(value.lower())
    
    return list(addresses)

def find_wallets_by_pattern(addresses: List[str], patterns: List[tuple]) -> Dict[str, List[str]]:
    """Найти адреса по паттернам"""
    found = {}
    
    for prefix, suffix in patterns:
        found[prefix] = []
        for addr in addresses:
            addr_lower = addr.lower()
            if addr_lower.startswith(prefix.lower()) and addr_lower.endswith(suffix.lower()):
                found[prefix].append(addr)
    
    return found

def main():
    print("="*70)
    print("ПОИСК АДРЕСОВ КОШЕЛЬКОВ ИЗ СИГНАЛА WARRIORS VS PELICANS")
    print("="*70)
    
    # Паттерны из изображения
    patterns = [
        ('0x4e7', '823'),
        ('0x97e', 'a30'),
        ('0xdb2', '56e')
    ]
    
    # Поиск рынка
    print("\n1. Поиск рынка Warriors vs Pelicans...")
    condition_id = search_market_by_title("Warriors Pelicans")
    
    if not condition_id:
        print("⚠️  Рынок не найден. Пробуем альтернативные варианты...")
        condition_id = search_market_by_title("Pelicans Warriors")
    
    if not condition_id:
        print("❌ Рынок не найден через API.")
        print("\nПопробуйте вручную найти condition_id для рынка Warriors vs Pelicans")
        print("и запустите скрипт с параметром condition_id")
        return
    
    # Получение транзакций
    print(f"\n2. Получение транзакций для condition_id: {condition_id}...")
    trades = get_trades_for_market(condition_id, limit=200)
    
    if not trades:
        print("⚠️  Транзакции не найдены через Data API")
        print("Попробуйте проверить логи бота или базу данных alerts_sent")
        return
    
    print(f"✅ Найдено {len(trades)} транзакций")
    
    # Извлечение адресов
    print("\n3. Извлечение адресов кошельков...")
    addresses = extract_wallet_addresses(trades)
    print(f"✅ Найдено {len(addresses)} уникальных адресов")
    
    # Поиск по паттернам
    print("\n4. Поиск адресов по паттернам из сигнала...")
    found = find_wallets_by_pattern(addresses, patterns)
    
    print("\n" + "="*70)
    print("РЕЗУЛЬТАТЫ:")
    print("="*70)
    
    all_found = []
    for prefix, suffix in patterns:
        if found[prefix]:
            all_found.extend(found[prefix])
            print(f"\n✅ {prefix}...{suffix}:")
            for addr in found[prefix]:
                print(f"   {addr}")
        else:
            print(f"\n⚠️  {prefix}...{suffix}: не найдено")
    
    if all_found:
        print("\n" + "="*70)
        print("НАЙДЕННЫЕ АДРЕСА КОШЕЛЬКОВ:")
        print("="*70)
        for i, addr in enumerate(all_found, 1):
            print(f"{i}. {addr}")
    else:
        print("\n⚠️  Адреса с нужными паттернами не найдены в транзакциях.")
        print("Возможно:")
        print("1. Транзакции еще не обработаны API")
        print("2. Адреса находятся в другом источнике")
        print("3. Это тестовый сигнал")

if __name__ == "__main__":
    main()

