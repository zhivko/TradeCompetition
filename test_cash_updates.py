#!/usr/bin/env python3
"""Test script for cash position updates"""

from XmlManager import TradingXMLManager
from Agent import ActiveTrade, ExitPlan

def test_cash_position_updates():
    """Test cash position updates when opening and closing trades"""
    logger.info('Testing cash position updates...')

    # Initialize XML manager
    xml_manager = TradingXMLManager('trade.xml')

    # Get initial account summary
    initial_summary = xml_manager.get_account_summary()
    logger.info(f'Initial cash: {initial_summary.get("available_cash", 0)}')

    # Create a test trade
    exit_plan = ExitPlan(profit_target=50000, stop_loss=30000, invalidation_condition='Test')
    test_trade = ActiveTrade(
        symbol='BTC',
        quantity=0.001,
        entry_price=40000,
        current_price=40000,
        liquidation_price=20000,
        unrealized_pnl=0,
        leverage=5,
        exit_plan=exit_plan,
        confidence=0.8,
        risk_usd=100,
        sl_oid=12345,
        tp_oid=67890,
        wait_for_fill=False,
        entry_oid=11111,
        notional_usd=200  # 0.001 * 40000 * 5 = 200
    )

    # Test opening trade (should reduce cash)
    logger.info('Opening test trade...')
    xml_manager.update_cash_position(-test_trade.notional_usd)
    summary_after_open = xml_manager.get_account_summary()
    logger.info(f'Cash after opening trade: {summary_after_open.get("available_cash", 0)}')

    # Test closing trade with profit
    exit_price = 45000  # Profit of 5000
    final_pnl = (exit_price - test_trade.entry_price) * test_trade.quantity * test_trade.leverage
    cash_change = test_trade.notional_usd + final_pnl
    logger.info(f'Final PnL: {final_pnl}, Cash change: {cash_change}')

    xml_manager.update_cash_position(cash_change)
    summary_after_close = xml_manager.get_account_summary()
    logger.info(f'Cash after closing trade: {summary_after_close.get("available_cash", 0)}')

    logger.info('Cash position update test completed successfully!')

if __name__ == "__main__":
    test_cash_position_updates()