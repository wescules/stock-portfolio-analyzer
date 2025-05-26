import os
import pandas as pd
import requests
import yfinance as yf
from datetime import datetime, date
import numpy as np
from dotenv import load_dotenv
import os
import finnhub
import time
import uuid
from zoneinfo import ZoneInfo
import websocket
import json

from portfolio import Portfolio
load_dotenv()

finnhub_key = os.getenv("FINNHUB_API_KEY")
client = finnhub.Client(api_key=finnhub_key)
class PortfolioManager:
    def __init__(self, data_dir="data", tx_file="transactions.json", portfolio_cache_file="portfolio_cache.json"):
        self.data_dir = data_dir
        self.tx_file = os.path.join(data_dir, tx_file)
        self.portfolio_cache_file = os.path.join(data_dir, portfolio_cache_file)
        os.makedirs(self.data_dir, exist_ok=True)
        self.portfolio = Portfolio(positions=self.get_positions())

    
    def save_positions(self):
        with open(self.tx_file, 'w') as f:
            json.dump(self.portfolio.get_positions(), f)
            
    def write_positions(self, positions):
        with open(self.tx_file, 'w') as f:
            json.dump(positions, f)
            
    def get_positions(self):
        with open(self.tx_file, 'r') as f:
            return json.load(f)
           
    def add_transaction(self, symbol: str, quantity: float, cost_basis: float, date: str = None,
                        company_name: str = None, type: str = None, action: str = None):
        if action == 'buy':
            self.portfolio.buy(symbol=symbol, quantity=quantity, price=cost_basis, date=date, company_name=company_name, security_type=type)
        elif action == 'sell':
            self.portfolio.sell(symbol=symbol, quantity=quantity, price=cost_basis, date=date)
        elif action == 'short':
            self.portfolio.short_sell(symbol=symbol, quantity=quantity, price=cost_basis, date=date, company_name=company_name, security_type=type)
        elif action == 'cover':
            self.portfolio.buy_to_cover(symbol=symbol, quantity=quantity, price=cost_basis, date=date)
        self.save_positions()
        
    def remove_transaction(self, transaction_id: str):
        positions = self.get_positions()
        new_positions = {}
        for symbol in positions.keys():
            transactions = []
            if len(positions[symbol]) == 1 and positions[symbol][0]['transactionId'] == transaction_id:
                continue
            elif len(positions[symbol]) == 1 and positions[symbol][0]['transactionId'] != transaction_id:
                transactions.append(positions[symbol][0])
                new_positions[symbol] = transactions
            else:
                for txn in positions[symbol]:
                    if txn['transactionId'] == transaction_id:
                        continue
                    transactions.append(txn)
                new_positions[symbol] = transactions
        self.write_positions(new_positions)

    def _read_cached_json(self, json_path: str) -> pd.DataFrame:
        """Read JSON with potential multi-index headers and flatten columns"""
        try:
            df = pd.read_json(json_path)
        except (ValueError, pd.errors.ParserError):
            # Fallback for single-level header
            df = pd.read_json(json_path)
        return df

    def _get_price_data(self, symbol: str, period: str = "5y") -> pd.DataFrame:
        json_path = os.path.join(self.data_dir, f"{symbol}.json")
        if os.path.exists(json_path):
            df = self._read_cached_json(json_path)
            return df
        # No cache: download full period
        print("Downloading and saving 5y of price data for " + symbol)
        
        if self.is_crypto_symbol(symbol) and '-USD' not in symbol:
            symbol = symbol + '-USD'
        attempt = 0
        backoff_factor = 1.0
        max_retries = 5
        while attempt < max_retries:
            try:
                df = yf.Ticker(symbol).history(period=period, auto_adjust=False)
                # If empty or malformed, consider as failure
                if df is None or df.empty:
                    raise ValueError("Empty DataFrame returned while trying to download")
                break
            except Exception as e:
                attempt += 1
                if attempt == max_retries:
                    print(f"Failed to download after {max_retries} attempts: {e}")
                    raise
                wait = backoff_factor * (2 ** (attempt - 1))
                print(f"Download failed (attempt {attempt}/{max_retries}): {e}")
                print(f"Retrying in {wait:.1f} seconds...")
                time.sleep(wait)

        df.to_json(json_path)
        return df

    def get_latest_crypto_price(self, ticker):
        print("Getting latest quote from CoinGecko for: " + ticker)
        coin_name = self.portfolio.get_positions()[ticker][0]['company_name']
        try:
            response = requests.get(f'https://api.coingecko.com/api/v3/simple/price?ids={coin_name}&vs_currencies=usd', timeout=10)
        except Exception as e:
            print("CoinGecko has failed. Using fallback and reading from file")
            last_known_price = self._get_price_data(ticker)['Close'].iloc[-1]
            return {'Close': last_known_price}, pd.to_datetime(date.today().isoformat())

        data = response.json()
        crypto_id, data = next(iter(data.items()))
        price = data["usd"]
        new_data = {
            'Close': price
        }
        return new_data, pd.to_datetime(date.today().isoformat())
    
    def is_crypto_symbol(self, symbol):
        symbol_transaction = self.portfolio.get_positions()[symbol][0]
        return symbol_transaction['security_type'].lower() == 'crypto' or symbol_transaction['security_type'].lower() == 'cash'
        
    def get_realtime_quote(self, symbol):
        if self.is_crypto_symbol(symbol):
            return self.get_latest_crypto_price(ticker=symbol)
        
        print("Getting latest quote from FinnHub for: " + symbol)
        quote = client.quote(symbol=symbol)
                
        new_data = {
            'Close': quote.get("c"),
            'High': quote.get("h"),
            'Low': quote.get("l"),
            'Open': quote.get("o"),
            'percent_change': quote.get('dp'),
            'previous_close_price': quote.get("pc"),
        }

        index = pd.to_datetime(date.today().isoformat())
        return new_data, index

    def _load_all_price_data(self, period: str = "5y") -> pd.DataFrame:
        syms = self.portfolio.get_positions().keys()
        frames = []
        for sym in syms:
            df = self._get_price_data(sym, period)[['Close']].copy()
            df = df.rename(columns={"Close": sym})
            frames.append(df)
        if not frames:
            return pd.DataFrame()
        data = pd.concat(frames, axis=1).sort_index().fillna(0)
        return data

    def compute_equity_history(self, period: str = "5y") -> list[dict]:
        price_data = self._load_all_price_data(period)

        # Cache current holdings
        holdings = self.portfolio.get_positions_and_quantities()

        # Only keep columns for current holdings
        price_data = price_data[list(holdings.keys())]
        
        # Get rid of weekends. We dont have data 
        price_data = price_data[price_data.index.day_of_week < 5]

        # Multiply each column by the quantity held
        for symbol, qty in holdings.items():
            price_data[symbol] = price_data[symbol] * qty

        # Sum across columns (each row is total equity on that date)
        columns = price_data.columns
        price_data['date'] = price_data.index.date
        daily_aggregated_values = price_data.groupby('date')[columns].sum()
        price_data = price_data.drop(columns=['date'])
        price_data['equity'] = daily_aggregated_values.sum(axis=1) if len(daily_aggregated_values.columns) > 1 else price_data[symbol]
                
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

        return equity_history

    def is_past_12_in_china(self):
        now = pd.Timestamp.now()
        ny_time = datetime.now(ZoneInfo("America/New_York"))
        # I'm not in the US so I need this
        return now.date() > ny_time.date()
    
    def get_portfolio_info_from_cache(self):
        with open(self.portfolio_cache_file) as f:
            return json.load(f)
        return {}
        
    def get_portfolio_info(self):
        total_value = 0
        realtime_prices = {}
        previous_close_price = {}
        type_breakdown = {}
        positions = self.get_positions()
        self.portfolio.set_positions(positions)
        for symbol in positions:
            purchases = positions[symbol]
            live_price, live_date = self.get_realtime_quote(symbol)
            price = live_price['Close']
            realtime_prices[symbol] = price

            if self.is_crypto_symbol(symbol):
                previous_close = self._get_price_data(symbol)['Close'].copy()
                prev_close = previous_close.iloc[-2] if self.is_past_12_in_china() else previous_close.iloc[-1]
            else:
                prev_close = live_price['previous_close_price']

            previous_close_price[symbol] = float(prev_close)
            
            total_quantity = sum(p["quantity"] for p in purchases)
            value = round(price * total_quantity, 2)
            total_value += value
            
            category = purchases[0]['security_type'].lower()
            type_breakdown[category] = type_breakdown.get(category, 0) + value
            
        self.portfolio.set_realtime_prices(current_prices=realtime_prices, previous_closing_prices=previous_close_price)
    
        portfolio_highlights = [
            {"name": k, "percent": round(v / total_value * 100, 1), "value": round(v, 2)}
            for k, v in type_breakdown.items()
        ]
        portfolio_info = self.portfolio.get_detailed_portfolio_report()
        portfolio_info['portfolioHighlights'] = portfolio_highlights

        with open(self.portfolio_cache_file, 'w') as f:
            json.dump(portfolio_info, f)

        return portfolio_info










# TESTING CODE
if __name__ == '__main__':
    manager = PortfolioManager()
    # manager.add_transaction(symbol="MSFT", quantity=10, cost_basis=100.1, date=None)
    # manager.add_transaction(symbol="TSLA", quantity=20, cost_basis=202.1, date=None)
    # manager.add_transaction(symbol="TSLA", quantity=10, cost_basis=302.1, date=None)
    
    # print(manager.get_transactions(symbol="TSLA"))
    # print(manager.portfolio_pnl())
    # print(manager.transaction_pnl(symbol="TSLA"))
    # print(manager.compute_equity_history())
    
    

    print(manager.get_portfolio_info())



    # def on_message(ws, message):
    #     data = json.loads(message)
    #     if data["type"] == "trade":
    #         for trade in data["data"]:
    #             print(f"Symbol: {trade['s']} | Price: {trade['p']} | Volume: {trade['v']}")

    # def on_open(ws):
    #     for symbol in manager.get_current_holdings().keys():
    #         ws.send(json.dumps({"type": "subscribe", "symbol": symbol}))
    #     print("✅ Subscribed to:", [manager.get_current_holdings().keys()])

    # def on_close(ws, close_status_code, close_msg):
    #     print("🚪 WebSocket closed")

    # def on_error(ws, error):
    #     print("❌ Error:", error)
        
    # socket = f"wss://ws.finnhub.io?token={finnhub_key}"
    # websocket.enableTrace(True)
    # ws = websocket.WebSocketApp(socket,
    #                             on_message=on_message,
    #                             on_open=on_open,
    #                             on_close=on_close,
    #                             on_error=on_error)

    # ws.run_forever()
    


    