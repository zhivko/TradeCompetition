import asyncio
import time
from datetime import datetime
from redis_utils import init_redis, get_cached_klines, get_redis_connection, fetch_klines_from_binance, cache_klines, detect_gaps_in_cached_data, fill_data_gaps


async def test_gap_detection_and_filling():
    """Test gap detection and filling functionality"""
    logger.info("Initializing Redis connection...")
    await init_redis()
    
    symbol = "BTCUSDT"
    resolution = "5m"
    
    # Test with a range where we know there will be gaps
    start_ts = int(time.mktime((2021, 1, 1, 0, 0, 0, 0, 0, 0)))  # 2021-01-01
    end_ts = int(time.mktime((2021, 1, 10, 0, 0, 0, 0, 0, 0)))   # 2021-01-10
    
    logger.info(f"Testing gap detection from {datetime.fromtimestamp(start_ts)} to {datetime.fromtimestamp(end_ts)}")
    
    # First check what's already in Redis
    cached_klines = await get_cached_klines(symbol, resolution, start_ts, end_ts)
    logger.info(f"Found {len(cached_klines)} cached klines in Redis for the range")
    
    if cached_klines:
        logger.info(f"First cached kline: {cached_klines[0]}")
        logger.info(f"Last cached kline: {cached_klines[-1]}")
    
    # Detect gaps in the data
    gaps = await detect_gaps_in_cached_data(symbol, resolution, start_ts, end_ts)
    logger.info(f"\nFound {len(gaps)} gaps in the cached data:")
    
    for i, gap in enumerate(gaps):
        logger.info(f"  Gap {i+1}: {datetime.fromtimestamp(gap['from_ts'])} to {datetime.fromtimestamp(gap['to_ts'])}, "
              f"missing {gap['missing_points']} data points")
    
    # Fill the gaps
    if gaps:
        logger.info(f"\nAttempting to fill {len(gaps)} gaps...")
        try:
            await fill_data_gaps(gaps)
            logger.info("Successfully filled all detected gaps")
        except Exception as e:
            logger.info(f"Error filling gaps: {e}")
            import traceback
            traceback.print_exc()
    
    # Check the data again after gap filling
    cached_klines_after = await get_cached_klines(symbol, resolution, start_ts, end_ts)
    logger.info(f"\nAfter gap filling, found {len(cached_klines_after)} cached klines in Redis for the range")


if __name__ == "__main__":
    asyncio.run(test_gap_detection_and_filling())