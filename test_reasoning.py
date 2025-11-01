from Agent import TradeXMLManager, ActiveTrade, ExitPlan
import os
import xml.etree.ElementTree as ET

# Clean up any existing trade.xml
if os.path.exists('trade.xml'):
    os.remove('trade.xml')

# Create XML manager
xml_manager = TradeXMLManager()

# Create a test trade with reasoning
trade = ActiveTrade(
    symbol='BTC',
    quantity=1.0,
    entry_price=50000.0,
    current_price=50000.0,
    liquidation_price=45000.0,
    unrealized_pnl=0.0,
    leverage=5,
    exit_plan=ExitPlan(
        profit_target=55000.0,
        stop_loss=45000.0,
        invalidation_condition='Test condition'
    ),
    confidence=0.8,
    risk_usd=5000.0,
    sl_oid=123456789012,
    tp_oid=123456789013,
    wait_for_fill=False,
    entry_oid=123456789014,
    notional_usd=250000.0
)

# Add reasoning
trade.add_reasoning('Test reasoning for BTC trade - expecting price breakout')

# Add trade to XML
xml_manager.add_active_trade(trade)
logger.info('Trade added to XML successfully')

# Verify the XML contains the reasoning
tree = ET.parse('trade.xml')
root = tree.getroot()
trade_elem = root.find('.//trade')
reasoning = trade_elem.find('reasoning')

if reasoning is not None:
    timestamp = reasoning.get('timestamp')
    reasoning_text = reasoning.text
    logger.info('Reasoning found:')
    logger.info(f'  Timestamp: {timestamp}')
    logger.info(f'  Reasoning: {reasoning_text}')
else:
    logger.info('No reasoning element found')

logger.info('Test completed successfully!')