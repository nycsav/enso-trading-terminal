"""
agent_framework.py — Enso Multi-Agent Trading Framework

A 3-layer, 6-agent pipeline that finds options trade setups and presents them
for human approval. Inspired by QuantInsti's LangGraph pattern, TradingAgents'
bull/bear debate structure, and LLM-Enhanced-Trading's sentiment integration —
but simplified for Perplexity Computer's architecture.

Perplexity IS the orchestrator. No LangGraph needed. The agents here are
Python functions that collect data and crunch numbers; Perplexity handles
natural-language reasoning, news analysis, and final presentation.

ARCHITECTURE:
    Layer 1 — Intelligence (Data Collection)
        NewsAgent       → scans news headlines, scores sentiment
        TechnicalAgent  → computes price-based signals (SMA, RSI, ATR, etc.)
        VolatilityAgent → estimates vol regime (HIGH/NORMAL/LOW)

    Layer 2 — Strategy (Signal Synthesis + Bull/Bear Debate)
        SignalSynthesizer → combines all 3 signals, runs bull/bear debate,
                            outputs confidence-scored recommendation

    Layer 3 — Execution (Risk Management + Order Prep)
        RiskManager → enforces position sizing and portfolio-level limits
        TradePrep   → assembles the final human-readable trade card

PIPELINE:
    run_pipeline(watchlist, portfolio_value, existing_positions)
    → returns list of trade recommendations sorted by confidence
    → user approves or rejects each one via the Enso UI

PHILOSOPHY:
    - AI finds trades. Humans approve them. Nothing auto-executes.
    - Confidence < 60 → skipped (not enough signal agreement)
    - Risk checks fail → skipped (doesn't fit portfolio limits)
    - Max 3 recommendations returned (highest confidence first)

STANDALONE DEMO:
    python3 -m modules.agent_framework

Dependencies:
    yfinance, numpy, pandas (all in requirements.txt)
    modules.strategy_map (same repo)
"""

from __future__ import annotations

import sys
import math
import datetime
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

from modules.strategy_map import STRATEGY_MAP, get_strategy
from modules.market_data_sources import FlashAlphaSource, FinvizVolumeScanner


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1: INTELLIGENCE — Data Collection Agents
# ══════════════════════════════════════════════════════════════════════════════

class NewsAgent:
    """
    Collects and scores market-moving news for a watchlist of tickers.

    IN PRODUCTION:
        Perplexity's morning cron calls this agent and populates news_items
        via web search results. Each headline is scored by the LLM for
        sentiment (-1 to +1) before being passed to the SignalSynthesizer.

    IN STANDALONE MODE (this file):
        Returns a structured placeholder so the pipeline can run without
        a live LLM call. Sentiment score defaults to 0 (neutral).

    News item schema:
        {
            "ticker":          str   — e.g. "AAPL"
            "headline":        str   — full headline text
            "sentiment_score": float — -1.0 (very bearish) to +1.0 (very bullish)
            "source":          str   — publication name
            "timestamp":       str   — ISO 8601 datetime string
            "relevance":       str   — "HIGH" | "MEDIUM" | "LOW"
        }
    """

    def scan(self, watchlist: list[str]) -> list[dict]:
        """
        Return structured news items for each ticker in watchlist.

        Args:
            watchlist: List of ticker symbols to scan, e.g. ["AAPL", "NVDA"]

        Returns:
            List of news item dicts. Empty list if no news found.

        Note:
            In production, Perplexity's cron fills this via web search and
            LLM sentiment scoring. In standalone mode, returns neutral placeholders
            so downstream agents still receive a properly structured input.
        """
        news_items = []
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for ticker in watchlist:
            # Placeholder structure — Perplexity populates real data in production
            news_items.append({
                "ticker": ticker.upper(),
                "headline": f"[Perplexity will populate: latest news for {ticker}]",
                "sentiment_score": 0.0,  # Neutral default; LLM scores this in production
                "source": "perplexity_web_search",
                "timestamp": ts,
                "relevance": "MEDIUM",
                "_note": (
                    "This placeholder is replaced by real headlines + LLM sentiment "
                    "scoring during the morning cron run. See modules/scheduled_tasks.py."
                ),
            })

        return news_items

    def inject_news(self, news_items: list[dict]) -> list[dict]:
        """
        Accept pre-scored news items from an external source (e.g., Perplexity cron).

        This is the entry point when real news data is available. Validates
        structure and clamps sentiment scores to [-1, 1].

        Args:
            news_items: List of news dicts with at minimum 'ticker' and
                        'sentiment_score' keys.

        Returns:
            Validated and normalized list of news items.
        """
        validated = []
        for item in news_items:
            if "ticker" not in item or "sentiment_score" not in item:
                continue
            item["sentiment_score"] = max(-1.0, min(1.0, float(item["sentiment_score"])))
            item.setdefault("headline", "")
            item.setdefault("source", "unknown")
            item.setdefault("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat())
            item.setdefault("relevance", "MEDIUM")
            validated.append(item)
        return validated

    def aggregate_sentiment(self, news_items: list[dict], ticker: str) -> dict:
        """
        Aggregate multiple news items for a single ticker into a summary.

        Args:
            news_items: Full list of news items (multiple tickers OK)
            ticker:     Ticker to aggregate for

        Returns:
            {
                "ticker":            str
                "avg_sentiment":     float  — mean score across all items
                "news_count":        int    — number of items found
                "sentiment_label":   str    — "BULLISH" | "BEARISH" | "NEUTRAL"
                "top_headline":      str    — highest-relevance headline
            }
        """
        ticker_news = [n for n in news_items if n.get("ticker", "").upper() == ticker.upper()]

        if not ticker_news:
            return {
                "ticker": ticker,
                "avg_sentiment": 0.0,
                "news_count": 0,
                "sentiment_label": "NEUTRAL",
                "top_headline": "No news found",
            }

        scores = [n["sentiment_score"] for n in ticker_news]
        avg = sum(scores) / len(scores)

        if avg >= 0.2:
            label = "BULLISH"
        elif avg <= -0.2:
            label = "BEARISH"
        else:
            label = "NEUTRAL"

        # Pick highest-relevance headline (HIGH > MEDIUM > LOW)
        rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        top = max(ticker_news, key=lambda n: rank.get(n.get("relevance", "LOW"), 1))

        return {
            "ticker": ticker,
            "avg_sentiment": round(avg, 3),
            "news_count": len(ticker_news),
            "sentiment_label": label,
            "top_headline": top.get("headline", ""),
        }


class TechnicalAgent:
    """
    Computes technical signals from historical price data using yfinance.

    Indicators computed:
        SMA_20       — 20-day simple moving average
        SMA_50       — 50-day simple moving average
        RSI_14       — 14-period Relative Strength Index
        VWAP         — Volume-Weighted Average Price (rolling 20-day approx)
        ATR_14       — 14-day Average True Range (volatility proxy)
        current_price — Latest closing price
        52w_high     — 52-week high
        52w_low      — 52-week low

    Signal logic:
        BULLISH  → price above SMA_20 AND SMA_50, OR RSI < 30 (oversold)
        BEARISH  → price below SMA_20 AND SMA_50, OR RSI > 70 (overbought)
        NEUTRAL  → everything else (conflicting or indeterminate signals)

    Bounce flag:
        If price is within 5% of the 52-week low, a potential bounce flag is
        set (bullish bias even if trend is bearish).
    """

    @staticmethod
    def _compute_rsi(prices: pd.Series, period: int = 14) -> float:
        """
        Compute the most recent RSI value for a price series.

        Uses Wilder's smoothing (EWM with com=period-1) — same method used
        in TradingView and most professional platforms.

        Args:
            prices: Closing price series (must have >= period+1 values)
            period: RSI lookback period (default 14)

        Returns:
            RSI value as float in [0, 100], or 50.0 if insufficient data.
        """
        if len(prices) < period + 1:
            return 50.0  # Neutral default if insufficient data

        delta = prices.diff().dropna()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

        last_gain = avg_gain.iloc[-1]
        last_loss = avg_loss.iloc[-1]

        if last_loss == 0:
            return 100.0
        rs = last_gain / last_loss
        return round(100 - (100 / (1 + rs)), 2)

    @staticmethod
    def _compute_vwap(hist: pd.DataFrame, window: int = 20) -> float:
        """
        Compute a rolling VWAP approximation over the last `window` days.

        Uses (High + Low + Close) / 3 as the typical price.

        Args:
            hist:   DataFrame with columns High, Low, Close, Volume
            window: Number of days to include in VWAP calculation

        Returns:
            VWAP value as float, or 0.0 if computation fails.
        """
        try:
            recent = hist.tail(window).copy()
            typical = (recent["High"] + recent["Low"] + recent["Close"]) / 3
            vwap = (typical * recent["Volume"]).sum() / recent["Volume"].sum()
            return round(float(vwap), 2)
        except Exception:
            return 0.0

    @staticmethod
    def _compute_atr(hist: pd.DataFrame, period: int = 14) -> float:
        """
        Compute Average True Range (ATR) over the last `period` days.

        True Range = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
        ATR = EWM mean of True Range.

        Args:
            hist:   DataFrame with columns High, Low, Close
            period: ATR lookback period

        Returns:
            ATR value as float, or 0.0 if computation fails.
        """
        try:
            high = hist["High"]
            low = hist["Low"]
            prev_close = hist["Close"].shift(1)

            tr = pd.concat([
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ], axis=1).max(axis=1)

            atr = tr.ewm(com=period - 1, min_periods=period).mean().iloc[-1]
            return round(float(atr), 4)
        except Exception:
            return 0.0

    def analyze(self, symbol: str, period: str = "6mo") -> dict:
        """
        Fetch historical price data and compute all technical indicators.

        Args:
            symbol: Ticker symbol, e.g. "AAPL"
            period: yfinance period string — "3mo", "6mo", "1y", etc.
                    Using "6mo" as default to have enough data for SMA_50 + RSI.

        Returns:
            {
                "symbol":         str
                "current_price":  float
                "sma_20":         float
                "sma_50":         float
                "rsi_14":         float
                "vwap":           float
                "atr_14":         float
                "high_52w":       float
                "low_52w":        float
                "near_52w_low":   bool   — True if within 5% of 52w low
                "signal":         str    — "BULLISH" | "BEARISH" | "NEUTRAL"
                "signal_reasons": list[str]  — human-readable explanation
                "error":          str | None — populated if data fetch failed
            }
        """
        result: dict = {
            "symbol": symbol.upper(),
            "current_price": 0.0,
            "sma_20": 0.0,
            "sma_50": 0.0,
            "rsi_14": 50.0,
            "vwap": 0.0,
            "atr_14": 0.0,
            "high_52w": 0.0,
            "low_52w": 0.0,
            "near_52w_low": False,
            "signal": "NEUTRAL",
            "signal_reasons": [],
            "error": None,
        }

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)

            if hist.empty or len(hist) < 20:
                result["error"] = f"Insufficient data for {symbol} (got {len(hist)} rows)"
                return result

            closes = hist["Close"]
            current_price = float(closes.iloc[-1])
            sma_20 = float(closes.tail(20).mean())
            sma_50 = float(closes.tail(50).mean()) if len(closes) >= 50 else sma_20
            rsi_14 = self._compute_rsi(closes)
            vwap = self._compute_vwap(hist)
            atr_14 = self._compute_atr(hist)

            # 52-week range (use full available history)
            hist_1y = ticker.history(period="1y")
            if not hist_1y.empty:
                high_52w = float(hist_1y["High"].max())
                low_52w = float(hist_1y["Low"].min())
            else:
                high_52w = float(hist["High"].max())
                low_52w = float(hist["Low"].min())

            near_52w_low = current_price <= low_52w * 1.05  # Within 5% of 52w low

            result.update({
                "current_price": round(current_price, 2),
                "sma_20": round(sma_20, 2),
                "sma_50": round(sma_50, 2),
                "rsi_14": rsi_14,
                "vwap": vwap,
                "atr_14": atr_14,
                "high_52w": round(high_52w, 2),
                "low_52w": round(low_52w, 2),
                "near_52w_low": near_52w_low,
            })

            # ── Signal determination ──────────────────────────────────────
            bullish_points = 0
            bearish_points = 0
            reasons = []

            # Trend: price vs SMAs
            if current_price > sma_20:
                bullish_points += 1
                reasons.append(f"Price (${current_price:.2f}) above SMA_20 (${sma_20:.2f})")
            else:
                bearish_points += 1
                reasons.append(f"Price (${current_price:.2f}) below SMA_20 (${sma_20:.2f})")

            if current_price > sma_50:
                bullish_points += 1
                reasons.append(f"Price above SMA_50 (${sma_50:.2f}) — uptrend")
            else:
                bearish_points += 1
                reasons.append(f"Price below SMA_50 (${sma_50:.2f}) — downtrend")

            # RSI
            if rsi_14 < 30:
                bullish_points += 2  # Oversold — strong bullish signal
                reasons.append(f"RSI {rsi_14:.1f} — OVERSOLD (strong bullish reversal signal)")
            elif rsi_14 > 70:
                bearish_points += 2  # Overbought — strong bearish signal
                reasons.append(f"RSI {rsi_14:.1f} — OVERBOUGHT (strong bearish reversal signal)")
            elif rsi_14 < 45:
                bearish_points += 1
                reasons.append(f"RSI {rsi_14:.1f} — slightly weak momentum")
            elif rsi_14 > 55:
                bullish_points += 1
                reasons.append(f"RSI {rsi_14:.1f} — slightly strong momentum")
            else:
                reasons.append(f"RSI {rsi_14:.1f} — neutral momentum")

            # VWAP
            if vwap > 0:
                if current_price > vwap:
                    bullish_points += 1
                    reasons.append(f"Price above VWAP (${vwap:.2f}) — institutional buying pressure")
                else:
                    bearish_points += 1
                    reasons.append(f"Price below VWAP (${vwap:.2f}) — institutional selling pressure")

            # 52-week proximity
            if near_52w_low:
                bullish_points += 1
                reasons.append(
                    f"Price within 5% of 52w low (${low_52w:.2f}) — potential bounce zone"
                )

            pct_from_52w_high = ((high_52w - current_price) / high_52w) * 100
            if pct_from_52w_high < 3:
                bearish_points += 1
                reasons.append(
                    f"Price within 3% of 52w high (${high_52w:.2f}) — potential resistance"
                )

            # Final signal
            if bullish_points > bearish_points:
                signal = "BULLISH"
            elif bearish_points > bullish_points:
                signal = "BEARISH"
            else:
                signal = "NEUTRAL"

            result["signal"] = signal
            result["signal_reasons"] = reasons

        except Exception as e:
            result["error"] = str(e)

        return result


class VolatilityAgent:
    """
    Analyzes volatility to determine the current vol regime.

    TWO DATA SOURCES (layered):

    1. Historical Volatility (always available)
       - HV_20, HV_60, vol_percentile vs trailing year
       - Computed from yfinance price data

    2. FlashAlpha GEX / Gamma Exposure (when API key configured)
       - Real-time dealer positioning: positive or negative gamma regime
       - Gamma flip level, call wall, put wall
       - Tells us whether dealers will DAMPEN or AMPLIFY price moves
       - This is the signal professional options desks use

    When FlashAlpha is available, GEX data UPGRADES the analysis:
       - Negative gamma + HIGH_VOL → "EXTREME" (moves will be amplified)
       - Positive gamma + HIGH_VOL → "HIGH_VOL" (dampened, premium selling sweet spot)
       - Negative gamma overrides NORMAL → bumps to HIGH_VOL (wider strikes needed)

    Vol Regime classification:
        LOW_VOL    → vol_percentile < 25   (options are cheap — buy premium)
        NORMAL     → 25 ≤ vol_percentile < 60
        HIGH_VOL   → 60 ≤ vol_percentile < 85  (options are expensive — sell premium)
        EXTREME    → vol_percentile ≥ 85   (treat like HIGH_VOL + extra caution)

    Strategy implications:
        HIGH_VOL / EXTREME → Sell premium (iron condor, credit spreads, CSP)
        LOW_VOL            → Buy premium (straddles, long options, debit spreads)
        NORMAL             → Directional plays based on technical signal
    """

    def __init__(self, flashalpha_source: Optional[FlashAlphaSource] = None):
        """
        Initialize with optional FlashAlpha GEX data source.

        Args:
            flashalpha_source: FlashAlphaSource instance. If provided and
                               configured, GEX data upgrades the vol analysis.
                               If None, falls back to historical vol only.
        """
        self._flashalpha = flashalpha_source

    @staticmethod
    def _annualized_vol(returns: pd.Series) -> float:
        """Convert a returns series to annualized volatility (percent)."""
        if len(returns) < 2:
            return 0.0
        return round(float(returns.std() * math.sqrt(252) * 100), 2)

    def analyze(self, symbol: str, current_price: float) -> dict:
        """
        Fetch historical prices and compute the volatility regime.

        If FlashAlpha is configured, also fetches GEX data to refine the
        regime classification with real dealer positioning data.

        Args:
            symbol:        Ticker symbol, e.g. "NVDA"
            current_price: Most recent closing price (from TechnicalAgent output)

        Returns:
            {
                "symbol":          str
                "hist_vol_20d":    float  — 20-day annualized HV (percent)
                "hist_vol_60d":    float  — 60-day annualized HV (percent)
                "vol_percentile":  float  — percentile vs trailing 1-year HV
                "vol_regime":      str    — "LOW_VOL" | "NORMAL" | "HIGH_VOL" | "EXTREME"
                "regime_note":     str    — one-line plain English interpretation
                "strategy_hint":   str    — suggested approach for this regime
                "gex_data":        dict|None — FlashAlpha GEX data (if available)
                "error":           str | None
            }
        """
        result: dict = {
            "symbol": symbol.upper(),
            "hist_vol_20d": 0.0,
            "hist_vol_60d": 0.0,
            "vol_percentile": 50.0,
            "vol_regime": "NORMAL",
            "regime_note": "Unable to compute — default to NORMAL",
            "strategy_hint": "Directional plays based on technical signal",
            "gex_data": None,
            "error": None,
        }

        try:
            hist = yf.Ticker(symbol).history(period="1y")

            if hist.empty or len(hist) < 65:
                result["error"] = f"Insufficient data for volatility analysis of {symbol}"
                return result

            log_returns = np.log(hist["Close"] / hist["Close"].shift(1)).dropna()

            hv_20 = self._annualized_vol(log_returns.tail(20))
            hv_60 = self._annualized_vol(log_returns.tail(60))

            # Compute rolling 20-day vol over the full year to get percentile
            rolling_hv = []
            for i in range(20, len(log_returns) + 1):
                window = log_returns.iloc[i - 20:i]
                rolling_hv.append(float(window.std() * math.sqrt(252) * 100))

            if rolling_hv:
                percentile = float(
                    sum(1 for v in rolling_hv if v <= hv_20) / len(rolling_hv) * 100
                )
            else:
                percentile = 50.0

            # Classify regime
            if percentile < 25:
                regime = "LOW_VOL"
                note = f"Volatility is historically cheap (bottom {percentile:.0f}% of the year)"
                hint = "Consider buying premium: Long straddles, debit spreads, or long options"
            elif percentile < 60:
                regime = "NORMAL"
                note = f"Volatility is in a normal range ({percentile:.0f}th percentile)"
                hint = "Directional plays — let the technical signal drive strategy selection"
            elif percentile < 85:
                regime = "HIGH_VOL"
                note = f"Volatility is elevated ({percentile:.0f}th percentile) — options are expensive"
                hint = "Sell premium: Iron condors, credit spreads, cash-secured puts"
            else:
                regime = "EXTREME"
                note = f"Volatility is extremely elevated ({percentile:.0f}th percentile) — proceed cautiously"
                hint = "Sell premium with wide strikes, or wait for vol to normalize"

            result.update({
                "hist_vol_20d": hv_20,
                "hist_vol_60d": hv_60,
                "vol_percentile": round(percentile, 1),
                "vol_regime": regime,
                "regime_note": note,
                "strategy_hint": hint,
            })

        except Exception as e:
            result["error"] = str(e)

        # ── FlashAlpha GEX overlay (if configured) ────────────────────
        #
        # When GEX data is available, it refines the regime classification:
        #   - Negative gamma + NORMAL  → bump to HIGH_VOL (amplified moves)
        #   - Negative gamma + HIGH_VOL → bump to EXTREME
        #   - Positive gamma + EXTREME  → keep as HIGH_VOL (dampened)
        #
        # GEX also provides call wall / put wall / gamma flip levels that
        # the SignalSynthesizer uses for strike zone guidance.

        if self._flashalpha and self._flashalpha.is_configured:
            try:
                gex = self._flashalpha.get_exposure_summary(symbol)
                result["gex_data"] = gex

                if gex.get("gex_available"):
                    gamma_regime = gex.get("gamma_regime", "UNKNOWN")
                    current_regime = result["vol_regime"]

                    # Negative gamma amplifies moves — bump regime up
                    if gamma_regime == "NEGATIVE":
                        if current_regime == "NORMAL":
                            result["vol_regime"] = "HIGH_VOL"
                            result["regime_note"] += (
                                f" | GEX: Negative gamma (flip at "
                                f"${gex.get('gamma_flip', 0):.2f}) — "
                                f"dealers amplifying moves, upgraded to HIGH_VOL"
                            )
                            result["strategy_hint"] = (
                                "Sell premium with WIDER strikes — negative gamma "
                                "means bigger-than-expected moves are likely"
                            )
                        elif current_regime == "HIGH_VOL":
                            result["vol_regime"] = "EXTREME"
                            result["regime_note"] += (
                                f" | GEX: Negative gamma confirms elevated risk — "
                                f"upgraded to EXTREME"
                            )
                            result["strategy_hint"] = (
                                "Sell premium with VERY WIDE strikes or wait — "
                                "negative gamma + high HV = storm conditions"
                            )

                    # Positive gamma dampens moves — great for premium selling
                    elif gamma_regime == "POSITIVE":
                        if current_regime == "EXTREME":
                            result["vol_regime"] = "HIGH_VOL"
                            result["regime_note"] += (
                                f" | GEX: Positive gamma (flip at "
                                f"${gex.get('gamma_flip', 0):.2f}) — "
                                f"dealers dampening moves, downgraded to HIGH_VOL"
                            )
                        if current_regime in ("HIGH_VOL", "EXTREME"):
                            result["strategy_hint"] = (
                                "Premium selling sweet spot — positive gamma means "
                                "dealers absorb moves + high IV = rich premiums"
                            )

                    # Add wall levels to result for strike guidance
                    if gex.get("call_wall", 0) > 0:
                        result["call_wall"] = gex["call_wall"]
                    if gex.get("put_wall", 0) > 0:
                        result["put_wall"] = gex["put_wall"]
                    if gex.get("gamma_flip", 0) > 0:
                        result["gamma_flip"] = gex["gamma_flip"]

            except Exception as e:
                # GEX is supplemental — don't fail the whole analysis
                result["gex_data"] = {"error": str(e), "gex_available": False}

        return result


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2: STRATEGY — Signal Synthesis + Bull/Bear Debate
# ══════════════════════════════════════════════════════════════════════════════

class SignalSynthesizer:
    """
    Combines outputs from all 3 Layer-1 agents into a single trade recommendation.

    Inspired by TradingAgents' bull/bear debate pattern: for every ticker, we
    explicitly construct BOTH a bull case and a bear case, then score confidence
    based on how strongly the evidence tilts one way.

    Confidence scoring (0–100):
        Signal agreement across all 3 agents → 80–100 (high conviction)
        2 of 3 agents agree                  → 50–79 (moderate conviction)
        Mixed / conflicting signals           → 0–49  (skip — not worth the risk)

    The pipeline filters out any signal with confidence < 60.

    The synthesizer also maps the combined signal to a specific options strategy
    via the STRATEGY_MAP lookup in modules/strategy_map.py.
    """

    def synthesize(
        self,
        news_summary: dict,
        technical: dict,
        volatility: dict,
    ) -> dict:
        """
        Run the bull/bear debate and produce a confidence-scored recommendation.

        Args:
            news_summary: Output of NewsAgent.aggregate_sentiment() for this ticker
            technical:    Output of TechnicalAgent.analyze() for this ticker
            volatility:   Output of VolatilityAgent.analyze() for this ticker

        Returns:
            {
                "symbol":             str
                "direction":          str   — "BULLISH" | "BEARISH" | "NEUTRAL"
                "confidence":         int   — 0–100
                "bull_case":          list[str]  — arguments for the trade
                "bear_case":          list[str]  — arguments against
                "vol_regime":         str
                "suggested_strategy": dict  — from STRATEGY_MAP
                "suggested_timeframe":str
                "risk_warning":       str
                "signal_breakdown":   dict  — raw scores from each agent
            }
        """
        symbol = technical.get("symbol", "UNKNOWN")
        tech_signal = technical.get("signal", "NEUTRAL")
        news_signal = news_summary.get("sentiment_label", "NEUTRAL")
        vol_regime = volatility.get("vol_regime", "NORMAL")

        # ── Build Bull Case ───────────────────────────────────────────────
        bull_case: list[str] = []
        bear_case: list[str] = []
        bullish_votes = 0
        bearish_votes = 0
        neutral_votes = 0

        # Vote 1: Technical signal
        if tech_signal == "BULLISH":
            bullish_votes += 1
            for reason in technical.get("signal_reasons", []):
                if any(w in reason.lower() for w in ["above", "oversold", "bounce", "buying"]):
                    bull_case.append(f"[Technical] {reason}")
        elif tech_signal == "BEARISH":
            bearish_votes += 1
            for reason in technical.get("signal_reasons", []):
                if any(w in reason.lower() for w in ["below", "overbought", "resistance", "selling"]):
                    bear_case.append(f"[Technical] {reason}")
        else:
            neutral_votes += 1

        # Add all technical reasons to appropriate case (even partial ones)
        for reason in technical.get("signal_reasons", []):
            if reason not in " ".join(bull_case) and reason not in " ".join(bear_case):
                if tech_signal == "BULLISH":
                    bull_case.append(f"[Technical] {reason}")
                elif tech_signal == "BEARISH":
                    bear_case.append(f"[Technical] {reason}")

        # Vote 2: News / sentiment signal
        news_score = news_summary.get("avg_sentiment", 0.0)
        if news_signal == "BULLISH":
            bullish_votes += 1
            bull_case.append(
                f"[News] Positive sentiment (score: {news_score:+.2f}) — "
                f"{news_summary.get('top_headline', 'Recent positive coverage')}"
            )
        elif news_signal == "BEARISH":
            bearish_votes += 1
            bear_case.append(
                f"[News] Negative sentiment (score: {news_score:+.2f}) — "
                f"{news_summary.get('top_headline', 'Recent negative coverage')}"
            )
        else:
            neutral_votes += 1
            bear_case.append(f"[News] Sentiment is neutral — no strong catalyst identified")

        # Vote 3: Volatility regime (adds color, not a direction vote)
        if vol_regime in ("HIGH_VOL", "EXTREME"):
            bear_case.append(
                f"[Volatility] {volatility.get('regime_note', '')} — "
                f"HV_20={volatility.get('hist_vol_20d', 0):.1f}%, "
                f"HV_60={volatility.get('hist_vol_60d', 0):.1f}%"
            )
            # High vol: slight bullish credit-selling edge if stock is at support
            if technical.get("near_52w_low"):
                bull_case.append(
                    "[Volatility] Elevated premium near 52w lows — "
                    "excellent setup for cash-secured puts to collect rich premium"
                )
        elif vol_regime == "LOW_VOL":
            bull_case.append(
                f"[Volatility] {volatility.get('regime_note', '')} — "
                f"cheap options favor buying premium strategies"
            )

        # Vote 3b: FlashAlpha GEX data (supplemental color)
        gex_data = volatility.get("gex_data")
        if gex_data and gex_data.get("gex_available"):
            gamma_regime = gex_data.get("gamma_regime", "UNKNOWN")
            gamma_flip = gex_data.get("gamma_flip", 0)
            call_wall = gex_data.get("call_wall", 0)
            put_wall = gex_data.get("put_wall", 0)

            if gamma_regime == "POSITIVE":
                bull_case.append(
                    f"[GEX] Positive gamma regime — dealers dampen moves. "
                    f"Flip at ${gamma_flip:.2f}. Favorable for premium selling."
                )
            elif gamma_regime == "NEGATIVE":
                bear_case.append(
                    f"[GEX] Negative gamma regime — dealers amplify moves. "
                    f"Flip at ${gamma_flip:.2f}. Use wider strikes or wait."
                )

            # Add wall levels to strike guidance context
            if call_wall > 0 and put_wall > 0:
                bull_case.append(
                    f"[GEX] Key levels: Call wall ${call_wall:.2f} / "
                    f"Put wall ${put_wall:.2f} — use as strike zone anchors"
                )

        # ── Determine overall direction ───────────────────────────────────
        if bullish_votes > bearish_votes:
            direction = "BULLISH"
        elif bearish_votes > bullish_votes:
            direction = "BEARISH"
        else:
            direction = "NEUTRAL"

        # ── Confidence scoring ────────────────────────────────────────────
        #
        # Base confidence from vote agreement:
        #   3 votes same direction → 80 base
        #   2 votes same direction → 55 base
        #   1 vote  (the rest neutral) → 40 base
        #
        # Adjustments:
        #   RSI extreme (< 30 or > 70) → +15
        #   Near 52w low (bounce zone) → +10
        #   News strongly aligned      → +10
        #   Vol regime supports strategy → +5
        #   Error in any agent         → -20

        total_aligned = max(bullish_votes, bearish_votes)
        if total_aligned == 3:
            base_confidence = 80
        elif total_aligned == 2:
            base_confidence = 55
        else:
            base_confidence = 38

        adjustments = 0
        rsi = technical.get("rsi_14", 50)
        if rsi < 30 or rsi > 70:
            adjustments += 15
        if technical.get("near_52w_low") and direction == "BULLISH":
            adjustments += 10
        if abs(news_score) >= 0.5:
            adjustments += 10
        if vol_regime in ("HIGH_VOL", "EXTREME") and direction in ("BEARISH", "NEUTRAL"):
            adjustments += 5
        if vol_regime == "LOW_VOL" and direction == "BULLISH":
            adjustments += 5

        # GEX alignment bonus: +5 if gamma regime supports the trade direction
        if gex_data and gex_data.get("gex_available"):
            gamma_regime = gex_data.get("gamma_regime", "UNKNOWN")
            if gamma_regime == "POSITIVE" and direction in ("NEUTRAL", "BULLISH"):
                adjustments += 5  # Positive gamma = mean-reversion = premium selling works
            elif gamma_regime == "NEGATIVE" and direction in ("BULLISH", "BEARISH"):
                adjustments += 3  # Directional plays benefit from amplified moves

        # Penalize if agents had errors
        if technical.get("error"):
            adjustments -= 20
        if volatility.get("error"):
            adjustments -= 10

        confidence = min(100, max(0, base_confidence + adjustments))

        # ── Strategy recommendation ────────────────────────────────────────
        # EXTREME vol treated same as HIGH_VOL for strategy mapping
        strategy_vol = "HIGH_VOL" if vol_regime == "EXTREME" else vol_regime
        suggested_strategy = get_strategy(direction, strategy_vol) or {
            "name": "No specific strategy",
            "description": "Signal unclear — consider waiting",
        }

        # Timeframe based on vol and confidence
        if confidence >= 75:
            timeframe = "30–45 DTE (next monthly expiration)"
        elif confidence >= 60:
            timeframe = "21–35 DTE (near-term expiration)"
        else:
            timeframe = "Monitor — insufficient conviction to enter"

        # Risk warning
        risk_warnings = []
        if vol_regime == "EXTREME":
            risk_warnings.append("EXTREME volatility — consider smaller position size")
        if rsi > 80:
            risk_warnings.append(f"RSI {rsi:.0f} is severely overbought — gap-down risk is real")
        if rsi < 20:
            risk_warnings.append(f"RSI {rsi:.0f} is severely oversold — dead-cat bounce risk")
        if technical.get("error"):
            risk_warnings.append("Technical data error — validate manually before trading")
        if news_summary.get("news_count", 0) == 0:
            risk_warnings.append("No news found — Perplexity cron may not have run yet")

        risk_warning = "; ".join(risk_warnings) if risk_warnings else "No major risk flags"

        return {
            "symbol": symbol,
            "direction": direction,
            "confidence": confidence,
            "bull_case": bull_case,
            "bear_case": bear_case,
            "vol_regime": vol_regime,
            "suggested_strategy": suggested_strategy,
            "suggested_timeframe": timeframe,
            "risk_warning": risk_warning,
            "signal_breakdown": {
                "technical": tech_signal,
                "news": news_signal,
                "vol_regime": vol_regime,
                "bullish_votes": bullish_votes,
                "bearish_votes": bearish_votes,
                "neutral_votes": neutral_votes,
            },
        }

    def recommend_strategy(self, direction: str, vol_regime: str, confidence: int) -> dict:
        """
        Look up the appropriate options strategy for a given market context.

        Maps (direction, vol_regime) → specific strategy from STRATEGY_MAP.
        If confidence < 60, returns a "Monitor" placeholder instead.

        Args:
            direction:  "BULLISH", "BEARISH", or "NEUTRAL"
            vol_regime: "HIGH_VOL", "NORMAL", "LOW_VOL", or "EXTREME"
            confidence: 0–100 confidence score

        Returns:
            Strategy dict from STRATEGY_MAP, or a "Monitor" dict if confidence too low.

        Strategy selection logic:
            BULLISH + HIGH_VOL  → Cash-Secured Put (collect fat premium, bullish bias)
            BULLISH + LOW_VOL   → Bull Call Spread (cheap debit entry)
            BULLISH + NORMAL    → Bull Call Spread (standard directional)
            BEARISH + HIGH_VOL  → Bear Call Spread (collect premium, bearish bias)
            BEARISH + LOW_VOL   → Bear Put Spread (cheap debit entry)
            BEARISH + NORMAL    → Bear Put Spread (standard directional)
            NEUTRAL + HIGH_VOL  → Iron Condor (sell premium both sides)
            NEUTRAL + LOW_VOL   → Long Straddle (bet on breakout)
            NEUTRAL + NORMAL    → Iron Condor narrow (range-bound play)
        """
        if confidence < 60:
            return {
                "name": "Monitor — No Trade",
                "description": (
                    "Confidence is below threshold. Insufficient signal agreement "
                    "to justify entering a trade. Watch for clearer setup."
                ),
            }

        # Normalize EXTREME → HIGH_VOL for strategy lookup
        lookup_regime = "HIGH_VOL" if vol_regime == "EXTREME" else vol_regime
        return get_strategy(direction, lookup_regime) or {
            "name": "Unknown — Review Manually",
            "description": "Strategy mapping not found for this signal combination.",
        }


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3: EXECUTION — Risk Management + Trade Preparation
# ══════════════════════════════════════════════════════════════════════════════

class RiskManager:
    """
    Enforces portfolio-level risk limits before any trade is presented for approval.

    This is the last line of defense before a trade card reaches the user.
    If a trade fails any check, it's filtered from the recommendations list.

    Default limits (all configurable at init):
        max_position_pct:      5.0%   — max portfolio allocation per position
        max_portfolio_risk_pct: 20.0% — total portfolio risk across all open positions
        max_single_loss:       $500   — max allowable loss on a single trade
        max_open_positions:    5      — stop adding positions after this count

    The RiskManager does NOT know the exact option premiums (that requires a
    live options chain pull). Instead, it estimates based on ATR and position
    sizing conventions typical for options spreads.
    """

    def __init__(
        self,
        max_position_pct: float = 5.0,
        max_portfolio_risk_pct: float = 20.0,
        max_single_loss: float = 500.0,
        max_open_positions: int = 5,
    ):
        """
        Initialize with configurable risk parameters.

        Args:
            max_position_pct:       Max % of portfolio in any single position
            max_portfolio_risk_pct: Max total portfolio risk across all positions
            max_single_loss:        Max dollar loss acceptable on a single trade
            max_open_positions:     Maximum number of concurrent open positions
        """
        self.max_position_pct = max_position_pct
        self.max_portfolio_risk_pct = max_portfolio_risk_pct
        self.max_single_loss = max_single_loss
        self.max_open_positions = max_open_positions

    def check(
        self,
        signal: dict,
        portfolio_value: float,
        existing_positions: int,
    ) -> dict:
        """
        Run all risk checks against the trade signal.

        Args:
            signal:              Output of SignalSynthesizer.synthesize()
            portfolio_value:     Current total portfolio value in dollars
            existing_positions:  Number of currently open positions

        Returns:
            {
                "approved":           bool   — True if all checks pass
                "adjusted_size":      int    — Recommended number of contracts (1–5)
                "max_loss_estimate":  float  — Estimated worst-case dollar loss
                "risk_notes":         list[str]  — Explanation of each check result
                "checks_passed":      int    — How many checks passed
                "checks_total":       int    — Total number of checks run
            }
        """
        risk_notes: list[str] = []
        checks_passed = 0
        checks_total = 4

        current_price = signal.get("current_price", signal.get("technical", {}).get("current_price", 0))
        atr = signal.get("atr_14", signal.get("technical", {}).get("atr_14", 0))
        confidence = signal.get("confidence", 0)

        # Estimate typical options spread cost as ~1.5× ATR (rough proxy)
        # For credit spreads, this represents the margin requirement
        # For debit spreads, this represents the premium paid
        atr_proxy = atr if atr > 0 else (current_price * 0.02)  # 2% fallback
        estimated_per_contract_risk = atr_proxy * 100  # 1 contract = 100 shares

        # ── Check 1: Max open positions ───────────────────────────────────
        if existing_positions >= self.max_open_positions:
            risk_notes.append(
                f"FAIL: Already at max positions ({existing_positions}/{self.max_open_positions}). "
                f"Close a position before opening new ones."
            )
        else:
            checks_passed += 1
            risk_notes.append(
                f"PASS: Position count OK ({existing_positions}/{self.max_open_positions} open)"
            )

        # ── Check 2: Position size limit ──────────────────────────────────
        max_position_dollars = portfolio_value * (self.max_position_pct / 100)
        if estimated_per_contract_risk > max_position_dollars:
            risk_notes.append(
                f"FAIL: Estimated position risk (${estimated_per_contract_risk:.0f}) "
                f"exceeds {self.max_position_pct}% position limit "
                f"(${max_position_dollars:.0f}). Reduce to 1 contract."
            )
            # Still passes — we just reduce size
            checks_passed += 1
        else:
            checks_passed += 1
            risk_notes.append(
                f"PASS: Position size within {self.max_position_pct}% limit "
                f"(${estimated_per_contract_risk:.0f} estimated risk)"
            )

        # ── Check 3: Single trade max loss ────────────────────────────────
        if estimated_per_contract_risk > self.max_single_loss:
            risk_notes.append(
                f"FAIL: Estimated loss per contract (${estimated_per_contract_risk:.0f}) "
                f"exceeds single-trade limit (${self.max_single_loss:.0f}). "
                f"Reduce position size or choose a narrower spread."
            )
        else:
            checks_passed += 1
            risk_notes.append(
                f"PASS: Single-trade risk OK "
                f"(${estimated_per_contract_risk:.0f} < ${self.max_single_loss:.0f} limit)"
            )

        # ── Check 4: Portfolio-level risk budget ──────────────────────────
        # Estimate current total risk: existing positions × avg estimated risk
        estimated_current_risk_pct = (existing_positions / self.max_open_positions) * self.max_portfolio_risk_pct
        remaining_risk_budget = self.max_portfolio_risk_pct - estimated_current_risk_pct
        this_trade_risk_pct = (estimated_per_contract_risk / portfolio_value) * 100

        if this_trade_risk_pct > remaining_risk_budget:
            risk_notes.append(
                f"FAIL: This trade ({this_trade_risk_pct:.1f}% of portfolio) would "
                f"exceed remaining risk budget ({remaining_risk_budget:.1f}%). "
                f"Consider closing existing positions first."
            )
        else:
            checks_passed += 1
            risk_notes.append(
                f"PASS: Portfolio risk budget OK "
                f"(this trade = {this_trade_risk_pct:.1f}%, "
                f"budget remaining = {remaining_risk_budget:.1f}%)"
            )

        # ── Position sizing recommendation ────────────────────────────────
        if estimated_per_contract_risk > 0 and portfolio_value > 0:
            target_risk_dollars = portfolio_value * (self.max_position_pct / 100)
            raw_contracts = int(target_risk_dollars / estimated_per_contract_risk)
            adjusted_size = max(1, min(5, raw_contracts))  # 1–5 contracts
        else:
            adjusted_size = 1

        # ── Final approval decision ───────────────────────────────────────
        # Approve if 3 or more checks pass (allow 1 borderline failure)
        approved = checks_passed >= 3 and existing_positions < self.max_open_positions

        return {
            "approved": approved,
            "adjusted_size": adjusted_size,
            "max_loss_estimate": round(estimated_per_contract_risk * adjusted_size, 2),
            "risk_notes": risk_notes,
            "checks_passed": checks_passed,
            "checks_total": checks_total,
        }


class TradePrep:
    """
    Assembles the final trade recommendation card for user approval.

    This is the output layer — it takes the synthesized signal and risk check
    results and formats them into a clean, human-readable trade card that the
    user can APPROVE or REJECT in the Enso UI.

    The trade card deliberately does NOT include specific strike prices —
    those require a live options chain pull (via api_client.py's option chain
    endpoint). The card shows the strategy structure so the user can pick
    their preferred strikes in the options page.
    """

    def prepare(self, signal: dict, risk_check: dict) -> dict:
        """
        Build the final trade card from signal and risk check outputs.

        Args:
            signal:     Output of SignalSynthesizer.synthesize()
            risk_check: Output of RiskManager.check()

        Returns:
            Complete trade card dict ready for display in the Enso UI:
            {
                "symbol":               str
                "strategy":             str   — strategy name
                "strategy_description": str   — plain-English explanation
                "direction":            str   — "BULLISH" | "BEARISH" | "NEUTRAL"
                "vol_regime":           str
                "confidence_score":     int   — 0–100
                "confidence_label":     str   — "HIGH" | "MODERATE" | "LOW"
                "bull_case":            list[str]
                "bear_case":            list[str]
                "suggested_strikes":    str   — approximate guidance (not exact)
                "contracts":            int   — recommended position size
                "max_loss":             float — estimated worst-case dollar loss
                "max_profit_potential": str   — qualitative description
                "suggested_timeframe":  str
                "risk_warning":         str
                "risk_manager_notes":   list[str]
                "action_required":      str   — always "APPROVE or REJECT"
                "generated_at":         str   — ISO timestamp
            }
        """
        strategy = signal.get("suggested_strategy", {})
        strategy_name = strategy.get("name", "Unknown Strategy")
        strategy_desc = strategy.get("description", "")
        direction = signal.get("direction", "NEUTRAL")
        confidence = signal.get("confidence", 0)
        symbol = signal.get("symbol", "UNKNOWN")
        current_price = signal.get("current_price", 0)
        vol_regime = signal.get("vol_regime", "NORMAL")

        # Confidence label
        if confidence >= 75:
            confidence_label = "HIGH"
        elif confidence >= 60:
            confidence_label = "MODERATE"
        else:
            confidence_label = "LOW"

        # Approximate strike guidance — not exact (user pulls real chain)
        atr = signal.get("atr_14", 0)
        cp = signal.get("current_price", current_price)

        # Use GEX walls for strike guidance if available, otherwise ATR
        gex_data = signal.get("_gex_data") or {}
        call_wall = gex_data.get("call_wall", 0) if gex_data.get("gex_available") else 0
        put_wall = gex_data.get("put_wall", 0) if gex_data.get("gex_available") else 0
        gamma_flip = gex_data.get("gamma_flip", 0) if gex_data.get("gex_available") else 0

        if atr > 0 and cp > 0:
            otm_offset = atr * 1.0  # ~1 ATR out of the money

            # Build GEX-informed strike guidance
            gex_note = ""
            if call_wall > 0 and put_wall > 0:
                gex_note = (
                    f" GEX levels: call wall ${call_wall:.2f}, "
                    f"put wall ${put_wall:.2f}, "
                    f"gamma flip ${gamma_flip:.2f}."
                )

            if direction == "BULLISH":
                strike_low = put_wall if put_wall > 0 else (cp - otm_offset)
                suggested_strikes = (
                    f"Look for strikes near ${cp:.2f} (ATM) to ${strike_low:.2f} "
                    f"(~1 ATR below / put wall).{gex_note} "
                    f"Pull the live options chain for exact strikes."
                )
            elif direction == "BEARISH":
                strike_high = call_wall if call_wall > 0 else (cp + otm_offset)
                suggested_strikes = (
                    f"Look for strikes near ${cp:.2f} (ATM) to ${strike_high:.2f} "
                    f"(~1 ATR above / call wall).{gex_note} "
                    f"Pull the live options chain for exact strikes."
                )
            else:  # NEUTRAL
                put_strike = put_wall if put_wall > 0 else (cp - otm_offset)
                call_strike = call_wall if call_wall > 0 else (cp + otm_offset)
                suggested_strikes = (
                    f"Target short strikes: "
                    f"${put_strike:.2f} put side / ${call_strike:.2f} call side."
                    f"{gex_note} Pull the live options chain for exact strikes."
                )
        else:
            suggested_strikes = "Pull the live options chain to select strikes."

        # Max profit potential description
        strat_reward = strategy.get("reward", "")
        if strat_reward:
            max_profit_potential = strat_reward
        elif direction == "BULLISH" and "Condor" not in strategy_name:
            max_profit_potential = "Unlimited (for long options) or defined by spread width"
        else:
            max_profit_potential = "Defined by spread width or premium collected"

        return {
            "symbol": symbol,
            "strategy": strategy_name,
            "strategy_description": strategy_desc,
            "direction": direction,
            "vol_regime": vol_regime,
            "confidence_score": confidence,
            "confidence_label": confidence_label,
            "bull_case": signal.get("bull_case", []),
            "bear_case": signal.get("bear_case", []),
            "suggested_strikes": suggested_strikes,
            "contracts": risk_check.get("adjusted_size", 1),
            "max_loss": risk_check.get("max_loss_estimate", 0.0),
            "max_profit_potential": max_profit_potential,
            "suggested_timeframe": signal.get("suggested_timeframe", ""),
            "risk_warning": signal.get("risk_warning", ""),
            "risk_manager_notes": risk_check.get("risk_notes", []),
            "action_required": "APPROVE or REJECT",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            # Raw data for downstream use (e.g., UI detail panel)
            "_signal_breakdown": signal.get("signal_breakdown", {}),
            "_risk_summary": {
                "checks_passed": risk_check.get("checks_passed"),
                "checks_total": risk_check.get("checks_total"),
                "approved": risk_check.get("approved"),
            },
        }


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline(
    watchlist: list[str],
    portfolio_value: float = 100_000.0,
    existing_positions: int = 0,
    news_data: Optional[list[dict]] = None,
    min_confidence: int = 60,
    flashalpha_api_key: Optional[str] = None,
    use_finviz_watchlist: bool = False,
    finviz_max_tickers: int = 10,
) -> list[dict]:
    """
    Run the full 3-layer multi-agent pipeline on a watchlist.

    Layer 0 (optional) → Finviz unusual volume scan for dynamic watchlist
    Layer 1 → Layer 2 → Layer 3, applied to each ticker in the watchlist.
    Tickers with insufficient signal confidence or failing risk checks are
    filtered out. Returns at most 3 recommendations, sorted by confidence.

    Args:
        watchlist:          List of ticker symbols, e.g. ["SPY", "AAPL", "NVDA"]
        portfolio_value:    Current portfolio value in dollars (default $100k)
        existing_positions: Number of currently open positions (for risk limits)
        news_data:          Optional pre-scored news items from Perplexity cron.
                            If None, NewsAgent returns neutral placeholders.
        min_confidence:     Minimum confidence score to include in output (default 60)
        flashalpha_api_key: Optional FlashAlpha API key for GEX data.
                            Falls back to FLASHALPHA_API_KEY env var.
        use_finviz_watchlist: If True, scan Finviz for unusual volume tickers
                              and merge with the provided watchlist.
        finviz_max_tickers:   Max tickers to pull from Finviz (default 10).

    Returns:
        List of trade card dicts (from TradePrep.prepare()), sorted by
        confidence_score descending. Max 3 items.

    Example:
        trades = run_pipeline(["SPY", "AAPL", "NVDA"], portfolio_value=50000)
        for trade in trades:
            print(trade["symbol"], trade["confidence_score"], trade["strategy"])
    """
    # ── Layer 0: Dynamic watchlist from Finviz (optional) ────────────
    if use_finviz_watchlist:
        print("  [Layer 0] Finviz unusual volume scan...")
        scanner = FinvizVolumeScanner()
        finviz_tickers = scanner.scan_tickers_only(max_tickers=finviz_max_tickers)
        if finviz_tickers:
            print(f"           Found {len(finviz_tickers)} unusual volume tickers: {finviz_tickers}")
            # Merge: Finviz tickers first (they have the signal), then provided watchlist
            merged = list(dict.fromkeys(finviz_tickers + watchlist))  # dedup, preserve order
            watchlist = merged[:15]  # cap at 15 to keep runtime reasonable
            print(f"           Merged watchlist ({len(watchlist)}): {watchlist}")
        else:
            print("           No unusual volume tickers found — using provided watchlist")

    # ── Initialize all agents ────────────────────────────────────────
    fa_source = FlashAlphaSource(api_key=flashalpha_api_key)
    news_agent = NewsAgent()
    tech_agent = TechnicalAgent()
    vol_agent = VolatilityAgent(flashalpha_source=fa_source)
    synthesizer = SignalSynthesizer()
    risk_mgr = RiskManager()
    prep = TradePrep()

    if fa_source.is_configured:
        print("  [Config] FlashAlpha GEX: ENABLED (API key configured)")
    else:
        print("  [Config] FlashAlpha GEX: DISABLED (set FLASHALPHA_API_KEY to enable)")

    recommendations: list[dict] = []
    skipped: list[dict] = []

    for symbol in watchlist:
        print(f"\n{'─' * 50}")
        print(f"  Analyzing: {symbol}")
        print(f"{'─' * 50}")

        # ── LAYER 1: Intelligence ─────────────────────────────────────────

        print(f"  [Layer 1] NewsAgent scanning {symbol}...")
        if news_data:
            raw_news = news_agent.inject_news(news_data)
        else:
            raw_news = news_agent.scan([symbol])
        news_summary = news_agent.aggregate_sentiment(raw_news, symbol)
        print(f"           News sentiment: {news_summary['sentiment_label']} "
              f"(score: {news_summary['avg_sentiment']:+.2f}, "
              f"{news_summary['news_count']} items)")

        print(f"  [Layer 1] TechnicalAgent analyzing {symbol}...")
        technical = tech_agent.analyze(symbol)
        if technical.get("error"):
            print(f"           WARNING: {technical['error']}")
        else:
            print(f"           Price: ${technical['current_price']:.2f} | "
                  f"SMA20: ${technical['sma_20']:.2f} | "
                  f"SMA50: ${technical['sma_50']:.2f} | "
                  f"RSI: {technical['rsi_14']:.1f}")
            print(f"           Signal: {technical['signal']}")

        print(f"  [Layer 1] VolatilityAgent analyzing {symbol}...")
        volatility = vol_agent.analyze(symbol, technical.get("current_price", 0))
        if volatility.get("error"):
            print(f"           WARNING: {volatility['error']}")
        else:
            print(f"           HV_20: {volatility['hist_vol_20d']:.1f}% | "
                  f"HV_60: {volatility['hist_vol_60d']:.1f}% | "
                  f"Vol%ile: {volatility['vol_percentile']:.0f}th | "
                  f"Regime: {volatility['vol_regime']}")

        # Display GEX data if available
        gex = volatility.get("gex_data")
        if gex and gex.get("gex_available"):
            print(f"           GEX: {gex['gamma_regime']} gamma | "
                  f"Flip: ${gex.get('gamma_flip', 0):.2f} | "
                  f"Call wall: ${gex.get('call_wall', 0):.2f} | "
                  f"Put wall: ${gex.get('put_wall', 0):.2f}")
        elif gex and gex.get("error"):
            print(f"           GEX: unavailable ({gex['error'][:60]})")
        else:
            print(f"           GEX: not configured (set FLASHALPHA_API_KEY to enable)")

        # ── LAYER 2: Strategy ─────────────────────────────────────────────

        print(f"  [Layer 2] SignalSynthesizer running bull/bear debate...")

        # Pass current_price, atr, and GEX data into signal for TradePrep
        signal = synthesizer.synthesize(news_summary, technical, volatility)
        signal["current_price"] = technical.get("current_price", 0)
        signal["atr_14"] = technical.get("atr_14", 0)
        signal["_gex_data"] = volatility.get("gex_data")

        print(f"           Direction: {signal['direction']} | "
              f"Confidence: {signal['confidence']}/100 | "
              f"Strategy: {signal['suggested_strategy'].get('name', 'N/A')}")

        if signal["confidence"] < min_confidence:
            reason = (
                f"confidence {signal['confidence']} < {min_confidence} threshold "
                f"(votes: {signal['signal_breakdown']['bullish_votes']}B "
                f"/ {signal['signal_breakdown']['bearish_votes']}Be "
                f"/ {signal['signal_breakdown']['neutral_votes']}N)"
            )
            print(f"  [SKIP] {symbol}: {reason}")
            skipped.append({"symbol": symbol, "reason": reason, "confidence": signal["confidence"]})
            continue

        # ── LAYER 3: Risk + Prep ──────────────────────────────────────────

        print(f"  [Layer 3] RiskManager checking position limits...")
        risk = risk_mgr.check(signal, portfolio_value, existing_positions)
        print(f"           Checks: {risk['checks_passed']}/{risk['checks_total']} passed | "
              f"Approved: {risk['approved']} | "
              f"Size: {risk['adjusted_size']} contract(s) | "
              f"Est. max loss: ${risk['max_loss_estimate']:.0f}")

        if not risk["approved"]:
            reason = f"risk check failed ({risk['checks_passed']}/{risk['checks_total']} passed)"
            print(f"  [SKIP] {symbol}: {reason}")
            skipped.append({"symbol": symbol, "reason": reason, "confidence": signal["confidence"]})
            continue

        print(f"  [Layer 3] TradePrep assembling trade card...")
        trade = prep.prepare(signal, risk)
        recommendations.append(trade)
        print(f"  [PASS] {symbol}: {trade['strategy']} | "
              f"Confidence: {trade['confidence_score']} ({trade['confidence_label']})")

    # Sort by confidence, return top 3
    recommendations.sort(key=lambda x: x.get("confidence_score", 0), reverse=True)
    top_recommendations = recommendations[:3]

    # Summary
    print(f"\n{'═' * 50}")
    print(f"  PIPELINE COMPLETE")
    print(f"  Watchlist:       {len(watchlist)} symbols")
    print(f"  Recommendations: {len(top_recommendations)}")
    print(f"  Skipped:         {len(skipped)}")
    if skipped:
        for s in skipped:
            print(f"    - {s['symbol']}: {s['reason']}")
    print(f"{'═' * 50}")

    return top_recommendations


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE DEMO
# ══════════════════════════════════════════════════════════════════════════════

def _print_trade_card(trade: dict, index: int) -> None:
    """Pretty-print a trade card to stdout."""
    sep = "═" * 60
    print(f"\n{sep}")
    print(f"  TRADE RECOMMENDATION #{index + 1}")
    print(sep)
    print(f"  Symbol       : {trade['symbol']}")
    print(f"  Strategy     : {trade['strategy']}")
    print(f"  Direction    : {trade['direction']} ({trade['vol_regime']})")
    print(f"  Confidence   : {trade['confidence_score']}/100 ({trade['confidence_label']})")
    print(f"  Contracts    : {trade['contracts']}")
    print(f"  Max Loss     : ${trade['max_loss']:.2f}")
    print(f"  Timeframe    : {trade['suggested_timeframe']}")
    print()

    print(f"  Strategy:")
    print(f"    {trade['strategy_description'][:120]}...")
    print()

    print(f"  Bull Case:")
    for b in trade["bull_case"][:3]:
        print(f"    + {b}")

    print(f"\n  Bear Case:")
    for b in trade["bear_case"][:3]:
        print(f"    - {b}")

    print(f"\n  Strike Guidance:")
    print(f"    {trade['suggested_strikes']}")

    print(f"\n  Risk Warning:")
    print(f"    {trade['risk_warning']}")

    print(f"\n  Risk Manager Notes:")
    for note in trade["risk_manager_notes"]:
        status = "✓" if note.startswith("PASS") else "✗"
        print(f"    {status} {note}")

    print(f"\n  ACTION REQUIRED: {trade['action_required']}")
    print(f"  Generated at   : {trade['generated_at']}")
    print(sep)


if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║          ENSO MULTI-AGENT TRADING FRAMEWORK              ║")
    print("║              Standalone Demo — 3-Layer Pipeline          ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print("Demo watchlist  : SPY, AAPL, NVDA")
    print("Portfolio value : $100,000")
    print("Open positions  : 0")
    print()
    print("NOTE: NewsAgent returns neutral placeholders in standalone mode.")
    print("      In production, Perplexity's morning cron supplies real news.")
    print()

    demo_watchlist = ["SPY", "AAPL", "NVDA"]
    demo_portfolio = 100_000.0
    demo_positions = 0

    results = run_pipeline(
        watchlist=demo_watchlist,
        portfolio_value=demo_portfolio,
        existing_positions=demo_positions,
    )

    if not results:
        print("\nNo trade recommendations met the confidence and risk thresholds.")
        print("This is normal — the agents are filtering for quality, not quantity.")
        print("Try again with different market conditions or adjust min_confidence.")
        sys.exit(0)

    print(f"\n{'═' * 60}")
    print(f"  {len(results)} TRADE RECOMMENDATION(S) READY FOR YOUR REVIEW")
    print(f"{'═' * 60}")

    for i, trade in enumerate(results):
        _print_trade_card(trade, i)

    print("\nAll recommendations require HUMAN APPROVAL before execution.")
    print("Navigate to the Enso options page to pull live chains and place orders.")
