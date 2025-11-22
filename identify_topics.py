#!/usr/bin/env python3
"""
Скрипт для определения, какой Topic ID соответствует какой теме
Отправляет тестовые сообщения в каждую тему с маркерами
"""
import os
import requests
import time
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

# Список найденных Topic ID из предыдущего запуска
TOPIC_IDS = [64, 3, 2]

def send_test_message(chat_id, topic_id, marker_text):
    """Отправить тестовое сообщение в тему с маркером"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "message_thread_id": topic_id,
        "text": f"🧪 ТЕСТ: {marker_text}\n\nTopic ID: {topic_id}"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("ok"):
            result = data.get("result", {})
            message_id = result.get("message_id")
            return True, message_id
        else:
            error_desc = data.get("description", "Unknown error")
            return False, error_desc
    except Exception as e:
        return False, str(e)

def main():
    print("=" * 60)
    print("🔍 ОПРЕДЕЛЕНИЕ ID ТЕМ")
    print("=" * 60)
    print()
    print(f"Канал: {CHAT_ID}")
    print(f"Найдено Topic ID: {TOPIC_IDS}")
    print()
    print("Сейчас отправлю тестовые сообщения в каждую тему...")
    print()
    
    results = {}
    
    # Отправляем сообщения в каждую тему с маркерами
    markers = {
        64: "🔵 МАРКЕР ДЛЯ TOPIC ID 64",
        3: "🟢 МАРКЕР ДЛЯ TOPIC ID 3",
        2: "🟡 МАРКЕР ДЛЯ TOPIC ID 2"
    }
    
    for topic_id in TOPIC_IDS:
        marker = markers.get(topic_id, f"📌 МАРКЕР ДЛЯ TOPIC ID {topic_id}")
        print(f"Отправляю сообщение в Topic ID {topic_id}...")
        success, result = send_test_message(CHAT_ID, topic_id, marker)
        
        if success:
            print(f"  ✅ Успешно отправлено! Message ID: {result}")
            results[topic_id] = "success"
        else:
            print(f"  ❌ Ошибка: {result}")
            results[topic_id] = f"error: {result}"
        
        time.sleep(1)  # Небольшая задержка между сообщениями
    
    print()
    print("=" * 60)
    print("📋 РЕЗУЛЬТАТЫ")
    print("=" * 60)
    print()
    print("Теперь откройте канал 'POLY DAO TEST' в Telegram и посмотрите:")
    print("в какой теме появилось сообщение с каким маркером.")
    print()
    print("Маркеры:")
    for topic_id, marker in markers.items():
        status = results.get(topic_id, "unknown")
        if status == "success":
            print(f"  Topic ID {topic_id}: {marker} ✅")
        else:
            print(f"  Topic ID {topic_id}: {marker} ❌ ({status})")
    print()
    print("=" * 60)
    print("📝 ПОСЛЕ ОПРЕДЕЛЕНИЯ")
    print("=" * 60)
    print()
    print("Когда определите, какая тема какая, добавьте в .env:")
    print()
    print("# Пример (замените на правильные ID):")
    print("TELEGRAM_LOW_SIZE_TOPIC_ID=2   # ID темы 'Low Size Alerts'")
    print("TELEGRAM_HIGH_SIZE_TOPIC_ID=3  # ID темы 'High Size Alerts'")
    print()
    print("Если не уверены, какой ID какой теме:")
    print("1. Откройте канал в Telegram")
    print("2. Найдите сообщение с маркером в теме 'Low Size Alerts'")
    print("3. Запомните Topic ID из этого сообщения")
    print("4. Повторите для 'High Size Alerts'")

if __name__ == "__main__":
    main()

