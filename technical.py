"""
Technical analysis using pandas_ta for Indian stocks.
Indicators: SMA(20/50), EMA(9/21), MACD(12,26,9), RSI, Stochastic, BB, ATR,
Supertrend, ADX, volume vs 20d avg, OBV. Composite score uses weighted
categories (trend / momentum / volatility / volume / ADX) with ADX gating
on momentum oscillators when ADX <= ADX_GATE_THRESHOLD.
"""

import math
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import pandas_ta as ta

from config import (
    TECHNICAL_PERIOD_DAYS,
    SMA_SHORT,
    SMA_LONG,
    EMA_SHORT,
    EMA_LONG,
    RSI_PERIOD,
    BOLLINGER_PERIOD,
    BOLLINGER_STD,
    MACD_FAST,
    MACD_SLOW,
    MACD_SIGNAL,
    ATR_PERIOD,
    STOCH_K,
    STOCH_D,
    STOCH_SMOOTH_K,
    SUPERTREND_LENGTH,
    SUPERTREND_MULTIPLIER,
    ADX_GATE_THRESHOLD,
)
from openalgo_data import fetch_daily_history

# Category weights for 0–100 technical score (sum = 1.0)
_W_TREND = 0.30
_W_MOMENTUM = 0.30
_W_VOLATILITY = 0.15
_W_VOLUME = 0.15
_W_ADX = 0.10


@dataclass
class TechnicalData:
    symbol: str
    current_price: float

    # Moving averages
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_9: Optional[float] = None
    ema_21: Optional[float] = None
    price_vs_sma20: Optional[str] = None  # Above | Below
    price_vs_sma50: Optional[str] = None
    golden_cross: Optional[bool] = None  # SMA20 > SMA50
    death_cross: Optional[bool] = None  # SMA20 < SMA50

    # RSI
    rsi: Optional[float] = None
    rsi_signal: Optional[str] = None  # Overbought | Oversold | Neutral

    # Stochastic (14, 3, 3)
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None
    stoch_signal: Optional[str] = None  # Overbought | Oversold | Neutral

    # MACD
    macd_value: Optional[float] = None
    macd_signal_line: Optional[float] = None
    macd_histogram: Optional[float] = None
    macd_signal_type: Optional[str] = None  # Bullish | Bearish

    # Bollinger Bands
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_signal: Optional[str] = None  # Overbought | Oversold | Neutral

    # ATR
    atr_14: Optional[float] = None

    # Supertrend (length, multiplier from config)
    supertrend: Optional[float] = None
    supertrend_direction: Optional[str] = None  # Bullish | Bearish

    # Volume
    avg_volume_20d: Optional[float] = None
    latest_volume: Optional[float] = None
    volume_signal: Optional[str] = None  # High | Normal | Low

    # OBV
    obv: Optional[float] = None
    obv_signal: Optional[str] = None  # Rising | Falling | Accumulation | Distribution | Neutral

    # ADX (trend strength)
    adx: Optional[float] = None
    trend_strength: Optional[str] = None  # Strong | Moderate | Weak
    adx_momentum_gate: bool = False  # True when ADX > threshold (oscillator signals trusted)

    # Overall
    score: float = 0.0  # 0-100
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


def _stoch_column_k() -> str:
    return f"STOCHk_{STOCH_K}_{STOCH_D}_{STOCH_SMOOTH_K}"


def _stoch_column_d() -> str:
    return f"STOCHd_{STOCH_K}_{STOCH_D}_{STOCH_SMOOTH_K}"


def _supertrend_cols() -> tuple[str, str]:
    return (
        f"SUPERT_{SUPERTREND_LENGTH}_{SUPERTREND_MULTIPLIER}",
        f"SUPERTd_{SUPERTREND_LENGTH}_{SUPERTREND_MULTIPLIER}",
    )


def _obv_character(close: pd.Series, obv_s: pd.Series) -> str:
    if obv_s is None or obv_s.empty or len(obv_s) < 12 or len(close) < 12:
        return "Neutral"
    px_chg = float(close.iloc[-1]) - float(close.iloc[-11])
    obv_chg = float(obv_s.iloc[-1]) - float(obv_s.iloc[-11])
    if px_chg < 0 and obv_chg > 0:
        return "Accumulation"
    if px_chg > 0 and obv_chg < 0:
        return "Distribution"
    if obv_chg > 0:
        return "Rising"
    if obv_chg < 0:
        return "Falling"
    return "Neutral"


def fetch_technical(symbol: str) -> Optional[TechnicalData]:
    """Compute technical indicators for a stock."""
    try:
        df = fetch_daily_history(symbol, days=TECHNICAL_PERIOD_DAYS + 60)

        if df is None or df.empty or len(df) < 50:
            return None

        df = df.dropna(subset=["Close"])
        if df.empty:
            return None

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]
        current_price = _safe_float(close.iloc[-1])
        if current_price is None:
            return None

        data = TechnicalData(symbol=symbol, current_price=current_price)

        sma20 = ta.sma(close, length=SMA_SHORT)
        sma50 = ta.sma(close, length=SMA_LONG)
        ema9 = ta.ema(close, length=EMA_SHORT)
        ema21 = ta.ema(close, length=EMA_LONG)

        if sma20 is not None and not sma20.empty:
            data.sma_20 = _safe_float(sma20.iloc[-1])
            if data.sma_20:
                data.price_vs_sma20 = "Above" if current_price > data.sma_20 else "Below"
        if sma50 is not None and not sma50.empty:
            data.sma_50 = _safe_float(sma50.iloc[-1])
            if data.sma_50:
                data.price_vs_sma50 = "Above" if current_price > data.sma_50 else "Below"
        if ema9 is not None and not ema9.empty:
            data.ema_9 = _safe_float(ema9.iloc[-1])
        if ema21 is not None and not ema21.empty:
            data.ema_21 = _safe_float(ema21.iloc[-1])

        if data.sma_20 and data.sma_50:
            data.golden_cross = data.sma_20 > data.sma_50
            data.death_cross = data.sma_20 < data.sma_50

        rsi = ta.rsi(close, length=RSI_PERIOD)
        if rsi is not None and not rsi.empty:
            data.rsi = _safe_float(rsi.iloc[-1])
            if data.rsi is not None and data.rsi > 70:
                data.rsi_signal = "Overbought"
            elif data.rsi is not None and data.rsi < 30:
                data.rsi_signal = "Oversold"
            else:
                data.rsi_signal = "Neutral"

        stoch_df = ta.stoch(
            high, low, close,
            k=STOCH_K, d=STOCH_D, smooth_k=STOCH_SMOOTH_K,
        )
        if stoch_df is not None and not stoch_df.empty:
            kcol, dcol = _stoch_column_k(), _stoch_column_d()
            if kcol in stoch_df.columns:
                data.stoch_k = _safe_float(stoch_df[kcol].iloc[-1])
            if dcol in stoch_df.columns:
                data.stoch_d = _safe_float(stoch_df[dcol].iloc[-1])
            if data.stoch_k is not None and data.stoch_d is not None:
                if data.stoch_k > 80 and data.stoch_d > 80:
                    data.stoch_signal = "Overbought"
                elif data.stoch_k < 20 and data.stoch_d < 20:
                    data.stoch_signal = "Oversold"
                else:
                    data.stoch_signal = "Neutral"

        macd_df = ta.macd(close, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
        if macd_df is not None and not macd_df.empty:
            data.macd_value = _safe_float(macd_df.iloc[-1, 0])
            data.macd_histogram = _safe_float(macd_df.iloc[-1, 1])
            data.macd_signal_line = _safe_float(macd_df.iloc[-1, 2])
            if data.macd_value is not None and data.macd_signal_line is not None:
                data.macd_signal_type = (
                    "Bullish" if data.macd_value > data.macd_signal_line else "Bearish"
                )

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

        atr_s = ta.atr(high, low, close, length=ATR_PERIOD)
        if atr_s is not None and not atr_s.empty:
            data.atr_14 = _safe_float(atr_s.iloc[-1])

        st_line, st_dir = _supertrend_cols()
        st_df = ta.supertrend(
            high, low, close,
            length=SUPERTREND_LENGTH,
            multiplier=SUPERTREND_MULTIPLIER,
        )
        if st_df is not None and not st_df.empty and st_line in st_df.columns:
            data.supertrend = _safe_float(st_df[st_line].iloc[-1])
            if st_dir in st_df.columns:
                dval = st_df[st_dir].iloc[-1]
                try:
                    dv = float(dval)
                    data.supertrend_direction = "Bullish" if dv > 0 else "Bearish"
                except (TypeError, ValueError):
                    pass

        if len(volume) >= 20:
            data.avg_volume_20d = float(volume.tail(20).mean())
            data.latest_volume = float(volume.iloc[-1])
            vol_ratio = (
                data.latest_volume / data.avg_volume_20d if data.avg_volume_20d > 0 else 1.0
            )
            if vol_ratio > 1.5:
                data.volume_signal = "High"
            elif vol_ratio < 0.5:
                data.volume_signal = "Low"
            else:
                data.volume_signal = "Normal"

        obv_s = ta.obv(close, volume)
        if obv_s is not None and not obv_s.empty:
            data.obv = _safe_float(obv_s.iloc[-1])
            data.obv_signal = _obv_character(close, obv_s)

        adx_df = ta.adx(high, low, close, length=14)
        if adx_df is not None and not adx_df.empty:
            data.adx = _safe_float(adx_df.iloc[-1, 0])
            if data.adx is not None:
                data.adx_momentum_gate = data.adx > ADX_GATE_THRESHOLD
                if data.adx > ADX_GATE_THRESHOLD:
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


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _score_trend(data: TechnicalData) -> tuple[float, list[str]]:
    s = 50.0
    sig: list[str] = []
    if data.price_vs_sma20 == "Above":
        s += 10
        sig.append("Price > SMA20")
    elif data.price_vs_sma20 == "Below":
        s -= 10
        sig.append("Price < SMA20")
    if data.price_vs_sma50 == "Above":
        s += 10
        sig.append("Price > SMA50")
    elif data.price_vs_sma50 == "Below":
        s -= 10
        sig.append("Price < SMA50")
    if data.golden_cross:
        s += 12
        sig.append("Golden Cross (SMA20>SMA50)")
    elif data.death_cross:
        s -= 12
        sig.append("Death Cross (SMA20<SMA50)")
    if data.supertrend_direction == "Bullish":
        s += 10
        sig.append("Supertrend Bullish")
    elif data.supertrend_direction == "Bearish":
        s -= 10
        sig.append("Supertrend Bearish")
    if data.ema_9 is not None and data.ema_21 is not None:
        if data.ema_9 > data.ema_21:
            s += 8
            sig.append("EMA9 > EMA21")
        else:
            s -= 8
            sig.append("EMA9 < EMA21")
    return _clamp(s), sig


def _score_momentum_raw(data: TechnicalData) -> tuple[float, list[str]]:
    s = 50.0
    sig: list[str] = []
    if data.rsi is not None:
        if data.rsi < 30:
            s += 12
            sig.append(f"RSI Oversold ({data.rsi})")
        elif data.rsi < 40:
            s += 5
            sig.append(f"RSI Mild Bull ({data.rsi})")
        elif data.rsi > 70:
            s -= 12
            sig.append(f"RSI Overbought ({data.rsi})")
        elif data.rsi > 60:
            s -= 4
            sig.append(f"RSI Mild Bear ({data.rsi})")
        else:
            sig.append(f"RSI Neutral ({data.rsi})")
    if data.stoch_signal == "Oversold":
        s += 10
        sig.append(f"Stoch Oversold (K={data.stoch_k})")
    elif data.stoch_signal == "Overbought":
        s -= 10
        sig.append(f"Stoch Overbought (K={data.stoch_k})")
    elif data.stoch_k is not None and data.stoch_d is not None:
        sig.append(f"Stoch K={data.stoch_k} D={data.stoch_d}")
    if data.macd_signal_type == "Bullish":
        s += 10
        sig.append("MACD Bullish")
    elif data.macd_signal_type == "Bearish":
        s -= 10
        sig.append("MACD Bearish")
    if data.macd_histogram is not None:
        if data.macd_histogram > 0:
            s += 4
        elif data.macd_histogram < 0:
            s -= 4
    return _clamp(s), sig


def _apply_adx_momentum_gate(momentum_score: float, data: TechnicalData) -> tuple[float, list[str]]:
    extra: list[str] = []
    if data.adx is None:
        return momentum_score, extra
    if data.adx <= ADX_GATE_THRESHOLD:
        dampened = 50.0 + (momentum_score - 50.0) * 0.35
        extra.append(
            f"Momentum gated (ADX {data.adx} ≤ {ADX_GATE_THRESHOLD}, ranging)"
        )
        return _clamp(dampened), extra
    extra.append(f"Momentum active (ADX {data.adx} > {ADX_GATE_THRESHOLD})")
    return momentum_score, extra


def _score_volatility(data: TechnicalData) -> tuple[float, list[str]]:
    s = 50.0
    sig: list[str] = []
    if data.bb_signal == "Oversold":
        s += 18
        sig.append("BB Oversold")
    elif data.bb_signal == "Overbought":
        s -= 18
        sig.append("BB Overbought")
    else:
        sig.append("BB Neutral band")
    if data.atr_14 is not None and data.current_price:
        atr_pct = (data.atr_14 / data.current_price) * 100.0
        if atr_pct < 1.5:
            s += 6
            sig.append(f"ATR low vs price ({atr_pct:.2f}%)")
        elif atr_pct > 4.0:
            s -= 6
            sig.append(f"ATR high vs price ({atr_pct:.2f}%)")
        else:
            sig.append(f"ATR {data.atr_14}")
    return _clamp(s), sig


def _score_volume_cat(data: TechnicalData) -> tuple[float, list[str]]:
    s = 50.0
    sig: list[str] = []
    up_ctx = data.price_vs_sma20 == "Above" or data.price_vs_sma50 == "Above"
    if data.volume_signal == "High":
        s += 12 if up_ctx else -10
        sig.append("Volume vs 20d: High")
    elif data.volume_signal == "Low":
        s -= 4
        sig.append("Volume vs 20d: Low")
    else:
        sig.append("Volume vs 20d: Normal")
    if data.obv_signal == "Accumulation":
        s += 12
        sig.append("OBV Accumulation")
    elif data.obv_signal == "Distribution":
        s -= 12
        sig.append("OBV Distribution")
    elif data.obv_signal == "Rising":
        s += 6
        sig.append("OBV Rising")
    elif data.obv_signal == "Falling":
        s -= 6
        sig.append("OBV Falling")
    return _clamp(s), sig


def _score_adx_cat(data: TechnicalData) -> tuple[float, list[str]]:
    sig: list[str] = []
    if data.adx is None or data.sma_50 is None:
        return 50.0, ["ADX N/A"]
    if data.adx <= ADX_GATE_THRESHOLD:
        sig.append(f"ADX ranging ({data.adx})")
        return _clamp(46.0 + data.adx * 0.15), sig
    strength = min(1.0, max(0.0, (data.adx - ADX_GATE_THRESHOLD) / 30.0))
    bullish = data.current_price > data.sma_50
    base = 50.0 + 38.0 * strength * (1.0 if bullish else -1.0)
    sig.append(f"ADX trending ({data.adx}, {'+' if bullish else '-'} bias vs SMA50)")
    return _clamp(base), sig


def _compute_technical_score(data: TechnicalData) -> tuple[float, str, str]:
    """Weighted 0–100 score: trend 30%, momentum 30%, volatility 15%, volume 15%, ADX 10%."""
    t_sc, t_sig = _score_trend(data)
    m_sc, m_sig = _score_momentum_raw(data)
    m_sc, gate_sig = _apply_adx_momentum_gate(m_sc, data)
    v_sc, v_sig = _score_volatility(data)
    vol_sc, vol_sig = _score_volume_cat(data)
    adx_sc, adx_sig = _score_adx_cat(data)

    score = (
        _W_TREND * t_sc
        + _W_MOMENTUM * m_sc
        + _W_VOLATILITY * v_sc
        + _W_VOLUME * vol_sc
        + _W_ADX * adx_sc
    )
    score = round(_clamp(score), 1)

    all_sig = t_sig + gate_sig + m_sig + v_sig + vol_sig + adx_sig
    summary = " | ".join(all_sig)

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

    return score, rating, summary
