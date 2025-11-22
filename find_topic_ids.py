#!/usr/bin/env python3
"""
Скрипт для поиска ID топиков в канале PolyDAO TEST
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = "-1003396499359"  # PolyDAO TEST

if not BOT_TOKEN:
    print("❌ TELEGRAM_BOT_TOKEN не найден в .env")
    exit(1)

def get_updates():
    """Получить последние обновления"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"offset": -200, "limit": 200}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("ok"):
            return data.get("result", [])
        return []
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return []

def main():
    print("="*70)
    print("ПОИСК ID ТОПИКОВ ДЛЯ КАНАЛА PolyDAO TEST")
    print("="*70)
    print()
    
    updates = get_updates()
    
    if not updates:
        print("❌ Обновления не найдены")
        print()
        print("💡 Инструкция:")
        print("1. Откройте канал 'PolyDAO TEST' в Telegram")
        print("2. Откройте каждый топик и отправьте боту сообщение:")
        print("   - General: отправьте 'GENERAL'")
        print("   - A-List Alerts: отправьте 'A-LIST'")
        print("   - Low Size Alerts: отправьте 'LOW SIZE'")
        print("   - High Size Alerts: отправьте 'HIGH SIZE'")
        print("3. Затем запустите этот скрипт снова")
        return
    
    print(f"✅ Найдено обновлений: {len(updates)}")
    print()
    
    topics = {}
    
    for update in updates:
        msg = update.get("message")
        if not msg:
            continue
        
        chat_id = str(msg["chat"]["id"])
        if chat_id != CHAT_ID:
            continue
        
        topic_id = msg.get("message_thread_id")
        text = msg.get("text", "").upper()
        
        if topic_id:
            if topic_id not in topics:
                topics[topic_id] = {
                    "messages": [],
                    "first_text": text[:50]
                }
            topics[topic_id]["messages"].append(text[:50])
    
    if not topics:
        print("❌ Топики не найдены в канале PolyDAO TEST")
        print()
        print("💡 Убедитесь, что:")
        print("   1. Вы отправили сообщения в топики (не в общий чат)")
        print("   2. Бот является администратором канала")
        print("   3. Канал является форум-группой (Topics enabled)")
        return
    
    print("="*70)
    print("📋 НАЙДЕННЫЕ ТОПИКИ:")
    print("="*70)
    print()
    
    topic_mapping = {}
    
    for topic_id, info in topics.items():
        msgs = info["messages"]
        first_text = info["first_text"]
        
        print(f"Topic ID: {topic_id}")
        print(f"  Сообщений: {len(msgs)}")
        print(f"  Примеры: {', '.join(msgs[:3])}")
        print()
        
        # Попробуем определить топик по содержимому
        all_text = " ".join(msgs).upper()
        if "A-LIST" in all_text or "ALIST" in all_text:
            topic_mapping["A_LIST"] = topic_id
        elif "LOW" in all_text or "LOW SIZE" in all_text:
            topic_mapping["LOW_SIZE"] = topic_id
        elif "HIGH" in all_text or "HIGH SIZE" in all_text:
            topic_mapping["HIGH_SIZE"] = topic_id
        elif "GENERAL" in all_text:
            topic_mapping["GENERAL"] = topic_id
    
    print("="*70)
    print("📝 РЕКОМЕНДУЕМЫЕ НАСТРОЙКИ ДЛЯ .env:")
    print("="*70)
    print()
    
    print(f"TELEGRAM_REPORTS_CHAT_ID={CHAT_ID}")
    print()
    
    if "LOW_SIZE" in topic_mapping:
        print(f"TELEGRAM_LOW_SIZE_TOPIC_ID={topic_mapping['LOW_SIZE']}")
    else:
        print("# TELEGRAM_LOW_SIZE_TOPIC_ID=<найти вручную>")
    
    if "HIGH_SIZE" in topic_mapping:
        print(f"TELEGRAM_HIGH_SIZE_TOPIC_ID={topic_mapping['HIGH_SIZE']}")
    else:
        print("# TELEGRAM_HIGH_SIZE_TOPIC_ID=<найти вручную>")
    
    if "A_LIST" in topic_mapping:
        print(f"TELEGRAM_A_LIST_TOPIC_ID={topic_mapping['A_LIST']}")
    else:
        print("# TELEGRAM_A_LIST_TOPIC_ID=<найти вручную>")
    
    print()
    print("💡 Если топики не определены автоматически:")
    print("   Отправьте в каждый топик сообщение с его названием:")
    print("   - 'LOW SIZE' в Low Size Alerts")
    print("   - 'HIGH SIZE' в High Size Alerts")
    print("   - 'A-LIST' в A-List Alerts")
    print("   Затем запустите скрипт снова")

if __name__ == "__main__":
    main()

