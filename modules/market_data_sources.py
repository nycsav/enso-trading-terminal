"""
market_data_sources.py — External Data Source Integrations for Enso

Two integrations that feed real market data into the agent framework:

1. FlashAlpha GEX/Exposure API
   - Gamma exposure (GEX) by strike — dealer hedging pressure
   - Key levels: gamma flip, call wall, put wall, max pain
   - Dealer regime classification (positive/negative gamma)
   - Free tier: 5 requests/day, covers GEX + key levels for individual equities
   - Auth: X-Api-Key header
   - SDK: pip install flashalpha

2. Finviz Unusual Volume Scanner
   - Scans for stocks with abnormal trading volume vs their historical average
   - Filters: large-cap, optionable, price > $10
   - Used as a "Layer 0" watchlist generator — replaces hardcoded ticker lists
   - Library: pip install finvizfinance

USAGE:
    # FlashAlpha — get GEX data for a single symbol
    fa = FlashAlphaSource(api_key="YOUR_KEY")
    gex = fa.get_gex("SPY")
    print(gex["gamma_regime"])  # "POSITIVE" or "NEGATIVE"

    # Finviz — get today's unusual volume tickers
    fv = FinvizVolumeScanner()
    tickers = fv.scan()
    print(tickers)  # ["AAPL", "NVDA", "TSLA", ...]

    # Combined: use Finviz to find tickers, then FlashAlpha to analyze them
    pipeline_watchlist = fv.scan(max_tickers=10)
    for ticker in pipeline_watchlist:
        gex = fa.get_gex(ticker)
        print(f"{ticker}: {gex['gamma_regime']}")

DEPENDENCIES:
    pip install flashalpha finvizfinance requests

NOTE:
    FlashAlpha free tier = 5 req/day (10 on some docs). The morning cron
    should budget these carefully — scan top 3-5 tickers, not 50.
    For higher volume, upgrade to Basic ($79/mo, 100 req/day).
"""

from __future__ import annotations

import os
import datetime
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# FLASHALPHA GEX / EXPOSURE API
# ══════════════════════════════════════════════════════════════════════════════

class FlashAlphaSource:
    """
    Client for the FlashAlpha Lab API — real-time options exposure analytics.

    Provides:
        - Per-strike gamma exposure (GEX) with call/put breakdown
        - Gamma flip level (where net GEX crosses zero)
        - Net GEX regime (positive or negative gamma)
        - Call wall and put wall strike levels
        - Dealer positioning context for options strategy selection

    Free tier: 5 requests/day, no credit card, GEX + key levels for
    individual US equities. ETFs (SPY, QQQ) require Basic plan ($79/mo).

    Sign up: https://flashalpha.com/pricing
    Docs:    https://flashalpha.com/docs/lab-api-gex

    Auth:
        Pass your API key via constructor or FLASHALPHA_API_KEY env var.
        Key goes in the X-Api-Key header on every request.

    Endpoints used:
        GET /v1/exposure/gex/{symbol}     — per-strike gamma exposure
        GET /v1/exposure/levels/{symbol}  — gamma flip, call/put walls (if available)
    """

    BASE_URL = "https://lab.flashalpha.com"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the FlashAlpha client.

        Args:
            api_key: FlashAlpha API key. Falls back to FLASHALPHA_API_KEY env var.

        Raises:
            ValueError: If no API key provided and env var not set.
        """
        self.api_key = api_key or os.environ.get("FLASHALPHA_API_KEY", "")
        if not self.api_key:
            logger.warning(
                "FlashAlpha API key not configured. "
                "Set FLASHALPHA_API_KEY env var or pass api_key to constructor. "
                "Sign up free at https://flashalpha.com/pricing"
            )

    @property
    def _headers(self) -> dict:
        return {"X-Api-Key": self.api_key}

    @property
    def is_configured(self) -> bool:
        """Check if an API key is available."""
        return bool(self.api_key)

    def get_gex(self, symbol: str, expiration: Optional[str] = None, auto_expiry: bool = True) -> dict:
        """
        Fetch gamma exposure (GEX) data for a symbol.

        Args:
            symbol:     Ticker symbol (e.g., "SPY", "AAPL", "NVDA")
            expiration: Optional expiry filter (YYYY-MM-DD). Required on
                        free tier — full-chain GEX needs Growth plan.
            auto_expiry: If True and no expiration given, automatically uses
                         the nearest Friday as expiry (free tier workaround).

        Returns:
            {
                "symbol":           str  — ticker
                "underlying_price": float — current price
                "gamma_flip":       float — strike where net GEX crosses zero
                "net_gex":          int   — aggregate net gamma exposure ($)
                "gamma_regime":     str   — "POSITIVE" or "NEGATIVE"
                "regime_note":      str   — plain-English interpretation
                "call_wall":        float — strike with highest call GEX (approx)
                "put_wall":         float — strike with highest put GEX (approx)
                "top_strikes":      list  — top 5 strikes by absolute net GEX
                "as_of":            str   — ISO timestamp of data
                "source":           str   — "flashalpha"
                "error":            str|None
            }
        """
        result = {
            "symbol": symbol.upper(),
            "underlying_price": 0.0,
            "gamma_flip": 0.0,
            "net_gex": 0,
            "gamma_regime": "UNKNOWN",
            "regime_note": "GEX data unavailable",
            "call_wall": 0.0,
            "put_wall": 0.0,
            "top_strikes": [],
            "as_of": "",
            "source": "flashalpha",
            "error": None,
        }

        if not self.is_configured:
            result["error"] = "FlashAlpha API key not configured"
            return result

        try:
            url = f"{self.BASE_URL}/v1/exposure/gex/{symbol.upper()}"
            params = {}
            if expiration:
                params["expiration"] = expiration
            elif auto_expiry:
                # Free tier requires a single expiry filter.
                # Auto-select nearest Friday (most liquid weekly expiry).
                today = datetime.date.today()
                days_ahead = 4 - today.weekday()  # Friday = 4
                if days_ahead <= 0:
                    days_ahead += 7
                nearest_friday = today + datetime.timedelta(days=days_ahead)
                params["expiration"] = nearest_friday.strftime("%Y-%m-%d")
                logger.info(
                    f"FlashAlpha: auto-selecting expiry {params['expiration']} "
                    f"for free tier (use expiration= to override)"
                )

            resp = requests.get(url, headers=self._headers, params=params, timeout=15)

            # If 403 with auto-expiry, try without (in case user has paid plan)
            if resp.status_code == 403 and auto_expiry and not expiration:
                logger.info("FlashAlpha: 403 with auto-expiry, retrying without filter...")
                resp = requests.get(
                    url, headers=self._headers, timeout=15
                )

            if resp.status_code == 403:
                result["error"] = (
                    f"FlashAlpha 403: {symbol} may require a paid plan "
                    "(ETFs/indices need Basic tier). "
                    "Try individual equities on free tier."
                )
                return result

            if resp.status_code == 404:
                result["error"] = f"FlashAlpha 404: No GEX data for {symbol}"
                return result

            resp.raise_for_status()
            data = resp.json()

            # Parse core fields
            underlying_price = float(data.get("underlying_price", 0))
            gamma_flip = float(data.get("gamma_flip", 0))
            net_gex = int(data.get("net_gex", 0))
            net_gex_label = data.get("net_gex_label", "")

            # Determine regime
            if net_gex_label:
                gamma_regime = net_gex_label.upper()
            elif underlying_price > 0 and gamma_flip > 0:
                gamma_regime = "POSITIVE" if underlying_price > gamma_flip else "NEGATIVE"
            else:
                gamma_regime = "UNKNOWN"

            # Build regime interpretation
            if gamma_regime == "POSITIVE":
                regime_note = (
                    f"Price (${underlying_price:.2f}) above gamma flip "
                    f"(${gamma_flip:.2f}) — dealers hedging dampens moves. "
                    "Stock tends to mean-revert. Favor selling premium."
                )
            elif gamma_regime == "NEGATIVE":
                regime_note = (
                    f"Price (${underlying_price:.2f}) below gamma flip "
                    f"(${gamma_flip:.2f}) — dealers hedging amplifies moves. "
                    "Stock can make outsized moves. Favor directional plays or wider strikes."
                )
            else:
                regime_note = "Unable to determine gamma regime"

            # Parse per-strike data for call/put walls
            strikes = data.get("strikes", [])
            call_wall = 0.0
            put_wall = 0.0
            top_strikes = []

            if strikes:
                # Find call wall (strike with highest call GEX)
                call_max = max(strikes, key=lambda s: abs(s.get("call_gex", 0)))
                call_wall = float(call_max.get("strike", 0))

                # Find put wall (strike with highest put GEX)
                put_max = max(strikes, key=lambda s: abs(s.get("put_gex", 0)))
                put_wall = float(put_max.get("strike", 0))

                # Top 5 strikes by absolute net GEX
                sorted_strikes = sorted(
                    strikes,
                    key=lambda s: abs(s.get("net_gex", 0)),
                    reverse=True,
                )[:5]
                top_strikes = [
                    {
                        "strike": s.get("strike"),
                        "net_gex": s.get("net_gex"),
                        "call_oi": s.get("call_oi", 0),
                        "put_oi": s.get("put_oi", 0),
                        "call_volume": s.get("call_volume", 0),
                        "put_volume": s.get("put_volume", 0),
                    }
                    for s in sorted_strikes
                ]

            result.update({
                "underlying_price": underlying_price,
                "gamma_flip": gamma_flip,
                "net_gex": net_gex,
                "gamma_regime": gamma_regime,
                "regime_note": regime_note,
                "call_wall": call_wall,
                "put_wall": put_wall,
                "top_strikes": top_strikes,
                "as_of": data.get("as_of", ""),
            })

        except requests.exceptions.Timeout:
            result["error"] = f"FlashAlpha timeout for {symbol}"
        except requests.exceptions.RequestException as e:
            result["error"] = f"FlashAlpha request error: {str(e)}"
        except (KeyError, ValueError, TypeError) as e:
            result["error"] = f"FlashAlpha parse error: {str(e)}"

        return result

    def get_exposure_summary(self, symbol: str) -> dict:
        """
        Fetch a simplified exposure summary — primarily for the VolatilityAgent.

        Returns a flattened dict with the most decision-relevant fields:
            gamma_regime, gamma_flip, call_wall, put_wall, underlying_price

        This is what the VolatilityAgent should call to augment its analysis.
        """
        gex = self.get_gex(symbol)

        return {
            "symbol": gex["symbol"],
            "gamma_regime": gex["gamma_regime"],
            "gamma_flip": gex["gamma_flip"],
            "underlying_price": gex["underlying_price"],
            "call_wall": gex["call_wall"],
            "put_wall": gex["put_wall"],
            "net_gex": gex["net_gex"],
            "regime_note": gex["regime_note"],
            "gex_available": gex["error"] is None,
            "error": gex["error"],
        }


# ══════════════════════════════════════════════════════════════════════════════
# FINVIZ UNUSUAL VOLUME SCANNER
# ══════════════════════════════════════════════════════════════════════════════

class FinvizVolumeScanner:
    """
    Scans Finviz for stocks with unusual trading volume.

    Unusual volume = current volume significantly above the stock's
    historical daily average. This often precedes or accompanies a
    major news event or institutional repositioning.

    Uses the finvizfinance Python library to apply filters:
        - Signal: Unusual Volume
        - Optionable: Yes (we need options to trade)
        - Price: Over $10 (avoid penny stocks)
        - Average Volume: Over 1M (liquidity for options)

    The scanner returns a ranked list of tickers that the morning
    cron can feed into the full agent pipeline as a dynamic watchlist.

    Install: pip install finvizfinance
    Source:  https://github.com/lit26/finvizfinance
    """

    # Default filters for the unusual volume scan
    DEFAULT_FILTERS = {
        "Option/Short": "Optionable",
        "Price": "Over $10",
        "Average Volume": "Over 1M",
    }
    DEFAULT_SIGNAL = "Unusual Volume"

    def __init__(self, filters: Optional[dict] = None, signal: Optional[str] = None):
        """
        Initialize the scanner with optional custom filters.

        Args:
            filters: Dict of Finviz filter name → value. Defaults to
                     large-cap, optionable, price > $10, avg vol > 1M.
            signal:  Finviz signal to use. Default: "Unusual Volume".
        """
        self.filters = filters or self.DEFAULT_FILTERS.copy()
        self.signal = signal or self.DEFAULT_SIGNAL

    def scan(self, max_tickers: int = 15) -> list[dict]:
        """
        Run the Finviz unusual volume scan and return ranked tickers.

        Args:
            max_tickers: Maximum number of tickers to return (default 15).
                         The morning cron should use 5-10 to stay within
                         FlashAlpha's free tier API limits.

        Returns:
            List of dicts, each containing:
            {
                "ticker":        str   — stock symbol
                "company":       str   — company name
                "price":         float — current price
                "change":        float — % change today
                "volume":        int   — current volume
                "rel_volume":    float — relative volume (vs avg), if available
                "sector":        str   — market sector
                "source":        str   — "finviz"
                "scan_time":     str   — ISO timestamp
            }

            Returns empty list if finvizfinance is not installed or scan fails.
        """
        try:
            from finvizfinance.screener.overview import Overview
        except ImportError:
            logger.error(
                "finvizfinance not installed. Run: pip install finvizfinance"
            )
            return []

        scan_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

        try:
            screener = Overview()
            screener.set_filter(
                signal=self.signal,
                filters_dict=self.filters,
            )
            df = screener.screener_view()

            if df is None or df.empty:
                logger.info("Finviz unusual volume scan returned no results")
                return []

            results = []
            for _, row in df.head(max_tickers).iterrows():
                ticker_data = {
                    "ticker": str(row.get("Ticker", "")),
                    "company": str(row.get("Company", "")),
                    "price": _safe_float(row.get("Price", 0)),
                    "change": _safe_percent(row.get("Change", "0%")),
                    "volume": _safe_int(row.get("Volume", 0)),
                    "rel_volume": _safe_float(row.get("Relative Volume", 0)),
                    "sector": str(row.get("Sector", "")),
                    "source": "finviz",
                    "scan_time": scan_time,
                }
                if ticker_data["ticker"]:
                    results.append(ticker_data)

            logger.info(
                f"Finviz unusual volume scan: {len(results)} tickers found "
                f"(from {len(df)} total matches)"
            )
            return results

        except Exception as e:
            logger.error(f"Finviz scan error: {e}")
            return []

    def scan_tickers_only(self, max_tickers: int = 10) -> list[str]:
        """
        Convenience method: return just the ticker symbols as a list.

        This is what the morning cron passes as the pipeline watchlist.

        Args:
            max_tickers: Maximum tickers to return.

        Returns:
            List of ticker strings, e.g. ["AAPL", "NVDA", "TSLA"]
        """
        results = self.scan(max_tickers=max_tickers)
        return [r["ticker"] for r in results if r.get("ticker")]

    def scan_with_fallback(
        self,
        max_tickers: int = 10,
        fallback_watchlist: Optional[list[str]] = None,
    ) -> list[str]:
        """
        Scan for unusual volume tickers, falling back to a default list
        if the scan returns no results or fails.

        This ensures the morning cron always has a watchlist to work with.

        Args:
            max_tickers:       Maximum tickers from Finviz scan.
            fallback_watchlist: Default tickers if scan fails.
                                Defaults to major large-cap names.

        Returns:
            List of ticker strings.
        """
        if fallback_watchlist is None:
            fallback_watchlist = [
                "SPY", "QQQ", "AAPL", "NVDA", "TSLA",
                "META", "MSFT", "AMZN", "GOOGL", "AMD",
            ]

        tickers = self.scan_tickers_only(max_tickers=max_tickers)

        if not tickers:
            logger.info(
                f"Finviz scan returned no results — using fallback watchlist: "
                f"{fallback_watchlist[:max_tickers]}"
            )
            return fallback_watchlist[:max_tickers]

        return tickers


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _safe_float(val) -> float:
    """Convert a value to float, returning 0.0 on failure."""
    try:
        if isinstance(val, str):
            val = val.replace(",", "").replace("$", "").strip()
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _safe_int(val) -> int:
    """Convert a value to int, returning 0 on failure."""
    try:
        if isinstance(val, str):
            val = val.replace(",", "").strip()
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def _safe_percent(val) -> float:
    """Convert a percentage string like '5.25%' to float 5.25."""
    try:
        if isinstance(val, str):
            val = val.replace("%", "").replace(",", "").strip()
        return float(val)
    except (ValueError, TypeError):
        return 0.0


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE DEMO
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║       ENSO MARKET DATA SOURCES — Integration Test       ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # ── Finviz Unusual Volume ─────────────────────────────────────────
    print("\n── Finviz Unusual Volume Scanner ──────────────────────────")
    scanner = FinvizVolumeScanner()
    print("Scanning for unusual volume tickers...")
    tickers = scanner.scan(max_tickers=5)

    if tickers:
        print(f"\nTop {len(tickers)} unusual volume stocks:")
        for t in tickers:
            print(
                f"  {t['ticker']:>6s}  ${t['price']:>8.2f}  "
                f"{t['change']:>+6.2f}%  "
                f"Vol: {t['volume']:>12,}  "
                f"RelVol: {t['rel_volume']:.2f}  "
                f"({t['sector']})"
            )
    else:
        print("  No unusual volume tickers found (or finvizfinance not installed)")

    # ── FlashAlpha GEX ────────────────────────────────────────────────
    print("\n── FlashAlpha GEX Scanner ─────────────────────────────────")
    fa = FlashAlphaSource()

    if fa.is_configured:
        # Test with a single equity (free tier friendly)
        test_symbol = "AAPL"
        print(f"Fetching GEX data for {test_symbol}...")
        gex = fa.get_gex(test_symbol)

        if gex["error"]:
            print(f"  Error: {gex['error']}")
        else:
            print(f"  Symbol:          {gex['symbol']}")
            print(f"  Price:           ${gex['underlying_price']:.2f}")
            print(f"  Gamma Flip:      ${gex['gamma_flip']:.2f}")
            print(f"  Net GEX:         ${gex['net_gex']:,.0f}")
            print(f"  Gamma Regime:    {gex['gamma_regime']}")
            print(f"  Call Wall:       ${gex['call_wall']:.2f}")
            print(f"  Put Wall:        ${gex['put_wall']:.2f}")
            print(f"  Regime Note:     {gex['regime_note']}")
            if gex["top_strikes"]:
                print(f"  Top Strikes:")
                for s in gex["top_strikes"][:3]:
                    print(
                        f"    ${s['strike']:>8.1f}  "
                        f"Net GEX: ${s['net_gex']:>12,}  "
                        f"Call OI: {s['call_oi']:>6,}  "
                        f"Put OI: {s['put_oi']:>6,}"
                    )
    else:
        print("  FlashAlpha not configured — set FLASHALPHA_API_KEY env var")
        print("  Sign up free at https://flashalpha.com/pricing")
        print("  (No credit card required)")

    print("\n── Done ──────────────────────────────────────────────────")
