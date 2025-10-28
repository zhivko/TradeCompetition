import asyncio
import time
from datetime import datetime
from redis_utils import init_redis, get_cached_klines, get_redis_connection
from MarketCoordinator import MarketCoordinator


async def print_data_for_months():
    """Print data from Redis for January and December of each year for each coin"""
    print("Initializing Redis connection...")
    await init_redis()
    
    coins = MarketCoordinator.COINS
    resolution = "5m"
    
    # Define time ranges for January and December for each year from 2021 to 2025
    months_to_check = []
    
    # January of each year
    for year in range(2021, 2026):
        jan_start = int(datetime(year, 1, 1).timestamp())
        jan_end = int(datetime(year, 1, 31, 23, 59, 59).timestamp())
        months_to_check.append((jan_start, jan_end, f"{year}-01"))
    
    # December of each year
    for year in range(2021, 2026):
        dec_start = int(datetime(year, 12, 1).timestamp())
        dec_end = int(datetime(year, 12, 31, 23, 59, 59).timestamp())
        months_to_check.append((dec_start, dec_end, f"{year}-12"))
    
    redis = await get_redis_connection()
    
    for coin in coins:
        symbol = f"{coin}USDT"
        print(f"\n{'='*60}")
        print(f"DATA FOR {coin}")
        print(f"{'='*60}")
        
        for start_ts, end_ts, month_str in months_to_check:
            print(f"\n--- {month_str} ---")
            
            try:
                cached_klines = await get_cached_klines(symbol, resolution, start_ts, end_ts)
                
                if cached_klines:
                    print(f"Found {len(cached_klines)} records")
                    # Print first and last few records to see the range
                    if len(cached_klines) <= 10:
                        for kline in cached_klines:
                            dt = datetime.fromtimestamp(kline['time'])
                            print(f"  {dt.strftime('%Y-%m-%d %H:%M:%S')} - O:{kline['open']}, H:{kline['high']}, L:{kline['low']}, C:{kline['close']}")
                    else:
                        # Print first 3 and last 3 records
                        for i, kline in enumerate(cached_klines):
                            if i < 3 or i >= len(cached_klines) - 3:
                                dt = datetime.fromtimestamp(kline['time'])
                                print(f"  {dt.strftime('%Y-%m-%d %H:%M:%S')} - O:{kline['open']}, H:{kline['high']}, L:{kline['low']}, C:{kline['close']}")
                                if i == 2:  # After first 3, add "..." if there are more
                                    if len(cached_klines) > 6:
                                        print("  ...")
                        if len(cached_klines) <= 6:
                            # If we already printed everything, add a separator
                            print()
                else:
                    print("No data found")
            except Exception as e:
                print(f"Error fetching data for {month_str}: {e}")

if __name__ == "__main__":
    asyncio.run(print_data_for_months())