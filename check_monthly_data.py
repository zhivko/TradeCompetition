#!/usr/bin/env python3
"""
Script to check monthly data distribution in Redis sorted sets from 2021 to 2025.
"""

import asyncio
from datetime import datetime
from redis_utils import get_redis_connection

COINS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "SOLUSDT"]

def get_month_ranges(year):
    """Get timestamp ranges for each month in a year."""
    ranges = []
    for month in range(1, 13):
        # First day of month
        start_date = datetime(year, month, 1)
        start_ts = int(start_date.timestamp())

        # First day of next month (or Jan 1 next year)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        end_ts = int(end_date.timestamp()) - 1  # End of last second of month

        ranges.append((month, start_ts, end_ts))
    return ranges

async def check_monthly_data():
    """Check data distribution by month for each coin."""
    redis = await get_redis_connection()

    print("MONTHLY DATA DISTRIBUTION (2021-2025)\n")

    for coin in COINS:
        print(f"COIN: {coin}")
        print("-" * 50)

        total_entries = 0

        for year in range(2021, 2026):  # 2021 to 2025
            print(f"  {year}:")
            monthly_ranges = get_month_ranges(year)

            for month, start_ts, end_ts in monthly_ranges:
                count = await redis.zcount(f"zset:kline:{coin}:5m", start_ts, end_ts)
                total_entries += count

                if count > 0:
                    month_name = datetime(year, month, 1).strftime("%b")
                    print("5d")

            print(f"    Total for {year}: {total_entries} entries")
            total_entries = 0  # Reset for next year

        # Overall total
        total_all = await redis.zcard(f"zset:kline:{coin}:5m")
        print(f"    GRAND TOTAL: {total_all} entries\n")

if __name__ == "__main__":
    asyncio.run(check_monthly_data())