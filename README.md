# stock-portfolio-analyzer
I'm sick of schwab, google/yahoo finance, and other portfolio analyzers. They suck. I'm building a portfolio analyzer that has:
- The simple visuals of google finance
- Ability to add cash positions (crazy that google/yahoo/seekingalpha doesnt have this!)
- Quant anaysis to see the risk adjusted performance of your portfolio and tips on how to optimize your holdings given the news/macroeconomic data at the time
- See real time prices even in after hours and pre-market (most portfolio viewers don't have this they only show closing price)
- Insider trades, news, float, instittiounal vs retail holdings, polititan trades, analyst ratings and consumer reports


---
![image](https://github.com/user-attachments/assets/7a082a05-5f5b-48d0-ad11-e45b1253aea5)

## 🚀 Portfolio Analyzer — Feature Roadmap

### 🧩 Phase 1: **Core Portfolio Engine (MVP)**

**Goal:** Replicate the basic functionality of Google Finance + cash tracking + live prices

#### ✅ Features:

* ✅ Add/edit/remove holdings (stocks, ETFs, crypto)
* ✅ Add/edit/remove cash transactions (deposits, withdrawals, dividends)
* ✅ Calculate current portfolio value (including cash)
* ✅ Use **live & extended-hours prices**
* ✅ Track average cost, P/L %, and net worth over time
* [ ] Import from CSV (optional)
* [ ] Implement short selling

#### 📦 Tools:

* [`yfinance`](https://pypi.org/project/yfinance/) or [`alpaca`](https://alpaca.markets/) for price data
* `pandas` for portfolio logic
* `Streamlit` or `Dash` for UI

---

### 📊 Phase 2: **Quantitative Analytics Dashboard**

**Goal:** Add portfolio statistics & risk analysis

#### ✅ Features:

* [ ] Annual return
* [ ] Volatility
* [ ] Sharpe ratio
* [ ] Maximum drawdown
* [ ] Beta & Alpha vs benchmark (e.g., SPY)
* [ ] Monthly return chart / rolling performance

#### 📦 Tools:

* [`quantstats`](https://github.com/ranaroussi/quantstats)
* `pandas`, `numpy`, `matplotlib`, `seaborn`
* Optional: `pyfolio`, `ffn`

---

### 🗓️ Phase 3: **News & Earnings Integration**

**Goal:** Surface timely info for smarter decisions

#### ✅ Features:

* [ ] Earnings calendar (per holding)
* [ ] News feed per stock
* [ ] Highlight important events: splits, dividend dates, earnings beats/misses
* [ ] Scrape SEC filings for form 10Q, 4, 144 for anolmalies in insider buys

#### 📦 APIs:

* [ ] [Marketaux](https://www.marketaux.com/) — news
* ✅ [Finnhub](https://finnhub.io/) — earnings & news
* ✅ [Yahoo Finance API](https://pypi.org/project/yahooquery/) — free data

---

### 📈 Phase 4: **Visual Portfolio Breakdown**

**Goal:** Improve readability and decision-making

#### ✅ Features:

* ✅ Asset allocation by category (stocks, cash, crypto, etc.)
* [ ] Sector exposure
* [ ] Geographical breakdown
* [ ] Heatmap of returns
* ✅ P/L timeline (line chart)

