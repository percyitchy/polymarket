#!/usr/bin/env python3
"""
Попытка извлечь condition_id из ключа k через перебор
"""
import sqlite3
import json
import hashlib
import requests

def find_condition_id_from_key(key: str) -> str:
    """Найти condition_id через перебор возможных вариантов"""
    db = sqlite3.connect('polymarket_notifier.db')
    cursor = db.cursor()
    
    # Пробуем найти через все condition_id в БД
    print("Ищу через condition_id из БД...")
    
    # 1. Из alerts_sent
    cursor.execute('SELECT DISTINCT condition_id, outcome_index, side FROM alerts_sent')
    alerts = cursor.fetchall()
    print(f"Проверяю {len(alerts)} вариантов из alerts_sent...")
    
    for condition_id, outcome_index, side in alerts:
        test_key = hashlib.sha256(f'{condition_id}:{outcome_index}:{side}'.encode()).hexdigest()
        if test_key == key:
            return condition_id
    
    # 2. Из других записей rolling_buys (если там есть conditionId)
    cursor.execute('SELECT data FROM rolling_buys')
    rows = cursor.fetchall()
    print(f"Проверяю {len(rows)} записей rolling_buys...")
    
    seen_condition_ids = set()
    for (data_str,) in rows:
        try:
            data = json.loads(data_str)
            events = data.get('events', [])
            for event in events:
                condition_id = event.get('conditionId') or event.get('condition_id')
                if condition_id and condition_id not in seen_condition_ids:
                    seen_condition_ids.add(condition_id)
                    # Проверяем все возможные outcome_index и side
                    for outcome_index in [0, 1]:
                        for side in ['BUY', 'SELL']:
                            test_key = hashlib.sha256(f'{condition_id}:{outcome_index}:{side}'.encode()).hexdigest()
                            if test_key == key:
                                return condition_id
        except:
            pass
    
    db.close()
    return None

def main():
    print("="*70)
    print("ИЗВЛЕЧЕНИЕ CONDITION_ID ИЗ КЛЮЧА K")
    print("="*70)
    
    db = sqlite3.connect('polymarket_notifier.db')
    cursor = db.cursor()
    
    # Находим ключ для Warriors vs Pelicans
    cursor.execute('SELECT k, data, updated_at FROM rolling_buys WHERE data LIKE "%Warriors vs. Pelicans%" ORDER BY updated_at DESC LIMIT 1')
    row = cursor.fetchone()
    
    if not row:
        print("\n⚠️  События Warriors vs Pelicans не найдены")
        return
    
    k, data_str, updated_at = row
    print(f"\nКлюч (k): {k}")
    print(f"Обновлено: {updated_at}")
    
    # Пробуем извлечь condition_id
    condition_id = find_condition_id_from_key(k)
    
    if condition_id:
        print(f"\n✅ НАЙДЕН Condition ID: {condition_id}")
        
        # Проверяем через API
        try:
            url = f'https://clob.polymarket.com/markets/{condition_id}'
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                title = data.get('question') or data.get('title')
                print(f"   Название: {title}")
            elif resp.status_code == 404:
                print(f"   Рынок закрыт (404), но condition_id: {condition_id}")
        except:
            pass
        
        print("\n" + "="*70)
        print("СЛЕДУЮЩИЙ ШАГ:")
        print("="*70)
        print(f"\nДля сохранения всех кошельков используйте:")
        print(f"python3 save_wallets_from_market.py {condition_id}")
    else:
        print("\n⚠️  Condition ID не найден через перебор")
        print("\nПроблема: condition_id не сохранялся в старых событиях")
        print("\nРешение:")
        print("1. ✅ Код исправлен - теперь condition_id будет сохраняться")
        print("2. Для старых событий найдите condition_id на polymarket.com")
        print("3. Или дождитесь нового сигнала - condition_id будет сохранен автоматически")
    
    db.close()

if __name__ == "__main__":
    main()

