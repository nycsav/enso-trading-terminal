#!/usr/bin/env python3
"""
Unit tests for modules/signal_filters.py — TimeOfDayFilter, FailedBreakdownFilter, FilterChain.
No network. No real orders.
"""
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.signal_filters import (  # noqa: E402
    ET,
    FailedBreakdownFilter,
    FilterChain,
    TimeOfDayFilter,
    default_chain,
)


def _et(year, month, day, hour, minute):
    return datetime(year, month, day, hour, minute, tzinfo=ET)


def _bars(rows):
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"])


failures: list[str] = []


def check(cond, label):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        failures.append(label)


# ---------------------------------------------------------------------------
# TimeOfDayFilter
# ---------------------------------------------------------------------------
def test_time_of_day():
    print("\n[TimeOfDayFilter]")
    f = TimeOfDayFilter()

    # Open window (09:45 ET Tuesday) — should block
    r = f.apply({"timestamp": _et(2026, 4, 14, 9, 45)})
    check(not r.allow and "open" in r.metadata.get("window", ""), "blocks first 30 min after open")

    # Close window (15:50 ET Tuesday) — should block
    r = f.apply({"timestamp": _et(2026, 4, 14, 15, 50)})
    check(not r.allow and "close" in r.metadata.get("window", ""), "blocks last 15 min before close")

    # Mid-session (11:00 ET Tuesday) — allow
    r = f.apply({"timestamp": _et(2026, 4, 14, 11, 0)})
    check(r.allow, "allows mid-session bars")

    # Weekend (Saturday) — block
    r = f.apply({"timestamp": _et(2026, 4, 18, 11, 0)})
    check(not r.allow and r.reason == "weekend", "blocks weekends")

    # Pre-market (08:00 ET) — block
    r = f.apply({"timestamp": _et(2026, 4, 14, 8, 0)})
    check(not r.allow and r.reason == "outside_rth", "blocks pre-market")

    # Post-close (17:00 ET) — block
    r = f.apply({"timestamp": _et(2026, 4, 14, 17, 0)})
    check(not r.allow and r.reason == "outside_rth", "blocks post-close")

    # Econ release within ±30 min — block
    release = _et(2026, 4, 14, 11, 0)
    r = f.apply(
        {"timestamp": _et(2026, 4, 14, 10, 45)},
        {"econ_releases": [release]},
    )
    check(not r.allow and "economic release" in r.reason, "blocks near econ release")

    # UTC timestamp converts correctly (15:00 UTC = 11:00 ET in April)
    utc_ts = datetime(2026, 4, 14, 15, 0, tzinfo=ZoneInfo("UTC"))
    r = f.apply({"timestamp": utc_ts})
    check(r.allow, "DST-correct UTC→ET conversion")

    # Naive datetime assumed ET
    r = f.apply({"timestamp": datetime(2026, 4, 14, 11, 0)})
    check(r.allow, "naive datetime treated as ET")


# ---------------------------------------------------------------------------
# FailedBreakdownFilter
# ---------------------------------------------------------------------------
def test_failed_breakdown():
    print("\n[FailedBreakdownFilter]")
    f = FailedBreakdownFilter(lookback_bars=3, tolerance_pct=0.1)
    support = 100.0

    # Bar pierces support (Low 99.5) then closes above (100.5) → detected
    bars = _bars([
        (101, 102, 100.5, 101.5),
        (101, 101.5, 99.5, 100.5),
        (100.6, 101, 100.2, 100.8),
    ])
    hit = f.detect(bars, support)
    check(hit is not None and hit["low"] == 99.5, "detects pierce + recovery")

    # No pierce (Low stays above support) → not detected
    bars_clean = _bars([
        (101, 102, 100.5, 101.5),
        (101, 101.5, 100.3, 100.9),
        (100.6, 101, 100.2, 100.8),
    ])
    check(f.detect(bars_clean, support) is None, "no false positive when no pierce")

    # Bar breaks and stays below (Close 99.8) → not a failed breakdown
    bars_breakdown = _bars([
        (101, 102, 100.5, 101.5),
        (100.5, 100.7, 99.5, 99.8),
        (99.7, 99.9, 99.2, 99.5),
    ])
    check(f.detect(bars_breakdown, support) is None, "real breakdown not flagged as failed")

    # Bearish signal with failed breakdown → blocked
    bars_hit = _bars([(100.5, 100.5, 99.5, 100.5)])
    r = f.apply({"direction": "BEARISH"}, {"bars": bars_hit, "support_price": support})
    check(not r.allow and r.metadata.get("failed_breakdown"), "blocks bearish signal on failed breakdown")

    # Bullish signal with failed breakdown → allowed with reversal tag
    r = f.apply({"direction": "BULLISH"}, {"bars": bars_hit, "support_price": support})
    check(
        r.allow and r.metadata.get("reversal_confirmation"),
        "tags bullish signal with reversal confirmation",
    )

    # Missing context → skipped (allow with note)
    r = f.apply({"direction": "BULLISH"}, None)
    check(r.allow and "no context" in r.reason, "skips gracefully on missing context")

    # Lookback bounds — pierce outside window should not trigger
    f_short = FailedBreakdownFilter(lookback_bars=1, tolerance_pct=0.1)
    bars_old = _bars([
        (100.5, 100.5, 99.5, 100.5),
        (100.6, 101, 100.2, 100.8),
    ])
    check(f_short.detect(bars_old, support) is None, "respects lookback window")


# ---------------------------------------------------------------------------
# FilterChain
# ---------------------------------------------------------------------------
def test_chain():
    print("\n[FilterChain]")
    chain = default_chain()

    # Mid-session bullish with failed breakdown → pass
    bars_hit = _bars([(100.5, 100.5, 99.5, 100.5)])
    r = chain.apply(
        {"direction": "BULLISH", "timestamp": _et(2026, 4, 14, 11, 0)},
        {"bars": bars_hit, "support_price": 100.0},
    )
    check(r.allow, "chain allows valid bullish reversal mid-session")
    check(r.metadata.get("failed_breakdown", {}).get("reversal_confirmation"), "chain propagates metadata")

    # Open window short-circuits before failed_breakdown runs
    r = chain.apply(
        {"direction": "BULLISH", "timestamp": _et(2026, 4, 14, 9, 45)},
        {"bars": bars_hit, "support_price": 100.0},
    )
    check(not r.allow and r.reason.startswith("time_of_day"), "chain short-circuits on first reject")
    check("failed_breakdown" not in r.metadata, "later filters skipped after short-circuit")


def main():
    print("=" * 60)
    print("SIGNAL FILTERS — UNIT TESTS")
    print("=" * 60)
    test_time_of_day()
    test_failed_breakdown()
    test_chain()
    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED: {len(failures)} test(s)")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
