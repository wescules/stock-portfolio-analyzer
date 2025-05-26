from urllib import response
from flask import Flask, render_template, jsonify, request
import yfinance as yf
from datetime import datetime, timedelta
import finnhub
import os
import pandas as pd
from portfolio_manager import PortfolioManager
import threading
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
manager = PortfolioManager()
finnhub_key = os.getenv("FINNHUB_API_KEY")
finnhub_client = finnhub.Client(api_key=finnhub_key)
thread_local = threading.local()


import portfolio_routes


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/equity')
def equity():
    equity_history = manager.compute_equity_history()
    return jsonify(equity_history)


def get_finnhub_suggestions(query):
    try:
        return finnhub_client.symbol_lookup(query).get('result', [])
    except:
        return []

def get_crypto_suggestions(query):
    try:
        return portfolio_routes.search_coins(query)
    except:
        return []

# Added mutithreading. 50% improvement in t load time
def get_combined_suggestions(typed_chars):
    with ThreadPoolExecutor() as executor:
        future_finnhub = executor.submit(get_finnhub_suggestions, typed_chars)
        future_crypto = executor.submit(get_crypto_suggestions, typed_chars)

        finnhub_suggestions = future_finnhub.result()
        crypto_suggestions = future_crypto.result()

    return finnhub_suggestions + crypto_suggestions

@app.route('/api/symbolSuggestion')
def fetchSymbolSuggestions():
    typed_chars = request.args.get('q', '')
    data = get_combined_suggestions(typed_chars)
    return jsonify(data)

@app.route('/api/equity/intraday')
def intraday_equity():
    days = int(request.args.get('days', 1))  # 1 or 5
    interval = request.args.get('interval', '1m')  # '1m', '5m', '30m' etc.
    end = datetime.utcnow()
    start = end - timedelta(days=days)

    holdings = manager.get_positions()

    # Only keep columns for current holdings
    price_data = yf.download(tickers=set(holdings.keys()), interval=interval, start=start, end=end, auto_adjust=False, prepost=False)
    # Optional: Ensure data is within regular trading hours (in case prepost=True or mixed)
    price_data = price_data.tz_localize(None)  # Sometimes needed before timezone conversion
    price_data.index = price_data.index.tz_localize('UTC').tz_convert('America/New_York')

    # Keep only data within regular market hours (9:30 AM to 4:00 PM)
    price_data = price_data.between_time("09:30", "16:00")

    # Multiply each column by the quantity held
    for symbol, qty in holdings.items():
        price_data[('Close', symbol)] = price_data[('Close', symbol)] * qty

    # Sum across columns (each row is total equity on that date)
    price_data = price_data.fillna(0)
    price_data['equity'] = price_data[('Close')].sum(axis=1)
            
    price_data['equity'].dropna(inplace=True)
            
    price_data['equity_pct_change'] = price_data['equity'].pct_change()

    # Identify rows where the equity dropped by more than 10%
    # This gets rid of trading holidays. We dont have data from weekends or holidays
    rows_to_drop = price_data[price_data['equity_pct_change'] < -0.10].index
    price_data.drop(rows_to_drop, inplace=True)
    price_data_cleaned = price_data.drop(columns=['equity_pct_change'])
    equity = price_data_cleaned['equity'].dropna()
    
    # Return as list of dicts with timestamp
    equity_history = [
        {"time": int(pd.Timestamp(ts).timestamp()), "equity": round(equity, 2)}
        for ts, equity in zip(equity.index, equity)
    ]

    return jsonify(equity_history)


if __name__ == '__main__':
    # manager.add_transaction(symbol="AAPL", quantity=10.1871, cost_basis=160.80, date=None, company_name="APPLE INC", type="Equity", action="buy")
    # manager.add_transaction(symbol="HOOD", quantity=500, cost_basis=63.14, date=None, company_name="ROBINHOOD MKTS INC CLA...", type="Equity", action="buy")
    # manager.add_transaction(symbol="META", quantity=248.2124, cost_basis=172.60, date=None, company_name="META PLATFORMS INC CLAS...", type="Equity", action="buy")
    # manager.add_transaction(symbol="GOOG", quantity=90.1075, cost_basis=201.19, date=None, company_name="ALPHABET INC CLASS C", type="Equity", action="buy")
    # manager.add_transaction(symbol="ATYR", quantity=1000, cost_basis=3.04, date=None, company_name="ATYR PHARMA INC", type="Equity", action="buy")
    # manager.add_transaction(symbol="V", quantity=184.2974, cost_basis=180.54, date=None, company_name="VISA INC CLASS A", type="Equity", action="buy")
    # manager.add_transaction(symbol="V", quantity=50, cost_basis=358.38, date=None, company_name="VISA INC CLASS A", type="Equity", action="buy")
    # manager.add_transaction(symbol="V", quantity=85, cost_basis=366.94, date=None, company_name="VISA INC CLASS A", type="Equity", action="buy")
    # manager.add_transaction(symbol="MSFT", quantity=21.3218, cost_basis=358.19, date=None, company_name="MICROSOFT CORP", type="Equity", action="buy")
    # manager.add_transaction(symbol="UBER", quantity=175, cost_basis=69.75, date=None, company_name="UBER TECHNOLOGIES INC", type="Equity", action="buy")
    # manager.add_transaction(symbol="RDDT", quantity=120, cost_basis=183.43, date=None, company_name="REDDIT INC CLASS A", type="Equity", action="buy")
    # manager.add_transaction(symbol="QQQ", quantity=47.1265, cost_basis=342.51, date=None, company_name="INVESCO QQQ TRUST", type="ETF", action="buy")
    # manager.add_transaction(symbol="SPY", quantity=21.155, cost_basis=414.93, date=None, company_name="SPDR S&P 500 ETF", type="ETF", action="buy")
    # manager.add_transaction(symbol="VOO", quantity=31.8308, cost_basis=383.35, date=None, company_name="VANGUARD S&P 500 ETF", type="ETF", action="buy")
    # manager.add_transaction(symbol="VTI", quantity=53.0149, cost_basis=214.01, date=None, company_name="VANGUARD TOTAL STOCK M...", type="ETF", action="buy")
    # manager.add_transaction(symbol="VOO", quantity=10, cost_basis=395.14, date=None, company_name="VANGUARD S&P 500 ETF", type="ETF", action="buy")
    # manager.add_transaction(symbol="VTI", quantity=39, cost_basis=221.11, date=None, company_name="VANGUARD TOTAL STOCK M...", type="ETF", action="buy")
    # manager.add_transaction(symbol="ETH-USD", quantity=1.0745, cost_basis=2625.81, date=None, company_name="ETHEREUM", type="CRYPTO", action="buy")
    # manager.add_transaction(symbol="ADA-USD", quantity=1492.884029, cost_basis=0.34, date=None, company_name="CARDANO", type="CRYPTO", action="buy")
    # manager.add_transaction(symbol="BTC-USD", quantity=0.20302474, cost_basis=16941.42, date=None, company_name="BITCOIN", type="CRYPTO", action="buy")
    # manager.add_transaction(symbol="USDT-USD", quantity=298711.14, cost_basis=1.00, date=None, company_name="Tether", type="CASH", action="buy")
    app.run(debug=True)



        # self.portfolio.buy(symbol="AAPL", quantity=10.1871, price=160.80, date=None, company_name="APPLE INC", security_type="Equity")
        # self.portfolio.buy(symbol="HOOD", quantity=500, price=63.14, date=None, company_name="ROBINHOOD MKTS INC CLA...", security_type="Equity")
        # self.portfolio.buy(symbol="META", quantity=248.2124, price=172.60, date=None, company_name="META PLATFORMS INC CLAS...", security_type="Equity")
        # self.portfolio.buy(symbol="GOOG", quantity=90.1075, price=201.19, date=None, company_name="ALPHABET INC CLASS C", security_type="Equity")
        # self.portfolio.buy(symbol="ATYR", quantity=1000, price=3.04, date=None, company_name="ATYR PHARMA INC", security_type="Equity")
        # self.portfolio.buy(symbol="V", quantity=184.2974, price=180.54, date=None, company_name="VISA INC CLASS A", security_type="Equity")
        # self.portfolio.buy(symbol="V", quantity=50, price=358.38, date=None, company_name="VISA INC CLASS A", security_type="Equity")
        # self.portfolio.buy(symbol="V", quantity=85, price=366.94, date=None, company_name="VISA INC CLASS A", security_type="Equity")
        # self.portfolio.buy(symbol="MSFT", quantity=21.3218, price=358.19, date=None, company_name="MICROSOFT CORP", security_type="Equity")
        # self.portfolio.buy(symbol="UBER", quantity=175, price=69.75, date=None, company_name="UBER TECHNOLOGIES INC", security_type="Equity")
        # self.portfolio.buy(symbol="RDDT", quantity=120, price=183.43, date=None, company_name="REDDIT INC CLASS A", security_type="Equity")
        # self.portfolio.buy(symbol="QQQ", quantity=47.1265, price=342.51, date=None, company_name="INVESCO QQQ TRUST", security_type="ETF")
        # self.portfolio.buy(symbol="SPY", quantity=21.155, price=414.93, date=None, company_name="SPDR S&P 500 ETF", security_type="ETF")
        # self.portfolio.buy(symbol="VOO", quantity=31.8308, price=383.35, date=None, company_name="VANGUARD S&P 500 ETF", security_type="ETF")
        # self.portfolio.buy(symbol="VTI", quantity=53.0149, price=214.01, date=None, company_name="VANGUARD TOTAL STOCK M...", security_type="ETF")
        # self.portfolio.buy(symbol="VOO", quantity=10, price=395.14, date=None, company_name="VANGUARD S&P 500 ETF", security_type="ETF")
        # self.portfolio.buy(symbol="VTI", quantity=39, price=221.11, date=None, company_name="VANGUARD TOTAL STOCK M...", security_type="ETF")
        # self.portfolio.buy(symbol="ETH-USD", quantity=1.0745, price=2625.81, date=None, company_name="ETHEREUM", security_type="CRYPTO")
        # self.portfolio.buy(symbol="ADA-USD", quantity=1492.884029, price=0.34, date=None, company_name="CARDANO", security_type="CRYPTO")
        # self.portfolio.buy(symbol="BTC-USD", quantity=0.20302474, price=16941.42, date=None, company_name="BITCOIN", security_type="CRYPTO")
        # self.portfolio.buy(symbol="USDT-USD", quantity=298711.14, price=1.00, date=None, company_name="Tether", security_type="CASH")

