#!/usr/bin/env python3
"""Test topic selection logic"""
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from notify import TelegramNotifier

load_dotenv()

notifier = TelegramNotifier()

print("=" * 60)
print("ТЕСТ ВЫБОРА ТЕМЫ")
print("=" * 60)
print()
print(f"low_size_topic_id: {notifier.low_size_topic_id}")
print(f"high_size_topic_id: {notifier.high_size_topic_id}")
print(f"size_threshold_usd: {notifier.size_threshold_usd}")
print()

# Test cases
test_cases = [
    (5000.0, "Low Size"),
    (10000.0, "High Size"),
    (15000.0, "High Size"),
    (1966.08, "Low Size"),  # Как в последнем сигнале
    (None, "Unknown Size"),
]

print("Тестирование логики выбора темы:")
print()

for total_usd, expected_category in test_cases:
    selected_topic_id = None
    size_category = None
    
    if isinstance(total_usd, (int, float)) and total_usd is not None:
        if total_usd < notifier.size_threshold_usd:
            selected_topic_id = notifier.low_size_topic_id
            size_category = "Low Size"
        else:
            selected_topic_id = notifier.high_size_topic_id
            size_category = "High Size"
    else:
        selected_topic_id = notifier.topic_id
        size_category = "Unknown Size"
    
    total_str = f"${total_usd:.2f}" if total_usd else "None"
    topic_str = f"Topic ID: {selected_topic_id}" if selected_topic_id else "Topic ID: None"
    
    status = "✅" if size_category == expected_category else "❌"
    print(f"{status} total_usd={total_str:>10} → {size_category:12} {topic_str}")

print()
print("=" * 60)

