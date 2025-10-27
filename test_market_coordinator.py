import asyncio
from MarketCoordinator import MarketCoordinator

async def test():
    coordinator = MarketCoordinator()
    await coordinator.prepare_market_state()
    print('Test completed successfully')

if __name__ == "__main__":
    asyncio.run(test())