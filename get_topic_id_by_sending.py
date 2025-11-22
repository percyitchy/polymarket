#!/usr/bin/env python3
"""
Получение Topic ID через отправку тестовых сообщений
Бот отправляет сообщения в каждую тему и получает их ID из ответа API
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
    exit(1)

# Список возможных Topic ID из предыдущего анализа
POSSIBLE_TOPIC_IDS = [64, 3, 2]

def send_message_to_topic(chat_id, topic_id, text):
    """Отправить сообщение в тему и получить ответ API"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "message_thread_id": topic_id,
        "text": text
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("ok"):
            result = data.get("result", {})
            return True, result, None
        else:
            error_desc = data.get("description", "Unknown error")
            return False, None, error_desc
    except requests.exceptions.HTTPError as e:
        try:
            error_data = e.response.json()
            error_desc = error_data.get("description", str(e))
        except:
            error_desc = str(e)
        return False, None, error_desc
    except Exception as e:
        return False, None, str(e)

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
        return None
    except:
        return None

def main():
    print("=" * 70)
    print("🔍 ПОЛУЧЕНИЕ TOPIC ID ЧЕРЕЗ ОТПРАВКУ СООБЩЕНИЙ")
    print("=" * 70)
    print()
    print(f"Канал ID: {CHAT_ID}")
    print()
    
    # Проверяем информацию о чате
    chat_info = get_chat_info(CHAT_ID)
    if chat_info:
        chat_type = chat_info.get("type", "unknown")
        title = chat_info.get("title", "Unknown")
        print(f"✅ Канал найден: {title}")
        print(f"   Тип: {chat_type}")
        if chat_type != "supergroup":
            print("   ⚠️  Канал должен быть супергруппой для использования тем")
        print()
    
    print("Пробую отправить сообщения в возможные темы...")
    print()
    
    results = {}
    
    # Пробуем отправить в каждую возможную тему
    for topic_id in POSSIBLE_TOPIC_IDS:
        print(f"Пробую Topic ID {topic_id}...")
        success, result, error = send_message_to_topic(
            CHAT_ID, 
            topic_id, 
            f"🧪 Тест Topic ID {topic_id}"
        )
        
        if success:
            message_id = result.get("message_id") if result else None
            print(f"  ✅ Успешно! Сообщение отправлено (Message ID: {message_id})")
            results[topic_id] = {"status": "success", "message_id": message_id}
        else:
            print(f"  ❌ Ошибка: {error}")
            results[topic_id] = {"status": "error", "error": error}
        
        time.sleep(1)  # Небольшая задержка
    
    print()
    print("=" * 70)
    print("📋 РЕЗУЛЬТАТЫ")
    print("=" * 70)
    print()
    
    successful_topics = [tid for tid, info in results.items() if info.get("status") == "success"]
    
    if not successful_topics:
        print("❌ Не удалось отправить сообщения ни в одну тему")
        print()
        print("Возможные причины:")
        print("1. Topic ID неправильные")
        print("2. Бот не имеет прав отправлять в эти темы")
        print("3. Канал не является форум-группой")
        print()
        print("💡 Альтернативный способ:")
        print("1. Откройте Telegram")
        print("2. Откройте канал 'POLY DAO TEST'")
        print("3. Откройте тему 'Low Size Alerts'")
        print("4. Скопируйте ссылку на тему (если доступно)")
        print("5. Или используйте @RawDataBot для получения ID")
        return
    
    print(f"✅ Успешно отправлено в {len(successful_topics)} тем(ы):")
    for tid in successful_topics:
        print(f"   - Topic ID {tid}")
    
    print()
    print("=" * 70)
    print("📝 СЛЕДУЮЩИЕ ШАГИ")
    print("=" * 70)
    print()
    print("1. Откройте канал 'POLY DAO TEST' в Telegram")
    print("2. Найдите сообщения '🧪 Тест Topic ID X' в темах")
    print("3. Определите:")
    print("   - В какой теме 'Low Size Alerts' появилось сообщение?")
    print("   - В какой теме 'High Size Alerts' появилось сообщение?")
    print()
    
    if len(successful_topics) == 2:
        print("Найдены 2 рабочие темы! Определите вручную:")
        print()
        for tid in successful_topics:
            print(f"   Topic ID {tid} → ?")
        print()
        print("После определения добавьте в .env:")
        print(f"TELEGRAM_REPORTS_CHAT_ID={CHAT_ID}")
        print("TELEGRAM_LOW_SIZE_TOPIC_ID=<ID_темы_Low_Size_Alerts>")
        print("TELEGRAM_HIGH_SIZE_TOPIC_ID=<ID_темы_High_Size_Alerts>")
    elif len(successful_topics) == 1:
        print(f"Найдена 1 рабочая тема: Topic ID {successful_topics[0]}")
        print("Проверьте, какая это тема (Low или High Size Alerts)")
        print()
        print("Для второй темы попробуйте другие ID из списка:")
        failed_topics = [tid for tid in POSSIBLE_TOPIC_IDS if tid not in successful_topics]
        for tid in failed_topics:
            print(f"   - Topic ID {tid}")
    
    print()

if __name__ == "__main__":
    main()

