#!/usr/bin/env python3
"""
Monitor recomputation progress for Phase 3 improvements
Shows real-time progress, category statistics, and improvements
"""

import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from db import PolymarketDB

load_dotenv()

def get_stats():
    """Get current statistics from database"""
    db_path = os.getenv('DB_PATH', 'polymarket_notifier.db')
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)
    
    db = PolymarketDB(db_path)
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Queue status
        cursor.execute('SELECT COUNT(*) FROM wallet_analysis_jobs WHERE status = "pending"')
        pending = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM wallet_analysis_jobs WHERE status = "processing"')
        processing = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM wallet_analysis_jobs WHERE status = "completed"')
        completed = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM wallet_analysis_jobs WHERE status = "failed"')
        failed = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM wallet_analysis_jobs')
        total = cursor.fetchone()[0]
        
        # Category statistics
        cursor.execute('SELECT SUM(markets) FROM wallet_category_stats')
        total_markets = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT SUM(markets) FROM wallet_category_stats WHERE category != "other/Unknown"')
        classified = cursor.fetchone()[0] or 0
        
        # New categories (Phase 2 & 3)
        cursor.execute('SELECT SUM(markets) FROM wallet_category_stats WHERE category LIKE "entertainment/%"')
        entertainment_markets = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT SUM(markets) FROM wallet_category_stats WHERE category = "tech/Releases"')
        tech_markets = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT SUM(markets) FROM wallet_category_stats WHERE category = "stocks/Companies"')
        stocks_markets = cursor.fetchone()[0] or 0
        
        # Top categories
        cursor.execute('''
            SELECT category, SUM(markets) as markets
            FROM wallet_category_stats
            WHERE category != "other/Unknown"
            GROUP BY category
            ORDER BY markets DESC
            LIMIT 10
        ''')
        top_categories = cursor.fetchall()
        
        # New categories detail
        cursor.execute('''
            SELECT category, SUM(markets) as markets
            FROM wallet_category_stats
            WHERE category LIKE "entertainment/%" OR category = "tech/Releases" OR category = "stocks/Companies"
            GROUP BY category
            ORDER BY markets DESC
        ''')
        new_categories = cursor.fetchall()
        
        return {
            'queue': {
                'total': total,
                'completed': completed,
                'processing': processing,
                'pending': pending,
                'failed': failed
            },
            'categories': {
                'total_markets': total_markets,
                'classified': classified,
                'unknown': total_markets - classified,
                'entertainment': entertainment_markets,
                'tech': tech_markets,
                'stocks': stocks_markets,
                'top_categories': top_categories,
                'new_categories': new_categories
            }
        }

def format_number(num):
    """Format number with commas"""
    return f"{num:,}"

def main():
    print("=" * 100)
    print("📊 МОНИТОРИНГ ПЕРЕСЧЁТА (ФАЗА 3)")
    print("=" * 100)
    print()
    
    # Baseline (before recomputation)
    baseline_unknown_pct = 66.01
    
    iteration = 0
    last_completed = 0
    start_time = time.time()
    
    try:
        while True:
            iteration += 1
            stats = get_stats()
            
            queue = stats['queue']
            cats = stats['categories']
            
            # Clear screen (optional, comment out if you want to see history)
            # os.system('clear' if os.name != 'nt' else 'cls')
            
            print("=" * 100)
            print(f"📊 ПРОГРЕСС ПЕРЕСЧЁТА (ФАЗА 3) - Итерация #{iteration}")
            print("=" * 100)
            print()
            print(f"⏱️  Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            
            # Queue status
            print(f"📋 Очередь анализа:")
            print(f"   • Всего задач: {format_number(queue['total'])}")
            print(f"   • ✅ Завершено: {format_number(queue['completed'])}")
            print(f"   • 🔄 Обрабатывается: {queue['processing']}")
            print(f"   • ⏳ Ожидает: {format_number(queue['pending'])}")
            if queue['failed'] > 0:
                print(f"   • ❌ Ошибок: {queue['failed']}")
            print()
            
            # Progress
            if queue['total'] > 0:
                progress = (queue['completed'] / queue['total'] * 100) if queue['total'] > 0 else 0
                remaining = queue['total'] - queue['completed']
                print(f"📈 Прогресс: {progress:.1f}% ({format_number(queue['completed'])} / {format_number(queue['total'])})")
                print(f"   Осталось: {format_number(remaining)} кошельков")
                
                # Rate calculation
                if iteration > 1 and queue['completed'] > last_completed:
                    completed_since_last = queue['completed'] - last_completed
                    elapsed = time.time() - start_time
                    if elapsed > 0:
                        rate_per_second = queue['completed'] / elapsed
                        if rate_per_second > 0:
                            eta_seconds = remaining / rate_per_second
                            eta_minutes = eta_seconds / 60
                            eta_hours = eta_minutes / 60
                            if eta_hours < 1:
                                print(f"   ⏱️  Примерное время до завершения: ~{eta_minutes:.0f} минут")
                            else:
                                print(f"   ⏱️  Примерное время до завершения: ~{eta_hours:.1f} часов")
                            print(f"   📊 Скорость: ~{rate_per_second:.1f} кошельков/сек")
                print()
            
            # Category statistics
            print(f"📊 Статистика категорий:")
            print(f"   • Всего рынков: {format_number(cats['total_markets'])}")
            if cats['total_markets'] > 0:
                classified_pct = cats['classified'] / cats['total_markets'] * 100
                unknown_pct = cats['unknown'] / cats['total_markets'] * 100
                print(f"   • ✅ Классифицировано: {format_number(cats['classified'])} ({classified_pct:.2f}%)")
                print(f"   • ❓ Unknown: {format_number(cats['unknown'])} ({unknown_pct:.2f}%)")
                
                # Improvement tracking
                improvement = baseline_unknown_pct - unknown_pct
                if improvement != 0:
                    print(f"   • 📉 Улучшение: Unknown изменился на {improvement:+.2f} п.п. (с {baseline_unknown_pct:.2f}% до {unknown_pct:.2f}%)")
                
                # New categories
                if cats['entertainment'] > 0:
                    print(f"   • 🎬 Entertainment: {format_number(cats['entertainment'])} рынков ({cats['entertainment']/cats['total_markets']*100:.2f}%)")
                if cats['tech'] > 0:
                    print(f"   • 💻 Tech/Releases: {format_number(cats['tech'])} рынков ({cats['tech']/cats['total_markets']*100:.2f}%)")
                if cats['stocks'] > 0:
                    print(f"   • 📈 Stocks/Companies: {format_number(cats['stocks'])} рынков ({cats['stocks']/cats['total_markets']*100:.2f}%)")
            print()
            
            # New categories detail
            if cats['new_categories']:
                print(f"🆕 Новые категории (Фаза 2 & 3):")
                for cat, markets in cats['new_categories']:
                    pct = (markets / cats['total_markets'] * 100) if cats['total_markets'] > 0 else 0
                    print(f"   • {cat:<30} {format_number(markets):>6} рынков ({pct:.2f}%)")
                print()
            
            # Top categories
            if cats['top_categories']:
                print(f"🏆 Топ-10 категорий:")
                for cat, markets in cats['top_categories']:
                    pct = (markets / cats['total_markets'] * 100) if cats['total_markets'] > 0 else 0
                    print(f"   • {cat:<30} {format_number(markets):>6} рынков ({pct:.2f}%)")
                print()
            
            # Status
            if queue['processing'] > 0 or queue['pending'] > 0:
                print('✅ Процесс активно работает!')
            elif queue['completed'] > 0 and queue['pending'] == 0 and queue['processing'] == 0:
                print('✅ Пересчёт завершён!')
                break
            else:
                print('⚠️  Процесс ещё не начался')
            
            print("=" * 100)
            print()
            print("Нажмите Ctrl+C для выхода")
            print()
            
            last_completed = queue['completed']
            
            # Wait before next update
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n\n👋 Мониторинг остановлен пользователем")
        print("=" * 100)

if __name__ == "__main__":
    main()

