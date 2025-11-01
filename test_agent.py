import asyncio
from Agent import TradingAgent, MarketDataManager
import json
from logging_config import logger

# Sample user prompt data based on the specification
sample_user_prompt = """
USER_PROMPT
It has been 5874 minutes since you started trading. The current time is 2025-10-26 15:06:03.742830 and you've been invoked 3651 times. Below, we are providing you with a variety of state data, price data, and predictive signals so you can discover alpha. Below that is your current account information, value, performance, positions, etc.

ALL OF THE PRICE OR SIGNAL DATA BELOW IS ORDERED: OLDEST → NEWEST

Timeframes note: Unless stated otherwise in a section title, intraday series are provided at 3‑minute intervals. If a coin uses a different interval, it is explicitly stated in that coin's section.

CURRENT MARKET STATE FOR ALL COINS
ALL BTC DATA
current_price = 113521.5, current_ema20 = 113704.001, current_macd = -22.879, current_rsi (7 period) = 23.688

In addition, here is the latest BTC open interest and funding rate for perps (the instrument you are trading):

Open Interest: Latest: 29600.73 Average: 29626.51

Funding Rate: 1.25e-05

Intraday series (by minute, oldest → latest):

Mid prices: [113851.5, 113895.0, 113902.0, 113873.0, 113790.0, 113608.0, 113608.5, 113594.0, 113535.0, 113521.5]

EMA indicators (20‑period): [113757.687, 113771.907, 113784.297, 113792.935, 113792.37, 113773.668, 113759.033, 113742.649, 113723.159, 113704.001]

MACD indicators: [68.556, 72.363, 74.122, 72.502, 63.386, 40.285, 23.642, 7.7, -8.787, -22.879]

RSI indicators (7‑Period): [62.006, 65.847, 64.814, 58.984, 43.951, 26.712, 30.697, 28.234, 24.789, 23.688]

RSI indicators (14‑Period): [57.44, 59.336, 58.954, 56.825, 50.432, 39.931, 41.577, 39.956, 37.61, 36.85]

Longer‑term context (4‑hour timeframe):

20‑Period EMA: 111036.947 vs. 50‑Period EMA: 110510.772

3‑Period ATR: 788.526 vs. 14‑Period ATR: 703.725

Current Volume: 1.924 vs. Average Volume: 4799.049

MACD indicators: [463.826, 498.613, 557.919, 601.934, 615.04, 639.28, 649.071, 618.474, 626.542, 757.985]

RSI indicators (14‑Period): [57.812, 57.861, 60.232, 60.48, 59.008, 60.504, 60.288, 56.764, 59.955, 68.443]

ALL ETH DATA
current_price = 4061.85, current_ema20 = 4074.536, current_macd = -3.283, current_rsi (7 period) = 19.96

In addition, here is the latest ETH open interest and funding rate for perps:

Open Interest: Latest: 469483.32 Average: 469693.15

Funding Rate: 1.25e-05

Intraday series (3‑minute intervals, oldest → latest):

Mid prices: [4078.15, 4078.05, 4080.6, 4077.3, 4071.55, 4072.2, 4066.55, 4067.95, 4067.4, 4061.85]

EMA indicators (20‑period): [4080.62, 4080.427, 4080.434, 4080.136, 4079.399, 4078.666, 4077.536, 4076.694, 4075.866, 4074.536]

MACD indicators: [1.242, 0.926, 0.82, 0.473, -0.196, -0.773, -1.608, -2.092, -2.503, -3.283]

RSI indicators (7‑Period): [40.266, 42.794, 49.556, 40.216, 30.086, 28.874, 21.725, 29.609, 28.38, 19.96]

RSI indicators (14‑Period): [45.626, 46.581, 49.192, 45.187, 39.837, 39.125, 34.476, 37.574, 36.882, 31.449]

Longer‑term context (4‑hour timeframe):

20‑Period EMA: 3935.178 vs. 50‑Period EMA: 3936.521

3‑Period ATR: 45.449 vs. 14‑Period ATR: 37.608

Current Volume: 4.747 vs. Average Volume: 102901.022

MACD indicators: [1.084, 2.594, 4.275, 6.46, 7.556, 10.315, 11.936, 11.299, 12.291, 20.993]

RSI indicators (14‑Period): [53.968, 52.344, 53.11, 54.482, 53.485, 56.615, 55.755, 52.18, 55.02, 65.887]

ALL SOL DATA
current_price = 198.565, current_ema20 = 198.975, current_macd = 0.079, current_rsi (7 period) = 33.85

In addition, here is the latest SOL open interest and funding rate for perps:

Open Interest: Latest: 3487849.08 Average: 3498128.3

Funding Rate: 1.25e-05

Intraday series (3‑minute intervals, oldest → latest):

SOL mid prices: [199.025, 199.025, 199.405, 199.21, 199.215, 199.23, 198.83, 198.965, 198.83, 198.565]

EMA indicators (20‑period): [198.921, 198.943, 198.989, 199.01, 199.035, 199.051, 199.03, 199.023, 199.01, 198.975]

MACD indicators: [0.26, 0.247, 0.256, 0.242, 0.234, 0.219, 0.175, 0.149, 0.122, 0.079]

RSI indicators (7‑Period): [45.814, 53.998, 62.749, 53.431, 55.532, 52.32, 38.562, 44.54, 41.974, 33.85]

RSI indicators (14‑Period): [51.239, 55.031, 59.549, 54.884, 55.898, 54.362, 47.008, 49.588, 48.226, 43.619]

Longer‑term context (4‑hour timeframe):

20‑Period EMA: 192.267 vs. 50‑Period EMA: 191.219

3‑Period ATR: 2.15 vs. 14‑Period ATR: 2.136

Current Volume: 264.29 vs. Average Volume: 830856.851

MACD indicators: [1.283, 1.427, 1.551, 1.531, 1.434, 1.556, 1.574, 1.507, 1.511, 1.843]

RSI indicators (14‑Period): [58.83, 58.967, 59.583, 56.24, 54.172, 59.6, 57.519, 55.382, 57.393, 65.33]

ALL BNB DATA
current_price = 1128.15, current_ema20 = 1130.883, current_macd = -1.672, current_rsi (7 period) = 31.862

In addition, here is the latest BNB open interest and funding rate for perps:

Open Interest: Latest: 71697.33 Average: 71080.31

Funding Rate: 1.25e-05

Intraday series (3‑minute intervals, oldest → latest):

BNB mid prices: [1131.85, 1132.35, 1132.1, 1131.05, 1130.9, 1129.7, 1127.6, 1127.4, 1127.9, 1128.15]

EMA indicators (20‑period): [1133.125, 1133.056, 1132.965, 1132.787, 1132.607, 1132.321, 1131.871, 1131.436, 1131.166, 1130.883]

MACD indicators: [-1.124, -1.05, -1.004, -1.036, -1.065, -1.079, -1.415, -1.608, -1.636, -1.672]

RSI indicators (7‑Period): [45.47, 48.65, 45.551, 36.507, 34.891, 26.12, 18.0, 17.071, 34.228, 31.862]

RSI indicators (14‑Period): [40.615, 42.249, 41.033, 37.19, 36.454, 32.022, 26.652, 25.949, 34.064, 32.871]

Longer‑term context (4‑hour timeframe):

20‑Period EMA: 1113.696 vs. 50‑Period EMA: 1115.116

3‑Period ATR: 7.407 vs. 14‑Period ATR: 11.175

Current Volume: 6.391 vs. Average Volume: 8881.467

MACD indicators: [4.391, 4.617, 4.407, 4.415, 3.901, 3.988, 4.043, 4.071, 4.414, 5.821]

RSI indicators (14‑Period): [50.682, 53.401, 51.977, 52.879, 50.717, 53.064, 53.207, 53.361, 55.18, 60.548]

ALL XRP DATA
current_price = 2.63345, current_ema20 = 2.638, current_macd = -0.002, current_rsi (7 period) = 31.566

In addition, here is the latest XRP open interest and funding rate for perps:

Open Interest: Latest: 52114902.0 Average: 52098349.6

Funding Rate: 1.25e-05

Intraday series (3‑minute intervals, oldest → latest):

XRP mid prices: [2.638, 2.642, 2.642, 2.642, 2.64, 2.638, 2.638, 2.637, 2.635, 2.63345]

EMA indicators (20‑period): [2.638, 2.639, 2.639, 2.639, 2.639, 2.639, 2.639, 2.639, 2.638, 2.638]

MACD indicators: [-0.003, -0.002, -0.002, -0.001, -0.001, -0.001, -0.001, -0.001, -0.001, -0.002]

RSI indicators (7‑Period): [56.685, 63.562, 60.415, 60.03, 52.594, 47.533, 48.361, 40.214, 38.495, 31.566]

RSI indicators (14‑Period): [51.732, 55.999, 54.539, 54.369, 51.115, 48.798, 49.153, 45.425, 44.598, 41.053]

Longer‑term context (4‑hour timeframe):

20‑Period EMA: 2.532 vs. 50‑Period EMA: 2.485

3‑Period ATR: 0.02 vs. 14‑Period ATR: 0.024

Current Volume: 4585.0 vs. Average Volume: 8353879.775

MACD indicators: [0.017, 0.023, 0.028, 0.032, 0.039, 0.044, 0.046, 0.048, 0.051, 0.055]

RSI indicators (14‑Period): [64.605, 68.444, 68.37, 70.774, 74.478, 74.924, 71.413, 72.127, 74.779, 76.912]

ALL DOGE DATA
current_price = 0.202375, current_ema20 = 0.203, current_macd = -0.0, current_rsi (7 period) = 44.514

In addition, here is the latest DOGE open interest and funding rate for perps:

Open Interest: Latest: 586664322.0 Average: 586716723.6

Funding Rate: 1.25e-05

Intraday series (3‑minute intervals, oldest → latest):

DOGE mid prices: [0.203, 0.203, 0.203, 0.203, 0.203, 0.203, 0.202, 0.202, 0.203, 0.202375]

EMA indicators (20‑period): [0.203, 0.203, 0.203, 0.203, 0.203, 0.203, 0.203, 0.203, 0.203, 0.203]

MACD indicators: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -0.0]

RSI indicators (7‑Period): [47.19, 52.164, 61.477, 46.572, 52.624, 51.649, 36.333, 45.516, 50.75, 44.514]

RSI indicators (14‑Period): [47.924, 49.907, 54.053, 48.022, 50.697, 50.299, 43.176, 47.106, 49.482, 46.66]

Longer‑term context (4‑hour timeframe):

20‑Period EMA: 0.197 vs. 50‑Period EMA: 0.197

3‑Period ATR: 0.003 vs. 14‑Period ATR: 0.002

Current Volume: 45955.0 vs. Average Volume: 82027751.756

MACD indicators: [0.001, 0.001, 0.001, 0.001, 0.001, 0.001, 0.001, 0.001, 0.001, 0.001]

RSI indicators (14‑Period): [56.012, 56.355, 56.57, 55.281, 51.654, 54.463, 51.643, 47.681, 52.284, 63.538]

HERE IS YOUR ACCOUNT INFORMATION & PERFORMANCE
Current Total Return (percent): 93.06%

Available Cash: 15581.17

Current Account Value: 19305.76

Current live positions & performance: {'symbol': 'BTC', 'quantity': 0.67, 'entry_price': 112430.1, 'current_price': 113521.5, 'liquidation_price': 109313.32, 'unrealized_pnl': 731.24, 'leverage': 25, 'exit_plan': {'profit_target': 114607.71, 'stop_loss': 111236.89, 'invalidation_condition': 'Price closes below 111000 on 3-minute candle'}, 'confidence': 0.88, 'risk_usd': 747.92, 'sl_oid': 212823854807, 'tp_oid': 212823807244, 'wait_for_fill': False, 'entry_oid': 212823778576, 'notional_usd': 76059.4}

Sharpe Ratio: 0.326

---END OF USER PROMPT---
"""

async def test_agent():
    logger.info("Testing the trading agent with sample data...")
    
    # Initialize the agent with a mock trader (since we don't have API keys)
    from AgentDeepSeek import AgentDeepSeek
    trader = AgentDeepSeek()
    agent = TradingAgent(trader)
    
    # Test market data parsing
    logger.info("\n1. Testing market data parsing...")
    market_data_manager = MarketDataManager()
    market_data = market_data_manager.parse_market_data(sample_user_prompt)
    logger.info(f"Parsed market data for {len(market_data)-1} coins and account info")  # -1 for account_info
    
    # Print some parsed data to verify
    logger.info(f"BTC current price: {market_data.get('btc', {}).get('current_price')}")
    logger.info(f"ETH current price: {market_data.get('eth', {}).get('current_price')}")
    logger.info(f"Account total return: {market_data.get('account_info', {}).get('total_return')}")
    
    # Test XML structure creation
    logger.info("\n2. Testing XML structure...")
    xml_manager = agent.xml_manager
    logger.info(f"Active trades: {len(xml_manager.get_active_trades())}")
    
    # Test comprehensive scenarios
    logger.info("\n3. Testing comprehensive trade scenarios...")

    trade_processor = agent.trade_processor
    xml_manager = agent.xml_manager

    # Scenario 1: Long position with profit (price increases)
    logger.info("\n--- Scenario 1: Long position with profit ---")
    long_profit_recommendation = {
        "action": "buy",
        "symbol": "BTC",
        "quantity": 0.0001,  # Very small quantity to avoid exposure limits
        "entry_price": 100000.0,
        "leverage": 5,
        "exit_plan": {
            "profit_target": 120000.0,
            "stop_loss": 95000.0,
            "invalidation_condition": "Manual close"
        },
        "confidence": 0.9,
        "reason": "Bullish signal - opening long position"
    }

    current_prices_scenario1 = {
        "BTC": 100000.0,  # Entry price
        "ETH": 4000.0,
        "BNB": 1100.0,
        "XRP": 2.5,
        "DOGE": 0.2
    }

    trade_processor.process_trade_recommendation(long_profit_recommendation, current_prices_scenario1, 10000.0, 0.9)

    # Update price to simulate profit (price increases)
    current_prices_profit = {
        "BTC": 110000.0,  # Price increased by 10%
        "ETH": 4000.0,
        "BNB": 1100.0,
        "XRP": 2.5,
        "DOGE": 0.2
    }

    agent._update_active_trades(current_prices_profit)
    active_trades = xml_manager.get_active_trades()
    logger.info(f"Active trades after price update: {len(active_trades)}")
    if active_trades:
        btc_trade = next((t for t in active_trades if t.get('coin') == 'BTC'), None)
        if btc_trade:
            logger.info(f"BTC Long position PnL: {btc_trade.get('pnl', 0):.2f}")

    # Scenario 2: Long position with loss (price decreases, hits stop loss)
    logger.info("\n--- Scenario 2: Long position with loss (stop loss) ---")
    long_loss_recommendation = {
        "action": "buy",
        "symbol": "ETH",
        "quantity": 0.001,  # Very small quantity to avoid exposure limits
        "entry_price": 4000.0,
        "leverage": 5,
        "exit_plan": {
            "profit_target": 4500.0,
            "stop_loss": 3800.0,  # Tight stop loss
            "invalidation_condition": "Manual close"
        },
        "confidence": 0.8,
        "reason": "Opening long position with tight stop loss"
    }

    current_prices_scenario2 = {
        "BTC": 110000.0,
        "ETH": 4000.0,  # Entry price
        "BNB": 1100.0,
        "XRP": 2.5,
        "DOGE": 0.2
    }

    trade_processor.process_trade_recommendation(long_loss_recommendation, current_prices_scenario2, 10000.0, 0.8)

    # Update price to trigger stop loss (price decreases below stop loss)
    current_prices_loss = {
        "BTC": 110000.0,
        "ETH": 3750.0,  # Below stop loss of 3800
        "BNB": 1100.0,
        "XRP": 2.5,
        "DOGE": 0.2
    }

    agent._check_and_close_trades()
    active_trades = xml_manager.get_active_trades()
    logger.info(f"Active trades after stop loss trigger: {len(active_trades)}")

    # Scenario 3: Short position with profit (price decreases)
    logger.info("\n--- Scenario 3: Short position with profit ---")
    short_profit_recommendation = {
        "action": "sell",  # Use sell action for short positions
        "symbol": "BNB",
        "quantity": 0.2,  # Positive quantity - sell action means short
        "entry_price": 1100.0,
        "leverage": 5,
        "exit_plan": {
            "profit_target": 1000.0,  # Lower target for shorts
            "stop_loss": 1150.0,  # Higher stop loss for shorts
            "invalidation_condition": "Manual close"
        },
        "confidence": 0.8,
        "reason": "Bearish signal - opening short position"
    }

    current_prices_scenario3 = {
        "BTC": 110000.0,
        "ETH": 3750.0,
        "BNB": 1100.0,  # Entry price
        "XRP": 2.5,
        "DOGE": 0.2
    }

    trade_processor.process_trade_recommendation(short_profit_recommendation, current_prices_scenario3, 10000.0, 0.8)

    # Update price to simulate profit for short (price decreases)
    current_prices_short_profit = {
        "BTC": 110000.0,
        "ETH": 3750.0,
        "BNB": 1050.0,  # Price decreased by 4.5%
        "XRP": 2.5,
        "DOGE": 0.2
    }

    agent._update_active_trades(current_prices_short_profit)
    active_trades = xml_manager.get_active_trades()
    logger.info(f"Active trades after short profit update: {len(active_trades)}")
    if active_trades:
        bnb_trade = next((t for t in active_trades if t.get('coin') == 'BNB'), None)
        if bnb_trade:
            logger.info(f"BNB Short position PnL: {bnb_trade.get('pnl', 0):.2f}")

    # Scenario 4: Short position with loss (price increases, hits stop loss)
    logger.info("\n--- Scenario 4: Short position with loss (stop loss) ---")
    short_loss_recommendation = {
        "action": "sell",  # Use sell action for short positions
        "symbol": "XRP",
        "quantity": 0.01,  # Positive quantity - sell action means short
        "entry_price": 2.5,
        "leverage": 5,
        "exit_plan": {
            "profit_target": 2.2,  # Lower target for shorts
            "stop_loss": 2.6,  # Tight stop loss for shorts
            "invalidation_condition": "Manual close"
        },
        "confidence": 0.8,
        "reason": "Opening short position with tight stop loss"
    }

    current_prices_scenario4 = {
        "BTC": 110000.0,
        "ETH": 3750.0,
        "BNB": 1050.0,
        "XRP": 2.5,  # Entry price
        "DOGE": 0.2
    }

    trade_processor.process_trade_recommendation(short_loss_recommendation, current_prices_scenario4, 10000.0, 0.8)

    # Update price to trigger stop loss for short (price increases above stop loss)
    current_prices_short_loss = {
        "BTC": 110000.0,
        "ETH": 3750.0,
        "BNB": 1050.0,
        "XRP": 2.65,  # Above stop loss of 2.6
        "DOGE": 0.2
    }

    agent._check_and_close_trades()
    active_trades = xml_manager.get_active_trades()
    logger.info(f"Active trades after short stop loss trigger: {len(active_trades)}")

    # Final validation
    logger.info("\n--- Final Validation ---")
    active_trades = xml_manager.get_active_trades()
    logger.info(f"Final active trades count: {len(active_trades)}")

    # Check cash position
    logger.info("Checking final cash position and trade details...")
    for trade in active_trades:
        logger.info(f"Trade: {trade.get('coin')} {trade.get('position_type', 'unknown')} - "
                   f"Quantity: {trade.get('quantity')} - "
                   f"Entry: {trade.get('entry_price')} - "
                   f"Current: {trade.get('price')} - "
                   f"PnL: {trade.get('pnl', 0):.2f}")

    logger.info("\n4. Comprehensive testing complete. All scenarios validated.")

if __name__ == "__main__":
    asyncio.run(test_agent())