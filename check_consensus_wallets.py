#!/usr/bin/env python3
"""
Check why wallets from consensus are not tracked
"""

from db import PolymarketDB

db = PolymarketDB()

# Проверяю кошельки из консенсуса
wallets_to_check = [
    "0xb744f56635b537e859152d14b022af5afe485210",
    "0x3657862e57070b82a289b5887ec943a7c2166d14",
    "0xd38b71f3e8ed1af7198b5a7da2fdf239b51b5e9c"
]

print("Проверяю кошельки из консенсуса:")
print()

for wallet in wallets_to_check:
    wallet_lower = wallet.lower()
    wallet_data = db.get_wallet(wallet_lower)
    
    if wallet_data:
        print(f"{wallet[:20]}...:")
        print(f"   В базе: ДА")
        print(f"   Trades: {wallet_data.get('traded_total')}")
        print(f"   Win Rate: {wallet_data.get('win_rate', 0)*100:.1f}%")
        print(f"   Daily Freq: {wallet_data.get('daily_trading_frequency')}")
        print(f"   Last Trade: {wallet_data.get('last_trade_at')}")
        
        # Проверяю критерии
        trades = wallet_data.get("traded_total", 0)
        win_rate = wallet_data.get("win_rate", 0)
        daily_freq = wallet_data.get("daily_trading_frequency")
        last_trade = wallet_data.get("last_trade_at")
        
        meets_criteria = True
        reasons = []
        
        if trades < 6:
            meets_criteria = False
            reasons.append(f"trades < 6 ({trades})")
        if win_rate < 0.75:
            meets_criteria = False
            reasons.append(f"win_rate < 75% ({win_rate*100:.1f}%)")
        if daily_freq and daily_freq > 20.0:
            meets_criteria = False
            reasons.append(f"daily_freq > 20 ({daily_freq})")
        if not last_trade:
            meets_criteria = False
            reasons.append("no last_trade_at")
        
        if meets_criteria:
            print(f"   ✅ Соответствует критериям")
        else:
            reason_str = ", ".join(reasons)
            print(f"   ❌ НЕ соответствует: {reason_str}")
    else:
        print(f"{wallet[:20]}...:")
        print(f"   В базе: НЕТ")
    print()

# Проверяю, входят ли они в список отслеживаемых
tracked = db.get_tracked_wallets(
    min_trades=6, max_trades=1000, 
    min_win_rate=0.75, max_win_rate=1.0, 
    max_daily_freq=20.0, limit=2000
)

print(f"\nВсего отслеживаемых: {len(tracked)}")
print("\nПроверяю, входят ли кошельки из консенсуса в список отслеживаемых:")
for wallet in wallets_to_check:
    wallet_lower = wallet.lower()
    if wallet_lower in tracked:
        idx = tracked.index(wallet_lower)
        print(f"   ✅ {wallet[:20]}... | Позиция {idx+1}")
    else:
        print(f"   ❌ {wallet[:20]}... | НЕ в списке")

