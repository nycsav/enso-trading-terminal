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

# Risk management defaults
STOP_LOSS_PCT = 50  # Cut position at -50% of premium paid
TAKE_PROFIT_PCT = 100  # Take profit at +100% of premium paid
MAX_EXPOSURE_PCT = 25  # Never have more than 25% of capital at risk
OTM_OFFSET_PCT = 2.0  # Use strikes 2% OTM for better risk/reward
IV_RANK_MAX = 50  # Only buy options when IV percentile < 50 (cheaper premiums)
IV_LOOKBACK_WINDOW = 60  # Days to compute IV rank

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

# ML Strategy defaults
ML_FORWARD_DAYS = 15  # Prediction horizon
ML_THRESHOLD_PCT = 2.0  # Min move to trigger signal
ML_MIN_CONFIDENCE = 55.0  # Min model confidence to trade
ML_N_ESTIMATORS = 200
ML_MAX_DEPTH = 4
ML_LEARNING_RATE = 0.05

# RL Agent defaults
RL_ALPHA = 0.1  # Learning rate
RL_GAMMA = 0.95  # Discount factor
RL_EPSILON = 0.15  # Exploration rate

# LLM / Perplexity API
PPLX_API_KEY = os.environ.get("PPLX_API_KEY", "")
