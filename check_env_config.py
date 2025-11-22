#!/usr/bin/env python3
"""
Проверка конфигурации .env для Topic ID
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("🔍 ПРОВЕРКА КОНФИГУРАЦИИ .env")
print("=" * 70)
print()

reports_chat_id = os.getenv("TELEGRAM_REPORTS_CHAT_ID")
low_size_topic_id = os.getenv("TELEGRAM_LOW_SIZE_TOPIC_ID")
high_size_topic_id = os.getenv("TELEGRAM_HIGH_SIZE_TOPIC_ID")
size_threshold = os.getenv("SIZE_THRESHOLD_USD", "10000")

print("Текущие значения из .env:")
print()

if reports_chat_id:
    print(f"✅ TELEGRAM_REPORTS_CHAT_ID={reports_chat_id}")
    if reports_chat_id == "-1003396499359":
        print("   ✅ Это правильный канал 'POLY DAO TEST'")
    else:
        print(f"   ⚠️  Это не канал 'POLY DAO TEST' (ожидается: -1003396499359)")
else:
    print("❌ TELEGRAM_REPORTS_CHAT_ID не установлен")

if low_size_topic_id:
    print(f"✅ TELEGRAM_LOW_SIZE_TOPIC_ID={low_size_topic_id}")
    if low_size_topic_id == "2":
        print("   ✅ Это правильный ID для 'Low Size Alerts'")
    else:
        print(f"   ⚠️  Ожидается: 2")
else:
    print("❌ TELEGRAM_LOW_SIZE_TOPIC_ID не установлен")

if high_size_topic_id:
    print(f"✅ TELEGRAM_HIGH_SIZE_TOPIC_ID={high_size_topic_id}")
    if high_size_topic_id == "3":
        print("   ✅ Это правильный ID для 'High Size Alerts'")
    else:
        print(f"   ⚠️  Ожидается: 3")
else:
    print("❌ TELEGRAM_HIGH_SIZE_TOPIC_ID не установлен")

print(f"✅ SIZE_THRESHOLD_USD={size_threshold}")

print()
print("=" * 70)
print("📋 РЕКОМЕНДАЦИИ")
print("=" * 70)
print()

if not reports_chat_id or reports_chat_id != "-1003396499359":
    print("⚠️  Нужно обновить TELEGRAM_REPORTS_CHAT_ID:")
    print("   TELEGRAM_REPORTS_CHAT_ID=-1003396499359")
    print()

if not low_size_topic_id or low_size_topic_id != "2":
    print("⚠️  Нужно обновить TELEGRAM_LOW_SIZE_TOPIC_ID:")
    print("   TELEGRAM_LOW_SIZE_TOPIC_ID=2")
    print()

if not high_size_topic_id or high_size_topic_id != "3":
    print("⚠️  Нужно обновить TELEGRAM_HIGH_SIZE_TOPIC_ID:")
    print("   TELEGRAM_HIGH_SIZE_TOPIC_ID=3")
    print()

if all([reports_chat_id == "-1003396499359", low_size_topic_id == "2", high_size_topic_id == "3"]):
    print("✅ Все настройки правильные!")
    print()
    print("💡 Если бот все еще отправляет в старый канал:")
    print("   1. Убедитесь, что бот перезапущен после обновления .env")
    print("   2. Проверьте логи бота при запуске - там должно быть:")
    print("      [NOTIFY] ✅ Using reports_chat_id: -1003396499359")
    print("      [NOTIFY] ✅ Topic routing configured: Low Size (ID: 2), High Size (ID: 3)")
else:
    print("💡 Запустите скрипт для автоматического обновления:")
    print("   python3 update_env_topics.py")

print()

