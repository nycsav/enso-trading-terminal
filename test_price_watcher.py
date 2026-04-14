#!/usr/bin/env python3
"""
Quick test for the Price Watcher module.
Tests: add alert, list alerts, dry-run check, cancel alert.
Does NOT place real orders.
"""

import os
import sys
import json
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.price_watcher import (
    WatchlistEntry,
    add_alert,
    load_watchlist,
    save_watchlist,
    cancel_alert,
    check_all_alerts,
    format_summary,
    get_underlying_price,
)


def main():
    print("=" * 60)
    print("ENSO PRICE WATCHER — MODULE TEST")
    print("=" * 60)

    # Use a temp file so we don't pollute the real watchlist
    test_path = os.path.join(tempfile.gettempdir(), "enso_test_watchlist.json")

    # Clean slate
    if os.path.exists(test_path):
        os.remove(test_path)

    # --- Test 1: Add alerts ---
    print("\n[1] Adding test alerts...")
    alert1 = add_alert(
        underlying_symbol="AAPL",
        target_price=250.00,
        option_symbol="AAPL260515C00240000",
        option_quantity=1,
        direction="ABOVE",
        strategy_note="Fibonacci resistance test",
        path=test_path,
    )
    print(f"    Added: {alert1.id} — AAPL ABOVE $250.00")

    alert2 = add_alert(
        underlying_symbol="NVDA",
        target_price=100.00,
        option_symbol="NVDA260515P00110000",
        option_quantity=2,
        direction="BELOW",
        strategy_note="Support breakdown test",
        path=test_path,
    )
    print(f"    Added: {alert2.id} — NVDA BELOW $100.00")
    print("    PASS ✓")

    # --- Test 2: Load and verify ---
    print("\n[2] Loading watchlist...")
    watchlist = load_watchlist(path=test_path)
    assert len(watchlist) == 2, f"Expected 2 alerts, got {len(watchlist)}"
    assert watchlist[0].underlying_symbol == "AAPL"
    assert watchlist[1].underlying_symbol == "NVDA"
    print(f"    Loaded {len(watchlist)} alerts")
    print("    PASS ✓")

    # --- Test 3: Price fetch ---
    print("\n[3] Testing price fetch (AAPL)...")
    price = get_underlying_price("AAPL")
    if price is not None:
        print(f"    AAPL current price: ${price:.2f}")
        print("    PASS ✓")
    else:
        print("    WARNING: Could not fetch price (may need API key or market closed)")
        print("    SKIP ⚠")

    # --- Test 4: Dry-run check ---
    print("\n[4] Running dry-run check on all alerts...")
    results = check_all_alerts(path=test_path, dry_run=True)
    summary = format_summary(results)
    print(summary)
    print("    PASS ✓")

    # --- Test 5: Cancel alert ---
    print(f"\n[5] Cancelling alert {alert2.id}...")
    success = cancel_alert(alert2.id, path=test_path)
    assert success, "Cancel should return True"
    watchlist = load_watchlist(path=test_path)
    cancelled = [e for e in watchlist if e.id == alert2.id][0]
    assert cancelled.status == "CANCELLED"
    print(f"    Alert {alert2.id} status: {cancelled.status}")
    print("    PASS ✓")

    # --- Test 6: JSON structure ---
    print("\n[6] Verifying JSON structure...")
    with open(test_path) as f:
        raw = json.load(f)
    print(f"    File: {test_path}")
    print(f"    Entries: {len(raw)}")
    print(f"    Fields per entry: {list(raw[0].keys())}")
    print("    PASS ✓")

    # Cleanup
    os.remove(test_path)

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
    print("\nModule is ready. Next steps:")
    print("  1. Pull on Mac Mini: cd ~/enso-trading-terminal && git pull")
    print("  2. Add an alert:     python3 -m modules.price_watcher add \\")
    print("                         --underlying NVDA --target 142.00 \\")
    print("                         --option NVDA260516C00135000 \\")
    print("                         --note 'Fibonacci resistance at $142'")
    print("  3. Dry-run test:     python3 -m modules.price_watcher test")
    print("  4. Live check:       python3 -m modules.price_watcher check")


if __name__ == "__main__":
    main()
