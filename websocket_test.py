import pandas as pd
import numpy as np
import time
import json
import threading
from collections import defaultdict
from flask import Flask, render_template, Response, g
import finnhub
import websocket # Using websocket-client library
import ssl
import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

app = Flask(__name__)

# --- Configuration ---
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')
if not FINNHUB_API_KEY:
    raise ValueError("FINNHUB_API_KEY not found in .env file. Please add it.")
client = finnhub.Client(api_key=FINNHUB_API_KEY)
# --- Global State for Real-time Prices ---
# This will store the latest prices received from Finnhub WebSocket
# Structure: {'SYMBOL': {'c': close, 'h': high, 'l': low, 'o': open, 'pc': previous_close}}
latest_finnhub_quotes = defaultdict(lambda: {'c': 0, 'pc': 0}) # Initialize with defaults to avoid errors

# --- Finnhub WebSocket Management ---
FINNHUB_WEBSOCKET_URL = f"wss://ws.finnhub.io?token={FINNHUB_API_KEY}"
finnhub_ws = None # Will hold the WebSocket connection object

def on_message(ws, message):
    """Callback for Finnhub WebSocket messages."""
    data = json.loads(message)
    if data and 'data' in data and data['data']:
        for quote in data['data']:
            symbol = quote.get('s')
            if symbol:
                # Update our global dictionary with the latest quote data
                latest_finnhub_quotes[symbol] = {
                    'c': quote.get('p', 0), # Current Price
                    'pc': quote.get('pc', latest_finnhub_quotes[symbol].get('pc', 0)) # Previous Close Price
                    # You might also want 'o', 'h', 'l' if needed for other calculations
                }
                # print(f"Received update for {symbol}: {latest_finnhub_quotes[symbol]}") # For debugging

def on_error(ws, error):
    print(f"❌ Finnhub WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("🚪  Finnhub WebSocket Closed ###")
    # Implement reconnection logic if needed in a production environment

def on_open(ws):
    print("✅  Finnhub WebSocket Opened ###")
    # Subscribe to symbols here after the connection is open
    # We will subscribe to portfolio symbols later, once portfolio is known

def start_finnhub_websocket(symbols_to_subscribe):
    """Starts the Finnhub WebSocket connection in a separate thread."""
    global finnhub_ws
    finnhub_ws = websocket.WebSocketApp(
        FINNHUB_WEBSOCKET_URL,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )

    # Use a separate thread to run the WebSocket app indefinitely
    def run_ws():
        finnhub_ws.run_forever()

    websocket_thread = threading.Thread(target=run_ws)
    websocket_thread.daemon = True # Daemon thread exits when main program exits
    websocket_thread.start()

    # Give a moment for the connection to establish
    time.sleep(1)

    # Subscribe to symbols (this needs to be done *after* on_open and *before* run_forever if possible,
    # or you can send it via on_open callback)
    # For simplicity, we'll send here after a short delay
    for symbol in symbols_to_subscribe:
        print(f"Subscribing to {symbol}")
        finnhub_ws.send(json.dumps({"type": "subscribe", "symbol": symbol}))
        time.sleep(0.3) # Small delay to avoid overwhelming Finnhub if many symbols

# --- Portfolio Manager Class (Modified for SSE & Finnhub WS) ---
class PortfolioManager:
    def __init__(self):
        # In a real app, this would load from a DB or file
        self.transactions = pd.DataFrame([
            {"symbol": "AAPL", "quantity": 10.1871, "cost_basis": 160.80, "date": "2023-01-01", "company_name": "APPLE INC", "type": "equity", "transactionId": "t1"},
            {"symbol": "GOOG", "quantity": 5.5, "cost_basis": 100.00, "date": "2023-03-15", "company_name": "Alphabet Inc Class C", "type": "equity", "transactionId": "t2"},
            {"symbol": "MSFT", "quantity": 2.0, "cost_basis": 300.00, "date": "2023-05-20", "company_name": "Microsoft Corp", "type": "equity", "transactionId": "t3"},
        ])

        # Get all unique symbols to subscribe to Finnhub
        self.all_portfolio_symbols = self.transactions['symbol'].unique().tolist()
        print(f"Portfolio Symbols: {self.all_portfolio_symbols}")

    def get_realtime_quote_from_finnhub_cache(self, symbol):
        """Retrieves the latest quote from our global cache."""
        quote_data = latest_finnhub_quotes.get(symbol, {'c': 0, 'pc': 0})
        return {
            'Close': quote_data['c'],
            'previous_close_price': quote_data['pc']
        }
    def getrealtime(self, symbol):
        quote = client.quote(symbol=symbol)
        
        return {
            'Close': quote.get("c"),
            'High': quote.get("h"),
            'Low': quote.get("l"),
            'Open': quote.get("o"),
            'percent_change': quote.get('dp'),
            'previous_close_price': quote.get("pc"),
        }


    # def _get_price_data(self, symbol):
    #     # This simulated method would fetch historical data, for crypto typically
    #     # For simplicity, returning dummy data if not found in live feed, or you'd fetch from historical API
    #     # In a real scenario, this would likely be fetched from a historical data provider
    #     # or stored locally.
    #     # For this example, we assume crypto symbols rely on external historical
    #     # or you'd have a mock for `previous_close` for cryptos if Finnhub WS doesn't provide it for them.
    #     if symbol == "BTCUSD":
    #          # Simulate historical data for BTCUSD (e.g., from a database/file)
    #         return pd.DataFrame({'Close': [40000, 42000, 43000, 44000, 45000, 46000, 47000]},
    #                              index=pd.to_datetime(['2025-05-17', '2025-05-18', '2025-05-19', '2025-05-20', '2025-05-21', '2025-05-22', '2025-05-23']))
    #     return pd.DataFrame({'Close': [10]}) # Default empty or fetch from other source

    def is_crypto_symbol(self, symbol):
        return symbol in ["BTCUSD", "ETHUSD", "XRPUSD"] # Example crypto symbols

    def is_past_12_in_china(self):
        # This is a dummy for demonstration, implement actual time zone logic
        return False

    def get_current_portfolio_summary(self):
        """
        Calculates the current portfolio summary using the latest real-time prices.
        This method is called periodically by the SSE stream.
        """
        grouped_dict = {
            symbol: group.to_dict(orient='records')
            for symbol, group in self.transactions.groupby('symbol')
        }

        response = []
        total_value = 0
        total_day_gain = 0
        total_cost_basis = 0
        type_breakdown = {}

        for symbol, purchases in grouped_dict.items():
            live_quote_data = self.getrealtime(symbol)
            # csv_path = os.path.join('data', f"{symbol}.json")
            # df = pd.read_json(csv_path)
            # live_quote_data = df.iloc[-1]
            price = live_quote_data['Close']
            prev_close = live_quote_data['previous_close_price']

            # If no live price yet, skip or use a fallback (e.g., previous close from stored data)
            if price == 0 and prev_close == 0:
                print(f"Warning: No real-time data for {symbol}. Skipping or using fallback.")
                continue # Skip this symbol for now, or use last known good data

            # Special handling for crypto previous close if Finnhub WS doesn't provide it
            if self.is_crypto_symbol(symbol) and (prev_close == 0 or prev_close == price): # Finnhub crypto 'pc' might be 0 or same as 'c' initially
                # You might need to fetch historical previous close for crypto separately
                # For this example, we'll try to get it from _get_price_data for crypto
                previous_close_series = live_quote_data
                if not previous_close_series.empty:
                    prev_close = previous_close_series.iloc[-2] if self.is_past_12_in_china() else previous_close_series.iloc[-1]
                else:
                    prev_close = price # Fallback if no historical data found
                # If prev_close is still 0 or unavailable, set to price to avoid division by zero
                if prev_close == 0: prev_close = price

            total_quantity = sum(p["quantity"] for p in purchases)
            value = round(price * total_quantity, 2)

            day_gain = round((price - prev_close) * total_quantity, 2) if prev_close else 0
            day_gain_percent = round((price - prev_close) / prev_close * 100, 2) if prev_close and prev_close != 0 else 0

            total_value += value
            total_day_gain += day_gain

            purchases_detail = []
            for p in purchases:
                qty = p["quantity"]
                basis = p["cost_basis"]
                gain = (price - basis) * qty
                gain_percent = ((price - basis) / basis * 100) if basis and basis != 0 else 0
                market_value = price * qty
                total_cost_basis += basis * qty

                purchases_detail.append({
                    "transactionId": p["transactionId"],
                    "date": p["date"],
                    "purchasePrice": basis,
                    "quantity": qty,
                    "value": round(market_value, 2),
                    "totalGain": round(gain, 2),
                    "totalGainPercent": round(gain_percent, 2)
                })

            category = purchases[0]['type'].lower()
            type_breakdown[category] = type_breakdown.get(category, 0) + value

            response.append({
                "id": symbol.lower(),
                "symbol": symbol,
                "name": purchases[0]['company_name'],
                "price": price,
                "quantity": round(total_quantity, 4),
                "dayGain": round(day_gain, 2),
                "dayGainPercent": round(day_gain_percent, 2),
                "value": value,
                "purchases": purchases_detail
            })

        total_gain = total_value - total_cost_basis
        total_gain_percent = (total_gain / total_cost_basis * 100) if total_cost_basis and total_cost_basis != 0 else 0

        yesterday_value = total_value - total_day_gain
        day_percent = (total_day_gain / yesterday_value * 100) if yesterday_value and yesterday_value != 0 else 0

        # Current time in Taiwan (UTC+8)
        # Using datetime.now() with timezone info for accurate "Asia/Shanghai" which is UTC+8
        from datetime import datetime
        import pytz
        tz = pytz.timezone('Asia/Shanghai')
        timestamp = datetime.now(tz).strftime("%b %d, %I:%M:%S %p UTC+8")

        portfolio_highlights = [
            {"name": k, "percent": round(v / total_value * 100, 1), "value": round(v, 2)}
            for k, v in type_breakdown.items()
        ] if total_value else [] # Avoid division by zero if total_value is 0

        return {
            "balance": round(total_value, 2),
            "dayChange": round(total_day_gain, 2),
            "dayPercent": round(day_percent, 2),
            "totalGain": round(total_gain, 2),
            "totalGainPercent": round(total_gain_percent, 2),
            "timestamp": timestamp,
            "portfolioHighlights": portfolio_highlights,
            "positions": response
        }

# --- Flask Routes ---
portfolio_manager = PortfolioManager() # Instantiate the manager once

@app.before_request
def before_request():
    # This ensures the Finnhub WebSocket connection is started only once
    # when the first request comes in, or more robustly, at app startup.
    if not hasattr(g, 'finnhub_ws_started'):
        start_finnhub_websocket(portfolio_manager.all_portfolio_symbols)
        g.finnhub_ws_started = True

@app.route('/')
def index():
    return render_template('websocket_test.html')

@app.route('/portfolio-stream')
def portfolio_stream():
    def generate_portfolio_updates():
        while True:
            # Get the latest calculated portfolio info
            portfolio_info = portfolio_manager.get_current_portfolio_summary()
            
            # Send it as an SSE event
            yield f"data: {json.dumps(portfolio_info)}\n\n"
            time.sleep(5) # Send updates every 5 seconds

    return Response(generate_portfolio_updates(), mimetype='text/event-stream')

if __name__ == '__main__':
    # It's crucial to set up the timezone for the timestamp
    try:
        import pytz
    except ImportError:
        print("Please install pytz: pip install pytz")
        exit()

    # For development: debug=True allows hot-reloading, threaded=True allows multiple SSE clients.
    # In production, use a production WSGI server like Gunicorn with eventlet/gevent workers.
    app.run(debug=True, threaded=True)