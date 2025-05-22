import os
import pandas as pd
import yfinance as yf
from datetime import datetime, date
import numpy as np
from dotenv import load_dotenv
import os
import finnhub
import time

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
        cols = ["symbol", "quantity", "cost_basis", "date"]
        return pd.DataFrame(columns=cols)

    def _save_transactions(self):
        self.transactions.to_json(self.tx_file, orient="records", date_format="iso")

    def add_transaction(self, symbol: str, quantity: float, cost_basis: float, date: str = None):
        date = pd.to_datetime(date) if date else pd.Timestamp.now()
        tx = {"symbol": symbol.upper(), "quantity": quantity,
              "cost_basis": cost_basis, "date": date}
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
            # Attempt to read multi-index header
            df = pd.read_csv(csv_path, parse_dates=True)
            df.columns = ['Date', "Close", "High", "Low", "Open", "Volume"]
            df = df.iloc[2:].reset_index(drop=True)
            df = df.set_index("Date", drop=True)
        except (ValueError, pd.errors.ParserError):
            # Fallback for single-level header
            df = pd.read_csv(csv_path, index_col='Date', parse_dates=True)
        return df

    def _get_price_data(self, symbol: str, period: str = "5y") -> pd.DataFrame:
        csv_path = os.path.join(self.data_dir, f"{symbol}.csv")
        if os.path.exists(csv_path):
            df = self._read_cached_csv(csv_path)
            last_date = datetime.strptime(df.index[-1], '%Y-%m-%d').date()
            today = datetime.today().date()
            if last_date < today:
                if 'USD' in symbol:
                    return df
                    
                print("Getting latest quote from FinnHub for: " + symbol)
                quote = client.quote(symbol=symbol)
                ts = pd.to_datetime(quote["t"]).strftime('%Y-%m-%d')
                
                # Build DataFrame
                new_data = pd.DataFrame([{
                    "Date": date.today().isoformat(),
                    "Close": quote.get("c"),
                    "High": quote.get("h"),
                    "Low": quote.get("l"),
                    "Open": quote.get("o"),
                    "Volume": quote.get("v", 1000000)
                }])
                new_data.set_index("Date", inplace=True)
                if not new_data.empty:
                    df = pd.concat([df, new_data[~new_data.index.isin(df.index)]])
                    df.to_csv(csv_path)
            return df
        # No cache: download full period
        print("Downloading and saving 5y of price data for " + symbol)
        
        attempt = 0
        backoff_factor = 1.0
        max_retries = 5
        while attempt < max_retries:
            try:
                df = yf.download(symbol, period=period, auto_adjust=True)
                # If empty or malformed, consider as failure
                if df is None or df.empty:
                    raise ValueError("Empty DataFrame returned")
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

        df.to_csv(csv_path)
        return df

    def _load_all_price_data(self, period: str = "5y") -> pd.DataFrame:
        syms = self.get_current_holdings().keys()
        frames = []
        for sym in syms:
            df = self._get_price_data(sym, period)[['Close']].copy().dropna()
            df.columns = pd.MultiIndex.from_product([[sym], df.columns])
            frames.append(df)
        if not frames:
            return pd.DataFrame()
        data = pd.concat(frames, axis=1).sort_index().dropna()
        return data

    def compute_equity_history(self, period: str = "5y") -> pd.DataFrame:
        price_data = self._load_all_price_data(period)

        equity_history = []

        for date_entry in price_data.index:
            total_equity = 0
            for symbol, quantity in self.get_current_holdings().items():
                try:
                    if symbol in ["ETH-USD", "ADA-USD"]:
                        price = price_data[symbol]["Close"][date_entry]
                    else:
                        price = price_data[symbol]["Close"][date_entry]
                    total_equity += float(price) * quantity
                except KeyError:
                    continue  # handle missing data
            equity_history.append({"time": int(pd.Timestamp(date_entry).timestamp()), "equity": round(total_equity, 2)})
            
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
                current_prices[sym] = self._get_price_data(sym)['Close'].iloc[-1]
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
        price = self._get_price_data(symbol)['Close'].iloc[-1]
        market_value = float(price) * total_qty
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


# if __name__ == '__main__':
#     manager = PortfolioManager()
#     manager.add_transaction(symbol="MSFT", quantity=10, cost_basis=100.1, date=None)
#     manager.add_transaction(symbol="TSLA", quantity=20, cost_basis=202.1, date=None)
#     manager.add_transaction(symbol="TSLA", quantity=10, cost_basis=302.1, date=None)
    
#     print(manager.get_transactions(symbol="TSLA"))
#     print(manager.portfolio_pnl())
#     print(manager.transaction_pnl(symbol="TSLA"))
#     print(manager.compute_equity_history())
    