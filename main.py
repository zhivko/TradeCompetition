import asyncio
import os
import sys
import xml.etree.ElementTree as ET
from Agent import TradingAgent
from AgentDeepSeek import AgentDeepSeek
from AgentDeepSeekLocal import AgentDeepSeekLocal
from MarketCoordinator import MarketCoordinator
from XmlManager import TradingXMLManager

async def main():
    """Main function to run the trading agent with market coordinator"""
    print("Initializing DeepSeek Trading Agent and Market Coordinator...")

    # Check for --fresh parameter
    fresh_start = "--fresh" in sys.argv

    # Check for --simulation parameter
    simulation_mode = "--simulation" in sys.argv

    if fresh_start:
        print("Fresh start requested. Clearing all active and closed trades from XML...")
        xml_manager = TradingXMLManager()
        xml_manager.clear_all_trades()
        print("All trades cleared successfully!")


        # Reset account summary to initial values
        xml_manager.update_account_summary(
            available_cash=10000.0,
            current_account_value=10000.0,
            sharpe_ratio=0.0
        )
        print("Account summary reset to initial values!")

    # Check if API key exists
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("Warning: DEEPSEEK_API_KEY not found in environment variables.")
        print("Please add your API key to the .env file to use the full functionality.")

    # Initialize the agents
    #agent_deepseek = TradingAgent(AgentDeepSeek())
    agent_deepseek_local = TradingAgent(AgentDeepSeekLocal())
    #agents = [agent_deepseek, agent_deepseek_local]
    agents = [agent_deepseek_local]
    print(f"Initialized agents: {[agent.kind for agent in agents]}")

    # Initialize agent sections in XML for all agents
    xml_manager = TradingXMLManager()
    active_kinds = [agent.kind for agent in agents]
    xml_manager.remove_unused_agents(active_kinds)
    for agent in agents:
        # Create agent section if it doesn't exist
        agent_elem = xml_manager.get_agent_section(agent.kind)
        # Ensure summary section exists
        summary_elem = agent_elem.find("summary")
        if summary_elem is None:
            summary_elem = ET.SubElement(agent_elem, "summary")
            ET.SubElement(summary_elem, "available_cash").text = "10000.0"
            ET.SubElement(summary_elem, "current_account_value").text = "10000.0"
            ET.SubElement(summary_elem, "sharpe_ratio").text = "0.0"
        # Ensure active_trades section exists
        active_trades_elem = agent_elem.find("active_trades")
        if active_trades_elem is None:
            ET.SubElement(agent_elem, "active_trades")
        # Ensure closed_trades section exists
        closed_trades_elem = agent_elem.find("closed_trades")
        if closed_trades_elem is None:
            ET.SubElement(agent_elem, "closed_trades")
    xml_manager._write_xml()
    print("Agent sections initialized in XML")
    print("Trading agents initialized successfully!")

    # Initialize the market coordinator
    coordinator = MarketCoordinator(simulation_mode=simulation_mode)
    print(f"Market coordinator initialized successfully! (Mode: {'Simulation' if simulation_mode else 'Live'})")

    try:
        print("\nStarting live market data feed...")
        print("The coordinator will fetch data from Binance every minute")
        print("and pass it to the trading agents for analysis.")

        # Run the market coordinator (which will continuously fetch data and pass to the agents)
        await coordinator.run_market_updates(agents)

    except KeyboardInterrupt:
        print("\nShutting down trading system...")
        print("Market coordinator stopped.")

if __name__ == "__main__":
    asyncio.run(main())