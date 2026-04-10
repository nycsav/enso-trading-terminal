"""
Backtesting Engine
- Walk-forward optimization with overfit detection
- Black-Scholes option pricing
- Portfolio-level analysis across multiple symbols
- 13+ performance metrics
"""
import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import timedelta
from modules.sr_engine import find_pivots, score_confluence
from config import (
    DEFAULT_CAPITAL,
    DEFAULT_POSITION_SIZE_PCT,
    DEFAULT_OPTION_EXPIRY_WEEKS,
    WALK_FORWARD_TRAIN_RATIO,
)


def black_scholes_call(S: float, K: float, T: float, r: float = 0.05,
                       sigma: float = 0.3) -> float:
    """Black-Scholes call option price."""
    if T <= 0 or sigma <= 0 or S <= 0:
        return max(0, S - K)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def black_scholes_put(S: float, K: float, T: float, r: float = 0.05,
                      sigma: float = 0.3) -> float:
    """Black-Scholes put option price."""
    if T <= 0 or sigma <= 0 or S <= 0:
        return max(0, K - S)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def estimate_iv(df: pd.DataFrame, window: int = 20) -> float:
    """Estimate implied volatility from historical returns."""
    returns = df["Close"].pct_change().dropna()
    if len(returns) < window:
        return 0.3  # Default IV
    recent_std = returns.iloc[-window:].std()
    return float(recent_std * np.sqrt(252))


def run_backtest(
    df: pd.DataFrame,
    symbol: str = "",
    proximity_threshold_pct: float = 1.5,
    option_expiry_weeks: int = DEFAULT_OPTION_EXPIRY_WEEKS,
    starting_capital: float = DEFAULT_CAPITAL,
    position_size_pct: float = DEFAULT_POSITION_SIZE_PCT,
    min_confluence: float = 40.0,
) -> dict:
    """
    Run a full backtest over historical data.
    
    For each bar:
    1. Calculate S/R levels using lookback window
    2. Generate signals (BUY_CALL at support, BUY_PUT at resistance)
    3. Price options using Black-Scholes
    4. Track P&L through option expiration
    
    Returns comprehensive results dict with trades, metrics, and equity curve.
    """
    if len(df) < 30:
        return {"error": "Insufficient data for backtest (need 30+ bars)"}

    trades = []
    equity_curve = []
    capital = starting_capital
    open_positions = []

    iv = estimate_iv(df)

    for i in range(30, len(df)):
        current_date = df.index[i]
        current_price = float(df["Close"].iloc[i])

        # Check and close expired positions
        still_open = []
        for pos in open_positions:
            if current_date >= pos["expiry_date"]:
                # Close the position
                exit_price = current_price
                if pos["type"] == "BUY_CALL":
                    option_exit = black_scholes_call(
                        exit_price, pos["strike"], 0.001, sigma=iv
                    )
                else:
                    option_exit = black_scholes_put(
                        exit_price, pos["strike"], 0.001, sigma=iv
                    )

                pnl = (option_exit - pos["entry_premium"]) * pos["contracts"] * 100
                capital += pnl + pos["cost"]  # Return cost + P&L

                pos["exit_date"] = current_date
                pos["exit_price"] = exit_price
                pos["exit_premium"] = option_exit
                pos["pnl"] = pnl
                pos["holding_days"] = (current_date - pos["entry_date"]).days
                trades.append(pos)
            else:
                still_open.append(pos)
        open_positions = still_open

        # Generate signals on lookback window
        lookback_df = df.iloc[max(0, i - 60) : i + 1].copy()
        if len(lookback_df) < 20:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

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
                # Determine signal type
                signal_type = "BUY_CALL" if level_type == "support" else "BUY_PUT"

                # Calculate position size
                max_cost = capital * (position_size_pct / 100)
                if max_cost <= 0:
                    continue

                # Price the option
                T = option_expiry_weeks / 52
                strike = level["price"]

                if signal_type == "BUY_CALL":
                    premium = black_scholes_call(current_price, strike, T, sigma=iv)
                else:
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
                })

                break  # One signal per bar

        equity_curve.append({"date": current_date, "equity": capital})

    # Force-close remaining positions at last price
    final_price = float(df["Close"].iloc[-1])
    for pos in open_positions:
        if pos["type"] == "BUY_CALL":
            option_exit = black_scholes_call(final_price, pos["strike"], 0.001, sigma=iv)
        else:
            option_exit = black_scholes_put(final_price, pos["strike"], 0.001, sigma=iv)

        pnl = (option_exit - pos["entry_premium"]) * pos["contracts"] * 100
        capital += pnl + pos["cost"]
        pos["exit_date"] = df.index[-1]
        pos["exit_price"] = final_price
        pos["exit_premium"] = option_exit
        pos["pnl"] = pnl
        pos["holding_days"] = (df.index[-1] - pos["entry_date"]).days
        trades.append(pos)

    metrics = calculate_metrics(trades, starting_capital, equity_curve)
    equity_df = pd.DataFrame(equity_curve)

    return {
        "trades": trades,
        "metrics": metrics,
        "equity_curve": equity_df,
        "symbol": symbol,
        "parameters": {
            "proximity_threshold_pct": proximity_threshold_pct,
            "option_expiry_weeks": option_expiry_weeks,
            "starting_capital": starting_capital,
            "position_size_pct": position_size_pct,
        },
    }


def calculate_metrics(trades: list, starting_capital: float,
                      equity_curve: list) -> dict:
    """Calculate 13+ performance metrics from trade results."""
    if not trades:
        return {
            "total_trades": 0,
            "win_rate": 0,
            "loss_rate": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "win_loss_ratio": 0,
            "total_pnl": 0,
            "total_return_pct": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
            "profit_factor": 0,
            "best_trade": 0,
            "worst_trade": 0,
            "avg_holding_period": 0,
            "call_count": 0,
            "put_count": 0,
            "monthly_pnl": {},
        }

    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    total_trades = len(trades)
    win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
    loss_rate = len(losses) / total_trades * 100 if total_trades > 0 else 0
    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0
    win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")

    total_pnl = sum(pnls)
    total_return_pct = (total_pnl / starting_capital) * 100

    # Max drawdown from equity curve
    if equity_curve:
        equities = [e["equity"] for e in equity_curve]
        peak = equities[0]
        max_dd = 0
        for eq in equities:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)
    else:
        max_dd = 0

    # Sharpe ratio (annualized)
    if len(pnls) > 1:
        returns = np.array(pnls) / starting_capital
        sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252) if np.std(returns) > 0 else 0
    else:
        sharpe = 0

    # Profit factor
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Holding period
    holding_days = [t.get("holding_days", 0) for t in trades]
    avg_holding = np.mean(holding_days) if holding_days else 0

    # Call vs Put breakdown
    call_count = sum(1 for t in trades if t["type"] == "BUY_CALL")
    put_count = sum(1 for t in trades if t["type"] == "BUY_PUT")

    # Monthly P&L
    monthly_pnl = {}
    for t in trades:
        if "exit_date" in t and t["exit_date"] is not None:
            month_key = t["exit_date"].strftime("%Y-%m")
            monthly_pnl[month_key] = monthly_pnl.get(month_key, 0) + t["pnl"]

    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate, 1),
        "loss_rate": round(loss_rate, 1),
        "avg_win": round(float(avg_win), 2),
        "avg_loss": round(float(avg_loss), 2),
        "win_loss_ratio": round(float(win_loss_ratio), 2),
        "total_pnl": round(float(total_pnl), 2),
        "total_return_pct": round(float(total_return_pct), 2),
        "max_drawdown": round(float(max_dd), 2),
        "sharpe_ratio": round(float(sharpe), 2),
        "profit_factor": round(float(profit_factor), 2),
        "best_trade": round(float(max(pnls)), 2),
        "worst_trade": round(float(min(pnls)), 2),
        "avg_holding_period": round(float(avg_holding), 1),
        "call_count": call_count,
        "put_count": put_count,
        "monthly_pnl": monthly_pnl,
    }


def walk_forward_optimization(
    df: pd.DataFrame,
    symbol: str = "",
    train_ratio: float = WALK_FORWARD_TRAIN_RATIO,
    proximity_range: tuple = (0.5, 3.0),
    proximity_step: float = 0.25,
    option_expiry_weeks: int = DEFAULT_OPTION_EXPIRY_WEEKS,
    starting_capital: float = DEFAULT_CAPITAL,
) -> dict:
    """
    Walk-forward optimization with overfit detection.
    
    1. Split data into train (70%) and test (30%)
    2. Test proximity thresholds across the range on training data
    3. Select best parameter from training
    4. Validate on test data
    5. Compare train vs test performance for overfit detection
    
    Overfit ratings:
    - ROBUST: Test Sharpe >= 50% of Train Sharpe
    - MODERATE: Test Sharpe >= 25% of Train Sharpe  
    - OVERFIT: Test Sharpe < 25% of Train Sharpe
    """
    split_idx = int(len(df) * train_ratio)
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()

    if len(train_df) < 40 or len(test_df) < 20:
        return {"error": "Insufficient data for walk-forward optimization"}

    # Grid search on training data
    proximity_values = np.arange(proximity_range[0], proximity_range[1] + proximity_step, proximity_step)
    train_results = []

    for prox in proximity_values:
        result = run_backtest(
            train_df, symbol=symbol,
            proximity_threshold_pct=float(prox),
            option_expiry_weeks=option_expiry_weeks,
            starting_capital=starting_capital,
        )
        train_results.append({
            "proximity": round(float(prox), 2),
            "sharpe": result["metrics"]["sharpe_ratio"],
            "total_pnl": result["metrics"]["total_pnl"],
            "win_rate": result["metrics"]["win_rate"],
            "total_trades": result["metrics"]["total_trades"],
            "max_drawdown": result["metrics"]["max_drawdown"],
        })

    # Find best parameter by Sharpe ratio
    best_train = max(train_results, key=lambda x: x["sharpe"])
    best_proximity = best_train["proximity"]

    # Validate on test data
    test_result = run_backtest(
        test_df, symbol=symbol,
        proximity_threshold_pct=best_proximity,
        option_expiry_weeks=option_expiry_weeks,
        starting_capital=starting_capital,
    )

    # Overfit detection
    train_sharpe = best_train["sharpe"]
    test_sharpe = test_result["metrics"]["sharpe_ratio"]

    if train_sharpe <= 0:
        overfit_rating = "OVERFIT"
    elif test_sharpe >= train_sharpe * 0.50:
        overfit_rating = "ROBUST"
    elif test_sharpe >= train_sharpe * 0.25:
        overfit_rating = "MODERATE"
    else:
        overfit_rating = "OVERFIT"

    return {
        "best_proximity": best_proximity,
        "train_results": train_results,
        "train_metrics": best_train,
        "test_metrics": test_result["metrics"],
        "test_trades": test_result["trades"],
        "overfit_rating": overfit_rating,
        "train_sharpe": train_sharpe,
        "test_sharpe": test_sharpe,
        "train_period": f"{train_df.index[0].strftime('%Y-%m-%d')} to {train_df.index[-1].strftime('%Y-%m-%d')}",
        "test_period": f"{test_df.index[0].strftime('%Y-%m-%d')} to {test_df.index[-1].strftime('%Y-%m-%d')}",
        "symbol": symbol,
    }


def run_multi_symbol_backtest(
    symbols: list,
    start_date: str = None,
    end_date: str = None,
    **kwargs,
) -> dict:
    """
    Run backtest across multiple symbols and aggregate results.
    Downloads data via yfinance for each symbol.
    """
    import yfinance as yf

    all_results = {}
    combined_trades = []

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date)
            if df.empty or len(df) < 30:
                all_results[symbol] = {"error": f"Insufficient data for {symbol}"}
                continue

            result = run_backtest(df, symbol=symbol, **kwargs)
            all_results[symbol] = result
            combined_trades.extend(result.get("trades", []))
        except Exception as e:
            all_results[symbol] = {"error": str(e)}

    # Aggregate metrics
    starting_capital = kwargs.get("starting_capital", DEFAULT_CAPITAL)
    agg_equity = []
    agg_metrics = calculate_metrics(combined_trades, starting_capital * len(symbols), agg_equity)

    return {
        "by_symbol": all_results,
        "combined_metrics": agg_metrics,
        "combined_trades": combined_trades,
        "symbols": symbols,
    }


def run_ml_backtest(
    df: pd.DataFrame,
    symbol: str = "",
    option_expiry_weeks: int = DEFAULT_OPTION_EXPIRY_WEEKS,
    starting_capital: float = DEFAULT_CAPITAL,
    position_size_pct: float = DEFAULT_POSITION_SIZE_PCT,
    min_confidence: float = 55.0,
    train_ratio: float = WALK_FORWARD_TRAIN_RATIO,
) -> dict:
    """
    Run ML-powered backtest using Gradient Boosted Trees.
    
    1. Split data into train/test
    2. Train ML model on training data
    3. Generate signals on test data
    4. Price options and track P&L
    
    Returns results dict compatible with existing dashboard.
    """
    from modules.ml_strategy import MLStrategy
    from modules.rl_agent import RLPositionSizer, TradingState

    if len(df) < 100:
        return {"error": "Insufficient data for ML backtest (need 100+ bars)"}

    # Split data
    split_idx = int(len(df) * train_ratio)
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()

    if len(train_df) < 80 or len(test_df) < 20:
        return {"error": "Insufficient data for train/test split"}

    # Train ML model
    ml = MLStrategy(forward_days=15, threshold_pct=2.0)
    train_result = ml.train(train_df)
    if "error" in train_result:
        return train_result

    # Initialize RL position sizer
    rl = RLPositionSizer()

    # Run backtest on test data
    trades = []
    equity_curve = []
    capital = starting_capital
    open_positions = []
    iv = estimate_iv(df)

    for i in range(50, len(test_df)):
        current_date = test_df.index[i]
        current_price = float(test_df["Close"].iloc[i])

        # Close expired positions
        still_open = []
        for pos in open_positions:
            if current_date >= pos["expiry_date"]:
                exit_price = current_price
                if pos["type"] == "BUY_CALL":
                    option_exit = black_scholes_call(
                        exit_price, pos["strike"], 0.001, sigma=iv
                    )
                else:
                    option_exit = black_scholes_put(
                        exit_price, pos["strike"], 0.001, sigma=iv
                    )
                pnl = (option_exit - pos["entry_premium"]) * pos["contracts"] * 100
                capital += pnl + pos["cost"]
                pos["exit_date"] = current_date
                pos["exit_price"] = exit_price
                pos["exit_premium"] = option_exit
                pos["pnl"] = pnl
                pos["holding_days"] = (current_date - pos["entry_date"]).days
                trades.append(pos)
            else:
                still_open.append(pos)
        open_positions = still_open

        # Get ML prediction using lookback window
        lookback_start = max(0, i - 60)
        lookback_df = test_df.iloc[lookback_start:i + 1].copy()
        if len(lookback_df) < 50:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        signal = ml.predict(lookback_df)
        regime = ml.get_regime(lookback_df)

        if signal["signal"] == "NO_TRADE" or signal["confidence"] < min_confidence:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        # RL position sizing
        from modules.ml_strategy import compute_features
        features = compute_features(lookback_df)
        rsi_val = float(features["rsi_14"].iloc[-1]) if "rsi_14" in features and not pd.isna(features["rsi_14"].iloc[-1]) else 50
        exposure_pct = sum(p["cost"] for p in open_positions) / capital * 100 if capital > 0 else 0

        state = TradingState.get_state(
            regime, iv, signal["confidence"], exposure_pct, rsi_val
        )
        rl_decision = rl.get_position_size(state)
        actual_size_pct = rl_decision["size_pct"] if rl_decision["size_pct"] > 0 else position_size_pct

        # Calculate position
        max_cost = capital * (actual_size_pct / 100)
        if max_cost <= 0:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        T = option_expiry_weeks / 52
        strike = current_price  # ATM options

        if signal["signal"] == "BUY_CALL":
            premium = black_scholes_call(current_price, strike, T, sigma=iv)
        else:
            premium = black_scholes_put(current_price, strike, T, sigma=iv)

        if premium <= 0.01:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        contracts = max(1, int(max_cost / (premium * 100)))
        cost = contracts * premium * 100
        if cost > capital:
            equity_curve.append({"date": current_date, "equity": capital})
            continue

        capital -= cost
        expiry_date = current_date + timedelta(weeks=option_expiry_weeks)

        open_positions.append({
            "symbol": symbol,
            "type": signal["signal"],
            "entry_date": current_date,
            "entry_price": current_price,
            "strike": strike,
            "entry_premium": premium,
            "contracts": contracts,
            "cost": cost,
            "expiry_date": expiry_date,
            "confluence": signal["confidence"],
            "ml_confidence": signal["confidence"],
            "regime": regime,
            "rl_action": rl_decision["action_name"],
        })

        equity_curve.append({"date": current_date, "equity": capital})

    # Force-close remaining positions
    final_price = float(test_df["Close"].iloc[-1])
    for pos in open_positions:
        if pos["type"] == "BUY_CALL":
            option_exit = black_scholes_call(final_price, pos["strike"], 0.001, sigma=iv)
        else:
            option_exit = black_scholes_put(final_price, pos["strike"], 0.001, sigma=iv)
        pnl = (option_exit - pos["entry_premium"]) * pos["contracts"] * 100
        capital += pnl + pos["cost"]
        pos["exit_date"] = test_df.index[-1]
        pos["exit_price"] = final_price
        pos["exit_premium"] = option_exit
        pos["pnl"] = pnl
        pos["holding_days"] = (test_df.index[-1] - pos["entry_date"]).days
        trades.append(pos)

    # Train RL on results for future use
    if trades:
        rl.train_on_backtest(trades, starting_capital)

    metrics = calculate_metrics(trades, starting_capital, equity_curve)
    equity_df = pd.DataFrame(equity_curve)

    return {
        "trades": trades,
        "metrics": metrics,
        "equity_curve": equity_df,
        "symbol": symbol,
        "strategy": "ML_GBT",
        "ml_training": train_result,
        "rl_summary": rl.get_training_summary(),
        "parameters": {
            "min_confidence": min_confidence,
            "option_expiry_weeks": option_expiry_weeks,
            "starting_capital": starting_capital,
            "position_size_pct": position_size_pct,
            "train_ratio": train_ratio,
        },
    }
