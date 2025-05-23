from flask import Flask, render_template, jsonify, request
import yfinance as yf
from datetime import datetime, timedelta

from portfolio_data_manager import PortfolioDataManager
import finnhub
import os

from portfolio_manager import PortfolioManager

app = Flask(__name__)
manager = PortfolioManager()
finnhub_key = os.getenv("FINNHUB_API_KEY")
finnhub_client = finnhub.Client(api_key=finnhub_key)



import portfolio_routes


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/equity')
def equity():
    equity_history = manager.compute_equity_history()
    return jsonify(equity_history)

@app.route('/api/symbolSuggestion')
def fetchSymbolSuggestions():
    typed_chars = request.args.get('q', '')
    sugggestions = finnhub_client.symbol_lookup(typed_chars)
    return jsonify(sugggestions)

@app.route('/api/equity/intraday')
def intraday_equity():
    days = int(request.args.get('days', 1))  # 1 or 5
    interval = request.args.get('interval', '1m')  # '1m', '5m', '30m' etc.
    end = datetime.utcnow()
    start = end - timedelta(days=days)

    equity_points = {}
    for asset, quantity in manager.get_current_holdings().items():
        if asset in ['USDT', 'ETH', 'ADA']:  # skip crypto for now unless mapped
            continue
        
        ticker = yf.Ticker(asset)
        try:
            hist = ticker.history(start=start, end=end, interval=interval, auto_adjust=False)
            for t, row in hist.iterrows():
                timestamp = int(t.timestamp())
                price = row['Close']
                equity_points.setdefault(timestamp, 0)
                equity_points[timestamp] += float(price) * quantity
                
        except Exception as e:
            print(f"Failed to fetch {asset}: {e}")

    # Convert and sort
    result = [{"time": ts, "equity": round(val, 2)} for ts, val in sorted(equity_points.items())]
    return jsonify(result)


if __name__ == '__main__':
    # manager.add_transaction(symbol="VTI", quantity=92.0149, cost_basis=286.77, date=None, company_name="VTI INSTRUMENTS")
    # manager.add_transaction(symbol="VOO", quantity=41.8308, cost_basis=535.77, date=None, company_name="VOO INDEX")
    # manager.add_transaction(symbol="V", quantity=269.2974, cost_basis=358.30, date=None, company_name="VISA")
    
    # manager.add_transaction(symbol="UBER", quantity=175, cost_basis=88.67, date=None, company_name="UBER")
    # manager.add_transaction(symbol="SPY", quantity=21.155, cost_basis=582.86, date=None, company_name="SPY INDEX")
    # manager.add_transaction(symbol="HOOD", quantity=500, cost_basis=63.14, date=None, company_name="ROBINHOOD")
    # manager.add_transaction(symbol="RDDT", quantity=120, cost_basis=183.43, date=None, company_name="REDDIT")
    # manager.add_transaction(symbol="MSFT", quantity=21.3218, cost_basis=358.19, date=None, company_name="MICROSOFT")
    # manager.add_transaction(symbol="USDT-USD", quantity=298711.14, cost_basis=1.00, date=None, company_name="CASH")
    # manager.add_transaction(symbol="ETH-USD", quantity=1.0745, cost_basis=2625.81, date=None, company_name="ETHEREUM")
    # manager.add_transaction(symbol="ADA-USD", quantity=1492.884029, cost_basis=0.34, date=None, company_name="CARDANO")
    # manager.add_transaction(symbol="BTC-USD", quantity=0.20302474, cost_basis=16941.42, date=None, company_name="BITCOIN")


    app.run(debug=True)
