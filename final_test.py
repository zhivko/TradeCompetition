import asyncio
import signal
import sys
from Agent import TradingAgent
from MarketCoordinator import MarketCoordinator

# Global variable to control the loop
running = True

def signal_handler(signum, frame):
    global running
    logger.info("\nReceived interrupt signal. Shutting down...")
    running = False
    sys.exit(0)

async def main():
    """Main function to run the trading agent with market coordinator"""
    global running
    
    logger.info("Initializing DeepSeek Trading Agent and Market Coordinator...")
    
    # Initialize the agent
    agent = TradingAgent()
    logger.info("Trading agent initialized successfully!")
    
    # Initialize the market coordinator
    coordinator = MarketCoordinator()
    logger.info("Market coordinator initialized successfully!")
    
    logger.info("\nStarting live market data feed...")
    logger.info("The coordinator will fetch data from Binance every minute")
    logger.info("and pass it to the trading agent for analysis.")
    logger.info("(Press Ctrl+C to stop)")
    
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
                
                logger.info(f"Market state prepared at {count + 1}/3")
                
                # Pass the market data to the trading agent
                await agent.process_user_prompt(user_prompt)
                
                logger.info(f"Prompt processed. Waiting for next update...")
                
                # Wait for 10 seconds before next update (instead of 60 for testing)
                await asyncio.sleep(10)
                count += 1
                
            except Exception as e:
                logger.info(f"Error in market coordinator: {e}")
                await asyncio.sleep(10)  # Wait before retrying
                
    except KeyboardInterrupt:
        logger.info("\nShutting down trading system...")
        logger.info("Market coordinator stopped.")

if __name__ == "__main__":
    asyncio.run(main())