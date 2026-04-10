"""
Enso Trading Terminal - Configuration
"""
import os

# Public.com API
PUBLIC_API_KEY = os.environ.get("PUBLIC_API_KEY", "")
PUBLIC_API_BASE = "https://api.public.com/v1"

# Default symbols for analysis
SYMBOLS = ["AMD", "QQQ", "SPY", "META", "TSLA", "NVDA", "AMZN", "GOOGL", "MSFT", "AAPL"]

# S/R Engine defaults
SR_LOOKBACK_DAYS = 20
PROXIMITY_THRESHOLD_PCT = 1.5  # Default proximity threshold (%)

# Backtester defaults
DEFAULT_CAPITAL = 10000
DEFAULT_POSITION_SIZE_PCT = 5  # % of capital per trade
DEFAULT_OPTION_EXPIRY_WEEKS = 3
WALK_FORWARD_TRAIN_RATIO = 0.70  # 70/30 split

# Confluence scoring weights
CONFLUENCE_WEIGHTS = {
    "proximity": 0.30,
    "volume": 0.25,
    "trend": 0.25,
    "retest": 0.20,
}

# Dashboard
DASH_HOST = "0.0.0.0"
DASH_PORT = int(os.environ.get("PORT", 8050))
DASH_DEBUG = os.environ.get("DASH_DEBUG", "false").lower() == "true"
