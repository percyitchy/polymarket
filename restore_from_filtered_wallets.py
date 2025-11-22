#!/usr/bin/env python3
"""
Восстановление кошельков из файла filtered_wallets_new_criteria_20251115_174511.txt
"""

import sys
import re
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from db import PolymarketDB

def extract_wallets_from_file(file_path: str):
    """Извлекает адреса кошельков из файла"""
    wallets = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Пропускаем заголовки (первые ~10 строк)
    for line in lines[10:]:
        line = line.strip()
        if not line or line.startswith('='):
            continue
        
        # Ищем адреса кошельков (0x + 40 hex символов)
        matches = re.findall(r'0x[a-fA-F0-9]{40}', line)
        if matches:
            wallets.extend(matches)
    
    # Удаляем дубликаты, сохраняя порядок
    seen = set()
    unique_wallets = []
    for w in wallets:
        if w.lower() not in seen:
            seen.add(w.lower())
            unique_wallets.append(w.lower())
    
    return unique_wallets

def restore_wallets(db_path: str, backup_file: str):
    """Восстанавливает кошельки из файла"""
    print("=" * 80)
    print("🔄 ВОССТАНОВЛЕНИЕ КОШЕЛЬКОВ ИЗ ФАЙЛА")
    print("=" * 80)
    print()
    
    # Извлекаем адреса
    print(f"📖 Читаю файл: {backup_file}")
    wallet_addresses = extract_wallets_from_file(backup_file)
    print(f"✅ Найдено уникальных адресов: {len(wallet_addresses)}")
    print()
    
    # Инициализируем базу данных
    db = PolymarketDB(db_path)
    
    # Проверяем, какие кошельки уже есть в базе
    print("🔍 Проверяю существующие кошельки...")
    existing_addresses = set()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT LOWER(address) FROM wallets")
        existing_addresses = {row[0].lower() for row in cursor.fetchall()}
    
    print(f"   Уже в базе: {len(existing_addresses)}")
    print()
    
    # Фильтруем кошельки, которых еще нет в базе
    new_wallets = [w for w in wallet_addresses if w.lower() not in existing_addresses]
    print(f"📋 Новых кошельков для добавления: {len(new_wallets)}")
    print()
    
    if not new_wallets:
        print("✅ Все кошельки уже в базе!")
        return
    
    # Добавляем кошельки в базу (без данных, они будут проанализированы позже)
    print("➕ Добавляю кошельки в базу...")
    added_count = 0
    failed_count = 0
    
    for wallet_address in new_wallets:
        try:
            # Добавляем кошелек в очередь анализа
            # Workers проанализируют и заполнят данные позже
            success = db.add_wallet_to_queue(
                address=wallet_address,
                display=wallet_address,
                source="restored_from_filtered_wallets"
            )
            if success:
                added_count += 1
            else:
                failed_count += 1
            
            if added_count % 100 == 0:
                print(f"   Добавлено: {added_count}/{len(new_wallets)}")
        except Exception as e:
            failed_count += 1
            if failed_count <= 5:  # Показываем только первые 5 ошибок
                print(f"   ⚠️  Ошибка при добавлении {wallet_address[:20]}...: {e}")
    
    print()
    print(f"✅ Добавлено в базу: {added_count} кошельков")
    if failed_count > 0:
        print(f"❌ Ошибок: {failed_count}")
    print()
    
    # Проверяем новую статистику
    stats = db.get_wallet_stats()
    print("📊 Новая статистика:")
    print(f"   Total wallets: {stats.get('total_wallets', 0)}")
    print(f"   Tracked wallets: {stats.get('tracked_wallets', 0)}")
    print()
    print("=" * 80)
    print("✅ Восстановление завершено!")
    print("   Кошельки добавлены в базу и будут проанализированы workers.")
    print("=" * 80)

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)
    
    backup_file = "filtered_wallets_new_criteria_20251115_174511.txt"
    
    if not os.path.exists(backup_file):
        print(f"❌ Файл не найден: {backup_file}")
        sys.exit(1)
    
    restore_wallets(db_path, backup_file)

