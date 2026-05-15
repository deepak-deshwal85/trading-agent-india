"""
LLM-based news sentiment (fast tier: Haiku / gpt-4o-mini).
Batches headlines to limit API calls. Used when --ai and AI_SENTIMENT_USE_LLM=true.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import config
from ai_analyzer import _parse_json, call_llm
from news_fetcher import NewsItem
from sentiment import (
    SentimentResult,
    _label_from_compound,
    recency_weight,
    source_credibility_multiplier,
)

logger = logging.getLogger("ai_sentiment")


def _headline_text(item: NewsItem) -> str:
    if item.summary:
        return f"{item.title}. {item.summary}"[:400]
    return item.title[:400]


def _classify_batch(batch: list[tuple[int, str]]) -> dict[int, float]:
    """batch: [(index, headline), ...] -> index -> compound score -1..1"""
    if not batch:
        return {}

    lines = "\n".join(f'{i}. "{text}"' for i, text in batch)
    prompt = f"""Classify Indian/global financial news headlines for market sentiment.
For each numbered headline return compound score from -1.0 (very bearish) to +1.0 (very bullish).

Headlines:
{lines}

Respond ONLY with JSON array, one object per headline, same order:
[{{"id": 1, "score": 0.25}}, ...]
Use the headline number as id."""

    raw, _provider, model = call_llm(
        prompt,
        tier="fast",
        max_tokens=config.AI_SENTIMENT_MAX_TOKENS,
        temperature=0.0,
    )
    data = _parse_json(raw)
    if isinstance(data, dict) and "results" in data:
        data = data["results"]
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array from {model}")

    scores: dict[int, float] = {}
    for row in data:
        if not isinstance(row, dict):
            continue
        idx = row.get("id")
        score = row.get("score")
        if idx is None or score is None:
            continue
        try:
            idx_i = int(idx)
            s = float(score)
            scores[idx_i] = max(-1.0, min(1.0, s))
        except (TypeError, ValueError):
            continue
    return scores


def analyze_news_sentiment_llm(news_items: list[NewsItem]) -> list[SentimentResult]:
    """Per-article sentiment via fast LLM; blend weights match VADER path."""
    if not news_items:
        return []

    model_id = config.resolve_ai_model("fast")
    provider = config.AI_PROVIDER
    model_used = f"llm-{provider}-{model_id}"

    indexed: list[tuple[int, str, NewsItem]] = []
    for i, item in enumerate(news_items, start=1):
        indexed.append((i, _headline_text(item), item))

    scores_by_id: dict[int, float] = {}
    batch_size = max(1, config.AI_SENTIMENT_BATCH_SIZE)

    for start in range(0, len(indexed), batch_size):
        chunk = indexed[start : start + batch_size]
        batch = [(i, text) for i, text, _ in chunk]
        try:
            scores_by_id.update(_classify_batch(batch))
        except Exception as e:
            logger.warning("LLM sentiment batch failed, using 0.0 for chunk: %s", e)

    results: list[SentimentResult] = []
    for idx, _text, item in indexed:
        compound = scores_by_id.get(idx, 0.0)
        cred = source_credibility_multiplier(item)
        rw = recency_weight(item.published_at)
        results.append(
            SentimentResult(
                text=item.title[:200],
                compound_score=round(compound, 4),
                label=_label_from_compound(compound),
                model_used=model_used,
                blend_weight=round(cred * rw, 4),
            )
        )
    return results
