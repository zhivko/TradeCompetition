import xml.etree.ElementTree as ET

# Parse XML
tree = ET.parse('trade.xml')
root = tree.getroot()

# Get AgentDeepSeek section
agent = root.find('.//agent[@kind="AgentDeepSeek"]')
if agent is None:
    print('AgentDeepSeek not found')
    exit(1)

# Get closed trades
closed_trades = agent.findall('closed_trades/trade')

for trade in closed_trades:
    coin = trade.find('coin').text
    entry_price = float(trade.find('entry_price').text or 0)
    exit_price = float(trade.find('price').text or 0)  # exit_price is stored as 'price'
    quantity = float(trade.find('quantity').text or 0)
    leverage = int(trade.find('leverage').text or 1)
    position_type_elem = trade.find('position_type')
    if position_type_elem is None:
        print(f"Warning: Missing position_type for {coin} trade, skipping")
        continue
    position_type = position_type_elem.text

    # Calculate correct PNL
    if position_type == "long":
        correct_pnl = (exit_price - entry_price) * abs(quantity) * leverage
    elif position_type == "short":
        correct_pnl = (entry_price - exit_price) * abs(quantity) * leverage
    else:
        print(f"Warning: Invalid position_type '{position_type}' for {coin} trade, skipping")
        continue

    # Update the pnl element
    pnl_elem = trade.find('pnl')
    if pnl_elem is not None:
        old_pnl = float(pnl_elem.text or 0)
        pnl_elem.text = str(correct_pnl)
        print(f"Updated {coin} trade PNL: {old_pnl} -> {correct_pnl}")
    else:
        print(f"Warning: No pnl element for {coin} trade")

# Save the XML
tree.write('trade.xml', encoding="utf-8", xml_declaration=True)
print("Closed trades PNL fixed")