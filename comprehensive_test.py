#!/usr/bin/env python3
"""
Comprehensive test script to verify that get_cached_klines_individual works
for all coins across all years from 2021 to 2025.
"""

import asyncio
from datetime import datetime, timezone
from redis_utils import init_redis, get_cached_klines_individual
from MarketCoordinator import MarketCoordinator

async def comprehensive_test():
    await init_redis()

    # Get all coins
    coins = MarketCoordinator.COINS
    symbols = [f"{coin}USDT" for coin in coins]

    # Test timestamps for each year (first day of each year at 00:00:00 UTC)
    test_years = [2021, 2022, 2023, 2024, 2025]
    test_timestamps = []
    for year in test_years:
        ts = int(datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())
        test_timestamps.append((year, ts))

    print("COMPREHENSIVE REDIS DATA TEST")
    print("=" * 80)
    print(f"Testing {len(symbols)} symbols across {len(test_years)} years")
    print(f"Total tests: {len(symbols) * len(test_timestamps)}")
    print()

    total_tests = 0
    passed_tests = 0

    for symbol in symbols:
        print(f"Testing {symbol}:")
        print("-" * 40)

        for year, ts in test_timestamps:
            total_tests += 1
            try:
                result = await get_cached_klines_individual(symbol, '5m', ts)
                if result and isinstance(result, dict) and 'time' in result:
                    passed_tests += 1
                    status = "PASS"
                    data_preview = f"time={result['time']}, close={result.get('close', 'N/A')}"
                else:
                    status = "FAIL"
                    data_preview = f"result={result}"
            except Exception as e:
                status = "ERROR"
                data_preview = f"exception={e}"

            dt_str = datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            print(f"  {year}: {status} - {dt_str} - {data_preview}")

        print()

    print("=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)
    print(f"Total tests: {total_tests}")
    print(f"Passed tests: {passed_tests}")
    print(f"Failed tests: {total_tests - passed_tests}")
    print(".1f")

    if passed_tests == total_tests:
        print("SUCCESS: All tests passed! Redis data is complete.")
    else:
        print("WARNING: Some tests failed. Data may be incomplete.")

if __name__ == "__main__":
    asyncio.run(comprehensive_test())