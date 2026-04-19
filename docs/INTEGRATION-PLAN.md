# Enso Trading Terminal — Integration Plan & Task Backlog

> Last updated: April 19, 2026 (post-audit)
> Status: Living document — update as tasks complete

---

## 📝 Audit Note (2026-04-19)

A codebase audit reconciled this plan against the actual repo at commit
`bc40157`. Tasks 1.1, 1.2, and 2.1 were already substantially built at the
time the plan was drafted; see status markers below for pointers to the
existing implementations.

---

## ✅ Phase 1: Public.com API Integration (COMPLETE)

### Task 1.1 — Wire `api_client.py` to Real Public.com SDK

**Status:** ✅ DONE (shipped v0.2.0)
**File:** `modules/api_client.py` — 524-line wrapper around `public_api_sdk v0.1.10` (`publicdotcom-py`)
**Account:** 5LF05438
**Auth:** `PUBLIC_COM_SECRET` env var

Implementation covers:
- Auth via `ApiKeyAuthConfig` with `PUBLIC_COM_SECRET`
- Positions, balances, order history, quotes, options chains
- Order placement + preflight, expirations, history
- Lazy SDK install on import

---

### Task 1.2 — Volatility Monitor (IV vs RV Gap Tracking)

**Status:** ✅ DONE (shipped v0.3.0 + v0.6.0)
**Existing implementations:**
- `modules/strategy_engines.py::run_iv_rv_backtest` — 20-day realized vol,
  IV-RV gap computation, threshold-based regime flags (HIGH_IV / LOW_IV).
- `modules/agent_framework.py::VolatilityAgent` — 4-level regime classifier
  (LOW_VOL / NORMAL / HIGH_VOL / EXTREME) with FlashAlpha gamma overlay that
  bumps the regime on negative-gamma dealer states.
- `modules/strategy_map.py` — 9-cell (direction × vol_regime) strategy matrix
  used by the synthesizer to pick plays.

**Remaining polish (optional, not blocking):**
- [ ] Extract shared vol logic into a dedicated `modules/vol_monitor.py`
- [ ] Add a vol-regime indicator panel to the Dash dashboard page

---

## 🟡 Phase 2: Signal Filters

### Task 2.1 — Vol Regime Filter

**Status:** ✅ DONE (effectively — implemented via strategy map, not a separate filter)
**Rationale:** The design goal (gate strategy selection by vol regime) is
already satisfied by `VolatilityAgent` → `strategy_map.get_strategy(direction, vol_regime)`.
Adding a standalone filter would duplicate this gating.

If a blocking filter (rather than strategy-selection gate) is still wanted,
this can be revisited as a follow-up; leaving closed for now.

---

### Task 2.2 — Time-of-Day Filter

**Status:** ✅ DONE (shipped v0.9.0)
**File:** `modules/signal_filters.py::TimeOfDayFilter`
**Tests:** `test_signal_filters.py` (9 cases pass)

Implementation:
- Blocks first `TOD_OPEN_BUFFER_MIN` minutes after open (default 30)
- Blocks last `TOD_CLOSE_BUFFER_MIN` minutes before close (default 15)
- Blocks weekends + pre/post-market
- Blocks ±`TOD_ECON_RELEASE_BUFFER_MIN` around econ releases passed via context
- ET timezone, DST-safe (`zoneinfo.ZoneInfo("America/New_York")`)

---

### Task 2.3 — Failed Breakdown Filter

**Status:** ✅ DONE (shipped v0.9.0)
**File:** `modules/signal_filters.py::FailedBreakdownFilter`
**Tests:** `test_signal_filters.py` (7 cases pass)

Implementation:
- Scans the last `FAILED_BREAKDOWN_LOOKBACK` bars (default 3)
- Detects pierce below support (with `FAILED_BREAKDOWN_TOLERANCE_PCT` tolerance)
  followed by close back above support
- Blocks bearish signals when detected (trapped shorts)
- Tags bullish signals with `reversal_confirmation: true`
- Composable via `FilterChain` with any other `SignalFilter`

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
