# Enso Trading Terminal

A real-time options trading dashboard with S/R automation and backtesting.

Built with Python, Dash/Plotly, and Black-Scholes option pricing. Connects to your Public.com brokerage account for live market data and signal generation.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![Dash](https://img.shields.io/badge/Dash-2.14+-00ADD8?logo=plotly&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

- **Live brokerage connection** — Public.com API integration for real-time account data, positions, and orders
- **Support/Resistance pivot-based signal generation** — 20-day lookback window identifies pivot highs and lows, clusters nearby levels, and generates actionable signals
- **Confluence scoring** — 4-factor weighted scoring system: proximity (30%), volume (25%), trend (25%), retest (20%)
- **Options automation** — `BUY_CALL` at support levels, `BUY_PUT` at resistance levels, filtered by minimum confluence threshold
- **Full backtesting engine** — Black-Scholes option pricing with configurable parameters across 10 major symbols
- **Walk-forward optimization** — 70/30 train/test split with overfit detection (ROBUST / MODERATE / OVERFIT ratings)
- **Multi-symbol portfolio analysis** — Run backtests across any combination of AMD, QQQ, SPY, META, TSLA, NVDA, AMZN, GOOGL, MSFT, AAPL
- **7 interactive Plotly charts** — Equity curve, price + S/R overlay, win rate by symbol, P&L histogram, monthly P&L, drawdown, confluence scatter

---

## Quick Start

```bash
git clone https://github.com/nycsav/enso-trading-terminal.git
cd enso-trading-terminal
pip install -r requirements.txt
export PUBLIC_API_KEY=your_key_here
python app.py
```

Dashboard runs at **http://localhost:8050**

> **Note:** The dashboard works without a Public.com API key — you'll see market data via yfinance and full backtesting capabilities. The API key enables live brokerage features (account info, positions, order placement).

---

## Backtesting Guide

The backtesting engine lets you simulate the S/R-based options strategy against historical data with configurable parameters.

### Navigating to the Backtest Page

Click the **chart-line icon** (📈 Backtest) in the left sidebar. The sidebar has two navigation links:
1. **Dashboard** — Main market overview with live S/R signals
2. **Backtest** — Full backtesting engine (this page)

### Configuring a Backtest

The backtest page has two rows of controls at the top:

**Row 1 — Symbol & Date Range:**
| Control | Description |
|---------|-------------|
| **Symbols** | Multi-select dropdown. Choose one or more from: AMD, QQQ, SPY, META, TSLA, NVDA, AMZN, GOOGL, MSFT, AAPL. Running multiple symbols produces a combined portfolio analysis. |
| **Start Date** | Beginning of the backtest window. Defaults to 1 year ago. |
| **End Date** | End of the backtest window. Defaults to today. |

**Row 2 — Strategy Parameters:**
| Control | Description | Range |
|---------|-------------|-------|
| **Proximity Threshold** | How close (%) price must be to a S/R level to trigger a signal. Lower = fewer but higher-conviction trades. | 0.5% – 3.0% (slider) |
| **Option Expiry** | Weeks to expiration for simulated options contracts. | 1–6 weeks (dropdown) |
| **Starting Capital** | Initial portfolio value in USD. | $1,000+ (input) |
| **Position Size** | Percentage of capital allocated per trade. | 1–25% (input) |

### Running a Backtest

1. Select your symbols and date range
2. Adjust the proximity threshold, expiry, capital, and position size
3. Click the green **"Run Backtest"** button
4. Wait for the loading spinner — the engine downloads price data, calculates S/R levels for each bar, generates signals, prices options via Black-Scholes, and tracks P&L through expiration
5. Results appear as metric cards and 7 interactive charts

### Understanding the 13+ Metrics

After a backtest completes, a row of metric cards appears above the charts:

| Metric | Description |
|--------|-------------|
| **Total Trades** | Number of completed option trades across all symbols |
| **Win Rate** | Percentage of trades with positive P&L |
| **Loss Rate** | Percentage of trades with zero or negative P&L |
| **Avg Win** | Average dollar profit on winning trades |
| **Avg Loss** | Average dollar loss on losing trades |
| **Win/Loss Ratio** | Ratio of average win to average loss (higher = better risk/reward) |
| **Total P&L** | Net profit/loss across all trades in dollars |
| **Max Drawdown** | Largest peak-to-trough decline as a percentage of peak equity |
| **Sharpe Ratio** | Risk-adjusted return (annualized). Above 1.0 is generally good, above 2.0 is excellent |
| **Profit Factor** | Gross profits divided by gross losses. Above 1.0 means the strategy is profitable |
| **Best Trade** | Highest single-trade profit in dollars |
| **Worst Trade** | Largest single-trade loss in dollars |
| **Avg Holding Period** | Average number of days positions are held before expiry |
| **Call vs Put Breakdown** | Count of BUY_CALL (support bounces) vs BUY_PUT (resistance rejections) |
| **Monthly P&L** | Profit/loss broken down by calendar month |

### Walk-Forward Optimization (WFO)

WFO tests whether your strategy parameters generalize to unseen data:

1. Click the blue **"Walk-Forward Optimization"** button
2. The engine splits your data into **70% training / 30% testing**
3. On the training set, it grid-searches proximity thresholds from 0.5% to 3.0% (in 0.25% steps) and selects the value with the highest Sharpe ratio
4. The best parameter is then validated on the 30% test set
5. Train vs test Sharpe ratios are compared for overfit detection

**Overfit Ratings:**
| Rating | Meaning | Criteria |
|--------|---------|----------|
| 🟢 **ROBUST** | Strategy generalizes well to unseen data | Test Sharpe ≥ 50% of Train Sharpe |
| 🟡 **MODERATE** | Some degradation on unseen data — use caution | Test Sharpe ≥ 25% of Train Sharpe |
| 🔴 **OVERFIT** | Strategy is curve-fitted to training data — do not trust | Test Sharpe < 25% of Train Sharpe |

The WFO results panel shows: best proximity parameter, train/test Sharpe ratios, train/test date ranges, test P&L, and test win rate.

### Exporting Results to CSV

Click the **"Export CSV"** button to download all trade data as a CSV file. The export includes: symbol, trade type, entry/exit dates, entry/exit prices, strike price, premium, P&L, contracts, holding period, and confluence score.

### Reading the 7 Charts

#### 1. Equity Curve
**Full-width line chart** showing portfolio value over time for each symbol. The starting point is your initial capital. Upward slopes indicate profitable periods; flat sections mean no open positions. Multiple symbols appear as separate colored lines for comparison.

#### 2. Price + S/R Overlay
**Candlestick chart** for the first selected symbol with horizontal dashed lines marking support (green) and resistance (red) levels. This shows where the engine identified tradeable levels and how price interacted with them during the backtest period.

#### 3. Win Rate by Symbol
**Bar chart** comparing win rates across all selected symbols. Bar color ranges from red (low win rate) through yellow to green (high win rate). The number on each bar shows total trades for that symbol. Useful for identifying which symbols the strategy works best on.

#### 4. P&L Histogram
**Distribution chart** of individual trade P&L values. A vertical dashed line at $0 separates winners from losers. A right-skewed distribution (more mass to the right) indicates the strategy has a positive edge. Look for fat right tails (occasional large wins) vs concentrated left tails (frequent small losses).

#### 5. Monthly P&L (Heatmap)
**Bar chart** showing net P&L by calendar month. Green bars are profitable months, red bars are losing months. Helps identify seasonality or whether performance is concentrated in a few months vs consistently distributed.

#### 6. Drawdown Chart
**Area chart** showing percentage drawdown from peak equity over time. Values are always negative or zero. Deeper valleys indicate larger drawdowns. Compare the depth and duration of drawdowns across symbols to assess risk.

#### 7. Confluence Scatter
**Scatter plot** of confluence score (x-axis) vs trade P&L (y-axis). Points are colored by trade type (green for BUY_CALL, red for BUY_PUT) and shaped by symbol. A positive correlation (higher confluence → higher P&L) validates that the confluence scoring system adds value. Look for clusters of profitable trades at higher confluence scores.

### Example Workflow

Here's a complete workflow for evaluating NVDA:

1. **Configure:** Select NVDA, set 1-year date range, 1.5% proximity, 3-week expiration, $10K capital, 5% position size
2. **Run Backtest:** Click "Run Backtest" and review the metric cards — check total P&L, win rate, and Sharpe ratio
3. **Analyze Equity Curve:** Look for consistent upward slope vs jagged performance. Check max drawdown
4. **Run WFO:** Click "Walk-Forward Optimization" to test parameter robustness
5. **Check Rating:** If **ROBUST** — the 1.5% proximity generalizes well. If **OVERFIT** — try different parameters
6. **Iterate:** Adjust proximity threshold (try 1.0% or 2.0%), re-run, compare Sharpe ratios
7. **Multi-Symbol:** Add SPY and QQQ to diversify, re-run to see combined portfolio performance
8. **Export:** Download the trade log CSV for detailed analysis in Excel or pandas

---

## Remote Deployment (Render)

Deploy the dashboard to Render.com for access from any device.

### Option 1: Blueprint Deployment (Recommended)

This repo includes a `render.yaml` blueprint file for one-click deployment:

1. Fork or push this repo to your GitHub account
2. Go to [Render Dashboard](https://dashboard.render.com/) → **New** → **Blueprint**
3. Connect your GitHub repo
4. Render reads `render.yaml` and configures everything automatically
5. Set the `PUBLIC_API_KEY` environment variable when prompted
6. Click **Apply** — your dashboard will be live in minutes

### Option 2: Manual Deployment

1. **Procfile** is already included:
   ```
   web: gunicorn app:server --bind 0.0.0.0:$PORT
   ```

2. **gunicorn** is already in `requirements.txt`

3. Go to [Render Dashboard](https://dashboard.render.com/) → **New** → **Web Service**

4. Connect your GitHub repo (`nycsav/enso-trading-terminal`)

5. Configure:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:server --bind 0.0.0.0:$PORT`
   - **Environment:** Python 3

6. Add environment variables:
   | Variable | Value |
   |----------|-------|
   | `PUBLIC_API_KEY` | Your Public.com API key |
   | `DASH_DEBUG` | `false` |

7. Click **Create Web Service**

8. Access your dashboard at `https://enso-trading-terminal.onrender.com` (or your custom domain)

> **Tip:** On the free tier, Render spins down after 15 minutes of inactivity. The first request after idle takes ~30 seconds to cold-start.

---

## Architecture

```
enso-trading-terminal/
├── app.py                      # Main Dash app with sidebar navigation
├── config.py                   # Configuration and environment variables
├── requirements.txt            # Python dependencies
├── Procfile                    # Render/Heroku deployment
├── render.yaml                 # Render blueprint for one-click deploy
├── modules/
│   ├── __init__.py
│   ├── sr_engine.py            # S/R calculation engine
│   │                           #   - 20-day pivot lookback
│   │                           #   - Level clustering (0.5% threshold)
│   │                           #   - 4-factor confluence scoring
│   │                           #   - Signal generation (BUY_CALL / BUY_PUT)
│   ├── backtester.py           # Walk-forward backtesting engine
│   │                           #   - Black-Scholes call/put pricing
│   │                           #   - Historical IV estimation
│   │                           #   - 13+ performance metrics
│   │                           #   - Walk-forward optimization
│   │                           #   - Overfit detection (ROBUST/MODERATE/OVERFIT)
│   ├── api_client.py           # Public.com API client
│   ├── research.py             # Market data fetching & technical indicators
│   └── scheduled_tasks.py      # Background signal monitoring
├── pages/
│   ├── __init__.py
│   └── backtest.py             # Backtest dashboard page
│                               #   - Interactive parameter controls
│                               #   - 7 Plotly charts
│                               #   - WFO results panel
│                               #   - CSV export
└── strategies/
    ├── strategy-testing-guide.md    # Plain-English strategy tutorial
    ├── backtest-specs.md            # Technical backtest specifications
    ├── strategy-rankings.json       # Structured strategy data
    ├── strategy-rankings.csv        # Strategy rankings (CSV)
    └── enso-options-strategy-map.html  # Interactive strategy dashboard
```

### Core Components

| Component | Responsibility |
|-----------|---------------|
| **`app.py`** | Main Dash application with dark-themed sidebar navigation, market overview page, live S/R signal table, candlestick + volume chart |
| **`modules/sr_engine.py`** | Pivot detection (20-day lookback), level clustering, 4-factor confluence scoring (proximity 30%, volume 25%, trend 25%, retest 20%), signal generation |
| **`modules/backtester.py`** | Full backtesting loop with Black-Scholes option pricing, position management, 13+ metrics calculation, walk-forward optimization with grid search, overfit detection |
| **`pages/backtest.py`** | Interactive backtest UI: symbol multi-select, date pickers, parameter sliders, 7 Plotly charts (equity, price+S/R, win rate, P&L histogram, monthly, drawdown, confluence), WFO panel, CSV export |
| **`config.py`** | Centralized configuration: API keys, default symbols, S/R parameters, confluence weights, backtest defaults |

---

## Institutional Options Strategies

The `strategies/` directory contains a complete institutional-grade options strategy research workspace:

| File | Description |
|------|-------------|
| **[strategy-testing-guide.md](strategies/strategy-testing-guide.md)** | Plain-English tutorial: how to test and use all 10 strategies, step-by-step |
| **[backtest-specs.md](strategies/backtest-specs.md)** | Technical backtest specifications for each strategy (developer-ready) |
| **[strategy-rankings.json](strategies/strategy-rankings.json)** | Structured data: rankings, scoring, data sources, build phases |
| **[strategy-rankings.csv](strategies/strategy-rankings.csv)** | Same rankings in CSV format for quick reference |
| **[enso-options-strategy-map.html](strategies/enso-options-strategy-map.html)** | Interactive dashboard: strategy rankings, phase timeline, AI use cases |

### The 10 Strategies (by priority)

| # | Strategy | Edge | Difficulty | Phase |
|---|----------|------|------------|-------|
| 1 | IV vs RV Gap Monitor | 9.2 | Medium | Phase 1 |
| 2 | Dealer Gamma Regime | 9.0 | High | Phase 2 |
| 3 | Skew Surface Trading | 8.8 | Expert | Phase 3 |
| 4 | Dispersion / Correlation | 8.5 | Expert | Phase 4 |
| 5 | Event Vol Strangle | 8.2 | Medium | Phase 1 |
| 6 | Term Structure Carry | 7.8 | Medium | Phase 2 |
| 7 | Pinning / 0DTE Dynamics | 7.5 | High | Phase 2 |
| 8 | Vol Risk Premium Harvest | 7.2 | Medium | Phase 1 |
| 9 | Cross-Asset Signal Fusion | 6.8 | High | Phase 3 |
| 10 | S/R + Vol Filter Overlay | 6.2 | Low | Baseline |

Start with the **[Strategy Testing Guide](strategies/strategy-testing-guide.md)** for the plain-English walkthrough.

---

## Tech Stack

| Technology | Purpose |
|------------|---------|
| **Python 3.11+** | Core language |
| **Dash / Plotly** | Interactive web dashboard and charting |
| **dash-bootstrap-components** | Dark theme UI components |
| **yfinance** | Historical market data |
| **scipy** | Black-Scholes normal distribution (CDF) |
| **numpy** | Numerical computations, array operations |
| **pandas** | Data manipulation and time series |
| **gunicorn** | Production WSGI server |

---

## License

MIT

---

Built by [Enso Labs](https://github.com/nycsav)
