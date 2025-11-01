#!/usr/bin/env python3
"""
Script to verify that historical data has been correctly cached in Redis
"""
import asyncio
from redis_utils import init_redis, get_cached_klines, get_redis_connection
from MarketCoordinator import MarketCoordinator

async def verify_redis_data():
    """Verify that historical data exists in Redis for all coins"""
    logger.info("Initializing Redis connection...")
    await init_redis()
    
    redis = await get_redis_connection()
    
    logger.info("Verifying data in Redis...")
    
    # Check for data in the zset keys for all coins
    for coin in MarketCoordinator.COINS:
        symbol = f"{coin}USDT"
        sorted_set_key = f"zset:kline:{symbol}:5m"
        
        # Check if the sorted set exists and how many members it has
        card = await redis.zcard(sorted_set_key)
        logger.info(f"{symbol}: {card} data points in Redis sorted set")
        
        # Get a sample of the data to verify it's properly formatted
        if card > 0:
            # Get first few and last few entries to verify range
            first_few = await redis.zrange(sorted_set_key, 0, 2, withscores=True)
            last_few = await redis.zrange(sorted_set_key, -3, -1, withscores=True)
            
            logger.info(f"  First few timestamps: {[int(score) for _, score in first_few]}")
            logger.info(f"  Last few timestamps: {[int(score) for _, score in last_few]}")
            
            # Check a sample of the data to ensure it has proper structure
            sample_data = await redis.zrange(sorted_set_key, 0, 0)
            if sample_data:
                import json
                try:
                    parsed = json.loads(sample_data[0])
                    if all(key in parsed for key in ['time', 'open', 'high', 'low', 'close', 'vol']):
                        logger.info(f"  [OK] Data structure is valid for {symbol}")
                    else:
                        logger.info(f"  [ERROR] Data structure is invalid for {symbol}: {parsed}")
                except json.JSONDecodeError:
                    logger.info(f"  [ERROR] Data is not valid JSON for {symbol}")
        else:
            logger.info(f"  [ERROR] No data found for {symbol}")
        logger.info()
    
    # Also test the get_cached_klines function directly with a small range
    logger.info("Testing get_cached_klines function with a small date range...")
    import time
    start_ts = 1609459200  # Jan 1, 2021
    end_ts = start_ts + 86400  # One day later
    
    for coin in MarketCoordinator.COINS[:2]:  # Just test first 2 coins
        symbol = f"{coin}USDT"
        klines = await get_cached_klines(symbol, "5m", start_ts, end_ts)
        logger.info(f"{symbol} (Jan 1-2, 2021): {len(klines)} klines retrieved")

if __name__ == "__main__":
    asyncio.run(verify_redis_data())