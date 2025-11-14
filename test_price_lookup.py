#!/usr/bin/env python3
"""
Тестовый скрипт для проверки получения цены для конкретного маркета
Используется для отладки проблемы с ценами в алертах
"""

import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from price_fetcher import get_current_price

# Тестовый кейс из примера пользователя
condition_id = "0x319a2f28b0de6794f3f951b7f4604d63caaeefe91a01659305189c3bc40a61be"
outcome_index = 0
wallet_prices = {
    "0x4762...dc1b": 0.760,
    "0xa117...a311": 0.750
}

print("=" * 80)
print("Тест получения цены для маркета Lakers vs. Hornets")
print("=" * 80)
print(f"Condition ID: {condition_id}")
print(f"Outcome Index: {outcome_index}")
print(f"Wallet Prices: {wallet_prices}")
print()

# Тест 1: Без wallet_prices
print("Тест 1: Получение цены БЕЗ wallet_prices fallback")
print("-" * 80)
price1 = get_current_price(condition_id=condition_id, outcome_index=outcome_index)
print(f"Результат: {price1}")
print()

# Тест 2: С wallet_prices
print("Тест 2: Получение цены С wallet_prices fallback")
print("-" * 80)
price2 = get_current_price(condition_id=condition_id, outcome_index=outcome_index, wallet_prices=wallet_prices)
print(f"Результат: {price2}")
print()

# Тест 3: Только wallet_prices (симуляция, когда все API недоступны)
print("Тест 3: Проверка wallet_prices fallback (если все API недоступны)")
print("-" * 80)
if wallet_prices:
    prices = [p for p in wallet_prices.values() if isinstance(p, (int, float)) and p > 0]
    if prices:
        avg_price = sum(prices) / len(prices)
        print(f"Средняя цена из wallet_prices: {avg_price:.6f} (из {len(prices)} кошельков)")
    else:
        print("Нет валидных цен в wallet_prices")
else:
    print("wallet_prices не предоставлен")

print()
print("=" * 80)
print("Итог:")
print(f"  Без wallet_prices: {price1}")
print(f"  С wallet_prices: {price2}")
print("=" * 80)

