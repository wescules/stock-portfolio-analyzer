from flask import Flask, render_template, jsonify
import random
import time
import yfinance as yf
import pandas as pd
import googlefinance

app = Flask(__name__)

# Simulated stock/crypto data
portfolio_data = [
    {"symbol": "VTI", "name": "Vanguard Total Stock Market Ind...", "price": 286.77, "quantity": 92.0149},
    # {"symbol": "VOO", "name": "Vanguard S&P 500 ETF", "price": 535.77, "quantity": 41.8308},
    # {"symbol": "V", "name": "Visa Inc", "price": 358.30, "quantity": 269.2974},
    # {"symbol": "UBER", "name": "Uber Technologies Inc", "price": 88.67, "quantity": 175},
    # {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "price": 582.86, "quantity": 21.155},
    # {"symbol": "USDT", "name": "Tether (USDT / USD)", "price": 1.00, "quantity": 298711.14},
    # {"symbol": "ETH", "name": "Ether (ETH / USD)", "price": 2625.81, "quantity": 1.0745},
    # {"symbol": "ADA", "name": "Cardano (ADA / USD)", "price": 0.79, "quantity": 1492.884029},
]


# Your portfolio
portfolio = {
    "VTI": 92.0149,
    # "VOO": 41.8308,
    # "V": 269.2974,
    # "UBER": 175,
    # "SPY": 21.155,
    # "USDT": 298711.14,
    # "ETH-USD": 1.0745,
    # "ADA-USD": 1492.884029,
}


# Historical price tracking
price_history = {asset['symbol']: [] for asset in portfolio_data}
equity_history = []  # stores total equity over time


# Adjust tickers for yfinance
tickers = list(portfolio.keys())

# Download historical prices
data = yf.download(tickers=tickers, period="6mo", interval="1d", group_by='ticker')

# Build equity over time
equity_history = []

for date in data.index:
    total_equity = 0
    for symbol, quantity in portfolio.items():
        try:
            if symbol in ["ETH-USD", "ADA-USD"]:
                price = data[symbol]["Close"][date]
            else:
                price = data[symbol]["Close"][date]
            total_equity += price * quantity
        except KeyError:
            continue  # handle missing data
    equity_history.append({"time": int(pd.Timestamp(date).timestamp()), "equity": round(total_equity, 2)})
    print(int(pd.Timestamp(date).timestamp()))
    print(total_equity)

@app.route('/')
def index():
    return render_template('index.html', portfolio=portfolio_data)

@app.route('/api/prices')
def prices():
    timestamp = int(time.time())
    total_equity = 0

    for asset in portfolio_data:
        change = random.uniform(-1, 1)
        asset['price'] = round(asset['price'] + change, 2)
        value = asset['price'] * asset['quantity']
        total_equity += value
        price_history[asset['symbol']].append({"time": timestamp, "price": asset['price']})
        if len(price_history[asset['symbol']]) > 1000:
            price_history[asset['symbol']] = price_history[asset['symbol']][-1000:]

    equity_history.append({"time": timestamp, "equity": round(total_equity, 2)})
    if len(equity_history) > 1000:
        equity_history[:] = equity_history[-1000:]

    return jsonify(portfolio_data)

@app.route('/api/history')
def history():
    return jsonify(price_history)

@app.route('/api/equity')
def equity():
    return jsonify(equity_history)

@app.route('/api/equity/intraday')
def intraday_equity():
    now = int(time.time())
    one_day_ago = now - 60 * 60 * 24
    five_days_ago = now - 60 * 60 * 24 * 5

    interval = 60  # 1 minute
    equity_data = []

    for t in range(five_days_ago, now + 1, interval):
        total_equity = 0
        for asset in portfolio_data:
            # Simulate high-frequency price fluctuations
            simulated_price = asset['price'] + random.uniform(-0.5, 0.5)
            value = simulated_price * asset['quantity']
            total_equity += value

        equity_data.append({"time": t, "equity": round(total_equity, 2)})

    return jsonify(equity_data)


if __name__ == '__main__':
    app.run(debug=True)



# Save to JSON or inject into Flask variable
import json
with open("equity_history.json", "w") as f:
    json.dump(equity_history, f, indent=2)
