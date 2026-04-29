"""
Recommendation engine that combines sentiment, fundamental, and technical analysis
to produce Buy / Sell / Hold recommendations with confidence scores.
"""

from dataclasses import dataclass
from typing import Optional

from config import WEIGHT_SENTIMENT, WEIGHT_FUNDAMENTAL, WEIGHT_TECHNICAL
from sentiment import SentimentResult
from fundamental import FundamentalData
from technical import TechnicalData


@dataclass
class Recommendation:
    symbol: str
    company_name: str
    sector: str
    current_price: Optional[float]

    # Individual scores (0-100)
    sentiment_score: float
    fundamental_score: float
    technical_score: float

    # Individual ratings
    sentiment_label: str
    fundamental_rating: str
    technical_rating: str

    # Combined
    composite_score: float       # 0-100
    recommendation: str          # STRONG BUY | BUY | HOLD | SELL | STRONG SELL
    confidence: str              # High | Medium | Low
    risk_level: str              # Low | Moderate | High | Very High

    # Key reasons
    bull_case: list[str]
    bear_case: list[str]
    key_levels: dict              # support, resistance

    # AI enrichment (populated later if --ai is used)
    ai_recommendation: Optional[str] = None
    ai_thesis: Optional[str] = None
    ai_target_price: Optional[str] = None
    ai_stop_loss: Optional[str] = None


def _sentiment_to_score(sentiment_agg: dict) -> float:
    """Convert aggregate sentiment (-1 to +1) to 0-100 scale."""
    raw = sentiment_agg.get("avg_score", 0.0)
    return max(0, min(100, (raw + 1) * 50))


def generate_recommendation(
    symbol: str,
    sentiment_agg: dict,
    fundamental: Optional[FundamentalData],
    technical: Optional[TechnicalData],
) -> Recommendation:
    """Combine all analyses into a single recommendation."""

    # ── Scores ──
    sent_score = _sentiment_to_score(sentiment_agg)
    fund_score = fundamental.score if fundamental else 50.0
    tech_score = technical.score if technical else 50.0

    composite = (
        WEIGHT_SENTIMENT * sent_score
        + WEIGHT_FUNDAMENTAL * fund_score
        + WEIGHT_TECHNICAL * tech_score
    )

    # ── Recommendation ──
    if composite >= 75:
        recommendation = "STRONG BUY"
    elif composite >= 62:
        recommendation = "BUY"
    elif composite >= 38:
        recommendation = "HOLD"
    elif composite >= 25:
        recommendation = "SELL"
    else:
        recommendation = "STRONG SELL"

    # ── Confidence ──
    scores = [sent_score, fund_score, tech_score]
    spread = max(scores) - min(scores)
    agreement = sum(1 for s in scores if abs(s - composite) < 15)

    if agreement >= 3 and spread < 20:
        confidence = "High"
    elif agreement >= 2:
        confidence = "Medium"
    else:
        confidence = "Low"

    # ── Risk Assessment ──
    risk_factors = 0
    if fundamental:
        if fundamental.debt_to_equity and fundamental.debt_to_equity > 100:
            risk_factors += 1
        if fundamental.pe_ratio and (fundamental.pe_ratio > 50 or fundamental.pe_ratio < 0):
            risk_factors += 1
        if fundamental.beta and fundamental.beta > 1.5:
            risk_factors += 1
    if technical:
        if technical.rsi and (technical.rsi > 75 or technical.rsi < 25):
            risk_factors += 1
        if technical.adx and technical.adx > 30:
            risk_factors += 1
        if technical.volume_signal == "High":
            risk_factors += 1

    if risk_factors >= 4:
        risk_level = "Very High"
    elif risk_factors >= 3:
        risk_level = "High"
    elif risk_factors >= 1:
        risk_level = "Moderate"
    else:
        risk_level = "Low"

    # ── Bull / Bear Cases ──
    bull_case = []
    bear_case = []

    if sentiment_agg.get("label") == "Bullish":
        bull_case.append(f"Positive news sentiment ({sentiment_agg.get('bullish_pct', 0)}% bullish)")
    elif sentiment_agg.get("label") == "Bearish":
        bear_case.append(f"Negative news sentiment ({sentiment_agg.get('bearish_pct', 0)}% bearish)")

    if fundamental:
        if fundamental.pe_ratio and 0 < fundamental.pe_ratio < 20:
            bull_case.append(f"Attractive valuation (P/E: {fundamental.pe_ratio:.1f})")
        elif fundamental.pe_ratio and fundamental.pe_ratio > 40:
            bear_case.append(f"Expensive valuation (P/E: {fundamental.pe_ratio:.1f})")

        if fundamental.roe and fundamental.roe > 0.15:
            roe_pct = fundamental.roe * 100 if fundamental.roe < 1 else fundamental.roe
            bull_case.append(f"High ROE ({roe_pct:.1f}%)")

        if fundamental.revenue_growth and fundamental.revenue_growth > 0.10:
            bull_case.append(f"Strong revenue growth ({fundamental.revenue_growth*100:.1f}%)")
        elif fundamental.revenue_growth and fundamental.revenue_growth < 0:
            bear_case.append(f"Revenue declining ({fundamental.revenue_growth*100:.1f}%)")

        if fundamental.debt_to_equity and fundamental.debt_to_equity > 100:
            bear_case.append(f"High debt (D/E: {fundamental.debt_to_equity:.0f})")
        elif fundamental.debt_to_equity and fundamental.debt_to_equity < 30:
            bull_case.append(f"Low debt (D/E: {fundamental.debt_to_equity:.0f})")

        if fundamental.dividend_yield and fundamental.dividend_yield > 0.02:
            bull_case.append(f"Good dividend yield ({fundamental.dividend_yield*100:.1f}%)")

    if technical:
        if technical.golden_cross:
            bull_case.append("Golden Cross (SMA20 > SMA50)")
        elif technical.death_cross:
            bear_case.append("Death Cross (SMA20 < SMA50)")

        if technical.rsi_signal == "Oversold":
            bull_case.append(f"RSI oversold ({technical.rsi}) - potential bounce")
        elif technical.rsi_signal == "Overbought":
            bear_case.append(f"RSI overbought ({technical.rsi}) - potential pullback")

        if technical.macd_signal_type == "Bullish":
            bull_case.append("MACD bullish crossover")
        elif technical.macd_signal_type == "Bearish":
            bear_case.append("MACD bearish crossover")

        if technical.bb_signal == "Oversold":
            bull_case.append("Below Bollinger lower band (oversold)")
        elif technical.bb_signal == "Overbought":
            bear_case.append("Above Bollinger upper band (overbought)")

    # ── Key Levels ──
    key_levels = {}
    if technical:
        if technical.sma_50:
            key_levels["SMA50 Support/Resistance"] = technical.sma_50
        if technical.bb_lower:
            key_levels["Bollinger Lower (Support)"] = technical.bb_lower
        if technical.bb_upper:
            key_levels["Bollinger Upper (Resistance)"] = technical.bb_upper
    if fundamental:
        if fundamental.fifty_two_week_low:
            key_levels["52-Week Low"] = fundamental.fifty_two_week_low
        if fundamental.fifty_two_week_high:
            key_levels["52-Week High"] = fundamental.fifty_two_week_high

    return Recommendation(
        symbol=symbol,
        company_name=fundamental.company_name if fundamental else symbol,
        sector=fundamental.sector if fundamental else "Unknown",
        current_price=technical.current_price if technical else (
            fundamental.current_price if fundamental else None
        ),
        sentiment_score=round(sent_score, 1),
        fundamental_score=round(fund_score, 1),
        technical_score=round(tech_score, 1),
        sentiment_label=sentiment_agg.get("label", "Neutral"),
        fundamental_rating=fundamental.rating if fundamental else "N/A",
        technical_rating=technical.rating if technical else "N/A",
        composite_score=round(composite, 1),
        recommendation=recommendation,
        confidence=confidence,
        risk_level=risk_level,
        bull_case=bull_case,
        bear_case=bear_case,
        key_levels=key_levels,
    )
