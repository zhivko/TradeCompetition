#!/usr/bin/env python3
"""
Script to fix all sorted sets by adding missing historical data from individual keys.
"""

import asyncio
import json
from redis_utils import get_redis_connection, get_sorted_set_key

COINS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "SOLUSDT"]

async def fix_sorted_set(symbol: str, resolution: str = "5m"):
    """Fix the sorted set by adding missing historical data."""
    redis = await get_redis_connection()
    sorted_set_key = get_sorted_set_key(symbol, resolution)

    print(f"Fixing {symbol} sorted set: {sorted_set_key}")

    # Get all individual kline keys for this coin
    pattern = f"kline:{symbol}:{resolution}:*"
    keys = []
    async for key in redis.scan_iter(match=pattern):
        keys.append(key)

    print(f"Found {len(keys)} individual {symbol} kline keys")

    if not keys:
        print(f"No {symbol} keys found")
        return

    # Get current sorted set members to check what's missing
    existing_scores = await redis.zrange(sorted_set_key, 0, -1, withscores=True)
    existing_timestamps = {int(score) for _, score in existing_scores}

    print(f"Current sorted set has {len(existing_timestamps)} entries")

    # Process keys that aren't in the sorted set
    added_count = 0
    async with redis.pipeline() as pipe:
        for key in keys:
            # Extract timestamp from key
            parts = key.split(":")
            if len(parts) == 4:
                try:
                    timestamp = int(parts[3])
                except ValueError:
                    continue

                # Skip if already in sorted set
                if timestamp in existing_timestamps:
                    continue

                # Get the data from the individual key
                data_str = await redis.get(key)
                if not data_str:
                    continue

                try:
                    # Parse the JSON data
                    kline_data = json.loads(data_str)

                    # Add to sorted set
                    await pipe.zadd(sorted_set_key, {data_str: timestamp})
                    added_count += 1

                    # Execute in batches
                    if added_count % 1000 == 0:
                        await pipe.execute()
                        print(f"Added {added_count} {symbol} entries so far")

                except json.JSONDecodeError as e:
                    print(f"Failed to parse JSON for key {key}: {e}")
                    continue

        # Execute any remaining commands
        await pipe.execute()

    print(f"Added {added_count} missing {symbol} entries to sorted set")

    # Verify the sorted set has data
    cardinality = await redis.zcard(sorted_set_key)
    print(f"{symbol} sorted set now has {cardinality} entries")

    # Check a sample of historical data
    historical_sample = await redis.zrangebyscore(sorted_set_key, 1609459200, 1609459200 + 86400, withscores=True)
    if historical_sample:
        print(f"Sample {symbol} historical data (2021):")
        for data_str, score in historical_sample[:3]:
            data = json.loads(data_str)
            print(f"  Time: {data['time']}, Price: {data['close']}")

async def main():
    """Fix all coins."""
    for coin in COINS:
        await fix_sorted_set(coin)
        print(f"--- Completed {coin} ---\n")

if __name__ == "__main__":
    asyncio.run(main())