#!/usr/bin/env python3
"""
Альтернативный способ получения ID тем из Telegram форум-группы
Отправляет тестовые сообщения в каждую тему и показывает их ID
"""
import os
import requests
import json
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
    print("Укажите ID канала 'POLY DAO TEST' в переменной TELEGRAM_REPORTS_CHAT_ID")
    exit(1)

def send_test_message(chat_id, topic_id=None):
    """Отправить тестовое сообщение в тему"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": f"🧪 Тестовое сообщение для определения ID темы"
    }
    if topic_id:
        payload["message_thread_id"] = topic_id
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("ok"):
            return data.get("result", {})
        else:
            print(f"❌ Ошибка API: {data.get('description', 'Unknown error')}")
            return None
    except Exception as e:
        print(f"❌ Ошибка при отправке: {e}")
        return None

def get_chat_info(chat_id):
    """Получить информацию о чате"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChat"
    params = {"chat_id": chat_id}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("ok"):
            return data.get("result", {})
        else:
            print(f"❌ Ошибка API: {data.get('description', 'Unknown error')}")
            return None
    except Exception as e:
        print(f"❌ Ошибка при запросе: {e}")
        return None

def main():
    print(f"🔍 Проверяю канал {CHAT_ID}...")
    print()
    
    # Проверяем тип чата
    chat_info = get_chat_info(CHAT_ID)
    if chat_info:
        chat_type = chat_info.get("type", "unknown")
        title = chat_info.get("title", "Unknown")
        print(f"✅ Канал найден: {title}")
        print(f"   Тип: {chat_type}")
        
        if chat_type != "supergroup":
            print("⚠️  Канал должен быть супергруппой (supergroup) для использования тем")
        print()
    
    print("=" * 60)
    print("📋 ИНСТРУКЦИЯ ПО ПОЛУЧЕНИЮ ID ТЕМ:")
    print("=" * 60)
    print()
    print("Способ 1: Через отправку сообщения в тему")
    print("1. Откройте канал 'POLY DAO TEST' в Telegram")
    print("2. Откройте тему 'Low Size Alerts'")
    print("3. Отправьте боту любое сообщение в этой теме")
    print("4. Затем запустите скрипт get_topic_ids_from_updates.py")
    print()
    print("Способ 2: Вручную через @RawDataBot")
    print("1. Добавьте @RawDataBot в канал 'POLY DAO TEST'")
    print("2. Откройте тему 'Low Size Alerts'")
    print("3. Отправьте любое сообщение в теме")
    print("4. @RawDataBot покажет message_thread_id в ответе")
    print()
    print("Способ 3: Через веб-интерфейс Telegram")
    print("1. Откройте https://web.telegram.org")
    print("2. Откройте канал 'POLY DAO TEST'")
    print("3. Откройте тему и посмотрите в URL: .../topic/12345")
    print("   где 12345 - это ID темы")
    print()
    print("=" * 60)
    print("📝 После получения ID тем добавьте в .env:")
    print("=" * 60)
    print()
    print("TELEGRAM_LOW_SIZE_TOPIC_ID=<ID_темы_Low_Size_Alerts>")
    print("TELEGRAM_HIGH_SIZE_TOPIC_ID=<ID_темы_High_Size_Alerts>")
    print()
    print("=" * 60)
    print("🧪 ТЕСТОВАЯ ОТПРАВКА:")
    print("=" * 60)
    print()
    print("Хотите отправить тестовое сообщение в канал?")
    print("(Это поможет проверить, что бот может отправлять сообщения)")
    print()
    
    # Попробуем отправить тестовое сообщение без темы
    print("Отправляю тестовое сообщение в канал (без темы)...")
    result = send_test_message(CHAT_ID)
    if result:
        print("✅ Тестовое сообщение отправлено успешно!")
        print(f"   Message ID: {result.get('message_id')}")
        print()
        print("Теперь попробуйте отправить сообщение в тему 'Low Size Alerts'")
        print("и запустите get_topic_ids_from_updates.py для получения ID")
    else:
        print("❌ Не удалось отправить тестовое сообщение")
        print("   Проверьте, что бот является администратором канала")

if __name__ == "__main__":
    main()

