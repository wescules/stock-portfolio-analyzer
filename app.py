from flask import Flask, render_template, jsonify, request
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
from portfolio_data_manager import PortfolioDataManager
import finnhub
import os
import requests
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

def search_coins(query):
    url = f"https://api.coingecko.com/api/v3/search?query={query}"
    response = requests.get(url, timeout=10)
    data = response.json().get('coins', [])
    
    result = []
    for coin in data:
        result.append({
            "description": coin.get("name", "").upper(),  # name of the coin
            "displaySymbol": coin.get("id", "").upper(),  # shorthand like BTC
            "symbol": coin.get("symbol", "").upper(),  # CoinGecko's unique ID
            "type": "Crypto"  # Custom type field
        })
        if len(result) > 4:
            return result
    
    return result


@app.route('/api/symbolSuggestion')
def fetchSymbolSuggestions():
    typed_chars = request.args.get('q', '')
    finnhub_sugggestions = finnhub_client.symbol_lookup(typed_chars)
    crypto_suggestions = search_coins(typed_chars)
    return jsonify(finnhub_sugggestions['result'] + crypto_suggestions)

@app.route('/api/equity/intraday')
def intraday_equity():
    days = int(request.args.get('days', 1))  # 1 or 5
    interval = request.args.get('interval', '1m')  # '1m', '5m', '30m' etc.
    end = datetime.utcnow()
    start = end - timedelta(days=days)

    equity_points = {}
    # tickers = list(manager.get_current_holdings().keys())
    # price_data = yf.download(tickers=tickers, interval=interval, start=start, end=end, auto_adjust=False)
    
    # # Cache current holdings
    # holdings = manager.get_current_holdings()

    # # Only keep columns for current holdings
    # price_data = price_data['Close'][list(holdings.keys())]
    # price_data = price_data.fillna(0)

    # # Multiply each column by the quantity held
    # for symbol, qty in holdings.items():
    #     price_data[symbol] = price_data[symbol] * qty

    # # Sum across columns (each row is total equity on that date)
    # price_data['equity'] = price_data.sum(axis=1)

    # # Return as list of dicts with timestamp
    # equity_history = [
    #     {"time": int(pd.Timestamp(ts).timestamp()), "equity": round(equity, 2)}
    #     for ts, equity in zip(price_data.index, price_data['equity'])
    # ]

    # return jsonify(equity_history)

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
    # manager.add_transaction(symbol="VTI", quantity=92.0149, cost_basis=286.77, date=None, company_name="VTI INSTRUMENTS", type="ETF")
    # manager.add_transaction(symbol="VOO", quantity=41.8308, cost_basis=535.77, date=None, company_name="VOO INDEX", type="ETF")
    # manager.add_transaction(symbol="V", quantity=269.2974, cost_basis=358.30, date=None, company_name="VISA", type="STOCK")
    
    # manager.add_transaction(symbol="UBER", quantity=175, cost_basis=88.67, date=None, company_name="UBER", type="STOCK")
    # manager.add_transaction(symbol="SPY", quantity=21.155, cost_basis=582.86, date=None, company_name="SPY INDEX", type="ETF")
    # manager.add_transaction(symbol="HOOD", quantity=500, cost_basis=63.14, date=None, company_name="ROBINHOOD", type="STOCK")
    # manager.add_transaction(symbol="RDDT", quantity=120, cost_basis=183.43, date=None, company_name="REDDIT", type="STOCK")
    # manager.add_transaction(symbol="MSFT", quantity=21.3218, cost_basis=358.19, date=None, company_name="MICROSOFT", type="STOCK")
    # manager.add_transaction(symbol="USDT-USD", quantity=298711.14, cost_basis=1.00, date=None, company_name="CASH", type="CASH")
    # manager.add_transaction(symbol="ETH-USD", quantity=1.0745, cost_basis=2625.81, date=None, company_name="ETHEREUM", type="CRYPTO")
    # manager.add_transaction(symbol="ADA-USD", quantity=1492.884029, cost_basis=0.34, date=None, company_name="CARDANO", type="CRYPTO")
    # manager.add_transaction(symbol="BTC-USD", quantity=0.20302474, cost_basis=16941.42, date=None, company_name="BITCOIN", type="CRYPTO")

    app.run(debug=True)