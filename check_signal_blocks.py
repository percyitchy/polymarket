#!/usr/bin/env python3
"""
Проверка всех возможных блокировок сигналов
"""
import sqlite3
import json
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

def check_all_blocks():
    print("="*70)
    print("ПОЛНАЯ ПРОВЕРКА БЛОКИРОВОК СИГНАЛОВ")
    print("="*70)
    
    db = sqlite3.connect('polymarket_notifier.db')
    cursor = db.cursor()
    
    # Настройки
    min_consensus = int(os.getenv('MIN_CONSENSUS', '3'))
    alert_window_min = float(os.getenv('ALERT_WINDOW_MIN', '20.0'))
    alert_cooldown_min = float(os.getenv('ALERT_COOLDOWN_MIN', '30.0'))
    
    print(f"\nНастройки:")
    print(f"  MIN_CONSENSUS: {min_consensus}")
    print(f"  ALERT_WINDOW_MIN: {alert_window_min} минут")
    print(f"  ALERT_COOLDOWN_MIN: {alert_cooldown_min} минут")
    
    # 1. Проверяем консенсусы в rolling_buys
    print(f"\n1. КОНСЕНСУСЫ В ROLLING_BUYS:")
    cursor.execute('SELECT k, data, updated_at FROM rolling_buys ORDER BY updated_at DESC LIMIT 50')
    rows = cursor.fetchall()
    
    potential_signals = []
    for k, data_str, updated_at in rows:
        try:
            data = json.loads(data_str)
            events = data.get('events', [])
            wallets = {e.get('wallet') for e in events if e.get('wallet')}
            
            if len(wallets) >= min_consensus:
                # Извлекаем condition_id
                condition_id = None
                outcome_index = None
                side = None
                
                for event in events:
                    if 'conditionId' in event:
                        condition_id = event['conditionId']
                    if 'outcomeIndex' in event:
                        outcome_index = event['outcomeIndex']
                    if 'side' in event:
                        side = event['side']
                
                market_title = events[0].get('marketTitle', 'N/A') if events else 'N/A'
                
                potential_signals.append({
                    'condition_id': condition_id,
                    'outcome_index': outcome_index,
                    'side': side,
                    'wallets': len(wallets),
                    'market': market_title,
                    'updated_at': updated_at,
                    'events': events
                })
        except Exception as e:
            pass
    
    print(f"   Найдено {len(potential_signals)} потенциальных сигналов (>= {min_consensus} кошельков)")
    
    if potential_signals:
        print(f"\n   Проверяю каждый сигнал на блокировки:\n")
        
        for i, signal in enumerate(potential_signals[:10], 1):
            print(f"{i}. {signal['market'][:50]}")
            print(f"   Кошельков: {signal['wallets']}")
            print(f"   Condition ID: {signal['condition_id'][:30] if signal['condition_id'] else 'N/A'}...")
            print(f"   Outcome: {signal['outcome_index']}, Side: {signal['side']}")
            
            if not signal['condition_id']:
                print(f"   ❌ БЛОКИРОВКА: condition_id отсутствует в событиях!")
                print(f"      (старые события не содержат condition_id)")
                continue
            
            # Проверка 1: Уже отправлен алерт?
            cursor.execute('''
                SELECT sent_at FROM alerts_sent
                WHERE condition_id = ? AND outcome_index = ? AND side = ?
                ORDER BY sent_at DESC LIMIT 1
            ''', (signal['condition_id'], signal['outcome_index'] or 0, signal['side'] or 'BUY'))
            alert = cursor.fetchone()
            
            if alert:
                alert_time = datetime.fromisoformat(alert[0].replace('Z', '+00:00'))
                signal_time = datetime.fromisoformat(signal['updated_at'].replace('Z', '+00:00'))
                diff_minutes = (signal_time - alert_time).total_seconds() / 60
                
                if diff_minutes < alert_cooldown_min:
                    print(f"   ⚠️  БЛОКИРОВКА: Cooldown активен ({diff_minutes:.1f} < {alert_cooldown_min} мин)")
                else:
                    print(f"   ✅ Алерт уже отправлен: {alert[0][:19]} ({diff_minutes:.1f} мин назад)")
            else:
                print(f"   ❌ Алерт НЕ отправлен - проверяю причины...")
                
                # Проверка 2: Проверяем цены в событиях
                prices = [e.get('price', 0) for e in signal['events'] if e.get('price')]
                if prices:
                    avg_price = sum(prices) / len(prices)
                    print(f"   Средняя цена в событиях: ${avg_price:.4f}")
                    
                    if avg_price <= 0.02 or avg_price >= 0.98:
                        print(f"   ❌ БЛОКИРОВКА: Цена указывает на закрытый рынок (${avg_price:.4f})")
                    elif avg_price <= 0.001 or avg_price >= 0.999:
                        print(f"   ❌ БЛОКИРОВКА: Рынок разрешен (${avg_price:.4f})")
                
                # Проверка 3: Проверяем временное окно
                if signal['events']:
                    timestamps = [e.get('ts', 0) for e in signal['events'] if e.get('ts')]
                    if len(timestamps) >= 2:
                        time_span = max(timestamps) - min(timestamps)
                        time_span_minutes = time_span / 60
                        print(f"   Временной разброс: {time_span_minutes:.1f} минут")
                        
                        if time_span_minutes > alert_window_min:
                            print(f"   ⚠️  БЛОКИРОВКА: События вне окна ({time_span_minutes:.1f} > {alert_window_min} мин)")
            
            print()
    
    # 2. Проверяем статистику блокировок
    print("\n2. СТАТИСТИКА БЛОКИРОВОК:")
    print("   (проверьте логи на сервере для детальной статистики)")
    print("   Команда для проверки:")
    print("   grep -i 'BLOCKED\\|blocked\\|suppress' /opt/polymarket-bot/polymarket_notifier.log | tail -50")
    
    # 3. Проверяем последние события
    print("\n3. ПОСЛЕДНИЕ СОБЫТИЯ:")
    cursor.execute('SELECT data, updated_at FROM rolling_buys ORDER BY updated_at DESC LIMIT 5')
    recent = cursor.fetchall()
    
    for data_str, updated_at in recent:
        try:
            data = json.loads(data_str)
            events = data.get('events', [])
            if events:
                wallets = {e.get('wallet') for e in events if e.get('wallet')}
                market_title = events[0].get('marketTitle', 'N/A')
                condition_id = events[0].get('conditionId') if events else None
                
                print(f"   {updated_at[:19]}: {len(wallets)} кошельков - {market_title[:40]}")
                if condition_id:
                    print(f"      Condition ID: {condition_id[:30]}...")
                else:
                    print(f"      ⚠️  Condition ID отсутствует (старое событие)")
        except:
            pass
    
    db.close()
    
    print("\n" + "="*70)
    print("РЕКОМЕНДАЦИИ:")
    print("="*70)
    print("1. Проверьте логи на сервере для детальной информации о блокировках")
    print("2. Убедитесь, что condition_id сохраняется в новых событиях (код исправлен)")
    print("3. Проверьте настройки MIN_CONSENSUS и ALERT_WINDOW_MIN")
    print("4. Проверьте, не блокируются ли сигналы из-за цен или активности рынков")

if __name__ == "__main__":
    check_all_blocks()

