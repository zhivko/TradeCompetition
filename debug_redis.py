#!/usr/bin/env python3
"""
Debug script to check Redis data for BTCUSDT 5m klines.
"""

import asyncio
from redis_utils import init_redis, get_cached_klines_individual, get_sorted_set_key, get_redis_connection

async def debug_redis():
    await init_redis()

    # Check if the sorted set exists and has data
    redis = await get_redis_connection()
    sorted_set_key = get_sorted_set_key('BTCUSDT', '5m')
    print(f'Checking sorted set: {sorted_set_key}')

    exists = await redis.exists(sorted_set_key)
    print(f'Sorted set exists: {exists}')

    if exists:
        count = await redis.zcard(sorted_set_key)
        print(f'Number of elements in sorted set: {count}')

        if count > 0:
            # Get some sample data
            samples = await redis.zrange(sorted_set_key, 0, 4, withscores=True)
            print('First 5 samples from sorted set:')
            for member, score in samples:
                print(f'  Score: {score}, Member preview: {str(member)[:100]}...')

    # Check the specific key
    result = await get_cached_klines_individual('BTCUSDT', '5m', 1610798100)
    print(f'Result for BTCUSDT 5m 1610798100: {result}')

    # Check if there are any BTCUSDT keys at all
    pattern = 'kline:BTCUSDT:5m:*'
    keys = []
    async for key in redis.scan_iter(match=pattern):
        keys.append(key)
        if len(keys) >= 10:  # Limit to first 10
            break
    print(f'Found {len(keys)} BTCUSDT 5m keys (showing first 10):')
    for key in keys:
        print(f'  {key}')

    # Check what data range actually exists
    if exists and count > 0:
        # Get min and max scores
        min_score = await redis.zrange(sorted_set_key, 0, 0, withscores=True)
        max_score = await redis.zrange(sorted_set_key, -1, -1, withscores=True)
        if min_score and max_score:
            min_ts = int(min_score[0][1])
            max_ts = int(max_score[0][1])
            print(f'Data range: {min_ts} to {max_ts}')
            print(f'Query timestamp 1610798100 is within range: {min_ts <= 1610798100 <= max_ts}')

if __name__ == "__main__":
    asyncio.run(debug_redis())