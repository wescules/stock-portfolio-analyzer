import pandas as pd
from datetime import datetime
import uuid # For unique transaction IDs

class Portfolio:
    """
    A portfolio management library to track stock positions,
    realized and unrealized profit/loss, and gain percentages,
    with tracking of P/L per transaction (FIFO method).
    """

    def __init__(self, positions: dict = {}, current_prices: dict = {}, previous_closing_prices: dict = {}):
        """
        Initializes an empty portfolio.
        self.positions: Stores active holdings {symbol: [lot1, lot2, ...]}
                       Each lot: {
                           'transactionId': unique_id,
                           'quantity': remaining_quantity,
                           'original_quantity': original_quantity,
                           'cost_basis': price_per_share,
                           'total_lot_cost_basis': quantity * price_per_share (at acquisition),
                           'date': transaction_date,
                           'position_type': 'long' or 'short', # Internal type for position direction
                           'action': 'Buy' or 'Sell Short', # The action that created this lot
                           'company_name': company_name,
                           'security_type': 'Common Stock' (default)
                       }
        self.realized_pnl: Stores total realized profit/loss.
        self.current_prices: Stores latest known prices for unrealized P/L calculation.
                             {symbol: price}
        self.previous_closing_prices: Stores the previous day's closing prices for day gain calculation.
                                     {symbol: price}
        self.transaction_history: A list of all recorded transactions.
        """
        self.positions = positions # {symbol: [list of lots]}
        self.realized_pnl = 0.0
        self.current_prices = current_prices
        self.previous_closing_prices = previous_closing_prices
        self.transaction_history = []
    
    def set_realtime_prices(self, current_prices, previous_closing_prices):
        self.current_prices = current_prices
        self.previous_closing_prices = previous_closing_prices
        
    def get_positions(self):
        return self.positions
    
    def set_positions(self, positions):
        self.positions = positions
    
    def get_positions_and_quantities(self):
        positions = self.get_positions()
        positions_and_quantities = {}
        for sym in positions.keys():
            quantity = 0
            for txn in positions[sym]:
                quantity += txn['quantity']
            positions_and_quantities[sym] = float(quantity)
        return positions_and_quantities
    
    def _record_transaction(self, symbol, action, quantity, price, date, company_name=None, transaction_id=None):
        """
        Internal helper to record any transaction for historical tracking.
        """
        self.transaction_history.append({
            'transaction_id': transaction_id if transaction_id else str(uuid.uuid4()),
            'date': date,
            'symbol': symbol,
            'action': action,
            'quantity': quantity,
            'price': price,
            'company_name': company_name if company_name else self._get_company_name_for_symbol(symbol)
        })

    def _get_company_name_for_symbol(self, symbol):
        """Helper to get company name from existing lots if available."""
        if symbol in self.positions and self.positions[symbol]:
            # Try to get company_name from the first lot
            return self.positions[symbol][0].get('company_name', 'N/A')
        return 'N/A'

    def buy(self, symbol, quantity, price, date, company_name='N/A', security_type='Common Stock'):
        """
        Records a 'Buy' transaction. Adds a new 'long' lot to the position.
        """
        if quantity <= 0 or price <= 0:
            print(f"Error: Quantity and price must be positive for Buy. Symbol: {symbol}")
            return

        transaction_id = str(uuid.uuid4())
        self._record_transaction(symbol, 'Buy', quantity, price, date, company_name, transaction_id)

        if symbol not in self.positions:
            self.positions[symbol] = []

        self.positions[symbol].append({
            'transactionId': transaction_id,
            'quantity': quantity,
            'original_quantity': quantity,
            'cost_basis': price,
            'total_lot_cost_basis': quantity * price, # Total cost for this lot
            'date': date,
            'position_type': 'long',
            'action': 'Buy', # The action that created this lot
            'company_name': company_name,
            'security_type': security_type
        })
        # Sort lots by date for FIFO
        # self.positions[symbol].sort(key=lambda x: datetime.strptime(x['date'], "%Y-%m-%d"))
        print(f"Bought {quantity} shares of {symbol} at ${price:.2f} on {date}.")

    def sell(self, symbol, quantity, price, date):
        """
        Records a 'Sell' transaction. Sells shares from existing 'long' lots using FIFO.
        Calculates realized P/L for each portion sold.
        """
        if symbol not in self.positions or not self.positions[symbol]:
            print(f"Error: Cannot sell {symbol}. No existing position.")
            return

        long_lots = [lot for lot in self.positions[symbol] if lot['position_type'] == 'long']
        if not long_lots:
            print(f"Error: Cannot sell {symbol}. You do not hold a long position.")
            return

        total_held_quantity = sum(lot['quantity'] for lot in long_lots)
        if quantity <= 0:
            print(f"Error: Quantity must be positive for Sell. Symbol: {symbol}")
            return
        if quantity > total_held_quantity:
            print(f"Warning: Selling more shares ({quantity}) than held ({total_held_quantity}) for {symbol}. Selling available shares.")
            quantity = total_held_quantity

        remaining_to_sell = quantity
        realized_pnl_for_transaction = 0.0
        lots_to_remove = []

        # Process lots using FIFO
        for lot in long_lots:
            if remaining_to_sell <= 0:
                break

            shares_from_lot = min(remaining_to_sell, lot['quantity'])
            
            # Calculate P/L for this portion
            pnl_from_lot = (price - lot['cost_basis']) * shares_from_lot
            realized_pnl_for_transaction += pnl_from_lot
            self.realized_pnl += pnl_from_lot

            lot['quantity'] -= shares_from_lot
            remaining_to_sell -= shares_from_lot

            if lot['quantity'] <= 1e-9: # If lot is fully depleted
                lots_to_remove.append(lot)

        # Remove depleted lots and update the position list
        self.positions[symbol] = [lot for lot in self.positions[symbol] if lot not in lots_to_remove]
        # Re-sort remaining lots (should already be sorted, but good practice)
        # self.positions[symbol].sort(key=lambda x: datetime.strptime(x['date'], "%Y-%m-%d"))

        # Clean up symbol if no lots remain
        if not self.positions[symbol]:
            del self.positions[symbol]
            if symbol in self.current_prices:
                del self.current_prices[symbol]
            if symbol in self.previous_closing_prices:
                del self.previous_closing_prices[symbol]

        self._record_transaction(symbol, 'Sell', quantity, price, date)
        print(f"Sold {quantity} shares of {symbol} at ${price:.2f} on {date}. Realized P/L for this sale: ${realized_pnl_for_transaction:.2f}")

    def short_sell(self, symbol, quantity, price, date, company_name='N/A', security_type='Common Stock'):
        """
        Records a 'Sell Short' transaction. Adds a new 'short' lot to the position.
        """
        if quantity <= 0 or price <= 0:
            print(f"Error: Quantity and price must be positive for Sell Short. Symbol: {symbol}")
            return

        transaction_id = str(uuid.uuid4())
        self._record_transaction(symbol, 'Sell Short', quantity, price, date, company_name, transaction_id)

        if symbol not in self.positions:
            self.positions[symbol] = []

        self.positions[symbol].append({
            'transactionId': transaction_id,
            'quantity': quantity, # Stored as positive quantity for short lot, but conceptually negative position
            'original_quantity': quantity,
            'cost_basis': price, # This is the proceeds from shorting
            'total_lot_cost_basis': quantity * price, # Total proceeds for this short lot
            'date': date,
            'position_type': 'short',
            'action': 'Sell Short', # The action that created this lot
            'company_name': company_name,
            'security_type': security_type
        })
        # Sort short lots by date for FIFO covering
        # self.positions[symbol].sort(key=lambda x: datetime.strptime(x['date'], "%Y-%m-%d"))
        print(f"Shorted {quantity} shares of {symbol} at ${price:.2f} on {date}.")


    def buy_to_cover(self, symbol, quantity, price, date):
        """
        Records a 'Buy to Cover' transaction. Covers shares from existing 'short' lots using FIFO.
        Calculates realized P/L for each portion covered.
        """
        if symbol not in self.positions or not self.positions[symbol]:
            print(f"Error: Cannot buy to cover {symbol}. No existing short position.")
            return

        short_lots = [lot for lot in self.positions[symbol] if lot['position_type'] == 'short']
        if not short_lots:
            print(f"Error: Cannot buy to cover {symbol}. You do not hold a short position.")
            return

        total_shorted_quantity = sum(lot['quantity'] for lot in short_lots)
        if quantity <= 0:
            print(f"Error: Quantity must be positive for Buy to Cover. Symbol: {symbol}")
            return
        if quantity > total_shorted_quantity:
            print(f"Warning: Buying to cover more shares ({quantity}) than shorted ({total_shorted_quantity}) for {symbol}. Covering available shares.")
            quantity = total_shorted_quantity

        remaining_to_cover = quantity
        realized_pnl_for_transaction = 0.0
        lots_to_remove = []

        # Process short lots using FIFO
        for lot in short_lots:
            if remaining_to_cover <= 0:
                break

            shares_from_lot = min(remaining_to_cover, lot['quantity'])
            
            # Calculate P/L for this portion (proceeds from short - cost to cover)
            pnl_from_lot = (lot['cost_basis'] - price) * shares_from_lot
            realized_pnl_for_transaction += pnl_from_lot
            self.realized_pnl += pnl_from_lot

            lot['quantity'] -= shares_from_lot
            remaining_to_cover -= shares_from_lot

            if lot['quantity'] <= 1e-9: # If lot is fully depleted
                lots_to_remove.append(lot)

        # Remove depleted lots and update the position list
        self.positions[symbol] = [lot for lot in self.positions[symbol] if lot not in lots_to_remove]
        # Re-sort remaining lots (should already be sorted, but good practice)
        # self.positions[symbol].sort(key=lambda x: datetime.strptime(x['date'], "%Y-%m-%d"))

        # Clean up symbol if no lots remain
        if not self.positions[symbol]:
            del self.positions[symbol]
            if symbol in self.current_prices:
                del self.current_prices[symbol]
            if symbol in self.previous_closing_prices:
                del self.previous_closing_prices[symbol]

        self._record_transaction(symbol, 'Buy to Cover', quantity, price, date)
        print(f"Bought to cover {quantity} shares of {symbol} at ${price:.2f} on {date}. Realized P/L for this cover: ${realized_pnl_for_transaction:.2f}")


    def update_current_price(self, symbol, price):
        """
        Updates the current market price for a given symbol.
        This is crucial for calculating unrealized P/L.
        """
        if price <= 0:
            print(f"Error: Current price must be positive for {symbol}.")
            return
        self.current_prices[symbol] = price
        print(f"Updated current price for {symbol} to ${price:.2f}.")

    def update_previous_closing_price(self, symbol, price):
        """
        Updates the previous day's closing price for a given symbol.
        This is crucial for calculating day gain.
        """
        if price <= 0:
            print(f"Error: Previous closing price must be positive for {symbol}.")
            return
        self.previous_closing_prices[symbol] = price
        print(f"Updated previous closing price for {symbol} to ${price:.2f}.")

    def get_position_details(self, symbol):
        """
        Returns detailed information for a specific stock position,
        including aggregate quantity, average cost/proceeds, total unrealized P/L,
        and total day gain if previous closing price is available.
        """
        if symbol not in self.positions:
            return None

        lots = self.positions[symbol]
        total_quantity = sum(lot['quantity'] if lot['position_type'] == 'long' else -lot['quantity'] for lot in lots)
        total_cost_basis = sum(lot['quantity'] * lot['cost_basis'] for lot in lots if lot['position_type'] == 'long')
        total_proceeds_basis = sum(lot['quantity'] * lot['cost_basis'] for lot in lots if lot['position_type'] == 'short')

        avg_price_per_share = 0.0
        if total_quantity > 0: # Long position
            avg_price_per_share = total_cost_basis / total_quantity if total_quantity != 0 else 0.0
        elif total_quantity < 0: # Short position
            avg_price_per_share = total_proceeds_basis / abs(total_quantity) if total_quantity != 0 else 0.0

        unrealized_pnl = 0.0
        unrealized_gain_percent = 0.0
        day_gain = 0.0
        day_gain_percent = 0.0

        current_price = self.current_prices.get(symbol)
        previous_closing_price = self.previous_closing_prices.get(symbol)

        if current_price is not None:
            for lot in lots:
                if lot['position_type'] == 'long':
                    unrealized_pnl += (current_price - lot['cost_basis']) * lot['quantity']
                else: # short
                    unrealized_pnl += (lot['cost_basis'] - current_price) * lot['quantity']

            # Calculate overall unrealized gain percentage for the symbol
            if total_quantity > 0: # Long position
                if total_cost_basis != 0:
                    unrealized_gain_percent = (unrealized_pnl / total_cost_basis) * 100
            elif total_quantity < 0: # Short position
                if total_proceeds_basis != 0:
                    unrealized_gain_percent = (unrealized_pnl / total_proceeds_basis) * 100

            # Calculate Day Gain for the aggregate position
            if previous_closing_price is not None and total_quantity != 0:
                if total_quantity > 0: # Long position
                    day_gain = (current_price - previous_closing_price) * total_quantity
                    if previous_closing_price != 0:
                        day_gain_percent = (day_gain / (previous_closing_price * total_quantity)) * 100
                else: # Short position
                    day_gain = (previous_closing_price - current_price) * abs(total_quantity)
                    if previous_closing_price != 0:
                        day_gain_percent = (day_gain / (previous_closing_price * abs(total_quantity))) * 100


        return {
            'symbol': symbol,
            'company_name': self._get_company_name_for_symbol(symbol),
            'quantity': total_quantity,
            'average_price_per_share': avg_price_per_share,
            'current_price': current_price,
            'unrealized_pnl': unrealized_pnl,
            'unrealized_gain_percent': unrealized_gain_percent,
            'day_gain': day_gain,
            'day_gain_percent': day_gain_percent
        }

    def get_portfolio_summary(self):
        """
        Returns a pandas DataFrame summarizing all active positions,
        including total quantity, average cost/proceeds, total unrealized P/L,
        and total day gain.
        """
        summary_data = []
        for symbol in self.positions:
            details = self.get_position_details(symbol)
            if details:
                summary_data.append(details)

        if not summary_data:
            return pd.DataFrame(columns=[
                'Symbol', 'Company Name', 'Quantity', 'Avg. Price/Share',
                'Current Price', 'Unrealized P/L', 'Unrealized Gain %',
                'Day Gain', 'Day Gain %'
            ])

        df = pd.DataFrame(summary_data)
        df = df.rename(columns={
            'company_name': 'Company Name',
            'average_price_per_share': 'Avg. Price/Share',
            'current_price': 'Current Price',
            'unrealized_pnl': 'Unrealized P/L',
            'unrealized_gain_percent': 'Unrealized Gain %',
            'day_gain': 'Day Gain',
            'day_gain_percent': 'Day Gain %'
        })
        df = df[['symbol', 'Company Name', 'quantity', 'Avg. Price/Share',
                 'Current Price', 'Unrealized P/L', 'Unrealized Gain %',
                 'Day Gain', 'Day Gain %']]
        df = df.sort_values(by='symbol').reset_index(drop=True)
        return df

    def get_realized_pnl(self):
        """
        Returns the total realized profit/loss for the portfolio.
        """
        return self.realized_pnl

    def get_total_unrealized_pnl(self):
        """
        Calculates and returns the total unrealized profit/loss for the portfolio.
        """
        total_unrealized = 0.0
        for symbol in self.positions:
            details = self.get_position_details(symbol)
            if details and details['unrealized_pnl'] is not None:
                total_unrealized += details['unrealized_pnl']
        return total_unrealized

    def get_total_pnl(self):
        """
        Returns the combined total of realized and unrealized profit/loss.
        """
        return self.realized_pnl + self.get_total_unrealized_pnl()

    def get_pnl_per_lot_summary(self):
        """
        Returns a pandas DataFrame summarizing the unrealized P/L and Day Gain for each individual active lot.
        """
        lot_pnl_data = []
        for symbol, lots in self.positions.items():
            current_price = self.current_prices.get(symbol)
            previous_closing_price = self.previous_closing_prices.get(symbol)

            for lot in lots:
                if lot['quantity'] > 0: # Only process active lots
                    unrealized_pnl = 0.0
                    unrealized_gain_percent = 0.0
                    day_gain = 0.0
                    day_gain_percent = 0.0

                    cost_or_proceeds = lot['quantity'] * lot['cost_basis']

                    if current_price is not None:
                        if lot['position_type'] == 'long':
                            unrealized_pnl = (current_price - lot['cost_basis']) * lot['quantity']
                            if cost_or_proceeds != 0:
                                unrealized_gain_percent = (unrealized_pnl / cost_or_proceeds) * 100
                        elif lot['position_type'] == 'short':
                            unrealized_pnl = (lot['cost_basis'] - current_price) * lot['quantity']
                            if cost_or_proceeds != 0:
                                unrealized_gain_percent = (unrealized_pnl / cost_or_proceeds) * 100

                    # Calculate Day Gain per lot
                    if current_price is not None and previous_closing_price is not None and lot['quantity'] != 0:
                        if lot['position_type'] == 'long':
                            day_gain = (current_price - previous_closing_price) * lot['quantity']
                            if previous_closing_price != 0:
                                day_gain_percent = (day_gain / (lot['quantity'] * previous_closing_price)) * 100
                        elif lot['position_type'] == 'short':
                            day_gain = (previous_closing_price - current_price) * lot['quantity']
                            if previous_closing_price != 0:
                                day_gain_percent = (day_gain / (lot['quantity'] * previous_closing_price)) * 100

                    lot_pnl_data.append({
                        'Symbol': symbol,
                        'Company Name': lot['company_name'],
                        'Lot ID': lot['transactionId'],
                        'Position Type': lot['position_type'].capitalize(),
                        'Transaction Action': lot['action'],
                        'Security Type': lot['security_type'],
                        'Quantity': lot['quantity'],
                        'Original Quantity': lot['original_quantity'],
                        'Purchase/Short Price': lot['cost_basis'],
                        'Total Lot Cost Basis': lot['total_lot_cost_basis'],
                        'Date': lot['date'],
                        'Current Price': current_price,
                        'Unrealized P/L': unrealized_pnl,
                        'Unrealized Gain %': unrealized_gain_percent,
                        'Day Gain': day_gain,
                        'Day Gain %': day_gain_percent
                    })
        if not lot_pnl_data:
            return pd.DataFrame(columns=[
                'Symbol', 'Company Name', 'Lot ID', 'Position Type', 'Transaction Action', 'Security Type',
                'Quantity', 'Original Quantity', 'Purchase/Short Price', 'Total Lot Cost Basis',
                'Date', 'Current Price', 'Unrealized P/L', 'Unrealized Gain %',
                'Day Gain', 'Day Gain %'
            ])
        return pd.DataFrame(lot_pnl_data).sort_values(by=['Symbol', 'Date']).reset_index(drop=True)


    def get_transaction_history(self):
        """
        Returns the complete transaction history as a pandas DataFrame.
        """
        if not self.transaction_history:
            return pd.DataFrame(columns=['transaction_id', 'date', 'symbol', 'action', 'quantity', 'price', 'company_name'])
        return pd.DataFrame(self.transaction_history)

    def get_detailed_portfolio_report(self):
        """
        Generates a nested dictionary report of the portfolio, including:
        - Overall portfolio summary (balance, day change, total gain)
        - Details for each symbol (price, quantity, day gain, total gain)
        - Details for each active lot within a symbol (purchase price, quantity, value, total gain)
        """
        total_portfolio_value = 0.0
        total_portfolio_day_gain = 0.0
        total_portfolio_previous_day_value = 0.0
        total_portfolio_unrealized_gain = 0.0
        total_portfolio_cost_basis_for_unrealized = 0.0

        all_symbol_details = []

        for symbol, lots in self.positions.items():
            current_price = self.current_prices.get(symbol)
            previous_closing_price = self.previous_closing_prices.get(symbol)

            symbol_total_quantity = 0.0
            symbol_current_value = 0.0
            symbol_day_gain = 0.0
            symbol_unrealized_gain = 0.0
            symbol_cost_basis = 0.0 # For calculating symbol's unrealized gain %

            symbol_lot_details = []

            for lot in lots:
                if lot['quantity'] <= 0: # Skip depleted lots
                    continue

                lot_quantity = lot['quantity']
                lot_purchase_price = lot['cost_basis']
                lot_type = lot['position_type'] # 'long' or 'short'

                # Calculate lot-specific metrics
                lot_value = 0.0
                lot_gain = 0.0
                lot_gain_percent = 0.0

                if current_price is not None:
                    lot_value = lot_quantity * current_price if lot_type == 'long' else -lot_quantity * current_price
                    if lot_type == 'long':
                        lot_gain = (current_price - lot_purchase_price) * lot_quantity
                        if lot_purchase_price != 0:
                            lot_gain_percent = (lot_gain / (lot_quantity * lot_purchase_price)) * 100
                    else: # short
                        lot_gain = (lot_purchase_price - current_price) * lot_quantity
                        if lot_purchase_price != 0:
                            lot_gain_percent = (lot_gain / (lot_quantity * lot_purchase_price)) * 100

                # Map internal transaction_action to the 'action' field in lot_detail
                lot_action_for_report = lot['action']

                symbol_lot_details.append({
                    "transactionId": lot["transactionId"],
                    "date": str(lot["date"]),
                    "purchasePrice": round(lot_purchase_price, 4),
                    "quantity": round(lot_quantity, 4),
                    "value": round(lot_value, 2),
                    "totalGain": round(lot_gain, 2),
                    "totalGainPercent": round(lot_gain_percent, 2),
                    "action": lot_action_for_report,
                    "securityType": lot["security_type"] # Added securityType
                })

                # Aggregate for symbol-level metrics
                if lot_type == 'long':
                    symbol_total_quantity += lot_quantity
                    symbol_cost_basis += lot_quantity * lot_purchase_price
                else: # short
                    symbol_total_quantity -= lot_quantity # Negative for short positions
                    symbol_cost_basis += lot_quantity * lot_purchase_price # Proceeds for short

                if current_price is not None:
                    if lot_type == 'long':
                        symbol_current_value += lot_quantity * current_price
                        symbol_unrealized_gain += (current_price - lot_purchase_price) * lot_quantity
                    else: # short
                        symbol_current_value -= lot_quantity * current_price # Value of short position is negative
                        symbol_unrealized_gain += (lot_purchase_price - current_price) * lot_quantity

                if current_price is not None and previous_closing_price is not None:
                    if lot_type == 'long':
                        symbol_day_gain += (current_price - previous_closing_price) * lot_quantity
                    else: # short
                        symbol_day_gain += (previous_closing_price - current_price) * lot_quantity

            # Calculate symbol-level day gain percentage
            symbol_day_gain_percent = 0.0
            if previous_closing_price is not None and symbol_total_quantity != 0:
                if symbol_total_quantity > 0: # Long position
                    if previous_closing_price != 0:
                        symbol_day_gain_percent = (symbol_day_gain / (previous_closing_price * symbol_total_quantity)) * 100
                else: # Short position
                    if previous_closing_price != 0:
                        symbol_day_gain_percent = (symbol_day_gain / (previous_closing_price * abs(symbol_total_quantity))) * 100

            # Calculate symbol-level total gain percentage (unrealized)
            symbol_total_gain_percent = 0.0
            if symbol_cost_basis != 0:
                symbol_total_gain_percent = (symbol_unrealized_gain / symbol_cost_basis) * 100

            symbol_detail = {
                "id": symbol.lower(),
                "symbol": symbol,
                "name": self._get_company_name_for_symbol(symbol),
                "price": round(current_price, 2) if current_price is not None else None,
                "quantity": round(symbol_total_quantity, 4),
                "dayGain": round(symbol_day_gain, 2),
                "dayGainPercent": round(symbol_day_gain_percent, 2),
                "value": round(symbol_current_value, 2),
                "totalGain": round(symbol_unrealized_gain, 2), # This is total unrealized gain for the symbol
                "totalGainPercent": round(symbol_total_gain_percent, 2), # This is total unrealized gain percent for the symbol
                "purchases": symbol_lot_details # Renamed from 'purchases' to 'lots' to be more general
            }
            all_symbol_details.append(symbol_detail)

            # Aggregate for portfolio-level metrics
            total_portfolio_value += symbol_current_value
            total_portfolio_day_gain += symbol_day_gain
            total_portfolio_unrealized_gain += symbol_unrealized_gain
            total_portfolio_cost_basis_for_unrealized += symbol_cost_basis # Sum of initial cost/proceeds for active lots

            # For portfolio day percent, we need total value from previous close
            if previous_closing_price is not None:
                if symbol_total_quantity > 0: # Long
                    total_portfolio_previous_day_value += previous_closing_price * symbol_total_quantity
                else: # Short
                    total_portfolio_previous_day_value += previous_closing_price * abs(symbol_total_quantity)


        # Calculate portfolio-level percentages
        portfolio_day_percent = 0.0
        if total_portfolio_previous_day_value != 0:
            portfolio_day_percent = (total_portfolio_day_gain / total_portfolio_previous_day_value) * 100

        portfolio_total_gain_percent = 0.0
        if total_portfolio_cost_basis_for_unrealized != 0:
            portfolio_total_gain_percent = (total_portfolio_unrealized_gain / total_portfolio_cost_basis_for_unrealized) * 100

        portfolio_info = {
            "balance": round(total_portfolio_value, 2),
            "dayChange": round(total_portfolio_day_gain, 2),
            "dayPercent": round(portfolio_day_percent, 2),
            "totalGain": round(total_portfolio_unrealized_gain, 2), # This is total unrealized gain
            "totalGainPercent": round(portfolio_total_gain_percent, 2), # This is total unrealized gain percent
            "timestamp": datetime.now().isoformat(),
            "positions": all_symbol_details
        }
        return portfolio_info


# --- Example Usage ---
if __name__ == "__main__":
    portfolio = Portfolio()

    print("--- Initial Portfolio State ---")
    print(portfolio.get_portfolio_summary())
    print(f"Total Realized P/L: ${portfolio.get_realized_pnl():.2f}")
    print(f"Total Unrealized P/L: ${portfolio.get_total_unrealized_pnl():.2f}")
    print(f"Total Portfolio P/L: ${portfolio.get_total_pnl():.2f}")
    print("\n")

    # Perform some transactions
    portfolio.buy("GOOG", 100, 100.00, "2024-01-10", "Alphabet Inc.")
    portfolio.buy("GOOG", 50, 150.00, "2024-01-15") # Second buy for GOOG
    portfolio.buy("NVDA", 75, 200.00, "2024-02-01", "NVIDIA Corp")
    portfolio.short_sell("MSFT", 10, 49.00, "2025-05-26", "MICROSOFT CORP") # Example short sell

    print("\n--- After Initial Buys and a Short Sell ---")
    print(portfolio.get_portfolio_summary())
    print(f"Total Realized P/L: ${portfolio.get_realized_pnl():.2f}")
    print(f"Total Unrealized P/L: ${portfolio.get_total_unrealized_pnl():.2f}")
    print(f"Total Portfolio P/L: ${portfolio.get_total_pnl():.2f}")
    print("\n")

    # Update current prices to see unrealized P/L
    portfolio.update_current_price("GOOG", 130.00)
    portfolio.update_current_price("NVDA", 210.00)
    portfolio.update_current_price("MSFT", 45.00) # Price drops, good for short

    # Update previous closing prices to see day gain
    portfolio.update_previous_closing_price("GOOG", 125.00)
    portfolio.update_previous_closing_price("NVDA", 205.00)
    portfolio.update_previous_closing_price("MSFT", 47.00) # Previous close for MSFT

    print("\n--- After Updating Current and Previous Prices ---")
    print(portfolio.get_portfolio_summary())
    print(f"Total Realized P/L: ${portfolio.get_realized_pnl():.2f}")
    print(f"Total Unrealized P/L: ${portfolio.get_total_unrealized_pnl():.2f}")
    print(f"Total Portfolio P/L: ${portfolio.get_total_pnl():.2f}")
    print("\n--- P/L Per Lot ---")
    print(portfolio.get_pnl_per_lot_summary())
    print("\n")

    # Sell some GOOG shares (FIFO will sell from the 2024-01-10 lot first)
    portfolio.sell("GOOG", 70, 140.00, "2024-03-01")

    print("\n--- After Selling GOOG (70 shares) ---")
    print(portfolio.get_portfolio_summary())
    print(f"Total Realized P/L: ${portfolio.get_realized_pnl():.2f}")
    print(f"Total Unrealized P/L: ${portfolio.get_total_unrealized_pnl():.2f}")
    print(f"Total Portfolio P/L: ${portfolio.get_total_pnl():.2f}")
    print("\n--- P/L Per Lot ---")
    print(portfolio.get_pnl_per_lot_summary())
    print("\n")

    # Short sell a stock
    portfolio.short_sell("TSLA", 20, 200.00, "2024-04-01", "Tesla Inc.")
    portfolio.short_sell("TSLA", 10, 210.00, "2024-04-05") # Second short for TSLA

    print("\n--- After Short Selling TSLA ---")
    print(portfolio.get_portfolio_summary())
    print(f"Total Realized P/L: ${portfolio.get_realized_pnl():.2f}")
    print(f"Total Unrealized P/L: ${portfolio.get_total_unrealized_pnl():.2f}")
    print(f"Total Portfolio P/L: ${portfolio.get_total_pnl():.2f}")
    print("\n--- P/L Per Lot ---")
    print(portfolio.get_pnl_per_lot_summary())
    print("\n")

    # Update current price for TSLA
    portfolio.update_current_price("TSLA", 190.00) # Price drops, good for short
    portfolio.update_previous_closing_price("TSLA", 195.00) # Previous close for TSLA

    print("\n--- After Updating TSLA Current and Previous Prices ---")
    print(portfolio.get_portfolio_summary())
    print(f"Total Realized P/L: ${portfolio.get_realized_pnl():.2f}")
    print(f"Total Unrealized P/L: ${portfolio.get_total_unrealized_pnl():.2f}")
    print(f"Total Portfolio P/L: ${portfolio.get_total_pnl():.2f}")
    print("\n--- P/L Per Lot ---")
    print(portfolio.get_pnl_per_lot_summary())
    print("\n")

    # Buy to cover TSLA (FIFO will cover from the 2024-04-01 lot first)
    portfolio.buy_to_cover("TSLA", 15, 180.00, "2024-05-01")

    print("\n--- After Buying to Cover TSLA (15 shares) ---")
    print(portfolio.get_portfolio_summary())
    print(f"Total Realized P/L: ${portfolio.get_realized_pnl():.2f}")
    print(f"Total Unrealized P/L: ${portfolio.get_total_unrealized_pnl():.2f}")
    print(f"Total Portfolio P/L: ${portfolio.get_total_pnl():.2f}")
    print("\n--- P/L Per Lot ---")
    print(portfolio.get_pnl_per_lot_summary())
    print("\n")

    print("\n--- Transaction History ---")
    print(portfolio.get_transaction_history())

    print("\n--- Detailed Portfolio Report (Nested Structure) ---")
    detailed_report = portfolio.get_detailed_portfolio_report()
    import json
    print(json.dumps(detailed_report, indent=4))
