#!/usr/bin/env python3
"""
Альтернативный способ определения Topic ID тем
Просит пользователя отправить сообщения вручную и анализирует обновления
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

def get_updates():
    """Получить последние обновления от бота"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {
        "offset": -100,  # Последние 100 обновлений
        "limit": 100
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("ok"):
            return data.get("result", [])
        else:
            print(f"❌ Ошибка API: {data.get('description', 'Unknown error')}")
            return []
    except Exception as e:
        print(f"❌ Ошибка при запросе: {e}")
        return []

def main():
    print("=" * 60)
    print("🔍 ОПРЕДЕЛЕНИЕ ID ТЕМ (РУЧНОЙ СПОСОБ)")
    print("=" * 60)
    print()
    print("Инструкция:")
    print("1. Откройте канал 'POLY DAO TEST' в Telegram")
    print("2. Откройте тему 'Low Size Alerts'")
    print("3. Отправьте боту сообщение: 'LOW SIZE TEST'")
    print("4. Откройте тему 'High Size Alerts'")
    print("5. Отправьте боту сообщение: 'HIGH SIZE TEST'")
    print()
    print("После этого нажмите Enter для анализа...")
    input()
    
    print()
    print("Анализирую обновления...")
    print()
    
    updates = get_updates()
    
    if not updates:
        print("❌ Обновления не найдены")
        print("Убедитесь, что вы отправили сообщения в темы")
        return
    
    # Ищем сообщения с маркерами
    topics_found = {}
    
    for update in updates:
        message = update.get("message")
        if not message:
            continue
        
        chat = message.get("chat", {})
        message_thread_id = message.get("message_thread_id")
        text = message.get("text", "").upper()
        
        if message_thread_id:
            chat_id = str(chat.get("id", ""))
            
            if chat_id == str(CHAT_ID):
                if message_thread_id not in topics_found:
                    topics_found[message_thread_id] = {
                        "messages": [],
                        "first_seen": message.get("date", 0)
                    }
                
                topics_found[message_thread_id]["messages"].append({
                    "text": text,
                    "date": message.get("date", 0)
                })
    
    if not topics_found:
        print("❌ Темы не найдены в обновлениях")
        print()
        print("Убедитесь, что:")
        print("1. Вы отправили сообщения в темы (не в общий чат)")
        print("2. Бот является администратором канала")
        print("3. Канал является форум-группой")
        return
    
    print(f"✅ Найдено тем: {len(topics_found)}")
    print()
    print("=" * 60)
    print("📋 РЕЗУЛЬТАТЫ АНАЛИЗА")
    print("=" * 60)
    print()
    
    low_size_id = None
    high_size_id = None
    
    for topic_id, info in topics_found.items():
        messages = info["messages"]
        print(f"📌 Topic ID: {topic_id}")
        print(f"   Сообщений: {len(messages)}")
        
        # Анализируем содержимое сообщений
        for msg in messages:
            text = msg.get("text", "")
            print(f"   - {text}")
            
            # Определяем по тексту
            if "LOW" in text or "LOW SIZE" in text:
                low_size_id = topic_id
            if "HIGH" in text or "HIGH SIZE" in text:
                high_size_id = topic_id
        
        print()
    
    print("=" * 60)
    print("📝 РЕКОМЕНДУЕМЫЕ НАСТРОЙКИ ДЛЯ .env")
    print("=" * 60)
    print()
    
    if low_size_id and high_size_id:
        print("✅ Обе темы определены автоматически!")
        print()
        print(f"TELEGRAM_LOW_SIZE_TOPIC_ID={low_size_id}")
        print(f"TELEGRAM_HIGH_SIZE_TOPIC_ID={high_size_id}")
    elif low_size_id:
        print("✅ Найдена тема 'Low Size Alerts'")
        print()
        print(f"TELEGRAM_LOW_SIZE_TOPIC_ID={low_size_id}")
        print(f"TELEGRAM_HIGH_SIZE_TOPIC_ID=<укажите_вручную>")
        print()
        print("Для 'High Size Alerts' проверьте остальные Topic ID:")
        for topic_id in topics_found.keys():
            if topic_id != low_size_id:
                print(f"  - Topic ID {topic_id}")
    elif high_size_id:
        print("✅ Найдена тема 'High Size Alerts'")
        print()
        print(f"TELEGRAM_LOW_SIZE_TOPIC_ID=<укажите_вручную>")
        print(f"TELEGRAM_HIGH_SIZE_TOPIC_ID={high_size_id}")
        print()
        print("Для 'Low Size Alerts' проверьте остальные Topic ID:")
        for topic_id in topics_found.keys():
            if topic_id != high_size_id:
                print(f"  - Topic ID {topic_id}")
    else:
        print("⚠️  Не удалось автоматически определить темы")
        print()
        print("Найдены следующие Topic ID:")
        for topic_id in topics_found.keys():
            print(f"  - Topic ID {topic_id}")
        print()
        print("Определите вручную:")
        print("1. Откройте канал в Telegram")
        print("2. Посмотрите, в какой теме вы отправили 'LOW SIZE TEST'")
        print("3. Запомните Topic ID этой темы - это Low Size")
        print("4. Посмотрите, в какой теме вы отправили 'HIGH SIZE TEST'")
        print("5. Запомните Topic ID этой темы - это High Size")
    
    print()
    print(f"TELEGRAM_REPORTS_CHAT_ID={CHAT_ID}")
    print()

if __name__ == "__main__":
    main()

