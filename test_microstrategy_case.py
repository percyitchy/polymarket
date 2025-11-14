#!/usr/bin/env python3
"""
Тестовый скрипт для отладки конкретного кейса MicroStrategy
"""

import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from price_fetcher import get_current_price
from notify import TelegramNotifier
from polymarket_notifier import PolymarketNotifier

# Данные из примера
condition_id = "0x312342f1015274a3f9b1b691238266c14f008ff499f03701c2978fec441b50ee"
outcome_index = 1
wallet_prices = {
    "0x382c...a0d7": 0.938,
    "0xe103...59fd": 0.950
}

print("=" * 80)
print("Тест кейса MicroStrategy")
print("=" * 80)
print(f"Condition ID: {condition_id}")
print(f"Outcome Index: {outcome_index}")
print(f"Wallet Prices: {wallet_prices}")
print()

# Тест 1: Получение цены через price_fetcher
print("Тест 1: Получение цены через price_fetcher.get_current_price()")
print("-" * 80)
price = get_current_price(
    condition_id=condition_id, 
    outcome_index=outcome_index, 
    wallet_prices=wallet_prices
)
print(f"Результат: {price}")
print()

# Тест 2: Проверка активности рынка
print("Тест 2: Проверка активности рынка")
print("-" * 80)
try:
    notifier = PolymarketNotifier()
    is_active = notifier.is_market_active(condition_id, outcome_index)
    print(f"is_market_active: {is_active}")
    
    # Получить детальную информацию о рынке
    market_info = notifier.get_market_info(condition_id)
    print(f"Market info: {market_info}")
except Exception as e:
    print(f"Ошибка: {e}")
    import traceback
    traceback.print_exc()
print()

# Тест 3: Симуляция получения цены через _get_current_price
print("Тест 3: Симуляция получения цены через _get_current_price")
print("-" * 80)
try:
    notifier = PolymarketNotifier()
    current_price = notifier._get_current_price(
        condition_id=condition_id,
        outcome_index=outcome_index,
        wallet_prices=wallet_prices
    )
    print(f"current_price из _get_current_price: {current_price}")
except Exception as e:
    print(f"Ошибка: {e}")
    import traceback
    traceback.print_exc()
print()

# Тест 4: Проверка через notify.py
print("Тест 4: Проверка через notify.py _get_current_price")
print("-" * 80)
try:
    telegram_notifier = TelegramNotifier()
    current_price = telegram_notifier._get_current_price(
        condition_id=condition_id,
        outcome_index=outcome_index,
        wallet_prices=wallet_prices
    )
    print(f"current_price из notify._get_current_price: {current_price}")
except Exception as e:
    print(f"Ошибка: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)

