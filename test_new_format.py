#!/usr/bin/env python3
"""Test new notification format"""
import sys
import os
sys.path.insert(0, '/home/ubuntu')

from notify import TelegramNotifier
from dotenv import load_dotenv

load_dotenv()

# Initialize notifier
token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

if not token or not chat_id:
    print("❌ Missing Telegram credentials")
    sys.exit(1)

notifier = TelegramNotifier(token, chat_id)

# Test with example wallets
test_wallets = [
    "0x83b9f9e2d28ab875b9c9f73cdd5535c4c8926124",
    "0x3cdaf931c538750ffa43b4de25366401d7446e17"
]

print("🧪 Testing new notification format...")

success = notifier.send_consensus_alert(
    condition_id="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
    outcome_index=0,
    wallets=test_wallets,
    window_minutes=15.0,
    min_consensus=2,
    alert_id="TEST123"
)

if success:
    print("✅ Test message sent successfully!")
else:
    print("❌ Failed to send test message")

