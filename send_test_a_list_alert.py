#!/usr/bin/env python3
"""
Тестовый скрипт для отправки A-list уведомления в топик
"""

import os
import sys
from dotenv import load_dotenv
from notify import TelegramNotifier
from datetime import datetime, timezone

load_dotenv()

def main():
    print("=" * 80)
    print("🧪 ТЕСТОВОЕ A-LIST УВЕДОМЛЕНИЕ")
    print("=" * 80)
    
    # Инициализация notifier
    notifier = TelegramNotifier()
    
    # Проверка конфигурации
    if not notifier.bot_token:
        print("❌ TELEGRAM_BOT_TOKEN не установлен в .env")
        return
    
    if not notifier.reports_chat_id:
        print("❌ TELEGRAM_REPORTS_CHAT_ID не установлен в .env")
        return
    
    if not notifier.a_list_topic_id:
        print("⚠️  TELEGRAM_A_LIST_TOPIC_ID не установлен в .env")
        print("   Уведомление будет отправлено без топика")
    else:
        print(f"✅ Topic ID для A-list: {notifier.a_list_topic_id}")
    
    print()
    print("📋 Параметры тестового уведомления:")
    print(f"   Chat ID: {notifier.reports_chat_id}")
    print(f"   Topic ID: {notifier.a_list_topic_id}")
    print()
    
    # Тестовые данные
    test_condition_id = "0x1234567890abcdef1234567890abcdef12345678"
    test_outcome_index = 0
    test_wallets = [
        "0x1111111111111111111111111111111111111111",
        "0x2222222222222222222222222222222222222222",
        "0x3333333333333333333333333333333333333333"
    ]
    test_a_list_wallets = [
        "0x1111111111111111111111111111111111111111",
        "0x2222222222222222222222222222222222222222"
    ]
    test_wallet_prices = {
        test_wallets[0]: 0.65,
        test_wallets[1]: 0.67,
        test_wallets[2]: 0.66
    }
    test_category = "crypto/BTC"
    test_market_title = "Will Bitcoin price exceed $100,000 by end of 2025?"
    test_total_usd = 15000.0
    
    print("📤 Отправка тестового уведомления...")
    print(f"   Market: {test_market_title}")
    print(f"   Category: {test_category}")
    print(f"   Wallets: {len(test_wallets)}")
    print(f"   A-list wallets: {len(test_a_list_wallets)}")
    print(f"   Total USD: ${test_total_usd:,.2f}")
    print()
    
    # Отправка уведомления
    success = notifier.send_consensus_alert(
        condition_id=test_condition_id,
        outcome_index=test_outcome_index,
        wallets=test_wallets,
        wallet_prices=test_wallet_prices,
        window_minutes=20.0,
        min_consensus=2,
        alert_id="TEST_A_LIST",
        market_title=test_market_title,
        market_slug="bitcoin-price-100k-2025",
        side="BUY",
        consensus_events=3,
        total_usd=test_total_usd,
        end_date=None,
        current_price=0.66,
        category=test_category,
        a_list_wallets=test_a_list_wallets
    )
    
    if success:
        print("✅ Тестовое уведомление отправлено успешно!")
        print()
        print("💡 Проверьте Telegram канал и топик A-list Alerts")
    else:
        print("❌ Ошибка при отправке тестового уведомления")
        print("   Проверьте логи для деталей")
    
    print("=" * 80)

if __name__ == "__main__":
    main()

