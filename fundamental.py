"""
Fundamental analysis of Indian stocks using yfinance.
Evaluates key financial health metrics and assigns a score.
"""

import yfinance as yf
import pandas as pd
from dataclasses import dataclass
from typing import Optional

from config import yf_ticker


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
    roe: Optional[float]           # Return on Equity (%)
    debt_to_equity: Optional[float]
    dividend_yield: Optional[float]
    revenue_growth: Optional[float] # YoY %
    profit_margin: Optional[float]
    operating_margin: Optional[float]
    free_cashflow: Optional[float]
    book_value: Optional[float]
    fifty_two_week_high: Optional[float]
    fifty_two_week_low: Optional[float]
    beta: Optional[float]
    score: float = 0.0             # 0-100, computed
    rating: str = "Neutral"        # Strong Buy | Buy | Neutral | Sell | Strong Sell


def _safe_get(info: dict, key: str, default=None):
    val = info.get(key, default)
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    return val


def fetch_fundamentals(symbol: str) -> Optional[FundamentalData]:
    """Fetch fundamental data for a single stock."""
    try:
        ticker = yf.Ticker(yf_ticker(symbol))
        info = ticker.info

        if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
            return None

        data = FundamentalData(
            symbol=symbol,
            company_name=_safe_get(info, "longName", symbol),
            sector=_safe_get(info, "sector", "Unknown"),
            market_cap=_safe_get(info, "marketCap"),
            current_price=_safe_get(info, "currentPrice",
                                    _safe_get(info, "regularMarketPrice")),
            pe_ratio=_safe_get(info, "trailingPE"),
            forward_pe=_safe_get(info, "forwardPE"),
            pb_ratio=_safe_get(info, "priceToBook"),
            eps=_safe_get(info, "trailingEps"),
            roe=_safe_get(info, "returnOnEquity"),
            debt_to_equity=_safe_get(info, "debtToEquity"),
            dividend_yield=_safe_get(info, "dividendYield"),
            revenue_growth=_safe_get(info, "revenueGrowth"),
            profit_margin=_safe_get(info, "profitMargins"),
            operating_margin=_safe_get(info, "operatingMargins"),
            free_cashflow=_safe_get(info, "freeCashflow"),
            book_value=_safe_get(info, "bookValue"),
            fifty_two_week_high=_safe_get(info, "fiftyTwoWeekHigh"),
            fifty_two_week_low=_safe_get(info, "fiftyTwoWeekLow"),
            beta=_safe_get(info, "beta"),
        )
        data.score, data.rating = _compute_fundamental_score(data)
        return data
    except Exception as e:
        print(f"  [warn] Fundamental fetch failed for {symbol}: {e}")
        return None


def _compute_fundamental_score(data: FundamentalData) -> tuple[float, str]:
    """
    Score fundamentals 0-100 based on value, quality, and growth metrics.
    Higher = more attractive.
    """
    score = 50.0  # start neutral

    # ── Valuation (P/E) ──
    if data.pe_ratio is not None:
        if data.pe_ratio < 0:
            score -= 10      # negative earnings
        elif data.pe_ratio < 15:
            score += 12       # undervalued
        elif data.pe_ratio < 25:
            score += 5        # fair value
        elif data.pe_ratio < 40:
            score -= 3        # slightly expensive
        else:
            score -= 8        # overvalued

    # ── Forward P/E vs trailing P/E (earnings growth expected) ──
    if data.forward_pe and data.pe_ratio and data.pe_ratio > 0:
        if data.forward_pe < data.pe_ratio * 0.85:
            score += 6        # strong earnings growth expected
        elif data.forward_pe < data.pe_ratio:
            score += 3

    # ── Price to Book ──
    if data.pb_ratio is not None:
        if data.pb_ratio < 1:
            score += 8
        elif data.pb_ratio < 3:
            score += 4
        elif data.pb_ratio > 8:
            score -= 5

    # ── Return on Equity ──
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

    # ── Debt to Equity ──
    if data.debt_to_equity is not None:
        if data.debt_to_equity < 30:
            score += 8
        elif data.debt_to_equity < 80:
            score += 3
        elif data.debt_to_equity > 150:
            score -= 8
        elif data.debt_to_equity > 100:
            score -= 4

    # ── Revenue Growth ──
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

    # ── Profit Margin ──
    if data.profit_margin is not None:
        margin_pct = data.profit_margin * 100
        if margin_pct > 20:
            score += 8
        elif margin_pct > 10:
            score += 4
        elif margin_pct < 0:
            score -= 8

    # ── Dividend Yield ──
    if data.dividend_yield is not None:
        dy_pct = data.dividend_yield * 100
        if dy_pct > 3:
            score += 5
        elif dy_pct > 1:
            score += 2

    # ── 52-week position (contrarian value signal) ──
    if (data.current_price and data.fifty_two_week_high
            and data.fifty_two_week_low and data.fifty_two_week_high > data.fifty_two_week_low):
        range_pct = ((data.current_price - data.fifty_two_week_low)
                     / (data.fifty_two_week_high - data.fifty_two_week_low))
        if range_pct < 0.3:
            score += 4   # near 52-week low (potential value)
        elif range_pct > 0.9:
            score -= 3   # near 52-week high (less upside)

    score = max(0, min(100, score))

    if score >= 75:
        rating = "Strong Buy"
    elif score >= 60:
        rating = "Buy"
    elif score >= 40:
        rating = "Neutral"
    elif score >= 25:
        rating = "Sell"
    else:
        rating = "Strong Sell"

    return round(score, 1), rating
