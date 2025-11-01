#!/usr/bin/env python3
"""
Script to repopulate the sorted sets for all coins with existing individual kline data.
"""

import asyncio
import json
from redis_utils import get_redis_connection, get_sorted_set_key

COINS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "SOLUSDT"]

async def repopulate_coin(symbol: str, resolution: str = "5m"):
    """Repopulate the sorted set for a specific coin."""
    redis = await get_redis_connection()
    sorted_set_key = get_sorted_set_key(symbol, resolution)

    print(f"Repopulating {symbol} sorted set: {sorted_set_key}")

    # Get all individual kline keys for this coin
    pattern = f"kline:{symbol}:{resolution}:*"
    keys = []
    async for key in redis.scan_iter(match=pattern):
        keys.append(key)

    print(f"Found {len(keys)} individual {symbol} kline keys")

    if not keys:
        print(f"No {symbol} keys found to repopulate")
        return

    # Clear existing sorted set first
    await redis.delete(sorted_set_key)
    print(f"Cleared existing {symbol} sorted set")

    # Process in batches to avoid memory issues
    batch_size = 1000
    total_processed = 0

    async with redis.pipeline() as pipe:
        for i, key in enumerate(keys):
            # Get the data from the individual key
            data_str = await redis.get(key)
            if not data_str:
                continue

            try:
                # Parse the JSON data
                kline_data = json.loads(data_str)
                timestamp = kline_data["time"]

                # Add to sorted set
                await pipe.zadd(sorted_set_key, {data_str: timestamp})

                total_processed += 1

                # Execute in batches
                if (i + 1) % batch_size == 0:
                    await pipe.execute()
                    print(f"Processed {i + 1}/{len(keys)} {symbol} keys")

            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON for key {key}: {e}")
                continue

        # Execute any remaining commands
        await pipe.execute()

    print(f"Successfully repopulated {total_processed} {symbol} entries in sorted set")

    # Verify the sorted set has data
    cardinality = await redis.zcard(sorted_set_key)
    print(f"{symbol} sorted set now has {cardinality} entries")

    # Check a sample
    sample = await redis.zrange(sorted_set_key, 0, 2, withscores=True)
    if sample:
        print(f"Sample {symbol} data:")
        for data_str, score in sample:
            data = json.loads(data_str)
            print(f"  Time: {data['time']}, Price: {data['close']}")

async def main():
    """Repopulate all coins."""
    for coin in COINS:
        await repopulate_coin(coin)
        print(f"--- Completed {coin} ---\n")

if __name__ == "__main__":
    asyncio.run(main())