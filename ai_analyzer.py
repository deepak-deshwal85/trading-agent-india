"""
AI-powered deep analysis using Anthropic Claude or OpenAI GPT.
Sends structured market data to the LLM and gets expert-level investment insights.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

import config
from config import ADX_GATE_THRESHOLD
from recommendation import Recommendation
from fundamental import FundamentalData
from technical import TechnicalData
from news_fetcher import NewsItem


@dataclass
class AIInsight:
    symbol: str
    market_outlook: str
    investment_thesis: str
    ai_recommendation: str        # STRONG BUY | BUY | HOLD | SELL | STRONG SELL
    target_price: Optional[str]
    stop_loss: Optional[str]
    time_horizon: str
    key_catalysts: list[str]
    key_risks: list[str]
    sector_view: str
    confidence_rationale: str
    provider: str                 # anthropic | openai


@dataclass
class MarketOverview:
    overall_outlook: str
    nifty_view: str
    global_impact: str
    sector_rotation: str
    top_picks: list[str]
    avoid_list: list[str]
    strategy_advice: str
    provider: str


def _build_stock_prompt(
    symbol: str,
    rec: Recommendation,
    fundamental: Optional[FundamentalData],
    technical: Optional[TechnicalData],
    news_items: list[NewsItem],
    market_sentiment: dict,
    world_sentiment: dict,
) -> str:
    news_text = ""
    for i, n in enumerate(news_items[:10], 1):
        news_text += f"  {i}. [{n.source}] {n.title}\n"
    if not news_text:
        news_text = "  No recent stock-specific news found.\n"

    fund_text = "  Not available\n"
    if fundamental:
        parts = [
            f"  Company: {fundamental.company_name}",
            f"  Sector: {fundamental.sector}",
        ]
        if fundamental.market_cap:
            parts.append(f"  Market Cap: {fundamental.market_cap:,.0f}")
        if fundamental.current_price:
            parts.append(f"  Current Price: ₹{fundamental.current_price:,.2f}")
        parts.extend([
            f"  P/E Ratio: {fundamental.pe_ratio}",
            f"  Forward P/E: {fundamental.forward_pe}",
            f"  P/B Ratio: {fundamental.pb_ratio}",
            f"  EPS: {fundamental.eps}",
            f"  ROE: {fundamental.roe}",
            f"  Debt/Equity: {fundamental.debt_to_equity}",
            f"  Revenue Growth: {fundamental.revenue_growth}",
            f"  Profit Margin: {fundamental.profit_margin}",
            f"  Dividend Yield: {fundamental.dividend_yield}",
            f"  52W High: {fundamental.fifty_two_week_high}",
            f"  52W Low: {fundamental.fifty_two_week_low}",
            f"  Beta: {fundamental.beta}",
            f"  Fundamental Score: {fundamental.score}/100 ({fundamental.rating})",
        ])
        fund_text = "\n".join(parts) + "\n"

    tech_text = "  Not available\n"
    if technical:
        tech_text = (
            f"  Current Price: ₹{technical.current_price:,.2f}\n"
            f"  SMA20: {technical.sma_20} (Price {technical.price_vs_sma20})\n"
            f"  SMA50: {technical.sma_50} (Price {technical.price_vs_sma50})\n"
            f"  EMA9: {technical.ema_9} | EMA21: {technical.ema_21}\n"
            f"  Golden Cross: {technical.golden_cross} | Death Cross: {technical.death_cross}\n"
            f"  RSI: {technical.rsi} ({technical.rsi_signal})\n"
            f"  Stochastic: K={technical.stoch_k} D={technical.stoch_d} ({technical.stoch_signal})\n"
            f"  MACD: {technical.macd_value} | Signal: {technical.macd_signal_line} ({technical.macd_signal_type})\n"
            f"  MACD Histogram: {technical.macd_histogram}\n"
            f"  Bollinger: Lower={technical.bb_lower} Mid={technical.bb_middle} Upper={technical.bb_upper} ({technical.bb_signal})\n"
            f"  ATR(14): {technical.atr_14}\n"
            f"  Supertrend: {technical.supertrend} ({technical.supertrend_direction})\n"
            f"  Volume: Latest={technical.latest_volume} Avg20d={technical.avg_volume_20d} ({technical.volume_signal})\n"
            f"  OBV: {technical.obv} ({technical.obv_signal})\n"
            f"  ADX: {technical.adx} ({technical.trend_strength}) | Oscillator gate: "
            f"{'ADX>' + str(ADX_GATE_THRESHOLD) + ' (momentum trusted)' if technical.adx_momentum_gate else 'ADX≤' + str(ADX_GATE_THRESHOLD) + ' (momentum damped in score)'}\n"
            f"  Technical Score: {technical.score}/100 ({technical.rating})\n"
            f"  Signals: {technical.signals_summary}\n"
        )

    return f"""You are a senior SEBI-registered equity research analyst specializing in Indian markets (NSE/BSE). Analyze the following data for {symbol} and provide an expert investment recommendation.

## RECENT NEWS FOR {symbol}:
{news_text}

## FUNDAMENTAL DATA:
{fund_text}

## TECHNICAL DATA:
{tech_text}

## MARKET SENTIMENT:
  Indian Market Sentiment: {market_sentiment.get('label', 'N/A')} (Score: {market_sentiment.get('avg_score', 0):.3f}, Bullish: {market_sentiment.get('bullish_pct', 0):.0f}%, Bearish: {market_sentiment.get('bearish_pct', 0):.0f}%)
  World News Sentiment: {world_sentiment.get('label', 'N/A')} (Score: {world_sentiment.get('avg_score', 0):.3f})

## OUR ALGORITHMIC SCORES:
  Sentiment Score: {rec.sentiment_score}/100
  Fundamental Score: {rec.fundamental_score}/100
  Technical Score: {rec.technical_score}/100
  Composite Score: {rec.composite_score}/100
  Algo Recommendation: {rec.recommendation} (Confidence: {rec.confidence})

Based on ALL the above data, provide your expert analysis. Respond ONLY with valid JSON in this exact format:
{{
  "investment_thesis": "2-4 sentence thesis explaining why to buy/sell/hold this stock right now",
  "ai_recommendation": "STRONG BUY | BUY | HOLD | SELL | STRONG SELL",
  "target_price": "target price in INR or null if uncertain",
  "stop_loss": "stop loss price in INR or null",
  "time_horizon": "Short Term (1-3 months) | Medium Term (3-12 months) | Long Term (1+ year)",
  "key_catalysts": ["catalyst 1", "catalyst 2", "catalyst 3"],
  "key_risks": ["risk 1", "risk 2", "risk 3"],
  "sector_view": "1 sentence on sector outlook",
  "confidence_rationale": "1-2 sentences on why you are or aren't confident in this call"
}}"""


def _build_market_overview_prompt(
    recommendations: list[Recommendation],
    market_sentiment: dict,
    world_sentiment: dict,
    market_headlines: list[str],
    world_headlines: list[str],
) -> str:
    import math
    rec_summary = ""
    sorted_recs = sorted(recommendations, key=lambda r: r.composite_score, reverse=True)
    for r in sorted_recs:
        price = r.current_price
        price_str = f"₹{price:,.2f}" if price and not math.isnan(price) else "N/A"
        rec_summary += f"  {r.symbol}: Score={r.composite_score:.0f} Rec={r.recommendation} Price={price_str} Sector={r.sector}\n"

    mkt_news = "\n".join(f"  - {h}" for h in market_headlines[:12])
    wld_news = "\n".join(f"  - {h}" for h in world_headlines[:8])

    return f"""You are India's top market strategist (like those at ICICI Securities, Motilal Oswal, HDFC Securities). Provide a comprehensive market overview based on today's data.

## MARKET SENTIMENT:
  Indian Market: {market_sentiment.get('label', 'N/A')} (Avg Score: {market_sentiment.get('avg_score', 0):.3f}, {market_sentiment.get('bullish_pct', 0):.0f}% Bullish, {market_sentiment.get('bearish_pct', 0):.0f}% Bearish)
  World: {world_sentiment.get('label', 'N/A')} (Avg Score: {world_sentiment.get('avg_score', 0):.3f})

## KEY INDIAN MARKET HEADLINES:
{mkt_news}

## KEY WORLD HEADLINES:
{wld_news}

## ALL STOCK SCORES (sorted best to worst):
{rec_summary}

Based on ALL this data, provide your expert market overview. Respond ONLY with valid JSON:
{{
  "overall_outlook": "1-2 sentence overall market outlook for Indian equities",
  "nifty_view": "1-2 sentence view on Nifty 50 direction with key levels",
  "global_impact": "1-2 sentences on how global factors are affecting Indian markets",
  "sector_rotation": "Which sectors to overweight/underweight and why (2-3 sentences)",
  "top_picks": ["symbol1", "symbol2", "symbol3", "symbol4", "symbol5"],
  "avoid_list": ["symbol1", "symbol2", "symbol3"],
  "strategy_advice": "2-3 sentence actionable strategy for retail investors today"
}}"""


def _call_anthropic(prompt: str, *, model: str, max_tokens: int = 2000) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _call_openai(prompt: str, *, model: str, max_tokens: int = 2000, temperature: float = 0.3) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a senior Indian equity research analyst. Always respond with valid JSON only, no markdown fences."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content


def call_llm(
    prompt: str,
    *,
    tier: str = "deep",
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> tuple[str, str, str]:
    """Call CLI provider. Returns (response_text, provider, model_id). tier: fast | deep."""
    primary = config.AI_PROVIDER.lower().strip()
    if primary not in ("openai", "anthropic"):
        raise RuntimeError(
            "AI provider not set. Run with --ai --provider anthropic or --ai --provider openai."
        )
    model = config.resolve_ai_model(tier)

    try:
        if primary == "openai":
            if not config.OPENAI_API_KEY:
                raise RuntimeError("OPENAI_API_KEY is not set in .env")
            text = _call_openai(
                prompt, model=model, max_tokens=max_tokens, temperature=temperature,
            )
            return text, "openai", model
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in .env")
        text = _call_anthropic(prompt, model=model, max_tokens=max_tokens)
        return text, "anthropic", model
    except Exception as e:
        raise RuntimeError(f"{primary} API call failed ({model}): {e}") from e


def _call_llm(prompt: str) -> tuple[str, str]:
    """Deep analysis (Sonnet / gpt-4o). Returns (response_text, provider_used)."""
    text, provider, _model = call_llm(prompt, tier="deep")
    return text, provider


def _parse_json(raw: str):
    """Extract JSON object or array from LLM response, handling markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for opener, closer in (("{", "}"), ("[", "]")):
            start = text.find(opener)
            end = text.rfind(closer) + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        raise


def analyze_stock_with_ai(
    symbol: str,
    rec: Recommendation,
    fundamental: Optional[FundamentalData],
    technical: Optional[TechnicalData],
    news_items: list[NewsItem],
    market_sentiment: dict,
    world_sentiment: dict,
) -> tuple[Optional[AIInsight], Optional[str]]:
    """Returns (AIInsight, None) on success, or (None, human-readable error)."""
    api_key = (
        config.OPENAI_API_KEY
        if config.AI_PROVIDER == "openai"
        else config.ANTHROPIC_API_KEY
    )
    if not api_key:
        return None, f"{symbol}: No API key for {config.AI_PROVIDER}"

    try:
        prompt = _build_stock_prompt(
            symbol, rec, fundamental, technical,
            news_items, market_sentiment, world_sentiment,
        )
        raw, provider_used = _call_llm(prompt)
        data = _parse_json(raw)

        return AIInsight(
            symbol=symbol,
            market_outlook="",
            investment_thesis=data.get("investment_thesis", ""),
            ai_recommendation=data.get("ai_recommendation", rec.recommendation),
            target_price=data.get("target_price"),
            stop_loss=data.get("stop_loss"),
            time_horizon=data.get("time_horizon", "Medium Term"),
            key_catalysts=data.get("key_catalysts", []),
            key_risks=data.get("key_risks", []),
            sector_view=data.get("sector_view", ""),
            confidence_rationale=data.get("confidence_rationale", ""),
            provider=provider_used,
        ), None
    except Exception as e:
        logging.getLogger("ai_analyzer").warning("AI stock analysis failed (%s): %s", symbol, e)
        return None, f"{symbol}: {e}"


def generate_market_overview(
    recommendations: list[Recommendation],
    market_sentiment: dict,
    world_sentiment: dict,
    market_news: list[NewsItem],
    world_news: list[NewsItem],
) -> tuple[Optional[MarketOverview], Optional[str]]:
    """Returns (overview, None) or (None, error message)."""
    api_key = (
        config.OPENAI_API_KEY
        if config.AI_PROVIDER == "openai"
        else config.ANTHROPIC_API_KEY
    )
    if not api_key:
        return None, f"No API key for {config.AI_PROVIDER}"

    try:
        market_headlines = [n.title for n in market_news[:15]]
        world_headlines = [n.title for n in world_news[:10]]

        prompt = _build_market_overview_prompt(
            recommendations, market_sentiment, world_sentiment,
            market_headlines, world_headlines,
        )
        raw, provider_used = _call_llm(prompt)
        data = _parse_json(raw)

        return MarketOverview(
            overall_outlook=data.get("overall_outlook", ""),
            nifty_view=data.get("nifty_view", ""),
            global_impact=data.get("global_impact", ""),
            sector_rotation=data.get("sector_rotation", ""),
            top_picks=data.get("top_picks", []),
            avoid_list=data.get("avoid_list", []),
            strategy_advice=data.get("strategy_advice", ""),
            provider=provider_used,
        ), None
    except Exception as e:
        logging.getLogger("ai_analyzer").warning("AI market overview failed: %s", e)
        return None, str(e)
