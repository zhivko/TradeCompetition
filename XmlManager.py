import xml.etree.ElementTree as ET
from datetime import datetime
import json
from typing import Dict

class TradingXMLManager:
    """Shared XML manager for the trading system"""
    
    def __init__(self, xml_file_path: str = "trade.xml"):
        self.xml_file_path = xml_file_path
        self.root = None
        self._initialize_xml()
    
    def _initialize_xml(self):
        """Initialize the XML structure if it doesn't exist"""
        try:
            # Try to load existing XML
            tree = ET.parse(self.xml_file_path)
            self.root = tree.getroot()

            # Ensure the structure is correct (trading as root)
            if self.root.tag == 'agent':
                # Convert from old structure to new structure
                self._convert_to_trading_structure()
        except FileNotFoundError:
            # Create new XML structure with trading as root
            self.root = ET.Element("trading")

            # Add state_of_market section (for market coordinator)
            state_of_market = ET.SubElement(self.root, "state_of_market")

            # Add agents section
            agents_elem = ET.SubElement(self.root, "agents")

            # Add agent section under agents
            agent_elem = ET.SubElement(agents_elem, "agent")

            # Add active trades section under agent
            active_trades = ET.SubElement(agent_elem, "active_trades")

            # Add closed trades section under agent
            closed_trades = ET.SubElement(agent_elem, "closed_trades")

            # Add summary section under agent
            summary = ET.SubElement(agent_elem, "summary")
            ET.SubElement(summary, "total_return").text = "0.0"
            ET.SubElement(summary, "available_cash").text = "10000.0"  # Starting amount
            ET.SubElement(summary, "current_account_value").text = "10000.0"
            ET.SubElement(summary, "sharpe_ratio").text = "0.0"

            # Write the initial structure to file
            self._write_xml()
    
    def _convert_to_trading_structure(self):
        """Convert old 'agent' root structure to new 'trading' root structure"""
        old_root = self.root
        new_root = ET.Element("trading")

        # Create new state_of_market section
        state_of_market = ET.SubElement(new_root, "state_of_market")

        # Create agents section
        agents_elem = ET.SubElement(new_root, "agents")

        # Move everything else under new agent section
        agent_elem = ET.SubElement(agents_elem, "agent")

        # Copy all elements from old root to new agent
        for child in old_root:
            agent_elem.append(child)

        self.root = new_root
    
    def _write_xml(self):
        """Write the current XML structure to file"""
        tree = ET.ElementTree(self.root)
        ET.indent(tree, space="  ", level=0)  # For pretty printing
        tree.write(self.xml_file_path, encoding="utf-8", xml_declaration=True)
    
    def get_agent_section(self, kind=None):
        """Get the agent section for a specific kind, whether it's the root or a child of trading root"""
        if self.root.tag == "agent":
            # Old structure, agent is root
            return self.root
        elif self.root.tag == "trading":
            # New structure, agent is child of agents
            agents_elem = self.root.find("agents")
            if agents_elem is None:
                agents_elem = ET.SubElement(self.root, "agents")

            if kind:
                # Find existing agent with this kind
                for agent_elem in agents_elem.findall("agent"):
                    if agent_elem.get("kind") == kind:
                        return agent_elem
                # Create new agent element for this kind
                agent_elem = ET.SubElement(agents_elem, "agent")
                agent_elem.set("kind", kind)
                return agent_elem
            else:
                # Fallback: return first agent or create one
                agent_elem = agents_elem.find("agent")
                if agent_elem is None:
                    agent_elem = ET.SubElement(agents_elem, "agent")
                return agent_elem
        else:
            # Unknown structure, return root
            return self.root
    
    def get_state_of_market_section(self):
        """Get the state_of_market section"""
        if self.root.tag == "trading":
            state_of_market = self.root.find("state_of_market")
            if state_of_market is None:
                # Create state_of_market element if it doesn't exist
                state_of_market = ET.SubElement(self.root, "state_of_market")
            return state_of_market
        else:
            # For backward compatibility
            state_of_market = self.root.find("state_of_market")
            if state_of_market is None:
                state_of_market = ET.SubElement(self.root, "state_of_market")
            return state_of_market
    
    def get_market_data_from_xml(self):
        """Extract market data from the XML state_of_market section"""
        state_of_market = self.get_state_of_market_section()
        market_data = {}

        for coin_elem in state_of_market.findall("coin"):
            coin_name = coin_elem.find("name").text.lower()
            coin_data = {}

            # Get all the individual elements
            for elem in coin_elem:
                if elem.tag != "name":  # Skip the name element
                    if elem.tag.endswith("_series"):  # Handle series elements
                        # Extract all "value" children for series
                        values = [float(v.text) for v in elem.findall("value")]
                        coin_data[elem.tag] = values
                    else:
                        try:
                            # Convert to appropriate type (float for numbers, string for others)
                            value = float(elem.text) if elem.text.replace('.', '', 1).replace('-', '', 1).isdigit() else elem.text
                            coin_data[elem.tag] = value
                        except (ValueError, AttributeError):
                            # If conversion fails, keep as string
                            coin_data[elem.tag] = elem.text

            market_data[coin_name] = coin_data

        return market_data

    def get_account_summary(self, kind=None) -> Dict[str, float]:
        """Get the current account summary from XML for a specific agent kind"""
        agent_elem = self.get_agent_section(kind)
        summary_elem = agent_elem.find("summary")

        if summary_elem is None:
            # Return default values if summary doesn't exist
            return {
                "total_return": 0.0,
                "available_cash": 10000.0,
                "current_account_value": 10000.0,
                "sharpe_ratio": 0.0
            }

        account_summary = {}
        for elem in summary_elem:
            try:
                account_summary[elem.tag] = float(elem.text or 0.0)
            except (ValueError, TypeError):
                account_summary[elem.tag] = 0.0

        return account_summary

    def update_account_summary(self, kind=None, **updates):
        """Update account summary values in XML for a specific agent kind"""
        agent_elem = self.get_agent_section(kind)
        summary_elem = agent_elem.find("summary")

        if summary_elem is None:
            summary_elem = ET.SubElement(agent_elem, "summary")

        for key, value in updates.items():
            elem = summary_elem.find(key)
            if elem is not None:
                elem.text = str(value)
            else:
                ET.SubElement(summary_elem, key).text = str(value)

        self._write_xml()

    def update_cash_position(self, amount_change: float, kind=None):
        """Update available cash by adding/subtracting the amount for a specific agent kind"""
        current_summary = self.get_account_summary(kind)
        current_cash = current_summary.get("available_cash", 10000.0)
        new_cash = current_cash + amount_change
        self.update_account_summary(kind=kind, available_cash=new_cash)

    def update_account_value(self, new_value: float, kind=None):
        """Update the current account value for a specific agent kind"""
        self.update_account_summary(kind=kind, current_account_value=new_value)

    def update_total_return(self, new_return: float, kind=None):
        """Update the total return percentage for a specific agent kind"""
        self.update_account_summary(kind=kind, total_return=new_return)

    def clear_all_trades(self, kind=None):
        """Clear all active and closed trades from XML for a specific agent kind or all agents if kind=None"""
        if kind is None:
            # Clear trades for all agents
            agents_elem = self.root.find("agents")
            if agents_elem is not None:
                for agent_elem in agents_elem.findall("agent"):
                    active_trades = agent_elem.find("active_trades")
                    if active_trades is not None:
                        active_trades.clear()

                    closed_trades = agent_elem.find("closed_trades")
                    if closed_trades is not None:
                        closed_trades.clear()
        else:
            # Clear trades for specific agent kind
            agent_elem = self.get_agent_section(kind)

            active_trades = agent_elem.find("active_trades")
            if active_trades is not None:
                active_trades.clear()

            closed_trades = agent_elem.find("closed_trades")
            if closed_trades is not None:
                closed_trades.clear()

        # Ensure state_of_market section is preserved
        state_of_market = self.get_state_of_market_section()
        if state_of_market is None:
            # Recreate state_of_market if it was accidentally cleared
            state_of_market = ET.SubElement(self.root, "state_of_market")

        # Ensure agents section is preserved
        agents_elem = self.root.find("agents")
        if agents_elem is None:
            agents_elem = ET.SubElement(self.root, "agents")

        self._write_xml()

    def remove_unused_agents(self, active_kinds):
        """Remove agents from XML that are not in the active_kinds list"""
        agents_elem = self.root.find("agents")
        if agents_elem is None:
            return

        # Get all agent elements
        agent_elems = agents_elem.findall("agent")
        for agent_elem in agent_elems:
            kind = agent_elem.get("kind")
            if kind not in active_kinds:
                agents_elem.remove(agent_elem)

        self._write_xml()