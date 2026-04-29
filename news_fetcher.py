"""
News aggregation from multiple Indian and global financial sources.
"""

import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field

from config import (
    GOOGLE_NEWS_RSS, GOOGLE_NEWS_MARKET_RSS, GOOGLE_NEWS_WORLD_RSS,
    ZERODHA_PULSE_URL, ET_MARKETS_RSS, MONEYCONTROL_RSS, LIVEMINT_RSS,
    HEADERS, MAX_NEWS_PER_SOURCE, REQUEST_TIMEOUT,
)


@dataclass
class NewsItem:
    title: str
    source: str
    url: str
    published: str = ""
    summary: str = ""
    related_stocks: list = field(default_factory=list)
    category: str = "general"  # general | stock_specific | world


def _parse_rss(url: str, source_name: str, category: str = "general",
               max_items: int = MAX_NEWS_PER_SOURCE) -> list[NewsItem]:
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_items]:
            title = entry.get("title", "")
            summary_raw = entry.get("summary", entry.get("description", ""))
            summary = BeautifulSoup(summary_raw, "html.parser").get_text(strip=True)
            items.append(NewsItem(
                title=title,
                source=source_name,
                url=entry.get("link", ""),
                published=entry.get("published", ""),
                summary=summary[:500],
                category=category,
            ))
        return items
    except Exception as e:
        print(f"  [warn] RSS fetch failed for {source_name}: {e}")
        return []


def fetch_google_news_for_stock(stock_name: str) -> list[NewsItem]:
    query = f"{stock_name}+stock+NSE+India"
    url = GOOGLE_NEWS_RSS.format(query=query)
    items = _parse_rss(url, "Google News", category="stock_specific", max_items=5)
    for item in items:
        item.related_stocks.append(stock_name)
    return items


def fetch_google_market_news() -> list[NewsItem]:
    return _parse_rss(GOOGLE_NEWS_MARKET_RSS, "Google News (Market)", category="general")


def fetch_google_world_news() -> list[NewsItem]:
    return _parse_rss(GOOGLE_NEWS_WORLD_RSS, "Google News (World)", category="world")


def fetch_et_markets() -> list[NewsItem]:
    return _parse_rss(ET_MARKETS_RSS, "Economic Times Markets", category="general")


def fetch_moneycontrol() -> list[NewsItem]:
    return _parse_rss(MONEYCONTROL_RSS, "MoneyControl", category="general")


def fetch_livemint() -> list[NewsItem]:
    return _parse_rss(LIVEMINT_RSS, "LiveMint Markets", category="general")


def fetch_zerodha_pulse() -> list[NewsItem]:
    """Scrape latest headlines from Zerodha Pulse."""
    items = []
    try:
        resp = requests.get(ZERODHA_PULSE_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select(".feed-card, .story, article, .post-card")[:MAX_NEWS_PER_SOURCE]:
            title_tag = card.select_one("h2, h3, .title, a.title")
            if not title_tag:
                title_tag = card.select_one("a")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            link = title_tag.get("href", "")
            if link and not link.startswith("http"):
                link = "https://pulse.zerodha.com" + link
            summary_tag = card.select_one("p, .description, .summary")
            summary = summary_tag.get_text(strip=True)[:500] if summary_tag else ""
            items.append(NewsItem(
                title=title,
                source="Zerodha Pulse",
                url=link,
                summary=summary,
                category="general",
            ))
    except Exception as e:
        print(f"  [warn] Zerodha Pulse scrape failed: {e}")
    return items


def fetch_broker_research() -> list[NewsItem]:
    """Fetch research headlines from major Indian brokerages via Google News."""
    broker_queries = [
        ("ICICI+Securities+stock+recommendation+India", "ICICI Securities"),
        ("Motilal+Oswal+stock+pick+India", "Motilal Oswal"),
        ("HDFC+Securities+stock+recommendation+India", "HDFC Securities"),
        ("Kotak+Securities+stock+target+India", "Kotak Securities"),
        ("Axis+Securities+stock+rating+India", "Axis Securities"),
    ]
    all_items = []
    for query, source in broker_queries:
        url = GOOGLE_NEWS_RSS.format(query=query)
        items = _parse_rss(url, source, category="general", max_items=5)
        all_items.extend(items)
    return all_items


def fetch_nse_announcements() -> list[NewsItem]:
    """Fetch NSE/BSE related news via Google News RSS."""
    queries = [
        "NSE+announcements+corporate+actions+India",
        "BSE+corporate+filings+results+India",
    ]
    items = []
    for q in queries:
        url = GOOGLE_NEWS_RSS.format(query=q)
        items.extend(_parse_rss(url, "NSE/BSE News", category="general", max_items=8))
    return items


def fetch_all_market_news() -> list[NewsItem]:
    """Aggregate news from all sources."""
    all_news = []
    all_news.extend(fetch_google_market_news())
    all_news.extend(fetch_et_markets())
    all_news.extend(fetch_moneycontrol())
    all_news.extend(fetch_livemint())
    all_news.extend(fetch_zerodha_pulse())
    all_news.extend(fetch_broker_research())
    all_news.extend(fetch_nse_announcements())
    return all_news


def fetch_world_news() -> list[NewsItem]:
    """Fetch global news that may impact Indian markets."""
    queries = [
        "US+Federal+Reserve+interest+rate+decision",
        "global+recession+trade+war+tariffs",
        "crude+oil+price+OPEC",
        "China+economy+growth",
        "US+stock+market+S&P+500+Nasdaq",
    ]
    items = fetch_google_world_news()
    for q in queries:
        url = GOOGLE_NEWS_RSS.format(query=q)
        items.extend(_parse_rss(url, "World News", category="world", max_items=5))
    return items


def fetch_stock_specific_news(symbols: list[str]) -> dict[str, list[NewsItem]]:
    """Fetch news for a list of stock symbols."""
    stock_news = {}
    for sym in symbols:
        stock_news[sym] = fetch_google_news_for_stock(sym)
    return stock_news
