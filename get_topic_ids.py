#!/usr/bin/env python3
"""
Скрипт для получения ID тем из Telegram форум-группы "POLY DAO TEST"
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
    print("Укажите ID канала 'POLY DAO TEST' в переменной TELEGRAM_REPORTS_CHAT_ID")
    exit(1)

def get_forum_topics(chat_id):
    """Получить список тем форум-группы"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getForumTopics"
    params = {
        "chat_id": chat_id
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("ok"):
            topics = data.get("result", {}).get("topics", [])
            return topics
        else:
            print(f"❌ Ошибка API: {data.get('description', 'Unknown error')}")
            return []
    except Exception as e:
        print(f"❌ Ошибка при запросе: {e}")
        return []

def main():
    print(f"🔍 Ищу темы в канале {CHAT_ID}...")
    print()
    
    topics = get_forum_topics(CHAT_ID)
    
    if not topics:
        print("❌ Темы не найдены или канал не является форум-группой")
        print()
        print("💡 Убедитесь, что:")
        print("   1. Канал 'POLY DAO TEST' является форум-группой (Topics enabled)")
        print("   2. Бот является администратором канала")
        print("   3. CHAT_ID указан правильно")
        return
    
    print(f"✅ Найдено тем: {len(topics)}")
    print()
    print("=" * 60)
    print("📋 СПИСОК ТЕМ:")
    print("=" * 60)
    print()
    
    low_size_id = None
    high_size_id = None
    
    for topic in topics:
        topic_id = topic.get("message_thread_id")
        name = topic.get("name", "Без названия")
        icon_color = topic.get("icon_color", 0)
        icon_emoji_id = topic.get("icon_emoji_id")
        
        print(f"📌 Тема: {name}")
        print(f"   ID: {topic_id}")
        print(f"   Icon Color: {icon_color}")
        if icon_emoji_id:
            print(f"   Icon Emoji ID: {icon_emoji_id}")
        print()
        
        # Определяем ID тем по названию
        name_lower = name.lower()
        if "low" in name_lower and "size" in name_lower:
            low_size_id = topic_id
        if "high" in name_lower and "size" in name_lower:
            high_size_id = topic_id
    
    print("=" * 60)
    print("📝 РЕКОМЕНДУЕМЫЕ НАСТРОЙКИ ДЛЯ .env:")
    print("=" * 60)
    print()
    
    if low_size_id:
        print(f"TELEGRAM_LOW_SIZE_TOPIC_ID={low_size_id}")
    else:
        print("# TELEGRAM_LOW_SIZE_TOPIC_ID=  # Не найдена тема 'Low Size Alerts'")
    
    if high_size_id:
        print(f"TELEGRAM_HIGH_SIZE_TOPIC_ID={high_size_id}")
    else:
        print("# TELEGRAM_HIGH_SIZE_TOPIC_ID=  # Не найдена тема 'High Size Alerts'")
    
    print()
    print(f"TELEGRAM_REPORTS_CHAT_ID={CHAT_ID}")
    print()
    
    if low_size_id and high_size_id:
        print("✅ Обе темы найдены! Добавьте эти строки в .env файл")
    elif low_size_id or high_size_id:
        print("⚠️  Найдена только одна тема. Проверьте названия тем в канале")
    else:
        print("❌ Темы 'Low Size Alerts' и 'High Size Alerts' не найдены")
        print("   Убедитесь, что темы созданы в канале 'POLY DAO TEST'")

if __name__ == "__main__":
    main()

