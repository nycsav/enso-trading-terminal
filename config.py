"""
Enso Trading Terminal - Configuration
Reads API credentials from environment variables or .env file.
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Public.com API (via publicdotcom-py SDK)
# ---------------------------------------------------------------------------
PUBLIC_COM_SECRET = os.environ.get("PUBLIC_COM_SECRET", "")
PUBLIC_COM_ACCOUNT_ID = os.environ.get("PUBLIC_COM_ACCOUNT_ID", "5LF05438")

# All known accounts
ACCOUNTS = {
    "brokerage": "5LF05438",
    "bond": "3CT06086",
    "high_yield": "5OT26212",
}

# ---------------------------------------------------------------------------
# Default symbols for analysis
# ---------------------------------------------------------------------------
SYMBOLS = ["AMD", "QQQ", "SPY", "META", "TSLA", "NVDA", "AMZN", "GOOGL", "MSFT", "AAPL"]

# ---------------------------------------------------------------------------
# S/R Engine defaults
# ---------------------------------------------------------------------------
SR_LOOKBACK_DAYS = 20
PROXIMITY_THRESHOLD_PCT = 1.5

# ---------------------------------------------------------------------------
# Confluence scoring weights
# ---------------------------------------------------------------------------
CONFLUENCE_WEIGHTS = {
    "proximity": 0.30,
    "volume": 0.25,
    "trend": 0.25,
    "retest": 0.20,
}

# ---------------------------------------------------------------------------
# Backtester defaults
# ---------------------------------------------------------------------------
DEFAULT_CAPITAL = 10000
DEFAULT_POSITION_SIZE_PCT = 5
DEFAULT_OPTION_EXPIRY_WEEKS = 3
WALK_FORWARD_TRAIN_RATIO = 0.70

# Risk management defaults
STOP_LOSS_PCT = 50
TAKE_PROFIT_PCT = 100
MAX_EXPOSURE_PCT = 25
OTM_OFFSET_PCT = 2.0
IV_RANK_MAX = 50
IV_LOOKBACK_WINDOW = 60

# ---------------------------------------------------------------------------
# ML Strategy defaults
# ---------------------------------------------------------------------------
ML_FORWARD_DAYS = 15
ML_THRESHOLD_PCT = 2.0
ML_MIN_CONFIDENCE = 55.0
ML_N_ESTIMATORS = 200
ML_MAX_DEPTH = 4
ML_LEARNING_RATE = 0.05

# ---------------------------------------------------------------------------
# RL Agent defaults
# ---------------------------------------------------------------------------
RL_ALPHA = 0.1
RL_GAMMA = 0.95
RL_EPSILON = 0.15

# ---------------------------------------------------------------------------
# Dashboard settings
# ---------------------------------------------------------------------------
DASH_HOST = "0.0.0.0"
DASH_PORT = int(os.environ.get("PORT", 8050))
DASH_DEBUG = os.environ.get("DASH_DEBUG", "false").lower() == "true"
REFRESH_INTERVAL_MS = 30_000  # 30 seconds
SR_PROXIMITY_PCT = 1.5
OPTIONS_WEEKS_OUT = (2, 4)
MARKET_OPEN_HOUR = 9  # ET
MARKET_OPEN_MIN = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MIN = 0

# ---------------------------------------------------------------------------
# Signal filter defaults (modules/signal_filters.py)
# ---------------------------------------------------------------------------
TOD_OPEN_BUFFER_MIN = 30            # block signals in first 30 min after open
TOD_CLOSE_BUFFER_MIN = 15           # block signals in last 15 min before close
TOD_ECON_RELEASE_BUFFER_MIN = 30    # block ±30 min around scheduled econ releases
FAILED_BREAKDOWN_LOOKBACK = 3       # bars to scan for failed breakdown
FAILED_BREAKDOWN_TOLERANCE_PCT = 0.1  # pct below support that counts as a pierce

# ---------------------------------------------------------------------------
# Theme colors (dark terminal aesthetic)
# ---------------------------------------------------------------------------
COLORS = {
    "bg": "#0d1117",
    "surface": "#161b22",
    "surface_alt": "#1c2333",
    "border": "#30363d",
    "text": "#e6edf3",
    "text_muted": "#8b949e",
    "text_faint": "#484f58",
    "green": "#3fb950",
    "red": "#f85149",
    "blue": "#58a6ff",
    "yellow": "#d29922",
    "purple": "#bc8cff",
    "orange": "#ffa657",
}

# ---------------------------------------------------------------------------
# LLM / Perplexity API
# ---------------------------------------------------------------------------
PPLX_API_KEY = os.environ.get("PPLX_API_KEY", "")


# ---------------------------------------------------------------------------
# Validate on import
# ---------------------------------------------------------------------------
def validate_config():
    warnings = []
    if not PUBLIC_COM_SECRET:
        warnings.append("PUBLIC_COM_SECRET not set - live brokerage data disabled. Set via env var or .env file.")
    if not PPLX_API_KEY:
        warnings.append("PPLX_API_KEY not set - AI research panel will use demo data.")
    return warnings
