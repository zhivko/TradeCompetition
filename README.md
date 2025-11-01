# TradeCompetition

A real-time automated trading competition platform that leverages AI-powered analysis to make trading decisions in cryptocurrency markets. The system features a web-based dashboard for monitoring multiple AI trading agents competing against each other, with live leaderboards, performance analytics, and real-time market data visualization.

The platform continuously fetches market data from Binance and Bybit exchanges, calculates comprehensive technical indicators, and uses DeepSeek AI models to analyze market conditions and generate trading signals. Multiple AI agents can run simultaneously, each with different strategies, creating a competitive trading environment.

## Features

### Web Dashboard & Competition Platform
- **Real-time Dashboard**: Interactive web interface with live updates via WebSocket connections
- **Multi-Agent Competition**: Support for multiple AI trading agents running simultaneously with different strategies
- **Live Leaderboard**: Real-time ranking of agents based on PNL and Sharpe ratio performance
- **Performance Analytics**: Comprehensive charts and metrics for agent performance comparison
- **Trading Competition**: Framework for running automated trading competitions between AI models

### Market Data Integration
- **Multi-Exchange Support**: Fetches data from Binance and Bybit exchanges with automatic failover
- **Real-time Data**: Live price data, open interest, funding rates, and trade data
- **Multi-Coin Support**: Tracks major cryptocurrencies (BTC, ETH, BNB, XRP, DOGE, SOL) plus BTC dominance index
- **Comprehensive Indicators**: Calculates EMA20, MACD, RSI (7 and 14 periods), ATR, and other technical indicators
- **Redis Caching**: High-performance Redis-based caching system for historical and real-time data

### AI-Powered Trading
- **DeepSeek Integration**: Uses DeepSeek AI models for intelligent market analysis and trading decisions
- **Multiple Agent Types**: Support for different AI agent implementations (DeepSeek, DeepSeekLocal, etc.)
- **Automated Execution**: Continuous monitoring with decisions made every minute
- **Custom Indicators**: Proprietary technical calculations without external dependencies
- **Confidence Scoring**: AI-generated confidence levels for trading decisions

### Data Management & Analytics
- **XML Persistence**: Structured XML storage for market state and trade data
- **Redis Streams**: Real-time data streaming and pub/sub messaging
- **Series Data**: Stores configurable time-series data with gap detection and filling
- **Modular Architecture**: Separated concerns with MarketCoordinator, TradingAgent, XMLManager, and Dashboard classes
- **Comprehensive Logging**: Detailed logging system with configurable levels and file rotation

## Requirements

- Python 3.8+
- DeepSeek API Key
- Redis Server (for data caching and real-time features)
- Node.js (optional, for additional frontend tooling)

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

5. **Configure API keys and Redis**:
    - Create a `.env` file in the project root
    - Add your DeepSeek API key:
      ```
      DEEPSEEK_API_KEY=your_api_key_here
      ```
    - Optional: Add other API keys for enhanced functionality:
      ```
      CMC_API_KEY=your_coinmarketcap_key_here
      BINANCE_API_KEY=your_binance_key_here
      BINANCE_API_SECRET=your_binance_secret_here
      ```

6. **Start Redis server** (required for dashboard and caching):
    - On Windows with WSL: `wsl --exec sudo service redis-server start`
    - On Linux/Mac: `redis-server`
    - Or install Redis and start the service

## Usage

### Running the Trading System

Start the core trading system:
```bash
python main.py
```

The system will:
- Establish connection to Binance and Bybit APIs
- Begin fetching market data every minute
- Process technical indicators and store in Redis
- Generate trading decisions using AI analysis
- Update the `trade.xml` file with current market state and trades

### Running the Web Dashboard

Start the web dashboard for monitoring and competition:
```bash
python dashboard.py
```

The dashboard will be available at `http://127.0.0.1:5000` and provides:
- **Live Dashboard** (`/`): Real-time overview of agent performance and market data
- **Leaderboard** (`/leaderboard`): Competitive ranking of all trading agents
- **Models** (`/models`): Detailed view of individual agent performance and configurations

### Running Both Systems Together

For full functionality, run both the trading system and dashboard:

**Terminal 1 - Trading System:**
```bash
python main.py
```

**Terminal 2 - Dashboard:**
```bash
python dashboard.py
```

The dashboard will automatically connect to the running trading system and display live updates.

## Project Structure

### Core Trading System
- `main.py` - Entry point for the trading system
- `MarketCoordinator.py` - Handles multi-exchange API data fetching and preprocessing
- `Agent.py` - Base trading agent class with common functionality
- `AgentDeepSeek.py` - DeepSeek API-based trading agent implementation
- `AgentDeepSeekLocal.py` - Local DeepSeek model trading agent
- `XmlManager.py` - Manages XML data structure and persistence
- `redis_utils.py` - Redis connection management and data caching utilities

### Web Dashboard
- `dashboard.py` - Flask web application for the trading competition dashboard
- `templates/` - HTML templates for the web interface
  - `base.html` - Base template with navigation and styling
  - `live.html` - Live trading dashboard with real-time updates
  - `leaderboard.html` - Agent performance leaderboard
  - `models.html` - Individual agent details and management
- `static/` - Static assets for the web interface
  - `css/dashboard.css` - Custom styling for the dashboard
  - `js/dashboard.js` - JavaScript utilities

### Data & Configuration
- `trade.xml` - Persistent storage of market data and trading activity
- `user_prompt.txt` - Log of AI prompts and responses for debugging
- `logging_config.py` - Centralized logging configuration
- `requirements.txt` - Python dependencies
- `.env` - Environment variables (API keys, etc.)

### Utilities & Testing
- `populate_missing_data.py` - Data backfilling utilities
- `populate_binance_data_5m.py` - Historical data population scripts
- `test_*.py` - Various test files for different components
- `print_redis_data.py` - Redis data inspection utilities
- `BinanceLiquidationClient.py` - Liquidation data monitoring

## Dependencies

### Core Dependencies
- `aiohttp` - Asynchronous HTTP client for API calls
- `python-dotenv` - Environment variable management
- `numpy` - Mathematical operations for indicator calculations
- `redis` - Redis database client for caching and real-time data
- `httpx` - Modern HTTP client for API requests

### Web Dashboard
- `flask` - Web framework for the dashboard
- `flask-socketio` - WebSocket support for real-time updates
- `plotly` - Interactive charts and visualizations (via CDN in templates)

### Exchange APIs
- `ccxt` - Cryptocurrency exchange library
- `python-binance` - Binance API client
- `pybit` - Bybit API client

### AI & ML
- `ta-lib` - Technical analysis library
- `websockets` - WebSocket client for real-time data

### Development & Testing
- `uvicorn` - ASGI server (for FastAPI components)
- `FastApi` - Modern API framework
- `logging` - Python logging utilities

## Data Flow

### Trading System Data Flow
1. **MarketCoordinator** fetches real-time data from Binance/Bybit APIs every minute
2. Raw market data is processed and technical indicators calculated
3. Data is cached in Redis for high-performance access and streamed via Redis pub/sub
4. Data is structured into XML format and persisted to `trade.xml`
5. **TradingAgent** instances receive processed data and generate AI analysis prompts
6. DeepSeek AI models analyze market conditions and return trading decisions with confidence scores
7. Trading decisions are logged, executed in simulation mode, and performance tracked

### Dashboard Data Flow
1. **DashboardDataManager** reads current state from `trade.xml` and Redis cache
2. Flask web server serves HTML templates with embedded JavaScript
3. WebSocket connections established between browser and Flask-SocketIO server
4. Real-time updates pushed to connected clients every 5 seconds via WebSocket
5. Interactive charts and visualizations rendered using Plotly.js
6. Leaderboard calculations performed on-demand and cached for performance

### Competition Mechanics
1. Multiple AI agents run simultaneously with different strategies and parameters
2. Each agent maintains independent PNL tracking and performance metrics
3. Real-time leaderboard ranking based on PNL and Sharpe ratio
4. Historical performance data preserved for analysis and comparison
5. Web dashboard provides live visualization of competition results

## API Endpoints

The dashboard provides REST API endpoints for programmatic access:

- `GET /api/agents` - Returns current agent data and performance metrics
- `GET /api/market` - Returns current market data and indicators
- `GET /api/leaderboard` - Returns sorted leaderboard data

## Configuration

### Environment Variables
- `DEEPSEEK_API_KEY` - Required for AI-powered trading decisions
- `CMC_API_KEY` - Optional, for BTC dominance data from CoinMarketCap
- `BINANCE_API_KEY` & `BINANCE_API_SECRET` - Optional, for enhanced Binance data access
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB` - Redis connection settings (defaults provided)

### Redis Configuration
The system uses Redis for:
- High-performance data caching
- Real-time data streaming
- WebSocket message queuing
- Historical data storage with TTL

### Agent Configuration
Multiple agent types can be configured:
- **AgentDeepSeek**: Uses DeepSeek API for cloud-based AI analysis
- **AgentDeepSeekLocal**: Uses local DeepSeek model for offline operation
- Custom agents can be created by extending the base `Agent` class

## Logging and Debugging

- All AI prompts and responses are saved to `user_prompt.txt`
- Comprehensive logging with configurable levels in `logging_config.py`
- XML structure provides human-readable data persistence
- Redis data inspection utilities available in `print_redis_data.py`
- Extensive test suite for individual components

## Call to Action

This system is designed for educational and research purposes. Always test thoroughly before any real trading activity. Market conditions can change rapidly, and past performance does not guarantee future results.
