#!/usr/bin/env python3
"""
HashDive Insiders Telegram Monitor - Server Version
Runs in headless mode for server deployment
"""

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import requests
import json
import time
from datetime import datetime
import os
from dotenv import load_dotenv
import sys

load_dotenv()


class HashDiveTelegramNotifier:
    """Send HashDive Insiders alerts to Telegram"""
    
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("HASHDIVE_CHAT_ID", "-1003285149330")
        self.base_url = "https://hashdive.com/Insiders"
        
        if not self.bot_token:
            print("⚠️  TELEGRAM_BOT_TOKEN не установлен")
    
    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send message to Telegram"""
        if not self.bot_token:
            print(f"[TEST] Would send: {text[:100]}")
            return False
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        
        try:
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"❌ Ошибка Telegram: {e}")
            return False
    
    def format_whale_alert(self, trades: list) -> str:
        """Format whale trades as Telegram alert"""
        if not trades:
            return None
        
        trades_sorted = sorted(trades, key=lambda x: float(x.get('invested', 0)), reverse=True)
        top_trades = trades_sorted[:5]
        
        message = f"""🐋 <b>HashDive Insiders: Кит активность обнаружена!</b>

📊 <b>Крупнейшие сделки за последний период:</b>

"""
        
        for i, trade in enumerate(top_trades, 1):
            market = trade.get('market', 'N/A')[:60]
            outcome = trade.get('outcome', 'N/A')
            current_price = trade.get('current_price', '0')
            entry_price = trade.get('entry_price', '0')
            pnl = trade.get('pnl', '0')
            invested = trade.get('invested', '0')
            user = trade.get('user_address', 'N/A')
            
            try:
                invested_float = float(invested)
                pnl_float = float(pnl)
                invested_formatted = f"${invested_float:,.0f}"
                
                if pnl_float > 0:
                    pnl_formatted = f"📈 +{pnl_float:.2f}%"
                else:
                    pnl_formatted = f"📉 {pnl_float:.2f}%"
            except:
                invested_formatted = f"${invested}"
                pnl_formatted = pnl
            
            if len(user) > 20:
                user_short = f"{user[:10]}...{user[-6:]}"
            else:
                user_short = user
            
            message += f"""<b>{i}. {market[:40]}</b>
• Исход: {outcome}
• Цена: {current_price} → {entry_price}
• PnL: {pnl_formatted}
• Вложено: {invested_formatted}
• <a href="https://hashdive.com/Analyze_User?user_address={user}">👤</a> {user_short}

"""
        
        message += f"""━━━━━━━━━━━━━━━━━━
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔗 <a href="https://hashdive.com/Insiders">HashDive Insiders</a>"""
        
        return message
    
    def scrape_and_alert(self, driver):
        """Scrape Insiders and send alerts"""
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌊 Parsing Insiders...")
            driver.get(self.base_url)
            time.sleep(10)
            
            # Scroll
            for i in range(5):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
            
            time.sleep(5)
            
            # Parse
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            trades = []
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')
                
                for row in rows[:20]:
                    cells = row.find_all(['td', 'th'])
                    row_data = [cell.get_text(strip=True) for cell in cells]
                    
                    if len(row_data) >= 7:
                        try:
                            trade = {
                                'market': row_data[0] if len(row_data) > 0 else '',
                                'outcome': row_data[1] if len(row_data) > 1 else '',
                                'user_address': row_data[2] if len(row_data) > 2 else '',
                                'current_price': row_data[3] if len(row_data) > 3 else '0',
                                'entry_price': row_data[4] if len(row_data) > 4 else '0',
                                'pnl': row_data[5] if len(row_data) > 5 else '0',
                                'invested': row_data[6] if len(row_data) > 6 else '0'
                            }
                            
                            if float(trade.get('invested', 0)) > 1000:
                                trades.append(trade)
                        except:
                            pass
            
            if trades:
                message = self.format_whale_alert(trades)
                if message:
                    sent = self.send_message(message)
                    if sent:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Sent alert with {len(trades)} trades")
                        return True
                    else:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Failed to send alert")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  No significant trades")
                return False
                
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error: {e}")
            return False


def monitor_with_alerts(interval_minutes=15, headless=True):
    """Monitor HashDive and send alerts to Telegram"""
    
    print("=" * 60)
    print("🐋 HashDive Insiders Telegram Monitor (Server Mode)")
    print("=" * 60)
    print(f"⚙️  Interval: {interval_minutes} minutes")
    print(f"⚙️  Headless: {headless}")
    print(f"⚙️  Chat: {os.getenv('HASHDIVE_CHAT_ID', '-1003285149330')}")
    print("=" * 60)
    
    notifier = HashDiveTelegramNotifier()
    
    # Setup browser
    print("\n🚀 Starting browser...")
    options = uc.ChromeOptions()
    
    if headless:
        options.add_argument("--headless=new")
        print("   Running in headless mode")
    
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    driver = uc.Chrome(options=options)
    
    try:
        # Login
        print("\n🔐 Checking authorization...")
        driver.get("https://hashdive.com")
        time.sleep(5)
        
        page_text = driver.page_source
        if 'Log in' in page_text or 'log in' in page_text.lower():
            print("\n⚠️  LOGIN REQUIRED!")
            print("=" * 60)
            print("This is a FIRST RUN setup.")
            print("You need to login manually ONCE on the server.")
            print("\nTwo options:")
            print("1. Run with headless=False first time to login")
            print("2. Use remote debugging to login from another computer")
            print("=" * 60)
            
            if headless:
                print("\n⚠️  Headless mode detected - cannot login!")
                print("Run with: headless=False first time, or:")
                print("Start headless with: --remote-debugging-port=9222")
                return
        
        print("✅ Ready!")
        
        iteration = 0
        while True:
            iteration += 1
            print(f"\n{'='*60}")
            print(f"📊 Iteration #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            notifier.scrape_and_alert(driver)
            
            wait_seconds = interval_minutes * 60
            print(f"\n⏳ Next check in {interval_minutes} min...")
            time.sleep(wait_seconds)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Stopped by user")
    finally:
        print("\n⏳ Closing browser...")
        driver.quit()


def main():
    print("\n🐋 HashDive Insiders Telegram Monitor (Server)")
    print("=" * 60)
    
    # Check bot token
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN not found in .env")
        print("Add: TELEGRAM_BOT_TOKEN=your_token")
        sys.exit(1)
    
    print("✅ Telegram configured")
    
    # Parse args
    headless = "--no-headless" not in sys.argv
    interval = 15
    
    if "--interval" in sys.argv:
        try:
            idx = sys.argv.index("--interval")
            interval = int(sys.argv[idx + 1])
        except:
            pass
    
    print(f"⚙️  Headless: {headless}")
    print(f"⚙️  Interval: {interval} minutes")
    print("\n🚀 Starting monitor...")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    monitor_with_alerts(interval_minutes=interval, headless=headless)


if __name__ == "__main__":
    main()

