import asyncio
from MarketCoordinator import MarketCoordinator
from Agent import TradingAgent

async def test_complete_system():
    coordinator = MarketCoordinator()
    agent = TradingAgent()
    
    # Prepare market state which should trigger XML creation
    market_state = await coordinator.prepare_market_state()
    logger.info('Market state prepared with length:', len(market_state))
    
    # Process with agent
    await agent.process_user_prompt(market_state)
    logger.info('Prompt processed by agent')

if __name__ == "__main__":
    asyncio.run(test_complete_system())