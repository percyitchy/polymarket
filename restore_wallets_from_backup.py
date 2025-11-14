#!/usr/bin/env python3
"""
Скрипт для восстановления кошельков из резервной копии tracked_wallets_20251106_185616.txt
Добавляет кошельки в очередь анализа для восстановления данных
"""

import sys
import re
from datetime import datetime
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from db import PolymarketDB
from wallet_analyzer import WalletAnalyzer

def parse_backup_file(file_path: str):
    """Парсит файл с резервной копией и извлекает адреса кошельков"""
    wallets = []
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Пропускаем заголовки (первые 8 строк)
    for line in lines[8:]:
        line = line.strip()
        if not line or line.startswith('='):
            continue
        
        # Парсим строку: Address Display Trades Win Rate PnL Daily Freq Last Trade Source
        parts = line.split()
        if len(parts) >= 8:
            address = parts[0]
            wallets.append({
                'address': address,
                'source': ' '.join(parts[7:]) if len(parts) > 7 else 'restored_from_backup'
            })
    
    return wallets

def restore_wallets(db_path: str, backup_file: str):
    """Восстанавливает кошельки из резервной копии"""
    print("=" * 80)
    print("🔄 ВОССТАНОВЛЕНИЕ КОШЕЛЬКОВ ИЗ РЕЗЕРВНОЙ КОПИИ")
    print("=" * 80)
    print()
    
    # Парсим файл с резервной копией
    print(f"📖 Читаю файл: {backup_file}")
    wallets = parse_backup_file(backup_file)
    print(f"✅ Найдено кошельков: {len(wallets)}")
    print()
    
    # Инициализируем базу данных
    db = PolymarketDB(db_path)
    
    # Проверяем, какие кошельки уже есть в базе
    print("🔍 Проверяю существующие кошельки...")
    existing_addresses = set()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT address FROM wallets")
        existing_addresses = {row[0] for row in cursor.fetchall()}
    
    print(f"   Уже в базе: {len(existing_addresses)}")
    print()
    
    # Фильтруем кошельки, которых еще нет в базе
    new_wallets = [w for w in wallets if w['address'] not in existing_addresses]
    print(f"📋 Новых кошельков для восстановления: {len(new_wallets)}")
    print()
    
    if not new_wallets:
        print("✅ Все кошельки уже в базе!")
        return
    
    # Добавляем кошельки в очередь анализа
    print("➕ Добавляю кошельки в очередь анализа...")
    added_count = 0
    
    for wallet in new_wallets:
        try:
            if db.add_wallet_to_queue(
                address=wallet['address'],
                display=wallet['address'],
                source=wallet['source']
            ):
                added_count += 1
            
            if added_count % 50 == 0:
                print(f"   Добавлено: {added_count}/{len(new_wallets)}")
        except Exception as e:
            print(f"   ⚠️  Ошибка при добавлении {wallet['address']}: {e}")
    
    print()
    print(f"✅ Добавлено в очередь: {added_count} кошельков")
    print()
    
    # Проверяем статус очереди
    stats = db.get_queue_stats()
    print("📊 Статус очереди:")
    print(f"   - Pending: {stats.get('pending_jobs', 0)}")
    print(f"   - Processing: {stats.get('processing_jobs', 0)}")
    print(f"   - Total: {stats.get('total_jobs', 0)}")
    print()
    print("=" * 80)
    print("✅ Восстановление завершено!")
    print("   Workers начнут анализировать кошельки и восстанавливать данные.")
    print("=" * 80)

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
    backup_file = "tracked_wallets_20251106_185616.txt"
    
    if not os.path.exists(backup_file):
        print(f"❌ Файл не найден: {backup_file}")
        sys.exit(1)
    
    restore_wallets(db_path, backup_file)

