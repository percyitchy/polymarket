#!/usr/bin/env python3
"""
HashDive Insiders Scraper using undetected-chromedriver
This bypasses Google's automation detection
"""

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime


def scrape_hashdive():
    """Scrape HashDive Insiders page with undetected chromedriver"""
    
    print("=" * 60)
    print("HashDive Insiders Scraper (Undetected ChromeDriver)")
    print("=" * 60)
    print("\n📋 Инструкция:")
    print("1. Браузер откроется с сайтом HashDive")
    print("2. Войдите через Google OAuth")
    print("   (undetected-chromedriver обычно не блокируется)")
    print("3. После логина подождите")
    print("4. Нажмите Enter для продолжения")
    print("5. Скрипт соберет данные")
    print("\n⏳ Нажмите Enter для запуска...")
    input()
    
    # Setup undetected chromedriver
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    
    driver = uc.Chrome(options=options)
    
    try:
        print("\n🚀 Открываю HashDive...")
        driver.get("https://hashdive.com")
        time.sleep(3)
        
        driver.save_screenshot("01_before_login.png")
        print("✓ Screenshot: 01_before_login.png")
        
        # Check if login needed
        page_text = driver.page_source
        
        if 'Log in' in page_text or 'Log in' in page_text or 'log in' in page_text.lower():
            print("\n⚠️  ВЫ НЕ ЗАЛОГИНЕНЫ")
        else:
            print("\n✅ Вы возможно уже залогинены")
        
        print("=" * 60)
        print("ВАЖНО! ДАЖЕ ЕСЛИ КАЖЕТСЯ ЧТО ВЫ ВОШЛИ:")
        print("1. Проверьте, есть ли кнопка 'Log in' в правом верхнем углу")
        print("2. Если ЕСТЬ - нажмите и войдите через Google")
        print("3. Если НЕТ - отлично, значит уже залогинены!")
        print("4. Подождите пока все загрузится полностью")
        print("5. НЕ ЗАКРЫВАЙТЕ браузер!")
        print("=" * 60)
        print("\n⏳ Ожидаю 120 секунд на ваш логин...")
        print("   После логина подождите ещё 15 секунд")
        print("   чтобы все загрузилось полностью")
        time.sleep(120)
        print("✓ Проверяю состояние...")
        
        # Check login status
        driver.save_screenshot("02_check_login.png")
        
        print("\n🌊 Переход на страницу Insiders...")
        print("   Подождите, пока страница полностью загрузится!")
        driver.get("https://hashdive.com/Insiders")
        print("   ✓ Страница загружается... жду 10 секунд")
        time.sleep(10)
        
        # Scroll down to load more content
        print("📜 Прокручиваю страницу для загрузки данных...")
        for i in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Больше времени для загрузки
        
        print("   Жду ещё 5 секунд для завершения загрузки...")
        time.sleep(5)
        
        driver.save_screenshot("03_insiders_page.png")
        print("✓ Screenshot: 03_insiders_page.png")
        
        # Get page source
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract data
        print("\n📊 Извлекаю данные...")
        data = {
            "timestamp": datetime.now().isoformat(),
            "tables": [],
            "all_text": soup.get_text()[:3000],
            "links": []
        }
        
        # Find all tables and data-containers
        tables = soup.find_all('table')
        dataframes = soup.find_all('div', class_=lambda x: x and 'dataframe' in x.lower())
        
        print(f"Found {len(tables)} tables, {len(dataframes)} dataframes")
        
        # Combine all data containers
        all_containers = list(tables) + list(dataframes)
        
        for idx, table in enumerate(all_containers):
            table_data = {
                "index": idx,
                "headers": [],
                "rows": []
            }
            
            # Try to get headers from thead
            thead = table.find('thead')
            if thead:
                headers = thead.find_all('th')
                table_data["headers"] = [h.get_text(strip=True) for h in headers]
            
            # Get rows from tbody or all rows if no tbody
            # For div dataframes, use different approach
            is_div = table.name == 'div'
            
            if is_div:
                # Streamlit dataframe structure
                rows = table.find_all('div', {'role': 'row'})
                if not rows:
                    rows = table.find_all(['div', 'span'])
            else:
                tbody = table.find('tbody')
                rows = tbody.find_all('tr') if tbody else table.find_all('tr')
            
            for row in rows[:50]:  # Limit to first 50 rows
                # For div-based structures, look for different cell types
                if is_div:
                    cells = row.find_all(['div', 'span'], recursive=False)
                else:
                    cells = row.find_all(['td', 'th'])
                
                row_data = []
                for cell in cells:
                    text = cell.get_text(strip=True)
                    # Check for links
                    links = []
                    for a in cell.find_all('a', href=True):
                        links.append({
                            "text": a.get_text(strip=True),
                            "href": a['href']
                        })
                    row_data.append({
                        "text": text,
                        "links": links
                    })
                
                if row_data:
                    table_data["rows"].append(row_data)
            
            if table_data["rows"]:
                data["tables"].append(table_data)
        
        # Find all links with addresses (Polygon addresses)
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link['href']
            text = link.get_text(strip=True)
            # Check if it's an address (starts with 0x)
            if href.startswith('http') and '0x' in text or href.startswith('0x'):
                data["links"].append({
                    "text": text,
                    "href": href
                })
        
        driver.save_screenshot("04_final.png")
        print("\n✅ Извлечено:")
        print(f"  - Таблиц: {len(data['tables'])}")
        print(f"  - Ссылок: {len(data['links'])}")
        
        return data
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        driver.save_screenshot("error.png")
        raise
        
    finally:
        print("\n⏳ Браузер останется открытым 60 секунд для проверки...")
        print("   Вы можете посмотреть результаты и скриншоты")
        time.sleep(60)
        print("\n⏳ Закрываю браузер...")
        driver.quit()


def main():
    print("\n" + "=" * 60)
    print("🌊 HashDive Insiders Scraper")
    print("Using undetected-chromedriver")
    print("=" * 60)
    
    data = scrape_hashdive()
    
    if data:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"hashdive_data_{timestamp}.json"
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Данные сохранены в {filename}")
        
        print("\n📊 КРАТКАЯ СВОДКА:")
        print("=" * 60)
        
        if data['tables']:
            for table in data['tables']:
                print(f"\n📋 Таблица #{table['index']}:")
                print(f"   Заголовков: {len(table['headers'])}")
                if table['headers']:
                    print(f"   Заголовки: {', '.join(table['headers'][:5])}")
                print(f"   Строк: {len(table['rows'])}")
                
                if table['rows']:
                    first_row = table['rows'][0]
                    if first_row:
                        print(f"   Первая строка: {first_row[0]['text'] if first_row else 'N/A'}")
                        if first_row[0]['links']:
                            print(f"   Ссылки: {len(first_row[0]['links'])}")
        else:
            print("\n⚠️  Таблицы не найдены")
            print("\nТекст на странице (первые 500 символов):")
            print(data['all_text'][:500])
        
        if data['links']:
            print(f"\n🔗 Найдено ссылок: {len(data['links'])}")
            for link in data['links'][:5]:
                print(f"   - {link['text']}: {link['href']}")
        
        print("\n" + "=" * 60)
        print(f"\n💡 Откройте {filename} чтобы посмотреть все данные")
    else:
        print("\n❌ Не удалось получить данные")


if __name__ == "__main__":
    main()

