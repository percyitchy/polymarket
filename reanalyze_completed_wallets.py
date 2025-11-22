#!/usr/bin/env python3
"""
Скрипт для переанализа кошельков со статусом 'completed'
для получения новых качественных метрик (total_volume, roi, avg_pnl_per_market, avg_stake)
"""

import sys
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import PolymarketDB

load_dotenv()

def reanalyze_completed_wallets():
    """Переанализировать кошельки со статусом 'completed'"""
    db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
    db = PolymarketDB(db_path)
    
    print("=" * 70)
    print("🔄 ПЕРЕАНАЛИЗ ЗАВЕРШЕННЫХ КОШЕЛЬКОВ")
    print("=" * 70)
    print()
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Находим все кошельки со статусом 'completed'
        cursor.execute("""
            SELECT address FROM wallet_analysis_jobs
            WHERE status = 'completed'
        """)
        
        completed_addresses = [row[0] for row in cursor.fetchall()]
        total_count = len(completed_addresses)
        
        print(f"📋 Найдено завершенных заданий: {total_count:,}")
        print()
        
        if total_count == 0:
            print("✅ Нет завершенных заданий для переанализа")
            return
        
        # Изменяем статус на 'pending' для переанализа
        now = datetime.now(timezone.utc).isoformat()
        
        updated_count = 0
        skipped_count = 0
        
        print("🔄 Изменяю статус на 'pending'...")
        print()
        
        for address in completed_addresses:
            try:
                # Проверяем, нет ли уже задания в статусе pending или processing
                cursor.execute("""
                    SELECT COUNT(*) FROM wallet_analysis_jobs
                    WHERE address = ? AND status IN ('pending', 'processing')
                """, (address,))
                
                if cursor.fetchone()[0] > 0:
                    skipped_count += 1
                    continue
                
                # Обновляем статус completed на pending
                cursor.execute("""
                    UPDATE wallet_analysis_jobs
                    SET status = 'pending',
                        created_at = ?,
                        updated_at = ?
                    WHERE address = ? AND status = 'completed'
                """, (now, now, address))
                
                if cursor.rowcount > 0:
                    updated_count += 1
                
                # Прогресс каждые 1000 кошельков
                if (updated_count + skipped_count) % 1000 == 0:
                    print(f"   Обработано: {updated_count + skipped_count:,}/{total_count:,}")
                    
            except Exception as e:
                print(f"⚠️  Ошибка при обновлении {address[:20]}...: {e}")
                skipped_count += 1
        
        conn.commit()
        
        print()
        print("=" * 70)
        print("✅ ПЕРЕАНАЛИЗ ЗАПУЩЕН")
        print("=" * 70)
        print(f"   Обновлено заданий: {updated_count:,}")
        print(f"   Пропущено (уже в очереди): {skipped_count:,}")
        print()
        print("💡 Workers начнут переанализировать эти кошельки")
        print("   и добавят новые качественные метрики:")
        print("   • total_volume")
        print("   • roi")
        print("   • avg_pnl_per_market")
        print("   • avg_stake")
        print("=" * 70)

if __name__ == "__main__":
    reanalyze_completed_wallets()

