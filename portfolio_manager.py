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
        cols = ["symbol", "quantity", "cost_basis", "date", "transactionId"]
        return pd.DataFrame(columns=cols)

    def _save_transactions(self):
        self.transactions.to_json(self.tx_file, orient="records", date_format="iso")

    def add_transaction(self, symbol: str, quantity: float, cost_basis: float, date: str = None, company_name: str = None):
        date = pd.to_datetime(date) if date else pd.Timestamp.now()
        tx = {"symbol": symbol.upper(), "quantity": quantity, "company_name": company_name,
              "cost_basis": cost_basis, "date": date, "transactionId": str(uuid.uuid4())}
        self.transactions = pd.concat([self.transactions, pd.DataFrame([tx])], ignore_index=True)
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
        
    def get_realtime_quote(self, symbol):
        if 'USD' in symbol:
            return self.get_latest_crypto_price(ticker=symbol)
        
        print("Getting latest quote from FinnHub for: " + symbol)
        quote = client.quote(symbol=symbol)
        
        new_data = {
            'Close': quote.get("c"),
            'High': quote.get("h"),
            'Low': quote.get("l"),
            'Open': quote.get("o"),
            'Volume': 3000000
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

    def compute_equity_history(self, period: str = "5y") -> pd.DataFrame:
        price_data = self._load_all_price_data(period)

        equity_history = []

        for date_entry in price_data.index:
            total_equity = 0
            for symbol, quantity in self.get_current_holdings().items():
                try:
                    price = price_data[symbol][datetime.strftime(date_entry, '%Y-%m-%d')]
                    total_equity += float(price.iloc[0]) * quantity
                except KeyError as e:
                    raise Exception(e)
            equity_history.append({"time": int(pd.Timestamp(date_entry).timestamp()), "equity": round(total_equity, 2)})
            
        return equity_history
    
    #TODO: optimize this function:
    # def compute_equity_history(self, period: str = "5y") -> list[dict]:
    #     price_data = self._load_all_price_data(period)

    #     # Ensure datetime index is sorted and standardized
    #     price_data.index = pd.to_datetime(price_data.index)

    #     # Cache current holdings
    #     holdings = self.get_current_holdings()

    #     # Only keep columns for current holdings
    #     price_data = price_data[list(holdings.keys())]

    #     # Multiply each column by the quantity held
    #     for symbol, qty in holdings.items():
    #         price_data[symbol] = price_data[symbol] * qty

    #     # Sum across columns (each row is total equity on that date)
    #     price_data['equity'] = price_data.sum(axis=1)

    #     # Return as list of dicts with timestamp
    #     equity_history = [
    #         {"time": int(ts.timestamp()), "equity": round(equity, 2)}
    #         for ts, equity in zip(price_data.index, price_data['equity'])
    #     ]

    #     return equity_history


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

        for symbol, purchases in grouped_dict.items():
            live_price, live_date = self.get_realtime_quote(symbol)
            price = live_price['Close']
            
            previous_close = self._get_price_data(symbol)['Close'].copy()
            prev_close = previous_close.iloc[-2] if self.is_past_12_in_china() else previous_close.iloc[-1]

            total_quantity = sum(p["quantity"] for p in purchases)
            value = round(price * total_quantity, 2)

            day_gain = round((price - prev_close) * total_quantity, 2) if prev_close else 0
            day_gain_percent = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0

            purchases_detail = []
            for p in purchases:
                qty = p["quantity"]
                basis = p["cost_basis"]
                gain = (price - basis) * qty
                gain_percent = ((price - basis) / basis * 100) if basis else 0
                market_value = price * qty

                purchases_detail.append({
                    "transactionId": p["transactionId"],
                    "date": p["date"],
                    "purchasePrice": basis,
                    "quantity": qty,
                    "value": round(market_value, 2),
                    "totalGain": round(gain, 2),
                    "totalGainPercent": round(gain_percent, 2)
                })

            response.append({
                "id": symbol.lower(),
                "symbol": symbol,
                "name": purchases[0]['company_name'],
                "price": price,
                "quantity": round(total_quantity, 4),
                "dayGain": round(day_gain, 2),
                "dayGainPercent": abs(round(day_gain_percent, 2)),
                "value": value,
                "purchases": purchases_detail
            })

        return response


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
    