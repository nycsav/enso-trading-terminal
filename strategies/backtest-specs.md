# Enso Strategy Backtest Specifications

**Version:** 1.0  
**Date:** 2026-04-12  
**Audience:** Developer  
**Scope:** Implementation-ready backtest specs for all 10 ranked strategies.

Strategies are ordered by rank. For each strategy, the spec describes exact signal logic, data contracts, parameter grids, metrics, walk-forward config, mock data generation, and integration notes against the existing Enso modules (`backtester.py`, `sr_engine.py`, `api_client.py`, `config.py`).

---

## Strategy: IV vs RV Gap Monitor
### Backtest ID: `iv_rv_gap`

**Signal Logic:**

- **Realized Volatility (RV):** 20-day rolling annualized close-to-close standard deviation.

$$RV_t = \sqrt{252} \cdot \sigma\!\left(\ln\frac{S_{t-i}}{S_{t-i-1}},\ i=0\ldots N-1\right)$$

- **Implied Volatility (IV):** 30-delta ATM IV from the nearest-expiry options chain (≥ 7 DTE, ≤ 45 DTE). Source: Polygon options chain, field `implied_volatility` on the closest ATM strike.

- **IV-RV Spread:** `gap = IV_atm - RV_20`

**Entry conditions — SELL PREMIUM (credit spread):**
1. `gap > iv_rv_threshold` (default 5 vol points, i.e. `IV - RV > 0.05`)
2. VIX < 30 (regime filter — avoid selling into crisis)
3. No open position in this symbol

Signal type: sell a 30-delta call spread (BUY_PUT analogue in existing engine) or iron condor.

**Entry conditions — BUY PREMIUM (debit spread):**
1. `gap < -iv_rv_threshold` (IV is cheap relative to RV)
2. Entry only within 5 days of a known catalyst (earnings, macro event)

**Exit conditions:**
- Fixed DTE exit: close at 21 DTE (standard theta decay target)
- Stop-loss: position loss exceeds 2× credit received (for sell trades) or 50% of debit paid (for buy trades)
- Hard expiration exit at 0 DTE

**Position sizing:**
- Max notional risk per trade = `capital × position_size_pct / 100`
- For credit spreads: max loss = width of spread × 100 × contracts; solve for contracts
- Kelly fraction (optional, advanced): `f = (p × b - q) / b` where `b = reward/risk`, `p = historical win rate`

**Data Requirements:**

| Field | Source | Frequency | Lookback |
|-------|--------|-----------|----------|
| Close price | yfinance | Daily | 1 year |
| Volume | yfinance | Daily | 1 year |
| ATM IV (30-delta) | Polygon options chain | Daily snapshot | 90 days |
| VIX close | yfinance (`^VIX`) | Daily | 1 year |
| Options expiry dates | Polygon options chain | On-demand | Current chain |

**Parameters to Optimize:**

| Parameter | Range | Default | Step |
|-----------|-------|---------|------|
| RV window (days) | 10–30 | 20 | 5 |
| IV-RV threshold (vol pts) | 2–10 | 5 | 1 |
| Exit DTE | 7–21 | 21 | 7 |
| Stop-loss multiplier | 1.5–3.0 | 2.0 | 0.5 |
| Max VIX (regime filter) | 20–35 | 30 | 5 |
| Position size % | 2–10 | 5 | 1 |

**Metrics to Track:**
- Sharpe ratio (annualized, trade-level)
- Profit factor
- Win rate, average win / average loss
- Theta decay captured: `(credit_received - close_cost) / credit_received × 100%`
- IV-RV spread at entry (distribution: mean, 25th/75th percentile)
- Regime breakdown: % trades entered in low/med/high VIX regimes
- Max consecutive losses
- Max drawdown (equity curve)

**Walk-Forward Config:**
- Train/test split: 70/30 (matches existing `WALK_FORWARD_TRAIN_RATIO`)
- Minimum train period: 252 trading days (need enough IV observations)
- Optimization target: Sharpe ratio
- Overfit detection: test Sharpe ≥ 50% of train Sharpe → ROBUST (reuse existing thresholds in `walk_forward_optimization`)
- Additional check: ensure test win rate is within ±15 percentage points of train win rate

**Mock Data Generation (if live data unavailable):**

IV data is the limiting factor. Generate synthetic IV as:

```
IV_t = RV_t + vrp_t
vrp_t ~ mean-reverting process: vrp_t = vrp_{t-1} × φ + ε_t
φ = 0.92 (daily persistence)
ε_t ~ N(0, σ_vrp²), σ_vrp = 0.02
long-run mean of vrp: 0.04 (4 vol points)
```

Underlying price: Geometric Brownian Motion with stochastic volatility (Heston or SABR). Use daily vol drawn from `RV_t` distribution sourced from SPY historical data (2015–2025). Enforce that synthetic IV is always positive and right-skewed (log-normal floor at 0.08).

Key statistical properties the mock data must have:
- IV > RV on ~65% of days (historically observed)
- Mean IV-RV spread: 3–5 vol points for large-cap equities
- VRP autocorrelation at lag-1: ~0.90

**Implementation Notes:**
- **Reuse:** `backtester.py:run_backtest()` loop skeleton, `backtester.py:calculate_metrics()`, `backtester.py:black_scholes_call/put()` for option pricing, `backtester.py:walk_forward_optimization()`
- **New modules needed:**
  - `modules/iv_fetcher.py`: Polygon options chain fetch → extract ATM IV per expiry → store as daily time-series
  - `modules/vol_calculator.py`: `compute_rv(df, window)` and `compute_iv_rv_gap(rv_series, iv_series)`
- **Estimated complexity:** ~350 lines of new code, 2–3 dev days. IV fetcher is the hardest piece (Polygon chain pagination).

---

## Strategy: Dealer Gamma Regime
### Backtest ID: `dealer_gamma_regime`

**Signal Logic:**

Gamma Exposure (GEX) quantifies whether market makers are net long or short gamma across all open option positions. The sign of aggregate GEX determines the regime:

$$GEX = \sum_{\text{strikes}} OI_{\text{call}} \cdot \Gamma_{\text{call}} \cdot S^2 \cdot 0.01 - OI_{\text{put}} \cdot \Gamma_{\text{put}} \cdot S^2 \cdot 0.01$$

(where S is spot, OI is open interest in contracts, Γ is Black-Scholes gamma per dollar)

- **Positive GEX regime:** `GEX > gex_threshold` → dealers are long gamma → they sell into rallies, buy dips → **mean-reversion signal**
- **Negative GEX regime:** `GEX < -gex_threshold` → dealers are short gamma → hedging amplifies moves → **momentum/breakout signal**

**Entry conditions — Positive GEX (mean-reversion):**
1. `GEX > +gex_threshold` at close
2. Price moves > `entry_move_pct` intraday in either direction
3. Signal: fade the move (BUY_CALL after intraday drop, BUY_PUT after intraday rally)
4. Hold until end of session or max 1 day

**Entry conditions — Negative GEX (momentum):**
1. `GEX < -gex_threshold` at close
2. Price breaks above/below prior session high/low
3. Signal: follow the breakout direction
4. Hold max 2 days (moves are sharp but short-lived)

**Exit conditions:**
- End-of-day exit for mean-reversion trades
- 2-day max hold for momentum trades
- Hard stop: 1% adverse move from entry

**Position sizing:**
- Volatility-scaled: `position_size = base_risk / (entry_move_pct × σ_daily)`
- Cap at 10% of capital per trade in negative GEX regime (fat tails)

**Data Requirements:**

| Field | Source | Frequency | Lookback |
|-------|--------|-----------|----------|
| GEX aggregate | SpotGamma or SqueezeMetrics | Daily (EOD) | 2 years |
| GEX by strike | SpotGamma | Daily | 90 days |
| SPX/SPY OHLCV | yfinance | Daily + intraday (1h) | 2 years |
| Open interest by strike | Polygon options chain | Daily snapshot | 90 days |
| VIX | yfinance (`^VIX`) | Daily | 2 years |

> **Data availability note:** SpotGamma and SqueezeMetrics GEX are paid subscriptions (~$50–200/month). Historical GEX data (2+ years) requires the professional tier. Until subscribed, use the simulation framework described below.

**Parameters to Optimize:**

| Parameter | Range | Default | Step |
|-----------|-------|---------|------|
| GEX threshold ($B) | 0.5–5.0 | 2.0 | 0.5 |
| Entry move % (mean-rev) | 0.3–1.5 | 0.8 | 0.2 |
| Max hold days (momentum) | 1–3 | 2 | 1 |
| Hard stop % | 0.5–2.0 | 1.0 | 0.5 |
| VIX regime cap | 25–40 | 35 | 5 |

**Metrics to Track:**
- Regime-split returns: separate Sharpe for positive GEX trades vs negative GEX trades
- Win rate by regime
- Average GEX value at entry
- Intraday reversion magnitude vs. entry signal magnitude
- Max adverse excursion (MAE) per trade
- Correlation of strategy returns with SPY (should be near zero if regime is correctly isolated)

**Walk-Forward Config:**
- Train/test split: 70/30
- Walk-forward windows: use 6-month rolling windows (GEX regimes shift over market cycles)
- Optimization target: Sharpe ratio per regime independently
- Overfit detection: compare regime classification accuracy (if GEX > threshold correctly predicts mean-reversion on > 55% of days in-sample, test must show > 50%)

**Mock Data Generation (if live data unavailable):**

This strategy **cannot be properly backtested without actual GEX data**. The following simulation is an approximation only:

1. Synthesize a GEX proxy from options OI via Polygon:
   ```
   For each expiry, compute per-strike gamma using BS formula
   GEX_proxy = Σ (call_OI × gamma_call - put_OI × gamma_put) × spot² × 0.01
   ```
2. GEX regime dynamics: model GEX as a hidden Markov Model with 2 states (positive/negative), transition matrix estimated from 2018–2022 SPX data.
3. Intraday returns in positive GEX: use AR(1) process with φ = 0.6 (mean-reversion).
4. Intraday returns in negative GEX: GARCH(1,1) with high persistence (α+β ≈ 0.97).
5. Key property: simulated data must show autocorrelation sign flip between positive and negative GEX regimes.

**Implementation Notes:**
- **Reuse:** `backtester.py:calculate_metrics()`, `backtester.py:black_scholes_call/put()` for GEX calculation
- **New modules needed:**
  - `modules/gex_engine.py`: GEX aggregation from OI + BS gamma; SpotGamma API client
  - `modules/regime_classifier.py`: classify positive/negative GEX regime, output regime label per bar
  - Intraday data feed (yfinance 1h bars or Polygon minute bars)
- **Estimated complexity:** ~600 lines of new code (GEX engine is mathematically intensive), 4–5 dev days. Blocked on data subscription until GEX source is confirmed.

---

## Strategy: Skew Surface Trading
### Backtest ID: `skew_surface`

**Signal Logic:**

The vol surface has three axes: strike (moneyness), tenor (DTE), and the smile shape. Mispricings are detected by comparing observed market IV at a given (strike, tenor) node against a fitted surface model.

**Surface model:** SVI (Stochastic Volatility Inspired) parametrization:

$$w(k) = a + b\left[\rho(k - m) + \sqrt{(k-m)^2 + \sigma^2}\right]$$

where `k = ln(K/F)` is log-moneyness, `w = σ²T` is total variance, and `(a, b, ρ, m, σ)` are the five SVI parameters fit to each expiry's smile.

**Mispricing signal:**
- For each node `(k_i, T_j)`: `z_score_ij = (IV_market - IV_SVI) / σ_residuals`
- Entry: `|z_score| > z_threshold` (default 2.0)
- Direction: if `z_score > z_threshold` → sell that node (sell expensive wing), hedge with adjacent strikes
- Direction: if `z_score < -z_threshold` → buy that node (buy cheap wing)

**Exit conditions:**
- `|z_score| < 0.5` (surface convergence)
- Max hold: 5 trading days
- DTE exit: close all legs at 7 DTE to avoid pin risk

**Position sizing:**
- Vega-neutral sizing: `contracts = target_vega / vega_per_contract`
- Target vega per position: 1% of portfolio vega budget
- Delta-hedge daily using underlying

**Data Requirements:**

| Field | Source | Frequency | Lookback |
|-------|--------|-----------|----------|
| Full options chain (all strikes, 4+ expiries) | iVolatility or CBOE DataShop | Daily EOD | 2 years |
| Underlying OHLCV | yfinance | Daily | 2 years |
| Risk-free rate | FRED (DGS3MO) | Daily | 2 years |
| Dividend yield | yfinance | On-demand | Current |
| CBOE SKEW index | yfinance (`^SKEW`) | Daily | 2 years |

> **Data availability note:** A full options chain with IV surface requires iVolatility (~$200/month) or CBOE DataShop (institutional pricing). This is a Phase 3 strategy and data cost is the primary gating factor.

**Parameters to Optimize:**

| Parameter | Range | Default | Step |
|-----------|-------|---------|------|
| Z-score entry threshold | 1.5–3.0 | 2.0 | 0.25 |
| Z-score exit threshold | 0.3–1.0 | 0.5 | 0.1 |
| Max hold days | 3–10 | 5 | 1 |
| Min DTE filter (entry) | 7–30 | 14 | 7 |
| Vega budget % of capital | 0.5–2.0 | 1.0 | 0.5 |
| SVI fit window (# expiries) | 3–6 | 4 | 1 |

**Metrics to Track:**
- Vega P&L (primary): `Σ vega_i × ΔIV_i`
- Delta P&L (should be near zero with daily hedging)
- Theta bleed per day
- Surface RMSE (quality of SVI fit over time)
- Z-score mean reversion speed (half-life of mispricing, measured in days)
- Sharpe ratio (vega P&L only, excluding delta hedge P&L)

**Walk-Forward Config:**
- Train/test split: 70/30
- SVI parameters re-calibrated daily (not walk-forward optimized in the classical sense)
- Walk-forward applies to: z-score threshold and vega budget
- Optimization target: Sharpe on vega P&L
- Overfit detection: monitor RMSE of SVI fit on test data vs. train — if test RMSE > 1.5× train RMSE, surface model is not generalizing

**Mock Data Generation (if live data unavailable):**

Generate a synthetic vol surface using a Heston model:
1. Calibrate Heston parameters `(v0, κ, θ, ξ, ρ)` to SPX surface on a representative date (e.g., 2024-01-15)
2. Simulate forward surfaces by perturbing parameters with a mean-reverting process:
   ```
   θ_t = θ_{t-1} × e^{-0.05} + θ_mean × (1 - e^{-0.05}) + N(0, 0.001)
   ```
3. Add random mispricing shocks: every 5–10 days, inject a z-score > 2 at a random node with 70% probability of reversion within 3 days
4. Required properties: put-call parity holds exactly, no-arbitrage constraints satisfied (calendar spread monotonicity, butterfly non-negativity)

**Implementation Notes:**
- **Reuse:** `backtester.py:black_scholes_call/put()` for Greeks calculation
- **New modules needed:**
  - `modules/vol_surface.py`: SVI calibration (`scipy.optimize.minimize`), surface interpolation, z-score computation
  - `modules/greeks_engine.py`: full Greeks (delta, gamma, vega, theta) for each leg
  - `modules/delta_hedger.py`: daily rebalancing logic
- **Estimated complexity:** ~900 lines of new code, 7–10 dev days. SVI calibration and no-arbitrage enforcement are the hardest parts. Requires numpy/scipy; consider `py_vollib` for Greeks shortcuts.

---

## Strategy: Dispersion / Correlation Trades
### Backtest ID: `dispersion_correlation`

**Signal Logic:**

A dispersion trade sells index volatility while buying single-stock volatility (or vice versa), profiting from the difference between implied correlation and realized correlation.

**Implied correlation:**

$$\rho_{impl} = \frac{\sigma_{index}^2 - \sum_i w_i^2 \sigma_i^2}{2 \sum_{i<j} w_i w_j \sigma_i \sigma_j}$$

where `σ_index` = ATM IV of the index (SPX/SPY), `σ_i` = ATM IV of constituent `i`, `w_i` = index weight.

**Realized correlation:**

$$\rho_{real} = \frac{\sigma_{index,real}^2 - \sum_i w_i^2 \sigma_{i,real}^2}{2 \sum_{i<j} w_i w_j \sigma_{i,real} \sigma_{j,real}}$$

**Entry — Sell Dispersion (short correlation):**
1. `ρ_impl - ρ_real > corr_threshold` (implied correlation is expensive; index vol rich vs. single-stock vol)
2. Sell ATM straddle on SPX, buy ATM straddles on top N constituents (vega-weighted)
3. VIX < 25 (no crisis)

**Entry — Buy Dispersion (long correlation):**
1. `ρ_impl - ρ_real < -corr_threshold`
2. Buy SPX straddle, sell constituent straddles

**Exit conditions:**
- Monthly (roll at expiration)
- Stop-loss: position vega loss > 30% of vega received

**Position sizing:**
- Vega-neutral at index level: `SPX_vega_sold = Σ constituent_vega_bought`
- Requires minimum ~$100K capital for meaningful notional; backtest should acknowledge this constraint

**Data Requirements:**

| Field | Source | Frequency | Lookback |
|-------|--------|-----------|----------|
| SPX/SPY ATM IV | Polygon or CBOE | Daily | 3 years |
| Top-50 S&P 500 constituents ATM IV | Polygon options chain | Daily | 3 years |
| S&P 500 constituent weights | SPDR holdings file (SPY) | Monthly | 3 years |
| Underlying prices (all components) | yfinance | Daily | 3 years |
| VIX | yfinance | Daily | 3 years |

> **Backtest feasibility note:** True dispersion backtesting requires simultaneous IV data for 20–50 names per day over years of history. This is currently impossible with free data sources. The simulation framework below is the realistic alternative for Phase 4 development.

**Parameters to Optimize:**

| Parameter | Range | Default | Step |
|-----------|-------|---------|------|
| Implied corr threshold | 0.05–0.20 | 0.10 | 0.05 |
| Number of constituents (N) | 5–20 | 10 | 5 |
| DTE at entry | 21–45 | 30 | 7 |
| VIX cap for entry | 20–30 | 25 | 5 |
| Stop-loss vega % | 20–40 | 30 | 10 |

**Metrics to Track:**
- Correlation P&L: `(ρ_impl_entry - ρ_real_hold_period) × vega_exposure`
- Vega P&L decomposition: index leg vs. constituent legs
- Implied vs. realized correlation spread over time (track as a time series)
- Basis risk: deviation between index vol and weighted constituent vol
- Sharpe ratio per trade cohort (by entry implied correlation spread)

**Walk-Forward Config:**
- Train/test split: 60/40 (more test data needed due to strategy's low trade frequency)
- Optimization target: Sharpe ratio
- Overfit detection: minimum 30 trades in test period required to declare result valid; if fewer, flag as "insufficient test data"
- Cross-validation: use 3 non-overlapping time periods and check consistency of optimal parameters

**Mock Data Generation (if live data unavailable):**

This strategy **requires a full simulation framework** — do not attempt to run it on real data until the data pipeline is built. Simulation approach:

1. Start with SPY realized returns from yfinance (genuine market data)
2. Compute realized correlation matrix for top-10 SPY holdings using `yfinance` (free, available now)
3. Generate synthetic implied correlation as: `ρ_impl_t = ρ_real_t + corr_premium_t`
   ```
   corr_premium_t = μ_corr + φ × corr_premium_{t-1} + ε_t
   μ_corr = 0.08, φ = 0.85, ε ~ N(0, 0.02²)
   ```
4. Synthesize individual constituent IVs: `IV_i = RV_i + vrp_i` (same VRP model as iv_rv_gap)
5. Enforce consistency: `σ_index_impl² = Σ_i Σ_j w_i w_j ρ_impl σ_i σ_j`

Key property: simulated implied correlation must be higher than realized correlation on 60%+ of days.

**Implementation Notes:**
- **Reuse:** `backtester.py:black_scholes_call/put()`, `backtester.py:calculate_metrics()`
- **New modules needed:**
  - `modules/correlation_engine.py`: implied/realized correlation computation, dispersion signal generator
  - `modules/multi_leg_backtester.py`: simultaneous multi-symbol position management (the existing `run_backtest` handles one instrument at a time)
  - `modules/index_weights.py`: parse and cache SPY/QQQ holding weights
- **Estimated complexity:** ~1200 lines of new code, 10–14 dev days. Multi-leg position management and correlation accounting are the primary challenges.

---

## Strategy: Event Vol Strangle
### Backtest ID: `event_vol_strangle`

**Signal Logic:**

Before known binary events (earnings, FDA decisions, macro), the market prices an "expected move" into options. The strategy compares the options-implied expected move to a model-predicted move.

**Implied expected move:**

$$EM_{impl} = \frac{ATM\_call_{1DTE} + ATM\_put_{1DTE}}{S_0}$$

(straddle price as a fraction of spot)

**Historical expected move (model):**

$$EM_{hist} = \text{median}\left(\left|\frac{S_{t+1} - S_t}{S_t}\right|\right)\ \text{over prior } N \text{ earnings}$$

**Entry — Sell Strangle (overpriced event vol):**
1. `EM_impl / EM_hist > sell_threshold` (e.g., > 1.25: implied move is 25% larger than historical average)
2. Enter 1 DTE before event (close of trading)
3. Sell OTM strangle: call at `S × (1 + EM_impl × 0.6)`, put at `S × (1 - EM_impl × 0.6)`

**Entry — Buy Straddle (underpriced event vol):**
1. `EM_impl / EM_hist < buy_threshold` (e.g., < 0.75)
2. Enter 2 DTE before event
3. Buy ATM straddle

**Exit conditions:**
- Both legs: exit at close on event day (day after earnings announcement)
- Stop-loss: 50% of premium received (sell) or 50% of premium paid (buy)
- Never hold through weekend if expiry crosses

**Position sizing:**
- Fixed risk: max loss per trade = `capital × position_size_pct / 100`
- For short strangle: max loss = credit received (full loss if stock gaps through both strikes); size so full loss ≤ risk budget
- For long straddle: max loss = debit paid; size to debit ≤ risk budget

**Data Requirements:**

| Field | Source | Frequency | Lookback |
|-------|--------|-----------|----------|
| Earnings calendar | yfinance (`calendar`) or Polygon earnings | Per-event | 3 years |
| ATM IV (1-2 DTE) | Polygon options chain | Daily snapshot pre-event | 3 years |
| Post-event close (day+1) | yfinance | Daily | 3 years |
| Historical earnings moves (per ticker) | yfinance (compute from OHLC) | Per-event | 5 years |
| VIX | yfinance (`^VIX`) | Daily | 3 years |

**Parameters to Optimize:**

| Parameter | Range | Default | Step |
|-----------|-------|---------|------|
| Sell threshold (EM_impl/EM_hist) | 1.10–1.50 | 1.25 | 0.05 |
| Buy threshold (EM_impl/EM_hist) | 0.60–0.90 | 0.75 | 0.05 |
| Historical earnings lookback (events) | 4–12 | 8 | 2 |
| OTM strangle offset multiplier | 0.5–0.8 | 0.6 | 0.1 |
| Stop-loss % of premium | 30–70 | 50 | 10 |
| Position size % | 2–8 | 4 | 2 |

**Metrics to Track:**
- Edge ratio: `EM_impl / EM_hist` distribution at entry (confirm systematic overpricing)
- P&L by direction (sell vs. buy events)
- P&L by earnings surprise magnitude (quartile bucketing)
- Theta collected vs. gamma realized
- Win rate separately for sell and buy trades
- Average holding period in hours (not days — this is a 24–48h strategy)
- VIX level at event entry (performance by VIX regime)

**Walk-Forward Config:**
- Train/test split: 70/30 (by time, not by event count)
- Minimum events per symbol for parameter optimization: 6 earnings cycles
- Optimization target: Sharpe ratio on sell trades independently, buy trades independently
- Overfit detection: test win rate must be within ±20 percentage points of train win rate; edge ratio threshold must produce ≥ 15 trades in test period

**Mock Data Generation (if live data unavailable):**

Earnings IV data is the critical missing piece (1–2 DTE options). Use this generation approach:

1. Pull 5 years of post-earnings moves for S&P 500 components from yfinance (day-after close change) — **this is free and available today**
2. For each historical event, generate a synthetic IV:
   ```
   IV_event = abs(actual_move) × overpricing_factor + noise
   overpricing_factor ~ LogNormal(μ=0.15, σ=0.10)  # 15% average overpricing
   noise ~ N(0, 0.005)
   ```
3. Straddle price: `premium = IV_event × S × sqrt(1/252)` (1 DTE approximation)
4. Post-event move: use actual historical earnings moves (no simulation needed)

Key property: `EM_impl > EM_actual` on ~55–60% of events (well-documented for large-cap equities).

**Implementation Notes:**
- **Reuse:** `backtester.py:black_scholes_call/put()`, `backtester.py:calculate_metrics()`, `backtester.py:walk_forward_optimization()` structure
- **New modules needed:**
  - `modules/earnings_calendar.py`: fetch and cache earnings dates; compute historical per-ticker move distribution
  - `modules/event_vol_pricer.py`: compute `EM_impl`, `EM_hist`, ratio, signal generation
- **Estimated complexity:** ~400 lines of new code, 3–4 dev days. Earnings calendar is the key dependency; yfinance `.calendar` attribute is unreliable — Polygon or a dedicated source is more robust.

---

## Strategy: Term Structure Carry
### Backtest ID: `term_structure_carry`

**Signal Logic:**

VIX futures exhibit persistent contango (front < back). The strategy harvests this roll yield by being short front-month VIX futures (via VXX short or SVXY long as proxies) when contango is steep.

**Contango ratio:**

$$CR = \frac{F_{M2}}{F_{M1}} - 1$$

where `F_M1` = front-month VIX futures settlement, `F_M2` = second-month VIX futures settlement.

**Entry — Short volatility (harvest carry):**
1. `CR > contango_threshold` (default 5%, i.e. M2 is 5% above M1)
2. VIX spot < 20 (low-vol regime)
3. VIX spot > M1 futures price (no backwardation)

**Entry — Long volatility (protect tail risk):**
1. `CR < 0` (backwardation: VIX futures in contango collapse)
2. VIX spot rising > 15% over 5 days
3. This is a defensive hedge, not a primary trade

**Exit conditions:**
- Weekly roll: close position on expiry Friday, re-evaluate Monday
- Emergency exit: VIX spot rises > `vix_spike_pct` (default 20%) in a single day
- Regular stop: position loss > `stop_loss_pct` (default 15%) of position value

**Position sizing:**
- Kelly-scaled to contango steepness: `size = base_size × min(CR / target_CR, 2.0)`
- Hard cap: never exceed 20% of capital in this strategy (tail risk constraint)
- Exposure via SVXY or `-1× VXX` ETF position (not raw futures in Phase 2)

**Data Requirements:**

| Field | Source | Frequency | Lookback |
|-------|--------|-----------|----------|
| VIX spot | yfinance (`^VIX`) | Daily | 5 years |
| VXX (front-month proxy) | yfinance (`VXX`) | Daily | 5 years |
| SVXY (inverse VIX ETP) | yfinance (`SVXY`) | Daily | 5 years |
| VIX futures (M1, M2) | CBOE futures data or Quandl | Daily | 5 years |
| SPY (regime reference) | yfinance | Daily | 5 years |

> **Note:** Raw VIX futures data requires CBOE subscription or Quandl `CHRIS/CBOE_VX` (historical only). As a proxy, use VXX/SVXY which directly embed roll yield. Test both approaches and compare.

**Parameters to Optimize:**

| Parameter | Range | Default | Step |
|-----------|-------|---------|------|
| Contango threshold (%) | 2–10 | 5 | 1 |
| VIX spot cap for entry | 15–25 | 20 | 2.5 |
| VIX spike emergency exit (%) | 10–30 | 20 | 5 |
| Stop-loss % | 10–25 | 15 | 5 |
| Position size cap (% capital) | 10–25 | 20 | 5 |
| Hold period (days before re-evaluation) | 5–15 | 7 | 5 |

**Metrics to Track:**
- Roll yield captured: `Σ (entry_price - exit_price) / entry_price × 100%` per roll
- Contango ratio at each entry (distribution)
- Max single-day loss (spike risk measure)
- Calmar ratio: annualized return / max drawdown (critical for this tail-risk strategy)
- Correlation of daily returns with SPY (should be negative in stress periods)
- VIX regime at entry: breakdown of entries by VIX quintile
- Time-in-market: % of trading days with an open position

**Walk-Forward Config:**
- Train/test split: 70/30
- Minimum train period: 3 years (must include at least one vol spike event, e.g., Feb 2018, March 2020, Aug 2024)
- Optimization target: Calmar ratio (not Sharpe — tail risk is asymmetric)
- Overfit detection: test Calmar ratio ≥ 40% of train Calmar ratio; if test period includes a spike event, max drawdown on test must be < 3× train max drawdown

**Mock Data Generation (if live data unavailable):**

VXX and SVXY data are available directly from yfinance (no mock needed for these). For raw VIX futures simulation:

1. Generate `F_M1_t = VIX_t + premium_1_t` where `premium_1_t ~ N(0.5, 0.3²)` (M1 slight premium)
2. Generate `F_M2_t = F_M1_t + contango_t` where `contango_t ~ LogNormal(μ=0.05, σ=0.03²)` clipped at 0 when `VIX > 25`
3. Inject 3–4 vol spike events per simulated year: VIX jumps `U(30%, 80%)` over 1–5 days, then mean-reverts with half-life 10 days
4. Key property: contango must be positive on ~70% of simulated days; backwardation events cluster around spike periods

**Implementation Notes:**
- **Reuse:** `backtester.py:calculate_metrics()`, `backtester.py:walk_forward_optimization()`, `backtester.py:run_backtest()` loop (modify for ETF-based positions rather than options)
- **New modules needed:**
  - `modules/term_structure.py`: fetch VIX futures or ETF proxy data; compute contango ratio; signal generation
  - Minor modification to `run_backtest()`: add ETF long/short position type alongside existing options types
- **Estimated complexity:** ~300 lines of new code, 2–3 dev days. ETF proxy approach (VXX/SVXY) is buildable today with yfinance alone; raw futures path adds 1–2 days of data engineering.

---

## Strategy: Pinning / 0DTE Dynamics
### Backtest ID: `pinning_0dte`

**Signal Logic:**

On expiration day, large open interest (OI) concentrations at specific strikes create "gravity" as dealers delta-hedge. The strategy identifies the gravitational strike and trades toward it.

**Max pain calculation:**

$$\text{MaxPain} = \arg\min_K \sum_{\text{all strikes}} \left[OI_{call}(K_i) \cdot \max(0, K - K_i) + OI_{put}(K_i) \cdot \max(0, K_i - K)\right]$$

**GEX pin level:** strike with largest net gamma concentration (separate from max pain — the pin strike is where dealer hedging creates maximum friction).

**Entry — Pinning trade (fade away from pin):**
1. On 0DTE expiration morning (09:35 ET)
2. `|S_open - pin_strike| < pin_proximity_pct × S_open` (price near pin)
3. If price moved away from pin on open, fade the move (bet on return to pin)
4. Signal: BUY_CALL if price below pin, BUY_PUT if price above pin

**Entry — Pin break trade (breakout if pin fails):**
1. Price moves > `pin_break_pct` away from pin after 11:00 ET
2. Negative GEX regime (from dealer_gamma_regime if available)
3. Signal: follow the break direction

**Exit conditions:**
- Both strategies: hard 14:00 ET exit (avoid end-of-day gamma explosion risk)
- Stop: 0.3% adverse move from entry

**Position sizing:**
- 0DTE options decay very rapidly; use maximum 2% capital per trade
- Prefer long options (not spreads) on 0DTE to keep execution simple

**Data Requirements:**

| Field | Source | Frequency | Lookback |
|-------|--------|-----------|----------|
| 0DTE options OI by strike | Polygon options chain | Intraday (morning snapshot) | 1 year |
| SPX/SPY intraday prices | yfinance (1m or 5m) or Polygon | Intraday | 1 year |
| 0DTE options prices (ATM) | Polygon options chain | Intraday | 1 year |
| GEX by strike (optional) | SpotGamma | Daily snapshot | 1 year |

> **Data availability note:** Intraday 0DTE options data (strikes, OI, prices) requires Polygon's Options Snapshot endpoint. Free tier has rate limits that make historical simulation slow but feasible. Backfilling 1 year of 0DTE data will require ~200–250 API calls (one per expiration day).

**Parameters to Optimize:**

| Parameter | Range | Default | Step |
|-----------|-------|---------|------|
| Pin proximity % | 0.1–0.5 | 0.25 | 0.05 |
| Pin break % (exit from pin gravity) | 0.3–1.0 | 0.6 | 0.1 |
| Hard exit time (ET) | 13:00–15:00 | 14:00 | 30 min |
| Stop-loss % | 0.2–0.6 | 0.3 | 0.1 |
| Position size % | 1–4 | 2 | 1 |

**Metrics to Track:**
- Pin accuracy: % of expiration days where final close was within 0.5% of max pain strike
- Conditional win rate: win rate when entered within `pin_proximity_pct` vs. further out
- Average distance from pin at entry and at exit
- Intraday path: classify each expiry as "pin day" (price oscillates near pin) vs. "break day" (pin fails)
- Trade duration in minutes (not days)
- P&L by time of entry (bucket into 9:30–10:00, 10:00–11:00, 11:00–13:00)

**Walk-Forward Config:**
- Train/test split: 70/30 by number of expiration events (not calendar time)
- Minimum train expiry days: 60 (about 3 months of weekly expirations)
- Optimization target: Sharpe ratio
- Overfit detection: pin accuracy on test ≥ 50% (random would be ~50%, so this is a low bar; require > 55%); test Sharpe ≥ 50% of train Sharpe

**Mock Data Generation (if live data unavailable):**

1. Simulate the pinning effect directly:
   ```
   On each expiry day:
   - Draw pin_strike from prior day's max OI concentration (use rounded SPY/SPX strike)
   - Morning open: S_open = pin_strike + N(0, σ_open²), σ_open = 0.003 × S
   - Intraday path: Ornstein-Uhlenbeck process around pin_strike
     dS = κ(pin_strike - S)dt + σ_intraday dW
     κ = 2.5 (mean-reversion speed), σ_intraday = 0.002/sqrt(hour)
   - Pin failure (30% of days): κ drops to 0.1 and process trends away
   ```
2. Key property: final close within 0.25% of pin_strike on ~55% of days (consistent with empirical SPX expiration data)
3. OI mock: place 60% of total OI at the ATM strike ± 2 strikes, distribute remainder uniformly

**Implementation Notes:**
- **Reuse:** `backtester.py:black_scholes_call/put()`, `backtester.py:calculate_metrics()`
- **New modules needed:**
  - `modules/max_pain.py`: compute max pain and GEX-based pin strike from OI data; requires intraday Polygon options snapshot
  - `modules/intraday_backtester.py`: new backtesting loop at minute/5-minute resolution (existing `run_backtest` is daily only)
- **Estimated complexity:** ~700 lines of new code, 5–7 dev days. The intraday backtester is the largest new component and will be reusable by the `dealer_gamma_regime` strategy.

---

## Strategy: Vol Risk Premium Harvest
### Backtest ID: `vrp_harvest`

**Signal Logic:**

This is a disciplined, filtered version of the IV-RV gap strategy (`iv_rv_gap`) focused specifically on systematic premium selling.

**Core filter stack (all must pass for a sell signal):**
1. `IV_atm - RV_20 > vrp_min_spread` (default 4 vol points — IV premium is meaningful)
2. `IV_atm / VIX < iv_percentile_cap` (IV is not in top decile of its own history — no crisis selling)
3. VIX < 25 (macro regime not elevated)
4. `SKEW_index < skew_cap` (default: CBOE SKEW < 135 — tail risk not extreme)
5. No open position in the same symbol

**Signal types:**
- If all 5 filters pass: sell ATM straddle (most aggressive) or sell 20-delta strangle (default)
- If filters 1–4 pass but not 5: skip (existing position management)

**Exit conditions:**
- Primary: take profit at 50% of max credit (standard theta target)
- Secondary: roll at 21 DTE — close and reopen 45 DTE
- Stop-loss: position loss reaches 2× credit received
- Regime stop: VIX crosses above 30 → close all short premium positions immediately

**Position sizing:**
- Maximum margin per trade: `capital × margin_pct / 100` (default 5%)
- Adjust by IV percentile: lower size when IV is elevated (more tail risk)
- `size_scalar = 1.0 - max(0, (IV_atm - IV_50th_pct) / (IV_90th_pct - IV_50th_pct))`

**Data Requirements:**

| Field | Source | Frequency | Lookback |
|-------|--------|-----------|----------|
| ATM IV (20–45 DTE) | Polygon options chain | Daily | 2 years |
| Realized vol (20-day) | yfinance (compute) | Daily | 2 years |
| VIX spot | yfinance (`^VIX`) | Daily | 2 years |
| CBOE SKEW index | yfinance (`^SKEW`) | Daily | 2 years |
| IV percentile history | Computed from IV time series | Daily (rolling) | 2 years |

**Parameters to Optimize:**

| Parameter | Range | Default | Step |
|-----------|-------|---------|------|
| VRP minimum spread (vol pts) | 2–8 | 4 | 1 |
| VIX cap for entry | 20–30 | 25 | 2.5 |
| SKEW cap for entry | 125–145 | 135 | 5 |
| Profit take % of credit | 30–60 | 50 | 10 |
| Stop-loss multiplier | 1.5–3.0 | 2.0 | 0.5 |
| IV percentile lookback (days) | 126–504 | 252 | 63 |
| Position size % | 2–8 | 5 | 1 |

**Metrics to Track:**
- VRP captured per trade: `credit_received - cost_to_close`
- Filter hit rate: % of days each filter is active (to measure filter restrictiveness)
- Sharpe ratio
- Maximum drawdown
- Crisis exposure: number of trades open when VIX > 30 (should be zero with correct filter)
- IV percentile at entry (distribution should cluster in 40th–70th percentile)
- Theta decay rate: P&L per DTE elapsed

**Walk-Forward Config:**
- Train/test split: 70/30
- Optimization target: Sharpe ratio
- Secondary objective: minimize max drawdown
- Overfit detection: test Sharpe ≥ 50% of train Sharpe; test max drawdown ≤ 2× train max drawdown (critical — overfitted filter stacks can catastrophically fail in test)
- Regime stress test: ensure test period contains at least one VIX > 25 episode

**Mock Data Generation (if live data unavailable):**

This strategy shares the IV generation model with `iv_rv_gap`. Extend the VRP simulation:
1. Generate IV time series (same as `iv_rv_gap` mock data section)
2. Generate SKEW index: `SKEW_t = 100 + 30 × β_t` where `β_t` is left-tail skewness factor
   ```
   β_t = 0.85 × β_{t-1} + N(0, 0.1²)
   SKEW_t clipped to [100, 160]
   ```
3. Inject correlation between VIX and SKEW: `corr(VIX, SKEW) ≈ 0.65`
4. Key property: all 5 filters pass simultaneously on ~30–40% of trading days (historically observed for large-cap single stocks)

**Implementation Notes:**
- **Reuse:** `backtester.py` entirely (this is the closest strategy to the existing engine), `modules/vol_calculator.py` from `iv_rv_gap`
- **New modules needed:**
  - `modules/vrp_filters.py`: the 5-filter stack; IV percentile calculator; SKEW fetch/normalize
  - Minor extension of `run_backtest()`: add SELL_STRADDLE / SELL_STRANGLE position types
- **Estimated complexity:** ~250 lines of new code, 1–2 dev days. This is the lowest-effort high-impact extension after `iv_rv_gap`.

---

## Strategy: Cross-Asset Signal Fusion
### Backtest ID: `cross_asset_fusion`

**Signal Logic:**

A macro overlay that classifies the market into one of three regimes and applies regime-specific filters to all other Enso strategies.

**Regime definition:**

| Regime | Conditions | Strategy bias |
|--------|------------|---------------|
| Risk-On | VIX < 18, CDX.IG spread < 60bp, MOVE < 90, no yield curve inversion | Full position size, all strategies active |
| Transition | Any single stress signal breached | Reduce position size to 50%, no new short-vol trades |
| Risk-Off | 2+ stress signals breached, or VIX > 30 | Close all short-vol, long-vol only, reduce position size to 25% |

**Signals used:**
- `VIX_z`: `(VIX_t - VIX_20d_mean) / VIX_20d_std` — equity vol z-score
- `CDX_IG_z`: `(CDX_t - CDX_20d_mean) / CDX_20d_std` — investment-grade credit spread z-score
- `MOVE_z`: `(MOVE_t - MOVE_20d_mean) / MOVE_20d_std` — rate vol z-score
- `MACRO_SURPRISE`: Citigroup Economic Surprise Index (CESI) directional change
- `YIELD_CURVE`: 10Y-2Y spread sign

**Composite stress score:**

$$\text{StressScore} = w_1 \cdot VIX\_z + w_2 \cdot CDX\_z + w_3 \cdot MOVE\_z - w_4 \cdot \text{sign}(CESI\_\Delta)$$

Default weights: `(0.35, 0.30, 0.20, 0.15)`

**Regime transitions:**
- Enter Risk-Off: StressScore > 2.0 for 2 consecutive days
- Enter Risk-On: StressScore < 0.5 for 3 consecutive days
- Transition: intermediate values

**Data Requirements:**

| Field | Source | Frequency | Lookback |
|-------|--------|-----------|----------|
| VIX | yfinance (`^VIX`) | Daily | 5 years |
| MOVE index | yfinance (`^MOVE`) or FRED | Daily | 5 years |
| CDX.IG 5Y | Bloomberg (paid) or Markit approximations | Daily | 5 years |
| Citigroup CESI | FRED or Quandl | Weekly | 5 years |
| 10Y-2Y Yield spread | FRED (T10Y2Y) | Daily | 5 years |
| SPY (reference) | yfinance | Daily | 5 years |

> **Data availability note:** CDX.IG is the hardest data point — it requires Bloomberg or a credit data subscription. As a free proxy, use HYG/LQD spread or the ICE BofA credit spread indices available on FRED. CESI is available via FRED series `USEPUINDXM` or via alternative data providers.

**Parameters to Optimize:**

| Parameter | Range | Default | Step |
|-----------|-------|---------|------|
| Risk-off threshold (StressScore) | 1.5–3.0 | 2.0 | 0.25 |
| Risk-on threshold (StressScore) | 0.0–1.0 | 0.5 | 0.25 |
| Risk-off confirmation days | 1–3 | 2 | 1 |
| Weight w1 (VIX) | 0.20–0.50 | 0.35 | 0.05 |
| Weight w2 (CDX) | 0.15–0.45 | 0.30 | 0.05 |
| Z-score lookback window | 10–30 | 20 | 5 |
| Transition position scalar | 0.3–0.7 | 0.5 | 0.1 |

**Metrics to Track:**
- Regime accuracy: % of regime transitions that correctly preceded a vol event within 5 days
- Overlay value-add: compare portfolio Sharpe with vs. without regime overlay applied
- Average regime duration (days per regime)
- Regime transition lead time: how many days before a VIX spike did regime shift to Risk-Off
- False positive rate: Risk-Off entries that resolved without a vol event
- Correlation of StressScore with future 10-day SPY returns

**Walk-Forward Config:**
- Train/test split: 60/40 (more test data needed — regime shifts are rare events)
- Optimization target: overlay value-add (Sharpe improvement) rather than standalone Sharpe
- Overfit detection: regime transition accuracy must be > 55% on both train and test; false positive rate must be < 40% on test
- Stress test: test period must include at least one Risk-Off episode; if not, extend test window

**Mock Data Generation (if live data unavailable):**

CDX.IG is currently the blocking data source. Free proxy approach:

1. Use FRED `BAMLC0A0CM` (ICE BofA US Corporate OAS) as CDX.IG proxy — **free and high quality**
2. Use FRED `T10Y2Y` for yield curve — **free**
3. Use `^MOVE` from yfinance (if unavailable, proxy with 10Y Treasury yield daily change × 50)
4. Generate synthetic CESI: `CESI_t = 0.7 × CESI_{t-1} + N(0, 15²)`; surprise events: every 30 days, inject a ±30 point shock
5. Key property: stress events (StressScore > 2) should cluster — autocorrelation at lag-1 must be > 0.7 during stress periods

**Implementation Notes:**
- **Reuse:** `backtester.py:calculate_metrics()`, `backtester.py:walk_forward_optimization()` structure
- **New modules needed:**
  - `modules/macro_regime.py`: multi-source data fetch (FRED, yfinance); z-score computation; StressScore; regime classifier
  - `modules/regime_overlay.py`: applies regime scalar to any strategy's position sizing (overlay architecture, not standalone)
  - `modules/fred_client.py`: thin FRED API client (free API key, no subscription)
- **Estimated complexity:** ~500 lines of new code, 4–5 dev days. The overlay architecture (plugging into other strategies) is the design challenge, not the math.

---

## Strategy: S/R + Vol Filter Overlay
### Backtest ID: `sr_vol_filter`

**Signal Logic:**

This is the live production strategy in Enso. The spec describes the upgrade to add vol-context filters to the existing S/R signals.

**Existing logic (unchanged):**
- `find_pivots()` → support/resistance levels
- `score_confluence()` → 4-factor score (proximity 30%, volume 25%, trend 25%, retest 20%)
- Entry: BUY_CALL at support, BUY_PUT at resistance if `confluence_total >= min_confluence`

**New vol filter (additions only):**

1. **IV-RV direction filter:** Only enter if IV-RV direction aligns with S/R type:
   - At support (BUY_CALL): IV-RV > 0 is tolerable (selling premium would be better but directional call is ok); IV-RV < -0.05 (IV very cheap) → flag as "premium buy opportunity" — adjust position toward straddle
   - At resistance (BUY_PUT): same logic inverted

2. **IV percentile filter:** Block entries when `IV_pct > 80th_percentile` (crisis mode — options too expensive for directional debit trade)

3. **Skew direction filter:**
   - At resistance (expect move down): if put skew > `skew_threshold` (puts already expensive), reduce position size by 50%
   - At support (expect move up): if call skew > `skew_threshold` (calls expensive relative to puts), flag and reduce size

**Updated confluence formula:**

$$\text{TotalScore} = 0.30 \cdot P + 0.25 \cdot V + 0.25 \cdot T + 0.20 \cdot R - 0.15 \cdot \text{VolPenalty}$$

`VolPenalty = max(0, IV_pct - 0.6) × 100` (0 when IV is below 60th percentile, up to 40 penalty points)

**Exit conditions:** unchanged from current production (option expiry, fixed DTE)

**Position sizing:** unchanged from production; vol filter only gates entry / adjusts size, does not change exit logic

**Data Requirements:**

| Field | Source | Frequency | Lookback |
|-------|--------|-----------|----------|
| Close, High, Low, Volume | yfinance (already integrated) | Daily | As current |
| ATM IV | Polygon options chain (new) | Daily | 252 days (for percentile) |
| RV (20-day) | Compute from yfinance Close | Daily | 20 days |
| Put/call skew | Polygon options chain (new) | Daily | 252 days |

**Parameters to Optimize:**

| Parameter | Range | Default | Step |
|-----------|-------|---------|------|
| Proximity threshold % | 0.5–3.0 | 1.5 | 0.25 |
| Min confluence score | 30–60 | 40 | 5 |
| IV percentile cap | 70–90 | 80 | 5 |
| Skew threshold (vol pts) | 3–10 | 5 | 1 |
| Vol penalty weight | 0.05–0.25 | 0.15 | 0.05 |
| Option expiry weeks | 2–6 | 3 | 1 |

**Metrics to Track:**
- All 13 existing metrics from `calculate_metrics()` (unchanged)
- New: win rate split by vol filter active / inactive (measure the filter's contribution)
- IV percentile at entry distribution
- Skew at entry for winning vs. losing trades
- Confluence score distribution with vs. without vol penalty term
- Side-by-side comparison: baseline (no vol filter) vs. upgraded (vol filter) on same test period

**Walk-Forward Config:**
- Train/test split: 70/30 (matches existing `WALK_FORWARD_TRAIN_RATIO`)
- Optimization target: Sharpe ratio (same as existing `walk_forward_optimization`)
- Overfit detection: existing criteria (test Sharpe ≥ 50% of train Sharpe = ROBUST)
- New comparison: run `walk_forward_optimization` on both baseline and upgraded version; report delta in test Sharpe as "vol filter value-add"

**Mock Data Generation (if live data unavailable):**

The underlying S/R backtest already works with yfinance data (no mock needed for the base case). For the vol filter extension:
1. Use `estimate_iv()` from `backtester.py` as a synthetic IV proxy — already implemented
2. For IV percentile, compute rolling 252-day percentile of the synthetic IV series
3. For skew, generate synthetic skew as: `skew_t = 0.03 + 0.7 × skew_{t-1} + N(0, 0.005²)`, representing put-call IV differential

Key property: synthetic IV must be correlated with VIX (r ≥ 0.80) and must be right-skewed.

**Implementation Notes:**
- **Reuse:** `sr_engine.py:find_pivots()`, `sr_engine.py:score_confluence()` (extend — do not replace), `backtester.py:run_backtest()` (minor modification to pass vol_filter flag), `backtester.py:calculate_metrics()`, `backtester.py:walk_forward_optimization()`
- **New modules needed:**
  - `modules/vol_filter.py`: IV percentile calculator, skew fetcher, vol penalty computation — pure functions, no side effects
  - Modify `score_confluence()` to accept optional `vol_penalty` argument (backward-compatible default: 0)
  - Modify `run_backtest()` signature: add `use_vol_filter: bool = False` flag
- **Estimated complexity:** ~200 lines of new code, 1–2 dev days. This is the simplest high-value addition — build this first before any other strategy to validate the vol filter concept before applying it more broadly.

---

## Appendix: Shared Infrastructure Notes

### Module dependency map

```
iv_rv_gap          → vol_calculator.py (new), iv_fetcher.py (new)
dealer_gamma_regime → gex_engine.py (new), regime_classifier.py (new), intraday_backtester.py (new)
skew_surface        → vol_surface.py (new), greeks_engine.py (new), delta_hedger.py (new)
dispersion_correlation → correlation_engine.py (new), multi_leg_backtester.py (new)
event_vol_strangle  → earnings_calendar.py (new), event_vol_pricer.py (new)
term_structure_carry → term_structure.py (new)
pinning_0dte        → max_pain.py (new), intraday_backtester.py (shared with dealer_gamma)
vrp_harvest         → vrp_filters.py (new), vol_calculator.py (shared with iv_rv_gap)
cross_asset_fusion  → macro_regime.py (new), regime_overlay.py (new), fred_client.py (new)
sr_vol_filter       → vol_filter.py (new), extends sr_engine.py + backtester.py
```

### Shared modules (build once, use everywhere)

| Module | Used by | Notes |
|--------|---------|-------|
| `vol_calculator.py` | iv_rv_gap, vrp_harvest | RV computation, IV percentile |
| `intraday_backtester.py` | dealer_gamma_regime, pinning_0dte | New event-loop at minute resolution |
| `regime_classifier.py` | dealer_gamma_regime, cross_asset_fusion | Generalize for reuse |
| `greeks_engine.py` | skew_surface, dispersion, pinning_0dte | Full Greeks beyond BS call/put |

### Walk-forward parameter summary (all strategies)

| Strategy | Train ratio | Min train bars | Opt target | Overfit threshold |
|----------|-------------|----------------|------------|-------------------|
| iv_rv_gap | 70% | 252 | Sharpe | Test ≥ 50% train |
| dealer_gamma_regime | 70% | 504 | Sharpe per regime | Regime accuracy test vs train |
| skew_surface | 70% | 252 | Sharpe (vega P&L) | RMSE ratio ≤ 1.5× |
| dispersion_correlation | 60% | 504 | Sharpe | Min 30 test trades |
| event_vol_strangle | 70% | 252 | Sharpe (by direction) | WR within ±20pp |
| term_structure_carry | 70% | 756 | Calmar | Test Calmar ≥ 40% train |
| pinning_0dte | 70% | 60 expirations | Sharpe | Pin accuracy > 55% |
| vrp_harvest | 70% | 252 | Sharpe | Test DD ≤ 2× train DD |
| cross_asset_fusion | 60% | 1260 | Overlay value-add | FPR < 40% on test |
| sr_vol_filter | 70% | 252 | Sharpe | Test ≥ 50% train (existing) |
