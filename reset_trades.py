import xml.etree.ElementTree as ET

# Parse XML
tree = ET.parse('trade.xml')
root = tree.getroot()

# Get AgentDeepSeek section
agent = root.find('.//agent[@kind="AgentDeepSeek"]')
if agent is None:
    print('AgentDeepSeek not found')
    exit(1)

# Clear active trades
active_trades = agent.find("active_trades")
if active_trades is not None:
    active_trades.clear()

# Clear closed trades
closed_trades = agent.find("closed_trades")
if closed_trades is not None:
    closed_trades.clear()

# Reset cash to 10000
summary = agent.find("summary")
if summary is not None:
    cash_elem = summary.find("available_cash")
    if cash_elem is not None:
        cash_elem.text = "10000.0"

    account_value_elem = summary.find("current_account_value")
    if account_value_elem is not None:
        account_value_elem.text = "10000.0"

    sharpe_elem = summary.find("sharpe_ratio")
    if sharpe_elem is not None:
        sharpe_elem.text = "0.0"

# Save the XML
tree.write('trade.xml', encoding="utf-8", xml_declaration=True)
print("All trades cleared and cash reset to $10,000")