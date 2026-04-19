"""
Signal Filters
Composable gates applied to strategy signals before they reach risk/execution.

Filters:
    TimeOfDayFilter      — blocks signals in the first N minutes after open and
                           the last M minutes before close (ET, DST-safe).
    FailedBreakdownFilter — detects when price broke below a support level but
                           closed back above within a lookback window; blocks
                           bearish signals and tags bullish signals as
                           reversal candidates.

Filters return FilterResult(allow, reason, metadata). A FilterChain short-
circuits on the first reject.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo

import pandas as pd

import config as cfg


ET = ZoneInfo("America/New_York")


@dataclass
class FilterResult:
    allow: bool
    reason: str = ""
    metadata: dict = field(default_factory=dict)


class SignalFilter:
    """Base class. Subclasses override apply()."""
    name = "filter"

    def apply(self, signal: dict, context: Optional[dict] = None) -> FilterResult:  # pragma: no cover - abstract
        raise NotImplementedError


class TimeOfDayFilter(SignalFilter):
    name = "time_of_day"

    def __init__(
        self,
        open_buffer_min: int = cfg.TOD_OPEN_BUFFER_MIN,
        close_buffer_min: int = cfg.TOD_CLOSE_BUFFER_MIN,
        econ_release_buffer_min: int = cfg.TOD_ECON_RELEASE_BUFFER_MIN,
    ):
        self.open_buffer = timedelta(minutes=open_buffer_min)
        self.close_buffer = timedelta(minutes=close_buffer_min)
        self.econ_buffer = timedelta(minutes=econ_release_buffer_min)

    def _to_et(self, ts: datetime) -> datetime:
        if ts.tzinfo is None:
            return ts.replace(tzinfo=ET)
        return ts.astimezone(ET)

    def _market_bounds(self, ts_et: datetime) -> tuple[datetime, datetime]:
        open_dt = ts_et.replace(
            hour=cfg.MARKET_OPEN_HOUR, minute=cfg.MARKET_OPEN_MIN, second=0, microsecond=0
        )
        close_dt = ts_et.replace(
            hour=cfg.MARKET_CLOSE_HOUR, minute=cfg.MARKET_CLOSE_MIN, second=0, microsecond=0
        )
        return open_dt, close_dt

    def apply(self, signal: dict, context: Optional[dict] = None) -> FilterResult:
        ts = signal.get("timestamp") or (context or {}).get("now") or datetime.now(ET)
        ts_et = self._to_et(ts)

        if ts_et.weekday() >= 5:
            return FilterResult(False, "weekend", {"time_et": ts_et.isoformat()})

        open_dt, close_dt = self._market_bounds(ts_et)

        if ts_et < open_dt or ts_et >= close_dt:
            return FilterResult(False, "outside_rth", {"time_et": ts_et.isoformat()})

        if ts_et < open_dt + self.open_buffer:
            return FilterResult(
                False,
                f"within {self.open_buffer.seconds // 60}min of open",
                {"time_et": ts_et.isoformat(), "window": "open"},
            )

        if ts_et >= close_dt - self.close_buffer:
            return FilterResult(
                False,
                f"within {self.close_buffer.seconds // 60}min of close",
                {"time_et": ts_et.isoformat(), "window": "close"},
            )

        econ_releases: Iterable[datetime] = (context or {}).get("econ_releases", [])
        for release in econ_releases:
            release_et = self._to_et(release)
            if abs((ts_et - release_et).total_seconds()) <= self.econ_buffer.total_seconds():
                return FilterResult(
                    False,
                    "near economic release",
                    {"time_et": ts_et.isoformat(), "release": release_et.isoformat()},
                )

        return FilterResult(True, "", {"time_et": ts_et.isoformat()})


class FailedBreakdownFilter(SignalFilter):
    """
    Detects failed breakdowns on a recent window of bars.

    A failed breakdown is a bar whose Low pierced a support level but whose
    Close recovered back above that support. It signals trapped shorts and
    supports bullish continuation while invalidating fresh bearish entries.
    """
    name = "failed_breakdown"

    def __init__(
        self,
        lookback_bars: int = cfg.FAILED_BREAKDOWN_LOOKBACK,
        tolerance_pct: float = cfg.FAILED_BREAKDOWN_TOLERANCE_PCT,
    ):
        self.lookback = lookback_bars
        self.tolerance = tolerance_pct / 100.0

    def detect(self, bars: pd.DataFrame, support_price: float) -> Optional[dict]:
        if bars is None or bars.empty or support_price <= 0:
            return None
        window = bars.tail(self.lookback)
        floor = support_price * (1.0 - self.tolerance)
        ceiling = support_price
        for idx, row in window.iterrows():
            if row["Low"] < floor and row["Close"] > ceiling:
                return {
                    "bar_index": idx,
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "support": float(support_price),
                    "recovery_pct": float((row["Close"] - row["Low"]) / row["Low"] * 100),
                }
        return None

    def apply(self, signal: dict, context: Optional[dict] = None) -> FilterResult:
        ctx = context or {}
        bars = ctx.get("bars") if ctx.get("bars") is not None else signal.get("bars")
        support = ctx.get("support_price") if ctx.get("support_price") is not None else signal.get("support_price")
        if bars is None or support is None:
            return FilterResult(True, "no context; skipped", {})

        hit = self.detect(bars, float(support))
        direction = (signal.get("direction") or "").upper()

        if hit is None:
            return FilterResult(True, "", {"failed_breakdown": False})

        if direction == "BEARISH":
            return FilterResult(
                False,
                "failed breakdown detected (trapped shorts) — bearish entry blocked",
                {"failed_breakdown": True, **hit},
            )

        return FilterResult(
            True,
            "failed breakdown — bullish reversal confirmation",
            {"failed_breakdown": True, "reversal_confirmation": True, **hit},
        )


class FilterChain:
    """Applies filters in order; short-circuits on first reject."""

    def __init__(self, filters: Iterable[SignalFilter]):
        self.filters = list(filters)

    def apply(self, signal: dict, context: Optional[dict] = None) -> FilterResult:
        metadata: dict[str, Any] = {}
        for f in self.filters:
            result = f.apply(signal, context)
            metadata[f.name] = {
                "allow": result.allow,
                "reason": result.reason,
                **result.metadata,
            }
            if not result.allow:
                return FilterResult(False, f"{f.name}: {result.reason}", metadata)
        return FilterResult(True, "", metadata)


def default_chain() -> FilterChain:
    return FilterChain([TimeOfDayFilter(), FailedBreakdownFilter()])
