#!/usr/bin/env python3
"""
Получение Topic ID из правильного канала "POLY DAO TEST"
"""
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Правильный CHAT_ID для канала "POLY DAO TEST"
CORRECT_CHAT_ID = "-1003396499359"

if not BOT_TOKEN:
    print("❌ TELEGRAM_BOT_TOKEN не найден в .env")
    exit(1)

def get_updates():
    """Получить последние обновления от бота"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {
        "offset": -200,
        "limit": 200
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

def format_date(timestamp):
    """Форматировать timestamp в читаемую дату"""
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(timestamp)

def main():
    print("=" * 70)
    print("🔍 ПОИСК TOPIC ID В КАНАЛЕ 'POLY DAO TEST'")
    print("=" * 70)
    print()
    print(f"Канал ID: {CORRECT_CHAT_ID}")
    print()
    print("ШАГ 1: Отправьте маркерные сообщения в темы")
    print("1. Откройте канал 'POLY DAO TEST' в Telegram")
    print("2. Откройте тему 'Low Size Alerts'")
    print("3. Отправьте боту сообщение: LOW SIZE TEST")
    print("4. Откройте тему 'High Size Alerts'")
    print("5. Отправьте боту сообщение: HIGH SIZE TEST")
    print()
    print("После отправки нажмите Enter...")
    print()
    
    try:
        input()
    except:
        pass
    
    print()
    print("Анализирую обновления...")
    print()
    
    updates = get_updates()
    
    if not updates:
        print("❌ Обновления не найдены")
        return
    
    # Ищем сообщения из правильного канала с topic_id
    topics = {}
    
    for update in updates:
        message = update.get("message")
        if not message:
            continue
        
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        message_thread_id = message.get("message_thread_id")
        text = message.get("text", "").upper().strip()
        
        # Только из правильного канала и только из тем
        if chat_id == CORRECT_CHAT_ID and message_thread_id:
            if message_thread_id not in topics:
                topics[message_thread_id] = {
                    "messages": [],
                    "last_seen": message.get("date", 0)
                }
            
            topics[message_thread_id]["messages"].append({
                "text": text,
                "date": message.get("date", 0),
                "full_text": message.get("text", "")
            })
            
            # Обновляем last_seen
            if message.get("date", 0) > topics[message_thread_id]["last_seen"]:
                topics[message_thread_id]["last_seen"] = message.get("date", 0)
    
    if not topics:
        print("❌ Темы не найдены в обновлениях")
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
        return
    
    print(f"✅ Найдено тем: {len(topics)}")
    print()
    print("=" * 70)
    print("📋 НАЙДЕННЫЕ ТЕМЫ")
    print("=" * 70)
    print()
    
    # Сортируем по последнему сообщению
    sorted_topics = sorted(topics.items(), key=lambda x: x[1]["last_seen"], reverse=True)
    
    low_size_id = None
    high_size_id = None
    
    for topic_id, info in sorted_topics:
        messages = info["messages"]
        last_seen = format_date(info["last_seen"])
        
        print(f"📌 Topic ID: {topic_id}")
        print(f"   Последнее сообщение: {last_seen}")
        print(f"   Всего сообщений: {len(messages)}")
        print("   Последние сообщения:")
        
        for msg in messages[-5:]:
            print(f"     - {msg['full_text'][:60]}")
        
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
        print("✅ Обе темы определены автоматически!")
        print()
        print(f"TELEGRAM_REPORTS_CHAT_ID={CORRECT_CHAT_ID}")
        print(f"TELEGRAM_LOW_SIZE_TOPIC_ID={low_size_id}")
        print(f"TELEGRAM_HIGH_SIZE_TOPIC_ID={high_size_id}")
        print("SIZE_THRESHOLD_USD=10000")
    elif low_size_id:
        print("✅ Найдена тема 'Low Size Alerts'")
        print()
        print(f"TELEGRAM_REPORTS_CHAT_ID={CORRECT_CHAT_ID}")
        print(f"TELEGRAM_LOW_SIZE_TOPIC_ID={low_size_id}")
        print(f"TELEGRAM_HIGH_SIZE_TOPIC_ID=<укажите_вручную>")
        print()
        print("Остальные Topic ID:")
        for tid, _ in sorted_topics:
            if tid != low_size_id:
                print(f"  - {tid}")
    elif high_size_id:
        print("✅ Найдена тема 'High Size Alerts'")
        print()
        print(f"TELEGRAM_REPORTS_CHAT_ID={CORRECT_CHAT_ID}")
        print(f"TELEGRAM_LOW_SIZE_TOPIC_ID=<укажите_вручную>")
        print(f"TELEGRAM_HIGH_SIZE_TOPIC_ID={high_size_id}")
        print()
        print("Остальные Topic ID:")
        for tid, _ in sorted_topics:
            if tid != high_size_id:
                print(f"  - {tid}")
    else:
        print("⚠️  Не удалось автоматически определить темы")
        print()
        print("Найдены следующие Topic ID:")
        for tid, _ in sorted_topics:
            print(f"  - {tid}")
        print()
        print("Определите вручную по сообщениям выше:")
        print("- Тема, где вы отправили 'LOW' → Low Size Alerts")
        print("- Тема, где вы отправили 'HIGH' → High Size Alerts")
        print()
        print(f"TELEGRAM_REPORTS_CHAT_ID={CORRECT_CHAT_ID}")
        print("TELEGRAM_LOW_SIZE_TOPIC_ID=<ID_где_отправили_LOW>")
        print("TELEGRAM_HIGH_SIZE_TOPIC_ID=<ID_где_отправили_HIGH>")
    
    print()

if __name__ == "__main__":
    main()

