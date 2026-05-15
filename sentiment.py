"""
Sentiment analysis for financial news using a VADER + ProsusAI FinBERT ensemble
(by default), optional yiyanghkust/finbert-tone weights, source credibility,
and recency decay. Falls back to VADER when FinBERT cannot be loaded.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from news_fetcher import NewsItem
from config import (
    SENTIMENT_BULLISH_THRESHOLD,
    SENTIMENT_BEARISH_THRESHOLD,
    SENTIMENT_USE_FINBERT_TONE,
    SENTIMENT_ENSEMBLE_VADER,
    SENTIMENT_ENSEMBLE_PROSUS,
    SENTIMENT_ENSEMBLE_TONE,
    SENTIMENT_RECENCY_HALF_LIFE_HOURS,
)


@dataclass
class SentimentResult:
    text: str
    compound_score: float  # -1.0 (bearish) to +1.0 (bullish), ensemble or single model
    label: str  # Bullish | Bearish | Neutral
    model_used: str  # vader | finbert | ensemble
    blend_weight: float = 1.0  # source credibility × recency (for aggregate_sentiment)


# ── Global financial lexicon (VADER) ─────────────────────────────────────────
_FINANCIAL_LEXICON_CORE = {
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

# ── India-specific regulatory, exchange, and flow language ─────────────────
_INDIA_LEXICON = {
    # RBI / policy
    "repo rate unchanged": 0.8, "rate pause": 0.6, "status quo": 0.4,
    "repo rate cut": 1.8, "repo rate hike": -1.6, "mpc meeting": 0.1,
    "liquidity infusion": 1.4, "liquidity withdrawal": -1.2,
    "crr cut": 1.3, "crr hike": -1.2, "slr": 0.0,
    "rbi governor": 0.1, "rbi circular": 0.2, "rbi penalty": -1.8,
    "rbi approval": 1.2, "rbi crackdown": -1.5,
    # SEBI / compliance
    "sebi order": -0.8, "sebi probe": -2.0, "sebi investigation": -2.0,
    "sebi approval": 1.5, "sebi nod": 1.4, "sebi clears": 1.4,
    "sebi fine": -1.8, "sebi bars": -2.2, "insider trading": -2.5,
    "open offer": 0.3, "takeover code": 0.0, "delisting": -0.8,
    # Promoters / governance
    "promoter pledge": -1.8, "pledge shares": -1.6, "unpledge": 1.0,
    "promoter buying": 2.0, "promoter selling": -1.8,
    "promoter stake reduction": -2.0, "stake sale": -1.0,
    "insider buying": 1.8, "insider selling": -1.8,
    "related party": -0.6, "corporate governance": -0.2,
    # NSE / BSE / market microstructure
    "circuit breaker": -1.5, "upper circuit": 2.0, "lower circuit": -2.0,
    "f&o ban": -1.4, "fno ban": -1.4, "ban in f&o": -1.4,
    "trade-to-trade": -0.8, "asm list": -0.9, "gsm stage": -1.0,
    "bulk deal": 0.2, "block deal": 0.2, "bulk deals": 0.2,
    "qip": -0.4, "qualified institutional placement": -0.4,
    "rights issue": -0.3, "preferential allotment": -0.2,
    "stock split": 0.8, "bonus issue": 1.0, "buyback": 1.6,
    "dividend declared": 1.3, "interim dividend": 1.2, "special dividend": 1.4,
    "results beat": 2.2, "results miss": -2.2, "guidance cut": -2.0,
    "guidance raise": 2.0, "revenue beat": 1.8, "ebitda beat": 1.9,
    "margin beat": 1.7, "margin miss": -1.7,
    # Flows (India)
    "fii outflow": -2.0, "fii inflow": 2.0, "fii selling": -2.0,
    "dii buying": 1.6, "dii selling": -1.4, "dii support": 1.2,
    "net buyer": 1.3, "net seller": -1.3, "institutional buying": 1.5,
    "mutual fund buying": 1.3, "sip flows": 1.0,
    # Risk / credit
    "auditor resignation": -2.5, "auditor change": -0.8,
    "going concern": -2.5, "npl spike": -2.0, "gnpa": -1.2,
    "asset quality": -0.3, "write-off": -1.8, "write back": 1.2,
    "fraud": -2.8, "forensic audit": -1.5, "default": -2.2,
    "debt restructuring": -1.0, "one-time charge": -1.0,
    # Macro India
    "monsoon": 0.6, "deficient monsoon": -1.0, "msp hike": 0.4,
    "gst collection": 0.3, "fiscal deficit": -0.6,
    # Sectors / events often in Indian headlines
    "coal shortage": -0.8, "power demand": 0.4,
    "import duty cut": 0.8, "import duty hike": -0.8,
    "pli scheme": 1.2, "production linked incentive": 1.2,
    "disinvestment": 0.2, "strategic sale": 0.3, "psu stake sale": -0.2,
    # ADR / global listing context
    "adr": 0.0, "gdr": 0.0,
}

_FINANCIAL_LEXICON = {**_FINANCIAL_LEXICON_CORE, **_INDIA_LEXICON}


def _get_vader_analyzer() -> SentimentIntensityAnalyzer:
    analyzer = SentimentIntensityAnalyzer()
    analyzer.lexicon.update(_FINANCIAL_LEXICON)
    return analyzer


_vader = _get_vader_analyzer()


def _label_from_compound(compound: float) -> str:
    if compound >= SENTIMENT_BULLISH_THRESHOLD:
        return "Bullish"
    if compound <= SENTIMENT_BEARISH_THRESHOLD:
        return "Bearish"
    return "Neutral"


def analyze_sentiment_vader(text: str) -> SentimentResult:
    scores = _vader.polarity_scores(text)
    compound = scores["compound"]
    return SentimentResult(
        text=text[:200],
        compound_score=round(compound, 4),
        label=_label_from_compound(compound),
        model_used="vader",
    )


def source_credibility_multiplier(item: NewsItem) -> float:
    """Higher weight for filings / regulators / top outlets; lower for social."""
    blob = f"{item.source} {item.url} {item.title}".lower()

    if any(s in blob for s in ("reddit.com", "twitter.com", "x.com", "telegram", ".t.me/", "t.me/")):
        return 0.6

    if "sebi.gov" in blob or "rbi.org" in blob or "rbi.gov" in blob:
        return 1.5
    if " sebi " in f" {blob} " or " rbi " in f" {blob} " or "reserve bank" in blob:
        return 1.5

    if "nseindia.com" in blob or "bseindia.com" in blob or "nse/bse" in item.source.lower():
        return 1.5

    if any(d in blob for d in ("economictimes.indiatimes.com", "moneycontrol.com", "livemint.com")):
        return 1.2
    src_l = item.source.lower()
    if any(x in src_l for x in ("economic times", "moneycontrol", "livemint")):
        return 1.2

    if any(
        x in item.source
        for x in (
            "ICICI Securities", "Motilal Oswal", "HDFC Securities",
            "Kotak Securities", "Axis Securities",
        )
    ):
        return 1.3

    return 1.0


def recency_weight(
    published_at: Optional[datetime],
    *,
    half_life_hours: float = SENTIMENT_RECENCY_HALF_LIFE_HOURS,
) -> float:
    """Exponential decay: half_life_hours old → ~50% weight."""
    if published_at is None or half_life_hours <= 0:
        return 1.0
    now = datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    hours_old = (now - published_at).total_seconds() / 3600.0
    if hours_old < 0:
        return 1.0
    return math.exp(-0.693 * hours_old / half_life_hours)


def _canonical_sentiment_label(label: str) -> str:
    raw = label.strip().lower()
    if raw.startswith("label_"):
        # yiyanghkust/finbert-tone id2label: 0 Neutral, 1 Positive, 2 Negative
        n = raw.replace("label_", "")
        if n == "1":
            return "positive"
        if n == "2":
            return "negative"
        return "neutral"
    if "pos" in raw and "neg" not in raw:
        return "positive"
    if "neg" in raw:
        return "negative"
    return "neutral"


def _directional_confidence_score(pipeline_results: list[dict[str, Any]]) -> float:
    """Argmax label × its probability in [-1, 1] (neutral → 0)."""
    if not pipeline_results:
        return 0.0
    top = max(pipeline_results, key=lambda r: float(r["score"]))
    lab = _canonical_sentiment_label(str(top["label"]))
    conf = float(top["score"])
    if lab == "positive":
        return conf
    if lab == "negative":
        return -conf
    return 0.0


def _load_finbert() -> Optional[Any]:
    try:
        from transformers import pipeline
        return pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            tokenizer="ProsusAI/finbert",
            top_k=None,
        )
    except Exception as e:
        logging.getLogger("sentiment").debug(
            "FinBERT (ProsusAI) load failed: %s — ensemble will fall back to VADER", e
        )
        return None


_finbert_pipeline: Optional[Any] = None
_finbert_load_failed = False
_finbert_tone_pipeline: Optional[Any] = None
_finbert_tone_attempted = False


def _get_finbert_pipeline() -> Optional[Any]:
    global _finbert_pipeline, _finbert_load_failed
    if _finbert_load_failed:
        return None
    if _finbert_pipeline is None:
        _finbert_pipeline = _load_finbert()
        if _finbert_pipeline is None:
            _finbert_load_failed = True
    return _finbert_pipeline


def _get_finbert_tone_pipeline() -> Optional[Any]:
    global _finbert_tone_pipeline, _finbert_tone_attempted
    if not SENTIMENT_USE_FINBERT_TONE:
        return None
    if _finbert_tone_attempted:
        return _finbert_tone_pipeline
    _finbert_tone_attempted = True
    try:
        from transformers import pipeline
        _finbert_tone_pipeline = pipeline(
            "sentiment-analysis",
            model="yiyanghkust/finbert-tone",
            tokenizer="yiyanghkust/finbert-tone",
            top_k=None,
        )
    except Exception as e:
        logging.getLogger("sentiment").debug(
            "FinBERT-Tone load failed: %s — continuing without tone model", e
        )
        _finbert_tone_pipeline = None
    return _finbert_tone_pipeline


def _run_finbert_pipeline(pipe: Any, text: str) -> float:
    truncated = text[:512]
    out = pipe(truncated)
    if isinstance(out, list) and out and isinstance(out[0], list):
        out = out[0]
    if not isinstance(out, list):
        return 0.0
    return _directional_confidence_score(out)


def _ensemble_weights(has_tone: bool) -> tuple[float, float, float]:
    w_v = SENTIMENT_ENSEMBLE_VADER
    w_p = SENTIMENT_ENSEMBLE_PROSUS
    w_t = SENTIMENT_ENSEMBLE_TONE if has_tone else 0.0
    if has_tone and (w_p + w_t) <= 0:
        return 1.0, 0.0, 0.0
    if not has_tone:
        # Prosus absorbs tone share
        w_p = w_p + w_t
        w_t = 0.0
    total = w_v + w_p + w_t
    if total <= 0:
        return 1.0, 0.0, 0.0
    return w_v / total, w_p / total, w_t / total


def analyze_sentiment_ensemble(text: str) -> SentimentResult:
    vader_c = _vader.polarity_scores(text)["compound"]
    fb = _get_finbert_pipeline()
    if fb is None:
        return SentimentResult(
            text=text[:200],
            compound_score=round(vader_c, 4),
            label=_label_from_compound(vader_c),
            model_used="vader",
        )

    prosus_score = _run_finbert_pipeline(fb, text)
    tone_pipe = _get_finbert_tone_pipeline()
    tone_score = _run_finbert_pipeline(tone_pipe, text) if tone_pipe else 0.0
    has_tone = tone_pipe is not None

    w_v, w_p, w_t = _ensemble_weights(has_tone)
    compound = w_v * vader_c + w_p * prosus_score + w_t * tone_score
    compound = max(-1.0, min(1.0, compound))

    return SentimentResult(
        text=text[:200],
        compound_score=round(compound, 4),
        label=_label_from_compound(compound),
        model_used="ensemble",
    )


def analyze_sentiment_finbert(text: str) -> SentimentResult:
    """Single ProsusAI FinBERT score (positive − negative), for compatibility."""
    fb = _get_finbert_pipeline()
    if fb is None:
        return analyze_sentiment_vader(text)
    try:
        truncated = text[:512]
        results = fb(truncated)
        if isinstance(results, list) and isinstance(results[0], list):
            results = results[0]
        score_map: dict[str, float] = {}
        for r in results:
            lab = _canonical_sentiment_label(str(r["label"]))
            score_map[lab] = float(r["score"])
        positive = score_map.get("positive", 0.0)
        negative = score_map.get("negative", 0.0)
        compound = positive - negative
        compound = max(-1.0, min(1.0, compound))
        return SentimentResult(
            text=text[:200],
            compound_score=round(compound, 4),
            label=_label_from_compound(compound),
            model_used="finbert",
        )
    except Exception:
        return analyze_sentiment_vader(text)


def analyze_news_sentiment(
    news_items: list[NewsItem],
    use_llm: bool = False,
) -> list[SentimentResult]:
    """Per-article sentiment with source × recency blend weights in aggregate."""
    if use_llm:
        from ai_sentiment import analyze_news_sentiment_llm
        return analyze_news_sentiment_llm(news_items)

    results: list[SentimentResult] = []
    for item in news_items:
        text = f"{item.title}. {item.summary}" if item.summary else item.title
        cred = source_credibility_multiplier(item)
        rw = recency_weight(item.published_at)
        blend_weight = round(cred * rw, 4)

        r = analyze_sentiment_ensemble(text)
        r.blend_weight = blend_weight
        results.append(r)
    return results


def aggregate_sentiment(results: list[SentimentResult]) -> dict:
    """Weighted mean of scores; label mix uses the same per-article scores."""
    if not results:
        return {
            "avg_score": 0.0, "label": "Neutral",
            "bullish_pct": 0, "bearish_pct": 0, "neutral_pct": 0,
            "count": 0,
        }

    weights = [max(r.blend_weight, 1e-6) for r in results]
    w_sum = sum(weights)
    avg = sum(r.compound_score * w for r, w in zip(results, weights)) / w_sum

    bullish = sum(1 for r in results if r.label == "Bullish")
    bearish = sum(1 for r in results if r.label == "Bearish")
    neutral = sum(1 for r in results if r.label == "Neutral")
    total = len(results)

    return {
        "avg_score": round(avg, 4),
        "label": _label_from_compound(avg),
        "bullish_pct": round(bullish / total * 100, 1),
        "bearish_pct": round(bearish / total * 100, 1),
        "neutral_pct": round(neutral / total * 100, 1),
        "count": total,
    }
