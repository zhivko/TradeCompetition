import asyncio
import os
import sys
from trading_agent import TradingAgent
from market_coordinator import MarketCoordinator
from xml_manager import TradingXMLManager

async def main():
    """Main function to run the trading agent with market coordinator"""
    print("Initializing DeepSeek Trading Agent and Market Coordinator...")

    # Check for /fresh parameter
    fresh_start = "/fresh" in sys.argv

    if fresh_start:
        print("Fresh start requested. Clearing all active and closed trades from XML...")
        xml_manager = TradingXMLManager()
        xml_manager.clear_all_trades()
        print("All trades cleared successfully!")

    # Check if API key exists
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("Warning: DEEPSEEK_API_KEY not found in environment variables.")
        print("Please add your API key to the .env file to use the full functionality.")

    # Initialize the agent
    agent = TradingAgent()
    print("Trading agent initialized successfully!")

    # Initialize the market coordinator
    coordinator = MarketCoordinator()
    print("Market coordinator initialized successfully!")

    try:
        print("\nStarting live market data feed...")
        print("The coordinator will fetch data from Binance every minute")
        print("and pass it to the trading agent for analysis.")

        # Run the market coordinator (which will continuously fetch data and pass to the agent)
        await coordinator.run_market_updates(agent)

    except KeyboardInterrupt:
        print("\nShutting down trading system...")
        print("Market coordinator stopped.")

if __name__ == "__main__":
    asyncio.run(main())