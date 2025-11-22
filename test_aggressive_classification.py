#!/usr/bin/env python3
"""
Тестирование агрессивной классификации для снижения Unknown до 20%
"""

import os
import sys
import logging
from dotenv import load_dotenv
from market_utils import classify_market

load_dotenv()

logging.basicConfig(
    level=logging.WARNING,  # Suppress debug logs
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_classification():
    """Тестировать классификацию на различных примерах"""
    
    print("=" * 80)
    print("🧪 ТЕСТИРОВАНИЕ АГРЕССИВНОЙ КЛАССИФИКАЦИИ")
    print("=" * 80)
    
    test_cases = [
        # Даты → macro/Events
        ({"category": ""}, None, "Will something happen on 2025-12-31?"),
        ({"category": ""}, None, "Deadline by end of December"),
        ({"category": ""}, None, "Event on January 15"),
        
        # Цены → macro/crypto
        ({"category": ""}, None, "Price above $100,000"),
        ({"category": ""}, None, "Will price exceed 5.5%?"),
        ({"category": ""}, None, "Bitcoin price above $100k"),
        
        # Короткий текст → ML
        ({"category": ""}, None, "bitcoin updown"),
        ({"category": ""}, None, "trump election"),
        ({"category": ""}, None, "lakers vs warriors"),
        
        # Пустые данные → эвристики
        ({"category": ""}, None, "win election"),
        ({"category": ""}, None, "price up"),
        ({"category": ""}, None, "game vs"),
        
        # event.category из API
        ({"category": "sports"}, None, "Some market"),
        ({"category": "politics"}, None, "Some market"),
        ({"category": "crypto"}, None, "Some market"),
    ]
    
    results = {
        "total": len(test_cases),
        "classified": 0,
        "unknown": 0,
        "categories": {}
    }
    
    print("\n📋 Результаты тестирования:")
    print()
    
    for i, (event, slug, question) in enumerate(test_cases, 1):
        category = classify_market(event, slug, question)
        
        if category == "other/Unknown":
            results["unknown"] += 1
            status = "❓"
        else:
            results["classified"] += 1
            status = "✅"
            results["categories"][category] = results["categories"].get(category, 0) + 1
        
        print(f"{status} {i}. {question[:60]}")
        print(f"   → {category}")
        print()
    
    print("=" * 80)
    print("📊 Статистика:")
    print(f"   Всего тестов: {results['total']}")
    print(f"   Классифицировано: {results['classified']} ({results['classified']/results['total']*100:.1f}%)")
    print(f"   Unknown: {results['unknown']} ({results['unknown']/results['total']*100:.1f}%)")
    print()
    
    if results["categories"]:
        print("📋 Распределение по категориям:")
        for cat, count in sorted(results["categories"].items(), key=lambda x: x[1], reverse=True):
            print(f"   {cat:<25} {count:>3}")
    
    print("\n" + "=" * 80)
    
    return results

if __name__ == "__main__":
    results = test_classification()
    
    if results["unknown"] / results["total"] < 0.2:
        print("✅ Цель достигнута: Unknown < 20%!")
    else:
        print(f"⚠️  Unknown = {results['unknown']/results['total']*100:.1f}%, нужно снизить до 20%")

