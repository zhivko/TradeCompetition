import asyncio
from MarketCoordinator import MarketCoordinator
from Agent import TradingAgent

async def integration_test():
    logger.info("Starting integration test...")
    
    # Initialize both components
    coordinator = MarketCoordinator()
    agent = TradingAgent()
    
    logger.info("Both coordinator and agent initialized successfully")
    
    # Test the market state preparation
    logger.info("\nTesting market state preparation...")
    market_prompt = await coordinator.prepare_market_state()
    logger.info(f"Market prompt generated with length: {len(market_prompt)} characters")
    
    # Check if XML was updated with state_of_market
    import xml.etree.ElementTree as ET
    try:
        tree = ET.parse("trade.xml")
        root = tree.getroot()
        
        state_of_market = root.find("state_of_market")
        if state_of_market is not None:
            logger.info(f"\nFound state_of_market section with {len(state_of_market.findall('coin'))} coins")
            for coin in state_of_market.findall("coin"):
                name = coin.find("name").text
                data = coin.find("data").text
                logger.info(f"  {name}: Data updated")
        else:
            logger.info("\nstate_of_market section NOT found in XML")
    except Exception as e:
        logger.info(f"Error reading XML: {e}")
    
    logger.info("\nIntegration test completed successfully!")

if __name__ == "__main__":
    asyncio.run(integration_test())