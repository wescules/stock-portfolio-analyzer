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
load_dotenv()

finnhub_key = os.getenv("FINNHUB_API_KEY")
client = finnhub.Client(api_key=finnhub_key)



class PortfolioManager:
    def __init__(self, data_dir="data", tx_file="transactions.json"):
        self.data_dir = data_dir
        self.tx_file = os.path.join(data_dir, tx_file)
        os.makedirs(self.data_dir, exist_ok=True)
        self.transactions = self._load_transactions()

    def _load_transactions(self):
        if os.path.exists(self.tx_file):
            return pd.read_json(self.tx_file)
        cols = ["symbol", "quantity", "cost_basis", "date", "transactionId", "type"]
        return pd.DataFrame(columns=cols)

    def _save_transactions(self):
        self.transactions.to_json(self.tx_file, orient="records", date_format="iso")

    def add_transaction(self, symbol: str, quantity: float, cost_basis: float, date: str = None, company_name: str = None, type: str = None):
        date = pd.to_datetime(date) if date else pd.Timestamp.now()
        tx = {"symbol": symbol.upper(), "quantity": quantity, "company_name": company_name,
              "cost_basis": cost_basis, "date": date, "transactionId": str(uuid.uuid4()), "type": type}
        self.transactions = pd.concat([self.transactions, pd.DataFrame([tx])], ignore_index=True)
        self._save_transactions()
        
    def remove_transaction(self, transaction_id: str):
        index_to_delete = self.transactions[self.transactions['transactionId'] == transaction_id].index
        self.transactions.drop(index_to_delete, inplace=True)
        self._save_transactions()


    def get_transactions(self, symbol: str = None) -> pd.DataFrame:
        df = self.transactions.copy()
        if symbol:
            df = df[df['symbol'] == symbol.upper()]
        return df

    def get_current_holdings(self) -> dict:
        holdings = {}
        for _, tx in self.transactions.iterrows():
            sym = tx['symbol']
            holdings[sym] = holdings.get(sym, 0) + tx['quantity']
        return {s: q for s, q in holdings.items() if q != 0}

    def _read_cached_csv(self, csv_path: str) -> pd.DataFrame:
        """Read CSV with potential multi-index headers and flatten columns"""
        try:
            df = pd.read_json(csv_path)
        except (ValueError, pd.errors.ParserError):
            # Fallback for single-level header
            df = pd.read_json(csv_path)
        return df

    def _get_price_data(self, symbol: str, period: str = "5y") -> pd.DataFrame:
        csv_path = os.path.join(self.data_dir, f"{symbol}.json")
        if os.path.exists(csv_path):
            df = self._read_cached_csv(csv_path)
            # last_date = pd.to_datetime(df.index[-1]).date()
            # today = datetime.today().date()
            # if last_date < today:
            #     if 'USD' in symbol: # ignore crypto for now
            #         return df
            #     new_data, new_index = self.get_realtime_quote(symbol)
            #     df.loc[new_index] = new_data
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

        # df.to_csv(csv_path)
        df.to_json(csv_path)
        return df

    def get_latest_crypto_price(self, ticker):
        print("Getting latest quote from CoinGecko for: " + ticker)
        grouped_dict = {
            symbol: group.to_dict(orient='records')
            for symbol, group in self.transactions.groupby('symbol')
        }
        coin_name = grouped_dict.get(ticker)[0]['company_name']
        response = requests.get(f'https://api.coingecko.com/api/v3/simple/price?ids={coin_name}&vs_currencies=usd', timeout=10)
        
        # fallback: read from json file
        if response.status_code != 200:
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
        symbol_info = self.transactions[self.transactions['symbol'] == symbol].index
        transaction = self.transactions.iloc[symbol_info]
        
        return transaction['type'].iloc[0].lower() == 'crypto' or transaction['type'].iloc[0].lower() == 'cash'
        
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
        syms = self.get_current_holdings().keys()
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
        holdings = self.get_current_holdings()

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


    def transaction_pnl(self, symbol: str = None) -> pd.DataFrame:
        txs = self.get_transactions(symbol)
        if txs.empty:
            return pd.DataFrame()
        pnl = []
        current_prices = {}
        for _, tx in txs.iterrows():
            sym = tx['symbol']
            if sym not in current_prices:
                current_prices[sym] = self._get_price_data(sym)[['Close']].iloc[-1]
            price = current_prices[sym]
            qty = tx['quantity']
            cost = tx['cost_basis'] * qty
            value = float(price) * qty
            pnl.append({
                'symbol': sym,
                'date': tx['date'],
                'quantity': qty,
                'cost_basis': tx['cost_basis'],
                'current_price': price,
                'pnl': value - cost,
                'return_pct': (value - cost) / cost * 100 if cost else None
            })
        return pd.DataFrame(pnl)

    def symbol_pnl(self, symbol: str) -> dict:
        txs = self.get_transactions(symbol)
        if txs.empty:
            return {}
        total_qty = txs['quantity'].sum()
        total_cost = (txs['quantity'] * txs['cost_basis']).sum()
        price = self._get_price_data(symbol)[['Close']].iloc[-1]

        market_value = float(price.iloc[0]) * total_qty
        pnl = market_value - total_cost
        return {
            'symbol': symbol,
            'quantity': total_qty,
            'cost_basis': total_cost,
            'market_value': market_value,
            'pnl': pnl,
            'return_pct': pnl / total_cost * 100 if total_cost else None
        }

    def portfolio_pnl(self) -> dict:
        summary = {'total_cost': 0, 'total_value': 0}
        for sym in self.get_current_holdings().keys():
            stats = self.symbol_pnl(sym)
            summary['total_cost'] += stats.get('cost_basis', 0)
            summary['total_value'] += stats.get('market_value', 0)
        total_pnl = summary['total_value'] - summary['total_cost']
        summary.update({
            'total_pnl': total_pnl,
            'return_pct': total_pnl / summary['total_cost'] * 100 if summary['total_cost'] else None
        })
        return summary

    def is_past_12_in_china(self):
        now = pd.Timestamp.now()
        ny_time = datetime.now(ZoneInfo("America/New_York"))
        # I'm not in the US so I need this
        return now.date() > ny_time.date()
        
    def get_portfolio_info(self):
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
            live_price, live_date = self.get_realtime_quote(symbol)
            price = live_price['Close']

            if self.is_crypto_symbol(symbol):
                previous_close = self._get_price_data(symbol)['Close'].copy()
                prev_close = previous_close.iloc[-2] if self.is_past_12_in_china() else previous_close.iloc[-1]
            else:
                prev_close = live_price['previous_close_price']

            total_quantity = sum(p["quantity"] for p in purchases)
            value = round(price * total_quantity, 2)

            day_gain = round((price - prev_close) * total_quantity, 2) if prev_close else 0
            day_gain_percent = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0

            total_value += value
            total_day_gain += day_gain

            purchases_detail = []
            for p in purchases:
                qty = p["quantity"]
                basis = p["cost_basis"]
                gain = (price - basis) * qty
                gain_percent = ((price - basis) / basis * 100) if basis else 0
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
        total_gain_percent = (total_gain / total_cost_basis * 100) if total_cost_basis else 0

        yesterday_value = total_value - total_day_gain
        day_percent = (total_day_gain / yesterday_value * 100) if yesterday_value else 0

        timestamp = pd.Timestamp.now(tz='Asia/Shanghai').strftime("%b %d, %I:%M:%S %p UTC+8")

        portfolio_highlights = [
            {"name": k, "percent": round(v / total_value * 100, 1), "value": round(v, 2)}
            for k, v in type_breakdown.items()
        ]

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
    
    # print(manager.get_portfolio_info())



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
    


    