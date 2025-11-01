import json
import re

def extract_json_from_response(content: str) -> str:
    """Extract JSON from LLM response that may contain thinking blocks"""
    # Look for JSON object in the response
    # First try to find JSON between ```json and ```
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
    if json_match:
        return json_match.group(1)

    # Then try to find JSON at the end (after thinking blocks)
    last_brace = content.rfind('{')
    if last_brace != -1:
        potential_json = content[last_brace:]
        # Validate it's valid JSON
        try:
            json.loads(potential_json)
            return potential_json
        except json.JSONDecodeError:
            pass

    # Fallback: try to find any JSON between { and }
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if json_match:
        return json_match.group(0)

    # If no JSON found, return the original content (might be plain JSON)
    return content

# Test with the provided response content
response_content = '''<think>
First, the user has specified that I must analyze market data and provide trading recommendations only in valid JSON format. The action can be BUY, SELL, or HOLD, based on conservative criteria: recommend only if the signal is strong and aligns with multiple indicators like RSI not extreme, MACD crossover confirmed. Otherwise, HOLD.

Key risk rules:
- Max 5 active trades at any time. I need to check the recent trades summary, but in this data, "positions" are empty and "active trades" are listed as [], so currently there are no active trades.
- Each trade risks MAX 2% of total capital (calculate based on stop-loss distance and leverage).
- Quantity formula: quantity = (total_capital * 0.02) / (stop_loss_distance * leverage * entry_price)
- Suggest stop-loss: 2-5% away from entry, based on volatility (e.g., ATR).
- If rules violated, output HOLD with reason.

Output ONLY valid JSON: {"action": "buy/sell/hold", "symbol": "<coin symbol if action is buy/sell>", "quantity": float, "stop_loss": float (price), "confidence": float 0-1, "reason": "brief explanation including risk calc", "invalidation_condition": "string"}

Example: With $10k capital, 3% stop distance, 5x leverage: quantity = (10000 * 0.02) / (0.03 * 5) = ~1333 units worth.

Market Data:
{json.dumps(market_data, indent=2)}

Account Information:
{json.dumps(account_info, indent=2)}

Active Trades:
{json.dumps(active_trades, indent=2)}

Current time: {datetime.now().isoformat()}

Only respond with valid JSON. Do not include any other text or explanation.
</think>
{
  "action": "hold",
  "symbol": null,
  "quantity": 0.0,
  "stop_loss": null,
  "confidence": 0.3,
  "reason": "No strong buy or sell signal detected for any coin; RSI and MACD indicators do not align strongly across multiple data points, with most showing neutral conditions or conflicting signals (e.g., DOGE has low RSI suggesting oversold but negative MACD indicating downtrend)."
}'''

extracted_json = extract_json_from_response(response_content)
logger.info("Extracted JSON:")
logger.info(extracted_json)

try:
    parsed = json.loads(extracted_json)
    logger.info("\nParsed successfully:")
    logger.info(json.dumps(parsed, indent=2))
except json.JSONDecodeError as e:
    logger.info(f"\nFailed to parse JSON: {e}")