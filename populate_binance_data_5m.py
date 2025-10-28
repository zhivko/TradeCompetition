import asyncio
import time
import json
from redis_utils import init_redis, get_oldest_cached_timestamp, fetch_klines_from_binance, cache_klines, fetch_open_interest_from_binance, cache_open_interest, get_cached_klines, get_cached_open_interest, get_redis_connection, get_sorted_set_key, detect_gaps_in_cached_data, fill_data_gaps, set_default_exchange, get_current_exchange_setting
from MarketCoordinator import MarketCoordinator

def get_timeframe_seconds(resolution: str) -> int:
    """Get timeframe in seconds for a given resolution."""
    multipliers = {"1m": 60, "5m": 300, "1h": 3600, "4h": 14400, "1d": 86400, "1w": 604800}
    return multipliers.get(resolution, 3600)

# Coins used in main.py (from MarketCoordinator)
coins = MarketCoordinator.COINS
resolution = "5m"  # Use 5m resolution for historical data

async def main():
    """Populate historical data for all coins from Binance starting from January 1, 2021"""
    print("Initializing Redis connection...")
    await init_redis()

    # Set default exchange to Binance
    set_default_exchange("binance")
    print(f"Exchange setting set to: binance")

    print("Checking and populating data from January 1, 2021 for all coins from Binance...")
    end_ts = int(time.time())
    start_ts = 1609459200  # January 1, 2021 00:00:00 UTC

    redis = await get_redis_connection()

    for coin in coins:
        symbol = f"{coin}USDT"
        print(f"Checking cached data for {coin}...")

        # Check if data is already cached
        cached_klines = await get_cached_klines(symbol, resolution, start_ts, end_ts)
        cached_oi = await get_cached_open_interest(symbol, resolution, start_ts, end_ts)

        # Always validate data quality for simulation mode - don't skip even if data exists
        print(f"[INFO] {coin} has {len(cached_klines)} cached klines and {len(cached_oi)} OI records - validating data quality")

        # Check for null/empty OHLC values in cached data
        null_count = sum(1 for k in cached_klines if not all(k.get(field) for field in ['time', 'open', 'high', 'low', 'close', 'vol']))
        if null_count > 0:
            print(f"[WARNING] Found {null_count} records with null/empty OHLC values in cached data for {coin} - will clean and refetch")
        else:
            print(f"[INFO] Cached data for {coin} appears valid - {len(cached_klines)} records with no null/empty OHLC values")

        # Check for gaps in the data - ALWAYS check for gaps, don't skip
        gaps = await detect_gaps_in_cached_data(symbol, resolution, start_ts, end_ts)
        if gaps:
            print(f"[WARNING] Found {len(gaps)} gaps in cached data for {coin} - will fill gaps")
            await fill_data_gaps(gaps)
            print(f"[SUCCESS] Filled gaps for {coin}")
        else:
            print(f"[INFO] No gaps found in cached data for {coin}")

        # Check if we have complete data coverage for the entire time range
        expected_points = int((end_ts - start_ts) / get_timeframe_seconds(resolution))
        coverage_percentage = (len(cached_klines) / expected_points) * 100 if expected_points > 0 else 0
        print(f"[INFO] Data coverage for {coin}: {len(cached_klines)}/{expected_points} points ({coverage_percentage:.1f}%)")

        if coverage_percentage < 95.0:  # Less than 95% coverage
            print(f"[WARNING] Insufficient data coverage for {coin} ({coverage_percentage:.1f}%) - will refetch complete dataset from Binance")
        else:
            print(f"[SUCCESS] Sufficient data coverage for {coin} ({coverage_percentage:.1f}%) - skipping refetch")
            # Add a small delay to prevent overwhelming the system
            await asyncio.sleep(0.1)
            continue  # Skip to next coin if coverage is good

        print(f"Fetching data for {coin} from Binance from {time.strftime('%Y-%m-%d', time.localtime(start_ts))} to {time.strftime('%Y-%m-%d', time.localtime(end_ts))}")

        # Fetch klines from Binance
        klines = None
        try:
            klines = fetch_klines_from_binance(symbol, resolution, start_ts, end_ts)
        except Exception as e:
            print(f"[ERROR] Binance API fetch failed for {coin}: {e}")
        
        if klines:
            # Filter out records with null/empty OHLC values
            filtered_klines = [k for k in klines if all(k.get(field) for field in ['time', 'open', 'high', 'low', 'close', 'vol'])]
            if len(filtered_klines) < len(klines):
                print(f"[WARNING] Filtered out {len(klines) - len(filtered_klines)} records with null/empty OHLC values for {coin}")
            if filtered_klines:
                await cache_klines(symbol, resolution, filtered_klines)
                print(f"[SUCCESS] Cached {len(filtered_klines)} klines for {coin}")
            else:
                print(f"[ERROR] No valid klines data after filtering for {coin}")
        else:
            print(f"[ERROR] No klines data fetched from Binance for {coin}")

        # Fetch open interest from Binance
        # Note: Binance only provides current open interest data, not historical
        # So we'll only get the current value and not attempt to fill the entire date range
        oi_data = None
        try:
            oi_data = fetch_open_interest_from_binance(symbol, resolution, start_ts, end_ts)
        except Exception as e:
            print(f"[WARNING] Binance OI fetch failed for {coin}: {e}")

        if oi_data:
            await cache_open_interest(symbol, resolution, oi_data)
            print(f"[SUCCESS] Cached {len(oi_data)} open interest records for {coin}")
        else:
            print(f"[WARNING] No open interest data fetched for {coin} from Binance - Binance only provides current OI data, not historical")

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
            print(f"[CLEANUP] Removed {cleaned_count} records with null/empty OHLC values for {coin}")

    print("Binance historical data population completed!")

if __name__ == "__main__":
    print("Usage: python populate_binance_data_5m.py")
    print("This script populates historical 5m data for all coins from Binance into Redis")
    print("We need this to run in simulation mode (main.py --simulation)")
    print()
    asyncio.run(main())