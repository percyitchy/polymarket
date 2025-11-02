#!/usr/bin/env python3
"""
HashDive Insiders Scraper with Google OAuth
Automatically handles login via saved session or manual login
"""

import asyncio
import json
import sys
from playwright.async_api import async_playwright
from datetime import datetime
import os


async def scrape_hashdive():
    """Scrape HashDive Insiders page with manual OAuth login"""
    
    print("=" * 60)
    print("HashDive Insiders Scraper (Google OAuth)")
    print("=" * 60)
    print("\n📋 Инструкция:")
    print("1. Браузер откроется с сайтом HashDive")
    print("2. Вы НЕ ВЫХОДИТЕ из браузера!")
    print("3. Нажмите 'Log in' и войдите через Google")
    print("4. После логина подождите 30 секунд")
    print("5. Скрипт автоматически соберет данные")
    print("\n⏳ Нажмите Enter, когда будете готовы...")
    input()
    
    async with async_playwright() as p:
        # Try to use real Chrome browser instead of Chromium
        try:
            browser = await p.chromium.launch(
                headless=False,
                channel='chrome'  # Use real Chrome if available
            )
        except:
            # Fallback to Chromium with stealth options
            browser = await p.chromium.launch(
                headless=False,
                args=['--disable-blink-features=AutomationControlled']
            )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York'
        )
        page = await context.new_page()
        
        try:
            print("\n🚀 Открываю HashDive...")
            await page.goto("https://hashdive.com", wait_until="networkidle", timeout=60000)
            await asyncio.sleep(2)
            
            await page.screenshot(path="01_page_loaded.png")
            print("✓ Screenshot: 01_page_loaded.png")
            
            # Check if already logged in
            page_text = await page.evaluate("document.body.innerText")
            
            if "Log in" in page_text:
                print("\n⚠️  ВЫ НЕ ЗАЛОГИНЕНЫ")
                print("=" * 60)
                print("ПОЖАЛУЙСТА, ВЫПОЛНИТЕ СЛЕДУЮЩЕЕ:")
                print("1. Найдите и нажмите кнопку 'Log in'")
                print("2. Войдите через Google OAuth")
                print("3. Дождитесь, когда увидите главную страницу")
                print("4. НЕ ЗАКРЫВАЙТЕ браузер")
                print("=" * 60)
                print("\n⏳ Ожидаю вашего логина (60 секунд)...")
                print("После того, как залогинитесь, подождите до конца таймера...")
                
                await asyncio.sleep(60)
                await page.screenshot(path="02_after_manual_login.png")
                print("\n✓ Проверяю, залогинились ли вы...")
            else:
                print("\n✓ Похоже, вы уже залогинены")
            
            # Navigate to Insiders
            print("\n🌊 Переход на страницу Insiders...")
            await page.goto("https://hashdive.com/Insiders", wait_until="networkidle", timeout=60000)
            await asyncio.sleep(5)
            
            await page.screenshot(path="03_insiders_page.png")
            print("✓ Screenshot: 03_insiders_page.png")
            
            # Check if we have access
            page_text = await page.evaluate("document.body.innerText")
            
            if "Free period ended" in page_text or "purchase a Pro plan" in page_text:
                print("\n❌ Нет доступа к данным")
                print("Сообщение на странице указывает, что нужен Pro план")
                print("\nПроверьте скриншот 03_insiders_page.png")
            else:
                print("\n✅ Доступ получен! Извлекаю данные...")
            
            # Extract table data
            data = await page.evaluate("""
                () => {
                    const result = {
                        tables: [],
                        text: document.body.innerText.substring(0, 3000),
                        elements: []
                    };
                    
                    // Get all tables
                    document.querySelectorAll('table').forEach((table, idx) => {
                        // Try to get headers
                        const headerCells = Array.from(table.querySelectorAll('thead th, tbody tr:first-child th'))
                            .map(h => h.innerText.trim());
                        
                        // If no headers in thead, try to get from first row
                        let headers = headerCells;
                        if (headers.length === 0) {
                            const firstRow = table.querySelector('tbody tr, tr');
                            if (firstRow) {
                                headers = Array.from(firstRow.querySelectorAll('th, td'))
                                    .map(cell => cell.innerText.trim());
                            }
                        }
                        
                        // Get all rows
                        const rows = [];
                        document.querySelectorAll('tbody tr, table tr').forEach((row, rowIdx) => {
                            const cells = Array.from(row.querySelectorAll('td, th'));
                            const rowData = cells.map(cell => {
                                const text = cell.innerText.trim();
                                const links = Array.from(cell.querySelectorAll('a')).map(a => ({
                                    text: a.innerText,
                                    href: a.href
                                }));
                                return {text: text, links: links};
                            });
                            if (rowData.length > 0) {
                                rows.push(rowData);
                            }
                        });
                        
                        result.tables.push({
                            index: idx,
                            headers: headers,
                            rows: rows
                        });
                    });
                    
                    // Get all divs that might contain data
                    document.querySelectorAll('[data-testid], [role="grid"], .stDataFrame').forEach((el, idx) => {
                        result.elements.push({
                            index: idx,
                            tag: el.tagName,
                            className: el.className,
                            dataTestId: el.getAttribute('data-testid'),
                            innerText: el.innerText.substring(0, 500)
                        });
                    });
                    
                    return result;
                }
            """)
            
            await page.screenshot(path="04_final_extraction.png")
            
            print(f"\n✅ Извлечено:")
            print(f"  - Таблиц: {len(data['tables'])}")
            print(f"  - Других элементов: {len(data['elements'])}")
            
            return data
            
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            await page.screenshot(path="error.png")
            raise
        finally:
            print("\n⏳ Браузер останется открытым еще 30 секунд для проверки...")
            await asyncio.sleep(30)
            await browser.close()


def main():
    print("\n" + "=" * 60)
    print("🌊 HashDive Insiders Scraper")
    print("=" * 60)
    print("\nЭтот скрипт парсит данные с https://hashdive.com/Insiders")
    print("Вам нужно будет войти через Google OAuth вручную")
    print("\nБраузер откроется и будет ждать вашего логина")
    print("=" * 60)
    
    data = asyncio.run(scrape_hashdive())
    
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
                print(f"   Строк: {len(table['rows'])}")
                
                if table['headers']:
                    print(f"   Заголовки: {', '.join(table['headers'][:5])}")
                
                if table['rows']:
                    print(f"   Первая строка: {table['rows'][0][0]['text'] if table['rows'][0] else 'N/A'}")
        else:
            print("\n⚠️  Таблицы не найдены")
            print("\nТекст на странице (первые 500 символов):")
            print(data['text'][:500])
        
        print("\n" + "=" * 60)
        print(f"\n💡 Откройте {filename} чтобы посмотреть все данные")
    else:
        print("\n❌ Не удалось получить данные")
        print("Проверьте скриншоты в текущей директории")


if __name__ == "__main__":
    main()

