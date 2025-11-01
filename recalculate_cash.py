import xml.etree.ElementTree as ET

# Parse XML
tree = ET.parse('trade.xml')
root = tree.getroot()

# Get AgentDeepSeek section
agent = root.find('.//agent[@kind="AgentDeepSeek"]')
if agent is None:
    print('AgentDeepSeek not found')
    exit(1)

# Get summary
summary = agent.find('summary')
available_cash = float(summary.find('available_cash').text)
print(f'Available Cash: {available_cash}')

# Get closed trades
closed_trades = agent.findall('closed_trades/trade')
total_pnl = 0
print('Closed trades PNL:')
for i, trade in enumerate(closed_trades, 1):
    coin = trade.find('coin').text
    pnl_elem = trade.find('pnl')
    agent_pnl_elem = trade.find('agentPnl')

    pnl = 0
    if pnl_elem is not None:
        pnl = float(pnl_elem.text or 0)
    elif agent_pnl_elem is not None:
        pnl = float(agent_pnl_elem.text or 0)

    total_pnl += pnl
    print(f'{i}. {coin}: pnl={pnl}')

print(f'Total Closed Trade PNL: {total_pnl}')
print(f'Expected Cash: {10000 + total_pnl}')
print(f'Actual Cash: {available_cash}')
print(f'Difference: {available_cash - (10000 + total_pnl)}')

# Recalculate and update cash
correct_cash = 10000 + total_pnl
summary.find('available_cash').text = str(correct_cash)
tree.write('trade.xml', encoding="utf-8", xml_declaration=True)
print(f'Updated cash to: {correct_cash}')