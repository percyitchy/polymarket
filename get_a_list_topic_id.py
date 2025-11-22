#!/usr/bin/env python3
"""
Получение Topic ID для A-list Alerts из последних сообщений в Telegram канале
"""

import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def get_updates(bot_token, offset=None, limit=100):
    """Получить обновления от Telegram Bot API"""
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    params = {"limit": limit}
    if offset:
        params["offset"] = offset
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Ошибка при получении обновлений: {e}")
        return None

def get_chat_messages(bot_token, chat_id, limit=10):
    """Получить последние сообщения из канала через getUpdates"""
    print(f"🔍 Поиск сообщений в чате {chat_id}...")
    
    updates = get_updates(bot_token, limit=100)
    if not updates or not updates.get("ok"):
        print("❌ Не удалось получить обновления")
        return []
    
    messages = []
    for update in updates.get("result", []):
        if "message" in update:
            msg = update["message"]
            msg_chat_id = str(msg.get("chat", {}).get("id", ""))
            
            # Проверяем chat_id (может быть строкой или числом)
            if msg_chat_id == str(chat_id) or msg_chat_id == chat_id:
                message_thread_id = msg.get("message_thread_id")
                if message_thread_id:
                    messages.append({
                        "message_id": msg.get("message_id"),
                        "message_thread_id": message_thread_id,
                        "text": msg.get("text", "")[:100],
                        "date": msg.get("date", 0)
                    })
    
    # Сортируем по дате (новые первыми)
    messages.sort(key=lambda x: x["date"], reverse=True)
    return messages[:limit]

def main():
    print("=" * 80)
    print("🔍 ПОИСК TOPIC ID ДЛЯ A-LIST ALERTS")
    print("=" * 80)
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    reports_chat_id = os.getenv("TELEGRAM_REPORTS_CHAT_ID")
    
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN не установлен в .env")
        return
    
    if not reports_chat_id:
        print("❌ TELEGRAM_REPORTS_CHAT_ID не установлен в .env")
        return
    
    print(f"✅ Bot Token: {bot_token[:10]}...")
    print(f"✅ Chat ID: {reports_chat_id}")
    print()
    
    # Получаем последние сообщения
    print("📥 Получение последних сообщений из канала...")
    messages = get_chat_messages(bot_token, reports_chat_id, limit=20)
    
    if not messages:
        print("⚠️  Не найдено сообщений с topic_id в последних обновлениях")
        print()
        print("💡 Альтернативный способ:")
        print("   1. Используйте @RawDataBot в Telegram")
        print("   2. Перешлите одно из ваших сообщений в A-list топик боту")
        print("   3. В ответе найдите поле 'message_thread_id' - это и есть Topic ID")
        return
    
    print(f"✅ Найдено {len(messages)} сообщений с topic_id")
    print()
    
    # Группируем по topic_id
    topics = {}
    for msg in messages:
        topic_id = msg["message_thread_id"]
        if topic_id not in topics:
            topics[topic_id] = {
                "count": 0,
                "last_seen": msg["date"],
                "sample_text": msg["text"]
            }
        topics[topic_id]["count"] += 1
        if msg["date"] > topics[topic_id]["last_seen"]:
            topics[topic_id]["last_seen"] = msg["date"]
            topics[topic_id]["sample_text"] = msg["text"]
    
    # Сортируем по количеству сообщений и последнему времени
    sorted_topics = sorted(
        topics.items(),
        key=lambda x: (x[1]["count"], x[1]["last_seen"]),
        reverse=True
    )
    
    print("📋 Найденные Topic ID:")
    print()
    
    for topic_id, info in sorted_topics:
        print(f"📌 Topic ID: {topic_id}")
        print(f"   Сообщений: {info['count']}")
        print(f"   Пример текста: {info['sample_text'][:60]}...")
        print()
    
    # Предлагаем наиболее вероятный вариант
    if sorted_topics:
        most_likely_id = sorted_topics[0][0]
        print("=" * 80)
        print("💡 РЕКОМЕНДУЕМЫЙ TOPIC ID:")
        print(f"   TELEGRAM_A_LIST_TOPIC_ID={most_likely_id}")
        print()
        print("📝 Добавьте эту строку в ваш .env файл")
        print("=" * 80)
        
        # Предлагаем обновить .env
        update_env = input("\nОбновить .env файл автоматически? (y/n): ").strip().lower()
        if update_env == 'y':
            update_env_file(most_likely_id)
    else:
        print("⚠️  Не удалось определить Topic ID автоматически")
        print()
        print("💡 Используйте @RawDataBot:")
        print("   1. Перешлите сообщение из A-list топика боту")
        print("   2. Найдите 'message_thread_id' в ответе")
        print("   3. Добавьте в .env: TELEGRAM_A_LIST_TOPIC_ID=<найденный_id>")

def update_env_file(topic_id):
    """Обновить .env файл с новым Topic ID"""
    env_path = ".env"
    
    if not os.path.exists(env_path):
        print(f"❌ Файл {env_path} не найден")
        return
    
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        updated = False
        new_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('TELEGRAM_A_LIST_TOPIC_ID='):
                new_lines.append(f"TELEGRAM_A_LIST_TOPIC_ID={topic_id}\n")
                updated = True
            else:
                new_lines.append(line)
        
        if not updated:
            # Добавляем в конец файла
            new_lines.append(f"\n# A-list Alerts Topic ID\n")
            new_lines.append(f"TELEGRAM_A_LIST_TOPIC_ID={topic_id}\n")
        
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        print(f"✅ Файл {env_path} обновлён")
        print(f"   TELEGRAM_A_LIST_TOPIC_ID={topic_id}")
    except Exception as e:
        print(f"❌ Ошибка при обновлении .env: {e}")

if __name__ == "__main__":
    main()

