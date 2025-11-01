#!/usr/bin/env python3
"""
Test script to verify that get_cached_klines_individual now works for 2021 timestamps.
"""

import asyncio
from redis_utils import init_redis, get_cached_klines_individual

async def test_2021_data():
    await init_redis()

    # Test the original failing timestamp
    result = await get_cached_klines_individual('BTCUSDT', '5m', 1610798100)
    print(f'SUCCESS: get_cached_klines_individual("BTCUSDT", "5m", 1610798100) returned: {result}')

    if result:
        print(f'   Data: time={result["time"]}, open={result["open"]}, high={result["high"]}, low={result["low"]}, close={result["close"]}, vol={result["vol"]}')

    # Test a few more timestamps
    test_timestamps = [
        1609459200,  # 2021-01-01 00:00:00 UTC
        1640995200,  # 2022-01-01 00:00:00 UTC
        1672531200,  # 2023-01-01 00:00:00 UTC
        1704067200,  # 2024-01-01 00:00:00 UTC
    ]

    for ts in test_timestamps:
        result = await get_cached_klines_individual('BTCUSDT', '5m', ts)
        status = 'OK' if result else 'FAIL'
        print(f'{status} BTCUSDT 5m {ts}: {"Found" if result else "Not found"}')

if __name__ == "__main__":
    asyncio.run(test_2021_data())