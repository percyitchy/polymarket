#!/usr/bin/env python3
"""
Тестовый скрипт для проверки интеграции новостной корреляции
"""
import sys
import os
import time
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from polymarket_notifier import PolymarketNotifier
from notify import TelegramNotifier

def test_adj_news_client():
    """Тест 1: Проверка инициализации AdjNewsClient"""
    print("="*70)
    print("ТЕСТ 1: Инициализация AdjNewsClient")
    print("="*70)
    
    try:
        from adj_news_client import AdjNewsClient
        
        api_key = os.getenv("ADJ_NEWS_API_KEY", "").strip()
        if api_key:
            client = AdjNewsClient(api_key=api_key)
            print("✅ AdjNewsClient инициализирован с API ключом")
        else:
            client = AdjNewsClient()
            print("⚠️  AdjNewsClient инициализирован без API ключа (низкие лимиты)")
        
        # Проверка rate limit статуса
        status = client.get_rate_limit_status()
        print(f"\n📊 Статус rate limit:")
        print(f"   - Daily: {status['daily_queries_used']}/{status['daily_queries_limit']}")
        print(f"   - Per-minute: {status['minute_queries_used']}/{status['minute_queries_limit']}")
        print(f"   - Authenticated: {status['authenticated']}")
        
        # Тест подключения
        if client.test_connection():
            print("\n✅ Подключение к API успешно")
        else:
            print("\n❌ Ошибка подключения к API")
            return False
        
        return True
    except Exception as e:
        print(f"\n❌ Ошибка при инициализации AdjNewsClient: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_news_correlation_method():
    """Тест 2: Проверка метода check_news_correlation"""
    print("\n" + "="*70)
    print("ТЕСТ 2: Метод check_news_correlation")
    print("="*70)
    
    try:
        notifier = PolymarketNotifier()
        
        if not notifier.adj_news_client:
            print("⚠️  AdjNewsClient не инициализирован, пропускаем тест")
            return False
        
        print(f"✅ PolymarketNotifier инициализирован")
        print(f"   - News correlation enabled: {notifier.news_correlation_enabled}")
        print(f"   - Min wallets for check: {notifier.news_min_wallets_for_check}")
        print(f"   - Min A-list for check: {notifier.news_min_a_list_for_check}")
        print(f"   - Time window: {notifier.news_time_window_hours}h")
        
        # Тест с реальным рынком (например, "trump")
        test_market = "trump"
        test_condition_id = "0xTEST1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        test_timestamp = time.time()
        
        print(f"\n🔍 Проверка новостей для рынка: '{test_market}'")
        print(f"   - Condition ID: {test_condition_id[:30]}...")
        print(f"   - Timestamp: {datetime.fromtimestamp(test_timestamp, tz=timezone.utc).isoformat()}")
        
        news_context = notifier.check_news_correlation(
            market_title=test_market,
            condition_id=test_condition_id,
            consensus_timestamp=test_timestamp
        )
        
        if news_context:
            print(f"\n✅ Новостная корреляция найдена:")
            print(f"   - Headline: {news_context.get('headline', 'N/A')[:80]}...")
            print(f"   - Source: {news_context.get('source', 'N/A')}")
            print(f"   - Published at: {news_context.get('published_at', 'N/A')}")
            print(f"   - URL: {news_context.get('url', 'N/A')[:60]}...")
        else:
            print(f"\n⚠️  Новостная корреляция не найдена (это нормально, если нет новостей в окне времени)")
        
        # Проверка статистики
        stats = notifier.news_correlation_stats
        print(f"\n📊 Статистика проверок:")
        print(f"   - Total checks: {stats['total_checks']}")
        print(f"   - News found: {stats['news_found']}")
        print(f"   - Rate limited: {stats['rate_limited']}")
        print(f"   - Errors: {stats['errors']}")
        
        return True
    except Exception as e:
        print(f"\n❌ Ошибка при тестировании метода: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_alert_with_news():
    """Тест 3: Отправка тестового алерта с новостным контекстом"""
    print("\n" + "="*70)
    print("ТЕСТ 3: Отправка алерта с новостным контекстом")
    print("="*70)
    
    try:
        notifier = TelegramNotifier()
        
        # Создаем тестовый новостной контекст
        test_news_context = {
            'headline': 'Breaking: Test News Article for Polymarket Integration Testing',
            'source': 'Test News Source',
            'published_at': str(time.time()),
            'url': 'https://example.com/test-news-article'
        }
        
        test_wallets = [
            "0x1234567890abcdef1234567890abcdef12345678",
            "0xabcdef1234567890abcdef1234567890abcdef12",
            "0x9876543210fedcba9876543210fedcba98765432",
            "0x1111111111111111111111111111111111111111"  # 4 кошелька для high-confidence
        ]
        
        test_wallet_prices = {
            "0x1234567890abcdef1234567890abcdef12345678": 0.65,
            "0xabcdef1234567890abcdef1234567890abcdef12": 0.67,
            "0x9876543210fedcba9876543210fedcba98765432": 0.66,
            "0x1111111111111111111111111111111111111111": 0.68
        }
        
        test_condition_id = "0xTEST1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        
        print(f"\n📤 Отправка тестового алерта с новостным контекстом...")
        print(f"   - Кошельков: {len(test_wallets)}")
        print(f"   - News headline: {test_news_context['headline'][:50]}...")
        
        success = notifier.send_consensus_alert(
            condition_id=test_condition_id,
            outcome_index=0,
            wallets=test_wallets,
            wallet_prices=test_wallet_prices,
            window_minutes=15.0,
            min_consensus=3,
            alert_id=f"TEST_NEWS_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            market_title="🧪 ТЕСТ С НОВОСТЯМИ - Проверка новостной корреляции",
            market_slug="test-news-signal",
            side="BUY",
            consensus_events=4,
            total_usd=5000.0,
            end_date=datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1),  # Будущая дата для теста
            current_price=0.66,
            category="test",
            a_list_wallets=None,
            oi_confirmed=False,
            order_flow_confirmed=False,
            news_context=test_news_context
        )
        
        if success:
            print("\n✅ Тестовый алерт с новостями отправлен успешно!")
            print("   Проверьте Telegram канал - должна быть секция с новостями")
        else:
            print("\n❌ Ошибка при отправке тестового алерта")
            print("   Проверьте логи")
        
        return success
    except Exception as e:
        print(f"\n❌ Ошибка при отправке алерта: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_configuration():
    """Тест 4: Проверка конфигурации"""
    print("\n" + "="*70)
    print("ТЕСТ 4: Проверка конфигурации")
    print("="*70)
    
    try:
        # Проверка env переменных
        print("\n📋 Проверка переменных окружения:")
        
        env_vars = {
            'ADJ_NEWS_API_KEY': os.getenv("ADJ_NEWS_API_KEY", ""),
            'NEWS_CORRELATION_ENABLED': os.getenv("NEWS_CORRELATION_ENABLED", "true"),
            'NEWS_MIN_WALLETS_FOR_CHECK': os.getenv("NEWS_MIN_WALLETS_FOR_CHECK", "4"),
            'NEWS_MIN_A_LIST_FOR_CHECK': os.getenv("NEWS_MIN_A_LIST_FOR_CHECK", "2"),
            'NEWS_TIME_WINDOW_HOURS': os.getenv("NEWS_TIME_WINDOW_HOURS", "1.0"),
        }
        
        for key, value in env_vars.items():
            if key == 'ADJ_NEWS_API_KEY':
                display_value = value[:20] + "..." if value and len(value) > 20 else (value if value else "не установлен")
            else:
                display_value = value
            print(f"   - {key}: {display_value}")
        
        # Проверка инициализации PolymarketNotifier
        notifier = PolymarketNotifier()
        
        print(f"\n✅ Конфигурация PolymarketNotifier:")
        print(f"   - adj_news_client available: {notifier.adj_news_client is not None}")
        print(f"   - news_correlation_enabled: {notifier.news_correlation_enabled}")
        print(f"   - news_min_wallets_for_check: {notifier.news_min_wallets_for_check}")
        print(f"   - news_min_a_list_for_check: {notifier.news_min_a_list_for_check}")
        print(f"   - news_time_window_hours: {notifier.news_time_window_hours}")
        print(f"   - news_correlation_stats: {notifier.news_correlation_stats}")
        
        return True
    except Exception as e:
        print(f"\n❌ Ошибка при проверке конфигурации: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Запуск всех тестов"""
    print("\n" + "="*70)
    print("ТЕСТИРОВАНИЕ ИНТЕГРАЦИИ НОВОСТНОЙ КОРРЕЛЯЦИИ")
    print("="*70)
    
    results = {}
    
    # Тест 1: Инициализация клиента
    results['client_init'] = test_adj_news_client()
    
    # Тест 2: Метод проверки новостей
    results['news_method'] = test_news_correlation_method()
    
    # Тест 3: Отправка алерта с новостями
    results['alert_with_news'] = test_alert_with_news()
    
    # Тест 4: Конфигурация
    results['configuration'] = test_configuration()
    
    # Итоги
    print("\n" + "="*70)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*70)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    total = len(results)
    passed = sum(1 for r in results.values() if r)
    
    print(f"\nВсего тестов: {total}")
    print(f"Пройдено: {passed}")
    print(f"Провалено: {total - passed}")
    
    if passed == total:
        print("\n🎉 Все тесты пройдены успешно!")
    else:
        print("\n⚠️  Некоторые тесты провалены. Проверьте логи выше.")

if __name__ == "__main__":
    main()

