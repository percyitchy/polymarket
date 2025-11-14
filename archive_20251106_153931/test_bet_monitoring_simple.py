#!/usr/bin/env python3
"""
Simple test for bet monitoring functionality (without Telegram)
"""

import asyncio
import logging
from bet_monitor import BetDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_bet_monitoring_simple():
    """Test bet monitoring functionality without Telegram"""
    
    logger.info("🧪 Testing bet monitoring functionality (no Telegram)...")
    
    # Initialize components
    bet_detector = BetDetector()
    
    # Test wallet addresses (using some from our database)
    test_wallets = [
        "0xed88d69d689f3e2f6d1f77b2e35d089c581df3c4",  # Top wallet
        "0x5bffcf561bcae83af680ad600cb99f1184d6ffbe",  # Second wallet
        "0x7fb7ad0d194d7123e711e7db6c9d418fac14e33d",  # Third wallet
    ]
    
    logger.info(f"Testing with {len(test_wallets)} wallets")
    
    # Test getting recent trades for one wallet
    logger.info("Testing trade fetching...")
    trades = await bet_detector.get_recent_trades(test_wallets[0], limit=10)
    logger.info(f"Found {len(trades)} recent trades for test wallet")
    
    if trades:
        logger.info("Sample trade data:")
        for i, trade in enumerate(trades[:3]):
            logger.info(f"  {i+1}. {trade.get('title', 'Unknown')} - {trade.get('side', 'Unknown')} - ${trade.get('amount', 0)}")
    
    # Test position parsing
    logger.info("Testing position parsing...")
    positions = []
    for trade in trades[:5]:  # Test with first 5 trades
        position = bet_detector.parse_trade_to_position(trade, test_wallets[0])
        if position:
            positions.append(position)
    
    logger.info(f"Parsed {len(positions)} positions")
    
    if positions:
        logger.info("Sample positions:")
        for i, pos in enumerate(positions[:3]):
            logger.info(f"  {i+1}. {pos.market_title} - {pos.outcome} - ${pos.amount}")
    
    # Test matching bet detection
    logger.info("Testing matching bet detection...")
    matching_bets = bet_detector.detect_matching_bets(positions)
    logger.info(f"Found {len(matching_bets)} potential matching bets")
    
    # Test alert formatting
    if matching_bets:
        logger.info("Sample alert message:")
        from bet_monitor import TelegramNotifier
        dummy_notifier = TelegramNotifier("dummy", "dummy")
        sample_message = dummy_notifier.format_matching_bet_alert(matching_bets[0])
        logger.info(sample_message)
    
    logger.info("✅ Bet monitoring test completed successfully!")
    
    return {
        'trades_fetched': len(trades),
        'positions_parsed': len(positions),
        'matching_bets': len(matching_bets)
    }

async def main():
    """Main test function"""
    results = await test_bet_monitoring_simple()
    print(f"\n📊 Test Results: {results}")

if __name__ == "__main__":
    asyncio.run(main())
