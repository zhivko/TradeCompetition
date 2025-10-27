import asyncio
from trading_agent import TradingAgent, ActiveTrade, ExitPlan
import random

async def test_trade_creation():
    agent = TradingAgent()
    
    # Create a mock trade to test timestamp functionality
    trade = ActiveTrade(
        symbol='BTC',
        quantity=0.1,
        entry_price=10000.0,
        current_price=10100.0,
        liquidation_price=9500.0,
        unrealized_pnl=100.0,
        leverage=10,
        exit_plan=ExitPlan(
            profit_target=11000.0,
            stop_loss=9800.0,
            invalidation_condition='Price drops below key support'
        ),
        confidence=0.8,
        risk_usd=200.0,
        sl_oid=random.randint(100000000000, 999999999999),
        tp_oid=random.randint(100000000000, 999999999999),
        wait_for_fill=False,
        entry_oid=random.randint(100000000000, 999999999999),
        notional_usd=10000.0
    )
    
    agent.xml_manager.add_active_trade(trade)
    print('Trade added successfully with timestamp:', trade.timestamp)
    
    # Read the XML to verify
    import xml.etree.ElementTree as ET
    tree = ET.parse('trade.xml')
    root = tree.getroot()
    
    # Find the agent section first
    if root.tag == 'trading':
        agent_elem = root.find('agent')
        active_trades = agent_elem.find('active_trades')
    else:
        # For backward compatibility
        active_trades = root.find('active_trades')
    
    if active_trades is not None:
        for trade_elem in active_trades.findall('active_trade'):
            timestamp_elem = trade_elem.find('timestamp')
            if timestamp_elem is not None:
                print('Found timestamp in XML:', timestamp_elem.text)
            else:
                print('No timestamp found in XML')
    else:
        print('active_trades section not found')

if __name__ == "__main__":
    asyncio.run(test_trade_creation())