#!/usr/bin/env python3
"""
Diagnostic script to check why wallet analyzer workers are not processing jobs
"""

import sys
import logging
from db import PolymarketDB
from wallet_analyzer import WalletAnalyzer, AnalysisConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    print("=" * 60)
    print("🔍 Диагностика работы воркеров анализа кошельков")
    print("=" * 60)
    
    db = PolymarketDB()
    
    # 1. Check queue status
    print("\n1️⃣ Проверка статуса очереди:")
    stats = db.get_queue_stats()
    print(f"   Всего задач: {stats.get('total_jobs', 0)}")
    print(f"   Ожидает обработки: {stats.get('pending_jobs', 0)}")
    print(f"   В обработке: {stats.get('processing_jobs', 0)}")
    print(f"   Готово к обработке: {stats.get('ready_jobs', 0)}")
    
    # 2. Check if get_pending_jobs works
    print("\n2️⃣ Проверка получения задач:")
    jobs = db.get_pending_jobs(limit=10)
    print(f"   get_pending_jobs(limit=10) вернул: {len(jobs)} задач")
    
    if jobs:
        job = jobs[0]
        print(f"   Первая задача: ID={job.get('id')}, Address={job.get('address')[:20]}..., Status={job.get('status')}")
        
        # 3. Test claim_job
        print("\n3️⃣ Проверка захвата задачи:")
        job_id = job.get('id')
        claimed = db.claim_job(job_id)
        print(f"   claim_job({job_id}) вернул: {claimed}")
        
        if claimed:
            # Check status after claim
            job_after = db.get_job_by_id(job_id)
            if job_after:
                print(f"   Статус после захвата: {job_after.get('status')}")
            
            # 4. Test analysis
            print("\n4️⃣ Проверка анализа кошелька:")
            config = AnalysisConfig(api_max_workers=1, api_timeout_sec=12)
            analyzer = WalletAnalyzer(db, config)
            
            try:
                result = analyzer._analyze_wallet(job)
                print(f"   Анализ завершен: {result}")
                
                if result:
                    db.complete_job(job_id)
                    print(f"   Задача {job_id} завершена и удалена из очереди")
                else:
                    print(f"   Задача {job_id} не прошла анализ (вернется в очередь)")
            except Exception as e:
                print(f"   ❌ Ошибка при анализе: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"   ❌ Не удалось захватить задачу {job_id}")
            # Reset to pending
            db.update_job_status(job_id, 'pending')
    else:
        print("   ❌ Нет доступных задач!")
        
        # Check why
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM wallet_analysis_jobs WHERE status = 'pending'")
            total_pending = cursor.fetchone()[0]
            print(f"   Но в БД есть {total_pending} задач в статусе 'pending'")
            
            # Check next_retry_at
            from datetime import datetime
            now = db.now_iso()
            cursor.execute("""
                SELECT COUNT(*) FROM wallet_analysis_jobs 
                WHERE status = 'pending' 
                AND (next_retry_at IS NULL OR next_retry_at <= ?)
            """, (now,))
            ready = cursor.fetchone()[0]
            print(f"   Из них готово к обработке: {ready}")
    
    # 5. Check for stuck processing jobs
    print("\n5️⃣ Проверка застрявших задач:")
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM wallet_analysis_jobs WHERE status = 'processing'")
        processing = cursor.fetchone()[0]
        print(f"   Задач в статусе 'processing': {processing}")
        
        if processing > 0:
            cursor.execute("""
                SELECT id, address, updated_at 
                FROM wallet_analysis_jobs 
                WHERE status = 'processing'
                ORDER BY updated_at ASC
                LIMIT 5
            """)
            stuck = cursor.fetchall()
            print(f"   Застрявшие задачи:")
            for row in stuck:
                print(f"     ID: {row[0]}, Address: {row[1][:20]}..., Updated: {row[2]}")
    
    # 6. Check cache
    print("\n6️⃣ Проверка кэша:")
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM wallet_analysis_cache")
        cached = cursor.fetchone()[0]
        print(f"   Кэшированных результатов: {cached}")
    
    print("\n" + "=" * 60)
    print("✅ Диагностика завершена")
    print("=" * 60)

if __name__ == "__main__":
    main()

