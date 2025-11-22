#!/usr/bin/env python3
"""Send test alert to Low Size topic (total_usd < $10,000)"""
import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from notify import TelegramNotifier

load_dotenv()

# Initialize notifier
telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
reports_chat_id = os.getenv("TELEGRAM_REPORTS_CHAT_ID")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

print(f"Token: {telegram_token[:10] if telegram_token else 'None'}...")
print(f"Reports chat_id: {reports_chat_id}")
print(f"Chat_id: {chat_id}")
print()

notifier = TelegramNotifier(telegram_token, chat_id, reports_chat_id)

# Test data for Low Size alert (total_usd < $10,000)
condition_id = "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
outcome_index = 0

# Sample wallets
wallets = [
    "0x220ce36c47fa467152b3bd8d431af74f232243c8",
    "0xb744f56635b537e859152d14b022af5afe485210",
    "0xc3c07f26b026052b2c2b5ce022c6f611ce4493fd"
]

wallet_prices = {
    "0x220ce36c47fa467152b3bd8d431af74f232243c8": 0.410,
    "0xb744f56635b537e859152d14b022af5afe485210": 0.400,
    "0xc3c07f26b026052b2c2b5ce022c6f611ce4493fd": 0.440
}

# Calculate end date (2 hours from now)
end_date = datetime.now(timezone.utc) + timedelta(hours=2)

# Send test alert with LOW SIZE (total_usd < $10,000)
print("Отправляю тестовый алерт в Low Size канал (total_usd < $10,000)...")
print()

# Format message manually to show end time
market_title = "Test Market - Low Size Alert"
total_usd = 5000.0  # Low Size (< $10k)
current_price = 0.450
position_display = "Test Outcome"

print(f"Market: {market_title}")
print(f"Total USD: ${total_usd:,.2f}")
print(f"Expected topic: Low Size Alerts")
if hasattr(notifier, 'low_size_topic_id') and notifier.low_size_topic_id:
    print(f"Topic ID: {notifier.low_size_topic_id}")
else:
    print("⚠️  Topic ID не настроен в .env")
print()

# Send test alert
success = notifier.send_consensus_alert(
    condition_id=condition_id,
    outcome_index=outcome_index,
    wallets=wallets,
    wallet_prices=wallet_prices,
    window_minutes=10.0,
    min_consensus=3,
    alert_id="test_low_size_" + datetime.now().strftime("%Y%m%d%H%M%S"),
    market_title=market_title,
    market_slug="test-low-size",
    side="BUY",
    consensus_events=3,
    total_usd=total_usd,
    end_date=end_date,
    current_price=current_price
)

if success:
    print()
    print("✅ Тестовый алерт успешно отправлен в Low Size канал!")
    print(f"   Канал: {reports_chat_id}")
    if hasattr(notifier, 'low_size_topic_id') and notifier.low_size_topic_id:
        print(f"   Topic ID: {notifier.low_size_topic_id}")
    else:
        print("   Topic ID: (проверьте логи бота)")
    print(f"   Total USD: ${total_usd:,.2f}")
    print()
    print("💡 Проверьте канал 'POLY DAO TEST' → тема 'Low Size Alerts'")
else:
    print()
    print("❌ Не удалось отправить тестовый алерт")
    print("Проверьте логи для деталей")

