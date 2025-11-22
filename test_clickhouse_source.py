#!/usr/bin/env python3
"""
Тестовый скрипт для проверки ClickHouse клиента
Использует новый ClickHouseClient класс
"""

import logging
import json
from clickhouse_client import ClickHouseClient, RateLimitExceeded

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Основная функция тестирования"""
    logger.info("=" * 60)
    logger.info("Тестирование ClickHouse Client")
    logger.info("=" * 60)
    
    # Initialize client
    client = ClickHouseClient()
    
    # Test 1: Connection test
    logger.info("\n1. Testing connection...")
    try:
        if client.test_connection():
            logger.info("✅ Connected to ClickHouse")
        else:
            logger.error("❌ Connection test failed")
            return
    except Exception as e:
        logger.error(f"❌ Connection test error: {type(e).__name__}: {e}")
        return
    
    # Test 2: Rate limit status
    logger.info("\n2. Checking rate limit status...")
    try:
        status = client.get_rate_limit_status()
        logger.info(f"Queries used: {status['queries_used']}/{status['queries_per_hour']}")
        logger.info(f"Queries remaining: {status['queries_remaining']}")
        logger.info(f"Reset time: {status['reset_time']}")
        logger.info("✅ Rate limit status retrieved")
    except Exception as e:
        logger.error(f"❌ Rate limit status error: {type(e).__name__}: {e}")
    
    # Test 3: Get latest price
    logger.info("\n3. Getting latest price...")
    # Use a real token_id from your database or test data
    # Example format: "0x123...:0" or just hex string
    test_token_id = "0x0000000000000000000000000000000000000000000000000000000000000001:0"  # Replace with real token_id
    try:
        price = client.get_latest_price(test_token_id)
        if price is not None:
            logger.info(f"Token ID: {test_token_id}")
            logger.info(f"Price: {price}")
            logger.info("✅ Success")
        else:
            logger.warning(f"⚠️ No price found for token_id={test_token_id}")
    except RateLimitExceeded as e:
        logger.warning(f"⚠️ Rate limit exceeded: {e}")
    except Exception as e:
        logger.error(f"❌ Get latest price error: {type(e).__name__}: {e}")
    
    # Test 4: Get open interest
    logger.info("\n4. Getting market open interest...")
    # Use a real condition_id from your database or test data
    test_condition_id = "0x0000000000000000000000000000000000000000000000000000000000000001"  # Replace with real condition_id
    try:
        oi = client.get_market_open_interest(test_condition_id)
        if oi:
            logger.info(f"Condition ID: {test_condition_id}")
            logger.info(f"Open Interest: {json.dumps(oi, indent=2, default=str)}")
            logger.info("✅ Success")
        else:
            logger.warning(f"⚠️ No open interest found for condition_id={test_condition_id}")
    except RateLimitExceeded as e:
        logger.warning(f"⚠️ Rate limit exceeded: {e}")
    except Exception as e:
        logger.error(f"❌ Get open interest error: {type(e).__name__}: {e}")
    
    # Test 5: Get user positions
    logger.info("\n5. Getting user positions...")
    # Use a real user_address from your database or test data
    test_user_address = "0x0000000000000000000000000000000000000000"  # Replace with real wallet address
    try:
        positions = client.get_user_positions(test_user_address)
        if positions:
            logger.info(f"User Address: {test_user_address}")
            logger.info(f"Positions: {json.dumps(positions, indent=2, default=str)}")
            logger.info(f"Found {len(positions)} positions")
            logger.info("✅ Success")
        else:
            logger.warning(f"⚠️ No positions found for user_address={test_user_address}")
    except RateLimitExceeded as e:
        logger.warning(f"⚠️ Rate limit exceeded: {e}")
    except Exception as e:
        logger.error(f"❌ Get user positions error: {type(e).__name__}: {e}")
    
    # Test 6: Get user balances
    logger.info("\n6. Getting user balances...")
    try:
        balances = client.get_user_balances(test_user_address)
        if balances:
            logger.info(f"User Address: {test_user_address}")
            logger.info(f"Balances: {json.dumps(balances, indent=2, default=str)}")
            logger.info("✅ Success")
        else:
            logger.warning(f"⚠️ No balances found for user_address={test_user_address}")
    except RateLimitExceeded as e:
        logger.warning(f"⚠️ Rate limit exceeded: {e}")
    except Exception as e:
        logger.error(f"❌ Get user balances error: {type(e).__name__}: {e}")
    
    # Test 7: Get recent trades
    logger.info("\n7. Getting recent trades...")
    try:
        trades = client.get_recent_trades(test_token_id, limit=5)
        if trades:
            logger.info(f"Token ID: {test_token_id}")
            logger.info(f"Recent Trades: {json.dumps(trades, indent=2, default=str)}")
            logger.info(f"Found {len(trades)} trades")
            logger.info("✅ Success")
        else:
            logger.warning(f"⚠️ No trades found for token_id={test_token_id}")
    except RateLimitExceeded as e:
        logger.warning(f"⚠️ Rate limit exceeded: {e}")
    except Exception as e:
        logger.error(f"❌ Get recent trades error: {type(e).__name__}: {e}")
    
    # Test 8: Rate limit handling
    logger.info("\n8. Testing rate limit handling...")
    logger.info("Making 65 queries rapidly to test rate limiting...")
    try:
        success_count = 0
        rate_limit_count = 0
        error_count = 0
        
        for i in range(65):
            try:
                # Use a simple query that won't fail due to data
                result = client._make_request("SELECT 1 FORMAT JSONEachRow")
                if result:
                    success_count += 1
                if (i + 1) % 10 == 0:
                    logger.info(f"  Made {i + 1} queries... (success: {success_count}, rate_limit: {rate_limit_count}, errors: {error_count})")
            except RateLimitExceeded as e:
                rate_limit_count += 1
                logger.info(f"  ⚠️ Rate limit hit at query {i + 1}: {e}")
                break  # Stop when rate limit is hit
            except Exception as e:
                error_count += 1
                logger.warning(f"  ❌ Error at query {i + 1}: {type(e).__name__}: {e}")
        
        logger.info(f"Rate limit test completed:")
        logger.info(f"  Successful queries: {success_count}")
        logger.info(f"  Rate limit hits: {rate_limit_count}")
        logger.info(f"  Errors: {error_count}")
        
        # Check final rate limit status
        final_status = client.get_rate_limit_status()
        logger.info(f"Final rate limit status: {final_status['queries_used']}/{final_status['queries_per_hour']} queries used")
        
    except Exception as e:
        logger.error(f"❌ Rate limit test error: {type(e).__name__}: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info("Тестирование завершено")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
