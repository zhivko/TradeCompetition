import xml.etree.ElementTree as ET

tree = ET.parse('trade.xml')
root = tree.getroot()
print('Root element:', root.tag)

state_of_market = root.find('state_of_market')
print('State of market section found:', state_of_market is not None)

if state_of_market is not None:
    coins = state_of_market.findall('coin')
    print('Number of coins:', len(coins))
    
    if coins:
        first_coin = coins[0]
        name_elem = first_coin.find('name')
        print('First coin:', name_elem.text if name_elem is not None else 'No name')
        
        liquidations = first_coin.find('top_10_buy_liquidations')
        print('Liquidation orders section found:', liquidations is not None)
        
        if liquidations is not None:
            print('Liquidation orders section is empty:', len(liquidations.findall('order')) == 0)