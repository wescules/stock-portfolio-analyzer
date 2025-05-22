from __main__ import app
from flask import Flask, request, jsonify
from portfolio_data_manager import PortfolioDataManager

manager = PortfolioDataManager()

@app.route("/update", methods=["POST"])
def update_data():
    updated = manager.update_all_symbols()
    return jsonify({"message": f"Updated {len(updated)} symbols."})



@app.route("/add_transaction", methods=["POST"])
def add_transaction():
    data = request.json
    symbol = data.get("symbol")
    quantity = data.get("quantity")
    cost_basis = data.get("cost_basis")
    date = data.get("date", None)

    if not all([symbol, quantity, cost_basis]):
        return jsonify({"error": "Missing required transaction data"}), 400

    manager.add_transaction(symbol, quantity, cost_basis, date)
    return jsonify({"message": f"Transaction added for {symbol.upper()}."})

@app.route("/summary/<symbol>", methods=["GET"])
def get_summary(symbol):
    summary = manager.get_position_summary(symbol)
    if summary is None:
        return jsonify({"error": "No data for symbol"}), 404
    return jsonify(summary)

@app.route("/analytics/<symbol>", methods=["GET"])
def get_analytics(symbol):
    try:
        metrics = manager.get_analytics(symbol)
        return jsonify(metrics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/transactions/<symbol>", methods=["GET"])
def get_transactions(symbol):
    txs = manager.get_transactions(symbol)
    return jsonify(txs.to_dict(orient="records"))

@app.route("/portfolio_summary", methods=["GET"])
def portfolio_summary():
    try:
        summary = manager.get_portfolio_summary()
        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
