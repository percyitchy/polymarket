#!/usr/bin/env python3
"""
Поиск адресов кошельков из сигнала Warriors vs Pelicans
"""
import os
import re
import sqlite3

# Паттерны из изображения
PATTERNS = [
    ('0x4e7', '823'),
    ('0x97e', 'a30'),
    ('0xdb2', '56e')
]

def search_in_files():
    """Поиск адресов в текстовых файлах"""
    print("Поиск адресов в текстовых файлах...\n")
    found = {}
    
    # Получаем все текстовые файлы
    txt_files = [f for f in os.listdir('.') if f.endswith('.txt')]
    
    for prefix, suffix in PATTERNS:
        found[prefix] = []
        for txt_file in txt_files:
            try:
                with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        # Ищем Ethereum адреса (42 символа, начинаются с 0x)
                        if line.startswith('0x') and len(line) == 42:
                            addr_lower = line.lower()
                            if addr_lower.startswith(prefix.lower()) and addr_lower.endswith(suffix.lower()):
                                if line not in found[prefix]:
                                    found[prefix].append(line)
                                    print(f"✅ Найден адрес для {prefix}...{suffix}:")
                                    print(f"   {line}")
                                    print(f"   Файл: {txt_file}, строка: {line_num}\n")
            except Exception as e:
                pass
    
    return found

def search_in_database():
    """Поиск адресов в базе данных"""
    print("\n" + "="*70)
    print("Поиск в базе данных...\n")
    
    try:
        db = sqlite3.connect('polymarket_notifier.db')
        cursor = db.cursor()
        
        found = {}
        for prefix, suffix in PATTERNS:
            found[prefix] = []
            cursor.execute('SELECT address FROM wallets WHERE LOWER(address) LIKE ? AND LOWER(address) LIKE ?', 
                         (f'{prefix.lower()}%', f'%{suffix.lower()}'))
            matches = cursor.fetchall()
            
            if matches:
                print(f"✅ Найдено в БД для {prefix}...{suffix}:")
                for match in matches:
                    addr = match[0]
                    found[prefix].append(addr)
                    # Получаем информацию
                    cursor.execute('SELECT win_rate, traded_total FROM wallets WHERE address = ?', (addr,))
                    info = cursor.fetchone()
                    if info:
                        wr, trades = info
                        print(f"   {addr}")
                        if wr:
                            print(f"   WR: {wr:.1%}, Trades: {trades}")
                        print()
        
        db.close()
        return found
    except Exception as e:
        print(f"Ошибка при работе с БД: {e}")
        return {}

def main():
    print("="*70)
    print("ПОИСК АДРЕСОВ КОШЕЛЬКОВ ИЗ СИГНАЛА")
    print("="*70)
    print("\nИщем адреса по паттернам:")
    for prefix, suffix in PATTERNS:
        print(f"  - {prefix}...{suffix}")
    print()
    
    # Поиск в файлах
    found_files = search_in_files()
    
    # Поиск в БД
    found_db = search_in_database()
    
    # Объединяем результаты
    print("\n" + "="*70)
    print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ:")
    print("="*70)
    
    all_found = []
    for prefix, suffix in PATTERNS:
        addresses = list(set(found_files.get(prefix, []) + found_db.get(prefix, [])))
        if addresses:
            print(f"\n✅ {prefix}...{suffix}:")
            for addr in addresses:
                print(f"   {addr}")
                all_found.append(addr)
        else:
            print(f"\n⚠️  {prefix}...{suffix}: не найдено")
    
    if all_found:
        print("\n" + "="*70)
        print("НАЙДЕННЫЕ АДРЕСА КОШЕЛЬКОВ:")
        print("="*70)
        for i, addr in enumerate(all_found, 1):
            print(f"{i}. {addr}")
    else:
        print("\n⚠️  Адреса не найдены в файлах и базе данных.")
        print("Возможно, это тестовый сигнал или адреса еще не добавлены в систему.")

if __name__ == "__main__":
    main()

