#!/usr/bin/env python3
"""
Диагностика причин отсутствия сигналов
"""

import sys
import logging
from db import PolymarketDB
from datetime import datetime, timezone, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print("=" * 70)
    print("🔍 ДИАГНОСТИКА ПРИЧИН ОТСУТСТВИЯ СИГНАЛОВ")
    print("=" * 70)
    
    db = PolymarketDB()
    
    # 1. Проверка отслеживаемых кошельков
    print("\n1️⃣ ОТСЛЕЖИВАЕМЫЕ КОШЕЛЬКИ:")
    stats = db.get_wallet_stats()
    tracked = stats.get('tracked_wallets', 0)
    total = stats.get('total_wallets', 0)
    print(f"   Отслеживаемых кошельков: {tracked}")
    print(f"   Всего в базе: {total}")
    
    if tracked < 3:
        print(f"   ⚠️  ПРОБЛЕМА: Меньше 3 кошельков! Нужно минимум 3 для консенсуса")
    
    # 2. Проверка последних алертов
    print("\n2️⃣ ПОСЛЕДНИЕ АЛЕРТЫ:")
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sent_at, condition_id, outcome_index, wallet_count, side
            FROM alerts_sent
            ORDER BY sent_at DESC
            LIMIT 5
        """)
        alerts = cursor.fetchall()
        if alerts:
            print(f"   Найдено {len(alerts)} последних алертов:")
            for alert in alerts:
                print(f"     {alert[0]}: {alert[1][:20]}..., outcome={alert[2]}, wallets={alert[3]}, side={alert[4]}")
        else:
            print("   ⚠️  ПРОБЛЕМА: Нет отправленных алертов в базе!")
    
    # 3. Проверка последних сделок
    print("\n3️⃣ ПОСЛЕДНИЕ СДЕЛКИ:")
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM last_trades
            WHERE timestamp > datetime('now', '-3 days')
        """)
        recent_trades = cursor.fetchone()[0]
        print(f"   Сделок за последние 3 дня: {recent_trades}")
        
        if recent_trades == 0:
            print("   ⚠️  ПРОБЛЕМА: Нет сделок за последние 3 дня!")
        
        # Check rolling buys
        cursor.execute("""
            SELECT COUNT(*) FROM rolling_buys
            WHERE timestamp > datetime('now', '-1 day')
        """)
        recent_rolling = cursor.fetchone()[0]
        print(f"   Событий в rolling_buys за последние 24 часа: {recent_rolling}")
    
    # 4. Проверка настроек
    print("\n4️⃣ НАСТРОЙКИ:")
    import os
    from dotenv import load_dotenv
    load_dotenv()
    min_consensus = int(os.getenv("MIN_CONSENSUS", "3"))
    alert_window = int(os.getenv("ALERT_WINDOW_MIN", "15"))
    print(f"   MIN_CONSENSUS: {min_consensus}")
    print(f"   ALERT_WINDOW_MIN: {alert_window}")
    
    # 5. Проверка проблем с API
    print("\n5️⃣ ПРОБЛЕМЫ С API:")
    print("   Проверьте логи на наличие:")
    print("   - Rate Limit ошибок (429)")
    print("   - RetryError")
    print("   - [SUPPRESS] блокировок")
    
    # 6. Проверка фильтров
    print("\n6️⃣ ВОЗМОЖНЫЕ БЛОКИРОВКИ:")
    print("   Проверьте логи на наличие:")
    print("   - [SUPPRESS] market_closed - рынок закрыт")
    print("   - [SUPPRESS] resolved - рынок разрешен")
    print("   - [SUPPRESS] price_high/low - цена слишком высокая/низкая")
    print("   - [SUPPRESS] ignore_30m_same_outcome - повторный алерт за 30 мин")
    print("   - [SUPPRESS] opposite_recent - противоположная сторона недавно")
    print("   - 🚫 Skipping trade - сделка пропущена (цена <=0.02 или >=0.98)")
    
    print("\n" + "=" * 70)
    print("✅ Диагностика завершена")
    print("=" * 70)
    
    print("\n💡 РЕКОМЕНДАЦИИ:")
    if tracked < 50:
        print("   - Увеличьте количество отслеживаемых кошельков")
    if recent_trades == 0:
        print("   - Проверьте, что кошельки делают сделки")
        print("   - Проверьте логи на ошибки API (429, RetryError)")
    print("   - Проверьте логи на [SUPPRESS] блокировки")
    print("   - Убедитесь, что рынки активны (не закрыты/разрешены)")

if __name__ == "__main__":
    main()

