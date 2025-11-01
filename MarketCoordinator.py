import asyncio
import aiohttp
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, List
import os
import traceback
import logging
from dotenv import load_dotenv
import requests

# Import shared XML manager
from XmlManager import TradingXMLManager
from Agent import TradeXMLManager
from BinanceLiquidationClient import BinanceLiquidationClient

from logging_config import logger

# Import numpy for array operations
import numpy as np

# Import ta-lib for technical indicators
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    logger.info("Warning: ta-lib not available, using custom calculations")

# Import Redis utilities for simulation mode
from redis_utils import get_cached_klines, get_cached_open_interest, get_oldest_cached_timestamp, get_cached_klines_individual_range


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
        """Get current ticker price for a symbol (using spot API)"""
        # Set the API endpoint for the coin1/coin2 pair
        api_endpoint = 'https://api.binance.com/api/v3/ticker/price?symbol=' + symbol
        response = requests.get(api_endpoint)

        try:
            # Parse the JSON data from the response and extract the current price
            data = response.json()
            current_price = float(data['price'])
            return current_price
        except Exception as e:
            logger.info(f"Exception fetching ticker price for {symbol}: {e}")
            return 0.0
    
    async def get_klines(self, symbol: str, interval: str = "3m", limit: int = 10) -> List:
        """Get kline/candlestick data for a symbol (using futures API)"""
        # Use futures API for klines to match the trading instruments
        endpoint = f"{self.futures_url}/fapi/v1/klines"
        params = {
            "symbol": symbol,  # Use symbol as-is (should include USDT)
            "interval": interval,
            "limit": limit
        }

        try:
            response = requests.get(endpoint, params=params)
            logger.info(f"DEBUG: Kline request for {symbol} {interval}: status {response.status_code}")
            if response.status_code != 200:
                logger.info(f"Error fetching klines for {symbol}: {response.status_code}")
                # Check if the symbol exists by trying ticker price first
                try:
                    price_response = requests.get(f"{self.futures_url}/fapi/v1/ticker/price", params={"symbol": symbol})
                    if price_response.status_code == 200:
                        price_data = price_response.json()
                        logger.info(f"DEBUG: Symbol {symbol} exists, price: {price_data.get('price', 'unknown')}")
                    else:
                        logger.info(f"DEBUG: Symbol {symbol} does not exist or is not available: {price_response.status_code}")
                except Exception as price_e:
                    logger.info(f"DEBUG: Error checking symbol existence: {price_e}")
                return []

            data = response.json()
            logger.info(f"DEBUG: Received {len(data) if data else 0} kline records for {symbol} {interval}")
            # Return full kline data: [open, high, low, close, volume, ...]
            return [[float(kline[1]), float(kline[2]), float(kline[3]), float(kline[4]), float(kline[5])] for kline in data]  # [1]=open, [2]=high, [3]=low, [4]=close, [5]=volume
        except Exception as e:
            logger.info(f"Exception fetching klines for {symbol}: {e}")
            return []
    
    async def get_24hr_ticker(self, symbol: str) -> Dict:
        """Get 24hr ticker data for a symbol (using futures API)"""
        endpoint = f"{self.futures_url}/fapi/v1/ticker/24hr"
        params = {"symbol": symbol}

        try:
            response = requests.get(endpoint, params=params)
            if response.status_code != 200:
                logger.info(f"Error fetching 24hr ticker for {symbol}: {response.status_code}")
                return {}

            return response.json()
        except Exception as e:
            logger.info(f"Exception fetching 24hr ticker for {symbol}: {e}")
            return {}
    
    async def get_open_interest(self, symbol: str) -> Dict:
        """Get open interest data for a symbol (futures)"""
        # Binance futures API for open interest
        endpoint = f"{self.futures_url}/fapi/v1/openInterest"
        params = {"symbol": f"{symbol}USDT"}  # Assuming USDT futures

        try:
            response = requests.get(endpoint, params=params)
            if response.status_code != 200:
                logger.info(f"Error fetching open interest for {symbol}: {response.status_code}")
                # Return default values when API call fails
                return {
                    "symbol": f"{symbol}USDT",
                    "openInterest": "0.0",
                    "time": int(datetime.now().timestamp() * 1000)  # Current timestamp in milliseconds
                }

            return response.json()
        except Exception as e:
            logger.info(f"Exception fetching open interest for {symbol}: {e}")
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
            response = requests.get(endpoint, params=params)
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    logger.info(f"Error fetching liquidation orders for {symbol}: {response.status_code}, Details: {error_data}")
                except Exception:
                    error_text = response.text
                    logger.info(f"Error fetching liquidation orders for {symbol}: {response.status_code}, Details: {error_text}")
                return {"rows": [], "total": 0}

            data = response.json()
            if not isinstance(data, list):
                logger.info(f"Unexpected response format for {symbol}: {data}")
                return {"rows": [], "total": 0}

            return {"rows": data, "total": len(data)}
        except Exception as e:
            logger.info(f"Exception fetching liquidation orders for {symbol}: {e}")
            return {"rows": [], "total": 0}
    
    async def get_funding_rate(self, symbol: str) -> Dict:
        """Get funding rate data for a symbol (futures)"""
        # Binance futures API for funding rate - both USDT and USD (coin-margined)
        funding_rates = {}

        # Get USDT-margined funding rate
        usdt_endpoint = f"{self.futures_url}/fapi/v1/fundingRate"
        usdt_params = {"symbol": f"{symbol}USDT"}

        try:
            response = requests.get(usdt_endpoint, params=usdt_params)
            if response.status_code == 200:
                data = response.json()
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
                logger.info(f"Error fetching USDT funding rate for {symbol}: {response.status_code}")
                # Default values on error
                funding_rates["usdt_funding_rate"] = 0.0
                funding_rates["usdt_funding_timestamp"] = 0
                funding_rates["usdt_next_funding_time"] = 0
        except Exception as e:
            logger.info(f"Exception fetching USDT funding rate for {symbol}: {e}")
            # Default values on exception
            funding_rates["usdt_funding_rate"] = 0.0
            funding_rates["usdt_funding_timestamp"] = 0
            funding_rates["usdt_next_funding_time"] = 0

        # Get USD (coin-margined) funding rate if available
        try:
            usd_endpoint = f"{self.futures_url}/dapi/v1/fundingRate"
            usd_params = {"symbol": f"{symbol}USD_PERP"}  # Coin-margined futures

            response = requests.get(usd_endpoint, params=usd_params)
            if response.status_code == 200:
                data = response.json()
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

    COINS = ["BTC", "ETH", "BNB", "XRP", "DOGE", "SOL"]

    def __init__(self, xml_file_path: str = "trade.xml", simulation_mode: bool = False):
        self.coins = self.COINS
        self.xml_manager = TradingXMLManager(xml_file_path)
        self.trade_xml_manager = TradeXMLManager(xml_file_path)
        self.xml_root = self.xml_manager.root
        self.liquidation_client = BinanceLiquidationClient(tracked_symbols=self.coins) if not simulation_mode else None
        self.simulation_mode = simulation_mode
        self.simulation_timestamp = None  # Will track current simulation time
        self.initial_simulation_timestamp = datetime(2022, 2, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp()  # Track initial simulation time - January 1, 2022 00:00:00 UTC (skip 2021 due to XRP data issues)
        
    def _initialize_xml(self):
        """Initialize is now handled by the shared XML manager"""
        # No need to implement this anymore as it's handled by shared manager
        pass
    
    async def prepare_market_state(self) -> str:
        """Prepare the market state by fetching data from Binance or Redis (simulation mode) and return a user prompt"""

        # Skip background liquidation collection to avoid WebSocket timeout issues
        # if not self.simulation_mode and self.liquidation_client:
        #     await self.liquidation_client.start_background_collection()

        return await self._prepare_market_state_data()

    async def _prepare_market_state_data(self) -> str:
        """Unified method to prepare market state data for both live and simulation modes"""
        if self.simulation_mode:
            return await self._prepare_simulation_market_state()
        else:
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
                logger.info(f"DEBUG: Current price for {symbol}: {current_price}")

                # Get kline data for indicators (3-minute intervals) - getting more data points for proper calculations
                # Need at least 50 data points to properly calculate EMA20, MACD (12,26,9), and RSI
                # But we'll only keep the last 10 values for the series in the XML
                kline_data = await fetcher.get_klines(symbol, "3m", 50)
                logger.info(f"DEBUG: Kline data for {symbol}: {len(kline_data)} records")
                kline_prices = [k[3] for k in kline_data]  # Close prices
                kline_highs = [k[1] for k in kline_data]   # High prices
                kline_lows = [k[2] for k in kline_data]    # Low prices
                kline_volumes = [k[4] for k in kline_data] # Volume data

                # Get longer term kline data for 4-hour timeframe (request more data for proper calculations)
                logger.info(f"DEBUG: Fetching 4h klines for {symbol}")
                kline_4h_data = await fetcher.get_klines(symbol, "4h", 200)  # Request more data for proper calculations
                logger.info(f"DEBUG: 4h data for {symbol}: {len(kline_4h_data) if kline_4h_data else 0} records")
                if not kline_4h_data or len(kline_4h_data) < 100:
                    logger.info(f"DEBUG: 4h failed or insufficient data ({len(kline_4h_data) if kline_4h_data else 0} records), trying 1h for {symbol}")
                    kline_4h_data = await fetcher.get_klines(symbol, "1h", 200)
                    logger.info(f"DEBUG: 1h data for {symbol}: {len(kline_4h_data) if kline_4h_data else 0} records")
                    if not kline_4h_data or len(kline_4h_data) < 100:
                        logger.info(f"DEBUG: 1h also failed or insufficient data ({len(kline_4h_data) if kline_4h_data else 0} records), using 3m data for {symbol}")
                        # Last resort: use 3m data for calculations
                        kline_4h_data = kline_data[:200] if len(kline_data) >= 200 else kline_data

                kline_4h_prices = [k[3] for k in kline_4h_data] if kline_4h_data else []  # Close prices
                kline_4h_highs = [k[1] for k in kline_4h_data] if kline_4h_data else []   # High prices
                kline_4h_lows = [k[2] for k in kline_4h_data] if kline_4h_data else []    # Low prices
                kline_4h_volumes = [k[4] for k in kline_4h_data] if kline_4h_data else [] # Volume data
                logger.info(f"DEBUG: Final data for {symbol}: {len(kline_4h_prices)} prices, {len(kline_4h_highs)} highs, {len(kline_4h_lows)} lows, {len(kline_4h_volumes)} volumes")

                # Skip liquidation orders data to avoid WebSocket issues
                # symbol_usdt = f"{coin}USDT"
                # top_liquidations = self.liquidation_client.get_top_liquidations(symbol_usdt) if self.liquidation_client else []
                # liquidation_orders = {"rows": top_liquidations, "total": len(top_liquidations)}
                liquidation_orders = {"rows": [], "total": 0}

                # Get open interest
                open_interest = await fetcher.get_open_interest(coin)

                # Get funding rate
                funding_data = await fetcher.get_funding_rate(coin)

                # Use the USDT funding rate for the display, fallback to 0 if not available
                funding_rate = funding_data.get("usdt_funding_rate", 0.0)

                # Calculate indicators from the price data using talib
                prices_np = np.array(kline_prices, dtype=float)

                # Calculate EMA20 using talib
                ema20_result = talib.EMA(prices_np, timeperiod=20)
                current_ema20 = float(ema20_result[-1]) if len(ema20_result) > 0 and not np.isnan(ema20_result[-1]) else current_price

                # Calculate MACD (12, 26, 9) using talib
                macd_result, macd_signal, macd_hist = talib.MACD(prices_np, fastperiod=12, slowperiod=26, signalperiod=9)
                current_macd = (
                    float(macd_result[-1]) if len(macd_result) > 0 and not np.isnan(macd_result[-1]) else 0,
                    float(macd_signal[-1]) if len(macd_signal) > 0 and not np.isnan(macd_signal[-1]) else 0,
                    float(macd_hist[-1]) if len(macd_hist) > 0 and not np.isnan(macd_hist[-1]) else 0
                )

                # Calculate RSI using talib
                rsi_result = talib.RSI(prices_np, timeperiod=7)
                current_rsi = float(rsi_result[-1]) if len(rsi_result) > 0 and not np.isnan(rsi_result[-1]) else 50.0

                # Generate series data using talib
                ema_20_series = [float(x) if not np.isnan(x) else kline_prices[i] for i, x in enumerate(ema20_result)]
                macd_value_series = [float(x) if not np.isnan(x) else 0 for x in macd_result]
                macd_signal_series = [float(x) if not np.isnan(x) else 0 for x in macd_signal]

                rsi_7_result = talib.RSI(prices_np, timeperiod=7)
                rsi_7_series = [float(x) if not np.isnan(x) else 50.0 for x in rsi_7_result]

                rsi_14_result = talib.RSI(prices_np, timeperiod=14)
                rsi_14_series = [float(x) if not np.isnan(x) else 50.0 for x in rsi_14_result]

                # Calculate long-term indicators from 4-hour data using ta-lib
                logger.info(f"DEBUG: Starting calculations for {symbol}, data_len={len(kline_4h_prices)}")

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

                logger.info(f"DEBUG: ta-lib calculations for {symbol}: EMA20={long_term_ema_20}, EMA50={long_term_ema_50}, ATR3={atr_3_period}, ATR14={atr_14_period}")

                # Calculate longer-term MACD and RSI series from 4-hour data using talib
                macd_4h_result, macd_4h_signal, macd_4h_hist = talib.MACD(prices_np, fastperiod=12, slowperiod=26, signalperiod=9)
                long_macd_series = [float(x) if not np.isnan(x) else 0 for x in macd_4h_result]

                rsi_4h_result = talib.RSI(prices_np, timeperiod=14)
                long_rsi_14_series = [float(x) if not np.isnan(x) else 50.0 for x in rsi_4h_result]

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
                macd_value_series = macd_value_series[-10:] if len(macd_value_series) >= 10 else macd_value_series
                macd_signal_series = macd_signal_series[-10:] if len(macd_signal_series) >= 10 else macd_signal_series
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
                    f"Intraday series (by {'5-minute' if self.simulation_mode else '3-minute'} intervals, oldest → latest):",
                    f"",
                    f"Mid prices: {intraday_prices}",
                    f"EMA indicators (20‑period): {ema_20_series}",
                    f"MACD value indicators: {macd_value_series}",
                    f"MACD signal indicators: {macd_signal_series}",
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
                    "current_macd": current_macd,
                    "current_rsi": current_rsi,
                    "open_interest_latest": open_interest.get('openInterest', '0.0'),
                    "open_interest_avg": open_interest.get('openInterest', '0.0'),
                    "funding_rate": funding_rate,
                    "intraday_prices": intraday_prices,
                    "ema_20_series": ema_20_series,
                    "macd_value_series": macd_value_series,
                    "macd_signal_series": macd_signal_series,
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

            # Update unrealized PNL for active trades and persist to XML
            await self._update_active_trades_pnl(active_trades, all_coin_data)

            # Add account information
            account_info = [
                f"HERE IS YOUR ACCOUNT INFORMATION & PERFORMANCE",
                f"Current Total Return (percent): {account_summary.get('total_return', 0.0)}%",
                f"Available Cash: {account_summary.get('available_cash', 10000.0)}",
                f"Current Account Value: {account_summary.get('current_account_value', 10000.0)}",
                f"Current live positions & performance: {json.dumps(active_trades, default=str)}",
                f"Sharpe Ratio: {account_summary.get('sharpe_ratio', 0.0)}"
            ]

            market_state_parts.extend(account_info)
            market_state_parts.append("---END OF USER PROMPT---")

            # Update the state_of_market in XML
            await self._update_state_of_market(all_coin_data)

            # Save the user prompt to file immediately after generation
            user_prompt_text = "\n".join(market_state_parts)
            self._save_user_prompt_to_file(user_prompt_text)

            return user_prompt_text

    async def _update_state_of_market(self, all_coin_data: Dict[str, Dict]):
        """Update the state_of_market section in the XML file"""
        # Get the state_of_market section via the shared manager
        state_of_market = self.xml_manager.get_state_of_market_section()

        # Update existing coin data or add new coins without clearing the section
        for coin in self.coins:
            coin_lower = coin.lower()
            if coin_lower in all_coin_data:
                coin_data = all_coin_data[coin_lower]

                # Find existing coin element or create new one
                coin_elem = None
                for existing_coin in state_of_market.findall("coin"):
                    if existing_coin.find("name") is not None and existing_coin.find("name").text == coin:
                        coin_elem = existing_coin
                        break

                if coin_elem is None:
                    coin_elem = ET.SubElement(state_of_market, "coin")
                    ET.SubElement(coin_elem, "name").text = coin

                # Clear existing subelements and add updated data
                for child in list(coin_elem):
                    coin_elem.remove(child)

                # Re-add name
                ET.SubElement(coin_elem, "name").text = coin

                # Add each piece of data as a separate XML element instead of JSON
                ET.SubElement(coin_elem, "current_price").text = str(coin_data["current_price"])
                ET.SubElement(coin_elem, "current_ema20").text = str(coin_data["current_ema20"])
                ET.SubElement(coin_elem, "current_macd_value").text = str(coin_data["current_macd"][0])
                ET.SubElement(coin_elem, "current_macd_signal").text = str(coin_data["current_macd"][1])
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

                macd_value_series_elem = ET.SubElement(coin_elem, "macd_value_series")
                for value in coin_data["macd_value_series"]:
                    ET.SubElement(macd_value_series_elem, "value").text = str(value)

                macd_signal_series_elem = ET.SubElement(coin_elem, "macd_signal_series")
                for value in coin_data["macd_signal_series"]:
                    ET.SubElement(macd_signal_series_elem, "value").text = str(value)

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
        logger.info("Starting market coordinator...")

        try:
            # Skip background liquidation collection to avoid WebSocket timeout issues
            # if self.liquidation_client:
            #     await self.liquidation_client.start_background_collection()
            #     logger.info("Background liquidation collection started")
            logger.info("Skipping liquidation collection to avoid WebSocket issues")
        except Exception as e:
            logger.info(f"Failed to start liquidation collection: {e}")

        while True:
            try:
                # Prepare the market state
                user_prompt = await self.prepare_market_state()

                if self.simulation_mode:
                    logger.info(f"Market state prepared at {datetime.fromtimestamp(self.simulation_timestamp)} (simulation)")
                else:
                    logger.info(f"Market state prepared at {datetime.now()}")

                # Pass the market data to all trading agents in parallel
                await asyncio.gather(*[agent.process_user_prompt(user_prompt) for agent in trading_agents])

                # No wait for simulation - continuous replay of historical data
                # Wait for live trading only
                if not self.simulation_mode:
                    await asyncio.sleep(120)  # 2 minutes for live trading

            except Exception as e:
                logger.info(f"Error in market coordinator: {e}")
                logger.info("Full stack trace:")
                traceback.print_exc()
                # Check if the error is related to undefined variable
                if "stop_loss_calculated_manually" in str(e):
                    logger.info("Detected undefined variable error - this should be fixed in Agent.py")
                await asyncio.sleep(60)  # Wait before retrying

    async def _prepare_simulation_market_state(self) -> str:
        """Prepare market state using historical data from Redis for simulation mode"""
        logger.info("Preparing simulation market state from Redis...")

        # Initialize simulation timestamp if not set
        if self.simulation_timestamp is None:
            self.simulation_timestamp = self.initial_simulation_timestamp

        # Prepare the market data section
        # Calculate minutes since start of simulation
        minutes_since_start = int((self.simulation_timestamp - self.initial_simulation_timestamp) // 60)
        invocations = minutes_since_start  # Each 5-minute interval is one invocation

        market_state_parts = [
            f"USER_PROMPT (SIMULATION MODE)",
            f"It has been {minutes_since_start} minutes since you started trading. The current simulation time is {datetime.fromtimestamp(self.simulation_timestamp)} and you've been invoked {invocations} times. Below, we are providing you with a variety of state data, price data, and predictive signals so you can discover alpha. Below that is your current account information, value, performance, positions, etc.",
            f"",
            f"ALL OF THE PRICE OR SIGNAL DATA BELOW IS ORDERED: OLDEST → NEWEST",
            f"",
            f"Timeframes note: Unless stated otherwise in a section title, intraday series are provided at 5‑minute intervals for simulation. If a coin uses a different interval, it is explicitly stated in that coin's section.",
            f"",
            f"CURRENT MARKET STATE FOR ALL COINS (SIMULATION)"
        ]

        all_coin_data = {}

        # Fetch data for each coin from Redis
        for coin in self.coins:
            # Get historical klines from Redis (simulate current market state)
            # Get the last 10 data points (50 for calculations like live mode) around the current simulation timestamp
            window_seconds = 50 * 5 * 60  # 50 points * 5 min * 60 sec = 15000 seconds
            start_ts = int(max(0, self.simulation_timestamp - window_seconds))
            end_ts = int(self.simulation_timestamp)

            symbol = f"{coin}USDT"  # Use USDT symbol format for Redis
            cached_klines = await get_cached_klines_individual_range(symbol, "5m", start_ts, end_ts)

            # Use the most recent kline as "current" price
            current_kline = cached_klines[-1] if cached_klines else None
            if not current_kline:
                continue

            current_price = current_kline['close']

            # Extract price data for indicators
            kline_prices = [k['close'] for k in cached_klines]
            kline_highs = [k['high'] for k in cached_klines]
            kline_lows = [k['low'] for k in cached_klines]
            kline_volumes = [k['vol'] for k in cached_klines]

            # Get longer term data (simulate 4h data using 5m data aggregated)
            # For simulation, we'll use the same data but treat it as 4h equivalent
            kline_4h_prices = kline_prices
            kline_4h_highs = kline_highs
            kline_4h_lows = kline_lows
            kline_4h_volumes = kline_volumes

            # Get open interest (use cached data if available)
            open_interest_data = await get_cached_open_interest(symbol, "5m", start_ts, end_ts)
            open_interest = {
                "openInterest": str(sum([oi.get('open_interest', 0) for oi in open_interest_data[-1:]] or [0.0])),
                "time": int(self.simulation_timestamp * 1000)
            }

            # Simulate funding rate (use a default value for simulation)
            funding_rate = 0.0001  # 0.01% funding rate for simulation

            # Calculate indicators from the price data
            prices_np = np.array(kline_prices, dtype=float)

            # Calculate EMA20
            ema20_result = talib.EMA(prices_np, timeperiod=20)
            current_ema20 = float(ema20_result[-1]) if len(ema20_result) > 0 and not np.isnan(ema20_result[-1]) else current_price

            # Calculate MACD (12, 26, 9)
            macd_result, macd_signal, macd_hist = talib.MACD(prices_np, fastperiod=12, slowperiod=26, signalperiod=9)
            current_macd = (
                float(macd_result[-1]) if len(macd_result) > 0 and not np.isnan(macd_result[-1]) else 0,
                float(macd_signal[-1]) if len(macd_signal) > 0 and not np.isnan(macd_signal[-1]) else 0,
                float(macd_hist[-1]) if len(macd_hist) > 0 and not np.isnan(macd_hist[-1]) else 0
            )

            # Calculate RSI
            rsi_result = talib.RSI(prices_np, timeperiod=7)
            current_rsi = float(rsi_result[-1]) if len(rsi_result) > 0 and not np.isnan(rsi_result[-1]) else 50.0

            # Generate series data
            ema_20_series = [float(x) if not np.isnan(x) else kline_prices[i] for i, x in enumerate(ema20_result)]
            macd_value_series = [float(x) if not np.isnan(x) else 0 for x in macd_result]
            macd_signal_series = [float(x) if not np.isnan(x) else 0 for x in macd_signal]

            rsi_7_result = talib.RSI(prices_np, timeperiod=7)
            rsi_7_series = [float(x) if not np.isnan(x) else 50.0 for x in rsi_7_result]

            rsi_14_result = talib.RSI(prices_np, timeperiod=14)
            rsi_14_series = [float(x) if not np.isnan(x) else 50.0 for x in rsi_14_result]

            # Calculate long-term indicators
            prices_np_4h = np.array(kline_4h_prices, dtype=float)
            highs_np = np.array(kline_4h_highs, dtype=float)
            lows_np = np.array(kline_4h_lows, dtype=float)

            # Calculate EMAs
            ema20_result_4h = talib.EMA(prices_np_4h, timeperiod=20)
            ema50_result_4h = talib.EMA(prices_np_4h, timeperiod=50)

            long_term_ema_20 = float(ema20_result_4h[-1]) if len(ema20_result_4h) > 0 and not np.isnan(ema20_result_4h[-1]) else current_price
            long_term_ema_50 = float(ema50_result_4h[-1]) if len(ema50_result_4h) > 0 and not np.isnan(ema50_result_4h[-1]) else current_price

            # Calculate ATR
            atr3_result = talib.ATR(highs_np, lows_np, prices_np_4h, timeperiod=3)
            atr14_result = talib.ATR(highs_np, lows_np, prices_np_4h, timeperiod=14)

            atr_3_period = float(atr3_result[-1]) if len(atr3_result) > 0 and not np.isnan(atr3_result[-1]) else current_price * 0.01
            atr_14_period = float(atr14_result[-1]) if len(atr14_result) > 0 and not np.isnan(atr14_result[-1]) else current_price * 0.02

            # Calculate longer-term MACD and RSI series
            macd_4h_result, macd_4h_signal, macd_4h_hist = talib.MACD(prices_np_4h, fastperiod=12, slowperiod=26, signalperiod=9)
            long_macd_series = [float(x) if not np.isnan(x) else 0 for x in macd_4h_result]

            rsi_4h_result = talib.RSI(prices_np_4h, timeperiod=14)
            long_rsi_14_series = [float(x) if not np.isnan(x) else 50.0 for x in rsi_4h_result]

            # Calculate volume data
            current_volume = kline_4h_volumes[-1] if kline_4h_volumes else current_price * 1000
            avg_volume = sum(kline_4h_volumes[-14:]) / len(kline_4h_volumes[-14:]) if len(kline_4h_volumes) >= 14 else sum(kline_4h_volumes) / len(kline_4h_volumes) if kline_4h_volumes else current_price * 1000

            # For the intraday prices, keep only the last 10 values
            intraday_prices = kline_prices[-10:] if len(kline_prices) >= 10 else kline_prices

            # Keep only the last 10 values for each series
            ema_20_series = ema_20_series[-10:] if len(ema_20_series) >= 10 else ema_20_series
            macd_value_series = macd_value_series[-10:] if len(macd_value_series) >= 10 else macd_value_series
            macd_signal_series = macd_signal_series[-10:] if len(macd_signal_series) >= 10 else macd_signal_series
            rsi_7_series = rsi_7_series[-10:] if len(rsi_7_series) >= 10 else rsi_7_series
            rsi_14_series = rsi_14_series[-10:] if len(rsi_14_series) >= 10 else rsi_14_series

            # Keep only the last 10 values for longer-term series
            long_macd_series = long_macd_series[-10:] if len(long_macd_series) >= 10 else long_macd_series
            long_rsi_14_series = long_rsi_14_series[-10:] if len(long_rsi_14_series) >= 10 else long_rsi_14_series

            # Simulate liquidation orders (empty for simulation)
            top_10_buy_orders = []
            top_10_sell_orders = []

            # Add coin data to market state
            coin_data = [
                f"ALL {coin} DATA (SIMULATION)",
                f"current_price = {current_price}, current_ema20 = {current_ema20}, current_macd = {current_macd[0]}, current_rsi (7 period) = {current_rsi}",
                f"",
                f"In addition, here is the latest {coin} open interest and funding rate for perps (the instrument you are trading):",
                f"",
                f"Open Interest: Latest: {open_interest.get('openInterest', '0.0')} Average: {open_interest.get('openInterest', '0.0')}",
                f"",
                f"Funding Rate: {funding_rate}",
                f"",
                f"Intraday series (by minute, oldest → latest):",
                f"",
                f"Mid prices: {intraday_prices}",
                f"EMA indicators (20‑period): {ema_20_series}",
                f"MACD value indicators: {macd_value_series}",
                f"MACD signal indicators: {macd_signal_series}",
                f"RSI indicators (7‑Period): {rsi_7_series}",
                f"RSI indicators (14‑Period): {rsi_14_series}",
                f"",
                f"Liquidation Orders (Biggest 10 Buy/Sell in past 24h):",
                f"",
                f"Top 10 Buy Liquidations:",
                f"  No liquidation data in simulation mode",
                f"",
                f"Top 10 Sell Liquidations:",
                f"  No liquidation data in simulation mode",
                f"",
                f"Longer‑term context (4‑hour timeframe):",
                f"",
                f"20‑Period EMA: {long_term_ema_20} vs. 50‑Period EMA: {long_term_ema_50}",
                f"3‑Period ATR: {atr_3_period} vs. 14‑Period ATR: {atr_14_period}",
                f"Current Volume: {current_volume} vs. Average Volume: {avg_volume}",
                f"MACD indicators: {long_macd_series}",
                f"RSI indicators (14‑Period): {long_rsi_14_series}",
                f""
            ]

            market_state_parts.extend(coin_data)

            # Store detailed coin data for XML update
            all_coin_data[coin.lower()] = {
                "current_price": current_price,
                "current_ema20": current_ema20,
                "current_macd": current_macd,
                "current_rsi": current_rsi,
                "open_interest_latest": open_interest.get('openInterest', '0.0'),
                "open_interest_avg": open_interest.get('openInterest', '0.0'),
                "funding_rate": funding_rate,
                "intraday_prices": intraday_prices,
                "ema_20_series": ema_20_series,
                "macd_value_series": macd_value_series,
                "macd_signal_series": macd_signal_series,
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
                "timestamp": datetime.fromtimestamp(self.simulation_timestamp).isoformat()
            }

        # Get account information from XML
        account_summary = self.xml_manager.get_account_summary()
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
        market_state_parts.append("---END OF USER PROMPT (SIMULATION)---")

        # Update the state_of_market in XML
        await self._update_state_of_market(all_coin_data)

        # Advance simulation time by 5 minutes for next iteration
        self.simulation_timestamp += 300  # 5 minutes

        # Save the user prompt to file
        user_prompt_text = "\n".join(market_state_parts)
        self._save_user_prompt_to_file(user_prompt_text, self.simulation_timestamp)

        return user_prompt_text
    def _save_user_prompt_to_file(self, user_prompt_text: str, simulation_timestamp: float = None):
        """Save the user prompt to file with appropriate header based on mode"""
        with open('user_prompt.txt', 'w', encoding='utf-8') as f:
            if simulation_timestamp is not None:
                f.write(f"--- (SIMULATION TIME: {datetime.fromtimestamp(simulation_timestamp)}) ---\n\n")
            else:
                f.write("--- USER_PROMPT ---\n\n")
            f.write(user_prompt_text)
            f.write("\n\n--- End of user prompt ---")

    async def _update_active_trades_pnl(self, active_trades, all_coin_data):
        """Update unrealized PNL for active trades and persist to XML"""
        try:
            for trade in active_trades:
                symbol = trade.get('symbol') or trade.get('coin', '').upper()
                if symbol and symbol.lower() in all_coin_data:
                    current_price = all_coin_data[symbol.lower()]['current_price']
                    entry_price = trade.get('entry_price', 0)
                    quantity = trade.get('quantity', 0)
                    leverage = trade.get('leverage', 1)
                    position_type = trade.get('position_type', 'long')

                    if entry_price > 0 and current_price > 0:
                        if position_type == "long":
                            unrealized_pnl = (current_price - entry_price) * abs(quantity) * leverage
                        else:  # short
                            unrealized_pnl = (entry_price - current_price) * abs(quantity) * leverage

                        trade['unrealized_pnl'] = unrealized_pnl
                        trade['pnl'] = unrealized_pnl  # Also update pnl for consistency

                        # Update the XML file with the new PNL value
                        await self._update_xml_trade_pnl(trade, symbol, unrealized_pnl)

        except Exception as e:
            logger.info(f"Error updating active trades PNL: {e}")

    async def _update_xml_trade_pnl(self, trade, symbol, pnl_value):
        """Update the PNL value in the XML file for persistence"""
        try:
            # Find the agent that owns this trade
            agent_kind = trade.get('agent', 'AgentDeepSeek')  # Default fallback

            # Get the agent section using the shared manager
            agent_elem = self.xml_manager.get_agent_section(agent_kind)

            if agent_elem is not None:
                # Find the active trade
                active_trades = agent_elem.find("active_trades")
                if active_trades is not None:
                    for trade_elem in active_trades.findall("trade"):
                        coin_elem = trade_elem.find("coin")
                        symbol_elem = trade_elem.find("symbol")
                        trade_symbol = None
                        if coin_elem is not None and coin_elem.text:
                            trade_symbol = coin_elem.text.upper()
                        elif symbol_elem is not None and symbol_elem.text:
                            trade_symbol = symbol_elem.text.upper()

                        if trade_symbol == symbol.upper():
                            # Update unrealized_pnl
                            pnl_elem = trade_elem.find("unrealized_pnl")
                            if pnl_elem is None:
                                pnl_elem = ET.SubElement(trade_elem, "unrealized_pnl")
                            pnl_elem.text = str(pnl_value)

                            # Also update pnl for consistency
                            pnl_elem2 = trade_elem.find("pnl")
                            if pnl_elem2 is None:
                                pnl_elem2 = ET.SubElement(trade_elem, "pnl")
                            pnl_elem2.text = str(pnl_value)

                            # Write back to file
                            self.xml_manager._write_xml()
                            logger.info(f"Updated XML for {symbol} trade PNL: {pnl_value}")
                            break

        except Exception as e:
            logger.info(f"Error updating XML trade PNL: {e}")

    async def close(self):
        """Close the liquidation client"""
        if self.liquidation_client:
            await self.liquidation_client.stop_background_collection()
