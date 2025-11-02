#!/usr/bin/env python3
"""
HashDive Insiders Telegram Monitor - Persistent Session Version
Saves browser session to avoid re-login every time
"""

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import requests
import time
from datetime import datetime
import os
from dotenv import load_dotenv
import sys

load_dotenv()


class HashDiveTelegramNotifier:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("HASHDIVE_CHAT_ID", "-1003285149330")
        self.base_url = "https://hashdive.com/Insiders"
    
    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
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
            print(f"❌ Error: {e}")
            return False
    
    def format_whale_alert(self, trades: list) -> str:
        if not trades:
            return None
        
        trades_sorted = sorted(trades, key=lambda x: float(x.get('invested', 0)), reverse=True)
        top_trades = trades_sorted[:5]
        
        message = f"""🐋 <b>HashDive Insiders: Кит активность!</b>

📊 <b>Крупнейшие сделки:</b>

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
• {outcome} | PnL: {pnl_formatted}
• Invested: {invested_formatted}
• <a href="https://hashdive.com/Analyze_User?user_address={user}">👤</a> {user_short}

"""
        
        message += f"""━━━━━━━━━━━━━━━━━━
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔗 <a href="https://hashdive.com/Insiders">HashDive Insiders</a>"""
        
        return message
    
    def scrape_and_alert(self, driver):
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌊 Parsing...")
            driver.get(self.base_url)
            time.sleep(10)
            
            for i in range(5):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
            
            time.sleep(5)
            
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
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Sent {len(trades)} trades")
                        return True
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ No significant trades")
            return False
                
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error: {e}")
            return False


def get_driver(user_data_dir=None, headless=True):
    """Get Chrome driver with persistent session"""
    
    options = uc.ChromeOptions()
    
    if headless:
        options.add_argument("--headless=new")
    
    # Use persistent user data directory
    if user_data_dir:
        options.add_argument(f"--user-data-dir={user_data_dir}")
    
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    driver = uc.Chrome(options=options)
    return driver


def monitor_with_alerts(interval_minutes=15, headless=True):
    """Monitor HashDive with persistent session"""
    
    print("=" * 60)
    print("🐋 HashDive Telegram Monitor (Persistent Session)")
    print("=" * 60)
    print(f"⚙️  Interval: {interval_minutes} minutes")
    print(f"⚙️  Headless: {headless}")
    print(f"⚙️  Session: PERSISTENT (сохраняется)")
    print("=" * 60)
    
    notifier = HashDiveTelegramNotifier()
    
    # Use persistent user data directory
    user_data_dir = "/tmp/hashdive_chrome_profile"
    
    print("\n🚀 Starting browser with saved session...")
    driver = get_driver(user_data_dir=user_data_dir, headless=headless)
    
    try:
        # Check login
        print("\n🔐 Checking authentication...")
        driver.get("https://hashdive.com")
        time.sleep(5)
        
        page_text = driver.page_source
        if 'Log in' in page_text or 'log in' in page_text.lower():
            print("\n⚠️  LOGIN REQUIRED!")
            print("=" * 60)
            print("FIRST TIME SETUP:")
            print("You need to login ONCE to HashDive")
            print("=" * 60)
            
            if headless:
                print("\n⚠️  Cannot login in headless mode!")
                print("Please run with --no-headless first:")
                print("  python3 hashdive_telegram_persistent.py --no-headless")
                return
            
            print("\n⏳ Waiting 180 seconds for login...")
            print("Login in the browser that opened!")
            time.sleep(180)  # 3 minutes for login
        
        print("✅ Ready!")
        
        iteration = 0
        while True:
            iteration += 1
            print(f"\n{'='*60}")
            print(f"📊 Iteration #{iteration} - {datetime.now().strftime('%H:%M:%S')}")
            
            notifier.scrape_and_alert(driver)
            
            wait_seconds = interval_minutes * 60
            print(f"\n⏳ Next check in {interval_minutes} min...")
            time.sleep(wait_seconds)
            
    except KeyboardInterrupt:
        print("\n⚠️  Stopped")
    finally:
        print("\n⏳ Closing...")
        # Don't quit - keep session alive
        # driver.quit()


def main():
    print("\n🐋 HashDive Telegram Monitor (Persistent)")
    
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        print("❌ TELEGRAM_BOT_TOKEN not found")
        sys.exit(1)
    
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
    print(f"⚙️  Session: SAVED in /tmp/hashdive_chrome_profile")
    print("\n🚀 Starting...")
    print("=" * 60)
    
    monitor_with_alerts(interval_minutes=interval, headless=headless)


if __name__ == "__main__":
    main()

