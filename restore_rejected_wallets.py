#!/usr/bin/env python3
"""
Восстановить валидные кошельки, которые были ошибочно помечены как rejected_inactive
из-за last_trade_at = NULL

ИСПРАВЛЕНИЕ ПРОБЛЕМЫ database is locked:
- Используется одно соединение для всех операций (не создаются новые через db.upsert_wallet/get_wallet)
- Увеличен busy_timeout до 30000 мс
- Добавлен retry-механизм для обработки временных блокировок
- Операции батчатся (commit каждые 20 кошельков)
- Прямые SQL-запросы вместо методов db для избежания множественных соединений
"""

import os
import sys
import sqlite3
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import PolymarketDB
from wallet_analyzer import MIN_TRADES, WIN_RATE_THRESHOLD

load_dotenv()

def restore_rejected_wallets():
    """Восстановить валидные кошельки из rejected_inactive"""
    db = PolymarketDB()
    db_path = db.db_path
    
    print("=" * 80)
    print("Восстановление валидных кошельков из rejected_inactive")
    print("=" * 80)
    print(f"База данных: {os.path.abspath(db_path)}")
    print(f"Критерии: trades >= {MIN_TRADES}, win_rate >= {WIN_RATE_THRESHOLD:.0%}")
    print()
    
    # Использовать одно соединение для всех операций
    # Увеличиваем timeout и busy_timeout для работы с возможными блокировками
    try:
        # Сначала попробуем сделать checkpoint для закрытия WAL-файла
        print("🔍 Проверка и подготовка базы данных...")
        try:
            checkpoint_conn = sqlite3.connect(db_path, timeout=10.0)
            checkpoint_conn.execute("PRAGMA journal_mode=WAL")
            checkpoint_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            checkpoint_conn.close()
            time.sleep(0.5)  # Небольшая пауза после checkpoint
            print("✅ WAL checkpoint выполнен")
        except Exception as e:
            print(f"⚠️  Checkpoint не удался (возможно, не критично): {e}")
        
        # Проверяем доступность базы
        test_conn = sqlite3.connect(db_path, timeout=10.0)
        test_conn.execute("PRAGMA journal_mode=WAL")
        test_conn.execute("PRAGMA busy_timeout=10000")
        test_cursor = test_conn.cursor()
        test_cursor.execute("SELECT COUNT(*) FROM wallets")
        test_count = test_cursor.fetchone()[0]
        test_conn.close()
        print(f"✅ База доступна. Текущее количество кошельков: {test_count}")
        print()
        
        # Открываем основное соединение
        print("🔒 Открытие соединения...")
        conn = sqlite3.connect(
            db_path,
            timeout=60.0,  # Увеличенный timeout для ожидания разблокировки
            check_same_thread=False
        )
        
        # Настройки для работы с WAL и блокировками
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=60000")  # Ждать до 60 секунд при блокировке
        conn.execute("PRAGMA synchronous=NORMAL")
        
        cursor = conn.cursor()
        
        # Найти кошельки с rejected_inactive, но валидные по критериям
        print("🔍 Поиск валидных кошельков для восстановления...")
        cursor.execute("""
            SELECT address, traded_total, win_rate, realized_pnl_total, 
                   daily_trading_frequency, last_trade_at, source
            FROM wallet_analysis_cache
            WHERE analysis_result = 'rejected_inactive'
            AND last_trade_at IS NULL
            AND traded_total >= ?
            AND win_rate >= ?
            ORDER BY win_rate DESC, traded_total DESC
        """, (MIN_TRADES, WIN_RATE_THRESHOLD))
        
        wallets_to_restore = cursor.fetchall()
        
        print(f"✅ Найдено валидных кошельков для восстановления: {len(wallets_to_restore)}")
        
        if not wallets_to_restore:
            print("ℹ️  Нет кошельков для восстановления")
            conn.close()
            return
        
        print(f"📝 Параметры подключения:")
        print(f"   - timeout: 30.0 секунд")
        print(f"   - busy_timeout: 30000 мс (30 секунд)")
        print(f"   - journal_mode: WAL")
        print()
        
        restored_count = 0
        skipped_count = 0
        error_count = 0
        batch_size = 20  # Commit каждые 20 кошельков
        now_iso = datetime.now(timezone.utc).isoformat()
        
        print("🔄 Начинаю восстановление...")
        print()
        
        for idx, (address, traded, win_rate, pnl, daily_freq, last_trade_at, source) in enumerate(wallets_to_restore, 1):
            max_retries = 3
            retry_delay = 0.5
            
            for retry in range(max_retries):
                try:
                    # Проверить, не существует ли уже в wallets (прямой SQL, без нового соединения)
                    cursor.execute("SELECT COUNT(*) FROM wallets WHERE address = ?", (address.lower(),))
                    exists = cursor.fetchone()[0] > 0
                    
                    if exists:
                        if idx == 1 or idx % 50 == 0:  # Логируем только периодически
                            print(f"⏭️  [{idx}/{len(wallets_to_restore)}] Пропущен {address[:20]}... (уже в базе)")
                        skipped_count += 1
                        break  # Выходим из retry-цикла
                    
                    # Восстановить кошелек (прямой SQL, без нового соединения)
                    cursor.execute("""
                        INSERT OR REPLACE INTO wallets(
                            address, display, traded_total, win_rate, 
                            realized_pnl_total, daily_trading_frequency, 
                            source, added_at, updated_at, last_trade_at
                        )
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        address.lower(),
                        address,
                        traded,
                        win_rate,
                        pnl or 0.0,
                        daily_freq,
                        source or "restored",
                        now_iso,
                        now_iso,
                        last_trade_at  # NULL - это нормально
                    ))
                    
                    # Обновить analysis_result в cache
                    cursor.execute("""
                        UPDATE wallet_analysis_cache
                        SET analysis_result = 'accepted'
                        WHERE address = ?
                    """, (address,))
                    
                    restored_count += 1
                    
                    # Логируем прогресс
                    if restored_count % 10 == 0 or idx == len(wallets_to_restore):
                        print(f"✅ [{idx}/{len(wallets_to_restore)}] Восстановлено {restored_count} кошельков...")
                    
                    # Commit батчами для производительности
                    if restored_count % batch_size == 0:
                        conn.commit()
                        time.sleep(0.1)  # Небольшая пауза после commit
                    
                    break  # Успешно, выходим из retry-цикла
                    
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower() and retry < max_retries - 1:
                        # Временная блокировка - повторяем попытку
                        wait_time = retry_delay * (retry + 1)
                        if idx <= 5:  # Логируем только для первых ошибок
                            print(f"⏳ [{idx}] Временная блокировка, повтор через {wait_time:.1f}с... (попытка {retry+1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        # Критическая ошибка или закончились попытки
                        error_count += 1
                        if error_count <= 5:  # Логируем только первые 5 ошибок
                            print(f"❌ [{idx}] Ошибка при обработке {address[:20]}...: {e}")
                        break
                except Exception as e:
                    error_count += 1
                    if error_count <= 5:
                        print(f"❌ [{idx}] Неожиданная ошибка {address[:20]}...: {e}")
                    break
        
        # Финальный commit для оставшихся изменений
        conn.commit()
        conn.close()
        print("✅ Транзакция завершена, соединение закрыто")
        
        print()
        print("=" * 80)
        print("📊 РЕЗУЛЬТАТЫ ВОССТАНОВЛЕНИЯ:")
        print("=" * 80)
        print(f"✅ Восстановлено: {restored_count}")
        print(f"⏭️  Пропущено (уже в базе): {skipped_count}")
        print(f"❌ Ошибок: {error_count}")
        print("=" * 80)
        
        # Показать итоговую статистику
        print()
        print("📊 Итоговая статистика базы данных:")
        db_final = PolymarketDB()
        stats = db_final.get_wallet_stats()
        print(f"   Всего кошельков в базе: {stats.get('total_wallets', 0)}")
        print(f"   Отслеживаемых: {stats.get('tracked_wallets', 0)}")
        
        # Показать статистику по analysis_result
        with db_final.get_connection() as conn_stat:
            cursor_stat = conn_stat.cursor()
            cursor_stat.execute("""
                SELECT analysis_result, COUNT(*) as count
                FROM wallet_analysis_cache
                WHERE analysis_result IN ('accepted', 'rejected_inactive')
                GROUP BY analysis_result
            """)
            results = cursor_stat.fetchall()
            if results:
                print()
                print("📈 Статистика по analysis_result:")
                for result, count in results:
                    print(f"   {result}: {count}")
        
    except Exception as e:
        print(f"❌ Критическая ошибка при работе с базой данных: {e}")
        import traceback
        traceback.print_exc()
        return

if __name__ == "__main__":
    restore_rejected_wallets()

