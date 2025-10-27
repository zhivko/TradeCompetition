import asyncio
import aiohttp
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List
import os
from dotenv import load_dotenv

# Import shared XML manager
from XmlManager import TradingXMLManager
from Agent import TradeXMLManager
from BinanceLiquidationClient import BinanceLiquidationClient

# Import numpy for array operations
import numpy as np

# Import ta-lib for technical indicators
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    print("Warning: ta-lib not available, using custom calculations")


def calculate_ema(prices: List[float], period: int) -> float:
    """Calculate EMA (Exponential Moving Average) for a given period"""
    if len(prices) < period:
        # If not enough data, return simple average
        return sum(prices) / len(prices) if prices else 0
    
    # Take the last 'period' prices
    data = prices[-period:]
    
    # Smoothing factor
    multiplier = 2 / (period + 1)
    
    # Calculate EMA
    ema = data[0]  # Start with the first value
    for price in data[1:]:
        ema = (price * multiplier) + (ema * (1 - multiplier))
    
    return ema


def calculate_simple_macd(prices: List[float]) -> tuple:
    """Calculate a simplified MACD value - difference between 12 and 26 period EMAs"""
    if len(prices) < 26:
        return (0, 0, 0)
    
    ema12 = calculate_ema(prices[-26:], 12)  # Use last 26 prices for 12 EMA
    ema26 = calculate_ema(prices[-26:], 26)  # Use last 26 prices for 26 EMA
    
    macd_line = ema12 - ema26
    
    # Calculate signal line (9-period EMA of MACD line)
    signal_line = macd_line * 0.8  # Approximate signal line
    histogram = macd_line - signal_line
    
    return (macd_line, signal_line, histogram)


def calculate_rsi(prices: List[float], period: int) -> float:
    """Calculate RSI (Relative Strength Index) for a given period"""
    if len(prices) < period + 1:
        return 50.0  # Neutral value if not enough data
    
    # Get the last 'period + 1' prices
    data = prices[-(period + 1):]
    
    # Calculate gains and losses
    gains = []
    losses = []
    
    for i in range(1, len(data)):
        change = data[i] - data[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    # Calculate average gain and loss
    if len(gains) < period or len(losses) < period:
        return 50.0
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_atr(high_prices: List[float], low_prices: List[float], close_prices: List[float], period: int) -> float:
    """Calculate ATR (Average True Range) for a given period"""
    if len(close_prices) < period + 1:
        return 0.0  # Return 0 if not enough data
    
    # Calculate True Range for each period
    tr_values = []
    for i in range(1, min(len(close_prices), period + 1)):
        high = high_prices[i] if i < len(high_prices) else close_prices[i]
        low = low_prices[i] if i < len(low_prices) else close_prices[i]
        prev_close = close_prices[i-1]
        
        # True Range = max(High - Low, abs(High - Previous Close), abs(Low - Previous Close))
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        tr_values.append(tr)
    
    # Calculate ATR as simple moving average of TR values
    if len(tr_values) >= period:
        atr = sum(tr_values[-period:]) / period
    else:
        atr = sum(tr_values) / len(tr_values) if tr_values else 0
    
    return atr


# Load environment variables
load_dotenv()


class BinanceMarketDataFetcher:
    """Class to fetch market data from Binance API"""

    def __init__(self):
        self.base_url = "https://api.binance.com"  # For spot market data
        self.futures_url = "https://fapi.binance.com"  # For futures market data
        self.spot_session = None  # For spot API (no auth required)
        self.futures_session = None  # For futures API (auth required)
        # Load API keys
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.secret_key = os.getenv("BINANCE_SECRET_KEY")

    async def __aenter__(self):
        # Create separate sessions for spot and futures
        # Spot session: no auth headers but with user agent
        spot_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.spot_session = aiohttp.ClientSession(headers=spot_headers)

        # Futures session: with API key headers if available, plus user agent
        futures_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        if self.api_key:
            futures_headers["X-MBX-APIKEY"] = self.api_key
        self.futures_session = aiohttp.ClientSession(headers=futures_headers)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.spot_session:
            await self.spot_session.close()
        if self.futures_session:
            await self.futures_session.close()
    
    async def get_ticker_price(self, symbol: str) -> float:
        """Get current ticker price for a symbol"""
        endpoint = f"{self.base_url}/api/v3/ticker/price"
        params = {"symbol": symbol}

        try:
            async with self.spot_session.get(endpoint, params=params) as response:
                if response.status != 200:
                    print(f"Error fetching ticker price for {symbol}: {response.status}")
                    return 0.0

                data = await response.json()
                return float(data['price'])
        except Exception as e:
            print(f"Exception fetching ticker price for {symbol}: {e}")
            return 0.0
    
    async def get_klines(self, symbol: str, interval: str = "3m", limit: int = 10) -> List:
        """Get kline/candlestick data for a symbol"""
        # Use spot API for klines since it doesn't require authentication
        endpoint = f"{self.base_url}/api/v3/klines"
        params = {
            "symbol": symbol,  # Use symbol as-is, without adding USDT
            "interval": interval,
            "limit": limit
        }

        try:
            async with self.spot_session.get(endpoint, params=params) as response:
                print(f"DEBUG: Kline request for {symbol} {interval}: status {response.status}")
                if response.status != 200:
                    print(f"Error fetching klines for {symbol}: {response.status}")
                    # Check if the symbol exists by trying ticker price first
                    try:
                        async with self.spot_session.get(f"{self.base_url}/api/v3/ticker/price", params={"symbol": f"{symbol}USDT"}) as price_response:
                            if price_response.status == 200:
                                price_data = await price_response.json()
                                print(f"DEBUG: Symbol {symbol}USDT exists, price: {price_data.get('price', 'unknown')}")
                            else:
                                print(f"DEBUG: Symbol {symbol}USDT does not exist or is not available: {price_response.status}")
                                # Try without USDT suffix for spot pairs
                                try:
                                    async with self.spot_session.get(f"{self.base_url}/api/v3/ticker/price", params={"symbol": symbol}) as alt_response:
                                        if alt_response.status == 200:
                                            alt_data = await alt_response.json()
                                            print(f"DEBUG: Symbol {symbol} exists without USDT, price: {alt_data.get('price', 'unknown')}")
                                        else:
                                            print(f"DEBUG: Symbol {symbol} also does not exist: {alt_response.status}")
                                except Exception as alt_e:
                                    print(f"DEBUG: Error checking alternative symbol: {alt_e}")
                    except Exception as price_e:
                        print(f"DEBUG: Error checking symbol existence: {price_e}")
                    return []

                data = await response.json()
                print(f"DEBUG: Received {len(data) if data else 0} kline records for {symbol} {interval}")
                # Return full kline data: [open, high, low, close, volume, ...]
                return [[float(kline[1]), float(kline[2]), float(kline[3]), float(kline[4]), float(kline[5])] for kline in data]  # [1]=open, [2]=high, [3]=low, [4]=close, [5]=volume
        except Exception as e:
            print(f"Exception fetching klines for {symbol}: {e}")
            return []
    
    async def get_24hr_ticker(self, symbol: str) -> Dict:
        """Get 24hr ticker data for a symbol"""
        endpoint = f"{self.base_url}/api/v3/ticker/24hr"
        params = {"symbol": symbol}

        try:
            async with self.spot_session.get(endpoint, params=params) as response:
                if response.status != 200:
                    print(f"Error fetching 24hr ticker for {symbol}: {response.status}")
                    return {}

                return await response.json()
        except Exception as e:
            print(f"Exception fetching 24hr ticker for {symbol}: {e}")
            return {}
    
    async def get_open_interest(self, symbol: str) -> Dict:
        """Get open interest data for a symbol (futures)"""
        # Binance futures API for open interest
        endpoint = f"{self.futures_url}/fapi/v1/openInterest"
        params = {"symbol": f"{symbol}USDT"}  # Assuming USDT futures

        try:
            async with self.futures_session.get(endpoint, params=params) as response:
                if response.status != 200:
                    print(f"Error fetching open interest for {symbol}: {response.status}")
                    # Return default values when API call fails
                    return {
                        "symbol": f"{symbol}USDT",
                        "openInterest": "0.0",
                        "time": int(datetime.now().timestamp() * 1000)  # Current timestamp in milliseconds
                    }

                return await response.json()
        except Exception as e:
            print(f"Exception fetching open interest for {symbol}: {e}")
            # Return default values when exception occurs
            return {
                "symbol": f"{symbol}USDT",
                "openInterest": "0.0",
                "time": int(datetime.now().timestamp() * 1000)  # Current timestamp in milliseconds
            }
    
    async def get_liquidation_orders(self, symbol: str) -> Dict[str, List | int]:
        """Get liquidation orders data for a symbol (futures)."""
        # Ensure symbol is in correct format (e.g., BNBUSDT)
        symbol = symbol.upper() + "USDT" if not symbol.endswith("USDT") else symbol.upper()
        endpoint = f"{self.futures_url}/fapi/v1/allForceOrders"
        params = {
            "symbol": symbol,
            "limit": 100,  # Max 1000, default 50
            # Optional: Add time range (in milliseconds)
            # "startTime": int(time.time() * 1000) - 24*60*60*1000,  # Last 24 hours
            # "endTime": int(time.time() * 1000),
        }

        try:
            async with self.futures_session.get(endpoint, params=params) as response:
                if response.status != 200:
                    try:
                        error_data = await response.json()
                        print(f"Error fetching liquidation orders for {symbol}: {response.status}, Details: {error_data}")
                    except Exception:
                        error_text = await response.text()
                        print(f"Error fetching liquidation orders for {symbol}: {response.status}, Details: {error_text}")
                    return {"rows": [], "total": 0}

                data = await response.json()
                if not isinstance(data, list):
                    print(f"Unexpected response format for {symbol}: {data}")
                    return {"rows": [], "total": 0}

                return {"rows": data, "total": len(data)}
        except Exception as e:
            print(f"Exception fetching liquidation orders for {symbol}: {e}")
            return {"rows": [], "total": 0}
    
    async def get_funding_rate(self, symbol: str) -> Dict:
        """Get funding rate data for a symbol (futures)"""
        # Binance futures API for funding rate - both USDT and USD (coin-margined) 
        funding_rates = {}
        
        # Get USDT-margined funding rate
        usdt_endpoint = f"{self.futures_url}/fapi/v1/fundingRate"
        usdt_params = {"symbol": f"{symbol}USDT"}

        try:
            async with self.futures_session.get(usdt_endpoint, params=usdt_params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data:  # Check if list is not empty
                        latest_funding = data[-1]  # Get the most recent funding rate
                        funding_rates["usdt_funding_rate"] = float(latest_funding.get("fundingRate", 0))
                        funding_rates["usdt_funding_timestamp"] = int(latest_funding.get("fundingTime", 0))
                        funding_rates["usdt_next_funding_time"] = int(latest_funding.get("nextFundingTime", 0))
                    else:
                        # Default values if no data returned
                        funding_rates["usdt_funding_rate"] = 0.0
                        funding_rates["usdt_funding_timestamp"] = 0
                        funding_rates["usdt_next_funding_time"] = 0
                else:
                    print(f"Error fetching USDT funding rate for {symbol}: {response.status}")
                    # Default values on error
                    funding_rates["usdt_funding_rate"] = 0.0
                    funding_rates["usdt_funding_timestamp"] = 0
                    funding_rates["usdt_next_funding_time"] = 0
        except Exception as e:
            print(f"Exception fetching USDT funding rate for {symbol}: {e}")
            # Default values on exception
            funding_rates["usdt_funding_rate"] = 0.0
            funding_rates["usdt_funding_timestamp"] = 0
            funding_rates["usdt_next_funding_time"] = 0

        # Get USD (coin-margined) funding rate if available
        try:
            usd_endpoint = f"{self.futures_url}/dapi/v1/fundingRate"
            usd_params = {"symbol": f"{symbol}USD_PERP"}  # Coin-margined futures

            async with self.futures_session.get(usd_endpoint, params=usd_params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data:  # Check if list is not empty
                        latest_funding = data[-1]  # Get the most recent funding rate
                        funding_rates["usd_funding_rate"] = float(latest_funding.get("fundingRate", 0))
                        funding_rates["usd_funding_timestamp"] = int(latest_funding.get("fundingTime", 0))
                        funding_rates["usd_next_funding_time"] = int(latest_funding.get("nextFundingTime", 0))
                    else:
                        # Default values if no data returned
                        funding_rates["usd_funding_rate"] = 0.0
                        funding_rates["usd_funding_timestamp"] = 0
                        funding_rates["usd_next_funding_time"] = 0
                else:
                    # Some coins may not have USD perpetual futures, so we set to 0
                    funding_rates["usd_funding_rate"] = 0.0
                    funding_rates["usd_funding_timestamp"] = 0
                    funding_rates["usd_next_funding_time"] = 0
        except Exception as e:
            # Some coins may not have USD perpetual futures, so we set to 0
            funding_rates["usd_funding_rate"] = 0.0
            funding_rates["usd_funding_timestamp"] = 0
            funding_rates["usd_next_funding_time"] = 0
        
        return funding_rates


class MarketCoordinator:
    """Market coordinator that prepares state of market each minute and pulls information from Binance"""

    def __init__(self, xml_file_path: str = "trade.xml"):
        self.coins = ["BTC", "ETH", "BNB", "XRP", "DOGE"]  # As specified in the requirements
        self.xml_manager = TradingXMLManager(xml_file_path)
        self.trade_xml_manager = TradeXMLManager(xml_file_path)
        self.xml_root = self.xml_manager.root
        self.liquidation_client = BinanceLiquidationClient(tracked_symbols=self.coins)
        
    def _initialize_xml(self):
        """Initialize is now handled by the shared XML manager"""
        # No need to implement this anymore as it's handled by shared manager
        pass
    
    async def prepare_market_state(self) -> str:
        """Prepare the market state by fetching data from Binance and return a user prompt"""

        # Start background liquidation collection if not already running
        await self.liquidation_client.start_background_collection()

        async with BinanceMarketDataFetcher() as fetcher:
            # Prepare the market data section
            market_state_parts = [
                f"USER_PROMPT",
                f"It has been {int(datetime.now().timestamp() // 60)} minutes since you started trading. The current time is {datetime.now()} and you've been invoked {int(datetime.now().timestamp() // 60)} times. Below, we are providing you with a variety of state data, price data, and predictive signals so you can discover alpha. Below that is your current account information, value, performance, positions, etc.",
                f"",
                f"ALL OF THE PRICE OR SIGNAL DATA BELOW IS ORDERED: OLDEST → NEWEST",
                f"",
                f"Timeframes note: Unless stated otherwise in a section title, intraday series are provided at 3‑minute intervals. If a coin uses a different interval, it is explicitly stated in that coin's section.",
                f"",
                f"CURRENT MARKET STATE FOR ALL COINS"
            ]
            
            all_coin_data = {}
            
            # Fetch data for each coin
            for coin in self.coins:
                symbol = f"{coin}USDT"  # Binance futures pairs typically use USDT
                
                # Get current price
                current_price = await fetcher.get_ticker_price(symbol)
                
                # Get kline data for indicators (3-minute intervals) - getting more data points for proper calculations
                # Need at least 50 data points to properly calculate EMA20, MACD (12,26,9), and RSI
                # But we'll only keep the last 10 values for the series in the XML
                kline_data = await fetcher.get_klines(symbol, "3m", 50)
                kline_prices = [k[3] for k in kline_data]  # Close prices
                kline_highs = [k[1] for k in kline_data]   # High prices
                kline_lows = [k[2] for k in kline_data]    # Low prices
                kline_volumes = [k[4] for k in kline_data] # Volume data

                # Get longer term kline data for 4-hour timeframe (request more data for proper calculations)
                print(f"DEBUG: Fetching 4h klines for {symbol}")
                kline_4h_data = await fetcher.get_klines(symbol, "4h", 200)  # Request more data for proper calculations
                if not kline_4h_data or len(kline_4h_data) < 100:
                    print(f"DEBUG: 4h failed or insufficient data ({len(kline_4h_data) if kline_4h_data else 0} records), trying 1h for {symbol}")
                    kline_4h_data = await fetcher.get_klines(symbol, "1h", 200)
                    if not kline_4h_data or len(kline_4h_data) < 100:
                        print(f"DEBUG: 1h also failed or insufficient data ({len(kline_4h_data) if kline_4h_data else 0} records), using 3m data for {symbol}")
                        # Last resort: use 3m data for calculations
                        kline_4h_data = kline_data[:200] if len(kline_data) >= 200 else kline_data

                kline_4h_prices = [k[3] for k in kline_4h_data] if kline_4h_data else []  # Close prices
                kline_4h_highs = [k[1] for k in kline_4h_data] if kline_4h_data else []   # High prices
                kline_4h_lows = [k[2] for k in kline_4h_data] if kline_4h_data else []    # Low prices
                kline_4h_volumes = [k[4] for k in kline_4h_data] if kline_4h_data else [] # Volume data
                print(f"DEBUG: Final data for {symbol}: {len(kline_4h_prices)} prices, {len(kline_4h_highs)} highs, {len(kline_4h_lows)} lows, {len(kline_4h_volumes)} volumes")

                # Get liquidation orders data from WebSocket client
                symbol_usdt = f"{coin}USDT"
                top_liquidations = self.liquidation_client.get_top_liquidations(symbol_usdt)
                liquidation_orders = {"rows": top_liquidations, "total": len(top_liquidations)}

                # Get open interest
                open_interest = await fetcher.get_open_interest(coin)

                # Get funding rate
                funding_data = await fetcher.get_funding_rate(coin)

                # Use the USDT funding rate for the display, fallback to 0 if not available
                funding_rate = funding_data.get("usdt_funding_rate", 0.0)

                # Calculate indicators from the price data
                # Calculate EMA20 from kline prices
                current_ema20 = calculate_ema(kline_prices, 20) if len(kline_prices) >= 20 else current_price

                # Calculate MACD (12, 26, 9) from kline prices
                # Using a simplified calculation - full MACD would need more data points
                current_macd = calculate_simple_macd(kline_prices) if len(kline_prices) >= 26 else (0, 0, 0)

                # Calculate RSI from kline prices
                current_rsi = calculate_rsi(kline_prices, 7) if len(kline_prices) >= 7 else 50.0  # Neutral value

                # Generate series data based on kline prices
                ema_20_series = [calculate_ema(kline_prices[:i+1], 20) if i >= 19 else kline_prices[i] for i in range(len(kline_prices))]
                macd_series = [calculate_simple_macd(kline_prices[:i+1])[0] if i >= 25 else 0 for i in range(len(kline_prices))]
                rsi_7_series = [calculate_rsi(kline_prices[:i+1], 7) if i >= 6 else 50.0 for i in range(len(kline_prices))]
                rsi_14_series = [calculate_rsi(kline_prices[:i+1], 14) if i >= 13 else 50.0 for i in range(len(kline_prices))]

                # Calculate long-term indicators from 4-hour data using ta-lib if available
                print(f"DEBUG: Starting calculations for {symbol}, TALIB_AVAILABLE={TALIB_AVAILABLE}, data_len={len(kline_4h_prices)}")

                if TALIB_AVAILABLE and len(kline_4h_prices) >= 50:
                    try:
                        # Convert to numpy arrays
                        prices_np = np.array(kline_4h_prices, dtype=float)
                        highs_np = np.array(kline_4h_highs, dtype=float)
                        lows_np = np.array(kline_4h_lows, dtype=float)

                        # Calculate EMAs using ta-lib
                        ema20_result = talib.EMA(prices_np, timeperiod=20)
                        ema50_result = talib.EMA(prices_np, timeperiod=50)

                        long_term_ema_20 = float(ema20_result[-1]) if len(ema20_result) > 0 and not np.isnan(ema20_result[-1]) else current_price
                        long_term_ema_50 = float(ema50_result[-1]) if len(ema50_result) > 0 and not np.isnan(ema50_result[-1]) else current_price

                        # Calculate ATR using ta-lib
                        atr3_result = talib.ATR(highs_np, lows_np, prices_np, timeperiod=3)
                        atr14_result = talib.ATR(highs_np, lows_np, prices_np, timeperiod=14)

                        atr_3_period = float(atr3_result[-1]) if len(atr3_result) > 0 and not np.isnan(atr3_result[-1]) else current_price * 0.01
                        atr_14_period = float(atr14_result[-1]) if len(atr14_result) > 0 and not np.isnan(atr14_result[-1]) else current_price * 0.02

                        print(f"DEBUG: ta-lib calculations for {symbol}: EMA20={long_term_ema_20}, EMA50={long_term_ema_50}, ATR3={atr_3_period}, ATR14={atr_14_period}")
                    except Exception as e:
                        print(f"DEBUG: ta-lib calculation error for {symbol}: {e}, falling back to custom")
                        # Fallback to custom calculations
                        long_term_ema_20 = calculate_ema(kline_4h_prices, 20) if len(kline_4h_prices) >= 20 else current_price
                        long_term_ema_50 = calculate_ema(kline_4h_prices, 50) if len(kline_4h_prices) >= 50 else current_price
                        atr_3_period = calculate_atr(kline_4h_highs, kline_4h_lows, kline_4h_prices, 3) if len(kline_4h_prices) >= 3 else current_price * 0.01
                        atr_14_period = calculate_atr(kline_4h_highs, kline_4h_lows, kline_4h_prices, 14) if len(kline_4h_prices) >= 14 else current_price * 0.02
                else:
                    print(f"DEBUG: Using custom calculations for {symbol} (ta-lib not available or insufficient data)")
                    # Fallback to custom calculations
                    long_term_ema_20 = calculate_ema(kline_4h_prices, 20) if len(kline_4h_prices) >= 20 else current_price
                    long_term_ema_50 = calculate_ema(kline_4h_prices, 50) if len(kline_4h_prices) >= 50 else current_price
                    atr_3_period = calculate_atr(kline_4h_highs, kline_4h_lows, kline_4h_prices, 3) if len(kline_4h_prices) >= 3 else current_price * 0.01
                    atr_14_period = calculate_atr(kline_4h_highs, kline_4h_lows, kline_4h_prices, 14) if len(kline_4h_prices) >= 14 else current_price * 0.02

                    print(f"DEBUG: custom calculations for {symbol}: EMA20={long_term_ema_20}, EMA50={long_term_ema_50}, ATR3={atr_3_period}, ATR14={atr_14_period}")

                # Calculate volume data from 4-hour data
                current_volume = kline_4h_volumes[-1] if kline_4h_volumes else current_price * 1000
                avg_volume = sum(kline_4h_volumes[-14:]) / len(kline_4h_volumes[-14:]) if len(kline_4h_volumes) >= 14 else sum(kline_4h_volumes) / len(kline_4h_volumes) if kline_4h_volumes else current_price * 1000

                # Calculate longer-term MACD series from 4-hour data
                long_macd_series = [calculate_simple_macd(kline_4h_prices[:i+1])[0] if i >= 25 else 0 for i in range(len(kline_4h_prices))]

                # Calculate longer-term RSI 14 series from 4-hour data
                long_rsi_14_series = [calculate_rsi(kline_4h_prices[:i+1], 14) if i >= 13 else 50.0 for i in range(len(kline_4h_prices))]
                
                # For the intraday prices, keep only the last 10 values
                intraday_prices = kline_prices[-10:] if len(kline_prices) >= 10 else kline_prices
                
                # Keep only the last 10 values for each series
                ema_20_series = ema_20_series[-10:] if len(ema_20_series) >= 10 else ema_20_series
                macd_series = macd_series[-10:] if len(macd_series) >= 10 else macd_series
                rsi_7_series = rsi_7_series[-10:] if len(rsi_7_series) >= 10 else rsi_7_series
                rsi_14_series = rsi_14_series[-10:] if len(rsi_14_series) >= 10 else rsi_14_series
                
                # Keep only the last 10 values for longer-term series
                long_macd_series = long_macd_series[-10:] if len(long_macd_series) >= 10 else long_macd_series
                long_rsi_14_series = long_rsi_14_series[-10:] if len(long_rsi_14_series) >= 10 else long_rsi_14_series
                
                # Process liquidation orders to get biggest 10 buy and sell orders
                buy_orders = []
                sell_orders = []
                
                if "rows" in liquidation_orders and liquidation_orders["rows"]:
                    for order in liquidation_orders["rows"]:
                        # Filter out orders older than 24 hours (86400000 milliseconds)
                        order_time = int(order.get("time", 0))
                        current_time = int(datetime.now().timestamp() * 1000)
                        
                        if current_time - order_time <= 86400000:  # Within 24 hours
                            order_info = {
                                "price": float(order.get("price", 0)),
                                "qty": float(order.get("qty", 0)),
                                "side": order.get("side", ""),
                                "symbol": order.get("symbol", "")
                            }
                            
                            if order_info["side"] == "BUY":
                                buy_orders.append(order_info)
                            elif order_info["side"] == "SELL":
                                sell_orders.append(order_info)
                
                # Sort by quantity (largest first) and take top 10
                buy_orders.sort(key=lambda x: x["qty"], reverse=True)
                sell_orders.sort(key=lambda x: x["qty"], reverse=True)
                
                top_10_buy_orders = buy_orders[:10] if buy_orders else []
                top_10_sell_orders = sell_orders[:10] if sell_orders else []
                
                # Add coin data to market state
                coin_data = [
                    f"ALL {coin} DATA",
                    f"current_price = {current_price}, current_ema20 = {current_ema20}, current_macd = {current_macd[0]}, current_rsi (7 period) = {current_rsi}",
                    f"",
                    f"In addition, here is the latest {coin} open interest and funding rate for perps (the instrument you are trading):",
                    f"",
                    f"Open Interest: Latest: {open_interest.get('openInterest', '0.0')} Average: {open_interest.get('openInterest', '0.0')}",  # Placeholder for average
                    f"",
                    f"Funding Rate: {funding_rate}",  # Real funding rate from API
                    f"",
                    f"Intraday series (by minute, oldest → latest):",
                    f"",
                    f"Mid prices: {intraday_prices}",
                    f"EMA indicators (20‑period): {ema_20_series}",
                    f"MACD indicators: {macd_series}",
                    f"RSI indicators (7‑Period): {rsi_7_series}",
                    f"RSI indicators (14‑Period): {rsi_14_series}",
                    f"",
                    f"Liquidation Orders (Biggest 10 Buy/Sell in past 24h):",
                    f"",
                    f"Top 10 Buy Liquidations:",
                ]
                
                # Add top 10 buy orders
                if top_10_buy_orders:
                    for i, order in enumerate(top_10_buy_orders, 1):
                        coin_data.append(f"  {i}. Price: {order['price']:.2f}, Quantity: {order['qty']:.6f}")
                else:
                    coin_data.append(f"  No significant buy liquidations in past 24h")

                coin_data.extend([
                    f"",
                    f"Top 10 Sell Liquidations:",
                ])

                # Add top 10 sell orders
                if top_10_sell_orders:
                    for i, order in enumerate(top_10_sell_orders, 1):
                        coin_data.append(f"  {i}. Price: {order['price']:.2f}, Quantity: {order['qty']:.6f}")
                else:
                    coin_data.append(f"  No significant sell liquidations in past 24h")
                
                coin_data.extend([
                    f"",
                    f"Longer‑term context (4‑hour timeframe):",
                    f"",
                    f"20‑Period EMA: {long_term_ema_20} vs. 50‑Period EMA: {long_term_ema_50}",
                    f"3‑Period ATR: {atr_3_period} vs. 14‑Period ATR: {atr_14_period}",
                    f"Current Volume: {current_volume} vs. Average Volume: {avg_volume}",  # Placeholder values
                    f"MACD indicators: {long_macd_series}",
                    f"RSI indicators (14‑Period): {long_rsi_14_series}",
                    f""
                ])
                
                market_state_parts.extend(coin_data)
                
                # Store detailed coin data for XML update
                all_coin_data[coin.lower()] = {
                    "current_price": current_price,
                    "current_ema20": current_ema20,
                    "current_macd": current_macd[0],
                    "current_rsi": current_rsi,
                    "open_interest_latest": open_interest.get('openInterest', '0.0'),
                    "open_interest_avg": open_interest.get('openInterest', '0.0'),
                    "funding_rate": funding_rate,
                    "intraday_prices": intraday_prices,
                    "ema_20_series": ema_20_series,
                    "macd_series": macd_series,
                    "rsi_7_series": rsi_7_series,
                    "rsi_14_series": rsi_14_series,
                    "long_term_ema_20": long_term_ema_20,
                    "long_term_ema_50": long_term_ema_50,
                    "atr_3_period": atr_3_period,
                    "atr_14_period": atr_14_period,
                    "current_volume": current_volume,
                    "avg_volume": avg_volume,
                    "long_macd_series": long_macd_series,
                    "long_rsi_14_series": long_rsi_14_series,
                    "top_10_buy_liquidations": top_10_buy_orders,
                    "top_10_sell_liquidations": top_10_sell_orders,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Get real account information from XML
            account_summary = self.xml_manager.get_account_summary()

            # Get active trades for positions info
            active_trades = self.trade_xml_manager.get_active_trades()

            # Add account information
            account_info = [
                f"HERE IS YOUR ACCOUNT INFORMATION & PERFORMANCE",
                f"Current Total Return (percent): {account_summary.get('total_return', 0.0)}%",
                f"Available Cash: {account_summary.get('available_cash', 10000.0)}",
                f"Current Account Value: {account_summary.get('current_account_value', 10000.0)}",
                f"Current live positions & performance: {json.dumps(active_trades)}",
                f"Sharpe Ratio: {account_summary.get('sharpe_ratio', 0.0)}"
            ]
            
            market_state_parts.extend(account_info)
            market_state_parts.append("---END OF USER PROMPT---")
            
            # Update the state_of_market in XML
            await self._update_state_of_market(all_coin_data)
            
            return "\n".join(market_state_parts)
    
    async def _update_state_of_market(self, all_coin_data: Dict[str, Dict]):
        """Update the state_of_market section in the XML file"""
        # Get the state_of_market section via the shared manager
        state_of_market = self.xml_manager.get_state_of_market_section()
        
        # Clear the state_of_market section completely
        state_of_market.clear()
        
        # Add current market state for each coin with detailed data
        for coin in self.coins:
            coin_lower = coin.lower()
            if coin_lower in all_coin_data:
                coin_data = all_coin_data[coin_lower]
                coin_elem = ET.SubElement(state_of_market, "coin")
                ET.SubElement(coin_elem, "name").text = coin
                
                # Add each piece of data as a separate XML element instead of JSON
                ET.SubElement(coin_elem, "current_price").text = str(coin_data["current_price"])
                ET.SubElement(coin_elem, "current_ema20").text = str(coin_data["current_ema20"])
                ET.SubElement(coin_elem, "current_macd").text = str(coin_data["current_macd"])
                ET.SubElement(coin_elem, "current_rsi").text = str(coin_data["current_rsi"])
                ET.SubElement(coin_elem, "open_interest_latest").text = str(coin_data["open_interest_latest"])
                ET.SubElement(coin_elem, "open_interest_avg").text = str(coin_data["open_interest_avg"])
                ET.SubElement(coin_elem, "funding_rate").text = str(coin_data["funding_rate"])
                
                # Intraday prices
                intraday_prices_elem = ET.SubElement(coin_elem, "intraday_prices")
                for price in coin_data["intraday_prices"]:
                    ET.SubElement(intraday_prices_elem, "value").text = str(price)
                
                # Intraday series
                ema_20_series_elem = ET.SubElement(coin_elem, "ema_20_series")
                for price in coin_data["ema_20_series"]:
                    ET.SubElement(ema_20_series_elem, "value").text = str(price)
                
                macd_series_elem = ET.SubElement(coin_elem, "macd_series")
                for value in coin_data["macd_series"]:
                    ET.SubElement(macd_series_elem, "value").text = str(value)
                
                rsi_7_series_elem = ET.SubElement(coin_elem, "rsi_7_series")
                for value in coin_data["rsi_7_series"]:
                    ET.SubElement(rsi_7_series_elem, "value").text = str(value)
                
                rsi_14_series_elem = ET.SubElement(coin_elem, "rsi_14_series")
                for value in coin_data["rsi_14_series"]:
                    ET.SubElement(rsi_14_series_elem, "value").text = str(value)
                
                # Longer-term indicators
                ET.SubElement(coin_elem, "long_term_ema_20").text = str(coin_data["long_term_ema_20"])
                ET.SubElement(coin_elem, "long_term_ema_50").text = str(coin_data["long_term_ema_50"])
                ET.SubElement(coin_elem, "atr_3_period").text = str(coin_data["atr_3_period"])
                ET.SubElement(coin_elem, "atr_14_period").text = str(coin_data["atr_14_period"])
                ET.SubElement(coin_elem, "current_volume").text = str(coin_data["current_volume"])
                ET.SubElement(coin_elem, "avg_volume").text = str(coin_data["avg_volume"])
                
                # Longer-term series
                long_macd_series_elem = ET.SubElement(coin_elem, "long_macd_series")
                for value in coin_data["long_macd_series"]:
                    ET.SubElement(long_macd_series_elem, "value").text = str(value)
                
                long_rsi_14_series_elem = ET.SubElement(coin_elem, "long_rsi_14_series")
                for value in coin_data["long_rsi_14_series"]:
                    ET.SubElement(long_rsi_14_series_elem, "value").text = str(value)
                
                # Top 10 buy liquidation orders
                top_10_buy_liquidations_elem = ET.SubElement(coin_elem, "top_10_buy_liquidations")
                for order in coin_data["top_10_buy_liquidations"]:
                    order_elem = ET.SubElement(top_10_buy_liquidations_elem, "order")
                    ET.SubElement(order_elem, "price").text = str(order["price"])
                    ET.SubElement(order_elem, "qty").text = str(order["qty"])
                    ET.SubElement(order_elem, "side").text = order["side"]
                    ET.SubElement(order_elem, "symbol").text = order["symbol"]
                
                # Top 10 sell liquidation orders
                top_10_sell_liquidations_elem = ET.SubElement(coin_elem, "top_10_sell_liquidations")
                for order in coin_data["top_10_sell_liquidations"]:
                    order_elem = ET.SubElement(top_10_sell_liquidations_elem, "order")
                    ET.SubElement(order_elem, "price").text = str(order["price"])
                    ET.SubElement(order_elem, "qty").text = str(order["qty"])
                    ET.SubElement(order_elem, "side").text = order["side"]
                    ET.SubElement(order_elem, "symbol").text = order["symbol"]
                
                ET.SubElement(coin_elem, "timestamp").text = coin_data["timestamp"]
        
        # Write to the XML file via shared manager
        self.xml_manager._write_xml()
    
    async def run_market_updates(self, trading_agents):
        """Run continuous market updates (to be called every minute)"""
        print("Starting market coordinator...")

        try:
            # Start background liquidation collection
            await self.liquidation_client.start_background_collection()
            print("Background liquidation collection started")
        except Exception as e:
            print(f"Failed to start liquidation collection: {e}")

        while True:
            try:
                # Prepare the market state
                user_prompt = await self.prepare_market_state()

                print(f"Market state prepared at {datetime.now()}")

                # Pass the market data to all trading agents in parallel
                await asyncio.gather(*[agent.process_user_prompt(user_prompt) for agent in trading_agents])

                # Wait for 60 seconds before next update
                await asyncio.sleep(120)

            except Exception as e:
                print(f"Error in market coordinator: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    async def close(self):
        """Close the liquidation client"""
        await self.liquidation_client.stop_background_collection()
