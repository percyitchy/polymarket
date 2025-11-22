#!/usr/bin/env python3
"""
Проверка сохранения адресов кошельков в алертах
Использование: python3 check_alert_wallets.py [condition_id]
"""
import sys
import sqlite3
import json
from datetime import datetime, timezone, timedelta

def check_recent_alerts(condition_id: str = None):
    """Проверить недавние алерты на наличие сохраненных адресов"""
    db = sqlite3.connect('polymarket_notifier.db')
    cursor = db.cursor()
    
    if condition_id:
        cursor.execute('''
            SELECT condition_id, outcome_index, wallet_count, sent_at, wallets_csv, wallet_details_json, side
            FROM alerts_sent
            WHERE condition_id = ?
            ORDER BY sent_at DESC
        ''', (condition_id,))
    else:
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        cursor.execute('''
            SELECT condition_id, outcome_index, wallet_count, sent_at, wallets_csv, wallet_details_json, side
            FROM alerts_sent
            WHERE sent_at >= ?
            ORDER BY sent_at DESC
            LIMIT 50
        ''', (week_ago,))
    
    alerts = cursor.fetchall()
    
    print("="*70)
    print("ПРОВЕРКА СОХРАНЕНИЯ АДРЕСОВ В АЛЕРТАХ")
    print("="*70)
    
    if condition_id:
        print(f"\nАлерты для condition_id: {condition_id}")
    else:
        print(f"\nПоследние 50 алертов (за 7 дней)")
    
    print(f"\nВсего найдено: {len(alerts)} алертов\n")
    
    stats = {
        "total": len(alerts),
        "with_wallets_csv": 0,
        "with_wallet_details": 0,
        "empty_wallets": 0,
        "mismatch_count": 0
    }
    
    for condition_id_val, outcome_index, wallet_count, sent_at, wallets_csv, wallet_details_json, side in alerts:
        wallets_from_csv = []
        wallets_from_json = []
        
        if wallets_csv:
            wallets_from_csv = [w.strip() for w in wallets_csv.split(',') if w.strip()]
            stats["with_wallets_csv"] += 1
        
        if wallet_details_json:
            try:
                details = json.loads(wallet_details_json)
                wallets_from_json = [d.get('wallet', '').strip() for d in details if d.get('wallet')]
                stats["with_wallet_details"] += 1
            except:
                pass
        
        # Проверяем несоответствия
        if wallet_count > 0 and len(wallets_from_csv) == 0:
            stats["empty_wallets"] += 1
            print(f"⚠️  ПРОБЛЕМА: Алерт от {sent_at}")
            print(f"   Condition ID: {condition_id_val[:30]}...")
            print(f"   Wallet count: {wallet_count}, но wallets_csv пуст!")
            print(f"   Side: {side}, Outcome: {outcome_index}")
            print()
        
        if wallet_count > 0 and len(wallets_from_csv) != wallet_count:
            stats["mismatch_count"] += 1
            print(f"⚠️  НЕСООТВЕТСТВИЕ: Алерт от {sent_at}")
            print(f"   Condition ID: {condition_id_val[:30]}...")
            print(f"   Wallet count: {wallet_count}, wallets_csv: {len(wallets_from_csv)}")
            print(f"   Адреса: {wallets_csv[:100]}...")
            print()
    
    print("="*70)
    print("СТАТИСТИКА:")
    print("="*70)
    print(f"Всего алертов: {stats['total']}")
    print(f"С wallets_csv: {stats['with_wallets_csv']} ({stats['with_wallets_csv']/stats['total']*100:.1f}%)")
    print(f"С wallet_details_json: {stats['with_wallet_details']} ({stats['with_wallet_details']/stats['total']*100:.1f}%)")
    print(f"Пустые wallets_csv при wallet_count > 0: {stats['empty_wallets']}")
    print(f"Несоответствие количества: {stats['mismatch_count']}")
    
    db.close()

if __name__ == "__main__":
    condition_id = sys.argv[1] if len(sys.argv) > 1 else None
    check_recent_alerts(condition_id)

