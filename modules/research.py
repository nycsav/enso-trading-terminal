"""
Market Research Module
- Fetch market data via yfinance
- Technical indicators
- Data preparation for S/R and backtesting
"""
import yfinance as yf
import pandas as pd
import numpy as np
from config import SYMBOLS


def fetch_market_data(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV data from yfinance."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return pd.DataFrame()
        return df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return pd.DataFrame()


def fetch_multi_symbol_data(symbols: list = None, period: str = "6mo") -> dict:
    """Fetch data for multiple symbols."""
    symbols = symbols or SYMBOLS
    data = {}
    for sym in symbols:
        df = fetch_market_data(sym, period=period)
        if not df.empty:
            data[sym] = df
    return data


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add common technical indicators to dataframe."""
    df = df.copy()

    # Moving averages
    df["SMA_20"] = df["Close"].rolling(20).mean()
    df["SMA_50"] = df["Close"].rolling(50).mean()
    df["EMA_12"] = df["Close"].ewm(span=12).mean()
    df["EMA_26"] = df["Close"].ewm(span=26).mean()

    # MACD
    df["MACD"] = df["EMA_12"] - df["EMA_26"]
    df["MACD_Signal"] = df["MACD"].ewm(span=9).mean()

    # RSI
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # Bollinger Bands
    df["BB_Mid"] = df["Close"].rolling(20).mean()
    bb_std = df["Close"].rolling(20).std()
    df["BB_Upper"] = df["BB_Mid"] + 2 * bb_std
    df["BB_Lower"] = df["BB_Mid"] - 2 * bb_std

    # ATR
    high_low = df["High"] - df["Low"]
    high_close = abs(df["High"] - df["Close"].shift())
    low_close = abs(df["Low"] - df["Close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(14).mean()

    # Volume SMA
    df["Vol_SMA_20"] = df["Volume"].rolling(20).mean()

    return df


def get_symbol_info(symbol: str) -> dict:
    """Get basic info about a symbol."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return {
            "symbol": symbol,
            "name": info.get("shortName", symbol),
            "sector": info.get("sector", "N/A"),
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE", 0),
            "52w_high": info.get("fiftyTwoWeekHigh", 0),
            "52w_low": info.get("fiftyTwoWeekLow", 0),
        }
    except Exception:
        return {"symbol": symbol, "name": symbol}
