#!/usr/bin/env python3
"""
Проверка конфигурации MIN_TOTAL_POSITION_USD
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("🔍 ПРОВЕРКА MIN_TOTAL_POSITION_USD")
print("=" * 70)
print()

min_position_usd = os.getenv("MIN_TOTAL_POSITION_USD")
if min_position_usd:
    try:
        min_position_usd_float = float(min_position_usd.split('#')[0].strip())
    except ValueError:
        print(f"❌ ОШИБКА: Неверное значение MIN_TOTAL_POSITION_USD='{min_position_usd}'")
        min_position_usd_float = None
else:
    min_position_usd_float = 2000.0  # Значение по умолчанию из кода
    print("⚠️  MIN_TOTAL_POSITION_USD не установлен в .env, используется значение по умолчанию")

print(f"Текущее значение: ${min_position_usd_float:.2f}")
print()

if min_position_usd_float is not None:
    if min_position_usd_float < 2000.0:
        print("❌ ПРОБЛЕМА: Значение меньше $2000!")
        print(f"   Текущее: ${min_position_usd_float:.2f}")
        print(f"   Требуется: $2000.00")
        print()
        print("📝 РЕШЕНИЕ:")
        print("   Обновите .env файл:")
        print("   MIN_TOTAL_POSITION_USD=2000")
        print()
        print("   Затем перезапустите сервис:")
        print("   sudo systemctl restart polymarket-bot")
    elif min_position_usd_float == 2000.0:
        print("✅ Значение установлено правильно: $2000.00")
        print()
        print("⚠️  Если сигналы всё ещё проходят с позицией < $2000:")
        print("   1. Проверьте логи: sudo journalctl -u polymarket-bot -f")
        print("   2. Убедитесь, что сервис перезапущен после изменения .env")
        print("   3. Проверьте, что используется правильный .env файл")
    else:
        print(f"✅ Значение установлено: ${min_position_usd_float:.2f}")
        print("   (больше требуемого минимума $2000)")

print()
print("=" * 70)
print("📋 ИНСТРУКЦИЯ ДЛЯ СЕРВЕРА")
print("=" * 70)
print()
print("1. Проверьте текущее значение на сервере:")
print("   grep MIN_TOTAL_POSITION_USD /opt/polymarket-bot/.env")
print()
print("2. Если значение меньше 2000, обновите:")
print("   nano /opt/polymarket-bot/.env")
print("   # Найдите строку MIN_TOTAL_POSITION_USD и установите:")
print("   MIN_TOTAL_POSITION_USD=2000")
print()
print("3. Перезапустите сервис:")
print("   sudo systemctl restart polymarket-bot")
print()
print("4. Проверьте логи для подтверждения:")
print("   sudo journalctl -u polymarket-bot -n 50 | grep MIN_TOTAL_POSITION_USD")
print()

