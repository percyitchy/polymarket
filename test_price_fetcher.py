#!/usr/bin/env python3
"""
Тестовый скрипт для демонстрации работы price_fetcher
"""

import logging
from price_fetcher import get_current_price, condition_id_to_token_id

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def test_price_fetcher():
    """Тестирование функции получения цены"""
    
    # Примеры из реальных данных (закрытые рынки)
    test_cases = [
        {
            "condition_id": "0x8404e511c4018ce709291c768824b49651d8713c8abdab85b19b7ee82a09d0d",
            "outcome_index": 1,
            "description": "LoL: T1 vs KT Rolster (BO5) - закрытый рынок"
        },
        {
            "condition_id": "0xa201124f1421c39673f834dc55f82560d3b7734772254f9e72fcb35fe441d41f",
            "outcome_index": 0,
            "description": "Will T1 win LoL Worlds 2025? - закрытый рынок"
        }
    ]
    
    print("=" * 80)
    print("ТЕСТИРОВАНИЕ МНОГОСТУПЕНЧАТОГО FALLBACK ДЛЯ ПОЛУЧЕНИЯ ЦЕНЫ")
    print("=" * 80)
    print()
    
    for i, test_case in enumerate(test_cases, 1):
        condition_id = test_case["condition_id"]
        outcome_index = test_case["outcome_index"]
        description = test_case["description"]
        
        print(f"Тест {i}: {description}")
        print(f"  condition_id: {condition_id[:30]}...")
        print(f"  outcome_index: {outcome_index}")
        
        # Конвертируем в token_id
        token_id = condition_id_to_token_id(condition_id, outcome_index)
        print(f"  token_id: {token_id[:50]}...")
        print()
        
        # Пробуем получить цену
        print("  Попытка получения цены...")
        try:
            price = get_current_price(
                condition_id=condition_id,
                outcome_index=outcome_index
            )
            
            if price is not None:
                print(f"  ✅ Цена получена: {price:.6f}")
            else:
                print(f"  ❌ Цена недоступна (все источники исчерпаны)")
        except Exception as e:
            print(f"  ❌ Ошибка: {type(e).__name__}: {e}")
        
        print()
        print("-" * 80)
        print()
    
    print("=" * 80)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 80)
    print()
    print("Примечания:")
    print("  - Если все источники вернули None, это нормально для закрытых рынков")
    print("  - Проверьте логи для детальной информации о каждом источнике")
    print("  - Убедитесь, что API ключи настроены в .env (если доступны)")

if __name__ == "__main__":
    test_price_fetcher()

