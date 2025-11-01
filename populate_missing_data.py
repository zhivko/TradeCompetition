import asyncio
import time
import json
from logging_config import logger
from redis_utils import init_redis, get_oldest_cached_timestamp, fetch_klines_from_bybit, fetch_klines_from_binance, cache_klines, fetch_open_interest_from_bybit, fetch_open_interest_from_binance, cache_open_interest, get_cached_klines, get_cached_open_interest, get_redis_connection, get_sorted_set_key, detect_gaps_in_cached_data, fill_data_gaps, set_default_exchange, get_current_exchange_setting
from MarketCoordinator import MarketCoordinator


def get_timeframe_seconds(resolution: str) -> int:
    """Get timeframe in seconds for a given resolution."""
    multipliers = {"1m": 60, "5m": 300, "1h": 3600, "4h": 14400, "1d": 86400, "1w": 604800}
    return multipliers.get(resolution, 3600)

# Coins used in main.py (from MarketCoordinator)
coins = MarketCoordinator.COINS
resolution = "5m"  # Use 5m resolution for historical data

async def main():
    """Populate historical data for all coins starting from January 1, 2021"""
    logger.info("Initializing Redis connection...")
    await init_redis()

    # Check current exchange setting
    current_exchange = get_current_exchange_setting()
    logger.info(f"Current exchange setting: {current_exchange}")

    # Allow command line override of exchange
    import sys
    if len(sys.argv) > 1:
        exchange_arg = sys.argv[1].lower()
        if exchange_arg in ["auto", "bybit", "binance"]:
            set_default_exchange(exchange_arg)
            logger.info(f"Exchange setting changed to: {exchange_arg}")
        else:
            logger.info(f"Invalid exchange argument: {exchange_arg}. Use 'auto', 'bybit', or 'binance'")

    logger.info("Checking and populating data from January 1, 2021 for all coins...")
    end_ts = int(time.time())
    start_ts = 1609459200  # January 1, 2021 00:00:00 UTC

    redis = await get_redis_connection()

    for coin in coins:
        symbol = f"{coin}USDT"
        logger.info(f"Checking cached data for {coin}...")

        # Check if data is already cached
        cached_klines = await get_cached_klines(symbol, resolution, start_ts, end_ts)
        cached_oi = await get_cached_open_interest(symbol, resolution, start_ts, end_ts)

        # Always validate data quality for simulation mode - don't skip even if data exists
        logger.info(f"[INFO] {coin} has {len(cached_klines)} cached klines and {len(cached_oi)} OI records - validating data quality")

        # Check for null/empty OHLC values in cached data
        null_count = sum(1 for k in cached_klines if not all(k.get(field) for field in ['time', 'open', 'high', 'low', 'close', 'vol']))
        if null_count > 0:
            logger.info(f"[WARNING] Found {null_count} records with null/empty OHLC values in cached data for {coin} - will clean and refetch")
        else:
            logger.info(f"[INFO] Cached data for {coin} appears valid - {len(cached_klines)} records with no null/empty OHLC values")

        # Check for gaps in the data - ALWAYS check for gaps, don't skip
        gaps = await detect_gaps_in_cached_data(symbol, resolution, start_ts, end_ts)
        if gaps:
            logger.info(f"[WARNING] Found {len(gaps)} gaps in cached data for {coin} - will fill gaps")
            await fill_data_gaps(gaps)
            logger.info(f"[SUCCESS] Filled gaps for {coin}")
        else:
            logger.info(f"[INFO] No gaps found in cached data for {coin}")

        # Check if we have complete data coverage for the entire time range
        expected_points = int((end_ts - start_ts) / get_timeframe_seconds(resolution))
        coverage_percentage = (len(cached_klines) / expected_points) * 100 if expected_points > 0 else 0
        logger.info(f"[INFO] Data coverage for {coin}: {len(cached_klines)}/{expected_points} points ({coverage_percentage:.1f}%)")

        if coverage_percentage < 100.0:  # Less than 100% coverage
            logger.info(f"[WARNING] Insufficient data coverage for {coin} ({coverage_percentage:.1f}%) - will refetch complete dataset")
            
            logger.info(f"Fetching data for {coin} from {time.strftime('%Y-%m-%d', time.localtime(start_ts))} to {time.strftime('%Y-%m-%d', time.localtime(end_ts))}")

            # For 5m timeframe, specifically use Binance API for complete refetch
            klines = None
            logger.info(f"[INFO] Attempting to fetch 5m data for {coin} from Binance...")
            
            try:
                klines = fetch_klines_from_binance(symbol, resolution, start_ts, end_ts)
            except Exception as e:
                logger.info(f"[ERROR] Binance API fetch failed for {coin}: {e}")
            
            if klines:
                # Filter out records with null/empty OHLC values
                filtered_klines = [k for k in klines if all(k.get(field) for field in ['time', 'open', 'high', 'low', 'close', 'vol'])]
                if len(filtered_klines) < len(klines):
                    logger.info(f"[WARNING] Filtered out {len(klines) - len(filtered_klines)} records with null/empty OHLC values for {coin}")
                if filtered_klines:
                    # Clear existing Redis data for this symbol before caching new complete dataset
                    redis = await get_redis_connection()
                    sorted_set_key = get_sorted_set_key(symbol, resolution)

                    # Delete all individual kline keys
                    pattern = f"kline:{symbol}:{resolution}:*"
                    deleted_keys = 0
                    async for key in redis.scan_iter(match=pattern):
                        await redis.delete(key)
                        deleted_keys += 1

                    # Delete sorted set
                    await redis.delete(sorted_set_key)
                    logger.info(f"[CLEANUP] Deleted {deleted_keys} individual keys and sorted set for {coin}")

                    await cache_klines(symbol, resolution, filtered_klines)
                    logger.info(f"[SUCCESS] Cached {len(filtered_klines)} klines for {coin}")
                else:
                    logger.info(f"[ERROR] No valid klines data after filtering for {coin} - clearing Redis data and refetching from Bybit as fallback")

                    # Clear existing Redis data for this symbol
                    redis = await get_redis_connection()
                    sorted_set_key = get_sorted_set_key(symbol, resolution)

                    # Delete all individual kline keys
                    pattern = f"kline:{symbol}:{resolution}:*"
                    deleted_keys = 0
                    async for key in redis.scan_iter(match=pattern):
                        await redis.delete(key)
                        deleted_keys += 1

                    # Delete sorted set
                    await redis.delete(sorted_set_key)
                    logger.info(f"[CLEANUP] Deleted {deleted_keys} individual keys and sorted set for {coin}")

                    # Refetch from Bybit as fallback
                    logger.info(f"[REFETCH] Refetching data for {coin} from Bybit as fallback...")
                    fresh_klines = fetch_klines_from_bybit(symbol, resolution, start_ts, end_ts)
                    if fresh_klines:
                        # Filter the fresh data as well
                        fresh_filtered_klines = [k for k in fresh_klines if all(k.get(field) for field in ['time', 'open', 'high', 'low', 'close', 'vol'])]
                        if len(fresh_filtered_klines) < len(fresh_klines):
                            logger.info(f"[WARNING] Filtered out {len(fresh_klines) - len(fresh_filtered_klines)} records from fresh Bybit data for {coin}")

                        if fresh_filtered_klines:
                            await cache_klines(symbol, resolution, fresh_filtered_klines)
                            logger.info(f"[SUCCESS] Cached {len(fresh_filtered_klines)} fresh klines for {coin}")
                        else:
                            logger.info(f"[ERROR] Fresh Bybit data also contains no valid klines for {coin}")
                    else:
                        logger.info(f"[ERROR] Failed to refetch data from Bybit for {coin}")
            else:
                logger.info(f"[ERROR] No klines data fetched from Binance for {coin}")
        else:
            logger.info(f"[SUCCESS] Sufficient data coverage for {coin} ({coverage_percentage:.1f}%) - skipping refetch")
            # Add a small delay to prevent overwhelming the system
            await asyncio.sleep(0.1)
            continue  # Skip to next coin if coverage is good

        # Always fetch open interest when refetching klines for complete dataset
        oi_data = None
        # Try Bybit first
        try:
            oi_data = fetch_open_interest_from_bybit(symbol, resolution, start_ts, end_ts)
        except Exception as e:
            logger.info(f"[WARNING] Bybit OI fetch failed for {coin}: {e}")

        # If Bybit failed or returned no data, try Binance
        if not oi_data:
            try:
                oi_data = fetch_open_interest_from_binance(symbol, resolution, start_ts, end_ts)
            except Exception as e:
                logger.info(f"[WARNING] Binance OI fetch failed for {coin}: {e}")

        if oi_data:
            await cache_open_interest(symbol, resolution, oi_data)
            logger.info(f"[SUCCESS] Cached {len(oi_data)} open interest records for {coin}")
        else:
            logger.info(f"[WARNING] No open interest data fetched for {coin} from any source")

        # Clean up existing data with null/empty OHLC values
        sorted_set_key = get_sorted_set_key(symbol, resolution)
        klines_data_redis = await redis.zrangebyscore(sorted_set_key, min=start_ts, max=end_ts, withscores=False)
        cleaned_count = 0
        for data_item in klines_data_redis:
            try:
                if isinstance(data_item, bytes):
                    data_str = data_item.decode('utf-8')
                elif isinstance(data_item, str):
                    data_str = data_item
                else:
                    continue
                parsed_data = json.loads(data_str)
                if not all(parsed_data.get(field) for field in ['time', 'open', 'high', 'low', 'close', 'vol']):
                    # Remove this record from Redis
                    await redis.zrem(sorted_set_key, data_str)
                    cleaned_count += 1
            except json.JSONDecodeError:
                continue

        if cleaned_count > 0:
            logger.info(f"[CLEANUP] Removed {cleaned_count} records with null/empty OHLC values for {coin}")

    logger.info("Historical data population completed!")

if __name__ == "__main__":
    logger.info("Usage: python populate_missing_data.py [auto|bybit|binance]")
    logger.info("  auto  - Use exchange preferences (default)")
    logger.info("  bybit - Force use of Bybit API only")
    logger.info("  binance - Force use of Binance API only")
    asyncio.run(main())
