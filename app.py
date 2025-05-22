from flask import Flask, render_template, jsonify, request
import random
import time
import yfinance as yf
import pandas as pd
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import finnhub

from portfolio_data_manager import PortfolioDataManager

from portfolio_manager import PortfolioManager
# load_dotenv()

# # Access your keys
# finnhub_key = os.getenv("FINNHUB_API_KEY")

# print(finnhub_key)

# # Setup client
# client = finnhub.Client(api_key=finnhub_key)

# # Get real-time quote
# quote = client.quote('AAPL')
# print(f"Current price: ${quote['c']} | Pre-market: ${quote['pc']}")

app = Flask(__name__)
manager = PortfolioManager()
# manager = # `PortfolioDataManager` is a class that is responsible for managing portfolio data. In this
# code snippet, it is being used to manage data related to equity symbols such as 'VTI' and
# 'VOO'. The `PortfolioDataManager` class likely has methods to fetch equity history data,
# update portfolio information, and handle data related to the portfolio's performance over
# time. It helps in organizing and handling the portfolio data efficiently within the
# application.
PortfolioDataManager(symbols=['VTI', 'VOO'])


# import portfolio_routes


# # Load historical data and prices at startup
equity_history = []

portfolio_data = [
    {"symbol": "VTI", "name": "Vanguard Total Stock Market Index", "cost_basis": 286.77, "quantity": 92.0149},
    # {"symbol": "VOO", "name": "Vanguard S&P 500 ETF", "cost_basis": 535.77, "quantity": 41.8308},
    # {"symbol": "V", "name": "Visa Inc", "cost_basis": 358.30, "quantity": 269.2974},
    # {"symbol": "UBER", "name": "Uber Technologies Inc", "cost_basis": 88.67, "quantity": 175},
    # {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "cost_basis": 582.86, "quantity": 21.155},
    # {"symbol": "USDT", "name": "Tether (USDT / USD)", "cost_basis": 1.00, "quantity": 298711.14},
    # {"symbol": "ETH", "name": "Ether (ETH / USD)", "cost_basis": 2625.81, "quantity": 1.0745},
    # {"symbol": "ADA", "name": "Cardano (ADA / USD)", "cost_basis": 0.79, "quantity": 1492.884029},
]


# # Historical price tracking
# price_history = {asset['symbol']: [] for asset in portfolio_data}
# equity_history = []  # stores total equity over time

# portfolio = { "VTI": 100}
# # Adjust tickers for yfinance
# tickers = list(portfolio.keys())

# # Download historical prices
# data = yf.download(tickers=tickers, period="6mo", interval="1d", group_by='ticker', auto_adjust=True)

# # Build equity over time
# equity_history = []

# for date in data.index:
#     total_equity = 0
#     for symbol, quantity in portfolio.items():
#         try:
#             if symbol in ["ETH-USD", "ADA-USD"]:
#                 price = data[symbol]["Close"][date]
#             else:
#                 price = data[symbol]["Close"][date]
#             total_equity += price * quantity
#         except KeyError:
#             continue  # handle missing data
#     equity_history.append({"time": int(pd.Timestamp(date).timestamp()), "equity": round(total_equity, 2)})


# print(equity_history)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/equity')
def equity():
    return jsonify(equity_history)

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
            hist = ticker.history(start=start, end=end, interval=interval)
            for t, row in hist.iterrows():
                timestamp = int(t.timestamp())
                price = row['Close']
                equity_points.setdefault(timestamp, 0)
                equity_points[timestamp] += price * quantity
        except Exception as e:
            print(f"Failed to fetch {asset}: {e}")

    # Convert and sort
    result = [{"time": ts, "equity": round(val, 2)} for ts, val in sorted(equity_points.items())]
    return jsonify(result)


if __name__ == '__main__':
    manager.add_transaction(symbol="VTI", quantity=92.0149, cost_basis=286.77, date=None)
    manager.add_transaction(symbol="VOO", quantity=41.8308, cost_basis=535.77, date=None)
    manager.add_transaction(symbol="V", quantity=269.2974, cost_basis=358.30, date=None)
    manager.add_transaction(symbol="UBER", quantity=175, cost_basis=88.67, date=None)
    manager.add_transaction(symbol="SPY", quantity=21.155, cost_basis=582.86, date=None)
    manager.add_transaction(symbol="HOOD", quantity=500, cost_basis=63.14, date=None)
    manager.add_transaction(symbol="RDDT", quantity=120, cost_basis=183.43, date=None)
    manager.add_transaction(symbol="MSFT", quantity=21.3218, cost_basis=358.19, date=None)
    manager.add_transaction(symbol="USDT-USD", quantity=298711.14, cost_basis=1.00, date=None)
    manager.add_transaction(symbol="ETH-USD", quantity=1.0745, cost_basis=2625.81, date=None)
    manager.add_transaction(symbol="ADA-USD", quantity=1492.884029, cost_basis=0.34, date=None)
    manager.add_transaction(symbol="BTC-USD", quantity=0.20302474, cost_basis=16941.42, date=None)






    
    print(manager.get_transactions(symbol="VTI"))
    print(manager.portfolio_pnl())
    print(manager.transaction_pnl(symbol="VTI"))
    equity_history = manager.compute_equity_history()

    app.run(debug=True)
