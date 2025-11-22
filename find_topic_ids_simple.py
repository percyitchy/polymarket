#!/usr/bin/env python3
"""
Простой способ найти Topic ID тем
"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_REPORTS_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")

if not BOT_TOKEN:
    print("❌ TELEGRAM_BOT_TOKEN не найден в .env")
    exit(1)

if not CHAT_ID:
    print("❌ TELEGRAM_CHAT_ID или TELEGRAM_REPORTS_CHAT_ID не найден в .env")
    exit(1)

print("=" * 70)
print("🔍 ПОИСК TOPIC ID ТЕМ")
print("=" * 70)
print()
print("ШАГ 1: Отправьте сообщения в темы")
print()
print("1. Откройте Telegram на телефоне/компьютере")
print("2. Откройте канал 'POLY DAO TEST'")
print("3. Откройте тему 'Low Size Alerts'")
print("4. Отправьте боту сообщение: LOW")
print("5. Откройте тему 'High Size Alerts'")
print("6. Отправьте боту сообщение: HIGH")
print()
print("После отправки сообщений нажмите Enter...")
print()

try:
    input()
except:
    pass

print()
print("Анализирую обновления...")
print()

# Получаем обновления
url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
params = {"offset": -100, "limit": 100}

try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    if not data.get("ok"):
        print(f"❌ Ошибка API: {data.get('description', 'Unknown error')}")
        exit(1)
    
    updates = data.get("result", [])
    
    # Ищем сообщения из нужного канала с topic_id
    topics = {}
    
    for update in updates:
        message = update.get("message")
        if not message:
            continue
        
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        message_thread_id = message.get("message_thread_id")
        text = message.get("text", "").upper().strip()
        
        # Только из нужного канала и только из тем
        if chat_id == str(CHAT_ID) and message_thread_id:
            if message_thread_id not in topics:
                topics[message_thread_id] = []
            
            topics[message_thread_id].append({
                "text": text,
                "date": message.get("date", 0)
            })
    
    if not topics:
        print("❌ Темы не найдены!")
        print()
        print("Убедитесь, что:")
        print("1. Вы отправили сообщения В ТЕМЫ (не в общий чат канала)")
        print("2. Бот является администратором канала")
        print("3. Канал является форум-группой (Topics enabled)")
        print()
        print("Попробуйте еще раз:")
        print("1. Откройте тему 'Low Size Alerts'")
        print("2. Отправьте боту: LOW")
        print("3. Откройте тему 'High Size Alerts'")
        print("4. Отправьте боту: HIGH")
        print("5. Запустите скрипт снова")
        exit(1)
    
    print(f"✅ Найдено тем: {len(topics)}")
    print()
    print("=" * 70)
    print("📋 РЕЗУЛЬТАТЫ")
    print("=" * 70)
    print()
    
    low_size_id = None
    high_size_id = None
    
    for topic_id, messages in topics.items():
        print(f"📌 Topic ID: {topic_id}")
        print(f"   Сообщений: {len(messages)}")
        
        # Показываем сообщения
        for msg in messages[-3:]:  # Последние 3
            print(f"   - {msg['text']}")
        
        # Определяем по содержимому
        all_text = " ".join([m["text"] for m in messages])
        if "LOW" in all_text:
            low_size_id = topic_id
            print(f"   ✅ Это тема 'Low Size Alerts'!")
        elif "HIGH" in all_text:
            high_size_id = topic_id
            print(f"   ✅ Это тема 'High Size Alerts'!")
        
        print()
    
    print("=" * 70)
    print("📝 НАСТРОЙКИ ДЛЯ .env")
    print("=" * 70)
    print()
    
    if low_size_id and high_size_id:
        print("✅ Обе темы определены!")
        print()
        print(f"TELEGRAM_REPORTS_CHAT_ID={CHAT_ID}")
        print(f"TELEGRAM_LOW_SIZE_TOPIC_ID={low_size_id}")
        print(f"TELEGRAM_HIGH_SIZE_TOPIC_ID={high_size_id}")
        print("SIZE_THRESHOLD_USD=10000")
    elif low_size_id:
        print("✅ Найдена тема 'Low Size Alerts'")
        print()
        print(f"TELEGRAM_REPORTS_CHAT_ID={CHAT_ID}")
        print(f"TELEGRAM_LOW_SIZE_TOPIC_ID={low_size_id}")
        print(f"TELEGRAM_HIGH_SIZE_TOPIC_ID=<укажите_вручную>")
        print()
        print("Остальные Topic ID:")
        for tid in topics.keys():
            if tid != low_size_id:
                print(f"  - {tid}")
    elif high_size_id:
        print("✅ Найдена тема 'High Size Alerts'")
        print()
        print(f"TELEGRAM_REPORTS_CHAT_ID={CHAT_ID}")
        print(f"TELEGRAM_LOW_SIZE_TOPIC_ID=<укажите_вручную>")
        print(f"TELEGRAM_HIGH_SIZE_TOPIC_ID={high_size_id}")
        print()
        print("Остальные Topic ID:")
        for tid in topics.keys():
            if tid != high_size_id:
                print(f"  - {tid}")
    else:
        print("⚠️  Не удалось автоматически определить темы")
        print()
        print("Найдены следующие Topic ID:")
        for tid in topics.keys():
            print(f"  - {tid}")
        print()
        print("Определите вручную по сообщениям выше:")
        print("- Тема, где вы отправили 'LOW' → Low Size Alerts")
        print("- Тема, где вы отправили 'HIGH' → High Size Alerts")
        print()
        print(f"TELEGRAM_REPORTS_CHAT_ID={CHAT_ID}")
        print("TELEGRAM_LOW_SIZE_TOPIC_ID=<ID_где_отправили_LOW>")
        print("TELEGRAM_HIGH_SIZE_TOPIC_ID=<ID_где_отправили_HIGH>")
    
    print()

except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

