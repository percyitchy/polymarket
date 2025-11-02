#!/usr/bin/env python3
"""Send test alert with market end time"""
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
reports_chat_id = os.getenv("TELEGRAM_REPORTS_CHAT_ID") or "-1002792658553"  # Default reports channel
chat_id = os.getenv("TELEGRAM_CHAT_ID")
topic_id = int(os.getenv("TELEGRAM_TOPIC_ID", 0)) if os.getenv("TELEGRAM_TOPIC_ID") else None

print(f"Token: {telegram_token[:10]}...")
print(f"Reports chat_id: {reports_chat_id}")
print(f"Chat_id: {chat_id}")

notifier = TelegramNotifier(telegram_token, chat_id, reports_chat_id)

# Test data
condition_id = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
outcome_index = 1

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

# Calculate end date (3 hours and 25 minutes from now, as in screenshot)
end_date = datetime.now(timezone.utc) + timedelta(hours=3, minutes=25)

# Send test alert directly to reports channel (bypassing checks)
print("Отправляю тестовый алерт в reports канал...")

# Format message manually to show end time
market_title = "Chiefs vs. Bills"
total_usd = 150588.0
current_price = 0.490
position_display = "Bills"

# Format wallet info
wallet_info = []
for i, wallet in enumerate(wallets, 1):
    wallet_short = f"{wallet[:5]}.......{wallet[-3:]}"
    price = wallet_prices.get(wallet, 0)
    
    # Get WR from database
    try:
        import sqlite3
        conn = sqlite3.connect('polymarket_notifier.db')
        cursor = conn.cursor()
        cursor.execute('SELECT win_rate, traded_total FROM wallets WHERE address = ?', (wallet,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            wr, trades = result
            wallet_info.append(f"{i}. `{wallet_short}` • WR: {wr:.1%} ({int(trades)} trades) @ ${price:.3f}")
        else:
            wallet_info.append(f"{i}. `{wallet_short}` @ ${price:.3f}")
    except:
        wallet_info.append(f"{i}. `{wallet_short}` @ ${price:.3f}")

# Calculate end time info
end_time_info = ""
if end_date:
    current_time = datetime.now(timezone.utc)
    time_diff = end_date - current_time
    if time_diff.total_seconds() > 0:
        total_seconds = int(time_diff.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        # Format: "Ends in: 3h 24m" (only this line, bold)
        ends_in_str = f"*🕐 Ends in: {hours}h {minutes}m*"
        end_time_info = f"\n{ends_in_str}"

# Build message
timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

# Build message (exactly as in notify.py)
message = f"""*🔮 Alpha Signal Detected (3 wallets)*

🎯 *Market:* {market_title}
Total position: {total_usd:,.0f} USDC💰

*Outcome:* {position_display}
👤 Traders involved:

{chr(10).join(wallet_info)}

Current price: *${current_price:.3f}*{end_time_info}

📅 {timestamp_utc} UTC"""

# Send directly to reports channel
print(f"Sending to chat_id: {reports_chat_id}")
print(f"Message length: {len(message)}")
print(f"Message preview: {message[:200]}...")

success = notifier.send_message(
    message, 
    chat_id=reports_chat_id,
    parse_mode="Markdown"
)

if success:
    print("✅ Тестовый алерт отправлен успешно в reports канал!")
else:
    print("❌ Ошибка отправки тестового алерта")

