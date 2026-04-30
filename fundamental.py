"""
Fundamental-style scoring for Indian stocks using OpenAlgo quotes + daily history.
(OpenAlgo does not expose full financial statements; we score from price, range, momentum, volume.)
"""

import pandas as pd
from dataclasses import dataclass
from typing import Any, Optional

from openalgo_data import fetch_daily_history, fetch_quote


@dataclass
class FundamentalData:
    symbol: str
    company_name: str
    sector: str
    market_cap: Optional[float]
    current_price: Optional[float]
    pe_ratio: Optional[float]
    forward_pe: Optional[float]
    pb_ratio: Optional[float]
    eps: Optional[float]
    roe: Optional[float]
    debt_to_equity: Optional[float]
    dividend_yield: Optional[float]
    revenue_growth: Optional[float]
    profit_margin: Optional[float]
    operating_margin: Optional[float]
    free_cashflow: Optional[float]
    book_value: Optional[float]
    fifty_two_week_high: Optional[float]
    fifty_two_week_low: Optional[float]
    beta: Optional[float]
    score: float = 0.0
    rating: str = "Neutral"


def _rating_from_score(score: float) -> str:
    if score >= 75:
        return "Strong Buy"
    if score >= 60:
        return "Buy"
    if score >= 40:
        return "Neutral"
    if score >= 25:
        return "Sell"
    return "Strong Sell"


def _compute_fundamental_score(data: FundamentalData) -> tuple[float, str]:
    """
    Score 0-100 from classic fundamentals when present.
    With OpenAlgo-only data most fields are None; 52-week logic still applies.
    """
    score = 50.0

    if data.pe_ratio is not None:
        if data.pe_ratio < 0:
            score -= 10
        elif data.pe_ratio < 15:
            score += 12
        elif data.pe_ratio < 25:
            score += 5
        elif data.pe_ratio < 40:
            score -= 3
        else:
            score -= 8

    if data.forward_pe and data.pe_ratio and data.pe_ratio > 0:
        if data.forward_pe < data.pe_ratio * 0.85:
            score += 6
        elif data.forward_pe < data.pe_ratio:
            score += 3

    if data.pb_ratio is not None:
        if data.pb_ratio < 1:
            score += 8
        elif data.pb_ratio < 3:
            score += 4
        elif data.pb_ratio > 8:
            score -= 5

    if data.roe is not None:
        roe_pct = data.roe * 100 if data.roe < 1 else data.roe
        if roe_pct > 20:
            score += 10
        elif roe_pct > 15:
            score += 6
        elif roe_pct > 10:
            score += 3
        elif roe_pct < 5:
            score -= 5

    if data.debt_to_equity is not None:
        if data.debt_to_equity < 30:
            score += 8
        elif data.debt_to_equity < 80:
            score += 3
        elif data.debt_to_equity > 150:
            score -= 8
        elif data.debt_to_equity > 100:
            score -= 4

    if data.revenue_growth is not None:
        growth_pct = data.revenue_growth * 100
        if growth_pct > 20:
            score += 10
        elif growth_pct > 10:
            score += 6
        elif growth_pct > 0:
            score += 2
        else:
            score -= 5

    if data.profit_margin is not None:
        margin_pct = data.profit_margin * 100
        if margin_pct > 20:
            score += 8
        elif margin_pct > 10:
            score += 4
        elif margin_pct < 0:
            score -= 8

    if data.dividend_yield is not None:
        dy_pct = data.dividend_yield * 100
        if dy_pct > 3:
            score += 5
        elif dy_pct > 1:
            score += 2

    if (data.current_price and data.fifty_two_week_high
            and data.fifty_two_week_low and data.fifty_two_week_high > data.fifty_two_week_low):
        range_pct = ((data.current_price - data.fifty_two_week_low)
                     / (data.fifty_two_week_high - data.fifty_two_week_low))
        if range_pct < 0.3:
            score += 4
        elif range_pct > 0.9:
            score -= 3

    score = max(0, min(100, score))
    return round(score, 1), _rating_from_score(score)


def _adjust_score_openalgo_context(
    score: float,
    hist: pd.DataFrame,
    quote: Optional[dict[str, Any]],
) -> float:
    """Boost/penalize using momentum and liquidity when fundamentals are sparse."""
    close = hist["Close"].astype(float)
    if len(close) >= 120:
        cur, past = float(close.iloc[-1]), float(close.iloc[-120])
        if past > 0:
            ret = (cur / past - 1) * 100
            if ret > 20:
                score += 10
            elif ret > 8:
                score += 5
            elif ret < -15:
                score -= 8
            elif ret < -8:
                score -= 4

    if quote and len(hist) >= 20 and "Volume" in hist.columns:
        v = quote.get("volume")
        if v is not None:
            try:
                v = float(v)
                avg = float(hist["Volume"].tail(20).mean())
                if avg > 0 and v > avg * 1.6:
                    score += 4
                elif avg > 0 and v < avg * 0.4:
                    score -= 2
            except (TypeError, ValueError):
                pass

    return max(0, min(100, score))


def fetch_fundamentals(symbol: str) -> Optional[FundamentalData]:
    """Build fundamental-style profile from OpenAlgo daily bars + quote."""
    hist = fetch_daily_history(symbol, days=420)
    if hist is None or len(hist) < 20:
        return None

    quote = fetch_quote(symbol)
    ltp = None
    if quote:
        for key in ("ltp", "last_price", "last"):
            if key in quote and quote[key] is not None:
                try:
                    ltp = float(quote[key])
                    break
                except (TypeError, ValueError):
                    pass

    try:
        last_close = float(hist["Close"].iloc[-1])
    except (TypeError, ValueError):
        return None

    current_price = ltp if ltp is not None else last_close

    hi = float(hist["High"].max())
    lo = float(hist["Low"].min())

    data = FundamentalData(
        symbol=symbol,
        company_name=symbol,
        sector="NSE Equity",
        market_cap=None,
        current_price=current_price,
        pe_ratio=None,
        forward_pe=None,
        pb_ratio=None,
        eps=None,
        roe=None,
        debt_to_equity=None,
        dividend_yield=None,
        revenue_growth=None,
        profit_margin=None,
        operating_margin=None,
        free_cashflow=None,
        book_value=None,
        fifty_two_week_high=hi,
        fifty_two_week_low=lo,
        beta=None,
    )
    base_score, _ = _compute_fundamental_score(data)
    adj = _adjust_score_openalgo_context(base_score, hist, quote)
    data.score = round(adj, 1)
    data.rating = _rating_from_score(data.score)
    return data
