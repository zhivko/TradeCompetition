import xml.etree.ElementTree as ET
from datetime import datetime
import time
import threading
import json
import os
from logging_config import logger
from flask import Flask, render_template, jsonify, request, make_response
from flask_socketio import SocketIO, emit
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

app = Flask(__name__)
socketio = SocketIO(app)

# WebSocket connections
connected_clients = set()

INITIAL_CAPITAL = 10000.0

class DashboardFileHandler(FileSystemEventHandler):
    """Handler for file system events in dashboard directories"""

    def on_modified(self, event):
        """Called when a file is modified"""
        if not event.is_directory:
            # Check if the file is in templates or static directories
            if 'templates' in event.src_path or 'static' in event.src_path:
                logger.info(f"Dashboard file changed: {event.src_path}")
                # Notify all connected clients to reload
                socketio.emit('reload_page', {'message': 'Dashboard files updated'})

    def on_created(self, event):
        """Called when a file is created"""
        if not event.is_directory:
            if 'templates' in event.src_path or 'static' in event.src_path:
                logger.info(f"Dashboard file created: {event.src_path}")
                socketio.emit('reload_page', {'message': 'Dashboard files updated'})

    def on_deleted(self, event):
        """Called when a file is deleted"""
        if not event.is_directory:
            if 'templates' in event.src_path or 'static' in event.src_path:
                logger.info(f"Dashboard file deleted: {event.src_path}")
                socketio.emit('reload_page', {'message': 'Dashboard files updated'})

class DashboardDataManager:
    """Manages data extraction from trade.xml for the dashboard"""

    def __init__(self, xml_file="trade.xml"):
        self.xml_file = xml_file
        self.last_update = None

    def get_agents_data(self):
        """Extract all agent data from XML"""
        if not os.path.exists(self.xml_file) or os.path.getsize(self.xml_file) == 0:
            return []
        try:
            tree = ET.parse(self.xml_file)
            root = tree.getroot()

            agents_data = []

            # Handle both old and new XML structures
            if root.tag == "trading":
                agents_elem = root.find("agents")
                if agents_elem is not None:
                    for agent_elem in agents_elem.findall("agent"):
                        agent_data = self._parse_agent_element(agent_elem)
                        if agent_data:
                            agents_data.append(agent_data)
            else:
                # Old structure - single agent
                agent_data = self._parse_agent_element(root)
                if agent_data:
                    agents_data.append(agent_data)

            return agents_data

        except Exception as e:
            logger.info(f"Error parsing XML: {e}")
            return []


    def _parse_agent_element(self, agent_elem):
        """Parse individual agent element"""
        try:
            agent_kind = agent_elem.get("kind", "Unknown")

            # Get summary data
            summary_elem = agent_elem.find("summary")
            summary = {}
            if summary_elem is not None:
                for elem in summary_elem:
                    try:
                        summary[elem.tag] = float(elem.text or 0.0)
                    except (ValueError, TypeError):
                        summary[elem.tag] = 0.0

            # Calculate PNL
            current_value = summary.get("current_account_value", INITIAL_CAPITAL)
            pnl = current_value - INITIAL_CAPITAL
            pnl_percentage = (pnl / INITIAL_CAPITAL) * 100 if INITIAL_CAPITAL > 0 else 0

            # Get active trades
            active_trades = []
            active_trades_elem = agent_elem.find("active_trades")
            if active_trades_elem is not None:
                for trade_elem in active_trades_elem:
                    trade_data = self._parse_trade_element(trade_elem)
                    if trade_data:
                        active_trades.append(trade_data)

            # Get closed trades
            closed_trades = []
            closed_trades_elem = agent_elem.find("closed_trades")
            if closed_trades_elem is not None:
                for trade_elem in closed_trades_elem:
                    trade_data = self._parse_trade_element(trade_elem)
                    if trade_data:
                        closed_trades.append(trade_data)

            # Get latest response
            latest_response = None
            response_elem = agent_elem.find("response")
            if response_elem is not None and response_elem.text:
                try:
                    latest_response = json.loads(response_elem.text)
                except json.JSONDecodeError:
                    latest_response = {"raw": response_elem.text}

            # Also check for latest_response element
            latest_response_elem = agent_elem.find("latest_response")
            if latest_response_elem is not None:
                response_elem = latest_response_elem.find("response")
                if response_elem is not None and response_elem.text:
                    try:
                        latest_response = json.loads(response_elem.text)
                    except json.JSONDecodeError:
                        latest_response = {"raw": response_elem.text}

            # Get timestamp from latest trade instead of response
            timestamp = None
            all_trades = active_trades + closed_trades
            if all_trades:
                # Find the most recent trade timestamp
                timestamps = [trade.get('timestamp') for trade in all_trades if trade.get('timestamp')]
                if timestamps:
                    timestamp = max(timestamps)
            # Fallback to response timestamp if no trades
            elif latest_response and 'timestamp' in latest_response:
                timestamp = latest_response['timestamp']

            return {
                "kind": agent_kind,
                "summary": summary,
                "pnl": pnl,
                "pnl_percentage": pnl_percentage,
                "active_trades": active_trades,
                "closed_trades": closed_trades,
                "latest_response": latest_response,
                "timestamp": timestamp,
                "active_trades_count": len(active_trades),
                "closed_trades_count": len(closed_trades)
            }

        except Exception as e:
            logger.info(f"Error parsing agent element: {e}")
            return None

    def _parse_trade_element(self, trade_elem):
        """Parse individual trade element"""
        try:
            trade_data = {}
            for elem in trade_elem:
                if elem.tag in ["entry_price", "quantity", "stop_loss", "exit_price", "pnl", "unrealized_pnl"]:
                    try:
                        trade_data[elem.tag] = float(elem.text or 0.0)
                    except (ValueError, TypeError):
                        trade_data[elem.tag] = 0.0
                elif elem.tag in ["timestamp", "symbol", "action", "status"]:
                    trade_data[elem.tag] = elem.text or ""
                elif elem.tag == "coin":
                    trade_data["symbol"] = elem.text.upper() if elem.text else ""
                elif elem.tag == "price":
                    # For closed trades, price is exit_price
                    try:
                        trade_data["exit_price"] = float(elem.text or 0.0)
                    except (ValueError, TypeError):
                        trade_data["exit_price"] = 0.0
                elif elem.tag == "reasoning":
                    # Extract reasoning text and check for manual stop loss calculation
                    reasoning_text = elem.text or ""
                    trade_data["reasoning"] = reasoning_text
                    trade_data["stop_loss_source"] = "manual" if "Stop-loss calculated manually" in reasoning_text else "llm"
                else:
                    trade_data[elem.tag] = elem.text or ""

            return trade_data

        except Exception as e:
            logger.info(f"Error parsing trade element: {e}")
            return None

    def get_market_data(self):
        """Extract market data from XML"""
        if not os.path.exists(self.xml_file) or os.path.getsize(self.xml_file) == 0:
            return {}
        try:
            tree = ET.parse(self.xml_file)
            root = tree.getroot()

            market_data = {}

            # Handle both old and new XML structures
            if root.tag == "trading":
                state_of_market = root.find("state_of_market")
            else:
                state_of_market = root.find("state_of_market")

            if state_of_market is not None:
                for coin_elem in state_of_market.findall("coin"):
                    coin_name = coin_elem.find("name").text.lower()
                    coin_data = {}

                    # Get current price and indicators
                    for elem in coin_elem:
                        if elem.tag == "name":
                            continue
                        elif elem.tag.endswith("_series"):
                            # Handle series data
                            values = []
                            for value_elem in elem.findall("value"):
                                try:
                                    values.append(float(value_elem.text))
                                except (ValueError, TypeError):
                                    values.append(0.0)
                            coin_data[elem.tag] = values
                        else:
                            try:
                                coin_data[elem.tag] = float(elem.text) if elem.text and elem.text.replace('.', '', 1).replace('-', '', 1).replace('e', '', 1).replace('+', '', 1).isdigit() else elem.text
                            except (ValueError, TypeError, AttributeError):
                                coin_data[elem.tag] = elem.text

                    market_data[coin_name] = coin_data

            return market_data

        except Exception as e:
            logger.info(f"Error parsing market data: {e}")
            return {}

    def get_leaderboard_data(self):
        """Generate leaderboard data sorted by PNL and Sharpe ratio"""
        agents = self.get_agents_data()

        # Sort by PNL descending, then by Sharpe ratio descending
        sorted_agents = sorted(agents,
                             key=lambda x: (x["pnl"], x.get("summary", {}).get("sharpe_ratio", 0)),
                             reverse=True)

        leaderboard = []
        for rank, agent in enumerate(sorted_agents, 1):
            leaderboard.append({
                "rank": rank,
                "agent": agent["kind"],
                "pnl": agent["pnl"],
                "pnl_percentage": agent["pnl_percentage"],
                "sharpe_ratio": agent.get("summary", {}).get("sharpe_ratio", 0),
                "active_trades": agent["active_trades_count"],
                "closed_trades": agent["closed_trades_count"]
            })

        return leaderboard

# Initialize data manager
data_manager = DashboardDataManager()

@app.route('/')
def index():
    """Redirect to live page"""
    response = make_response(render_template('live.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/live')
def live():
    """Live dashboard page"""
    response = make_response(render_template('live.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/leaderboard')
def leaderboard():
    """Leaderboard page"""
    response = make_response(render_template('leaderboard.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/models')
def models():
    """Models page"""
    response = make_response(render_template('models.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/agents')
def api_agents():
    """API endpoint for agent data"""
    agents = data_manager.get_agents_data()
    response = make_response(jsonify(agents))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/market')
def api_market():
    """API endpoint for market data"""
    market = data_manager.get_market_data()
    response = make_response(jsonify(market))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/leaderboard')
def api_leaderboard():
    """API endpoint for leaderboard data"""
    leaderboard = data_manager.get_leaderboard_data()
    response = make_response(jsonify(leaderboard))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@socketio.on('connect')
def handle_connect(auth=None):
    logger.info('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

@socketio.on('request_update')
def handle_request_update():
    # Force fresh read from XML file
    data_manager.__init__('trade.xml')  # Reinitialize to clear any cached data
    agents = data_manager.get_agents_data()
    market = data_manager.get_market_data()
    leaderboard = data_manager.get_leaderboard_data()

    # Get the latest timestamp from agents
    latest_timestamp = datetime.now().isoformat()
    for agent in agents:
        if agent.get('timestamp'):
            latest_timestamp = agent['timestamp']
            break

    emit('data_update', {
        'agents': agents,
        'market': market,
        'leaderboard': leaderboard,
        'timestamp': latest_timestamp
    })

def background_update():
    """Background task for periodic updates"""
    while True:
        try:
            # Send updates to all connected clients
            agents = data_manager.get_agents_data()
            market = data_manager.get_market_data()
            leaderboard = data_manager.get_leaderboard_data()

            # Get the latest timestamp from agents
            latest_timestamp = datetime.now().isoformat()
            for agent in agents:
                if agent.get('timestamp'):
                    latest_timestamp = agent['timestamp']
                    break

            update_data = {
                'agents': agents,
                'market': market,
                'leaderboard': leaderboard,
                'timestamp': latest_timestamp
            }

            # Send to all connected clients
            socketio.emit('data_update', update_data)

        except Exception as e:
            logger.info(f"Error in background update: {e}")

        # Update every 5 seconds
        time.sleep(5)

# Start background thread
update_thread = threading.Thread(target=background_update)
update_thread.daemon = True
update_thread.start()

# Setup file watcher for dashboard files
file_handler = DashboardFileHandler()
observer = Observer()
observer.schedule(file_handler, path='templates', recursive=True)
observer.schedule(file_handler, path='static', recursive=True)
observer.start()

if __name__ == '__main__':
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    finally:
        observer.stop()
        observer.join()