#!/usr/bin/env python3
"""
Показать все найденные темы и их последние сообщения
Помогает визуально определить, какая тема какая
"""
import os
import requests
from datetime import datetime
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
        "offset": -200,  # Последние 200 обновлений
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
    print("🔍 АНАЛИЗ ВСЕХ ТЕМ В КАНАЛЕ")
    print("=" * 70)
    print()
    print(f"Канал ID: {CHAT_ID}")
    print("Анализирую последние обновления...")
    print()
    
    updates = get_updates()
    
    if not updates:
        print("❌ Обновления не найдены")
        return
    
    # Группируем сообщения по темам
    topics = {}
    
    for update in updates:
        message = update.get("message")
        if not message:
            continue
        
        chat = message.get("chat", {})
        message_thread_id = message.get("message_thread_id")
        chat_id = str(chat.get("id", ""))
        
        # Только сообщения из нужного канала
        if chat_id != str(CHAT_ID):
            continue
        
        # Только сообщения из тем (не из общего чата)
        if not message_thread_id:
            continue
        
        if message_thread_id not in topics:
            topics[message_thread_id] = {
                "messages": [],
                "first_seen": message.get("date", 0),
                "last_seen": message.get("date", 0)
            }
        
        msg_info = {
            "text": message.get("text", ""),
            "date": message.get("date", 0),
            "from": message.get("from", {}).get("first_name", "Unknown")
        }
        
        topics[message_thread_id]["messages"].append(msg_info)
        
        # Обновляем last_seen
        if msg_info["date"] > topics[message_thread_id]["last_seen"]:
            topics[message_thread_id]["last_seen"] = msg_info["date"]
    
    if not topics:
        print("❌ Темы не найдены в обновлениях")
        print()
        print("💡 Чтобы найти темы:")
        print("1. Откройте канал 'POLY DAO TEST' в Telegram")
        print("2. Откройте любую тему (Low Size Alerts или High Size Alerts)")
        print("3. Отправьте боту любое сообщение в этой теме")
        print("4. Повторите для другой темы")
        print("5. Запустите этот скрипт снова")
        return
    
    print(f"✅ Найдено тем: {len(topics)}")
    print()
    print("=" * 70)
    print("📋 СПИСОК ВСЕХ ТЕМ И ИХ СООБЩЕНИЙ")
    print("=" * 70)
    print()
    
    # Сортируем по последнему сообщению (самые свежие первыми)
    sorted_topics = sorted(topics.items(), key=lambda x: x[1]["last_seen"], reverse=True)
    
    for topic_id, info in sorted_topics:
        messages = info["messages"]
        last_seen = format_date(info["last_seen"])
        
        print(f"📌 Topic ID: {topic_id}")
        print(f"   Последнее сообщение: {last_seen}")
        print(f"   Всего сообщений в теме: {len(messages)}")
        print()
        print("   Последние сообщения:")
        
        # Показываем последние 5 сообщений
        for msg in messages[-5:]:
            text = msg["text"][:60] + "..." if len(msg["text"]) > 60 else msg["text"]
            date = format_date(msg["date"])
            from_name = msg["from"]
            print(f"   • [{date}] {from_name}: {text}")
        
        print()
        print("-" * 70)
        print()
    
    print("=" * 70)
    print("💡 КАК ОПРЕДЕЛИТЬ, КАКАЯ ТЕМА КАКАЯ")
    print("=" * 70)
    print()
    print("Посмотрите на последние сообщения в каждой теме выше.")
    print("Если вы видите свои сообщения или знакомый контент,")
    print("вы сможете определить, какая тема 'Low Size Alerts',")
    print("а какая 'High Size Alerts'.")
    print()
    print("Если не можете определить:")
    print("1. Откройте тему 'Low Size Alerts' в Telegram")
    print("2. Отправьте боту сообщение: 'THIS IS LOW SIZE TOPIC'")
    print("3. Откройте тему 'High Size Alerts'")
    print("4. Отправьте боту сообщение: 'THIS IS HIGH SIZE TOPIC'")
    print("5. Запустите этот скрипт снова - вы увидите эти сообщения")
    print()
    print("=" * 70)
    print("📝 ПОСЛЕ ОПРЕДЕЛЕНИЯ ДОБАВЬТЕ В .env:")
    print("=" * 70)
    print()
    print("TELEGRAM_REPORTS_CHAT_ID=" + CHAT_ID)
    print("TELEGRAM_LOW_SIZE_TOPIC_ID=<ID_темы_Low_Size_Alerts>")
    print("TELEGRAM_HIGH_SIZE_TOPIC_ID=<ID_темы_High_Size_Alerts>")
    print()
    
    # Пытаемся автоматически определить по содержимому
    print("=" * 70)
    print("🤖 ПОПЫТКА АВТОМАТИЧЕСКОГО ОПРЕДЕЛЕНИЯ")
    print("=" * 70)
    print()
    
    low_size_candidates = []
    high_size_candidates = []
    
    for topic_id, info in topics.items():
        # Анализируем все сообщения в теме
        all_text = " ".join([msg["text"].upper() for msg in info["messages"]])
        
        low_score = 0
        high_score = 0
        
        if "LOW" in all_text:
            low_score += 2
        if "SMALL" in all_text:
            low_score += 1
        if "HIGH" in all_text:
            high_score += 2
        if "LARGE" in all_text:
            high_score += 1
        
        if low_score > 0:
            low_size_candidates.append((topic_id, low_score))
        if high_score > 0:
            high_size_candidates.append((topic_id, high_score))
    
    if low_size_candidates:
        low_size_candidates.sort(key=lambda x: x[1], reverse=True)
        print(f"✅ Возможно 'Low Size Alerts': Topic ID {low_size_candidates[0][0]}")
        print(f"   (найдено упоминаний 'low' или 'small' в сообщениях)")
    else:
        print("❓ Не удалось определить 'Low Size Alerts' автоматически")
    
    if high_size_candidates:
        high_size_candidates.sort(key=lambda x: x[1], reverse=True)
        print(f"✅ Возможно 'High Size Alerts': Topic ID {high_size_candidates[0][0]}")
        print(f"   (найдено упоминаний 'high' или 'large' в сообщениях)")
    else:
        print("❓ Не удалось определить 'High Size Alerts' автоматически")
    
    print()
    print("⚠️  Это только предположение! Проверьте визуально по сообщениям выше.")

if __name__ == "__main__":
    main()

