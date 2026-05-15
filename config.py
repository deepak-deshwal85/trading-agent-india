"""
Configuration for Indian Market Stock Advisory System.
- app.env  — non-secret app settings (models, thresholds); committed to git
- .env     — secrets only (API keys, Telegram); never commit
"""

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
# Defaults from app.env; .env may override any key (e.g. emergency model swap)
load_dotenv(_ROOT / "app.env", override=False)
load_dotenv(_ROOT / ".env", override=True)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    return _env(key, "true" if default else "false").lower() in ("1", "true", "yes")


def _env_float(key: str, default: float) -> float:
    try:
        return float(_env(key, str(default)))
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


# ── AI Provider (runtime: CLI --provider anthropic | openai) ─────────────────
AI_PROVIDER = ""

# Secrets — .env only
ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
OPENAI_API_KEY = _env("OPENAI_API_KEY")

# Models — app.env defaults; .env may override *_DEEP / *_FAST if needed
ANTHROPIC_MODEL_FAST = _env("ANTHROPIC_MODEL_FAST", "claude-haiku-4-5")
ANTHROPIC_MODEL_DEEP = _env("ANTHROPIC_MODEL_DEEP", "claude-sonnet-4-6")
OPENAI_MODEL_FAST = _env("OPENAI_MODEL_FAST", "gpt-4o-mini")
OPENAI_MODEL_DEEP = (
    _env("OPENAI_MODEL_DEEP")
    or _env("OPENAI_MODEL")
    or "gpt-4o"
)

# Back-compat alias (deep tier, OpenAI only)
OPENAI_MODEL = OPENAI_MODEL_DEEP

AI_SENTIMENT_USE_LLM = _env_bool("AI_SENTIMENT_USE_LLM", True)
AI_SENTIMENT_BATCH_SIZE = _env_int("AI_SENTIMENT_BATCH_SIZE", 25)
AI_SENTIMENT_MAX_TOKENS = _env_int("AI_SENTIMENT_MAX_TOKENS", 1024)

# ── Telegram (.env) ───────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _env("TELEGRAM_CHAT_ID")
TELEGRAM_CAPTION = _env("TELEGRAM_CAPTION")

# ── Nifty 50 Constituents (NSE Symbols) ──────────────────────────────────────
NIFTY_50 = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL",
    "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DIVISLAB",
    "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK",
    "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK",
    "INDUSINDBK", "INFY", "ITC", "JSWSTEEL", "KOTAKBANK",
    "LT", "M&M", "MARUTI", "NESTLEIND", "NTPC",
    "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SBIN",
    "SHRIRAMFIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS",
    "TATASTEEL", "TECHM", "TITAN", "TRENT", "ULTRACEMCO",
    "WIPRO",
]

# ── News Source Configuration ─────────────────────────────────────────────────
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
GOOGLE_NEWS_MARKET_RSS = "https://news.google.com/rss/search?q=indian+stock+market+nifty+sensex&hl=en-IN&gl=IN&ceid=IN:en"
GOOGLE_NEWS_WORLD_RSS = "https://news.google.com/rss/search?q=global+markets+economy+fed+tariffs&hl=en-IN&gl=IN&ceid=IN:en"

ZERODHA_PULSE_URL = "https://pulse.zerodha.com/"

ET_MARKETS_RSS = "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"
MONEYCONTROL_RSS = "https://www.moneycontrol.com/rss/marketreports.xml"
LIVEMINT_RSS = "https://www.livemint.com/rss/markets"

# ── Analysis Parameters ───────────────────────────────────────────────────────
TECHNICAL_PERIOD_DAYS = 365
SMA_SHORT = 20
SMA_LONG = 50
EMA_SHORT = 9
EMA_LONG = 21
RSI_PERIOD = 14
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
ATR_PERIOD = 14
STOCH_K = 14
STOCH_D = 3
STOCH_SMOOTH_K = 3
SUPERTREND_LENGTH = 7
SUPERTREND_MULTIPLIER = 3
ADX_GATE_THRESHOLD = 25

# ── Sentiment Thresholds ─────────────────────────────────────────────────────
SENTIMENT_BULLISH_THRESHOLD = 0.15
SENTIMENT_BEARISH_THRESHOLD = -0.15

SENTIMENT_USE_FINBERT_TONE = _env_bool("SENTIMENT_USE_FINBERT_TONE", True)
SENTIMENT_ENSEMBLE_VADER = _env_float("SENTIMENT_ENSEMBLE_VADER", 0.30)
SENTIMENT_ENSEMBLE_PROSUS = _env_float("SENTIMENT_ENSEMBLE_PROSUS", 0.45)
SENTIMENT_ENSEMBLE_TONE = _env_float("SENTIMENT_ENSEMBLE_TONE", 0.25)
SENTIMENT_RECENCY_HALF_LIFE_HOURS = _env_float("SENTIMENT_RECENCY_HALF_LIFE_HOURS", 24.0)

# ── Recommendation Weights ────────────────────────────────────────────────────
WEIGHT_SENTIMENT = 0.25
WEIGHT_FUNDAMENTAL = 0.40
WEIGHT_TECHNICAL = 0.35

# ── Request Headers ───────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

MAX_NEWS_PER_SOURCE = 15
REQUEST_TIMEOUT = 15

# Fixed PDF output path (always written after analysis)
PDF_REPORT_PATH = "reports/market_report.pdf"


def resolve_ai_model(tier: str = "deep") -> str:
    """Return model id for CLI provider and tier: 'fast' (Haiku) or 'deep' (Sonnet)."""
    provider = AI_PROVIDER.lower().strip()
    if provider == "openai":
        return OPENAI_MODEL_FAST if tier == "fast" else OPENAI_MODEL_DEEP
    if provider == "anthropic":
        return ANTHROPIC_MODEL_FAST if tier == "fast" else ANTHROPIC_MODEL_DEEP
    raise RuntimeError("AI provider not set. Use --ai --provider anthropic|openai.")
