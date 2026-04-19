# Enso Trading Terminal — Claude Code Context

> Last updated: April 19, 2026  
> Maintainer: Sav Banerjee (Enso Labs)  
> Repo: https://github.com/nycsav/enso-trading-terminal  
> Live: https://enso-trading-terminal.onrender.com  
> Local dev: `~/trading-dashboard/trading-dashboard/` on Mac Mini

---

## 🏗 Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Web Framework | Dash (Plotly) |
| Charts | Plotly (7 interactive charts on Backtest page) |
| Data | yfinance, scipy, scikit-learn |
| Server | gunicorn |
| CI/CD | GitHub Actions |
| Hosting | Render (free tier) |
| Brokerage | Public.com (account: 5LF05438) |
| API Auth | `PUBLIC_COM_SECRET` env var |

---

## 📁 Project Structure

```
enso-trading-terminal/
├── app.py                        # Main Dash app entry point
├── config.py                     # App config, constants
├── requirements.txt              # Python dependencies
├── Procfile                      # gunicorn start command
├── render.yaml                   # Render deployment config
├── .env.example                  # Env var template (no secrets)
├── .gitignore
├── CHANGELOG.md                  # Version history
├── CLAUDE.md                     # ← YOU ARE HERE
├── test_price_watcher.py         # Price watcher tests
├── assets/                       # Static assets (CSS, images)
├── pages/                        # Dash multi-page app pages
├── modules/                      # Core engine modules
├── strategies/                   # 10 institutional options strategies
│   ├── [10 strategy files]
│   ├── testing-guide.md
│   └── backtest-specs.md
└── docs/
    ├── INTEGRATION-PLAN.md       # Pending tasks & roadmap
    ├── api-opportunities-analysis.md
    ├── capability-instructions.md
    ├── multi-agent-architecture.md
    └── user-guide.pdf
```

---

## ✅ What's Built

### Core Engines
- **S/R Engine** — 20-day pivot lookback, 4-factor confluence scoring
- **Backtesting Engine** — Black-Scholes option pricing, walk-forward optimization
- **ML Strategy** — Gradient Boosted Trees
- **RL Agent** — Q-Learning
- **LLM Signals** — Perplexity Sonar integration

### UI / Pages
- 7 interactive Plotly charts on Backtest page
- Multi-page Dash app structure under `pages/`

### Strategies (`strategies/` folder)
- 10 institutional options strategies
- Testing guide + backtest specs included

### Infrastructure
- GitHub Actions CI/CD pipeline (`.github/` folder)
- Render deployment via `render.yaml`
- `.env.example` documents all required env vars

---

## ⏳ What's Pending (Priority Order)

See `docs/INTEGRATION-PLAN.md` for full task details.

### 🔴 High Priority
_None outstanding — see `docs/INTEGRATION-PLAN.md` for audit details._

### 🟡 Medium Priority
1. **2 Signal Filters** — approved but not built:
   - `time_of_day` filter
   - `failed_breakdown` filter
   - (`vol_regime` is already gated inside `modules/strategy_map.py` + `VolatilityAgent`)

### ✅ Already Built (previously listed as pending)
- `modules/api_client.py` — 524-line real `public_api_sdk v0.1.10` wrapper
- IV/RV gap monitor — `modules/strategy_engines.py::run_iv_rv_backtest` (20-day RV, threshold alerts)
- Vol regime classifier — `VolatilityAgent` in `modules/agent_framework.py` (LOW/NORMAL/HIGH/EXTREME with gamma overlay)

### 🟢 Low Priority / Nice to Have
5. Additional backtest visualization improvements
6. Strategy performance comparison dashboard

---

## 🔐 Environment Variables

```bash
PUBLIC_COM_SECRET=<your_public_com_api_key>   # Public.com brokerage API
PERPLEXITY_API_KEY=<key>                      # LLM signals via Sonar
# See .env.example for full list
```

**Never commit secrets.** Use Render environment variable dashboard for production.

---

## 🚀 Running Locally

```bash
cd ~/trading-dashboard/trading-dashboard/
pip install -r requirements.txt
python app.py
# App runs at http://localhost:8050
```

## 🚀 Running in Production

```bash
gunicorn app:server
# Render auto-deploys on push to main
```

---

## 🧠 Architecture Notes for Claude Code

- **Entry point** is `app.py` — initializes Dash app and registers pages
- **`config.py`** holds all constants, thresholds, and strategy parameters — edit here first before touching engine logic
- **`modules/`** contains the core trading engines — treat as stable, modify carefully
- **`pages/`** contains Dash page layouts — UI changes go here
- **`strategies/`** is documentation + specs, not executable code (yet)
- **`modules/api_client.py`** is a working 524-line wrapper around `public_api_sdk v0.1.10` (`publicdotcom-py`); import from here for all brokerage calls
- The app uses **Dash multi-page** architecture — each file in `pages/` auto-registers as a route

---

## 📋 Key Decisions & Constraints

- Render free tier = cold starts, 512MB RAM limit — keep dependencies lean
- yfinance is the primary data source until Public.com API is live
- Black-Scholes pricing is implemented in the backtesting engine (no external options pricing lib)
- Walk-forward optimization uses scikit-learn pipelines
- Q-Learning RL agent is custom (not stable-baselines)
