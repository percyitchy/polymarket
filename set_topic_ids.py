#!/usr/bin/env python3
"""
Простой скрипт для настройки Topic ID вручную
"""
import os
import re
from dotenv import load_dotenv

load_dotenv()

CHAT_ID = os.getenv("TELEGRAM_REPORTS_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
ENV_FILE = ".env"

print("=" * 70)
print("⚙️  НАСТРОЙКА TOPIC ID")
print("=" * 70)
print()
print("Если вы уже знаете Topic ID тем, введите их ниже.")
print("Если не знаете, используйте @RawDataBot (см. get_topic_ids_manual.py)")
print()
print("Обычно Topic ID - это небольшие числа:")
print("- Первая тема обычно имеет ID = 2")
print("- Вторая тема обычно имеет ID = 3")
print("- И так далее...")
print()

# Читаем текущий .env если есть
env_content = ""
if os.path.exists(ENV_FILE):
    with open(ENV_FILE, 'r', encoding='utf-8') as f:
        env_content = f.read()

# Спрашиваем у пользователя
try:
    low_size_id = input("Введите Topic ID для 'Low Size Alerts' (или Enter для пропуска): ").strip()
    high_size_id = input("Введите Topic ID для 'High Size Alerts' (или Enter для пропуска): ").strip()
except:
    low_size_id = ""
    high_size_id = ""

print()
print("=" * 70)
print("📝 ОБНОВЛЕНИЕ .env")
print("=" * 70)
print()

# Удаляем старые значения если есть
lines = env_content.split('\n')
new_lines = []
skip_next = False

for i, line in enumerate(lines):
    # Пропускаем строки с этими переменными
    if any(var in line for var in ['TELEGRAM_LOW_SIZE_TOPIC_ID', 'TELEGRAM_HIGH_SIZE_TOPIC_ID', 'SIZE_THRESHOLD_USD']):
        # Но оставляем комментарии
        if line.strip().startswith('#'):
            new_lines.append(line)
        continue
    new_lines.append(line)

env_content = '\n'.join(new_lines)

# Добавляем новые значения
if not env_content.endswith('\n') and env_content:
    env_content += '\n'

# Добавляем секцию если её нет
if 'TELEGRAM_REPORTS_CHAT_ID' not in env_content:
    env_content += f"\n# Telegram Forum Topics (for size-based routing)\n"
    env_content += f"TELEGRAM_REPORTS_CHAT_ID={CHAT_ID}\n"

if 'TELEGRAM_LOW_SIZE_TOPIC_ID' not in env_content:
    env_content += "\n# Telegram Forum Topics (for size-based routing)\n"
    env_content += "# Use get_topic_ids_manual.py script to find topic IDs\n"
    env_content += "# Low Size: alerts with total position < $10,000\n"
    env_content += "# High Size: alerts with total position >= $10,000\n"

if low_size_id:
    # Обновляем или добавляем
    pattern = r'^TELEGRAM_LOW_SIZE_TOPIC_ID=.*$'
    if re.search(pattern, env_content, re.MULTILINE):
        env_content = re.sub(pattern, f'TELEGRAM_LOW_SIZE_TOPIC_ID={low_size_id}', env_content, flags=re.MULTILINE)
    else:
        env_content += f"TELEGRAM_LOW_SIZE_TOPIC_ID={low_size_id}\n"
    print(f"✅ TELEGRAM_LOW_SIZE_TOPIC_ID={low_size_id}")
else:
    env_content += "TELEGRAM_LOW_SIZE_TOPIC_ID=\n"
    print("⚠️  TELEGRAM_LOW_SIZE_TOPIC_ID не указан")

if high_size_id:
    pattern = r'^TELEGRAM_HIGH_SIZE_TOPIC_ID=.*$'
    if re.search(pattern, env_content, re.MULTILINE):
        env_content = re.sub(pattern, f'TELEGRAM_HIGH_SIZE_TOPIC_ID={high_size_id}', env_content, flags=re.MULTILINE)
    else:
        env_content += f"TELEGRAM_HIGH_SIZE_TOPIC_ID={high_size_id}\n"
    print(f"✅ TELEGRAM_HIGH_SIZE_TOPIC_ID={high_size_id}")
else:
    env_content += "TELEGRAM_HIGH_SIZE_TOPIC_ID=\n"
    print("⚠️  TELEGRAM_HIGH_SIZE_TOPIC_ID не указан")

# Добавляем SIZE_THRESHOLD_USD если его нет
if 'SIZE_THRESHOLD_USD' not in env_content:
    env_content += "SIZE_THRESHOLD_USD=10000  # Threshold for Low/High Size routing (default: $10,000)\n"
    print("✅ SIZE_THRESHOLD_USD=10000")

# Сохраняем
try:
    with open(ENV_FILE, 'w', encoding='utf-8') as f:
        f.write(env_content)
    print()
    print(f"✅ Файл {ENV_FILE} обновлен!")
except Exception as e:
    print(f"❌ Ошибка при сохранении: {e}")
    exit(1)

print()
print("=" * 70)
print("📋 ИТОГОВАЯ КОНФИГУРАЦИЯ")
print("=" * 70)
print()
print(f"TELEGRAM_REPORTS_CHAT_ID={CHAT_ID}")
if low_size_id:
    print(f"TELEGRAM_LOW_SIZE_TOPIC_ID={low_size_id}")
else:
    print("TELEGRAM_LOW_SIZE_TOPIC_ID=<не указан>")
if high_size_id:
    print(f"TELEGRAM_HIGH_SIZE_TOPIC_ID={high_size_id}")
else:
    print("TELEGRAM_HIGH_SIZE_TOPIC_ID=<не указан>")
print("SIZE_THRESHOLD_USD=10000")
print()
print("💡 Если ID не указаны, используйте @RawDataBot:")
print("   python3 get_topic_ids_manual.py")
print()

