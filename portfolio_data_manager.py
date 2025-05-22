import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np

class PortfolioDataManager:
    def __init__(self, symbols=None, data_dir="data", tx_dir="transactions"):
        self.symbols = set(symbols or [])
        self.data_dir = data_dir
        self.tx_dir = tx_dir
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(tx_dir, exist_ok=True)

    def add_symbol(self, symbol: str):
        symbol = symbol.upper()
        self.symbols.add(symbol)
        if not os.path.exists(self.get_data_path(symbol)):
            self.get_initial_data(symbol)

    def remove_symbol(self, symbol: str):
        symbol = symbol.upper()
        self.symbols.discard(symbol)
        os.remove(self.get_data_path(symbol))
        os.remove(self.get_transaction_path(symbol))

    def get_data_path(self, symbol: str):
        return os.path.join(self.data_dir, f"{symbol}.csv")

    def get_transaction_path(self, symbol: str):
        return os.path.join(self.tx_dir, f"{symbol}_transactions.csv")

    def get_initial_data(self, symbol: str):
        df = yf.download(symbol, period="1y", interval="1d")
        df.to_csv(self.get_data_path(symbol))
        return df

    def load_cached_data(self, symbol: str):
        path = self.get_data_path(symbol)
        if os.path.exists(path):
            df = pd.read_csv(path, index_col="Date", parse_dates=True)
        else:
            df = self.get_initial_data(symbol)
        return df
    
    def fetch_equity_history(self):
        frames = []
        for symbol in self.symbols:
            path = self.get_data_path(symbol)
            if os.path.exists(path):
                df = pd.read_csv(path, index_col="Date", parse_dates=True)
            else:
                df = self.get_initial_data(symbol)
                
            df = df[["Close"]].copy()
            df.columns = pd.MultiIndex.from_product([[symbol], df.columns])
            frames.append(df)

        if not frames:
            return pd.DataFrame()

        combined_df = pd.concat(frames, axis=1).sort_index()
        
        equity_history = []

        for date in data.index:
            total_equity = 0
            for symbol, quantity in portfolio.items():
                try:
                    # If only 1 symbol is fetched, data won't be nested
                    if len(portfolio) == 1 and "Close" in data.columns:
                        price = data["Close"][date]
                    else:
                        price = data[symbol]["Close"][date]
                    total_equity += price * quantity
                except KeyError:
                    continue  # skip missing data

            equity_history.append({
                "time": int(pd.Timestamp(date).timestamp()),
                "equity": round(total_equity, 2)
            })

        return equity_history



    def update_data(self, symbol: str, df):
        last_date = df.index[-1].date()
        today = datetime.today().date()
        if last_date < today:
            new_data = yf.download(
                symbol,
                start=(last_date + timedelta(days=1)).strftime("%Y-%m-%d"),
                end=(today + timedelta(days=1)).strftime("%Y-%m-%d"),
                interval="1d"
            )
            if not new_data.empty:
                df = pd.concat([df, new_data[~new_data.index.isin(df.index)]])
                df.to_csv(self.get_data_path(symbol))
        return df

    def update_all_symbols(self):
        data_dict = {}
        for symbol in self.symbols:
            df = self.load_cached_data(symbol)
            updated_df = self.update_data(symbol, df)
            data_dict[symbol] = updated_df
        return data_dict

    # ===== Transactions =====
    def add_transaction(self, symbol: str, quantity, cost_basis, date=None):
        symbol = symbol.upper()
        self.symbols.add(symbol)
        if not os.path.exists(self.get_data_path(symbol)):
            self.get_initial_data(symbol)

        if symbol not in self.symbols:
            raise Exception(symbol + " is not in portfolio")
        date = pd.to_datetime(date or datetime.today()).strftime('%Y-%m-%d')
        tx_path = self.get_transaction_path(symbol)
        new_tx = pd.DataFrame([{
            "Date": date,
            "Quantity": quantity,
            "CostBasis": cost_basis
        }])
        if os.path.exists(tx_path):
            df = pd.read_csv(tx_path)
            df = pd.concat([df, new_tx], ignore_index=True)
        else:
            df = new_tx
        df.to_csv(tx_path, index=False)

    def get_transactions(self, symbol: str):
        path = self.get_transaction_path(symbol.upper())
        if os.path.exists(path):
            return pd.read_csv(path, parse_dates=["Date"])
        return pd.DataFrame(columns=["Date", "Quantity", "CostBasis"])

    # ===== Position Summary =====
    def get_position_summary(self, symbol: str):
        df = self.get_transactions(symbol)
        if df.empty:
            return None

        net_quantity = df["Quantity"].sum()
        if net_quantity == 0:
            return {"Shares": 0, "AverageCost": 0, "UnrealizedP&L": 0}

        total_cost = (df["Quantity"] * df["CostBasis"]).sum()
        avg_cost = total_cost / df["Quantity"].sum()

        price_data = self.load_cached_data(symbol)
        current_price = price_data["Close"].iloc[-1]

        unrealized_pl = (current_price - avg_cost) * net_quantity

        return {
            "Shares": net_quantity,
            "AverageCost": round(avg_cost, 2),
            "CurrentPrice": round(current_price, 2),
            "UnrealizedP&L": round(unrealized_pl, 2)
        }

    # ===== Analytics =====
    def get_analytics(self, symbol: str):
        price_data = self.load_cached_data(symbol)
        price_data["Return"] = price_data["Close"].pct_change()
        price_data = price_data.dropna()

        total_return = (price_data["Close"].iloc[-1] / price_data["Close"].iloc[0]) - 1
        annual_volatility = np.std(price_data["Return"]) * np.sqrt(252)
        sharpe_ratio = total_return / annual_volatility if annual_volatility != 0 else None
        max_drawdown = ((price_data["Close"] / price_data["Close"].cummax()) - 1).min()

        return {
            "TotalReturnPct": round(total_return * 100, 2),
            "AnnualVolatility": round(annual_volatility, 4),
            "SharpeRatio": round(sharpe_ratio, 2) if sharpe_ratio is not None else "N/A",
            "MaxDrawdownPct": round(max_drawdown * 100, 2)
        }

    # ===== Portfolio Summary =====
    def get_portfolio_summary(self):
        total_value = 0
        total_cost = 0
        total_unrealized = 0
        returns = []

        for symbol in self.symbols:
            txs = self.get_transactions(symbol)
            if txs.empty:
                continue

            quantity = txs["Quantity"].sum()
            if quantity == 0:
                continue

            avg_cost = (txs["Quantity"] * txs["CostBasis"]).sum() / quantity
            price_data = self.load_cached_data(symbol)
            current_price = price_data["Close"].iloc[-1]

            position_value = current_price * quantity
            position_cost = avg_cost * quantity
            unrealized_pl = position_value - position_cost

            total_value += position_value
            total_cost += position_cost
            total_unrealized += unrealized_pl

            # For return metrics
            price_data["Return"] = price_data["Close"].pct_change()
            returns.append(price_data["Return"].dropna())

        total_return_pct = ((total_value / total_cost) - 1) * 100 if total_cost else 0
        realized_pl = 0  # Can be implemented later with sell tracking

        # Combine returns
        if returns:
            all_returns = pd.concat(returns, axis=1).mean(axis=1)
            annual_vol = np.std(all_returns) * np.sqrt(252)
            sharpe = (total_return_pct / 100) / annual_vol if annual_vol != 0 else None
            drawdown = ((all_returns + 1).cumprod() / (all_returns + 1).cumprod().cummax()) - 1
            max_drawdown = drawdown.min()
        else:
            annual_vol = sharpe = max_drawdown = 0

        return {
            "TotalValue": round(total_value, 2),
            "TotalCost": round(total_cost, 2),
            "TotalUnrealizedPL": round(total_unrealized, 2),
            "TotalReturnPct": round(total_return_pct, 2),
            "AnnualVolatility": round(annual_vol, 4),
            "SharpeRatio": round(sharpe, 2) if sharpe else "N/A",
            "MaxDrawdownPct": round(max_drawdown * 100, 2) if max_drawdown else "N/A"
        }
