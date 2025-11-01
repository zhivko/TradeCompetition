import asyncio
import time
from datetime import datetime
from redis_utils import init_redis, get_cached_klines, get_redis_connection, fetch_klines_from_binance, cache_klines


async def test_binance_fetch_larger_range():
    """Test Binance fetching functionality with a larger range that might have gaps"""
    logger.info("Initializing Redis connection...")
    await init_redis()
    
    symbol = "BTCUSDT"
    resolution = "5m"
    
    # Test with a timeframe that includes both recent and older data
    start_ts = int(time.mktime((2024, 1, 1, 0, 0, 0, 0, 0, 0)))  # 2024-01-01
    end_ts = int(time.mktime((2024, 1, 3, 0, 0, 0, 0, 0, 0)))    # 2024-01-03
    
    logger.info(f"Testing fetch from {datetime.fromtimestamp(start_ts)} to {datetime.fromtimestamp(end_ts)}")
    
    # First check what's already in Redis
    cached_klines = await get_cached_klines(symbol, resolution, start_ts, end_ts)
    logger.info(f"Found {len(cached_klines)} cached klines in Redis for the range")
    
    if cached_klines:
        logger.info(f"First cached kline: {cached_klines[0]}")
        logger.info(f"Last cached kline: {cached_klines[-1]}")
    
    # Now try to fetch from Binance directly
    logger.info(f"\nAttempting to fetch from Binance for {symbol} {resolution}...")
    try:
        binance_klines = fetch_klines_from_binance(symbol, resolution, start_ts, end_ts)
        logger.info(f"Received {len(binance_klines)} klines from Binance")
        
        if binance_klines:
            logger.info(f"First Binance kline: {binance_klines[0]}")
            logger.info(f"Last Binance kline: {binance_klines[-1]}")
        
            # Test caching the new data
            if binance_klines:
                logger.info(f"\nTesting caching of {len(binance_klines)} klines...")
                await cache_klines(symbol, resolution, binance_klines)
                logger.info("Successfully cached Binance data")
        
    except Exception as e:
        logger.info(f"Error fetching from Binance: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_binance_fetch_larger_range())