import asyncio
from MarketCoordinator import MarketCoordinator
from logging_config import logger

async def test():
    coordinator = MarketCoordinator()
    await coordinator.prepare_market_state()
    logger.info('Test completed successfully')

if __name__ == "__main__":
    asyncio.run(test())