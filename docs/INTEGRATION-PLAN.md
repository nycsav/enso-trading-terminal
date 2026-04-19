# Enso Trading Terminal — Integration Plan & Task Backlog

> Last updated: April 19, 2026  
> Status: Living document — update as tasks complete

---

## 🔴 Phase 1: Public.com API Integration (HIGH PRIORITY)

### Task 1.1 — Wire `api_client.py` to Real Public.com SDK

**Status:** 🔴 NOT STARTED — current file is a placeholder stub  
**File:** `api_client.py` (modules/ or root)  
**Account:** 5LF05438  
**Auth:** `PUBLIC_COM_SECRET` env var

**What needs to happen:**
- [ ] Install/import official Public.com Python SDK (or REST client)
- [ ] Implement authentication with `PUBLIC_COM_SECRET`
- [ ] Wire account data endpoints: positions, balances, order history
- [ ] Wire market data endpoints: quotes, options chains
- [ ] Replace all mock/stub returns with real API calls
- [ ] Add error handling, rate limiting, retry logic
- [ ] Add unit tests to cover API client methods

**Reference:** `docs/api-opportunities-analysis.md` has endpoint research.

---

### Task 1.2 — Phase 1: Volatility Monitor (IV vs RV Gap Tracking)

**Status:** 🔴 NOT STARTED  
**Location:** New module — `modules/vol_monitor.py` (suggested)

**What needs to happen:**
- [ ] Build IV (Implied Volatility) data pipeline — pull from options chain
- [ ] Build RV (Realized Volatility) calculator — rolling window on price data
- [ ] Compute IV vs RV gap (vol premium)
- [ ] Define threshold alerts: e.g., IV/RV ratio > 1.3 = elevated premium
- [ ] Surface gap data as a signal input for strategy selection
- [ ] Add vol regime classification: `low / normal / elevated / extreme`
- [ ] Integrate display into Dash UI (new chart or indicator panel)

**Design notes:**
- Use 20-day RV to match existing S/R engine lookback period
- IV source: Public.com options chain once API is live; yfinance options as fallback

---

## 🟡 Phase 2: Signal Filters (MEDIUM PRIORITY)

All 3 filters below have been **approved in design** but not yet built.

### Task 2.1 — Vol Regime Filter

**Status:** 🟡 APPROVED, NOT BUILT  
**Depends on:** Task 1.2 (vol_monitor.py)  
**Location:** `modules/signal_filters.py` (new) or inline in strategy engine

**Logic:**
- [ ] Gate strategy signals based on current vol regime
- [ ] `low vol` → favor debit spreads, long gamma
- [ ] `elevated vol` → favor credit spreads, short premium
- [ ] `extreme vol` → block new entries, manage existing positions only
- [ ] Config thresholds in `config.py`

---

### Task 2.2 — Time-of-Day Filter

**Status:** 🟡 APPROVED, NOT BUILT  
**Location:** `modules/signal_filters.py`

**Logic:**
- [ ] Block signal generation during first 30 min (9:30–10:00 ET) — avoid open volatility
- [ ] Block signal generation last 15 min (3:45–4:00 ET) — avoid close slippage
- [ ] Flag signals generated within 30 min of major economic releases
- [ ] All times in US/Eastern; handle DST correctly
- [ ] Make windows configurable via `config.py`

---

### Task 2.3 — Failed Breakdown Filter

**Status:** 🟡 APPROVED, NOT BUILT  
**Location:** `modules/signal_filters.py`

**Logic:**
- [ ] Detect when price breaks below S/R level but closes back above within N bars
- [ ] Tag these as `failed_breakdown` events
- [ ] Use as a bullish reversal signal input (failed breakdown = trapped shorts)
- [ ] Define N (lookback bars) in `config.py` — suggested default: 3 bars
- [ ] Integrate with existing S/R engine confluence scoring

---

## 🟢 Phase 3: UI & Reporting Enhancements (LOW PRIORITY)

### Task 3.1 — Strategy Performance Comparison Dashboard

**Status:** 🟢 BACKLOG  

- [ ] Side-by-side performance table for all 10 strategies
- [ ] Sharpe ratio, max drawdown, win rate, avg P&L per strategy
- [ ] Filter by date range, market regime, ticker
- [ ] Export to CSV

---

### Task 3.2 — Backtest Visualization Improvements

**Status:** 🟢 BACKLOG  

- [ ] Add equity curve chart to backtest results
- [ ] Add trade-by-trade breakdown table
- [ ] Highlight walk-forward optimization windows on chart
- [ ] Add benchmark comparison (SPY overlay)

---

## 📌 Architecture Decisions Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-04 | Keep yfinance as fallback data source | Public.com API not yet live; yfinance covers all dev/test needs |
| 2026-04 | Signal filters in dedicated `signal_filters.py` module | Keeps strategy logic clean; filters composable |
| 2026-04 | Vol regime thresholds in `config.py` | Makes tuning easy without touching engine code |
| 2026-04 | 20-day RV window matches S/R lookback | Consistency across engines; single parameter to tune |

---

## 🔗 Related Docs

- `docs/api-opportunities-analysis.md` — Public.com API endpoint research
- `docs/capability-instructions.md` — Agent capability definitions
- `docs/multi-agent-architecture.md` — Multi-agent system design
- `strategies/testing-guide.md` — How to test strategies
- `strategies/backtest-specs.md` — Backtest specification details
- `CLAUDE.md` (root) — Full project context for Claude Code
