from __main__ import app
from flask import Flask, request, jsonify
from portfolio_data_manager import PortfolioDataManager
from portfolio_manager import PortfolioManager

manager = PortfolioManager()

# @app.route("/update", methods=["POST"])
# def update_data():
#     updated = manager.update_all_symbols()
#     return jsonify({"message": f"Updated {len(updated)} symbols."})



@app.route("/api/add_transaction", methods=["POST"])
def add_transaction():
    data = request.json
    symbol = data.get("symbol")
    quantity = data.get("quantity")
    cost_basis = data.get("cost_basis")
    company_name = data.get("company_name")
    type = data.get("type")
    date = data.get("date", None)

    if not all([symbol, quantity, cost_basis, company_name, type]):
        return jsonify({"error": "Missing required transaction data"}), 400

    manager.add_transaction(symbol, quantity, cost_basis, date, company_name, type)
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