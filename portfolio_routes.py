from __main__ import app
from flask import request, jsonify
from portfolio_manager import PortfolioManager
import requests
manager = PortfolioManager()

@app.route("/api/add_transaction", methods=["POST"])
def add_transaction():
    data = request.json
    symbol = data.get("symbol")
    quantity = data.get("quantity")
    cost_basis = data.get("cost_basis")
    company_name = data.get("company_name")
    type = data.get("type")
    date = data.get("date", None)
    action = data.get("action")

    if not all([symbol, quantity, cost_basis, company_name, type, action]):
        return jsonify({"error": "Missing required transaction data"}), 400

    manager.add_transaction(symbol, quantity, cost_basis, date, company_name, type, action)
    return jsonify({"message": f"Transaction added for {symbol.upper()}."})


@app.route("/api/transactions/<id>", methods=["DELETE"])
def delete_trasaction(id):
    manager.remove_transaction(id)
    return jsonify({"message": f"Transaction deleted for {id}."})

@app.route("/api/portfolio", methods=["GET"])
def get_portfolio_info():
    response = manager.get_portfolio_info()
    return jsonify(response)

@app.route("/api/cache/portfolio", methods=["GET"])
def get_portfolio_info_from_cache():
    response = manager.get_portfolio_info_from_cache()
    return jsonify(response)

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
