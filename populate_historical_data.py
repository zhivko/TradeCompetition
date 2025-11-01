#!/usr/bin/env python3
"""
Script to populate Redis with historical kline data from 2021-2025 for all coins.
Uses Binance API to fetch historical data and caches it to Redis.
"""

import asyncio
from datetime import datetime, timezone
from redis_utils import (
    init_redis, cache_klines, fetch_klines_from_binance,
    get_cached_klines_individual, get_sorted_set_key, get_redis_connection
)
from MarketCoordinator import MarketCoordinator
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Time range: 2021 to 2025 inclusive
START_YEAR = 2021
END_YEAR = 2025
RESOLUTION = "5m"

def get_year_range(year: int) -> tuple[int, int]:
    """Get start and end timestamps for a given year."""
    # First day of the year at 00:00:00 UTC
    start_ts = int(datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())

    # First day of next year at 00:00:00 UTC
    end_ts = int(datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())

    return start_ts, end_ts

async def populate_coin_data(symbol: str, year: int) -> bool:
    """Populate data for a specific coin and year."""
    try:
        logger.info(f"📊 Starting population for {symbol} {year}")

        start_ts, end_ts = get_year_range(year)
        logger.info(f"   Time range: {datetime.fromtimestamp(start_ts, timezone.utc)} to {datetime.fromtimestamp(end_ts, timezone.utc)}")

        # Check if we already have data for this year
        redis = await get_redis_connection()
        sorted_set_key = get_sorted_set_key(symbol, RESOLUTION)

        existing_count = await redis.zcount(sorted_set_key, start_ts, end_ts)
        if existing_count > 1000:  # If we have substantial data, skip
            logger.info(f"   ✅ Already have {existing_count} data points for {symbol} {year}, skipping")
            return True

        # Fetch data from Binance
        logger.info(f"   📡 Fetching data from Binance API...")
        klines = fetch_klines_from_binance(symbol, RESOLUTION, start_ts, end_ts)

        if not klines:
            logger.warning(f"   ❌ No data received from Binance for {symbol} {year}")
            return False

        logger.info(f"   📦 Received {len(klines)} klines from Binance")

        # Cache the data
        logger.info(f"   💾 Caching data to Redis...")
        await cache_klines(symbol, RESOLUTION, klines)

        # Verify the data was cached
        cached_count = await redis.zcount(sorted_set_key, start_ts, end_ts)
        logger.info(f"   ✅ Successfully cached {cached_count} data points for {symbol} {year}")

        return True

    except Exception as e:
        logger.error(f"   ❌ Error populating {symbol} {year}: {e}")
        return False

async def populate_all_historical_data():
    """Populate historical data for all coins from 2021-2025."""
    await init_redis()

    # Get all coins from MarketCoordinator
    coins = MarketCoordinator.COINS
    logger.info(f"🎯 Starting historical data population for {len(coins)} coins: {coins}")

    total_years = END_YEAR - START_YEAR + 1
    total_operations = len(coins) * total_years
    completed_operations = 0

    for coin in coins:
        symbol = f"{coin}USDT"
        logger.info(f"\n{'='*60}")
        logger.info(f"🪙 Processing {symbol}")
        logger.info(f"{'='*60}")

        for year in range(START_YEAR, END_YEAR + 1):
            success = await populate_coin_data(symbol, year)
            completed_operations += 1

            if success:
                logger.info(f"✅ Completed {symbol} {year} ({completed_operations}/{total_operations})")
            else:
                logger.warning(f"⚠️ Failed {symbol} {year} ({completed_operations}/{total_operations})")

            # Small delay to be respectful to the API
            await asyncio.sleep(0.5)

    logger.info(f"\n{'='*80}")
    logger.info("🎉 HISTORICAL DATA POPULATION COMPLETED")
    logger.info(f"{'='*80}")

    # Final verification
    await verify_population()

async def verify_population():
    """Verify that historical data was populated correctly."""
    logger.info("\n🔍 VERIFYING DATA POPULATION...")

    # Test a few key timestamps from 2021
    test_timestamps = [
        1610798100,  # 2021-01-16 11:55:00 UTC (original failing case)
        1609459200,  # 2021-01-01 00:00:00 UTC
        1640995200,  # 2022-01-01 00:00:00 UTC
        1672531200,  # 2023-01-01 00:00:00 UTC
        1704067200,  # 2024-01-01 00:00:00 UTC
    ]

    coins_to_test = MarketCoordinator.COINS

    success_count = 0
    total_tests = len(test_timestamps) * len(coins_to_test)

    for symbol in coins_to_test:
        logger.info(f"\nTesting {symbol}:")
        for ts in test_timestamps:
            result = await get_cached_klines_individual(symbol, RESOLUTION, ts)
            dt = datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

            if result:
                success_count += 1
                logger.info(f"  ✅ {dt}: Found data")
            else:
                logger.warning(f"  ❌ {dt}: No data found")

    logger.info(f"\n📊 VERIFICATION RESULTS: {success_count}/{total_tests} tests passed")

    if success_count == total_tests:
        logger.info("🎉 ALL TESTS PASSED - Historical data population successful!")
    else:
        logger.warning(f"⚠️ {total_tests - success_count} tests failed - Some data may be missing")

if __name__ == "__main__":
    asyncio.run(populate_all_historical_data())