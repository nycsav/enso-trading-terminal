"""
LLM-Powered Signal Analysis
- Perplexity Sonar API for real-time financial news sentiment
- News headline sentiment scoring
- Market context enrichment for ML signals
- Graceful fallback when API key not configured
"""
import os
import requests
import json
from datetime import datetime
from typing import Optional


PPLX_API_KEY = os.environ.get("PPLX_API_KEY", "")
PPLX_API_URL = "https://api.perplexity.ai/chat/completions"


def get_market_sentiment(symbol: str, api_key: str = None) -> dict:
    """
    Query Perplexity Sonar for real-time market sentiment on a symbol.
    Returns sentiment score (-100 to 100) and key news themes.
    """
    key = api_key or PPLX_API_KEY
    if not key:
        return {
            "sentiment_score": 0,
            "confidence": 0,
            "themes": [],
            "source": "none",
            "error": "No Perplexity API key configured",
        }

    try:
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        prompt = (
            f"Analyze the current market sentiment for {symbol} stock. "
            f"Consider recent news, earnings, analyst ratings, and market conditions. "
            f"Respond in JSON format with: "
            f'{{"sentiment_score": <-100 to 100>, "confidence": <0 to 100>, '
            f'"bull_factors": ["..."], "bear_factors": ["..."], '
            f'"key_event": "...", "outlook": "bullish/bearish/neutral"}}'
        )

        payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": "You are a financial analyst. Respond only in valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 500,
            "temperature": 0.1,
        }

        response = requests.post(PPLX_API_URL, headers=headers,
                                 json=payload, timeout=15)
        response.raise_for_status()

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        # Parse JSON from response
        try:
            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            parsed = json.loads(content.strip())
        except json.JSONDecodeError:
            parsed = {
                "sentiment_score": 0,
                "confidence": 30,
                "bull_factors": [],
                "bear_factors": [],
                "key_event": "Unable to parse response",
                "outlook": "neutral",
            }

        return {
            "sentiment_score": parsed.get("sentiment_score", 0),
            "confidence": parsed.get("confidence", 50),
            "themes": (
                parsed.get("bull_factors", [])[:3]
                + parsed.get("bear_factors", [])[:3]
            ),
            "outlook": parsed.get("outlook", "neutral"),
            "key_event": parsed.get("key_event", ""),
            "source": "perplexity_sonar",
            "timestamp": datetime.now().isoformat(),
        }

    except requests.exceptions.Timeout:
        return {
            "sentiment_score": 0,
            "confidence": 0,
            "themes": [],
            "source": "error",
            "error": "API timeout",
        }
    except Exception as e:
        return {
            "sentiment_score": 0,
            "confidence": 0,
            "themes": [],
            "source": "error",
            "error": str(e),
        }


def get_options_flow(symbol: str, api_key: str = None) -> dict:
    """
    Query for unusual options activity and institutional flow.
    """
    key = api_key or PPLX_API_KEY
    if not key:
        return {
            "unusual_activity": False,
            "flow_bias": "neutral",
            "confidence": 0,
            "source": "none",
            "error": "No API key",
        }

    try:
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        prompt = (
            f"What is the current unusual options activity for {symbol}? "
            f"Report any large block trades, unusual volume, or institutional positioning. "
            f"Respond in JSON: "
            f'{{"unusual_activity": true/false, "flow_bias": "bullish/bearish/neutral", '
            f'"confidence": <0-100>, "notable_trades": ["..."], '
            f'"put_call_ratio": <float>, "iv_rank": <0-100>}}'
        )

        payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": "You are an options flow analyst. Respond only in valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 400,
            "temperature": 0.1,
        }

        response = requests.post(PPLX_API_URL, headers=headers,
                                 json=payload, timeout=15)
        response.raise_for_status()

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            parsed = json.loads(content.strip())
        except json.JSONDecodeError:
            parsed = {"unusual_activity": False, "flow_bias": "neutral", "confidence": 0}

        return {
            "unusual_activity": parsed.get("unusual_activity", False),
            "flow_bias": parsed.get("flow_bias", "neutral"),
            "confidence": parsed.get("confidence", 0),
            "notable_trades": parsed.get("notable_trades", [])[:3],
            "put_call_ratio": parsed.get("put_call_ratio", 1.0),
            "iv_rank": parsed.get("iv_rank", 50),
            "source": "perplexity_sonar",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        return {
            "unusual_activity": False,
            "flow_bias": "neutral",
            "confidence": 0,
            "source": "error",
            "error": str(e),
        }


def enrich_signal(signal: dict, symbol: str, api_key: str = None) -> dict:
    """
    Enrich an ML signal with LLM-derived sentiment and flow data.
    Adjusts confidence based on sentiment alignment.
    """
    sentiment = get_market_sentiment(symbol, api_key)
    flow = get_options_flow(symbol, api_key)

    # Base signal
    enriched = signal.copy()
    enriched["sentiment"] = sentiment
    enriched["options_flow"] = flow

    # Adjust confidence based on alignment
    original_confidence = signal.get("confidence", 50)
    adjustment = 0

    # Sentiment alignment
    if sentiment.get("confidence", 0) > 40:
        if signal.get("signal") == "BUY_CALL" and sentiment.get("sentiment_score", 0) > 20:
            adjustment += 10
        elif signal.get("signal") == "BUY_PUT" and sentiment.get("sentiment_score", 0) < -20:
            adjustment += 10
        elif signal.get("signal") == "BUY_CALL" and sentiment.get("sentiment_score", 0) < -30:
            adjustment -= 15  # Contradicting sentiment
        elif signal.get("signal") == "BUY_PUT" and sentiment.get("sentiment_score", 0) > 30:
            adjustment -= 15

    # Options flow alignment
    if flow.get("confidence", 0) > 40:
        if signal.get("signal") == "BUY_CALL" and flow.get("flow_bias") == "bullish":
            adjustment += 8
        elif signal.get("signal") == "BUY_PUT" and flow.get("flow_bias") == "bearish":
            adjustment += 8
        elif flow.get("unusual_activity", False):
            adjustment += 5  # Unusual activity = higher conviction

    enriched["adjusted_confidence"] = max(0, min(100, original_confidence + adjustment))
    enriched["confidence_adjustment"] = adjustment

    return enriched
