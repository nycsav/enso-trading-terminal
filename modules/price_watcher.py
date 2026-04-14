"""
price_watcher.py — Fibonacci Exit Automation for Enso

Monitors underlying stock prices and auto-exits option positions when
the underlying hits a target price (e.g., a Fibonacci resistance level
identified on ThinkOrSwim).

HOW IT WORKS:
    1. User buys an option on Public.com after identifying Fibonacci levels
    2. User tells Perplexity: "Watch NVDA at $142, sell my call when it hits"
    3. A Perplexity cron runs this module every 30 min during market hours
    4. When the underlying crosses the target, it places a LIMIT SELL on the option
    5. User gets a notification confirming the exit

COMPONENTS:
    PriceWatcher      — Core class that checks prices and triggers exits
    WatchlistEntry    — A single price alert with target + option details
    load_watchlist()  — Reads active alerts from JSON file
    save_watchlist()  — Persists alerts to JSON file

USAGE (standalone test):
    python3 -m modules.price_watcher --test

USAGE (from Perplexity cron):
    The cron calls check_all_alerts() which:
    - Loads watchlist from ~/enso-trading-terminal/price_watchlist.json
    - Checks each underlying price via Public.com API
    - If target hit → places sell order → marks alert as TRIGGERED
    - Returns summary of actions taken

DEPENDENCIES:
    publicdotcom-py, yfinance (fallback for price checks)

NOTE:
    This module NEVER auto-executes without the user first setting up
    the alert. The cron only monitors — the user controls what's watched.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Watchlist file location (on Mac Mini)
# ---------------------------------------------------------------------------
DEFAULT_WATCHLIST_PATH = os.path.expanduser(
    "~/enso-trading-terminal/price_watchlist.json"
)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class WatchlistEntry:
    """A single price-triggered exit alert."""

    # Identifiers
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # What to watch
    underlying_symbol: str = ""          # e.g. "NVDA"
    target_price: float = 0.0            # e.g. 142.00 (Fibonacci level)
    direction: str = "ABOVE"             # "ABOVE" = sell when price >= target
                                         # "BELOW" = sell when price <= target

    # What to sell
    option_symbol: str = ""              # OSI symbol, e.g. "NVDA260516C00135000"
    option_quantity: int = 1             # Number of contracts to sell
    order_type: str = "LIMIT"            # LIMIT (recommended) or MARKET
    limit_offset_pct: float = 2.0        # Sell limit = bid * (1 - offset%)
                                         # 2% below bid ensures fast fill

    # Context (for notifications)
    strategy_note: str = ""              # e.g. "Fibonacci resistance at $142"
    account_id: str = ""                 # Public.com account ID

    # State
    status: str = "ACTIVE"               # ACTIVE, TRIGGERED, CANCELLED, ERROR
    triggered_at: str = ""
    order_id: str = ""
    fill_price: float = 0.0
    error_message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "WatchlistEntry":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Watchlist persistence
# ---------------------------------------------------------------------------

def load_watchlist(path: str = DEFAULT_WATCHLIST_PATH) -> list[WatchlistEntry]:
    """Load watchlist from JSON file. Returns empty list if file missing."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return [WatchlistEntry.from_dict(entry) for entry in data]
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to load watchlist: {e}")
        return []


def save_watchlist(
    entries: list[WatchlistEntry], path: str = DEFAULT_WATCHLIST_PATH
) -> None:
    """Save watchlist to JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump([e.to_dict() for e in entries], f, indent=2)
    logger.info(f"Watchlist saved: {len(entries)} entries → {path}")


def add_alert(
    underlying_symbol: str,
    target_price: float,
    option_symbol: str,
    option_quantity: int = 1,
    direction: str = "ABOVE",
    order_type: str = "LIMIT",
    limit_offset_pct: float = 2.0,
    strategy_note: str = "",
    account_id: str = "",
    path: str = DEFAULT_WATCHLIST_PATH,
) -> WatchlistEntry:
    """Add a new price alert to the watchlist."""
    entry = WatchlistEntry(
        underlying_symbol=underlying_symbol.upper(),
        target_price=target_price,
        option_symbol=option_symbol.upper(),
        option_quantity=option_quantity,
        direction=direction.upper(),
        order_type=order_type.upper(),
        limit_offset_pct=limit_offset_pct,
        strategy_note=strategy_note,
        account_id=account_id or os.environ.get("PUBLIC_COM_ACCOUNT_ID", ""),
    )
    watchlist = load_watchlist(path)
    watchlist.append(entry)
    save_watchlist(watchlist, path)
    logger.info(
        f"Alert added: {entry.id} — {entry.underlying_symbol} "
        f"{entry.direction} ${entry.target_price:.2f} → sell {entry.option_symbol}"
    )
    return entry


def cancel_alert(alert_id: str, path: str = DEFAULT_WATCHLIST_PATH) -> bool:
    """Cancel an active alert by ID."""
    watchlist = load_watchlist(path)
    for entry in watchlist:
        if entry.id == alert_id and entry.status == "ACTIVE":
            entry.status = "CANCELLED"
            save_watchlist(watchlist, path)
            logger.info(f"Alert cancelled: {alert_id}")
            return True
    return False


# ---------------------------------------------------------------------------
# Price checking
# ---------------------------------------------------------------------------

def get_underlying_price(symbol: str) -> Optional[float]:
    """
    Get the current price of an underlying stock.

    Tries Public.com API first (via SDK), falls back to yfinance.
    Returns None if both fail.
    """
    # Method 1: Public.com SDK (preferred — uses same auth as order placement)
    price = _get_price_via_public_sdk(symbol)
    if price is not None:
        return price

    # Method 2: yfinance fallback (free, no auth needed)
    price = _get_price_via_yfinance(symbol)
    if price is not None:
        return price

    logger.error(f"Could not get price for {symbol} from any source")
    return None


def _get_price_via_public_sdk(symbol: str) -> Optional[float]:
    """Get price via Public.com SDK."""
    try:
        from public_api_sdk import (
            PublicApiClient,
            PublicApiClientConfiguration,
            OrderInstrument,
            InstrumentType,
        )
        from public_api_sdk.auth_config import ApiKeyAuthConfig

        secret = os.environ.get("PUBLIC_COM_SECRET")
        account_id = os.environ.get("PUBLIC_COM_ACCOUNT_ID")
        if not secret:
            return None

        client = PublicApiClient(
            ApiKeyAuthConfig(api_secret_key=secret),
            config=PublicApiClientConfiguration(
                default_account_number=account_id
            ),
        )
        client.api_client.session.headers["User-Agent"] = "enso-price-watcher/1.0"

        quotes = client.get_quotes([
            OrderInstrument(symbol=symbol, type=InstrumentType.EQUITY)
        ])
        client.close()

        if quotes and len(quotes) > 0:
            return float(quotes[0].last)
        return None
    except Exception as e:
        logger.debug(f"Public SDK price fetch failed for {symbol}: {e}")
        return None


def _get_price_via_yfinance(symbol: str) -> Optional[float]:
    """Get price via yfinance (free fallback)."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d")
        if not data.empty:
            return float(data["Close"].iloc[-1])
        return None
    except Exception as e:
        logger.debug(f"yfinance price fetch failed for {symbol}: {e}")
        return None


def get_option_bid(option_symbol: str) -> Optional[float]:
    """Get the current bid price for an option contract."""
    try:
        from public_api_sdk import (
            PublicApiClient,
            PublicApiClientConfiguration,
            OrderInstrument,
            InstrumentType,
        )
        from public_api_sdk.auth_config import ApiKeyAuthConfig

        secret = os.environ.get("PUBLIC_COM_SECRET")
        account_id = os.environ.get("PUBLIC_COM_ACCOUNT_ID")
        if not secret:
            return None

        client = PublicApiClient(
            ApiKeyAuthConfig(api_secret_key=secret),
            config=PublicApiClientConfiguration(
                default_account_number=account_id
            ),
        )
        client.api_client.session.headers["User-Agent"] = "enso-price-watcher/1.0"

        quotes = client.get_quotes([
            OrderInstrument(symbol=option_symbol, type=InstrumentType.OPTION)
        ])
        client.close()

        if quotes and len(quotes) > 0:
            q = quotes[0]
            # Prefer bid, fall back to last
            if hasattr(q, "bid") and q.bid is not None and float(q.bid) > 0:
                return float(q.bid)
            return float(q.last)
        return None
    except Exception as e:
        logger.debug(f"Option bid fetch failed for {option_symbol}: {e}")
        return None


# ---------------------------------------------------------------------------
# Order placement
# ---------------------------------------------------------------------------

def place_exit_order(entry: WatchlistEntry, option_bid: float) -> dict:
    """
    Place a sell order to exit the option position.

    Returns dict with order_id and status, or error info.
    """
    try:
        from public_api_sdk import (
            PublicApiClient,
            PublicApiClientConfiguration,
            OrderRequest,
            OrderInstrument,
            InstrumentType,
            OrderSide,
            OrderType,
            OrderExpirationRequest,
            TimeInForce,
            OpenCloseIndicator,
        )
        from public_api_sdk.auth_config import ApiKeyAuthConfig

        secret = os.environ.get("PUBLIC_COM_SECRET")
        account_id = entry.account_id or os.environ.get("PUBLIC_COM_ACCOUNT_ID")
        if not secret:
            return {"error": "PUBLIC_COM_SECRET not set"}

        client = PublicApiClient(
            ApiKeyAuthConfig(api_secret_key=secret),
            config=PublicApiClientConfiguration(
                default_account_number=account_id
            ),
        )
        client.api_client.session.headers["User-Agent"] = "enso-price-watcher/1.0"

        # Calculate limit price: bid minus offset for fast fill
        if entry.order_type == "LIMIT":
            offset_mult = 1 - (entry.limit_offset_pct / 100)
            limit_price = round(option_bid * offset_mult, 2)
            # Floor at $0.01
            limit_price = max(limit_price, 0.01)
            otype = OrderType.LIMIT
        else:
            limit_price = None
            otype = OrderType.MARKET

        order_kwargs = {
            "order_id": str(uuid.uuid4()),
            "instrument": OrderInstrument(
                symbol=entry.option_symbol,
                type=InstrumentType.OPTION,
            ),
            "order_side": OrderSide.SELL,
            "order_type": otype,
            "quantity": str(entry.option_quantity),
            "open_close_indicator": OpenCloseIndicator.CLOSE,
            "expiration": OrderExpirationRequest(
                time_in_force=TimeInForce.DAY
            ),
        }
        if limit_price is not None:
            order_kwargs["limit_price"] = Decimal(str(limit_price))

        order_request = OrderRequest(**order_kwargs)
        response = client.place_order(order_request)
        client.close()

        return {
            "order_id": response.order_id,
            "limit_price": limit_price,
            "status": "PLACED",
        }

    except Exception as e:
        logger.error(f"Exit order failed for {entry.option_symbol}: {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Core check loop — called by the Perplexity cron
# ---------------------------------------------------------------------------

def check_all_alerts(
    path: str = DEFAULT_WATCHLIST_PATH,
    dry_run: bool = False,
) -> list[dict]:
    """
    Check all active alerts. If any underlying hits its target, exit the option.

    Args:
        path: Path to watchlist JSON file
        dry_run: If True, don't place orders — just report what would happen

    Returns:
        List of action summaries (one per alert checked)
    """
    watchlist = load_watchlist(path)
    active = [e for e in watchlist if e.status == "ACTIVE"]

    if not active:
        return [{"message": "No active alerts"}]

    results = []

    for entry in active:
        # 1. Get current underlying price
        current_price = get_underlying_price(entry.underlying_symbol)
        if current_price is None:
            results.append({
                "alert_id": entry.id,
                "symbol": entry.underlying_symbol,
                "status": "SKIP",
                "reason": "Could not fetch price",
            })
            continue

        # 2. Check if target is hit
        triggered = False
        if entry.direction == "ABOVE" and current_price >= entry.target_price:
            triggered = True
        elif entry.direction == "BELOW" and current_price <= entry.target_price:
            triggered = True

        if not triggered:
            distance = abs(current_price - entry.target_price)
            distance_pct = (distance / entry.target_price) * 100
            results.append({
                "alert_id": entry.id,
                "symbol": entry.underlying_symbol,
                "option": entry.option_symbol,
                "current_price": current_price,
                "target_price": entry.target_price,
                "direction": entry.direction,
                "distance": f"${distance:.2f} ({distance_pct:.1f}%)",
                "status": "WATCHING",
            })
            continue

        # 3. TARGET HIT — get option bid and place exit order
        logger.info(
            f"TARGET HIT: {entry.underlying_symbol} @ ${current_price:.2f} "
            f"(target: ${entry.target_price:.2f} {entry.direction})"
        )

        if dry_run:
            results.append({
                "alert_id": entry.id,
                "symbol": entry.underlying_symbol,
                "option": entry.option_symbol,
                "current_price": current_price,
                "target_price": entry.target_price,
                "status": "DRY_RUN_TRIGGERED",
                "note": entry.strategy_note,
            })
            continue

        # Get option bid for limit price calculation
        option_bid = get_option_bid(entry.option_symbol)
        if option_bid is None or option_bid <= 0:
            entry.status = "ERROR"
            entry.error_message = "Could not get option bid price"
            results.append({
                "alert_id": entry.id,
                "symbol": entry.underlying_symbol,
                "option": entry.option_symbol,
                "status": "ERROR",
                "reason": "Could not get option bid — market may be closed",
            })
            continue

        # Place the exit order
        order_result = place_exit_order(entry, option_bid)

        if "error" in order_result:
            entry.status = "ERROR"
            entry.error_message = order_result["error"]
            results.append({
                "alert_id": entry.id,
                "symbol": entry.underlying_symbol,
                "option": entry.option_symbol,
                "status": "ERROR",
                "reason": order_result["error"],
            })
        else:
            entry.status = "TRIGGERED"
            entry.triggered_at = datetime.now(timezone.utc).isoformat()
            entry.order_id = order_result["order_id"]
            entry.fill_price = order_result.get("limit_price", 0)
            results.append({
                "alert_id": entry.id,
                "symbol": entry.underlying_symbol,
                "option": entry.option_symbol,
                "current_price": current_price,
                "target_price": entry.target_price,
                "order_id": order_result["order_id"],
                "limit_price": order_result.get("limit_price"),
                "status": "EXIT_ORDER_PLACED",
                "note": entry.strategy_note,
            })

    # Save updated statuses
    save_watchlist(watchlist, path)
    return results


# ---------------------------------------------------------------------------
# Human-readable summary (for cron notifications)
# ---------------------------------------------------------------------------

def format_summary(results: list[dict]) -> str:
    """Format check results into a notification-friendly summary."""
    if not results:
        return "Price Watcher: No alerts to check."

    triggered = [r for r in results if r.get("status") == "EXIT_ORDER_PLACED"]
    watching = [r for r in results if r.get("status") == "WATCHING"]
    errors = [r for r in results if r.get("status") == "ERROR"]
    skipped = [r for r in results if r.get("status") == "SKIP"]

    lines = []

    if triggered:
        lines.append("EXIT ORDERS PLACED:")
        for t in triggered:
            lines.append(
                f"  {t['symbol']} hit ${t['target_price']:.2f} "
                f"(now ${t['current_price']:.2f}) → "
                f"Selling {t['option']} at ~${t.get('limit_price', 'MKT')}"
            )
            if t.get("note"):
                lines.append(f"    Strategy: {t['note']}")
            lines.append(f"    Order ID: {t['order_id']}")

    if watching:
        lines.append(f"\nMONITORING ({len(watching)} alerts):")
        for w in watching:
            lines.append(
                f"  {w['symbol']}: ${w['current_price']:.2f} → "
                f"target ${w['target_price']:.2f} {w['direction']} "
                f"({w['distance']} away)"
            )

    if errors:
        lines.append(f"\nERRORS ({len(errors)}):")
        for e in errors:
            lines.append(f"  {e['symbol']}: {e.get('reason', 'Unknown error')}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI for testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="Enso Price Watcher")
    sub = parser.add_subparsers(dest="command")

    # Test command — dry run check
    test_parser = sub.add_parser("test", help="Run a dry-run check on all alerts")
    test_parser.add_argument("--path", default=DEFAULT_WATCHLIST_PATH)

    # Add command — add a new alert
    add_parser = sub.add_parser("add", help="Add a new price alert")
    add_parser.add_argument("--underlying", required=True, help="Underlying symbol (e.g. NVDA)")
    add_parser.add_argument("--target", required=True, type=float, help="Target price")
    add_parser.add_argument("--option", required=True, help="Option OSI symbol to sell")
    add_parser.add_argument("--quantity", type=int, default=1, help="Number of contracts")
    add_parser.add_argument("--direction", default="ABOVE", choices=["ABOVE", "BELOW"])
    add_parser.add_argument("--note", default="", help="Strategy note")
    add_parser.add_argument("--path", default=DEFAULT_WATCHLIST_PATH)

    # List command — show active alerts
    list_parser = sub.add_parser("list", help="List all alerts")
    list_parser.add_argument("--path", default=DEFAULT_WATCHLIST_PATH)

    # Cancel command
    cancel_parser = sub.add_parser("cancel", help="Cancel an alert")
    cancel_parser.add_argument("--id", required=True, help="Alert ID to cancel")
    cancel_parser.add_argument("--path", default=DEFAULT_WATCHLIST_PATH)

    # Check command — live check (places real orders if triggered!)
    check_parser = sub.add_parser("check", help="Live check — will place orders!")
    check_parser.add_argument("--path", default=DEFAULT_WATCHLIST_PATH)

    args = parser.parse_args()

    if args.command == "test":
        print("=" * 60)
        print("PRICE WATCHER — DRY RUN")
        print("=" * 60)
        results = check_all_alerts(path=args.path, dry_run=True)
        print(format_summary(results))

    elif args.command == "add":
        entry = add_alert(
            underlying_symbol=args.underlying,
            target_price=args.target,
            option_symbol=args.option,
            option_quantity=args.quantity,
            direction=args.direction,
            strategy_note=args.note,
            path=args.path,
        )
        print(f"Alert added: {entry.id}")
        print(f"  Watch: {entry.underlying_symbol} {entry.direction} ${entry.target_price:.2f}")
        print(f"  Sell:  {entry.option_symbol} x{entry.option_quantity}")
        if entry.strategy_note:
            print(f"  Note:  {entry.strategy_note}")

    elif args.command == "list":
        watchlist = load_watchlist(path=args.path)
        if not watchlist:
            print("No alerts configured.")
        else:
            print("=" * 60)
            print("PRICE WATCHER ALERTS")
            print("=" * 60)
            for e in watchlist:
                status_icon = {
                    "ACTIVE": "●",
                    "TRIGGERED": "✓",
                    "CANCELLED": "✗",
                    "ERROR": "!",
                }.get(e.status, "?")
                print(
                    f"  [{status_icon}] {e.id}: {e.underlying_symbol} "
                    f"{e.direction} ${e.target_price:.2f} → "
                    f"sell {e.option_symbol} x{e.option_quantity} "
                    f"[{e.status}]"
                )
                if e.strategy_note:
                    print(f"      Note: {e.strategy_note}")
                if e.triggered_at:
                    print(f"      Triggered: {e.triggered_at}")
                if e.order_id:
                    print(f"      Order ID: {e.order_id}")

    elif args.command == "cancel":
        if cancel_alert(args.id, path=args.path):
            print(f"Alert {args.id} cancelled.")
        else:
            print(f"Alert {args.id} not found or already inactive.")

    elif args.command == "check":
        print("=" * 60)
        print("PRICE WATCHER — LIVE CHECK")
        print("=" * 60)
        results = check_all_alerts(path=args.path, dry_run=False)
        print(format_summary(results))

    else:
        parser.print_help()
