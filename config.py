"""
Configuration for Indian Market Stock Advisory System.
Loads secrets from .env file — never hardcode API keys.
"""

import os
from dotenv import load_dotenv

load_dotenv()

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

# Mapping NSE symbols to yfinance tickers (append .NS for NSE)
def yf_ticker(nse_symbol: str) -> str:
    return f"{nse_symbol}.NS"

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
EMA_SHORT = 12
EMA_LONG = 26
RSI_PERIOD = 14
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ── Sentiment Thresholds ─────────────────────────────────────────────────────
SENTIMENT_BULLISH_THRESHOLD = 0.15
SENTIMENT_BEARISH_THRESHOLD = -0.15

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
