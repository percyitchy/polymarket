#!/usr/bin/env python3
"""
Обновление .env файла с правильными Topic ID
"""
import os
import re

ENV_FILE = ".env"
CORRECT_CHAT_ID = "-1003396499359"
LOW_SIZE_TOPIC_ID = "2"
HIGH_SIZE_TOPIC_ID = "3"
SIZE_THRESHOLD = "10000"

def update_env_file():
    """Обновить .env файл с правильными значениями"""
    
    # Читаем текущий .env
    env_content = ""
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            env_content = f.read()
    else:
        print(f"⚠️  Файл {ENV_FILE} не найден, будет создан новый")
    
    lines = env_content.split('\n')
    new_lines = []
    
    # Флаги для отслеживания, что мы уже добавили
    added_reports_chat_id = False
    added_low_size_topic = False
    added_high_size_topic = False
    added_threshold = False
    
    # Обрабатываем существующие строки
    for line in lines:
        stripped = line.strip()
        
        # Пропускаем старые значения этих переменных
        if stripped.startswith('TELEGRAM_REPORTS_CHAT_ID='):
            # Обновляем на правильное значение
            new_lines.append(f"TELEGRAM_REPORTS_CHAT_ID={CORRECT_CHAT_ID}")
            added_reports_chat_id = True
            continue
        elif stripped.startswith('TELEGRAM_LOW_SIZE_TOPIC_ID='):
            new_lines.append(f"TELEGRAM_LOW_SIZE_TOPIC_ID={LOW_SIZE_TOPIC_ID}")
            added_low_size_topic = True
            continue
        elif stripped.startswith('TELEGRAM_HIGH_SIZE_TOPIC_ID='):
            new_lines.append(f"TELEGRAM_HIGH_SIZE_TOPIC_ID={HIGH_SIZE_TOPIC_ID}")
            added_high_size_topic = True
            continue
        elif stripped.startswith('SIZE_THRESHOLD_USD='):
            new_lines.append(f"SIZE_THRESHOLD_USD={SIZE_THRESHOLD}")
            added_threshold = True
            continue
        
        new_lines.append(line)
    
    # Добавляем недостающие переменные в конец
    if not added_reports_chat_id:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.append("# Telegram Forum Topics Configuration")
        new_lines.append(f"TELEGRAM_REPORTS_CHAT_ID={CORRECT_CHAT_ID}")
    
    if not added_low_size_topic:
        new_lines.append(f"TELEGRAM_LOW_SIZE_TOPIC_ID={LOW_SIZE_TOPIC_ID}")
    
    if not added_high_size_topic:
        new_lines.append(f"TELEGRAM_HIGH_SIZE_TOPIC_ID={HIGH_SIZE_TOPIC_ID}")
    
    if not added_threshold:
        new_lines.append(f"SIZE_THRESHOLD_USD={SIZE_THRESHOLD}  # Threshold for Low/High Size routing (default: $10,000)")
    
    # Сохраняем
    new_content = '\n'.join(new_lines)
    
    try:
        with open(ENV_FILE, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"✅ Файл {ENV_FILE} успешно обновлен!")
        return True
    except Exception as e:
        print(f"❌ Ошибка при сохранении: {e}")
        return False

def main():
    print("=" * 70)
    print("⚙️  ОБНОВЛЕНИЕ .env С ПРАВИЛЬНЫМИ TOPIC ID")
    print("=" * 70)
    print()
    print("Будут добавлены/обновлены следующие значения:")
    print()
    print(f"TELEGRAM_REPORTS_CHAT_ID={CORRECT_CHAT_ID}")
    print(f"TELEGRAM_LOW_SIZE_TOPIC_ID={LOW_SIZE_TOPIC_ID}")
    print(f"TELEGRAM_HIGH_SIZE_TOPIC_ID={HIGH_SIZE_TOPIC_ID}")
    print(f"SIZE_THRESHOLD_USD={SIZE_THRESHOLD}")
    print()
    
    if update_env_file():
        print()
        print("=" * 70)
        print("✅ ГОТОВО!")
        print("=" * 70)
        print()
        print("Теперь перезапустите бота, чтобы изменения вступили в силу:")
        print("  python3 polymarket_notifier.py")
        print()
        print("Сигналы будут автоматически распределяться:")
        print("  - Low Size (< $10,000) → тема 'Low Size Alerts' (Topic ID: 2)")
        print("  - High Size (>= $10,000) → тема 'High Size Alerts' (Topic ID: 3)")
    else:
        print()
        print("⚠️  Не удалось автоматически обновить .env")
        print("Добавьте значения вручную в файл .env")

if __name__ == "__main__":
    main()

