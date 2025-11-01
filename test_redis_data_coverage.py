#!/usr/bin/env python3
"""
Test script to check Redis data coverage for BTCUSDT from 2021 to 2025.
Uses binary search to efficiently count data and compares against expected counts.
"""

import asyncio
from datetime import datetime, timezone
from redis_utils import get_cached_klines_individual
from typing import List, Dict, Any
import logging
import calendar

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Coin to test
COIN = "BTCUSDT"

# Resolution to test
RESOLUTION = "5m"

# Time range: 2021 to 2025 inclusive
START_YEAR = 2021
END_YEAR = 2025

def get_month_range(year: int, month: int) -> tuple[int, int]:
    """Get start and end timestamps for a given month."""
    # First day of the month at 00:00:00 UTC
    start_ts = int(datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())

    # First day of next month at 00:00:00 UTC
    if month == 12:
        end_ts = int(datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())
    else:
        end_ts = int(datetime(year, month + 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())

    return start_ts, end_ts

def get_expected_monthly_count(year: int, month: int) -> int:
    """Calculate expected number of 5-minute intervals in a month."""
    # Get number of days in the month
    days_in_month = calendar.monthrange(year, month)[1]

    # Each day has 24 * 60 / 5 = 288 five-minute intervals
    return days_in_month * 288

async def count_data_in_range(symbol: str, start_ts: int, end_ts: int) -> int:
    """Use binary search to efficiently count data points in a timestamp range."""
    # Generate all possible 5-minute timestamps in the range
    timestamps = []
    current_ts = start_ts
    while current_ts < end_ts:
        timestamps.append(current_ts)
        current_ts += 300  # 5 minutes in seconds

    # Use binary search to find the first and last valid data points
    left, right = 0, len(timestamps) - 1
    first_valid = -1
    last_valid = -1

    # Find first valid timestamp
    while left <= right:
        mid = (left + right) // 2
        data = await get_cached_klines_individual(symbol, RESOLUTION, timestamps[mid])
        if data is not None:
            first_valid = mid
            right = mid - 1
        else:
            left = mid + 1

    # Find last valid timestamp
    left, right = 0, len(timestamps) - 1
    while left <= right:
        mid = (left + right) // 2
        data = await get_cached_klines_individual(symbol, RESOLUTION, timestamps[mid])
        if data is not None:
            last_valid = mid
            left = mid + 1
        else:
            right = mid - 1

    if first_valid == -1 or last_valid == -1:
        return 0

    # Count consecutive data points from first to last
    count = 0
    for i in range(first_valid, last_valid + 1):
        data = await get_cached_klines_individual(symbol, RESOLUTION, timestamps[i])
        if data is not None:
            count += 1

    return count

async def test_btc_months():
    """Test BTCUSDT data coverage for all months from 2021 to 2025."""
    logger.info(f"Starting Redis data coverage test for {COIN} 2021-2025 (monthly)")

    warnings = []

    for year in range(START_YEAR, END_YEAR + 1):
        logger.info(f"\n=== Testing Year {year} ===")

        for month in range(1, 13):
            # Skip future months in current year
            current_year = datetime.now(timezone.utc).year
            current_month = datetime.now(timezone.utc).month
            if year == current_year and month > current_month:
                break

            month_name = datetime(year, month, 1).strftime('%B')
            expected_count = get_expected_monthly_count(year, month)
            start_ts, end_ts = get_month_range(year, month)

            logger.info(f"  {month_name} {year} (expected: {expected_count} entries):")

            try:
                actual_count = await count_data_in_range(COIN, start_ts, end_ts)

                # Calculate percentage
                percentage = (actual_count / expected_count * 100) if expected_count > 0 else 0

                status = "✅" if abs(actual_count - expected_count) < (expected_count * 0.1) else "⚠️"

                logger.info(f"    {COIN}: {actual_count}/{expected_count} ({percentage:.1f}%) {status}")

                # Add warning if data is significantly missing
                if actual_count < expected_count * 0.5:  # Less than 50% of expected data
                    warnings.append(f"{COIN} {month_name} {year}: Only {actual_count}/{expected_count} entries ({percentage:.1f}%)")

            except Exception as e:
                logger.error(f"    {COIN}: ERROR - {e}")
                warnings.append(f"{COIN} {month_name} {year}: ERROR - {e}")

    # Summary of warnings
    if warnings:
        logger.info("\n" + "="*80)
        logger.info("⚠️  DATA GAPS DETECTED")
        logger.info("="*80)
        for warning in warnings:
            logger.warning(f"  {warning}")
    else:
        logger.info("\n" + "="*80)
        logger.info("✅ ALL MONTHS HAVE ADEQUATE DATA COVERAGE")
        logger.info("="*80)

if __name__ == "__main__":
    asyncio.run(test_btc_months())