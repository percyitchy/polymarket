#!/usr/bin/env python3
"""
Тест одного маркета: вызывает price_fetcher.get_current_price для одного выбранного рынка
и печатает компактный результат с источником цены (gamma/clob/trades/finfeed/wallet_fallback).
"""

import os
import sys
import argparse
from typing import Optional, Dict

from dotenv import load_dotenv

# Ensure project root on path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv()

from price_fetcher import get_current_price  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test fetching price for a single Polymarket market (by slug or condition_id)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", type=str, help="Market slug, e.g. 'will-trump-win-2024-election'")
    group.add_argument("--condition-id", type=str, help="Market condition id, e.g. '0xabc123...'");
    parser.add_argument("--outcome-index", type=int, default=0, help="Outcome index (0=Yes, 1=No). Default: 0")
    parser.add_argument(
        "--use-wallet-prices",
        action="store_true",
        help="If set, pass test wallet_prices fallback [0.51, 0.72]"
    )
    return parser.parse_args()


def build_wallet_prices(use_wallet_prices_flag: bool) -> Optional[Dict[str, float]]:
    if not use_wallet_prices_flag:
        return None
    # Provide a small, valid dict for fallback averaging
    return {
        "0xwalletA": 0.51,
        "0xwalletB": 0.72,
    }


def main() -> None:
    args = parse_args()

    slug: Optional[str] = args.slug
    condition_id: Optional[str] = args.condition_id if hasattr(args, "condition_id") else None
    outcome_index: int = args.outcome_index
    wallet_prices = build_wallet_prices(args.use_wallet_prices)

    print("=" * 80)
    print("🔍 Single Market Price Test")
    print("=" * 80)
    print(f"- slug          : {slug or 'N/A'}")
    print(f"- condition_id  : {condition_id or 'N/A'}")
    print(f"- outcome_index : {outcome_index}")
    print(f"- wallet_prices : {'enabled' if wallet_prices else 'disabled'}")
    print()

    # Call price fetcher in the most realistic way
    price, source = get_current_price(
        condition_id=condition_id,
        outcome_index=outcome_index,
        slug=slug,
        wallet_prices=wallet_prices,
        debug=True,
    )

    print("—" * 80)
    if price is not None:
        print(f"✅ Price: {price:.6f}")
    else:
        print("⚠️  Price: N/A")
    print(f"🔗 Source: {source or 'none'}")
    print("—" * 80)


if __name__ == "__main__":
    main()


