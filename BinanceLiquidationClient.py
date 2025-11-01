import asyncio
import json
import websockets
from typing import Dict, List
import logging
from collections import defaultdict

# Set up logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BinanceLiquidationClient:
    def __init__(self, tracked_symbols: List[str] = None):
        self.ws_url = "wss://fstream.binance.com/ws"
        self.top_liquidations: Dict[str, List[Dict]] = defaultdict(list)  # symbol -> list of top 10 biggest liquidations
        self.collection_task = None
        # Convert to USDT format and store as set for fast lookup
        self.tracked_symbols = set(f"{symbol}USDT" for symbol in (tracked_symbols or ["BTC", "ETH", "BNB", "XRP", "DOGE"]))

    def _update_top_liquidations(self, order: Dict):
        """Update the top 10 liquidations for a symbol"""
        symbol = order.get("s", "")
        if not symbol:
            return

        # Add the new order
        self.top_liquidations[symbol].append(order)

        # Sort by quantity descending and keep top 10
        self.top_liquidations[symbol].sort(key=lambda x: float(x.get("q", 0)), reverse=True)
        self.top_liquidations[symbol] = self.top_liquidations[symbol][:10]

    async def start_background_collection(self):
        """Start collecting all-market liquidations in the background"""
        if self.collection_task is not None:
            logger.warning("Collection already running")
            return

        self.collection_task = asyncio.create_task(self._collect_all_market_liquidations())

    async def stop_background_collection(self):
        """Stop the background collection"""
        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
            self.collection_task = None

    async def _collect_all_market_liquidations(self):
        """Continuously collect all-market liquidations"""
        stream_name = "!forceOrder@arr"
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": [stream_name],
            "id": 1
        }

        while True:
            try:
                async with websockets.connect(self.ws_url) as websocket:
                    await websocket.send(json.dumps(subscribe_msg))
                    logger.info("Subscribed to all-market liquidations stream")

                    while True:
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                            data = json.loads(message)

                            # Debug: Log the message structure
                            if not isinstance(data, dict):
                                logger.warning(f"Received non-dict message: {data}")
                                continue

                            if "e" in data and data["e"] == "forceOrder":  # Force order event
                                # Check if it's an array format (all-market) or single order format (per-symbol)
                                if "a" in data:
                                    # All-market format: 'a' contains array of orders
                                    orders_array = data["a"]
                                    if not isinstance(orders_array, list):
                                        logger.warning(f"'a' field is not a list: {orders_array}")
                                        continue

                                    for order_data in orders_array:
                                        if "o" not in order_data:
                                            logger.warning(f"Order data missing 'o' field: {order_data}")
                                            continue

                                        order = order_data["o"]
                                        symbol = order.get("s", "")
                                        if symbol in self.tracked_symbols:
                                            self._update_top_liquidations(order)
                                            logger.debug(f"All-market liquidation: {order['s']} {order['S']} {order['q']} @ {order['p']}")
                                elif "o" in data:
                                    # Per-symbol format: 'o' contains single order
                                    order = data["o"]
                                    symbol = order.get("s", "")
                                    if symbol in self.tracked_symbols:
                                        self._update_top_liquidations(order)
                                        logger.debug(f"Per-symbol liquidation: {order['s']} {order['S']} {order['q']} @ {order['p']}")
                                else:
                                    logger.warning(f"forceOrder event missing both 'a' and 'o' fields: {data}")
                                    continue
                            else:
                                logger.debug(f"Received non-forceOrder event: {data.get('e', 'unknown')}")
                        except asyncio.TimeoutError:
                            continue
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse JSON message: {e}, message: {message[:200]}...")
                            continue
                        except Exception as e:
                            logger.error(f"Error processing message: {e}, type: {type(e)}")
                            break

            except Exception as e:
                logger.error(f"All-market WebSocket error: {e}")
                await asyncio.sleep(5)  # Wait before reconnecting

    def get_top_liquidations(self, symbol: str) -> List[Dict]:
        """Get the top 10 biggest liquidations for a symbol"""
        return self.top_liquidations.get(symbol, [])

    async def subscribe_to_liquidations(self, symbol: str, duration_seconds: int = 60) -> Dict[str, List]:
        """
        Subscribe to real-time liquidation orders for a symbol.
        Collects events for a specified duration (default 60s).
        Returns collected data.
        """
        # Stream name: lowercase symbol without 'USDT' + @forceOrder
        stream_name = symbol.lower().replace("usdt", "") + "@forceOrder"
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": [stream_name],
            "id": 1
        }

        collected = []

        try:
            async with websockets.connect(self.ws_url) as websocket:
                # Send subscription
                await websocket.send(json.dumps(subscribe_msg))
                logger.info(f"Subscribed to {stream_name} stream")

                # Collect messages for the duration
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < duration_seconds:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        if "e" in data and data["e"] == "forceOrder":  # Force order event
                            order = data["o"]  # The order object
                            collected.append(order)
                            self._update_top_liquidations(order)
                            logger.info(f"Received liquidation: {order['s']} {order['S']} {order['q']} @ {order['p']}")
                    except asyncio.TimeoutError:
                        continue  # No message, keep waiting
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        break

                return {"rows": collected, "total": len(collected)}

        except Exception as e:
            logger.error(f"WebSocket error for {symbol}: {e}")
            return {"rows": [], "total": 0}

# Example usage
async def main():
    client = BinanceLiquidationClient()

    # Start background collection
    await client.start_background_collection()

    # Wait a bit for some data
    await asyncio.sleep(10)

    # Get top liquidations for a symbol
    top_btc = client.get_top_liquidations("BTCUSDT")
    logger.info(f"Top BTC liquidations: {len(top_btc)}")

    # Stop collection
    await client.stop_background_collection()

if __name__ == "__main__":
    asyncio.run(main())