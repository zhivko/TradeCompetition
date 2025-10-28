import asyncio
import time
from datetime import datetime
from redis_utils import init_redis, fetch_klines_from_binance

async def test_binance_pagination():
    """Test how much data we can actually fetch from Binance"""
    print("Testing Binance pagination...")
    await init_redis()
    
    symbol = "BTCUSDT"
    resolution = "5m"
    
    # Test with a wide range - from Jan 1, 2021 to now
    start_ts = 1609459200  # January 1, 2021 00:00:00 UTC
    end_ts = int(time.time())  # Current time
    
    print(f"Fetching from {datetime.fromtimestamp(start_ts)} to {datetime.fromtimestamp(end_ts)}")
    
    # Try fetching with current implementation
    try:
        klines = fetch_klines_from_binance(symbol, resolution, start_ts, end_ts)
        print(f"Received {len(klines)} klines from Binance")
        
        if klines:
            print(f"First kline: {klines[0]}")
            print(f"Last kline: {klines[-1]}")
            print(f"First timestamp: {datetime.fromtimestamp(klines[0]['time'])}")
            print(f"Last timestamp: {datetime.fromtimestamp(klines[-1]['time'])}")
    except Exception as e:
        print(f"Error fetching from Binance: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_binance_pagination())