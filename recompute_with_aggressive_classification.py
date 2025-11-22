#!/usr/bin/env python3
"""
Пересчёт категорий с агрессивной классификацией для снижения Unknown до 20%
"""

import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Запустить пересчёт с агрессивной классификацией"""
    print("=" * 80)
    print("🔄 ПЕРЕСЧЁТ КАТЕГОРИЙ С АГРЕССИВНОЙ КЛАССИФИКАЦИЕЙ")
    print("=" * 80)
    print()
    print("📋 Улучшения:")
    print("   ✅ Кэширование web scraping (SQLite + in-memory)")
    print("   ✅ Агрессивная ML классификация (порог 0.05)")
    print("   ✅ Классификация по датам → macro/Events")
    print("   ✅ Классификация по ценам → macro/crypto")
    print("   ✅ Эвристики для минимальных данных")
    print("   ✅ Использование event.category из API")
    print()
    print("⚠️  Это займёт время (пересчёт всех кошельков)")
    print()
    
    confirm = input("Продолжить пересчёт? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Отменено.")
        return
    
    print("\n🚀 Запуск пересчёта...")
    print("   (Это может занять несколько часов)")
    print()
    
    # Запускаем пересчёт через daily_wallet_analysis.py
    import subprocess
    result = subprocess.run(
        ["python", "daily_wallet_analysis.py", "--recompute-all-categories"],
        capture_output=False
    )
    
    if result.returncode == 0:
        print("\n✅ Пересчёт завершён!")
        print("   Запустите check_classification_improvements.py для проверки результатов")
    else:
        print("\n❌ Ошибка при пересчёте")
        print(f"   Exit code: {result.returncode}")

if __name__ == "__main__":
    main()

