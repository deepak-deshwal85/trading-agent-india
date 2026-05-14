"""
Configuration for Indian Market Stock Advisory System.
Loads secrets from .env file — never hardcode API keys.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── OpenAlgo (market data — replaces Yahoo Finance) ───────────────────────────
OPENALGO_API_KEY = os.getenv("OPENALGO_API_KEY", "")
OPENALGO_HOST = os.getenv("OPENALGO_HOST", "http://127.0.0.1:5000")
OPENALGO_USERNAME = os.getenv("OPENALGO_USERNAME", "")
OPENALGO_EXCHANGE = os.getenv("OPENALGO_EXCHANGE", "NSE")
# Broker API history vs OpenAlgo DuckDB — use "db" if your deploy stores dailies in Historify
OPENALGO_HISTORY_SOURCE = os.getenv("OPENALGO_HISTORY_SOURCE", "api")

# ── AI Provider Configuration ─────────────────────────────────────────────────
# Options: "anthropic" | "openai"
AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic").lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

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

# ── Broker holdings (python main.py --holdings) via OpenAlgo ────────────────
# When true, merge open positions from positionbook() with demat holdings().
HOLDINGS_INCLUDE_OPENALGO_POSITIONS = os.getenv(
    "HOLDINGS_INCLUDE_OPENALGO_POSITIONS", "true"
).lower() in ("1", "true", "yes")

# ── News Source Configuration ─────────────────────────────────────────────────
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
GOOGLE_NEWS_MARKET_RSS = "https://news.google.com/rss/search?q=indian+stock+market+nifty+sensex&hl=en-IN&gl=IN&ceid=IN:en"
GOOGLE_NEWS_WORLD_RSS = "https://news.google.com/rss/search?q=global+markets+economy+fed+tariffs&hl=en-IN&gl=IN&ceid=IN:en"

ZERODHA_PULSE_URL = "https://pulse.zerodha.com/"

ET_MARKETS_RSS = "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"
MONEYCONTROL_RSS = "https://www.moneycontrol.com/rss/marketreports.xml"
LIVEMINT_RSS = "https://www.livemint.com/rss/markets"

# ── Analysis Parameters ───────────────────────────────────────────────────────
TECHNICAL_PERIOD_DAYS = 365       # 1 year of price history for technicals
SMA_SHORT = 20
SMA_LONG = 50
# Fast EMA pair for price signals (distinct from MACD’s 12/26 inputs)
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
# Indian markets: gate oscillator signals when ADX is below this (ranging regime)
ADX_GATE_THRESHOLD = 25

# ── Sentiment Thresholds ─────────────────────────────────────────────────────
SENTIMENT_BULLISH_THRESHOLD = 0.15
SENTIMENT_BEARISH_THRESHOLD = -0.15

# Ensemble (--finbert): confidence-weighted FinBERT + VADER; optional FinBERT-Tone
# Weights sum to 1.0. If FinBERT-Tone is disabled or fails to load, Prosus weight
# absorbs the tone share (see sentiment._ensemble_weights).
SENTIMENT_USE_FINBERT_TONE = os.getenv("SENTIMENT_USE_FINBERT_TONE", "true").lower() in (
    "1", "true", "yes",
)
SENTIMENT_ENSEMBLE_VADER = float(os.getenv("SENTIMENT_ENSEMBLE_VADER", "0.30"))
SENTIMENT_ENSEMBLE_PROSUS = float(os.getenv("SENTIMENT_ENSEMBLE_PROSUS", "0.45"))
SENTIMENT_ENSEMBLE_TONE = float(os.getenv("SENTIMENT_ENSEMBLE_TONE", "0.25"))
# Recency: exp(-ln(2) * hours_old / half_life) — 24h → 50% weight
SENTIMENT_RECENCY_HALF_LIFE_HOURS = float(os.getenv("SENTIMENT_RECENCY_HALF_LIFE_HOURS", "24"))

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
