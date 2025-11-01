import xml.etree.ElementTree as ET

tree = ET.parse('trade.xml')
root = tree.getroot()
logger.info('Root element:', root.tag)

state_of_market = root.find('state_of_market')
logger.info('State of market section found:', state_of_market is not None)

if state_of_market is not None:
    coins = state_of_market.findall('coin')
    logger.info('Number of coins:', len(coins))
    
    if coins:
        first_coin = coins[0]
        name_elem = first_coin.find('name')
        logger.info('First coin:', name_elem.text if name_elem is not None else 'No name')
        
        liquidations = first_coin.find('top_10_buy_liquidations')
        logger.info('Liquidation orders section found:', liquidations is not None)
        
        if liquidations is not None:
            logger.info('Liquidation orders section is empty:', len(liquidations.findall('order')) == 0)