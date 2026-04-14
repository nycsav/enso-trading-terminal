# Changelog

All notable changes to the Enso Trading Terminal are documented here.

---

## [v0.7.0] — 2026-04-14 — FlashAlpha GEX + Finviz Unusual Volume Integration

### Added
- **modules/market_data_sources.py** — External data source integrations (561 lines)
  - `FlashAlphaSource` — Real-time gamma exposure (GEX) via FlashAlpha API
    - Per-strike GEX with call/put breakdown
    - Gamma flip level, call wall, put wall
    - Dealer regime classification (positive/negative gamma)
    - Free tier: 5 req/day, no credit card
  - `FinvizVolumeScanner` — Unusual volume stock screener
    - Filters: optionable, price > $10, avg volume > 1M
    - Dynamic watchlist generator ("Layer 0")
    - Fallback to default large-cap list if scan fails

### Changed
- **modules/agent_framework.py** — Upgraded to 1,572 lines with two major enhancements:
  - `VolatilityAgent` now accepts FlashAlpha source — GEX data refines vol regime:
    - Negative gamma + NORMAL → bumped to HIGH_VOL (amplified moves)
    - Negative gamma + HIGH_VOL → bumped to EXTREME
    - Positive gamma + EXTREME → downgraded to HIGH_VOL (dampened)
  - `SignalSynthesizer` uses GEX in bull/bear debate (gamma regime + wall levels)
  - `TradePrep` uses call wall / put wall for strike zone guidance (replaces ATR-only)
  - `run_pipeline()` gains 3 new params: `flashalpha_api_key`, `use_finviz_watchlist`, `finviz_max_tickers`
  - Pipeline now shows GEX data in console output when available
- **requirements.txt** — Added `finvizfinance>=1.0.0` and `flashalpha>=0.1.0`

### Data Sources
- FlashAlpha Lab API: https://flashalpha.com/docs/lab-api-gex
- Finviz screener: https://finviz.com/screener.ashx
- finvizfinance library: https://github.com/lit26/finvizfinance

---

## [v0.6.0] — 2026-04-14 — Multi-Agent Trading Framework

### Added
- **modules/agent_framework.py** — 3-layer, 6-agent trading intelligence engine (1,380 lines)
  - Layer 1 (Intelligence): NewsAgent, TechnicalAgent, VolatilityAgent
  - Layer 2 (Strategy): SignalSynthesizer with bull/bear debate pattern
  - Layer 3 (Execution): RiskManager + TradePrep
  - `run_pipeline()` entry point chains all agents, returns top 3 recommendations
- **modules/strategy_map.py** — 9-strategy options mapping (direction + volatility regime → specific play)
- **docs/multi-agent-architecture.md** — Full architecture design document
- **Morning Market Scanner** — Perplexity cron job at 8:15 AM ET (weekdays) feeding Layer 1

### Architecture Sources
- QuantInsti multi-agent bot (analyst → portfolio → execution pipeline)
- TradingAgents / UCLA+MIT (bull/bear debate for balanced analysis)
- LLM-Enhanced-Trading (sentiment integration boosted TSLA Sharpe from 0.34 to 3.47)
- FinRL-Trading (weight-centric architecture with Alpaca paper deployment)

---

## [v0.5.0] — 2026-04-13 — Phase 1: Perplexity Automation (Stocks & Options)

### Added
- **docs/capability-instructions.md** — Step-by-step instructions for 8 new capabilities (copy-paste prompts for Perplexity + dashboard enhancements)
- **docs/api-opportunities-analysis.md** — Full analysis of 12 untapped Public.com API opportunities, prioritized
- **docs/user-guide.pdf** — Updated user guide (v2) with new Section 8: Perplexity Automation

### New Capabilities (Prompt-Based — No Code Changes)
1. **Morning Briefing** — Weekday 9:30 AM portfolio summary via Perplexity cron
2. **Expiration Alert** — Weekday 3:45 PM options expiration watch via Perplexity cron
3. **Covered Call Scanner** — Monday 9:00 AM scan of holdings for covered call opportunities
4. **Dip Alert** — Weekday 3:00 PM watchlist monitoring with protective put suggestions
5. **Research-to-Trade Pipeline** — On-demand research → options chain → strategy → preflight → trade
6. **Rebate Tracker** — On-demand monthly contract volume and rebate tier tracking

### Planned Dashboard Enhancements
7. **Cancel-and-Replace Orders** — Edit active orders via new Public.com PUT endpoint (March 2026)
8. **Multi-Leg Strategy Builder** — Iron condors, spreads, straddles as single multi-leg orders

---

## [v0.4.0] — 2026-04-13 — Symbol Expansion & Dark Theme Fix

### Changed
- Expanded symbol dropdowns from 10 to 60+ tickers across Dashboard and Backtest pages
- Made all dropdowns searchable (type-to-filter)

### Fixed
- Dark theme CSS: invisible text on form controls (dark text on dark background)
- Added `assets/custom.css` with overrides for all Dash form elements

---

## [v0.3.0] — 2026-04-13 — Extended Backtesting Strategies

### Added
- **modules/strategy_engines.py** — 6 new backtesting strategies (1,057 lines):
  - IV vs RV Gap Monitor
  - Event Vol Strangle
  - Vol Risk Premium Harvest
  - S/R + Vol Filter Overlay
  - Term Structure Carry
  - Cross-Asset Momentum
- Total strategies now: 8 (2 original + 6 new)
- Updated `pages/backtest.py` with all 8 strategies in the dropdown

---

## [v0.2.0] — 2026-04-13 — Real SDK Integration & Live Brokerage Pages

### Added
- **modules/api_client.py** — 525-line SDK wrapper verified against `public_api_sdk` v0.1.10
- **pages/portfolio.py** — Live portfolio view (equity, positions, P&L, buying power)
- **pages/options.py** — Live options chain viewer (calls, puts, Greeks, bid/ask)
- **pages/orders.py** — Order management (preflight calculator + order placement)
- **config.py** — Full configuration with `PUBLIC_COM_SECRET`, color theme, account IDs

### Changed
- **app.py** — 5 sidebar nav items (Dashboard, Portfolio, Backtest, Options Chain, Orders)
- Connection status indicator in sidebar (green/red dot)

---

## [v0.1.0] — Initial Release

### Added
- Dash app with S/R engine, backtester, ML/RL strategy modules
- Support/Resistance pivot detection with confluence scoring
- Black-Scholes option pricing
- Walk-forward optimization with overfit detection
- 7 interactive Plotly charts
- Render deployment configuration (Procfile, render.yaml)
- Institutional options strategy workspace (10 strategies documented)
