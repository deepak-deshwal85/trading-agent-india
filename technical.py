"""
Technical analysis using pandas_ta for Indian stocks.
Computes RSI, MACD, Moving Averages, Bollinger Bands, Volume analysis.
"""

import math
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from dataclasses import dataclass
from typing import Optional

from config import (
    yf_ticker, TECHNICAL_PERIOD_DAYS,
    SMA_SHORT, SMA_LONG, EMA_SHORT, EMA_LONG,
    RSI_PERIOD, BOLLINGER_PERIOD, BOLLINGER_STD,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL,
)


@dataclass
class TechnicalData:
    symbol: str
    current_price: float

    # Moving Averages
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    price_vs_sma20: Optional[str] = None   # Above | Below
    price_vs_sma50: Optional[str] = None
    golden_cross: Optional[bool] = None     # SMA20 > SMA50
    death_cross: Optional[bool] = None      # SMA20 < SMA50

    # RSI
    rsi: Optional[float] = None
    rsi_signal: Optional[str] = None        # Overbought | Oversold | Neutral

    # MACD
    macd_value: Optional[float] = None
    macd_signal_line: Optional[float] = None
    macd_histogram: Optional[float] = None
    macd_signal_type: Optional[str] = None  # Bullish | Bearish

    # Bollinger Bands
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_signal: Optional[str] = None         # Overbought | Oversold | Neutral

    # Volume
    avg_volume_20d: Optional[float] = None
    latest_volume: Optional[float] = None
    volume_signal: Optional[str] = None     # High | Normal | Low

    # ADX (trend strength)
    adx: Optional[float] = None
    trend_strength: Optional[str] = None    # Strong | Moderate | Weak

    # Overall
    score: float = 0.0      # 0-100
    rating: str = "Neutral"  # Strong Buy | Buy | Neutral | Sell | Strong Sell
    signals_summary: str = ""


def _safe_float(val) -> Optional[float]:
    """Convert to float, returning None for NaN/Inf."""
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 2)
    except (TypeError, ValueError):
        return None


def fetch_technical(symbol: str) -> Optional[TechnicalData]:
    """Compute technical indicators for a stock."""
    try:
        ticker = yf.Ticker(yf_ticker(symbol))
        df = ticker.history(period="1y")

        if df.empty or len(df) < 50:
            return None

        df = df.dropna(subset=["Close"])
        if df.empty:
            return None

        close = df["Close"]
        volume = df["Volume"]
        current_price = _safe_float(close.iloc[-1])
        if current_price is None:
            return None

        data = TechnicalData(symbol=symbol, current_price=current_price)

        # ── Moving Averages ──
        sma20 = ta.sma(close, length=SMA_SHORT)
        sma50 = ta.sma(close, length=SMA_LONG)
        ema12 = ta.ema(close, length=EMA_SHORT)
        ema26 = ta.ema(close, length=EMA_LONG)

        if sma20 is not None and not sma20.empty:
            data.sma_20 = _safe_float(sma20.iloc[-1])
            if data.sma_20:
                data.price_vs_sma20 = "Above" if current_price > data.sma_20 else "Below"
        if sma50 is not None and not sma50.empty:
            data.sma_50 = _safe_float(sma50.iloc[-1])
            if data.sma_50:
                data.price_vs_sma50 = "Above" if current_price > data.sma_50 else "Below"
        if ema12 is not None and not ema12.empty:
            data.ema_12 = _safe_float(ema12.iloc[-1])
        if ema26 is not None and not ema26.empty:
            data.ema_26 = _safe_float(ema26.iloc[-1])

        if data.sma_20 and data.sma_50:
            data.golden_cross = data.sma_20 > data.sma_50
            data.death_cross = data.sma_20 < data.sma_50

        # ── RSI ──
        rsi = ta.rsi(close, length=RSI_PERIOD)
        if rsi is not None and not rsi.empty:
            data.rsi = _safe_float(rsi.iloc[-1])
            if data.rsi is not None and data.rsi > 70:
                data.rsi_signal = "Overbought"
            elif data.rsi < 30:
                data.rsi_signal = "Oversold"
            else:
                data.rsi_signal = "Neutral"

        # ── MACD ──
        macd_df = ta.macd(close, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
        if macd_df is not None and not macd_df.empty:
            data.macd_value = _safe_float(macd_df.iloc[-1, 0])
            data.macd_histogram = _safe_float(macd_df.iloc[-1, 1])
            data.macd_signal_line = _safe_float(macd_df.iloc[-1, 2])
            if data.macd_value is not None and data.macd_signal_line is not None:
                data.macd_signal_type = "Bullish" if data.macd_value > data.macd_signal_line else "Bearish"

        # ── Bollinger Bands ──
        bb = ta.bbands(close, length=BOLLINGER_PERIOD, std=BOLLINGER_STD)
        if bb is not None and not bb.empty:
            data.bb_lower = _safe_float(bb.iloc[-1, 0])
            data.bb_middle = _safe_float(bb.iloc[-1, 1])
            data.bb_upper = _safe_float(bb.iloc[-1, 2])
            if data.bb_upper and current_price > data.bb_upper:
                data.bb_signal = "Overbought"
            elif data.bb_lower and current_price < data.bb_lower:
                data.bb_signal = "Oversold"
            else:
                data.bb_signal = "Neutral"

        # ── Volume Analysis ──
        if len(volume) >= 20:
            data.avg_volume_20d = float(volume.tail(20).mean())
            data.latest_volume = float(volume.iloc[-1])
            vol_ratio = data.latest_volume / data.avg_volume_20d if data.avg_volume_20d > 0 else 1.0
            if vol_ratio > 1.5:
                data.volume_signal = "High"
            elif vol_ratio < 0.5:
                data.volume_signal = "Low"
            else:
                data.volume_signal = "Normal"

        # ── ADX (Average Directional Index) ──
        adx_df = ta.adx(df["High"], df["Low"], close, length=14)
        if adx_df is not None and not adx_df.empty:
            data.adx = _safe_float(adx_df.iloc[-1, 0])
            if data.adx > 25:
                data.trend_strength = "Strong"
            elif data.adx > 20:
                data.trend_strength = "Moderate"
            else:
                data.trend_strength = "Weak"

        data.score, data.rating, data.signals_summary = _compute_technical_score(data)
        return data

    except Exception as e:
        print(f"  [warn] Technical analysis failed for {symbol}: {e}")
        return None


def _compute_technical_score(data: TechnicalData) -> tuple[float, str, str]:
    """Score technical indicators 0-100. Higher = more bullish."""
    score = 50.0
    signals = []

    # ── Moving Average Signals ──
    if data.price_vs_sma20 == "Above":
        score += 5
        signals.append("Price > SMA20")
    elif data.price_vs_sma20 == "Below":
        score -= 5
        signals.append("Price < SMA20")

    if data.price_vs_sma50 == "Above":
        score += 5
        signals.append("Price > SMA50")
    elif data.price_vs_sma50 == "Below":
        score -= 5
        signals.append("Price < SMA50")

    if data.golden_cross:
        score += 8
        signals.append("Golden Cross (SMA20>SMA50)")
    elif data.death_cross:
        score -= 8
        signals.append("Death Cross (SMA20<SMA50)")

    # ── RSI ──
    if data.rsi is not None:
        if data.rsi < 30:
            score += 10
            signals.append(f"RSI Oversold ({data.rsi})")
        elif data.rsi < 40:
            score += 4
            signals.append(f"RSI Near Oversold ({data.rsi})")
        elif data.rsi > 70:
            score -= 10
            signals.append(f"RSI Overbought ({data.rsi})")
        elif data.rsi > 60:
            score -= 3
            signals.append(f"RSI Near Overbought ({data.rsi})")
        else:
            signals.append(f"RSI Neutral ({data.rsi})")

    # ── MACD ──
    if data.macd_signal_type == "Bullish":
        score += 8
        signals.append("MACD Bullish")
    elif data.macd_signal_type == "Bearish":
        score -= 8
        signals.append("MACD Bearish")

    if data.macd_histogram is not None and data.macd_histogram > 0:
        score += 3
    elif data.macd_histogram is not None and data.macd_histogram < 0:
        score -= 3

    # ── Bollinger Bands ──
    if data.bb_signal == "Oversold":
        score += 8
        signals.append("BB Oversold (below lower band)")
    elif data.bb_signal == "Overbought":
        score -= 8
        signals.append("BB Overbought (above upper band)")

    # ── Volume ──
    if data.volume_signal == "High":
        if score >= 50:
            score += 5
            signals.append("High Volume (confirms trend)")
        else:
            score -= 3
            signals.append("High Volume (selling pressure)")
    elif data.volume_signal == "Low":
        signals.append("Low Volume (weak conviction)")

    # ── ADX Trend Strength ──
    if data.trend_strength == "Strong":
        if score >= 50:
            score += 4
        else:
            score -= 4
        signals.append(f"Strong Trend (ADX={data.adx})")
    elif data.trend_strength == "Weak":
        signals.append(f"Weak Trend (ADX={data.adx})")

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

    return round(score, 1), rating, " | ".join(signals)
