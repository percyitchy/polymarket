#!/usr/bin/env python3
"""
Тестовый скрипт для отправки тестового сигнала
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from notify import TelegramNotifier
from datetime import datetime, timezone

def send_test_alert():
    """Отправить тестовый сигнал"""
    print("="*70)
    print("ОТПРАВКА ТЕСТОВОГО СИГНАЛА")
    print("="*70)
    
    notifier = TelegramNotifier()
    
    # Тестовые данные
    test_wallets = [
        "0x1234567890abcdef1234567890abcdef12345678",
        "0xabcdef1234567890abcdef1234567890abcdef12",
        "0x9876543210fedcba9876543210fedcba98765432"
    ]
    
    test_wallet_prices = {
        "0x1234567890abcdef1234567890abcdef12345678": 0.65,
        "0xabcdef1234567890abcdef1234567890abcdef12": 0.67,
        "0x9876543210fedcba9876543210fedcba98765432": 0.66
    }
    
    test_condition_id = "0xTEST1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    
    print(f"\n📤 Отправка тестового сигнала...")
    print(f"   - Кошельков: {len(test_wallets)}")
    print(f"   - Condition ID: {test_condition_id[:30]}...")
    print(f"   - Total USD: $5000.00")
    
    success = notifier.send_consensus_alert(
        condition_id=test_condition_id,
        outcome_index=0,
        wallets=test_wallets,
        wallet_prices=test_wallet_prices,
        window_minutes=15.0,
        min_consensus=3,
        alert_id=f"TEST_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        market_title="🧪 ТЕСТОВЫЙ СИГНАЛ - Проверка работы бота",
        market_slug="test-signal",
        side="BUY",
        consensus_events=3,
        total_usd=5000.0,
        end_date=datetime.now(timezone.utc),
        current_price=0.66,
        category="test",
        a_list_wallets=None
    )
    
    if success:
        print("\n✅ Тестовый сигнал отправлен успешно!")
        print("   Проверьте Telegram канал")
    else:
        print("\n❌ Ошибка при отправке тестового сигнала")
        print("   Проверьте логи")
    
    return success

if __name__ == "__main__":
    send_test_alert()

