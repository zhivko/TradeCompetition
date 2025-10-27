# TradeCompetition

A real-time automated trading system that leverages AI-powered analysis to make trading decisions in cryptocurrency markets. The system continuously fetches market data from Binance, calculates technical indicators, and uses DeepSeek AI to analyze market conditions and generate trading signals.

## Features

### Market Data Integration
- **Real-time Data**: Fetches live price data, open interest, and funding rates from Binance Spot and Futures APIs
- **Multi-Coin Support**: Tracks 5 major cryptocurrencies (BTC, ETH, BNB, XRP, DOGE)
- **Comprehensive Indicators**: Calculates EMA20, MACD, RSI (7 and 14 periods), ATR, and other technical indicators

### AI-Powered Trading
- **DeepSeek Integration**: Uses DeepSeek AI model for intelligent market analysis and trading decisions
- **Automated Execution**: Continuous monitoring with decisions made every minute
- **Custom Indicators**: Proprietary technical calculations without external dependencies

### Data Management
- **XML Persistence**: Structured XML storage for market state and trade data
- **Series Data**: Stores last 10 values for all time-series data while using longer lookback periods for accurate calculations
- **Modular Architecture**: Separated concerns with MarketCoordinator, TradingAgent, and XMLManager classes

## Requirements

- Python 3.8+
- DeepSeek API Key

## Installation

1. **Clone the repository** (if applicable) or navigate to the project directory

2. **Create virtual environment**:
   ```bash
   python -m venv .venv
   ```

3. **Activate the virtual environment**:
   ```bash
   # On Windows
   .venv\Scripts\activate.bat
   ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure API key**:
   - Create a `.env` file in the project root
   - Add your DeepSeek API key:
     ```
     DEEPSEEK_API_KEY=your_api_key_here
     ```

## Usage

Start the trading system:
```bash
python main.py
```

The system will:
- Establish connection to Binance APIs
- Begin fetching market data every minute
- Process technical indicators
- Generate trading decisions using AI analysis
- Update the `trade.xml` file with current market state and trades

## Project Structure

- `main.py` - Entry point for the trading system
- `market_coordinator.py` - Handles Binance API data fetching and preprocessing
- `trading_agent.py` - Implements AI-powered trading logic and decisions
- `xml_manager.py` - Manages XML data structure and persistence
- `trade.xml` - Persistent storage of market data and trading activity
- `user_prompt.txt` - Log of AI prompts and responses for debugging

## Dependencies

- `aiohttp` - Asynchronous HTTP client for API calls
- `python-dotenv` - Environment variable management
- `numpy` - Mathematical operations for indicator calculations

## Data Flow

1. **MarketCoordinator** fetches data from Binance APIs every minute
2. Raw data is processed and technical indicators calculated
3. Data is structured into XML format and saved
4. **TradingAgent** receives processed data and generates AI prompts
5. DeepSeek API analyzes market conditions and returns trading decisions
6. Decisions are logged and can be acted upon (trading execution not yet implemented)

## Logging and Debugging

- All AI prompts and responses are saved to `user_prompt.txt`
- Comprehensive logging throughout the application
- XML structure provides human-readable data persistence

## Call to Action

This system is designed for educational and research purposes. Always test thoroughly before any real trading activity. Market conditions can change rapidly, and past performance does not guarantee future results.
