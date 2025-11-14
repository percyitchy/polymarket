#!/usr/bin/env python3
"""
Test script for bet monitoring functionality
"""

import asyncio
import os
import logging
from dotenv import load_dotenv
from bet_monitor import BetDetector, TelegramNotifier

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_bet_monitoring():
    """Test bet monitoring functionality"""
    
    # Check configuration
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        logger.error("❌ Missing Telegram configuration. Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return
    
    logger.info("🧪 Testing bet monitoring functionality...")
    
    # Initialize components
    bet_detector = BetDetector()
    
    # Test wallet addresses (using some from our database)
    test_wallets = [
        "0xed88d69d689f3e2f6d1f77b2e35d089c581df3c4",  # Top wallet
        "0x5bffcf561bcae83af680ad600cb99f1184d6ffbe",  # Second wallet
        "0x7fb7ad0d194d7123e711e7db6c9d418fac14e33d",  # Third wallet
    ]
    
    logger.info(f"Testing with {len(test_wallets)} wallets")
    
    # Initialize Telegram notifier
    async with TelegramNotifier(bot_token, chat_id) as telegram_notifier:
        # Send test message
        test_message = """
🧪 <b>Bet Monitoring Test</b>

Testing bet monitoring functionality with:
👥 Wallets: 3 test wallets
🎯 Min Consensus: 2 wallets
⏰ Alert Window: 15 minutes
🔄 Poll Interval: 7 seconds

This is a test message to verify Telegram integration.
        """.strip()
        
        success = await telegram_notifier.send_message(test_message)
        
        if success:
            logger.info("✅ Test message sent successfully!")
        else:
            logger.error("❌ Failed to send test message")
            return
        
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
        
        # Send completion message (only if we have results)
        if len(trades) > 0:
            completion_message = f"""
✅ <b>Bet Monitoring Test Complete</b>

📊 Results:
• Trades fetched: {len(trades)}
• Positions parsed: {len(positions)}
• Matching bets detected: {len(matching_bets)}

The bet monitoring system is ready! 🚀
            """.strip()
            
            await telegram_notifier.send_message(completion_message)
        else:
            logger.info("Skipping completion message to avoid rate limiting")

async def main():
    """Main test function"""
    await test_bet_monitoring()

if __name__ == "__main__":
    asyncio.run(main())
