#!/usr/bin/env python3
"""
Поиск кошельков с матча Warriors vs Pelicans
Расширенный поиск по всем возможным источникам
"""
import requests
import sqlite3
import json
from typing import List, Dict, Optional, Set
from datetime import datetime, timezone

def search_all_markets_for_keywords(keywords: List[str], limit: int = 500) -> List[Dict]:
    """Поиск всех рынков по ключевым словам (включая неактивные)"""
    found_markets = []
    
    try:
        # Пробуем CLOB API - активные рынки
        url = "https://clob.polymarket.com/markets"
        params = {
            "limit": limit,
            "sort": "volume"
        }
        
        print(f"🔍 Поиск активных рынков...")
        response = requests.get(url, params=params, timeout=20)
        if response.status_code == 200:
            markets = response.json()
            if isinstance(markets, list):
                for market in markets:
                    title = (market.get("question") or market.get("title") or "").lower()
                    if any(kw.lower() in title for kw in keywords):
                        condition_id = market.get("conditionId") or market.get("id")
                        found_markets.append({
                            "condition_id": condition_id,
                            "title": market.get("question") or market.get("title"),
                            "active": market.get("active", True),
                            "source": "CLOB"
                        })
                        print(f"✅ Найден: {market.get('question') or market.get('title')}")
                        print(f"   Condition ID: {condition_id}")
    except Exception as e:
        print(f"Ошибка при поиске активных рынков: {e}")
    
    # Также пробуем поиск через разные варианты названий
    variations = [
        "warriors pelicans",
        "warriors vs pelicans",
        "golden state pelicans",
        "gsw pelicans",
        "warriors new orleans"
    ]
    
    for variation in variations:
        if variation not in [k.lower() for k in keywords]:
            try:
                url = "https://clob.polymarket.com/markets"
                params = {
                    "limit": limit,
                    "sort": "volume"
                }
                response = requests.get(url, params=params, timeout=20)
                if response.status_code == 200:
                    markets = response.json()
                    if isinstance(markets, list):
                        for market in markets:
                            title = (market.get("question") or market.get("title") or "").lower()
                            if variation in title:
                                condition_id = market.get("conditionId") or market.get("id")
                                # Проверяем, не добавлен ли уже
                                if not any(m["condition_id"] == condition_id for m in found_markets):
                                    found_markets.append({
                                        "condition_id": condition_id,
                                        "title": market.get("question") or market.get("title"),
                                        "active": market.get("active", True),
                                        "source": "CLOB"
                                    })
                                    print(f"✅ Найден (вариант '{variation}'): {market.get('question') or market.get('title')}")
            except:
                pass
    
    return found_markets

def get_trades_for_market(condition_id: str) -> List[Dict]:
    """Получить транзакции для рынка"""
    trades = []
    
    # Пробуем Data API
    try:
        url = "https://data-api.polymarket.com/trades"
        params = {"condition_id": condition_id, "limit": 500}
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                trades = data
            elif isinstance(data, dict):
                trades = data.get("trades", []) or data.get("data", [])
    except Exception as e:
        print(f"Ошибка Data API: {e}")
    
    # Пробуем CLOB API
    if not trades:
        try:
            url = f"https://clob.polymarket.com/markets/{condition_id}/trades"
            params = {"limit": 500}
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    trades = data
                elif isinstance(data, dict):
                    trades = data.get("trades", []) or data.get("data", [])
        except Exception as e:
            print(f"Ошибка CLOB API: {e}")
    
    return trades

def extract_wallet_addresses(trades: List[Dict]) -> Set[str]:
    """Извлечь адреса кошельков из транзакций"""
    addresses = set()
    
    for trade in trades:
        for field in ["maker", "taker", "user", "trader", "address", "wallet", "account"]:
            value = trade.get(field)
            if isinstance(value, str) and value.startswith("0x") and len(value) == 42:
                addresses.add(value.lower())
        
        if "user" in trade and isinstance(trade["user"], dict):
            for field in ["address", "wallet", "id"]:
                value = trade["user"].get(field)
                if isinstance(value, str) and value.startswith("0x") and len(value) == 42:
                    addresses.add(value.lower())
    
    return addresses

def find_wallets_by_pattern(addresses: List[str]) -> Dict[str, List[str]]:
    """Найти адреса по паттернам из сигнала"""
    patterns = [
        ('0x4e7', '823'),
        ('0x97e', 'a30'),
        ('0xdb2', '56e')
    ]
    
    found = {}
    for prefix, suffix in patterns:
        found[prefix] = []
        for addr in addresses:
            addr_lower = addr.lower()
            if addr_lower.startswith(prefix.lower()) and addr_lower.endswith(suffix.lower()):
                found[prefix].append(addr)
    
    return found

def get_wallet_info_from_db(address: str) -> Optional[Dict]:
    """Получить информацию о кошельке из БД"""
    try:
        db = sqlite3.connect('polymarket_notifier.db')
        cursor = db.cursor()
        cursor.execute('SELECT win_rate, traded_total, realized_pnl_total FROM wallets WHERE address = ?', (address.lower(),))
        result = cursor.fetchone()
        db.close()
        if result:
            return {"win_rate": result[0], "trades": result[1], "pnl": result[2]}
    except:
        pass
    return None

def main():
    print("="*70)
    print("ПОИСК КОШЕЛЬКОВ С МАТЧА WARRIORS VS PELICANS")
    print("="*70)
    
    # Поиск рынков
    print("\n1. Поиск рынков Warriors vs Pelicans...")
    keywords = ["warriors", "pelicans"]
    markets = search_all_markets_for_keywords(keywords, limit=500)
    
    if not markets:
        print("⚠️  Рынки не найдены через API")
        print("\nПроверяем базу данных на наличие недавних алертов...")
        
        # Проверяем БД на наличие алертов с похожими названиями
        db = sqlite3.connect('polymarket_notifier.db')
        cursor = db.cursor()
        cursor.execute('''
            SELECT DISTINCT condition_id, sent_at 
            FROM alerts_sent 
            WHERE sent_at >= datetime('now', '-30 days')
            ORDER BY sent_at DESC
            LIMIT 50
        ''')
        
        recent_alerts = cursor.fetchall()
        print(f"Найдено {len(recent_alerts)} недавних алертов")
        
        # Пробуем получить названия рынков для каждого
        for condition_id, sent_at in recent_alerts[:20]:
            try:
                url = f"https://clob.polymarket.com/markets/{condition_id}"
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    title = (data.get("question") or data.get("title") or "").lower()
                    if "warriors" in title or "pelicans" in title:
                        markets.append({
                            "condition_id": condition_id,
                            "title": data.get("question") or data.get("title"),
                            "active": data.get("active", False),
                            "source": "DB"
                        })
                        print(f"✅ Найден в БД: {data.get('question') or data.get('title')}")
            except:
                pass
        
        db.close()
    
    if not markets:
        print("\n❌ Рынок Warriors vs Pelicans не найден")
        print("\nВозможные причины:")
        print("  - Рынок уже закрыт и удален")
        print("  - Это был тестовый сигнал")
        print("  - Название рынка отличается")
        return
    
    # Обрабатываем найденные рынки
    print(f"\n2. Обработка {len(markets)} найденных рынков...")
    
    all_addresses = set()
    all_found_wallets = {}
    
    for market in markets:
        condition_id = market["condition_id"]
        title = market["title"]
        
        print(f"\n📊 Рынок: {title}")
        print(f"   Condition ID: {condition_id}")
        
        # Получаем транзакции
        trades = get_trades_for_market(condition_id)
        if trades:
            print(f"   ✅ Получено {len(trades)} транзакций")
            addresses = extract_wallet_addresses(trades)
            all_addresses.update(addresses)
            print(f"   ✅ Извлечено {len(addresses)} уникальных адресов")
        else:
            print(f"   ⚠️  Транзакции не найдены")
    
    if not all_addresses:
        print("\n⚠️  Адреса не найдены в транзакциях")
        return
    
    # Поиск по паттернам
    print(f"\n3. Поиск адресов по паттернам из сигнала...")
    print(f"   Всего уникальных адресов: {len(all_addresses)}")
    
    found = find_wallets_by_pattern(list(all_addresses))
    
    print("\n" + "="*70)
    print("РЕЗУЛЬТАТЫ ПОИСКА:")
    print("="*70)
    
    all_found = []
    patterns = [
        ('0x4e7', '823'),
        ('0x97e', 'a30'),
        ('0xdb2', '56e')
    ]
    
    for prefix, suffix in patterns:
        if found[prefix]:
            all_found.extend(found[prefix])
            print(f"\n✅ {prefix}...{suffix}:")
            for addr in found[prefix]:
                print(f"   {addr}")
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
        output_file = f"warriors_pelicans_wallets_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
        with open(output_file, 'w') as f:
            f.write("Адреса кошельков с матча Warriors vs Pelicans:\n")
            f.write(f"Дата поиска: {datetime.now(timezone.utc).isoformat()}\n\n")
            for addr in all_found:
                f.write(f"{addr}\n")
        print(f"\n✅ Адреса сохранены в файл: {output_file}")
    else:
        print("\n⚠️  Адреса с нужными паттернами не найдены")
        print(f"\nВсего найдено {len(all_addresses)} уникальных адресов с этого рынка")
        print("Первые 20 адресов:")
        for i, addr in enumerate(list(all_addresses)[:20], 1):
            print(f"  {i}. {addr}")

if __name__ == "__main__":
    main()

