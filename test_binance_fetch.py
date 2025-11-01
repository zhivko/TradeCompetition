import asyncio
import time
from datetime import datetime
from redis_utils import init_redis, get_cached_klines, get_redis_connection, fetch_klines_from_binance


async def test_binance_fetch():
    """Test Binance fetching functionality on a small timeframe"""
    logger.info("Initializing Redis connection...")
    await init_redis()
    
    symbol = "BTCUSDT"
    resolution = "5m"
    
    # Test with a small timeframe first - use data from 2 days ago
    now = int(time.time())
    start_ts = now - 2 * 24 * 60 * 60  # 2 days ago
    end_ts = now - 1 * 24 * 60 * 60    # 1 day ago
    
    logger.info(f"Testing fetch from {datetime.fromtimestamp(start_ts)} to {datetime.fromtimestamp(end_ts)}")
    
    # First check what's already in Redis
    cached_klines = await get_cached_klines(symbol, resolution, start_ts, end_ts)
    logger.info(f"Found {len(cached_klines)} cached klines in Redis")
    
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
        
    except Exception as e:
        logger.info(f"Error fetching from Binance: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_binance_fetch())