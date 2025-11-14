#!/usr/bin/env python3
"""
Check for potential consensus cases in the last 6 hours
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import PolymarketDB
from datetime import datetime, timezone, timedelta
import requests
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

def check_recent_consensus():
    """Check if there were any cases where 2+ wallets traded the same market"""
    db = PolymarketDB()
    six_hours_ago = datetime.now(timezone.utc) - timedelta(hours=6)
    
    # Get tracked wallets
    tracked_wallets = db.get_tracked_wallets(
        min_trades=6, max_trades=1000, 
        min_win_rate=0.75, max_win_rate=1.0, 
        max_daily_freq=20.0, limit=2000
    )
    
    print(f"📊 Отслеживаемых кошельков: {len(tracked_wallets)}")
    print(f"⏰ Проверяю сделки за последние 6 часов...")
    print()
    
    # Check recent trades from tracked wallets
    market_trades = defaultdict(list)  # condition_id -> list of (wallet, timestamp, outcome)
    
    checked_count = 0
    found_trades = 0
    
    for wallet in tracked_wallets[:100]:  # Check first 100 wallets
        try:
            url = "https://data-api.polymarket.com/trades"
            response = requests.get(url, params={"user": wallet, "limit": 10}, timeout=10)
            
            if response.ok:
                trades = response.json()
                for trade in trades:
                    timestamp_val = trade.get("timestamp")
                    if timestamp_val:
                        # Handle both string and numeric timestamps
                        if isinstance(timestamp_val, str):
                            dt = datetime.fromisoformat(timestamp_val.replace("Z", "+00:00"))
                        elif isinstance(timestamp_val, (int, float)):
                            dt = datetime.fromtimestamp(timestamp_val / 1000 if timestamp_val > 1e10 else timestamp_val, tz=timezone.utc)
                        else:
                            continue
                        
                        if dt >= six_hours_ago:
                            condition_id = trade.get("conditionId")
                            outcome_index = trade.get("outcomeIndex")
                            side = trade.get("side", "BUY")
                            
                            if condition_id is not None and outcome_index is not None:
                                market_trades[condition_id].append({
                                    "wallet": wallet,
                                    "timestamp": dt,
                                    "outcome_index": outcome_index,
                                    "side": side,
                                    "price": trade.get("price", 0),
                                    "usd_amount": trade.get("usdAmount", 0)
                                })
                                found_trades += 1
            
            checked_count += 1
            if checked_count % 20 == 0:
                print(f"   Проверено {checked_count}/{min(100, len(tracked_wallets))} кошельков...")
            
        except Exception as e:
            print(f"   ⚠️  Ошибка для {wallet[:20]}...: {e}")
    
    print()
    print(f"✅ Проверено кошельков: {checked_count}")
    print(f"📈 Найдено сделок за 6 часов: {found_trades}")
    print()
    
    # Find markets with 2+ wallets
    consensus_candidates = []
    for condition_id, trades in market_trades.items():
        # Group by outcome_index and side
        by_outcome_side = defaultdict(list)
        for trade in trades:
            key = (trade["outcome_index"], trade["side"])
            by_outcome_side[key].append(trade)
        
        for (outcome_index, side), trade_list in by_outcome_side.items():
            if len(trade_list) >= 2:
                # Sort by timestamp
                trade_list.sort(key=lambda x: x["timestamp"])
                
                # Check time window (15 minutes)
                first_time = trade_list[0]["timestamp"]
                last_time = trade_list[-1]["timestamp"]
                window_minutes = (last_time - first_time).total_seconds() / 60
                
                if window_minutes <= 15:
                    wallets_involved = [t["wallet"] for t in trade_list]
                    consensus_candidates.append({
                        "condition_id": condition_id,
                        "outcome_index": outcome_index,
                        "side": side,
                        "wallet_count": len(trade_list),
                        "window_minutes": window_minutes,
                        "wallets": wallets_involved,
                        "first_trade": first_time,
                        "last_trade": last_time,
                        "prices": [t["price"] for t in trade_list]
                    })
    
    if consensus_candidates:
        print(f"🎯 Найдено потенциальных консенсусов: {len(consensus_candidates)}")
        print()
        
        for i, candidate in enumerate(consensus_candidates[:10], 1):
            print(f"{i}. Маркет: {candidate['condition_id'][:30]}...")
            print(f"   Исход: {candidate['outcome_index']} | Сторона: {candidate['side']}")
            print(f"   Кошельков: {candidate['wallet_count']}")
            print(f"   Окно: {candidate['window_minutes']:.1f} минут")
            print(f"   Время: {candidate['first_trade'].strftime('%Y-%m-%d %H:%M:%S')} - {candidate['last_trade'].strftime('%H:%M:%S')}")
            print(f"   Цены: {[f'${p:.3f}' for p in candidate['prices']]}")
            print(f"   Кошельки: {', '.join([w[:20] + '...' for w in candidate['wallets']])}")
            print()
    else:
        print("❌ Не найдено случаев консенсуса (2+ кошелька на одном маркете)")
        print()
        print("Возможные причины:")
        print("   1. Отслеживаемые кошельки не торговали за последние 6 часов")
        print("   2. Сделки были на разных маркетах")
        print("   3. Сделки были вне временного окна (15 минут)")
        print("   4. Сделки были в разных направлениях (BUY vs SELL)")

if __name__ == "__main__":
    check_recent_consensus()

