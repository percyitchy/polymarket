#!/usr/bin/env python3
"""
Получение ID тем из последних обновлений Telegram бота
Используйте этот скрипт после отправки сообщения в тему
"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    print("❌ TELEGRAM_BOT_TOKEN не найден в .env")
    exit(1)

def get_updates():
    """Получить последние обновления от бота"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {
        "offset": -50,  # Последние 50 обновлений
        "limit": 50
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
    print("🔍 Анализирую последние обновления бота...")
    print()
    
    updates = get_updates()
    
    if not updates:
        print("❌ Обновления не найдены")
        print()
        print("💡 Инструкция:")
        print("1. Откройте канал 'POLY DAO TEST' в Telegram")
        print("2. Откройте тему 'Low Size Alerts'")
        print("3. Отправьте боту любое сообщение в этой теме")
        print("4. Затем запустите этот скрипт снова")
        return
    
    print(f"✅ Найдено обновлений: {len(updates)}")
    print()
    
    topics_found = {}
    
    for update in updates:
        message = update.get("message")
        if not message:
            continue
        
        chat = message.get("chat", {})
        message_thread_id = message.get("message_thread_id")
        
        if message_thread_id:
            chat_id = str(chat.get("id", ""))
            chat_title = chat.get("title", "Unknown")
            text = message.get("text", "")
            date = message.get("date", 0)
            
            if message_thread_id not in topics_found:
                topics_found[message_thread_id] = {
                    "chat_id": chat_id,
                    "chat_title": chat_title,
                    "first_seen": date,
                    "messages": []
                }
            
            topics_found[message_thread_id]["messages"].append({
                "text": text[:50],
                "date": date
            })
    
    if not topics_found:
        print("❌ Темы не найдены в обновлениях")
        print()
        print("💡 Убедитесь, что:")
        print("   1. Вы отправили сообщение в тему (не в общий чат)")
        print("   2. Бот является администратором канала")
        print("   3. Канал является форум-группой (Topics enabled)")
        return
    
    print("=" * 60)
    print("📋 НАЙДЕННЫЕ ТЕМЫ:")
    print("=" * 60)
    print()
    
    low_size_id = None
    high_size_id = None
    
    for topic_id, info in topics_found.items():
        chat_title = info["chat_title"]
        message_count = len(info["messages"])
        
        print(f"📌 Topic ID: {topic_id}")
        print(f"   Канал: {chat_title}")
        print(f"   Сообщений в теме: {message_count}")
        print()
        
        # Попробуем определить тему по содержимому сообщений
        # (это не идеально, но может помочь)
        for msg in info["messages"][:3]:
            text_lower = msg.get("text", "").lower()
            if "low" in text_lower or "small" in text_lower:
                low_size_id = topic_id
            if "high" in text_lower or "large" in text_lower:
                high_size_id = topic_id
    
    print("=" * 60)
    print("📝 РЕКОМЕНДУЕМЫЕ НАСТРОЙКИ ДЛЯ .env:")
    print("=" * 60)
    print()
    
    if len(topics_found) == 1:
        topic_id = list(topics_found.keys())[0]
        print(f"# Найдена одна тема, укажите её ID вручную:")
        print(f"TELEGRAM_LOW_SIZE_TOPIC_ID={topic_id}")
        print(f"TELEGRAM_HIGH_SIZE_TOPIC_ID=<ID_другой_темы>")
    elif len(topics_found) == 2:
        topic_ids = list(topics_found.keys())
        print(f"# Найдены две темы, укажите их вручную:")
        print(f"TELEGRAM_LOW_SIZE_TOPIC_ID={topic_ids[0]}")
        print(f"TELEGRAM_HIGH_SIZE_TOPIC_ID={topic_ids[1]}")
    else:
        print("# Найдено несколько тем. Укажите ID вручную:")
        for topic_id in topics_found.keys():
            print(f"# Topic ID: {topic_id}")
        print("TELEGRAM_LOW_SIZE_TOPIC_ID=<ID_темы_Low_Size_Alerts>")
        print("TELEGRAM_HIGH_SIZE_TOPIC_ID=<ID_темы_High_Size_Alerts>")
    
    print()
    print(f"TELEGRAM_REPORTS_CHAT_ID={list(topics_found.values())[0]['chat_id']}")
    print()
    
    print("💡 Для точного определения:")
    print("   1. Отправьте сообщение 'LOW' в тему 'Low Size Alerts'")
    print("   2. Отправьте сообщение 'HIGH' в тему 'High Size Alerts'")
    print("   3. Запустите скрипт снова")

if __name__ == "__main__":
    main()

