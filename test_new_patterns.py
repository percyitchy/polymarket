#!/usr/bin/env python3
"""Test new classification patterns"""

from market_utils import classify_market

print('=' * 100)
print('ТЕСТИРОВАНИЕ НОВЫХ УЛУЧШЕНИЙ')
print('=' * 100)

tests = [
    # Crypto "up or down" паттерны
    ('solana up or down on november 5?', 'crypto/Altcoins'),
    ('bitcoin up or down on november 5?', 'crypto/BTC'),
    ('ethereum up or down on november 14?', 'crypto/Altcoins'),
    ('ethereum up or down - october 10, 2:30pm-2:45pm et', 'crypto/Altcoins'),
    
    # NBA команды
    ('kings vs. bulls', 'sports/NBA'),
    ('heat vs. lakers', 'sports/NBA'),
    ('76ers vs. wizards', 'sports/NBA'),
    ('raptors vs. spurs', 'sports/NBA'),
    
    # NHL команды
    ('capitals vs. stars', 'sports/NHL'),
    ('blackhawks vs. jets', 'sports/NHL'),
    ('bruins vs. senators', 'sports/NHL'),
    
    # MLB команды
    ('dodgers vs. blue jays', 'sports/MLB'),
    
    # Soccer команды
    ('will brighton win on 2025-11-01?', 'sports/Soccer'),
    ('will arsenal fc win on 2025-11-04?', 'sports/Soccer'),
    ('will club atlético de madrid win on 2025-11-04?', 'sports/Soccer'),
    
    # Tennis турниры
    ('hellenic championship: novak djokovic vs lorenzo musetti', 'sports/Other'),
    ('wta finals, final stage: jessica pegula vs elena rybakina', 'sports/Other'),
    
    # Esports
    ('valorant tournament', 'sports/Other'),
]

passed = 0
failed = 0

for test_input, expected in tests:
    result = classify_market({}, None, test_input)
    status = '✅' if result == expected else '❌'
    print(f"{status} {test_input[:60]:<60} → {result:<20} (expected: {expected})")
    if result == expected:
        passed += 1
    else:
        failed += 1

print('=' * 100)
print(f'Passed: {passed}/{len(tests)}, Failed: {failed}/{len(tests)}')
print('=' * 100)

