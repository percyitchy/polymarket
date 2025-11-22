#!/usr/bin/env python3
"""
Поиск condition_id через trade_id из событий
"""
import requests
import sqlite3
import json

def find_condition_id_from_trade_id(trade_id: str) -> str:
    """Найти condition_id через trade_id"""
    try:
        # Пробуем через Data API
        url = "https://data-api.polymarket.com/trades"
        params = {"trade_id": trade_id, "limit": 1}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0].get("condition_id") or data[0].get("conditionId")
            elif isinstance(data, dict):
                trades = data.get("trades", []) or data.get("data", [])
                if trades:
                    return trades[0].get("condition_id") or trades[0].get("conditionId")
    except:
        pass
    
    return None

def main():
    print("="*70)
    print("ПОИСК CONDITION_ID ДЛЯ WARRIORS VS PELICANS")
    print("="*70)
    
    # Trade IDs из событий
    trade_ids = [
        "0x4d72f6725b6848fc0b23ea0512010cb8088a1eb0417d9b83d02278c6bf40c4bc",
        "0x05bdbdb38a04d1c133a1bd349c28d768a5aaa5efea17eb110a6d9ab2275a5e36",
        "0x8873965e34a27f789490bbcbc65d0d89ffd94b6043f97bf8d2b658701c141245"
    ]
    
    print(f"\nПробую найти condition_id через {len(trade_ids)} trade_id...\n")
    
    found_condition_id = None
    
    for trade_id in trade_ids:
        print(f"Проверяю trade_id: {trade_id[:20]}...")
        condition_id = find_condition_id_from_trade_id(trade_id)
        
        if condition_id:
            print(f"✅ Найден condition_id: {condition_id}")
            
            # Проверяем через API
            try:
                url = f"https://clob.polymarket.com/markets/{condition_id}"
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    title = data.get("question") or data.get("title")
                    print(f"   Название: {title}")
                    found_condition_id = condition_id
                    break
                elif resp.status_code == 404:
                    print(f"   Рынок закрыт, но condition_id: {condition_id}")
                    found_condition_id = condition_id
                    break
            except:
                found_condition_id = condition_id
                break
        else:
            print("   Не найден")
    
    if found_condition_id:
        print("\n" + "="*70)
        print("РЕЗУЛЬТАТ:")
        print("="*70)
        print(f"\n✅ Condition ID: {found_condition_id}")
        print("\nДля сохранения всех кошельков используйте:")
        print(f"python3 save_wallets_from_market.py {found_condition_id}")
    else:
        print("\n⚠️  Condition ID не найден через trade_id")
        print("\nРекомендации:")
        print("1. Найдите condition_id на polymarket.com через DevTools")
        print("2. Или используйте скрипт поиска по названию после открытия рынка")

if __name__ == "__main__":
    main()

