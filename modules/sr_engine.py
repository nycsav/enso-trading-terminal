"""
Support/Resistance Engine
- 20-day pivot-based lookback
- 4-factor confluence scoring (proximity, volume, trend, retest)
- Signal generation: BUY_CALL at support, BUY_PUT at resistance
"""
import pandas as pd
import numpy as np
from config import SR_LOOKBACK_DAYS, CONFLUENCE_WEIGHTS


def find_pivots(df: pd.DataFrame, lookback: int = SR_LOOKBACK_DAYS) -> dict:
    """
    Identify support and resistance levels from pivot highs/lows
    over the specified lookback window.
    
    Returns dict with 'support' and 'resistance' lists of price levels.
    """
    highs = df["High"].values
    lows = df["Low"].values
    closes = df["Close"].values

    supports = []
    resistances = []

    window = max(3, lookback // 4)

    for i in range(window, len(df) - window):
        # Pivot low → support
        if lows[i] == min(lows[i - window : i + window + 1]):
            supports.append({"price": float(lows[i]), "date": df.index[i], "idx": i})
        # Pivot high → resistance
        if highs[i] == max(highs[i - window : i + window + 1]):
            resistances.append({"price": float(highs[i]), "date": df.index[i], "idx": i})

    # Cluster nearby levels (within 0.5%)
    supports = _cluster_levels(supports)
    resistances = _cluster_levels(resistances)

    return {"support": supports, "resistance": resistances}


def _cluster_levels(levels: list, threshold_pct: float = 0.5) -> list:
    """Merge levels that are within threshold_pct of each other."""
    if not levels:
        return []

    sorted_levels = sorted(levels, key=lambda x: x["price"])
    clustered = [sorted_levels[0]]

    for lvl in sorted_levels[1:]:
        last = clustered[-1]
        if abs(lvl["price"] - last["price"]) / last["price"] * 100 < threshold_pct:
            # Merge: average the price, keep latest date
            clustered[-1] = {
                "price": (last["price"] + lvl["price"]) / 2,
                "date": max(last["date"], lvl["date"]),
                "idx": max(last["idx"], lvl["idx"]),
                "touches": last.get("touches", 1) + 1,
            }
        else:
            lvl["touches"] = 1
            clustered.append(lvl)

    return clustered


def score_confluence(level: dict, current_price: float, df: pd.DataFrame,
                     proximity_threshold_pct: float = 1.5) -> dict:
    """
    Score a S/R level using 4 confluence factors:
    1. Proximity: How close price is to the level
    2. Volume: Volume spike near the level
    3. Trend: Alignment with moving average trend
    4. Retest: Number of times level has been tested
    
    Returns dict with individual scores and weighted total (0-100).
    """
    level_price = level["price"]
    distance_pct = abs(current_price - level_price) / current_price * 100

    # 1. Proximity score (higher when closer)
    if distance_pct <= proximity_threshold_pct:
        proximity_score = max(0, 100 * (1 - distance_pct / proximity_threshold_pct))
    else:
        proximity_score = 0

    # 2. Volume score (check for volume spike at level)
    avg_volume = df["Volume"].rolling(20).mean().iloc[-1]
    recent_volume = df["Volume"].iloc[-5:].mean()
    volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
    volume_score = min(100, volume_ratio * 50)

    # 3. Trend score (SMA alignment)
    sma_20 = df["Close"].rolling(20).mean().iloc[-1]
    sma_50 = df["Close"].rolling(50).mean().iloc[-1] if len(df) >= 50 else sma_20
    if current_price > sma_20 > sma_50:
        trend_direction = "bullish"
        trend_score = 80
    elif current_price < sma_20 < sma_50:
        trend_direction = "bearish"
        trend_score = 80
    else:
        trend_direction = "neutral"
        trend_score = 40

    # 4. Retest score (more touches = stronger level)
    touches = level.get("touches", 1)
    retest_score = min(100, touches * 25)

    # Weighted total
    total = (
        CONFLUENCE_WEIGHTS["proximity"] * proximity_score
        + CONFLUENCE_WEIGHTS["volume"] * volume_score
        + CONFLUENCE_WEIGHTS["trend"] * trend_score
        + CONFLUENCE_WEIGHTS["retest"] * retest_score
    )

    return {
        "level_price": level_price,
        "distance_pct": round(distance_pct, 2),
        "proximity_score": round(proximity_score, 1),
        "volume_score": round(volume_score, 1),
        "trend_score": round(trend_score, 1),
        "trend_direction": trend_direction,
        "retest_score": round(retest_score, 1),
        "touches": touches,
        "confluence_total": round(total, 1),
    }


def generate_signals(df: pd.DataFrame, proximity_threshold_pct: float = 1.5,
                     min_confluence: float = 40.0) -> list:
    """
    Generate trading signals based on S/R proximity and confluence scoring.
    
    BUY_CALL when price is near support with sufficient confluence.
    BUY_PUT when price is near resistance with sufficient confluence.
    
    Returns list of signal dicts.
    """
    current_price = float(df["Close"].iloc[-1])
    levels = find_pivots(df)
    signals = []

    # Check supports → BUY_CALL
    for s in levels["support"]:
        score = score_confluence(s, current_price, df, proximity_threshold_pct)
        if score["confluence_total"] >= min_confluence and score["distance_pct"] <= proximity_threshold_pct:
            signals.append({
                "type": "BUY_CALL",
                "level_type": "support",
                "level_price": s["price"],
                "current_price": current_price,
                "confluence": score,
            })

    # Check resistances → BUY_PUT
    for r in levels["resistance"]:
        score = score_confluence(r, current_price, df, proximity_threshold_pct)
        if score["confluence_total"] >= min_confluence and score["distance_pct"] <= proximity_threshold_pct:
            signals.append({
                "type": "BUY_PUT",
                "level_type": "resistance",
                "level_price": r["price"],
                "current_price": current_price,
                "confluence": score,
            })

    # Sort by confluence score descending
    signals.sort(key=lambda x: x["confluence"]["confluence_total"], reverse=True)
    return signals


def get_sr_summary(df: pd.DataFrame, symbol: str = "") -> dict:
    """Get a full S/R analysis summary for a symbol."""
    current_price = float(df["Close"].iloc[-1])
    levels = find_pivots(df)
    signals = generate_signals(df)

    scored_supports = [
        score_confluence(s, current_price, df) for s in levels["support"]
    ]
    scored_resistances = [
        score_confluence(r, current_price, df) for r in levels["resistance"]
    ]

    return {
        "symbol": symbol,
        "current_price": current_price,
        "supports": scored_supports,
        "resistances": scored_resistances,
        "signals": signals,
        "num_supports": len(levels["support"]),
        "num_resistances": len(levels["resistance"]),
    }
