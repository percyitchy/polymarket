#!/usr/bin/env python3
"""
Получение CHAT_ID нового канала "POLY DAO TEST"
"""
import os
import requests
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
        "offset": -100,
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
    print("=" * 70)
    print("🔍 ПОИСК CHAT_ID КАНАЛА 'POLY DAO TEST'")
    print("=" * 70)
    print()
    print("Инструкция:")
    print("1. Откройте канал 'POLY DAO TEST' в Telegram")
    print("2. Отправьте боту любое сообщение в канале (можно в общий чат или в любую тему)")
    print("3. Нажмите Enter после отправки...")
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
        print("Убедитесь, что вы отправили сообщение боту в канале")
        return
    
    # Ищем каналы с названием содержащим "POLY DAO" или "TEST"
    found_channels = {}
    
    for update in updates:
        message = update.get("message")
        if not message:
            continue
        
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        chat_title = chat.get("title", "")
        chat_type = chat.get("type", "")
        
        # Ищем супергруппы и каналы
        if chat_type in ["supergroup", "channel"]:
            # Проверяем название
            title_lower = chat_title.lower()
            if "poly dao" in title_lower or "test" in title_lower or "dao" in title_lower:
                if chat_id not in found_channels:
                    found_channels[chat_id] = {
                        "title": chat_title,
                        "type": chat_type,
                        "messages": []
                    }
                
                msg_text = message.get("text", "")[:50]
                found_channels[chat_id]["messages"].append(msg_text)
    
    if not found_channels:
        print("❌ Канал 'POLY DAO TEST' не найден в обновлениях")
        print()
        print("Найдены следующие каналы/группы:")
        all_chats = {}
        for update in updates:
            message = update.get("message")
            if message:
                chat = message.get("chat", {})
                chat_id = str(chat.get("id", ""))
                chat_title = chat.get("title", "")
                chat_type = chat.get("type", "")
                if chat_type in ["supergroup", "channel", "group"]:
                    if chat_id not in all_chats:
                        all_chats[chat_id] = {"title": chat_title, "type": chat_type}
        
        for chat_id, info in all_chats.items():
            print(f"  - {info['title']} (ID: {chat_id}, тип: {info['type']})")
        
        print()
        print("💡 Если канал 'POLY DAO TEST' есть в списке выше, используйте его ID")
        return
    
    print(f"✅ Найдено каналов: {len(found_channels)}")
    print()
    print("=" * 70)
    print("📋 НАЙДЕННЫЕ КАНАЛЫ")
    print("=" * 70)
    print()
    
    for chat_id, info in found_channels.items():
        print(f"📌 Название: {info['title']}")
        print(f"   CHAT_ID: {chat_id}")
        print(f"   Тип: {info['type']}")
        print(f"   Сообщений в обновлениях: {len(info['messages'])}")
        print()
    
    # Если найден один канал - предлагаем его
    if len(found_channels) == 1:
        chat_id = list(found_channels.keys())[0]
        title = found_channels[chat_id]["title"]
        print("=" * 70)
        print("✅ РЕКОМЕНДУЕМЫЙ CHAT_ID")
        print("=" * 70)
        print()
        print(f"TELEGRAM_REPORTS_CHAT_ID={chat_id}")
        print()
        print(f"Это канал: {title}")
        print()
        print("💡 Добавьте эту строку в .env файл")
        print("   Затем запустите скрипты для получения Topic ID")
    else:
        print("=" * 70)
        print("📝 ВЫБЕРИТЕ ПРАВИЛЬНЫЙ CHAT_ID")
        print("=" * 70)
        print()
        print("Найдено несколько каналов. Выберите правильный:")
        for i, (chat_id, info) in enumerate(found_channels.items(), 1):
            print(f"{i}. {info['title']} (ID: {chat_id})")
        print()
        print("Добавьте выбранный ID в .env:")
        print("TELEGRAM_REPORTS_CHAT_ID=<выбранный_ID>")

if __name__ == "__main__":
    main()

