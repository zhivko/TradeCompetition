import os
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
import json
import asyncio
import aiohttp
from dotenv import load_dotenv
from abc import ABC, abstractmethod

# Import shared XML manager
from XmlManager import TradingXMLManager

# Load environment variables
load_dotenv()

# Money management constants
MAX_EXPOSURE_PERCENT = 0.1  # 10% of cash position exposed as active trades
MIN_CONFIDENCE_THRESHOLD = 0.7  # Minimum confidence required for trading actions
# Money management constants
MAX_EXPOSURE_PERCENT = 0.1  # 10% of cash position exposed as active trades

# Dataclasses for trade structures
@dataclass
class ExitPlan:
    profit_target: float
    stop_loss: float
    invalidation_condition: str

@dataclass
class ActiveTrade:
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    liquidation_price: float
    unrealized_pnl: float
    leverage: int
    exit_plan: ExitPlan
    confidence: float
    risk_usd: float
    sl_oid: int
    tp_oid: int
    wait_for_fill: bool
    entry_oid: int
    notional_usd: float
    timestamp: str = None  # ISO format timestamp when trade was created
    reasoning: List[Dict[str, str]] = None  # List of reasoning entries with timestamps

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.reasoning is None:
            self.reasoning = []

    def add_reasoning(self, reasoning_text: str):
        """Add a new reasoning entry with current timestamp"""
        self.reasoning.append({
            "timestamp": datetime.now().isoformat(),
            "reasoning": reasoning_text
        })

@dataclass
class ClosedTrade:
    symbol: str
    quantity: float
    entry_price: float
    exit_price: float
    leverage: int
    pnl: float

@dataclass
class AccountSummary:
    total_return: float
    available_cash: float
    current_account_value: float
    sharpe_ratio: float


class MarketDataManager:
    """Class to manage parsing and handling market data from user prompts"""
    
    def __init__(self):
        self.coins = ["BTC", "ETH", "BNB", "XRP", "DOGE"]  # As specified in the requirements
    
    def parse_market_data(self, user_prompt: str) -> Dict:
        """Parse the user prompt to extract all market data"""
        market_data = {}
        
        # Extract account information
        account_section = self._extract_section(user_prompt, "HERE IS YOUR ACCOUNT INFORMATION & PERFORMANCE")
        market_data["account_info"] = self._parse_account_info(account_section)
        
        # Extract market data for each coin
        for coin in self.coins:
            coin_section = self._extract_section(user_prompt, f"ALL {coin} DATA")
            market_data[coin.lower()] = self._parse_coin_data(coin_section, coin)
        
        return market_data
        
    def _extract_section(self, text: str, start_marker: str) -> str:
        """Extract a section of text between a start marker and the next section or end of text"""
        start_idx = text.find(start_marker)
        if start_idx == -1:
            return ""
        
        # Look for the next section header or end of text
        next_coin_idx = -1
        for coin in self.coins:
            if coin != start_marker.split()[-1]:  # Don't match the current coin
                coin_pos = text.find(f"ALL {coin} DATA", start_idx + len(start_marker))
                if coin_pos != -1 and (next_coin_idx == -1 or coin_pos < next_coin_idx):
                    next_coin_idx = coin_pos
        
        end_idx = next_coin_idx if next_coin_idx != -1 else len(text)
        
        return text[start_idx:end_idx]
    
    def _parse_account_info(self, account_section: str) -> Dict:
        """Parse account information from the provided section"""
        info = {}
        
        # Extract total return
        total_return_match = self._find_pattern(account_section, r"Current Total Return \(percent\): ([\d.]+)%")
        if total_return_match:
            info["total_return"] = float(total_return_match)
        
        # Extract available cash
        cash_match = self._find_pattern(account_section, r"Available Cash: ([\d.]+)")
        if cash_match:
            info["available_cash"] = float(cash_match)
        
        # Extract account value
        account_value_match = self._find_pattern(account_section, r"Current Account Value: ([\d.]+)")
        if account_value_match:
            info["current_account_value"] = float(account_value_match)
        
        # Extract sharpe ratio
        sharpe_match = self._find_pattern(account_section, r"Sharpe Ratio: ([\d.]+)")
        if sharpe_match:
            info["sharpe_ratio"] = float(sharpe_match)
        
        # Extract current positions
        positions_start = account_section.find("Current live positions & performance:")
        if positions_start != -1:
            positions_str = account_section[positions_start:]
            # This would need more complex parsing in a real implementation
            info["positions"] = self._parse_positions(positions_str)
        
        return info
    
    def _parse_positions(self, positions_str: str) -> List[Dict]:
        """Parse the current positions section"""
        # This is a simplified version - in a real implementation, this would need more robust parsing
        # based on the exact format of the positions data
        return []
    
    def _parse_coin_data(self, coin_section: str, coin_name: str) -> Dict:
        """Parse data for a specific coin from the provided section"""
        data = {}
        
        # Extract current values
        current_price_match = self._find_pattern(coin_section, r"current_price = ([\d.]+)")
        if current_price_match:
            data["current_price"] = float(current_price_match)
        
        current_ema20_match = self._find_pattern(coin_section, r"current_ema20 = ([\d.]+)")
        if current_ema20_match:
            data["current_ema20"] = float(current_ema20_match)
        
        current_macd_match = self._find_pattern(coin_section, r"current_macd = ([\d.-]+)")
        if current_macd_match:
            data["current_macd"] = float(current_macd_match)
        
        current_rsi_match = self._find_pattern(coin_section, r"current_rsi \(7 period\) = ([\d.]+)")
        if current_rsi_match:
            data["current_rsi"] = float(current_rsi_match)
        
        # Extract open interest and funding rate
        open_interest_match = self._find_pattern(coin_section, r"Open Interest: Latest: ([\d.]+)")
        if open_interest_match:
            data["open_interest_latest"] = float(open_interest_match)
        
        avg_open_interest_match = self._find_pattern(coin_section, r"Average: ([\d.]+)")
        if avg_open_interest_match:
            data["open_interest_avg"] = float(avg_open_interest_match)
        
        funding_rate_match = self._find_pattern(coin_section, r"Funding Rate: ([\d.e+-]+)")
        if funding_rate_match:
            data["funding_rate"] = float(funding_rate_match)
        
        # Extract intraday series (this would need more complex parsing in a real implementation)
        data["intraday_prices"] = self._parse_series(coin_section, "Mid prices")
        data["ema_20_series"] = self._parse_series(coin_section, "EMA indicators")
        data["macd_series"] = self._parse_series(coin_section, "MACD indicators")
        data["rsi_7_series"] = self._parse_series(coin_section, "RSI indicators")
        
        # Extract 4-hour timeframe data
        data["long_term_ema_20"] = self._find_pattern(coin_section, rf"20‑Period EMA: ([\d.]+)")
        data["long_term_ema_50"] = self._find_pattern(coin_section, rf"50‑Period EMA: ([\d.]+)")
        data["atr_3_period"] = self._find_pattern(coin_section, rf"3‑Period ATR: ([\d.]+)")
        data["atr_14_period"] = self._find_pattern(coin_section, rf"14‑Period ATR: ([\d.]+)")
        
        # Extract liquidation orders data
        data["top_10_buy_liquidations"] = self._parse_liquidation_orders(coin_section, "Top 10 Buy Liquidations")
        data["top_10_sell_liquidations"] = self._parse_liquidation_orders(coin_section, "Top 10 Sell Liquidations")
        
        return data
    
    def _find_pattern(self, text: str, pattern: str) -> Optional[str]:
        """Find a pattern in text and return the first capturing group"""
        import re
        match = re.search(pattern, text)
        return match.group(1) if match else None
    
    def _parse_series(self, text: str, series_name: str) -> List[float]:
        """Parse a series of values from text"""
        import re
        # Look for the series pattern like: Mid prices: [1.1, 2.2, 3.3]
        pattern = rf"{series_name}.*?:\s*\[([^\]]+)\]"
        match = re.search(pattern, text)
        
        if match:
            values_str = match.group(1)
            # Split by comma and convert to float
            values = [float(x.strip()) for x in values_str.split(",")]
            return values
        else:
            return []  # Return empty list if pattern not found
    
    def _parse_liquidation_orders(self, text: str, section_name: str) -> List[Dict]:
        """Parse liquidation orders from a section of text"""
        import re
        orders = []
        
        # Find the section containing the liquidation orders
        section_pattern = rf"{section_name}:(.*?)(?:\n\n|\Z)"
        section_match = re.search(section_pattern, text, re.DOTALL)
        
        if section_match:
            section_text = section_match.group(1)
            # Parse each order line like: "  1. Price: 113000.00, Quantity: 0.500000"
            order_pattern = r"\s*\d+\.\s*Price:\s*([\d.]+),\s*Quantity:\s*([\d.]+)"
            order_matches = re.findall(order_pattern, section_text)
            
            for price, qty in order_matches:
                orders.append({
                    "price": float(price),
                    "qty": float(qty)
                })
        
        return orders


class Agent(ABC):
    """Abstract base class for trading decision makers"""

    def __init__(self):
        pass

    def _construct_prompt(self, market_data: Dict, account_info: Dict, active_trades: List[Dict]) -> str:
        """Construct the prompt to send to the LLM"""
        prompt = f"""
Analyze the data above. Be conservative: only recommend BUY or SELL if the signal is strong and aligns with multiple indicators (e.g., RSI not extreme, MACD crossover confirmed). Otherwise, HOLD to avoid overtrading.

Risk Rules (MUST FOLLOW):
- Max 5 active/open trades at any time (check recent trades summary).
- Each trade risks MAX 2% of total capital (calculate based on stop-loss distance and leverage).
- Quantity formula: quantity = (total_capital * 0.02) / (stop_loss_distance * leverage * entry_price)
- Suggest stop-loss: 2-5% away from entry, based on volatility (e.g., ATR).
- If rules violated, output HOLD with reason.

Output ONLY valid JSON: {{"action": "buy/sell/hold", "symbol": "<coin symbol if action is buy/sell>", "quantity": float, "stop_loss": float (price), "confidence": float 0-1, "reason": "brief explanation including risk calc"}}

Example: With $10k capital, 3% stop distance, 5x leverage: quantity = (10000 * 0.02) / (0.03 * 5) = ~1333 units worth.

Market Data:
{json.dumps(market_data, indent=2)}

Account Information:
{json.dumps(account_info, indent=2)}

Active Trades:
{json.dumps(active_trades, indent=2)}

Current time: {datetime.now().isoformat()}

Only respond with valid JSON. Do not include any other text or explanation.
"""
        return prompt

    def _enforce_risk_rules(self, recommendation: Dict, market_data: Dict, portfolio: Dict) -> Dict:
        """Enforce risk rules after parsing the LLM response"""
        # Enforce max trades
        active_trades = portfolio.get('trades', [])
        active_count = len([t for t in active_trades if not t.get('closed', False)])
        if recommendation.get('action') != 'hold' and active_count >= 5:
            recommendation['action'] = 'hold'
            recommendation['reason'] += " (Overridden: Max 5 active trades reached)"

        # Enforce risk per trade
        if recommendation.get('action') != 'hold':
            total_capital = portfolio.get('total_value', 0)
            symbol = recommendation.get('symbol', '')
            entry_price = recommendation.get('entry_price', market_data.get(symbol.lower(), {}).get('current_price', 0))
            stop_loss = recommendation.get('stop_loss', 0)
            leverage = portfolio.get('leverage', 1.0)

            if entry_price > 0 and stop_loss > 0:
                stop_distance = abs(stop_loss - entry_price) / entry_price
                quantity = recommendation.get('quantity', 0)
                risk_percent = (quantity * entry_price * leverage * stop_distance) / total_capital

                if risk_percent > 0.02:
                    recommendation['action'] = 'hold'
                    recommendation['reason'] += f" (Overridden: Risk {risk_percent:.2%} > 2% max)"

        return recommendation

    def _save_prompt_and_response(self, prompt: str, recommendation: Dict, api_type: str = "API"):
        """Save the prompt and response to files"""
        # Save the full prompt to user_prompt.txt
        with open('user_prompt.txt', 'w', encoding='utf-8') as f:
            f.write(f"--- Prompt sent to {api_type} at {datetime.now()} ---\n\n")
            f.write(prompt)
            f.write(f"\n\n--- End of prompt ---")

        # Save the response to llm_response.txt
        with open('llm_response.txt', 'w', encoding='utf-8') as f:
            f.write(f"--- {api_type} Response at {datetime.now()} ---\n")
            f.write(json.dumps(recommendation, indent=2))
            f.write(f"\n--- End of response ---")

    async def get_trade_recommendation(self, market_data: Dict, account_info: Dict, active_trades: List[Dict], portfolio: Dict = None) -> Dict:
        """Get trade recommendation based on market data using template method pattern"""
        # Construct the prompt for the API
        prompt = self._construct_prompt(market_data, account_info, active_trades)

        # Call the API (implemented by subclasses)
        content = await self._call_api(prompt)

        # Parse the JSON response
        recommendation = json.loads(content)

        # Save the prompt and response
        self._save_prompt_and_response(prompt, recommendation, self.__class__.__name__)

        # Enforce risk rules post-parsing
        if portfolio:
            recommendation = self._enforce_risk_rules(recommendation, market_data, portfolio)

        return recommendation

    async def _call_api(self, prompt: str) -> str:
        """Default implementation for calling API with common logic"""
        headers = self._get_headers()
        payload = self._get_payload(prompt)

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.api_url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        raise Exception(f"API request failed with status {response.status}")

                    result = await response.json()
                    return result['choices'][0]['message']['content']
            except Exception as e:
                print(f"Error calling API: {e}")
                # Return a default JSON string in case of API failure
                return json.dumps({
                    "action": "hold",  # Default action if API fails
                    "reason": "API error - holding position"
                })

    def _get_payload(self, prompt: str) -> Dict:
        """Default payload implementation - can be overridden if needed"""
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert cryptocurrency trading agent. Analyze market data and provide trading recommendations. Only respond with valid JSON containing your trade decision."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2,  # Lower temperature for more consistent decisions
            "response_format": {"type": "json_object"}
        }

    @abstractmethod
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for the API request"""
        pass




class TradeXMLManager:
    """Class to manage trade data persistence in XML format"""

    def __init__(self, xml_file_path: str = "trade.xml"):
        self.xml_manager = TradingXMLManager(xml_file_path)
        self.root = self.xml_manager.root

    def _get_agent_section(self):
        """Get the agent section via the shared manager"""
        return self.xml_manager.get_agent_section()

    def _write_xml(self):
        """Write the current XML structure to file via the shared manager"""
        self.xml_manager._write_xml()

    def add_latest_response(self, response: Dict, kind: str = None):
        """Add the latest agent response to the XML"""
        agent_elem = self._get_agent_section()

        # Set kind attribute if provided
        if kind:
            agent_elem.set("kind", kind)

        # Remove existing latest_response if it exists
        existing_response = agent_elem.find("latest_response")
        if existing_response is not None:
            agent_elem.remove(existing_response)

        # Create new latest_response element
        latest_response_elem = ET.SubElement(agent_elem, "latest_response")

        # Add the response as JSON string
        ET.SubElement(latest_response_elem, "response").text = json.dumps(response)

        # Add timestamp
        ET.SubElement(latest_response_elem, "timestamp").text = datetime.now().isoformat()

        self._write_xml()
    
    def add_active_trade(self, trade: ActiveTrade):
        """Add a new active trade to the XML and update cash position"""
        agent_elem = self._get_agent_section()
        active_trades = agent_elem.find("active_trades")

        trade_elem = ET.SubElement(active_trades, "trade")  # Changed from active_trade to trade
        ET.SubElement(trade_elem, "coin").text = trade.symbol  # Changed from symbol to coin
        ET.SubElement(trade_elem, "price").text = str(trade.current_price)  # Changed from current_price to price
        ET.SubElement(trade_elem, "quantity").text = str(trade.quantity)
        ET.SubElement(trade_elem, "entry_price").text = str(trade.entry_price)
        ET.SubElement(trade_elem, "leverage").text = str(trade.leverage)
        ET.SubElement(trade_elem, "takeprofit").text = str(trade.exit_plan.profit_target)  # Changed from profit_target
        ET.SubElement(trade_elem, "stop_loss").text = str(trade.exit_plan.stop_loss)
        ET.SubElement(trade_elem, "invalidation_condition").text = trade.exit_plan.invalidation_condition
        ET.SubElement(trade_elem, "pnl").text = "0"  # Start with 0

        # Keep some additional fields that might be needed
        ET.SubElement(trade_elem, "liquidation_price").text = str(trade.liquidation_price)
        ET.SubElement(trade_elem, "unrealized_pnl").text = str(trade.unrealized_pnl)
        ET.SubElement(trade_elem, "confidence").text = str(trade.confidence)
        ET.SubElement(trade_elem, "risk_usd").text = str(trade.risk_usd)
        ET.SubElement(trade_elem, "sl_oid").text = str(trade.sl_oid)
        ET.SubElement(trade_elem, "tp_oid").text = str(trade.tp_oid)
        ET.SubElement(trade_elem, "wait_for_fill").text = str(trade.wait_for_fill).lower()
        ET.SubElement(trade_elem, "entry_oid").text = str(trade.entry_oid)
        ET.SubElement(trade_elem, "notional_usd").text = str(trade.notional_usd)
        ET.SubElement(trade_elem, "timestamp").text = trade.timestamp

        # Add reasoning history
        if trade.reasoning:
            # Store the most recent reasoning entry
            latest_reasoning = trade.reasoning[-1] if trade.reasoning else {}
            reasoning_elem = ET.SubElement(trade_elem, "reasoning")
            reasoning_elem.set("timestamp", latest_reasoning.get("timestamp", ""))
            reasoning_elem.text = latest_reasoning.get("reasoning", "")

        self._write_xml()

        # Reduce cash position by the notional value of the trade
        self.xml_manager.update_cash_position(-trade.notional_usd)
    
    def update_active_trade(self, symbol: str, **updates):
        """Update an existing active trade"""
        agent_elem = self._get_agent_section()
        active_trades = agent_elem.find("active_trades")

        for trade_elem in active_trades.findall("trade"):  # Changed from active_trade to trade
            coin_elem = trade_elem.find("coin")
            if coin_elem is not None and coin_elem.text == symbol:
                for key, value in updates.items():
                    elem = trade_elem.find(key)
                    if elem is not None:
                        elem.text = str(value).lower() if isinstance(value, bool) else str(value)
                    else:
                        # If the element doesn't exist, create it (for new fields like timestamp)
                        ET.SubElement(trade_elem, key).text = str(value).lower() if isinstance(value, bool) else str(value)
                break

        self._write_xml()
    
    def close_active_trade(self, symbol: str, exit_price: float, reasoning: str = None):
        """Move an active trade to closed trades and update cash position"""
        agent_elem = self._get_agent_section()
        active_trades = agent_elem.find("active_trades")
        closed_trades = agent_elem.find("closed_trades")

        for i, trade_elem in enumerate(active_trades.findall("trade")):  # Changed from active_trade to trade
            coin_elem = trade_elem.find("coin")
            if coin_elem is not None and coin_elem.text == symbol:
                # Add reasoning if provided
                if reasoning:
                    reasoning_elem = trade_elem.find("reasoning")
                    if reasoning_elem is None:
                        reasoning_elem = ET.SubElement(trade_elem, "reasoning")
                    reasoning_elem.set("timestamp", datetime.now().isoformat())
                    reasoning_elem.text = reasoning

                # Get the trade details
                quantity = float(trade_elem.find("quantity").text or 0)
                entry_price = float(trade_elem.find("entry_price").text or 0)
                leverage = int(trade_elem.find("leverage").text or 1)

                # Calculate final PnL
                final_pnl = (exit_price - entry_price) * quantity * leverage

                # Create closed trade element
                closed_trade_elem = ET.SubElement(closed_trades, "closed_trade")
                # Copy all trade details
                for child in trade_elem:
                    closed_trade_elem.append(child)

                # Update final price and pnl
                price_elem = closed_trade_elem.find("price")
                if price_elem is not None:
                    price_elem.text = str(exit_price)

                pnl_elem = closed_trade_elem.find("pnl")
                if pnl_elem is not None:
                    pnl_elem.text = str(final_pnl)

                # Remove the trade from active trades
                active_trades.remove(trade_elem)

                # Add back the notional value plus PnL to cash position
                notional_usd = float(trade_elem.find("notional_usd").text or 0)
                cash_change = notional_usd + final_pnl
                self.xml_manager.update_cash_position(cash_change)
                break

        self._write_xml()
    
    def get_active_trades(self) -> List[Dict]:
        """Get all active trades as a list of dictionaries"""
        active_trades = []
        agent_elem = self._get_agent_section()
        if agent_elem is None:
            return active_trades
        active_trades_elem = agent_elem.find("active_trades")
        if active_trades_elem is None:
            return active_trades

        for trade_elem in active_trades_elem.findall("trade"):  # Changed from active_trade to trade
            trade_dict = {}
            for child in trade_elem:
                trade_dict[child.tag] = self._convert_xml_value(child.text)
            active_trades.append(trade_dict)

        return active_trades
    
    def _convert_xml_value(self, value: str):
        """Convert XML string value to appropriate Python type"""
        if value.lower() == "true":
            return True
        elif value.lower() == "false":
            return False
        
        try:
            # Try to convert to int first
            return int(value)
        except ValueError:
            try:
                # Then try to convert to float
                return float(value)
            except ValueError:
                # Return as string if neither works
                return value


class TradeDecisionProcessor:
    """Process trade decisions and execute trades based on API recommendations"""

    def __init__(self, xml_manager: TradeXMLManager):
        self.xml_manager = xml_manager
        # Trade event callbacks
        self.on_trade_opened = None
        self.on_trade_closed = None
        
    def process_trade_recommendation(self, recommendation: Dict, current_prices: Dict[str, float], available_cash: float, confidence: float):
        """Process the trade recommendation from the API and execute trades if needed"""
        print(f"DEBUG [{self.kind}]: Processing recommendation: {recommendation}")
        print(f"DEBUG [{self.kind}]: Available cash: {available_cash}")
        print(f"DEBUG [{self.kind}]: Current prices: {current_prices}")
        print(f"DEBUG [{self.kind}]: Confidence: {confidence}")

        # Adjust quantity based on confidence and enforce minimum threshold
        if confidence < MIN_CONFIDENCE_THRESHOLD:
            print(f"Confidence {confidence} < {MIN_CONFIDENCE_THRESHOLD}, not trading")
            action = "hold"
        else:
            action = recommendation.get("action", "hold")
            if action == "buy":
                original_quantity = recommendation.get("quantity", 0.0)
                adjusted_quantity = original_quantity * confidence
                recommendation["quantity"] = adjusted_quantity
                print(f"DEBUG [{self.kind}]: Adjusted quantity from {original_quantity} to {adjusted_quantity} based on confidence {confidence}")

        print(f"DEBUG [{self.kind}]: Action determined: {action}")

        if action == "hold":
            print("No trade action recommended - holding position")
            return

        elif action == "buy":
            symbol = recommendation.get("symbol")
            print(f"DEBUG [{self.kind}]: Buy action - symbol: {symbol}")
            if not symbol:
                print("Buy action specified but no symbol provided")
                return

            # Check exposure limit before executing buy trade
            current_exposure = self._get_current_exposure_percent(available_cash)
            quantity = recommendation.get("quantity", 0.0)
            entry_price = recommendation.get("entry_price", current_prices.get(symbol.lower(), 0))
            leverage = recommendation.get("leverage", 1)
            new_notional = entry_price * quantity * leverage
            print(f"DEBUG [{self.kind}]: Buy - current_exposure: {current_exposure}, quantity: {quantity}, entry_price: {entry_price}, leverage: {leverage}, new_notional: {new_notional}")

            total_exposure_after = current_exposure + (new_notional / available_cash) if available_cash > 0 else float('inf')
            print(f"DEBUG [{self.kind}]: Buy - total_exposure_after: {total_exposure_after}, MAX_EXPOSURE_PERCENT: {MAX_EXPOSURE_PERCENT}")

            if total_exposure_after > MAX_EXPOSURE_PERCENT:
                print(f"Trade rejected: would exceed {MAX_EXPOSURE_PERCENT*100}% exposure limit. " +
                      f"Current exposure: {current_exposure*100:.2f}%, " +
                      f"Potential exposure: {total_exposure_after*100:.2f}%")
                return

            print("DEBUG: Buy - exposure check passed, proceeding to execute trade")
            # Create and execute buy trade
            self._execute_buy_trade(symbol, recommendation, current_prices)

        elif action == "sell":
            symbol = recommendation.get("symbol")
            print(f"DEBUG [{self.kind}]: Sell action - symbol: {symbol}")
            if not symbol:
                print("Sell action specified but no symbol provided")
                return

            # Check if we have an active position for this symbol
            active_trades = self.xml_manager.get_active_trades()
            has_position = any(trade.get("symbol") == symbol for trade in active_trades)
            print(f"DEBUG [{self.kind}]: Sell - has_position: {has_position}, active_trades count: {len(active_trades)}")

            if has_position:
                self._execute_sell_trade(symbol, recommendation, current_prices)
            else:
                print(f"No active position for {symbol} to sell")
        else:
            print(f"Unknown action: {action}")
    
    def _execute_buy_trade(self, symbol: str, recommendation: Dict, current_prices: Dict[str, float]):
        """Execute a buy trade based on the recommendation"""
        current_price = current_prices.get(symbol.upper())
        if not current_price:
            print(f"Could not get current price for {symbol}")
            return
            
        quantity = recommendation.get("quantity", 0.0)
        entry_price = recommendation.get("entry_price", current_price)  # Use current price if no entry price specified
        leverage = recommendation.get("leverage", 1)
        
        exit_plan_data = recommendation.get("exit_plan", {})
        profit_target = exit_plan_data.get("profit_target", 0.0)
        stop_loss = exit_plan_data.get("stop_loss", 0.0)
        invalidation_condition = exit_plan_data.get("invalidation_condition", "Manual close")
        
        confidence = recommendation.get("confidence", 0.0)
        
        # Generate random order IDs (in a real implementation, these would come from the exchange)
        import random
        sl_oid = random.randint(100000000000, 999999999999)
        tp_oid = random.randint(100000000000, 999999999999)
        entry_oid = random.randint(100000000000, 999999999999)
        
        # Calculate risk in USD (simplified calculation)
        risk_usd = abs(entry_price - stop_loss) * quantity * leverage
        notional_usd = entry_price * quantity * leverage
        
        # Calculate unrealized PnL (simplified)
        unrealized_pnl = (current_price - entry_price) * quantity * leverage
        
        # Create the new active trade
        trade = ActiveTrade(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            current_price=current_price,
            liquidation_price=self._calculate_liquidation_price(entry_price, leverage),  # Simplified calculation
            unrealized_pnl=unrealized_pnl,
            leverage=leverage,
            exit_plan=ExitPlan(
                profit_target=profit_target,
                stop_loss=stop_loss,
                invalidation_condition=invalidation_condition
            ),
            confidence=confidence,
            risk_usd=risk_usd,
            sl_oid=sl_oid,
            tp_oid=tp_oid,
            wait_for_fill=False,
            entry_oid=entry_oid,
            notional_usd=notional_usd
        )

        # Add reasoning from the recommendation
        reasoning_text = recommendation.get("reason", "No reasoning provided")
        trade.add_reasoning(reasoning_text)
        
        # Add the trade to XML
        self.xml_manager.add_active_trade(trade)
        print(f"Buy trade executed for {symbol}: quantity={quantity}, entry_price={entry_price}")

        # Signal trade opened event
        if self.on_trade_opened:
            self.on_trade_opened(symbol, trade)
    
    def _execute_sell_trade(self, symbol: str, recommendation: Dict, current_prices: Dict[str, float]):
        """Execute a sell trade (close position)"""
        current_price = current_prices.get(symbol.upper())
        if not current_price:
            print(f"Could not get current price for {symbol}")
            return

        # Get reasoning from recommendation
        reasoning = recommendation.get("reason", "API recommended sell")

        # Close the active trade in the XML
        self.xml_manager.close_active_trade(symbol, current_price, reasoning)
        print(f"Sell trade executed for {symbol}: closed at price={current_price}")

        # Signal trade closed event
        if self.on_trade_closed:
            self.on_trade_closed(symbol, current_price)
    
    def _calculate_liquidation_price(self, entry_price: float, leverage: int) -> float:
        """Calculate the liquidation price (simplified calculation)"""
        # This is a simplified calculation; in reality, this would depend on the exchange's formula
        # Assuming 100% maintenance margin requirement for simplicity
        if leverage == 0:
            return 0.0

        # Simplified liquidation price calculation (doesn't account for funding fees, etc.)
        return entry_price * (leverage - 1) / leverage

    def _get_current_exposure_percent(self, available_cash: float) -> float:
        """Calculate the current exposure as a percentage of available cash"""
        active_trades = self.xml_manager.get_active_trades()
        total_notional = sum(trade.get("notional_usd", 0) for trade in active_trades)

        if available_cash == 0:
            return 1.0 if total_notional > 0 else 0.0  # Fully exposed if cash is 0

        return total_notional / available_cash


class TradingAgent:
    """Main trading agent that coordinates all components"""

    def __init__(self, trader: Agent):
        self.market_data_manager = MarketDataManager()
        self.trader = trader
        # Determine kind based on trader type
        self.kind = self._determine_kind(trader)
        self.xml_manager = TradeXMLManager()
        self.trade_processor = TradeDecisionProcessor(self.xml_manager)

        # Load Binance API credentials from environment
        self.binance_api_key = os.getenv("binance_api_key")
        self.binance_secret_key = os.getenv("binance_secret_key")

        # Trade event callbacks
        self.on_trade_opened = None
        self.on_trade_closed = None

        # Signal cooldown to prevent overtrading
        self.signal_cooldown = 300  # 5 minutes in seconds
        self.last_signal_time = 0

    def _determine_kind(self, trader: Agent) -> str:
        """Determine the kind of agent based on the trader type"""
        return trader.__class__.__name__

    def _update_active_trades(self, current_prices: Dict[str, float]):
        """Update all active trades with current prices and calculate PnL"""
        active_trades = self.xml_manager.get_active_trades()

        for trade in active_trades:
            symbol = trade.get("symbol") or trade.get("coin")
            if symbol in current_prices:
                current_price = current_prices[symbol]
                # Update price
                self.xml_manager.update_active_trade(symbol, price=current_price)

                # Recalculate PnL
                entry_price = trade.get("entry_price")
                quantity = trade.get("quantity", 0)
                leverage = trade.get("leverage", 1)
                if entry_price:
                    pnl = (current_price - entry_price) * quantity * leverage
                    self.xml_manager.update_active_trade(symbol, pnl=pnl)

    def _check_and_close_trades(self):
        """Check if any active trades should be closed due to stop loss or take profit"""
        active_trades = self.xml_manager.get_active_trades()

        for trade in active_trades:
            symbol = trade.get("symbol") or trade.get("coin")
            current_price = trade.get("price") or trade.get("current_price", 0)
            takeprofit = trade.get("takeprofit") or trade.get("profit_target", 0)
            stop_loss = trade.get("stop_loss", 0)

            should_close = False
            exit_price = current_price

            if takeprofit > 0 and current_price >= takeprofit:
                should_close = True
                print(f"Closing {symbol} trade - take profit reached at {current_price}")
            elif stop_loss > 0 and current_price <= stop_loss:
                should_close = True
                print(f"Closing {symbol} trade - stop loss reached at {current_price}")

            if should_close:
                # Determine reasoning based on close condition
                if takeprofit > 0 and current_price >= takeprofit:
                    reasoning = f"Take profit triggered at {current_price}"
                elif stop_loss > 0 and current_price <= stop_loss:
                    reasoning = f"Stop loss triggered at {current_price}"
                else:
                    reasoning = "Trade closed due to exit condition"

                self.xml_manager.close_active_trade(symbol, exit_price, reasoning)
                # Signal trade closed event for stop loss/take profit closures
                if self.on_trade_closed:
                    self.on_trade_closed(symbol, exit_price)

    async def process_user_prompt(self, user_prompt: str):
        """Process a user prompt and execute trading decisions"""
        print(f"Processing user prompt for {self.kind} at {datetime.now()}")

        # Check signal cooldown to prevent overtrading
        import time
        current_time = time.time()
        if current_time - self.last_signal_time < self.signal_cooldown:
            print(f"Signal cooldown active. Last signal: {self.last_signal_time}, current: {current_time}, cooldown: {self.signal_cooldown}")
            return  # Skip processing if cooldown is active

        # Parse the market data from the user prompt
        market_data = self.market_data_manager.parse_market_data(user_prompt)

        # Extract account information
        account_info = market_data.get("account_info", {})

        # Extract current prices for all coins (needed for updating active trades)
        current_prices = {}
        for coin in ["BTC", "ETH", "BNB", "XRP", "DOGE"]:
            coin_data = market_data.get(coin.lower(), {})
            if "current_price" in coin_data:
                current_prices[coin] = coin_data["current_price"]

        # Update active trades with current prices and recalculate PnL
        normalized_current_prices = {k.upper(): v for k, v in current_prices.items()}
        self._update_active_trades(normalized_current_prices)

        # Check and close trades that hit stop loss or take profit
        self._check_and_close_trades()

        # Get active trades for the prompt
        active_trades = self.xml_manager.get_active_trades()

        # Get trade recommendation from the configured trader
        portfolio = {
            'total_value': account_info.get('current_account_value', 0),
            'trades': active_trades,
            'leverage': 5.0  # Default leverage, can be made configurable
        }
        recommendation = await self.trader.get_trade_recommendation(market_data, account_info, active_trades, portfolio)

        # Save the latest agent response to XML
        self.xml_manager.add_latest_response(recommendation, self.kind)

        # Process the trade recommendation (may open new trades if exposure allows)
        confidence = recommendation.get("confidence", 0.0)
        self.trade_processor.process_trade_recommendation(recommendation, normalized_current_prices, account_info.get("available_cash", 0), confidence)

        # Update last signal time only if we actually processed a signal (not on cooldown)
        self.last_signal_time = current_time

        print("Completed processing user prompt")

    async def run_trading_session(self, prompts_generator):
        """Run a complete trading session with multiple prompts"""
        print("Starting trading session...")

        async for prompt in prompts_generator:
            await self.process_user_prompt(prompt)

            # Add a small delay between processing prompts
            await asyncio.sleep(0.1)

        print("Trading session completed")
