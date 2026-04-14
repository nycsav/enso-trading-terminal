"""
strategy_map.py — Enso Options Strategy Mapping Module

Maps (direction, volatility_regime) tuples to specific options strategies with
plain-English descriptions, risk/reward profiles, and complexity ratings.

Used by SignalSynthesizer in agent_framework.py to recommend the right strategy
based on the combined output of the TechnicalAgent and VolatilityAgent.

Direction values:  BULLISH | BEARISH | NEUTRAL
Vol regime values: HIGH_VOL | NORMAL | LOW_VOL

Usage:
    from modules.strategy_map import STRATEGY_MAP, get_strategy, list_all_strategies

    strategy = get_strategy("BULLISH", "HIGH_VOL")
    print(strategy["name"])           # "Cash-Secured Put"
    print(strategy["description"])    # Plain-English explanation
"""

from typing import Optional


# ── Core Strategy Map ─────────────────────────────────────────────────────────
#
# Keys: (direction, vol_regime)
#   direction   → "BULLISH" | "BEARISH" | "NEUTRAL"
#   vol_regime  → "HIGH_VOL" | "NORMAL" | "LOW_VOL"
#
# Values: dict with name, description, risk, reward, complexity, capital_required
# ─────────────────────────────────────────────────────────────────────────────

STRATEGY_MAP: dict[tuple[str, str], dict] = {

    # ── BULLISH ──────────────────────────────────────────────────────────────

    ("BULLISH", "HIGH_VOL"): {
        "name": "Cash-Secured Put",
        "description": (
            "Sell a put option below the current price. You collect premium upfront. "
            "If the stock drops to your strike, you buy it at a discount. Works best "
            "when volatility is high — elevated IV means bigger premiums."
        ),
        "risk": (
            "You could be forced to buy the stock at the strike price if it drops "
            "significantly. Max loss = (strike price × 100) minus premium collected."
        ),
        "reward": (
            "Keep the full premium if the stock stays above the strike at expiration. "
            "Max profit = premium collected."
        ),
        "complexity": "Beginner",
        "capital_required": "High (must hold cash equal to 100 × strike price)",
        "ideal_conditions": "Bullish bias, high IV, willing to own the stock at strike",
        "typical_dte": "30-45 days",
    },

    ("BULLISH", "LOW_VOL"): {
        "name": "Bull Call Spread",
        "description": (
            "Buy a call at a lower strike and sell a call at a higher strike. "
            "Limits both your risk and your reward. Cheap to enter when volatility "
            "is low — you pay less for the long call, and the spread locks in defined risk."
        ),
        "risk": (
            "Lose the entire net premium paid if the stock doesn't rise above the "
            "lower (bought) strike by expiration."
        ),
        "reward": (
            "Max profit = difference between strikes minus the net premium paid. "
            "Example: $5-wide spread for $1.50 debit → max profit $3.50 per share."
        ),
        "complexity": "Intermediate",
        "capital_required": "Low (just the net debit — typically $50–$300 per spread)",
        "ideal_conditions": "Bullish directional bet, low IV, defined risk preference",
        "typical_dte": "21-45 days",
    },

    ("BULLISH", "NORMAL"): {
        "name": "Bull Call Spread",
        "description": (
            "Buy a call at a lower strike and sell a call at a higher strike. "
            "Defined risk, defined reward. A clean directional play when you expect "
            "the stock to move higher but want to limit downside."
        ),
        "risk": (
            "Lose the net premium paid if the stock doesn't rise above the lower strike."
        ),
        "reward": (
            "Max profit = strike width minus net premium paid. "
            "Full profit if stock is above the upper strike at expiration."
        ),
        "complexity": "Intermediate",
        "capital_required": "Low (net debit only)",
        "ideal_conditions": "Moderate bullish conviction, normal IV environment",
        "typical_dte": "21-45 days",
    },

    # ── BEARISH ──────────────────────────────────────────────────────────────

    ("BEARISH", "HIGH_VOL"): {
        "name": "Bear Call Spread",
        "description": (
            "Sell a call at a lower strike and buy a call at a higher strike to cap "
            "your risk. You collect premium upfront, betting that the stock stays "
            "below your short (lower) strike. Fat premiums in high-vol environments "
            "make this an attractive credit collection play."
        ),
        "risk": (
            "Max loss = strike width minus premium collected. "
            "Example: $5-wide spread for $1.50 credit → max loss $3.50 per share."
        ),
        "reward": (
            "Keep the full premium collected if the stock stays below the short strike "
            "at expiration. Max profit = premium collected."
        ),
        "complexity": "Intermediate",
        "capital_required": "Moderate (margin held for the spread width)",
        "ideal_conditions": "Bearish bias, high IV, stock overbought or at resistance",
        "typical_dte": "30-45 days",
    },

    ("BEARISH", "LOW_VOL"): {
        "name": "Bear Put Spread",
        "description": (
            "Buy a put at a higher strike and sell a put at a lower strike to offset "
            "cost. Profits if the stock drops. Debit spread — you pay a net premium "
            "upfront but your risk is fully defined. Low IV means cheaper entry."
        ),
        "risk": (
            "Lose the net premium paid if the stock doesn't fall below the higher "
            "(bought put) strike by expiration."
        ),
        "reward": (
            "Max profit = strike width minus net premium paid. "
            "Full profit if stock is below the lower (short) strike at expiration."
        ),
        "complexity": "Intermediate",
        "capital_required": "Low (net debit only)",
        "ideal_conditions": "Bearish directional bet, low IV, defined risk preference",
        "typical_dte": "21-45 days",
    },

    ("BEARISH", "NORMAL"): {
        "name": "Bear Put Spread",
        "description": (
            "Buy a put at a higher strike and sell a put at a lower strike. "
            "Defined risk bearish play — you pay a net debit and profit if the "
            "stock declines. Clean structure with capped risk and reward."
        ),
        "risk": "Lose net premium if the stock rises or stays flat.",
        "reward": "Max profit = strike width minus net premium. Full profit below lower strike.",
        "complexity": "Intermediate",
        "capital_required": "Low (net debit only)",
        "ideal_conditions": "Moderate bearish conviction, normal IV environment",
        "typical_dte": "21-45 days",
    },

    # ── NEUTRAL ───────────────────────────────────────────────────────────────

    ("NEUTRAL", "HIGH_VOL"): {
        "name": "Iron Condor",
        "description": (
            "Sell both a call spread above and a put spread below the current price. "
            "Profits if the stock stays in a range between your short strikes. Best when "
            "volatility is high — fat premiums make the risk/reward attractive, and "
            "stocks often mean-revert after vol spikes."
        ),
        "risk": (
            "Max loss = the wider of the two spread widths minus total premium collected. "
            "Loss is capped — you know your worst case going in."
        ),
        "reward": (
            "Keep the full combined premium if the stock stays between both short "
            "strikes at expiration. Max profit = total credit received."
        ),
        "complexity": "Intermediate",
        "capital_required": "Moderate (margin held for the wider spread)",
        "ideal_conditions": "No strong directional view, high IV, stock expected to range",
        "typical_dte": "30-45 days",
    },

    ("NEUTRAL", "LOW_VOL"): {
        "name": "Long Straddle",
        "description": (
            "Buy both a call and a put at the same at-the-money strike. Profits if the "
            "stock makes a big move in either direction — you don't care which way. "
            "Best when volatility is cheap and you expect a catalyst (earnings, FDA, "
            "macro event) to trigger a breakout."
        ),
        "risk": (
            "Lose the total premium paid for both options if the stock barely moves "
            "by expiration. Time decay works against you."
        ),
        "reward": (
            "Theoretically unlimited on the upside; large downside profit potential. "
            "Profitable if the stock moves more than the total premium paid."
        ),
        "complexity": "Beginner",
        "capital_required": "Moderate (cost of both ATM options — typically higher per-share cost)",
        "ideal_conditions": "Neutral bias, low IV, expecting a volatility expansion or catalyst",
        "typical_dte": "14-30 days (closer to catalyst)",
    },

    ("NEUTRAL", "NORMAL"): {
        "name": "Iron Condor (narrow)",
        "description": (
            "Sell a narrow call spread and put spread around the current price. "
            "Smaller premium collected compared to a wide condor, but a higher "
            "probability of keeping it. Good for range-bound stocks with no "
            "strong directional catalyst expected."
        ),
        "risk": "Max loss = spread width minus premium collected (fully defined).",
        "reward": "Keep full premium if stock stays in range between short strikes.",
        "complexity": "Intermediate",
        "capital_required": "Moderate (margin for spread)",
        "ideal_conditions": "Neutral bias, normal IV, low expected movement",
        "typical_dte": "30-45 days",
    },
}


# ── Helper Functions ──────────────────────────────────────────────────────────

def get_strategy(direction: str, vol_regime: str) -> Optional[dict]:
    """
    Look up the recommended options strategy for a given direction and vol regime.

    Args:
        direction:  "BULLISH", "BEARISH", or "NEUTRAL"
        vol_regime: "HIGH_VOL", "NORMAL", or "LOW_VOL"

    Returns:
        Strategy dict with name, description, risk, reward, complexity, etc.
        Returns None if no matching strategy found.

    Example:
        strategy = get_strategy("BULLISH", "HIGH_VOL")
        # Returns: {"name": "Cash-Secured Put", "description": ..., ...}
    """
    key = (direction.upper(), vol_regime.upper())
    return STRATEGY_MAP.get(key)


def get_strategy_name(direction: str, vol_regime: str) -> str:
    """
    Return just the strategy name for a direction + vol_regime combination.

    Returns "Unknown Strategy" if no match found.
    """
    strategy = get_strategy(direction, vol_regime)
    return strategy["name"] if strategy else "Unknown Strategy"


def list_all_strategies() -> list[dict]:
    """
    Return all strategies in the map as a list of dicts,
    each including the direction and vol_regime keys.

    Useful for displaying the full strategy menu in the UI.
    """
    result = []
    for (direction, vol_regime), strategy in STRATEGY_MAP.items():
        entry = {
            "direction": direction,
            "vol_regime": vol_regime,
            **strategy,
        }
        result.append(entry)
    return result


def get_complexity_filter(max_complexity: str = "Intermediate") -> list[dict]:
    """
    Filter strategies by complexity level.

    Args:
        max_complexity: "Beginner" returns only beginner strategies.
                        "Intermediate" returns all (beginner + intermediate).

    Returns:
        List of matching strategy dicts.
    """
    complexity_rank = {"Beginner": 1, "Intermediate": 2, "Advanced": 3}
    max_rank = complexity_rank.get(max_complexity, 2)

    return [
        {"direction": d, "vol_regime": v, **s}
        for (d, v), s in STRATEGY_MAP.items()
        if complexity_rank.get(s["complexity"], 2) <= max_rank
    ]


# ── Module demo ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("ENSO STRATEGY MAP — All Strategies")
    print("=" * 60)

    for (direction, vol_regime), strategy in STRATEGY_MAP.items():
        print(f"\n[{direction} + {vol_regime}]")
        print(f"  Strategy    : {strategy['name']}")
        print(f"  Complexity  : {strategy['complexity']}")
        print(f"  Capital     : {strategy['capital_required']}")
        print(f"  Typical DTE : {strategy['typical_dte']}")
        print(f"  Description : {strategy['description'][:80]}...")

    print("\n" + "=" * 60)
    print("Beginner-only strategies:")
    print("=" * 60)
    for s in get_complexity_filter("Beginner"):
        print(f"  {s['direction']} + {s['vol_regime']} → {s['name']}")
