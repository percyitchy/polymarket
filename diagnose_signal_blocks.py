#!/usr/bin/env python3
"""
Полная диагностика блокировок сигналов
Проверяет все возможные причины отсутствия сигналов
"""
import sqlite3
import json
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

def check_all_blocks():
    print("="*70)
    print("ПОЛНАЯ ДИАГНОСТИКА БЛОКИРОВОК СИГНАЛОВ")
    print("="*70)
    
    db = sqlite3.connect('polymarket_notifier.db')
    cursor = db.cursor()
    
    # 1. Настройки
    print("\n1. НАСТРОЙКИ:")
    min_consensus = int(os.getenv('MIN_CONSENSUS', '3'))
    alert_window_min = float(os.getenv('ALERT_WINDOW_MIN', '20.0'))
    alert_cooldown_min = float(os.getenv('ALERT_COOLDOWN_MIN', '30.0'))
    min_total_position_usd = float(os.getenv('MIN_TOTAL_POSITION_USD', '1000.0'))  # Значение по умолчанию из кода
    conflict_window_min = float(os.getenv('CONFLICT_WINDOW_MIN', '60.0'))
    
    print(f"   MIN_CONSENSUS: {min_consensus}")
    print(f"   ALERT_WINDOW_MIN: {alert_window_min} минут")
    print(f"   ALERT_COOLDOWN_MIN: {alert_cooldown_min} минут")
    print(f"   MIN_TOTAL_POSITION_USD: ${min_total_position_usd:.2f}")
    print(f"   CONFLICT_WINDOW_MIN: {conflict_window_min} минут")
    
    if min_total_position_usd > 0:
        print(f"   ⚠️  ВНИМАНИЕ: MIN_TOTAL_POSITION_USD = ${min_total_position_usd:.2f}")
        print(f"      Сигналы будут блокироваться, если total_usd < ${min_total_position_usd:.2f}")
    
    # 2. Проверяем консенсусы
    print("\n2. КОНСЕНСУСЫ В ROLLING_BUYS:")
    cursor.execute('SELECT k, data, updated_at FROM rolling_buys ORDER BY updated_at DESC LIMIT 100')
    rows = cursor.fetchall()
    
    consensus_with_condition_id = []
    consensus_without_condition_id = []
    
    for k, data_str, updated_at in rows:
        try:
            data = json.loads(data_str)
            events = data.get('events', [])
            wallets = {e.get('wallet') for e in events if e.get('wallet')}
            
            if len(wallets) >= min_consensus:
                condition_id = None
                for event in events:
                    if 'conditionId' in event:
                        condition_id = event['conditionId']
                        break
                
                if condition_id:
                    consensus_with_condition_id.append({
                        'condition_id': condition_id,
                        'wallets': len(wallets),
                        'events': events,
                        'updated_at': updated_at
                    })
                else:
                    consensus_without_condition_id.append({
                        'wallets': len(wallets),
                        'events': events,
                        'updated_at': updated_at
                    })
        except:
            pass
    
    print(f"   Консенсусов с condition_id: {len(consensus_with_condition_id)}")
    print(f"   Консенсусов без condition_id (старые): {len(consensus_without_condition_id)}")
    
    if consensus_with_condition_id:
        print(f"\n   Проверяю консенсусы с condition_id на блокировки:\n")
        
        for i, signal in enumerate(consensus_with_condition_id[:5], 1):
            condition_id = signal['condition_id']
            outcome_index = signal['events'][0].get('outcomeIndex', 0) if signal['events'] else 0
            side = signal['events'][0].get('side', 'BUY') if signal['events'] else 'BUY'
            wallets_count = signal['wallets']
            
            # Извлекаем данные
            market_title = signal['events'][0].get('marketTitle', 'N/A') if signal['events'] else 'N/A'
            total_usd = sum(e.get('usd', 0) for e in signal['events'] if isinstance(e.get('usd'), (int, float)))
            prices = [e.get('price', 0) for e in signal['events'] if isinstance(e.get('price'), (int, float)) and e.get('price') > 0]
            
            print(f"{i}. {market_title[:50]}")
            print(f"   Condition ID: {condition_id[:30]}...")
            print(f"   Кошельков: {wallets_count}, Outcome: {outcome_index}, Side: {side}")
            print(f"   Total USD: ${total_usd:.2f}")
            if prices:
                print(f"   Цены: {[f'${p:.3f}' for p in prices[:3]]}")
            
            # Проверка 1: Уже отправлен?
            cursor.execute('''
                SELECT sent_at FROM alerts_sent
                WHERE condition_id = ? AND outcome_index = ? AND side = ?
                ORDER BY sent_at DESC LIMIT 1
            ''', (condition_id, outcome_index, side))
            alert = cursor.fetchone()
            
            if alert:
                print(f"   ✅ Алерт уже отправлен: {alert[0][:19]}")
            else:
                print(f"   ❌ Алерт НЕ отправлен - проверяю блокировки:")
                
                # Проверка 2: MIN_TOTAL_POSITION_USD
                if total_usd < min_total_position_usd:
                    print(f"      ❌ БЛОКИРОВКА: Total USD ${total_usd:.2f} < ${min_total_position_usd:.2f}")
                else:
                    print(f"      ✅ Total USD OK: ${total_usd:.2f} >= ${min_total_position_usd:.2f}")
                
                # Проверка 3: Цены
                if prices:
                    avg_price = sum(prices) / len(prices)
                    if avg_price <= 0.001 or avg_price >= 0.999:
                        print(f"      ❌ БЛОКИРОВКА: Рынок разрешен (цена ${avg_price:.4f})")
                    elif avg_price <= 0.02 or avg_price >= 0.98:
                        print(f"      ⚠️  Возможная блокировка: Цена ${avg_price:.4f} указывает на закрытый рынок")
                    else:
                        print(f"      ✅ Цена OK: ${avg_price:.4f}")
                
                # Проверка 4: Cooldown
                cursor.execute('''
                    SELECT sent_at FROM alerts_sent
                    WHERE condition_id = ? AND outcome_index = ?
                    ORDER BY sent_at DESC LIMIT 1
                ''', (condition_id, outcome_index))
                recent_alert = cursor.fetchone()
                
                if recent_alert:
                    alert_time = datetime.fromisoformat(recent_alert[0].replace('Z', '+00:00'))
                    signal_time = datetime.fromisoformat(signal['updated_at'].replace('Z', '+00:00'))
                    diff_minutes = (signal_time - alert_time).total_seconds() / 60
                    
                    if diff_minutes < alert_cooldown_min:
                        print(f"      ❌ БЛОКИРОВКА: Cooldown активен ({diff_minutes:.1f} < {alert_cooldown_min} мин)")
                    else:
                        print(f"      ✅ Cooldown OK: {diff_minutes:.1f} >= {alert_cooldown_min} мин")
            
            print()
    
    # 3. Статистика блокировок
    print("\n3. СТАТИСТИКА:")
    print(f"   Консенсусов с >= {min_consensus} кошельками: {len(consensus_with_condition_id) + len(consensus_without_condition_id)}")
    print(f"   Из них с condition_id: {len(consensus_with_condition_id)}")
    print(f"   Из них без condition_id (старые): {len(consensus_without_condition_id)}")
    
    # 4. Проверка последних событий
    print("\n4. ПОСЛЕДНИЕ СОБЫТИЯ:")
    cursor.execute('SELECT data, updated_at FROM rolling_buys ORDER BY updated_at DESC LIMIT 10')
    recent = cursor.fetchall()
    
    events_with_condition_id = 0
    events_without_condition_id = 0
    
    for data_str, updated_at in recent:
        try:
            data = json.loads(data_str)
            events = data.get('events', [])
            if events:
                has_condition_id = any('conditionId' in e for e in events)
                if has_condition_id:
                    events_with_condition_id += 1
                else:
                    events_without_condition_id += 1
        except:
            pass
    
    print(f"   Событий с condition_id: {events_with_condition_id}")
    print(f"   Событий без condition_id: {events_without_condition_id}")
    
    if events_without_condition_id > events_with_condition_id:
        print(f"\n   ⚠️  ПРОБЛЕМА: Большинство событий без condition_id!")
        print(f"      Это значит, что бот не был перезапущен после исправления кода")
        print(f"      Или события создаются до того, как condition_id добавляется")
    
    db.close()
    
    print("\n" + "="*70)
    print("ВЫВОДЫ И РЕКОМЕНДАЦИИ:")
    print("="*70)
    
    issues = []
    
    if min_total_position_usd > 0:
        issues.append(f"MIN_TOTAL_POSITION_USD = ${min_total_position_usd:.2f} может блокировать сигналы")
    
    if events_without_condition_id > events_with_condition_id:
        issues.append("Большинство событий без condition_id - нужен перезапуск бота")
    
    if len(consensus_with_condition_id) == 0:
        issues.append("Нет консенсусов с condition_id для проверки блокировок")
    
    if issues:
        print("\n⚠️  НАЙДЕННЫЕ ПРОБЛЕМЫ:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
    else:
        print("\n✅ Критических проблем не найдено")
    
    print("\n📋 ДЕЙСТВИЯ:")
    print("1. Проверьте логи на сервере:")
    print("   grep -i 'BLOCKED\\|blocked\\|suppress' /opt/polymarket-bot/polymarket_notifier.log | tail -50")
    print("\n2. Если MIN_TOTAL_POSITION_USD > 0, проверьте total_usd в событиях")
    print("\n3. Перезапустите бот после исправления кода:")
    print("   sudo systemctl restart polymarket-notifier")
    print("\n4. Проверьте, что новые события содержат condition_id")

if __name__ == "__main__":
    check_all_blocks()

