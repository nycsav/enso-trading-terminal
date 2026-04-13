"""
Strategy Engines — Extended Backtesting Strategies
Provides 6 additional backtesting strategies for the Enso Trading Terminal:
  1. IV vs RV Gap Monitor         (run_iv_rv_backtest)
  2. Event Vol Strangle           (run_event_vol_backtest)
  3. Vol Risk Premium Harvest     (run_vrp_backtest)
  4. S/R + Vol Filter Overlay     (run_sr_vol_backtest)
  5. Term Structure Carry         (run_term_carry_backtest)
  6. Cross-Asset Momentum         (run_cross_asset_backtest)

All functions share the same signature pattern and return structure as run_backtest().
"""

import pandas as pd
import numpy as np
from datetime import timedelta

from modules.backtester import (
    black_scholes_call,
    black_scholes_put,
    estimate_iv,
    compute_iv_rank,
    calculate_metrics,
)
from modules.sr_engine import find_pivots, score_confluence
from config import (
    DEFAULT_CAPITAL,
    DEFAULT_POSITION_SIZE_PCT,
    DEFAULT_OPTION_EXPIRY_WEEKS,
    STOP_LOSS_PCT,
    TAKE_PROFIT_PCT,
    MAX_EXPOSURE_PCT,
    OTM_OFFSET_PCT,
    IV_RANK_MAX,
)


# ── Helper utilities ──────────────────────────────────────────────────────────

def _fetch_vix(start=None, end=None) -> pd.Series:
    """Fetch VIX closing prices from yfinance. Returns a Series indexed by date."""
    try:
        import yfinance as yf
        vix = yf.Ticker("^VIX").history(start=start, end=end)
        if vix.empty:
            return pd.Series(dtype=float)
        return vix["Close"]
    except Exception:
        return pd.Series(dtype=float)


def _compute_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Compute RSI for a price series."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=window - 1, min_periods=window).mean()
    avg_loss = loss.ewm(com=window - 1, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _open_position(
    capital: float,
    position_size_pct: float,
    signal_type: str,
    current_price: float,
    current_date,
    option_expiry_weeks: int,
    iv: float,
    symbol: str,
    otm_offset_pct: float = OTM_OFFSET_PCT,
    extra_fields: dict = None,
) -> tuple:
    """
    Compute option parameters and build a position dict.
    Returns (position_dict, cost) or (None, 0) if position can't be opened.
    """
    max_cost = capital * (position_size_pct / 100)
    if max_cost <= 0:
        return None, 0

    T = option_expiry_weeks / 52
    if signal_type == "BUY_CALL":
        strike = current_price * (1 + otm_offset_pct / 100)
        premium = black_scholes_call(current_price, strike, T, sigma=iv)
    else:
        strike = current_price * (1 - otm_offset_pct / 100)
        premium = black_scholes_put(current_price, strike, T, sigma=iv)

    if premium <= 0.01:
        return None, 0

    contracts = max(1, int(max_cost / (premium * 100)))
    cost = contracts * premium * 100
    if cost > capital:
        return None, 0

    expiry_date = current_date + timedelta(weeks=option_expiry_weeks)
    pos = {
        "symbol": symbol,
        "type": signal_type,
        "entry_date": current_date,
        "entry_price": current_price,
        "strike": strike,
        "entry_premium": premium,
        "contracts": contracts,
        "cost": cost,
        "expiry_date": expiry_date,
        "confluence": 50.0,  # default; overridden by caller
    }
    if extra_fields:
        pos.update(extra_fields)
    return pos, cost


def _manage_positions(
    open_positions: list,
    current_date,
    current_price: float,
    iv: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    capital: float,
    trades: list,
) -> tuple:
    """
    Check each open position for exit conditions.
    Returns (still_open, updated_capital).
    """
    still_open = []
    for pos in open_positions:
        remaining_T = max(0.001, (pos["expiry_date"] - current_date).days / 365)
        if pos["type"] == "BUY_CALL":
            current_opt_val = black_scholes_call(current_price, pos["strike"], remaining_T, sigma=iv)
        else:
            current_opt_val = black_scholes_put(current_price, pos["strike"], remaining_T, sigma=iv)

        pnl_pct = (
            (current_opt_val - pos["entry_premium"]) / pos["entry_premium"] * 100
            if pos["entry_premium"] > 0 else 0
        )

        should_close = False
        close_reason = ""
        if current_date >= pos["expiry_date"]:
            should_close = True
            close_reason = "expired"
        elif pnl_pct <= -stop_loss_pct:
            should_close = True
            close_reason = "stop_loss"
        elif pnl_pct >= take_profit_pct:
            should_close = True
            close_reason = "take_profit"

        if should_close:
            if current_date >= pos["expiry_date"]:
                option_exit = (
                    black_scholes_call(current_price, pos["strike"], 0.001, sigma=iv)
                    if pos["type"] == "BUY_CALL"
                    else black_scholes_put(current_price, pos["strike"], 0.001, sigma=iv)
                )
            else:
                option_exit = current_opt_val

            pnl = (option_exit - pos["entry_premium"]) * pos["contracts"] * 100
            capital += pnl + pos["cost"]
            pos["exit_date"] = current_date
            pos["exit_price"] = current_price
            pos["exit_premium"] = option_exit
            pos["pnl"] = pnl
            pos["holding_days"] = (current_date - pos["entry_date"]).days
            pos["close_reason"] = close_reason
            trades.append(pos)
        else:
            still_open.append(pos)

    return still_open, capital


def _force_close_positions(
    open_positions: list,
    final_price: float,
    final_date,
    iv: float,
    capital: float,
    trades: list,
) -> float:
    """Force-close all remaining positions at end of backtest."""
    for pos in open_positions:
        if pos["type"] == "BUY_CALL":
            option_exit = black_scholes_call(final_price, pos["strike"], 0.001, sigma=iv)
        else:
            option_exit = black_scholes_put(final_price, pos["strike"], 0.001, sigma=iv)
        pnl = (option_exit - pos["entry_premium"]) * pos["contracts"] * 100
        capital += pnl + pos["cost"]
        pos["exit_date"] = final_date
        pos["exit_price"] = final_price
        pos["exit_premium"] = option_exit
        pos["pnl"] = pnl
        pos["holding_days"] = (final_date - pos["entry_date"]).days
        pos["close_reason"] = "force_close"
        trades.append(pos)
    return capital


# ── Strategy 1: IV vs RV Gap Monitor ─────────────────────────────────────────

def run_iv_rv_backtest(
    df: pd.DataFrame,
    symbol: str = "",
    starting_capital: float = DEFAULT_CAPITAL,
    position_size_pct: float = DEFAULT_POSITION_SIZE_PCT,
    option_expiry_weeks: int = DEFAULT_OPTION_EXPIRY_WEEKS,
    stop_loss_pct: float = STOP_LOSS_PCT,
    take_profit_pct: float = TAKE_PROFIT_PCT,
    iv_rv_threshold: float = 0.05,
    max_vix: float = 30.0,
    **kwargs,
) -> dict:
    """
    IV vs RV Gap Monitor.
    - Sell premium (BUY_PUT) when IV > RV + threshold (rich premium)
    - Buy premium  (BUY_CALL) when IV < RV - threshold (cheap vol)
    - Skip trades if VIX > max_vix.
    """
    if len(df) < 30:
        return {"error": "Insufficient data for IV/RV backtest (need 30+ bars)"}

    # Fetch VIX once for the whole period
    start_str = df.index[0].strftime("%Y-%m-%d") if hasattr(df.index[0], "strftime") else None
    end_str = df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], "strftime") else None
    vix_series = _fetch_vix(start=start_str, end=end_str)

    trades = []
    equity_curve = []
    capital = starting_capital
    open_positions = []
    iv = estimate_iv(df)

    returns = df["Close"].pct_change()

    for i in range(30, len(df)):
        current_date = df.index[i]
        current_price = float(df["Close"].iloc[i])

        # Manage open positions
        open_positions, capital = _manage_positions(
            open_positions, current_date, current_price, iv,
            stop_loss_pct, take_profit_pct, capital, trades
        )

        # 20-day realized vol (annualized)
        rv_slice = returns.iloc[i - 20:i].dropna()
        if len(rv_slice) < 10:
            equity_curve.append({"date": current_date, "equity": capital})
            continue
        rv = float(rv_slice.std() * np.sqrt(252))

        # Estimated IV from recent 20-bar window
        lookback_df = df.iloc[max(0, i - 20):i + 1].copy()
        iv_current = estimate_iv(lookback_df, window=min(20, len(lookback_df) - 1))

        # VIX regime filter
        vix_val = None
        if not vix_series.empty:
            # Find closest VIX date <= current_date
            vix_dates = vix_series.index
            # Handle timezone-naive vs timezone-aware mismatch
            try:
                past_vix = vix_series[vix_dates <= current_date]
            except TypeError:
                # Strip timezone info for comparison
                current_date_naive = current_date.replace(tzinfo=None) if hasattr(current_date, 'tzinfo') else current_date
                vix_dates_naive = vix_series.index.tz_localize(None) if vix_series.index.tz is not None else vix_series.index
                vix_series_naive = pd.Series(vix_series.values, index=vix_dates_naive)
                past_vix = vix_series_naive[vix_dates_naive <= current_date_naive]
            if not past_vix.empty:
                vix_val = float(past_vix.iloc[-1])

        if vix_val is not None and vix_val > max_vix:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        # Determine signal
        gap = iv_current - rv
        signal_type = None
        if gap > iv_rv_threshold:
            signal_type = "BUY_PUT"   # IV rich → sell premium
        elif gap < -iv_rv_threshold:
            signal_type = "BUY_CALL"  # IV cheap → buy premium

        if signal_type is None or open_positions:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        pos, cost = _open_position(
            capital, position_size_pct, signal_type, current_price,
            current_date, option_expiry_weeks, iv, symbol,
            extra_fields={"iv_rv_gap": round(gap, 4), "rv": round(rv, 4),
                          "iv_est": round(iv_current, 4), "confluence": abs(gap) * 100},
        )
        if pos:
            capital -= cost
            open_positions.append(pos)

        equity_curve.append({"date": current_date, "equity": capital})

    # Force-close
    final_price = float(df["Close"].iloc[-1])
    capital = _force_close_positions(open_positions, final_price, df.index[-1], iv, capital, trades)

    metrics = calculate_metrics(trades, starting_capital, equity_curve)
    return {
        "trades": trades,
        "metrics": metrics,
        "equity_curve": pd.DataFrame(equity_curve),
        "symbol": symbol,
        "strategy": "IV_RV_GAP",
        "parameters": {
            "iv_rv_threshold": iv_rv_threshold,
            "max_vix": max_vix,
            "option_expiry_weeks": option_expiry_weeks,
            "starting_capital": starting_capital,
            "position_size_pct": position_size_pct,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
        },
    }


# ── Strategy 2: Event Vol Strangle ────────────────────────────────────────────

def run_event_vol_backtest(
    df: pd.DataFrame,
    symbol: str = "",
    starting_capital: float = DEFAULT_CAPITAL,
    position_size_pct: float = DEFAULT_POSITION_SIZE_PCT,
    option_expiry_weeks: int = DEFAULT_OPTION_EXPIRY_WEEKS,
    stop_loss_pct: float = STOP_LOSS_PCT,
    take_profit_pct: float = TAKE_PROFIT_PCT,
    pre_event_days: int = 5,
    iv_rank_sell_threshold: float = 60.0,
    iv_rank_buy_threshold: float = 30.0,
    post_event_close_days: int = 2,
    **kwargs,
) -> dict:
    """
    Event Vol Strangle.
    Uses quarterly proxy earnings dates (every ~63 trading days).
    - If IV rank > sell_threshold in pre-event window: BUY_PUT (expecting IV crush)
    - If IV rank < buy_threshold in pre-event window: BUY_CALL (expecting vol expansion)
    - Closes position within post_event_close_days after event.
    """
    if len(df) < 80:
        return {"error": "Insufficient data for event vol backtest (need 80+ bars)"}

    # Build list of proxy earnings event indices (every ~63 trading days)
    event_indices = list(range(100, len(df), 63))
    if not event_indices:
        return {"error": "Not enough data for quarterly events"}

    trades = []
    equity_curve = []
    capital = starting_capital
    open_positions = []
    iv = estimate_iv(df)

    # Track which events we've acted on
    active_event_target_dates = {}  # event_idx -> close_target_date

    for i in range(30, len(df)):
        current_date = df.index[i]
        current_price = float(df["Close"].iloc[i])

        # Manage normal stop/tp exits
        open_positions, capital = _manage_positions(
            open_positions, current_date, current_price, iv,
            stop_loss_pct, take_profit_pct, capital, trades
        )

        # Check if we should force-close any event position post-event
        still_open = []
        for pos in open_positions:
            close_target = pos.get("event_close_target")
            if close_target is not None and current_date >= close_target:
                remaining_T = max(0.001, (pos["expiry_date"] - current_date).days / 365)
                if pos["type"] == "BUY_CALL":
                    option_exit = black_scholes_call(current_price, pos["strike"], remaining_T, sigma=iv)
                else:
                    option_exit = black_scholes_put(current_price, pos["strike"], remaining_T, sigma=iv)
                pnl = (option_exit - pos["entry_premium"]) * pos["contracts"] * 100
                capital += pnl + pos["cost"]
                pos["exit_date"] = current_date
                pos["exit_price"] = current_price
                pos["exit_premium"] = option_exit
                pos["pnl"] = pnl
                pos["holding_days"] = (current_date - pos["entry_date"]).days
                pos["close_reason"] = "post_event_close"
                trades.append(pos)
            else:
                still_open.append(pos)
        open_positions = still_open

        # Check if we're in a pre-event window for any upcoming event
        in_pre_event = False
        event_close_target = None
        for ev_idx in event_indices:
            if ev_idx >= len(df):
                continue
            event_date = df.index[ev_idx]
            days_to_event = (event_date - current_date).days
            if 0 < days_to_event <= pre_event_days * 2:  # approximate trading day window
                in_pre_event = True
                event_close_target = event_date + timedelta(days=post_event_close_days * 2)
                break

        if not in_pre_event or open_positions:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        # Compute IV rank on lookback
        lookback_df = df.iloc[max(0, i - 90):i + 1].copy()
        iv_rank = compute_iv_rank(lookback_df, window=min(60, len(lookback_df) - 21))

        signal_type = None
        if iv_rank > iv_rank_sell_threshold:
            signal_type = "BUY_PUT"
        elif iv_rank < iv_rank_buy_threshold:
            signal_type = "BUY_CALL"

        if signal_type is None:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        pos, cost = _open_position(
            capital, position_size_pct, signal_type, current_price,
            current_date, option_expiry_weeks, iv, symbol,
            extra_fields={
                "iv_rank": round(iv_rank, 1),
                "event_close_target": event_close_target,
                "confluence": iv_rank,
            },
        )
        if pos:
            capital -= cost
            open_positions.append(pos)

        equity_curve.append({"date": current_date, "equity": capital})

    # Force-close remaining
    final_price = float(df["Close"].iloc[-1])
    capital = _force_close_positions(open_positions, final_price, df.index[-1], iv, capital, trades)

    metrics = calculate_metrics(trades, starting_capital, equity_curve)
    return {
        "trades": trades,
        "metrics": metrics,
        "equity_curve": pd.DataFrame(equity_curve),
        "symbol": symbol,
        "strategy": "EVENT_VOL_STRANGLE",
        "parameters": {
            "pre_event_days": pre_event_days,
            "iv_rank_sell_threshold": iv_rank_sell_threshold,
            "iv_rank_buy_threshold": iv_rank_buy_threshold,
            "post_event_close_days": post_event_close_days,
            "option_expiry_weeks": option_expiry_weeks,
            "starting_capital": starting_capital,
            "position_size_pct": position_size_pct,
        },
    }


# ── Strategy 3: Vol Risk Premium Harvest ─────────────────────────────────────

def run_vrp_backtest(
    df: pd.DataFrame,
    symbol: str = "",
    starting_capital: float = DEFAULT_CAPITAL,
    position_size_pct: float = 3.0,
    option_expiry_weeks: int = DEFAULT_OPTION_EXPIRY_WEEKS,
    stop_loss_pct: float = 75.0,
    take_profit_pct: float = 50.0,
    iv_rank_min: float = 30.0,
    iv_rank_max_sell: float = 70.0,
    max_vix: float = 25.0,
    **kwargs,
) -> dict:
    """
    Vol Risk Premium Harvest.
    Systematically sells options premium when conditions are favorable:
    - IV rank in [iv_rank_min, iv_rank_max_sell]
    - RV < IV (premium exists)
    - VIX < max_vix
    Signal: BUY_PUT (proxy for selling puts to collect premium).
    Uses smaller position sizes and adjusted stops.
    """
    if len(df) < 30:
        return {"error": "Insufficient data for VRP backtest (need 30+ bars)"}

    start_str = df.index[0].strftime("%Y-%m-%d") if hasattr(df.index[0], "strftime") else None
    end_str = df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], "strftime") else None
    vix_series = _fetch_vix(start=start_str, end=end_str)

    trades = []
    equity_curve = []
    capital = starting_capital
    open_positions = []
    iv = estimate_iv(df)
    returns = df["Close"].pct_change()

    for i in range(30, len(df)):
        current_date = df.index[i]
        current_price = float(df["Close"].iloc[i])

        open_positions, capital = _manage_positions(
            open_positions, current_date, current_price, iv,
            stop_loss_pct, take_profit_pct, capital, trades
        )

        if open_positions:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        lookback_df = df.iloc[max(0, i - 60):i + 1].copy()
        if len(lookback_df) < 20:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        iv_rank = compute_iv_rank(lookback_df)

        # IV rank window check
        if not (iv_rank_min <= iv_rank <= iv_rank_max_sell):
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        # RV < IV check
        rv_slice = returns.iloc[i - 20:i].dropna()
        if len(rv_slice) < 10:
            equity_curve.append({"date": current_date, "equity": capital})
            continue
        rv = float(rv_slice.std() * np.sqrt(252))
        iv_est = estimate_iv(lookback_df, window=min(20, len(lookback_df) - 1))
        if rv >= iv_est:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        # VIX filter
        vix_val = None
        if not vix_series.empty:
            try:
                past_vix = vix_series[vix_series.index <= current_date]
            except TypeError:
                current_date_naive = current_date.replace(tzinfo=None) if hasattr(current_date, 'tzinfo') else current_date
                vix_dates_naive = vix_series.index.tz_localize(None) if vix_series.index.tz is not None else vix_series.index
                vix_series_naive = pd.Series(vix_series.values, index=vix_dates_naive)
                past_vix = vix_series_naive[vix_dates_naive <= current_date_naive]
            if not past_vix.empty:
                vix_val = float(past_vix.iloc[-1])

        if vix_val is not None and vix_val > max_vix:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        # Signal: sell premium → BUY_PUT
        pos, cost = _open_position(
            capital, position_size_pct, "BUY_PUT", current_price,
            current_date, option_expiry_weeks, iv, symbol,
            extra_fields={
                "iv_rank": round(iv_rank, 1),
                "rv": round(rv, 4),
                "iv_est": round(iv_est, 4),
                "confluence": iv_rank,
            },
        )
        if pos:
            capital -= cost
            open_positions.append(pos)

        equity_curve.append({"date": current_date, "equity": capital})

    final_price = float(df["Close"].iloc[-1])
    capital = _force_close_positions(open_positions, final_price, df.index[-1], iv, capital, trades)

    metrics = calculate_metrics(trades, starting_capital, equity_curve)
    return {
        "trades": trades,
        "metrics": metrics,
        "equity_curve": pd.DataFrame(equity_curve),
        "symbol": symbol,
        "strategy": "VRP_HARVEST",
        "parameters": {
            "iv_rank_min": iv_rank_min,
            "iv_rank_max_sell": iv_rank_max_sell,
            "max_vix": max_vix,
            "option_expiry_weeks": option_expiry_weeks,
            "starting_capital": starting_capital,
            "position_size_pct": position_size_pct,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
        },
    }


# ── Strategy 4: S/R + Vol Filter Overlay ─────────────────────────────────────

def run_sr_vol_backtest(
    df: pd.DataFrame,
    symbol: str = "",
    starting_capital: float = DEFAULT_CAPITAL,
    position_size_pct: float = DEFAULT_POSITION_SIZE_PCT,
    option_expiry_weeks: int = DEFAULT_OPTION_EXPIRY_WEEKS,
    stop_loss_pct: float = STOP_LOSS_PCT,
    take_profit_pct: float = TAKE_PROFIT_PCT,
    proximity_threshold_pct: float = 1.5,
    min_confluence: float = 40.0,
    volume_multiplier: float = 1.5,
    iv_rank_range: tuple = (20.0, 60.0),
    sma_period: int = 50,
    max_exposure_pct: float = MAX_EXPOSURE_PCT,
    otm_offset_pct: float = OTM_OFFSET_PCT,
    **kwargs,
) -> dict:
    """
    S/R + Vol Filter Overlay.
    Enhanced version of the standard S/R strategy with:
    - IV rank filter: only trade when IV rank is in [iv_rank_range[0], iv_rank_range[1]]
    - Volume confirmation: current volume > volume_multiplier × 20-day average
    - Trend filter: price must be above (for calls) or below (for puts) 50-day SMA
    """
    if len(df) < 60:
        return {"error": "Insufficient data for S/R+Vol backtest (need 60+ bars)"}

    trades = []
    equity_curve = []
    capital = starting_capital
    open_positions = []
    iv = estimate_iv(df)

    # Pre-compute 20-day volume average and 50-day SMA as rolling series
    vol_avg = df["Volume"].rolling(20).mean()
    sma50 = df["Close"].rolling(sma_period).mean()

    for i in range(60, len(df)):
        current_date = df.index[i]
        current_price = float(df["Close"].iloc[i])

        open_positions, capital = _manage_positions(
            open_positions, current_date, current_price, iv,
            stop_loss_pct, take_profit_pct, capital, trades
        )

        lookback_df = df.iloc[max(0, i - 60):i + 1].copy()
        if len(lookback_df) < 20:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        # IV rank filter
        iv_rank = compute_iv_rank(lookback_df)
        iv_lo, iv_hi = iv_rank_range
        if not (iv_lo <= iv_rank <= iv_hi):
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        # Volume confirmation
        current_vol = float(df["Volume"].iloc[i])
        avg_vol = float(vol_avg.iloc[i]) if not np.isnan(vol_avg.iloc[i]) else 0
        if avg_vol <= 0 or current_vol < volume_multiplier * avg_vol:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        # Max exposure check
        current_exposure = sum(p["cost"] for p in open_positions)
        if current_exposure >= capital * (max_exposure_pct / 100):
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        # Trend filter (SMA50)
        sma_val = float(sma50.iloc[i]) if not np.isnan(sma50.iloc[i]) else current_price
        price_above_sma = current_price > sma_val

        # S/R signal
        levels = find_pivots(lookback_df)
        all_levels = (
            [("support", s) for s in levels["support"]]
            + [("resistance", r) for r in levels["resistance"]]
        )

        for level_type, level in all_levels:
            score = score_confluence(level, current_price, lookback_df, proximity_threshold_pct)
            if (
                score["confluence_total"] >= min_confluence
                and score["distance_pct"] <= proximity_threshold_pct
            ):
                signal_type = "BUY_CALL" if level_type == "support" else "BUY_PUT"

                # Trend filter: skip calls in downtrend, skip puts in uptrend
                if signal_type == "BUY_CALL" and not price_above_sma:
                    continue
                if signal_type == "BUY_PUT" and price_above_sma:
                    continue

                max_cost = capital * (position_size_pct / 100)
                if max_cost <= 0:
                    continue

                T = option_expiry_weeks / 52
                if signal_type == "BUY_CALL":
                    strike = level["price"] * (1 - otm_offset_pct / 100)
                    premium = black_scholes_call(current_price, strike, T, sigma=iv)
                else:
                    strike = level["price"] * (1 + otm_offset_pct / 100)
                    premium = black_scholes_put(current_price, strike, T, sigma=iv)

                if premium <= 0.01:
                    continue

                contracts = max(1, int(max_cost / (premium * 100)))
                cost = contracts * premium * 100
                if cost > capital:
                    continue

                capital -= cost
                expiry_date = current_date + timedelta(weeks=option_expiry_weeks)
                open_positions.append({
                    "symbol": symbol,
                    "type": signal_type,
                    "entry_date": current_date,
                    "entry_price": current_price,
                    "strike": strike,
                    "entry_premium": premium,
                    "contracts": contracts,
                    "cost": cost,
                    "expiry_date": expiry_date,
                    "confluence": score["confluence_total"],
                    "iv_rank": round(iv_rank, 1),
                    "volume_ratio": round(current_vol / avg_vol, 2) if avg_vol > 0 else 0,
                    "sma_trend": "above" if price_above_sma else "below",
                })
                break

        equity_curve.append({"date": current_date, "equity": capital})

    final_price = float(df["Close"].iloc[-1])
    capital = _force_close_positions(open_positions, final_price, df.index[-1], iv, capital, trades)

    metrics = calculate_metrics(trades, starting_capital, equity_curve)
    return {
        "trades": trades,
        "metrics": metrics,
        "equity_curve": pd.DataFrame(equity_curve),
        "symbol": symbol,
        "strategy": "SR_VOL_OVERLAY",
        "parameters": {
            "proximity_threshold_pct": proximity_threshold_pct,
            "volume_multiplier": volume_multiplier,
            "iv_rank_range": list(iv_rank_range),
            "sma_period": sma_period,
            "option_expiry_weeks": option_expiry_weeks,
            "starting_capital": starting_capital,
            "position_size_pct": position_size_pct,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
        },
    }


# ── Strategy 5: Term Structure Carry ─────────────────────────────────────────

def run_term_carry_backtest(
    df: pd.DataFrame,
    symbol: str = "",
    starting_capital: float = DEFAULT_CAPITAL,
    position_size_pct: float = DEFAULT_POSITION_SIZE_PCT,
    option_expiry_weeks: int = DEFAULT_OPTION_EXPIRY_WEEKS,
    stop_loss_pct: float = STOP_LOSS_PCT,
    take_profit_pct: float = TAKE_PROFIT_PCT,
    short_window: int = 10,
    long_window: int = 60,
    contango_threshold: float = 0.8,
    backwardation_threshold: float = 1.2,
    max_vix: float = 35.0,
    **kwargs,
) -> dict:
    """
    Term Structure Carry.
    Compares short-term vs long-term realized vol to detect vol term structure shape:
    - Contango (short_vol < long_vol * contango_threshold): sell premium → BUY_PUT
    - Backwardation (short_vol > long_vol * backwardation_threshold): buy premium → BUY_CALL
    - VIX filter: skip if VIX > max_vix.
    """
    min_required = long_window + 10
    if len(df) < min_required:
        return {"error": f"Insufficient data for term carry backtest (need {min_required}+ bars)"}

    start_str = df.index[0].strftime("%Y-%m-%d") if hasattr(df.index[0], "strftime") else None
    end_str = df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], "strftime") else None
    vix_series = _fetch_vix(start=start_str, end=end_str)

    trades = []
    equity_curve = []
    capital = starting_capital
    open_positions = []
    iv = estimate_iv(df)

    returns = df["Close"].pct_change()

    for i in range(long_window, len(df)):
        current_date = df.index[i]
        current_price = float(df["Close"].iloc[i])

        open_positions, capital = _manage_positions(
            open_positions, current_date, current_price, iv,
            stop_loss_pct, take_profit_pct, capital, trades
        )

        if open_positions:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        # Compute short and long realized vol
        short_slice = returns.iloc[i - short_window:i].dropna()
        long_slice = returns.iloc[i - long_window:i].dropna()

        if len(short_slice) < short_window // 2 or len(long_slice) < long_window // 2:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        short_vol = float(short_slice.std() * np.sqrt(252))
        long_vol = float(long_slice.std() * np.sqrt(252))

        if long_vol == 0:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        # VIX filter
        vix_val = None
        if not vix_series.empty:
            try:
                past_vix = vix_series[vix_series.index <= current_date]
            except TypeError:
                current_date_naive = current_date.replace(tzinfo=None) if hasattr(current_date, 'tzinfo') else current_date
                vix_dates_naive = vix_series.index.tz_localize(None) if vix_series.index.tz is not None else vix_series.index
                vix_series_naive = pd.Series(vix_series.values, index=vix_dates_naive)
                past_vix = vix_series_naive[vix_dates_naive <= current_date_naive]
            if not past_vix.empty:
                vix_val = float(past_vix.iloc[-1])

        if vix_val is not None and vix_val > max_vix:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        # Signal determination
        ratio = short_vol / long_vol
        signal_type = None
        if ratio < contango_threshold:
            signal_type = "BUY_PUT"         # contango → sell premium
        elif ratio > backwardation_threshold:
            signal_type = "BUY_CALL"        # backwardation → buy premium

        if signal_type is None:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        pos, cost = _open_position(
            capital, position_size_pct, signal_type, current_price,
            current_date, option_expiry_weeks, iv, symbol,
            extra_fields={
                "short_vol": round(short_vol, 4),
                "long_vol": round(long_vol, 4),
                "vol_ratio": round(ratio, 4),
                "vix": vix_val,
                "confluence": abs(1 - ratio) * 100,
            },
        )
        if pos:
            capital -= cost
            open_positions.append(pos)

        equity_curve.append({"date": current_date, "equity": capital})

    final_price = float(df["Close"].iloc[-1])
    capital = _force_close_positions(open_positions, final_price, df.index[-1], iv, capital, trades)

    metrics = calculate_metrics(trades, starting_capital, equity_curve)
    return {
        "trades": trades,
        "metrics": metrics,
        "equity_curve": pd.DataFrame(equity_curve),
        "symbol": symbol,
        "strategy": "TERM_CARRY",
        "parameters": {
            "short_window": short_window,
            "long_window": long_window,
            "contango_threshold": contango_threshold,
            "backwardation_threshold": backwardation_threshold,
            "max_vix": max_vix,
            "option_expiry_weeks": option_expiry_weeks,
            "starting_capital": starting_capital,
            "position_size_pct": position_size_pct,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
        },
    }


# ── Strategy 6: Cross-Asset Momentum ─────────────────────────────────────────

def run_cross_asset_backtest(
    df: pd.DataFrame,
    symbol: str = "",
    starting_capital: float = DEFAULT_CAPITAL,
    position_size_pct: float = DEFAULT_POSITION_SIZE_PCT,
    option_expiry_weeks: int = DEFAULT_OPTION_EXPIRY_WEEKS,
    stop_loss_pct: float = STOP_LOSS_PCT,
    take_profit_pct: float = TAKE_PROFIT_PCT,
    rsi_oversold: float = 35.0,
    rsi_overbought: float = 70.0,
    vix_short_window: int = 10,
    vix_long_window: int = 20,
    **kwargs,
) -> dict:
    """
    Cross-Asset Momentum.
    Uses VIX trend + symbol RSI for cross-asset confirmation:
    - VIX falling (short SMA < long SMA) AND RSI < rsi_oversold: BUY_CALL
      (fear declining, symbol oversold → bullish)
    - VIX rising  (short SMA > long SMA) AND RSI > rsi_overbought: BUY_PUT
      (fear rising, symbol overbought → bearish)
    """
    if len(df) < 30:
        return {"error": "Insufficient data for cross-asset backtest (need 30+ bars)"}

    start_str = df.index[0].strftime("%Y-%m-%d") if hasattr(df.index[0], "strftime") else None
    end_str = df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], "strftime") else None
    vix_series = _fetch_vix(start=start_str, end=end_str)

    # Align VIX to the symbol's dates
    vix_aligned = pd.Series(dtype=float)
    if not vix_series.empty:
        try:
            vix_aligned = vix_series.reindex(df.index, method="ffill")
        except TypeError:
            # Handle tz mismatch
            try:
                idx_naive = df.index.tz_localize(None) if df.index.tz is not None else df.index
                vix_idx_naive = vix_series.index.tz_localize(None) if vix_series.index.tz is not None else vix_series.index
                vix_s_naive = pd.Series(vix_series.values, index=vix_idx_naive)
                vix_aligned = vix_s_naive.reindex(idx_naive, method="ffill")
                vix_aligned.index = df.index
            except Exception:
                vix_aligned = pd.Series(dtype=float)

    # Precompute RSI on symbol
    rsi_series = _compute_rsi(df["Close"], window=14)

    # Precompute VIX SMAs if we have aligned data
    if not vix_aligned.empty and len(vix_aligned.dropna()) >= vix_long_window:
        vix_sma_short = vix_aligned.rolling(vix_short_window).mean()
        vix_sma_long = vix_aligned.rolling(vix_long_window).mean()
    else:
        vix_sma_short = pd.Series(dtype=float)
        vix_sma_long = pd.Series(dtype=float)

    trades = []
    equity_curve = []
    capital = starting_capital
    open_positions = []
    iv = estimate_iv(df)

    for i in range(max(30, vix_long_window), len(df)):
        current_date = df.index[i]
        current_price = float(df["Close"].iloc[i])

        open_positions, capital = _manage_positions(
            open_positions, current_date, current_price, iv,
            stop_loss_pct, take_profit_pct, capital, trades
        )

        if open_positions:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        # RSI value
        rsi_val = float(rsi_series.iloc[i]) if i < len(rsi_series) and not np.isnan(rsi_series.iloc[i]) else 50.0

        # VIX trend
        if vix_sma_short.empty or vix_sma_long.empty:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        vs_short = float(vix_sma_short.iloc[i]) if i < len(vix_sma_short) and not np.isnan(vix_sma_short.iloc[i]) else None
        vs_long = float(vix_sma_long.iloc[i]) if i < len(vix_sma_long) and not np.isnan(vix_sma_long.iloc[i]) else None

        if vs_short is None or vs_long is None:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        vix_falling = vs_short < vs_long
        vix_rising = vs_short > vs_long

        # Signal logic
        signal_type = None
        if vix_falling and rsi_val < rsi_oversold:
            signal_type = "BUY_CALL"
        elif vix_rising and rsi_val > rsi_overbought:
            signal_type = "BUY_PUT"

        if signal_type is None:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        # Confluence score: distance from RSI neutral (50) + VIX spread magnitude
        vix_spread = abs(vs_short - vs_long)
        rsi_distance = abs(rsi_val - 50)
        confluence_score = min(100, (rsi_distance / 50 + vix_spread / 5) * 50)

        pos, cost = _open_position(
            capital, position_size_pct, signal_type, current_price,
            current_date, option_expiry_weeks, iv, symbol,
            extra_fields={
                "rsi": round(rsi_val, 1),
                "vix_sma_short": round(vs_short, 2),
                "vix_sma_long": round(vs_long, 2),
                "vix_trend": "falling" if vix_falling else "rising",
                "confluence": round(confluence_score, 1),
            },
        )
        if pos:
            capital -= cost
            open_positions.append(pos)

        equity_curve.append({"date": current_date, "equity": capital})

    final_price = float(df["Close"].iloc[-1])
    capital = _force_close_positions(open_positions, final_price, df.index[-1], iv, capital, trades)

    metrics = calculate_metrics(trades, starting_capital, equity_curve)
    return {
        "trades": trades,
        "metrics": metrics,
        "equity_curve": pd.DataFrame(equity_curve),
        "symbol": symbol,
        "strategy": "CROSS_ASSET_MOMENTUM",
        "parameters": {
            "rsi_oversold": rsi_oversold,
            "rsi_overbought": rsi_overbought,
            "vix_short_window": vix_short_window,
            "vix_long_window": vix_long_window,
            "option_expiry_weeks": option_expiry_weeks,
            "starting_capital": starting_capital,
            "position_size_pct": position_size_pct,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
        },
    }
