#!/usr/bin/env python3
"""
Скрипт для проверки работы прокси после добавления IP в whitelist
"""

import requests
import urllib3
import sys
from proxy_manager import ProxyManager

# Отключаем предупреждения SSL для прокси
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_proxy_connection():
    """Тестирует подключение через прокси"""
    print("=" * 80)
    print("🧪 ТЕСТ ПОДКЛЮЧЕНИЯ ЧЕРЕЗ ПРОКСИ")
    print("=" * 80)
    print()
    
    pm = ProxyManager()
    
    if not pm.proxy_enabled or not pm.proxies:
        print("❌ Прокси не настроены или не загружены")
        print("   Проверьте переменную POLYMARKET_PROXIES в .env файле")
        return False
    
    print(f"✅ Загружено прокси: {len(pm.proxies)}")
    print()
    
    # Тестируем первые 3 прокси
    test_url = "https://clob.polymarket.com/markets"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Connection": "close",
        "Proxy-Connection": "close"
    }
    
    success_count = 0
    fail_count = 0
    
    print("🔄 Тестирую подключение к Polymarket API...")
    print()
    
    for i in range(min(3, len(pm.proxies))):
        proxy = pm.get_proxy(rotate=True)
        proxy_str = proxy["http"][:60] if proxy else "None"
        print(f"📡 Тест {i+1}/3: {proxy_str}...")
        
        try:
            response = requests.get(
                test_url,
                proxies=proxy,
                headers=headers,
                timeout=15,
                verify=False
            )
            if response.status_code == 200:
                print(f"   ✅ УСПЕХ! Статус: {response.status_code}")
                data = response.json()
                count = len(data) if isinstance(data, list) else "N/A"
                print(f"   ✅ Получено маркетов: {count}")
                success_count += 1
            else:
                print(f"   ⚠️ Статус: {response.status_code}")
                fail_count += 1
        except requests.exceptions.ProxyError as e:
            error_msg = str(e)
            if "Connection not allowed by ruleset" in error_msg:
                print(f"   ❌ ОШИБКА: IP не в whitelist")
                print(f"   💡 Добавьте IP YOUR_SERVER_IP в whitelist ProxyWing")
            else:
                print(f"   ❌ ProxyError: {error_msg[:80]}")
            fail_count += 1
        except requests.exceptions.Timeout as e:
            print(f"   ❌ Timeout: {e}")
            fail_count += 1
        except requests.exceptions.ConnectionError as e:
            error_msg = str(e)
            if "Connection not allowed" in error_msg:
                print(f"   ❌ ОШИБКА: IP не в whitelist")
                print(f"   💡 Добавьте IP YOUR_SERVER_IP в whitelist ProxyWing")
            else:
                print(f"   ❌ ConnectionError: {error_msg[:80]}")
            fail_count += 1
        except Exception as e:
            print(f"   ❌ Ошибка: {type(e).__name__}: {str(e)[:80]}")
            fail_count += 1
        
        print()
    
    print("=" * 80)
    print(f"📊 РЕЗУЛЬТАТЫ: ✅ {success_count} успешных, ❌ {fail_count} неудачных")
    print("=" * 80)
    print()
    
    if success_count > 0:
        print("🎉 ПРОКСИ РАБОТАЮТ!")
        print("   Бот будет использовать прокси для запросов к API")
        return True
    else:
        print("⚠️ ПРОКСИ НЕ РАБОТАЮТ")
        print("   Бот автоматически переключится на прямое подключение")
        print()
        print("💡 РЕКОМЕНДАЦИИ:")
        print("   1. Проверьте, добавлен ли IP YOUR_SERVER_IP в whitelist ProxyWing")
        print("   2. Подождите несколько минут после добавления IP (изменения могут")
        print("      вступить в силу не сразу)")
        print("   3. Обратитесь в поддержку ProxyWing, если проблема сохраняется")
        return False

if __name__ == "__main__":
    success = test_proxy_connection()
    sys.exit(0 if success else 1)

