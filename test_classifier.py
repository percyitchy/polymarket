#!/usr/bin/env python3
"""Test enhanced classifier"""

from market_utils import classify_market

tests = [
    ('buccaneers vs. seahawks', 'sports/NFL'),
    ('spread: patriots (-3.5)', 'sports/NFL'),
    ('nfl-tb-sea-2025-10-05', 'sports/NFL'),
    ('will tesla beat quarterly earnings?', 'macro/Fed'),
    ('ethereum up or down - november 3', 'crypto/Altcoins'),
    ('bitcoin up or down', 'crypto/BTC'),
    ('lol t1 vs kt rolster', 'sports/Other'),
    ('atp tennis', 'sports/Other'),
    ('masters golf', 'sports/Other'),
    ('epl manchester', 'sports/Soccer'),
    ('will biden win 2024 election?', 'politics/US'),
]

print('=' * 80)
print('FINAL TEST SUITE')
print('=' * 80)

passed = 0
failed = 0

for test_input, expected in tests:
    result = classify_market({}, None, test_input)
    status = '✅' if result == expected else '❌'
    print(f"{status} {test_input[:50]:<50} → {result:<20} (expected: {expected})")
    if result == expected:
        passed += 1
    else:
        failed += 1

print('=' * 80)
print(f'Passed: {passed}/{len(tests)}, Failed: {failed}/{len(tests)}')
print('=' * 80)

