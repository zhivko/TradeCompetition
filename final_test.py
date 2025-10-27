import asyncio
import signal
import sys
from Agent import TradingAgent
from MarketCoordinator import MarketCoordinator

# Global variable to control the loop
running = True

def signal_handler(signum, frame):
    global running
    print("\nReceived interrupt signal. Shutting down...")
    running = False
    sys.exit(0)

async def main():
    """Main function to run the trading agent with market coordinator"""
    global running
    
    print("Initializing DeepSeek Trading Agent and Market Coordinator...")
    
    # Initialize the agent
    agent = TradingAgent()
    print("Trading agent initialized successfully!")
    
    # Initialize the market coordinator
    coordinator = MarketCoordinator()
    print("Market coordinator initialized successfully!")
    
    print("\nStarting live market data feed...")
    print("The coordinator will fetch data from Binance every minute")
    print("and pass it to the trading agent for analysis.")
    print("(Press Ctrl+C to stop)")
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Run the market coordinator (which will continuously fetch data and pass to the agent)
        # For testing purposes, we'll only run for a few iterations
        count = 0
        while running and count < 3:  # Only run 3 iterations for testing
            try:
                # Prepare the market state
                user_prompt = await coordinator.prepare_market_state()
                
                print(f"Market state prepared at {count + 1}/3")
                
                # Pass the market data to the trading agent
                await agent.process_user_prompt(user_prompt)
                
                print(f"Prompt processed. Waiting for next update...")
                
                # Wait for 10 seconds before next update (instead of 60 for testing)
                await asyncio.sleep(10)
                count += 1
                
            except Exception as e:
                print(f"Error in market coordinator: {e}")
                await asyncio.sleep(10)  # Wait before retrying
                
    except KeyboardInterrupt:
        print("\nShutting down trading system...")
        print("Market coordinator stopped.")

if __name__ == "__main__":
    asyncio.run(main())