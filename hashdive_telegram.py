#!/usr/bin/env python3
"""
HashDive Insiders Telegram Alerts
Sends whale trade alerts to Telegram channel
"""

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import requests
import json
import time
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()


class HashDiveTelegramNotifier:
    """Send HashDive Insiders alerts to Telegram"""
    
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("HASHDIVE_CHAT_ID", "-1003285149330")  # Новый канал
        self.base_url = "https://hashdive.com/Insiders"
        
        if not self.bot_token:
            print("⚠️  TELEGRAM_BOT_TOKEN не установлен в .env")
    
    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send message to Telegram"""
        if not self.bot_token:
            print(f"Would send: {text}")
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
            print(f"❌ Ошибка отправки в Telegram: {e}")
            return False
    
    def format_whale_alert(self, trades: list) -> str:
        """Format whale trades as Telegram alert"""
        if not trades:
            return None
        
        # Sort by invested amount
        trades_sorted = sorted(trades, key=lambda x: float(x.get('invested', 0)), reverse=True)
        top_trades = trades_sorted[:5]  # Top 5
        
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
            
            # Format numbers
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
            
            # Shorten user address
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
            print("\n🌊 Переходим на Insiders...")
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
            
            # Find tables
            tables = soup.find_all('table')
            for table in tables:
                headers = []
                thead = table.find('thead')
                if thead:
                    headers = [h.get_text(strip=True) for h in thead.find_all('th')]
                
                # Get rows
                tbody = table.find('tbody')
                rows = tbody.find_all('tr') if tbody else table.find_all('tr')
                
                for row in rows[:20]:
                    cells = row.find_all(['td', 'th'])
                    row_data = [cell.get_text(strip=True) for cell in cells]
                    
                    # Check if this looks like trade data
                    if len(row_data) >= 7:  # Minimum columns for trade data
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
                            
                            # Filter significant trades (invested > 1000)
                            if float(trade.get('invested', 0)) > 1000:
                                trades.append(trade)
                        except:
                            pass
            
            if trades:
                message = self.format_whale_alert(trades)
                if message:
                    self.send_message(message)
                    print(f"✅ Отправлено алерта с {len(trades)} сделками")
                    return True
            else:
                print("⚠️  Нет крупных сделок для алерта")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False


def monitor_with_alerts(interval_minutes=15):
    """Monitor HashDive and send alerts to Telegram"""
    
    print("=" * 60)
    print("🐋 HashDive Insiders Telegram Monitor")
    print("=" * 60)
    print(f"\n⚙️  Настройки:")
    print(f"   Интервал: {interval_minutes} минут")
    print(f"   Chat ID: -1003285149330")
    print("\n✅ Начинаю мониторинг...")
    
    notifier = HashDiveTelegramNotifier()
    
    # Setup browser
    print("\n🚀 Запускаю браузер...")
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = uc.Chrome(options=options)
    
    try:
        # Login once
        print("\n🔐 Проверяю авторизацию...")
        driver.get("https://hashdive.com")
        time.sleep(3)
        
        page_text = driver.page_source
        if 'Log in' in page_text or 'log in' in page_text.lower():
            print("\n⚠️  ТРЕБУЕТСЯ ВХОД")
            print("Войдите через Google в открывшемся браузере")
            print("⏳ Ожидаю 120 секунд...")
            time.sleep(120)
        
        print("✅ Готово!")
        
        iteration = 0
        while True:
            iteration += 1
            print(f"\n{'='*60}")
            print(f"📊 Итерация #{iteration} - {datetime.now().strftime('%H:%M:%S')}")
            
            # Scrape and alert
            notifier.scrape_and_alert(driver)
            
            # Wait
            print(f"\n⏳ Следующая проверка через {interval_minutes} мин...")
            time.sleep(interval_minutes * 60)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Остановлено пользователем")
    finally:
        driver.quit()


if __name__ == "__main__":
    print("\n🐋 HashDive Insiders Telegram Monitor")
    print("Отправляет алерты о крупных сделках в Telegram\n")
    
    # Check bot token
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN не найден в .env")
        print("Добавьте: TELEGRAM_BOT_TOKEN=ваш_токен")
        exit(1)
    
    print("✅ Telegram настроен")
    print("\n🚀 Начинаю мониторинг каждые 15 минут...")
    
    monitor_with_alerts(interval_minutes=15)

