#!/usr/bin/env python3
"""
HashDive Insiders Monitoring - Automated monitoring every N minutes
WARNING: Uses browser automation - may get rate limited
"""

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
import os
import sys


def scrape_hashdive_insiders(driver):
    """Scrape current Insiders page data"""
    
    print(f"\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🌊 Захожу на HashDive Insiders...")
    
    try:
        driver.get("https://hashdive.com/Insiders")
        time.sleep(10)  # Wait for page load
        
        # Scroll to load content
        for i in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        
        time.sleep(5)
        
        # Parse data
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "tables": []
        }
        
        # Find tables
        tables = soup.find_all('table')
        
        for idx, table in enumerate(tables):
            table_data = {
                "index": idx,
                "headers": [],
                "rows": []
            }
            
            thead = table.find('thead')
            if thead:
                headers = thead.find_all('th')
                table_data["headers"] = [h.get_text(strip=True) for h in headers]
            
            tbody = table.find('tbody')
            rows = tbody.find_all('tr') if tbody else table.find_all('tr')
            
            for row in rows[:50]:
                cells = row.find_all(['td', 'th'])
                row_data = []
                for cell in cells:
                    text = cell.get_text(strip=True)
                    links = []
                    for a in cell.find_all('a', href=True):
                        links.append({
                            "text": a.get_text(strip=True),
                            "href": a['href']
                        })
                    row_data.append({"text": text, "links": links})
                
                if row_data:
                    table_data["rows"].append(row_data)
            
            if table_data["rows"]:
                data["tables"].append(table_data)
        
        return data
        
    except Exception as e:
        print(f"❌ Ошибка при парсинге: {e}")
        return None


def monitor_hashdive(interval_minutes=5, max_iterations=None):
    """
    Monitor HashDive Insiders page
    
    Args:
        interval_minutes: How often to check (default 5 minutes)
        max_iterations: Stop after N iterations (None = unlimited)
    """
    
    print("=" * 60)
    print("🌊 HashDive Insiders Monitor")
    print("=" * 60)
    print(f"\n⚙️  Настройки:")
    print(f"   Интервал: {interval_minutes} минут")
    print(f"   Итераций: {'Бесконечно' if max_iterations is None else max_iterations}")
    print("\n⚠️  ПРЕДУПРЕЖДЕНИЕ:")
    print("   • Это парсинг через браузер (НЕ API)")
    print("   • Может занять ~3 минуты на каждую проверку")
    print("   • HashDive может ограничить по IP/User-Agent")
    print("   • Рекомендуется: не чаще 1 раза в 10-15 минут")
    print("\n💡 Совет: Запустите раз в час или вручную по запросу")
    print("=" * 60)
    
    # Setup browser ONCE
    print("\n🚀 Запускаю браузер (это займет ~30 секунд)...")
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = uc.Chrome(options=options)
    
    try:
        # Initial login
        print("\n🔐 Проверяю авторизацию...")
        driver.get("https://hashdive.com")
        time.sleep(3)
        
        page_text = driver.page_source
        if 'Log in' in page_text or 'log in' in page_text.lower():
            print("\n⚠️  ТРЕБУЕТСЯ ВХОД В СИСТЕМУ")
            print("=" * 60)
            print("ПОЖАЛУЙСТА:")
            print("1. Войдите через Google")
            print("2. Дождитесь загрузки главной страницы")
            print("3. НЕ ЗАКРЫВАЙТЕ браузер!")
            print("=" * 60)
            print("\n⏳ Ожидаю 120 секунд на ваш логин...")
            time.sleep(120)
        
        print("✅ Авторизация проверена")
        
        # Start monitoring loop
        iteration = 0
        while max_iterations is None or iteration < max_iterations:
            iteration += 1
            print("\n" + "=" * 60)
            print(f"📊 Итерация #{iteration}")
            
            # Scrape data
            data = scrape_hashdive_insiders(driver)
            
            if data and data['tables']:
                # Save data
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"hashdive_monitor_{timestamp}.json"
                
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                print(f"\n✅ Данные сохранены: {filename}")
                print(f"   Таблиц: {len(data['tables'])}")
                for table in data['tables']:
                    print(f"   - Таблица {table['index']}: {len(table['rows'])} строк")
            
            # Wait for next iteration
            if max_iterations is None or iteration < max_iterations:
                print(f"\n⏳ Следующая проверка через {interval_minutes} минут...")
                time.sleep(interval_minutes * 60)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Прерывание пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
    finally:
        print("\n⏳ Закрываю браузер...")
        driver.quit()


def main():
    print("\n🌊 HashDive Insiders Monitor")
    print("Автоматический мониторинг крупных сделок")
    print()
    
    # Ask for configuration
    print("Как часто проверять? (минут)")
    print("1. Каждые 5 минут (НЕ рекомендуется)")
    print("2. Каждые 10 минут")
    print("3. Каждые 15 минут")
    print("4. Каждый час")
    print("5. Ручной запуск (только 1 раз)")
    
    choice = input("\nВаш выбор (1-5): ").strip()
    
    intervals = {
        "1": (5, "⚠️ Очень часто - риск ограничения!"),
        "2": (10, "✅ Рекомендуется"),
        "3": (15, "✅ Безопасно"),
        "4": (60, "✅ Максимально безопасно"),
        "5": (0, "Один раз")
    }
    
    if choice == "5":
        interval = 0
        max_iter = 1
        print("\n🔄 Запуск один раз")
    elif choice in intervals:
        interval, note = intervals[choice]
        max_iter = None
        print(f"\n⚙️  Интервал: {interval} минут")
        print(f"   {note}")
        
        cont = input("\nПродолжить? (y/n): ")
        if cont.lower() != 'y':
            print("Отменено")
            return
            
        # Ask how many iterations
        print("\nСколько раз проверять?")
        print("1. Бесконечно (до прерывания Ctrl+C)")
        print("2. 10 раз")
        print("3. 5 раз")
        
        iter_choice = input("Ваш выбор (1-3): ").strip()
        if iter_choice == "1":
            max_iter = None
        elif iter_choice == "2":
            max_iter = 10
        elif iter_choice == "3":
            max_iter = 5
        else:
            max_iter = 1
    else:
        print("Неверный выбор, отменено")
        return
    
    print("\n" + "=" * 60)
    print("🚀 Начинаю мониторинг...")
    print("=" * 60)
    print("\n💡 Для остановки нажмите Ctrl+C")
    print()
    
    monitor_hashdive(interval_minutes=interval, max_iterations=max_iter)


if __name__ == "__main__":
    main()

