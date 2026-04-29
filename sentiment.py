"""
Sentiment analysis for financial news using VADER and optionally FinBERT.
VADER runs instantly (no GPU needed). FinBERT gives deeper financial-domain accuracy.
"""

import os
from dataclasses import dataclass
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from news_fetcher import NewsItem
from config import SENTIMENT_BULLISH_THRESHOLD, SENTIMENT_BEARISH_THRESHOLD


@dataclass
class SentimentResult:
    text: str
    compound_score: float   # -1.0 (bearish) to +1.0 (bullish)
    label: str              # Bullish | Bearish | Neutral
    model_used: str         # vader | finbert


# ── Financial lexicon additions for VADER ─────────────────────────────────────
_FINANCIAL_LEXICON = {
    "bullish": 2.5, "bearish": -2.5, "rally": 2.0, "crash": -3.0,
    "surge": 2.2, "plunge": -2.8, "upgrade": 2.0, "downgrade": -2.0,
    "outperform": 1.8, "underperform": -1.8, "buy": 1.5, "sell": -1.5,
    "overweight": 1.5, "underweight": -1.5, "breakout": 2.0, "breakdown": -2.0,
    "accumulate": 1.8, "reduce": -1.2, "target": 0.5, "dividend": 1.0,
    "profit": 1.5, "loss": -1.5, "growth": 1.5, "decline": -1.5,
    "earnings beat": 2.5, "earnings miss": -2.5, "record high": 2.5,
    "all-time high": 2.5, "52-week low": -2.0, "52-week high": 2.0,
    "inflation": -0.8, "recession": -2.5, "recovery": 1.8,
    "FII buying": 2.0, "FII selling": -2.0, "DII buying": 1.5,
    "rate hike": -1.5, "rate cut": 1.5, "hawkish": -1.0, "dovish": 1.0,
    "tariff": -1.2, "sanctions": -1.5, "stimulus": 1.8,
    "nifty up": 1.5, "nifty down": -1.5, "sensex up": 1.5, "sensex down": -1.5,
    "robust": 1.5, "weak": -1.2, "strong results": 2.0, "poor results": -2.0,
    "margin expansion": 1.8, "margin contraction": -1.8,
    "order win": 2.0, "order book": 1.2, "debt reduction": 1.5,
}


def _get_vader_analyzer() -> SentimentIntensityAnalyzer:
    analyzer = SentimentIntensityAnalyzer()
    analyzer.lexicon.update(_FINANCIAL_LEXICON)
    return analyzer


_vader = _get_vader_analyzer()


def analyze_sentiment_vader(text: str) -> SentimentResult:
    scores = _vader.polarity_scores(text)
    compound = scores["compound"]
    if compound >= SENTIMENT_BULLISH_THRESHOLD:
        label = "Bullish"
    elif compound <= SENTIMENT_BEARISH_THRESHOLD:
        label = "Bearish"
    else:
        label = "Neutral"
    return SentimentResult(
        text=text[:200],
        compound_score=round(compound, 4),
        label=label,
        model_used="vader",
    )


def _load_finbert():
    """Lazy-load FinBERT model (downloads ~400MB on first run)."""
    try:
        from transformers import pipeline
        return pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            tokenizer="ProsusAI/finbert",
            top_k=None,
        )
    except Exception as e:
        print(f"  [warn] FinBERT load failed: {e}. Falling back to VADER.")
        return None


_finbert_pipeline = None


def analyze_sentiment_finbert(text: str) -> SentimentResult:
    global _finbert_pipeline
    if _finbert_pipeline is None:
        _finbert_pipeline = _load_finbert()
    if _finbert_pipeline is None:
        return analyze_sentiment_vader(text)

    try:
        truncated = text[:512]
        results = _finbert_pipeline(truncated)
        if isinstance(results, list) and isinstance(results[0], list):
            results = results[0]
        score_map = {}
        for r in results:
            score_map[r["label"]] = r["score"]

        positive = score_map.get("positive", 0)
        negative = score_map.get("negative", 0)
        neutral = score_map.get("neutral", 0)

        compound = positive - negative  # range: -1 to +1

        if compound >= SENTIMENT_BULLISH_THRESHOLD:
            label = "Bullish"
        elif compound <= SENTIMENT_BEARISH_THRESHOLD:
            label = "Bearish"
        else:
            label = "Neutral"

        return SentimentResult(
            text=text[:200],
            compound_score=round(compound, 4),
            label=label,
            model_used="finbert",
        )
    except Exception:
        return analyze_sentiment_vader(text)


def analyze_news_sentiment(news_items: list[NewsItem],
                           use_finbert: bool = False) -> list[SentimentResult]:
    """Analyze sentiment for a batch of news items."""
    analyze_fn = analyze_sentiment_finbert if use_finbert else analyze_sentiment_vader
    results = []
    for item in news_items:
        text = f"{item.title}. {item.summary}" if item.summary else item.title
        results.append(analyze_fn(text))
    return results


def aggregate_sentiment(results: list[SentimentResult]) -> dict:
    """Compute aggregate sentiment statistics."""
    if not results:
        return {
            "avg_score": 0.0, "label": "Neutral",
            "bullish_pct": 0, "bearish_pct": 0, "neutral_pct": 0,
            "count": 0,
        }
    scores = [r.compound_score for r in results]
    avg = sum(scores) / len(scores)
    bullish = sum(1 for r in results if r.label == "Bullish")
    bearish = sum(1 for r in results if r.label == "Bearish")
    neutral = sum(1 for r in results if r.label == "Neutral")
    total = len(results)

    if avg >= SENTIMENT_BULLISH_THRESHOLD:
        label = "Bullish"
    elif avg <= SENTIMENT_BEARISH_THRESHOLD:
        label = "Bearish"
    else:
        label = "Neutral"

    return {
        "avg_score": round(avg, 4),
        "label": label,
        "bullish_pct": round(bullish / total * 100, 1),
        "bearish_pct": round(bearish / total * 100, 1),
        "neutral_pct": round(neutral / total * 100, 1),
        "count": total,
    }
