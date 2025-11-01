
#!/usr/bin/env python3
"""
Script to repopulate the Redis sorted set with existing individual kline data.
This fixes the issue where individual kline keys exist but the sorted set is missing entries.
"""

import asyncio
import json
from redis_utils import get_redis_connection, get_sorted_set_key

async def repopulate_sorted_set(symbol: str = "BTCUSDT", resolution: str = "5m"):
    """Repopulate the sorted set with existing individual kline data."""
    redis = await get_redis_connection()
    sorted_set_key = get_sorted_set_key(symbol, resolution)

    print(f"Repopulating sorted set: {sorted_set_key}")

    # Get all individual kline keys for this symbol and resolution
    pattern = f"kline:{symbol}:{resolution}:*"
    keys = []
    async for key in redis.scan_iter(match=pattern):
        keys.append(key)

    print(f"Found {len(keys)} individual kline keys")

    if not keys:
        print("No keys found to repopulate")
        return

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

                # Remove any existing entry with this timestamp
                await pipe.zremrangebyscore(sorted_set_key, timestamp, timestamp)
                # Add the new entry
                await pipe.zadd(sorted_set_key, {data_str: timestamp})

                total_processed += 1

                # Execute in batches
                if (i + 1) % batch_size == 0:
                    await pipe.execute()
                    print(f"Processed {i + 1}/{len(keys)} keys")

            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON for key {key}: {e}")
                continue

        # Execute any remaining commands
        await pipe.execute()

    print(f"Successfully repopulated {total_processed} entries in sorted set {sorted_set_key}")

    # Verify the sorted set has data
    cardinality = await redis.zcard(sorted_set_key)
    print(f"Sorted set now has {cardinality} entries")

if __name__ == "__main__":
    asyncio.run(repopulate_sorted_set())