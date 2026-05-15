"""
Free NSE market data: Yahoo Finance (yfinance) primary, jugaad-data (NSE) fallback.
No API keys or broker login required.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

import pandas as pd

_warned_missing_symbols: set[str] = set()
_last_history_source: dict[str, str] = {}


def _nse_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def to_yahoo_symbol(symbol: str) -> str:
    """NSE trading symbol → Yahoo ticker (e.g. RELIANCE → RELIANCE.NS)."""
    return f"{_nse_symbol(symbol)}.NS"


def _normalize_ohlcv_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    if isinstance(out.index, pd.DatetimeIndex) and "Date" not in out.columns:
        out = out.reset_index()
        first = out.columns[0]
        if str(first).lower() in ("date", "datetime", "index"):
            out = out.drop(columns=[first])

    colmap: dict[str, str] = {}
    for c in out.columns:
        cl = str(c).strip().lower().replace(" ", "").replace(".", "")
        if cl in ("open", "opening", "ch_opening_price"):
            colmap[c] = "Open"
        elif cl in ("high", "ch_trade_high_price"):
            colmap[c] = "High"
        elif cl in ("low", "ch_trade_low_price"):
            colmap[c] = "Low"
        elif cl in ("close", "closing", "ch_closing_price", "adjclose", "adj_close"):
            colmap[c] = "Close"
        elif cl in ("volume", "vol", "ch_tot_traded_qty", "ttl_trd_qnty"):
            colmap[c] = "Volume"
    out = out.rename(columns=colmap)

    if "Close" not in out.columns:
        return pd.DataFrame()

    for col in ("Open", "High", "Low", "Volume"):
        if col not in out.columns:
            if col == "Volume":
                out[col] = 0.0
            else:
                out[col] = out["Close"]

    keep = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in out.columns]
    out = out[keep].apply(pd.to_numeric, errors="coerce")
    out = out.dropna(subset=["Close"])
    return out.reset_index(drop=True)


def _fetch_yfinance_history(symbol: str, days: int) -> Optional[pd.DataFrame]:
    try:
        import yfinance as yf
    except ImportError:
        return None

    sym = _nse_symbol(symbol)
    yahoo = to_yahoo_symbol(sym)
    end_d = date.today() + timedelta(days=1)
    start_d = end_d - timedelta(days=max(days, 30) + 15)

    try:
        raw = yf.Ticker(yahoo).history(start=start_d, end=end_d, auto_adjust=True)
        df = _normalize_ohlcv_df(raw)
        if df is not None and not df.empty:
            _last_history_source[sym] = "yfinance"
            return df
    except Exception as e:
        print(f"  [warn] yfinance history error for {sym}: {e}")
    return None


def _fetch_jugaad_history(symbol: str, days: int) -> Optional[pd.DataFrame]:
    try:
        from jugaad_data.nse import stock_df
    except ImportError:
        return None

    sym = _nse_symbol(symbol)
    end_d = date.today()
    start_d = end_d - timedelta(days=max(days, 30) + 15)

    try:
        raw = stock_df(sym, start_d, end_d, series="EQ")
        df = _normalize_ohlcv_df(raw)
        if df is not None and not df.empty:
            _last_history_source[sym] = "jugaad-data"
            return df
    except Exception as e:
        print(f"  [warn] jugaad-data history error for {sym}: {e}")
    return None


def fetch_daily_history(symbol: str, days: int = 420) -> Optional[pd.DataFrame]:
    """Daily OHLCV (Open, High, Low, Close, Volume), oldest first."""
    sym = _nse_symbol(symbol)
    df = _fetch_yfinance_history(sym, days)
    if df is None or df.empty:
        df = _fetch_jugaad_history(sym, days)

    if df is None or df.empty:
        if sym not in _warned_missing_symbols:
            _warned_missing_symbols.add(sym)
            print(
                f"  [warn] No price history for {sym} (tried yfinance, then jugaad-data). "
                "Check NSE symbol spelling (e.g. M&M, BAJAJ-AUTO)."
            )
        return None
    return df


def _fetch_yfinance_quote(symbol: str) -> Optional[dict[str, Any]]:
    try:
        import yfinance as yf
    except ImportError:
        return None

    sym = _nse_symbol(symbol)
    try:
        t = yf.Ticker(to_yahoo_symbol(sym))
        fi = getattr(t, "fast_info", None)
        ltp = None
        vol = None
        if fi is not None:
            ltp = getattr(fi, "last_price", None) or getattr(fi, "lastPrice", None)
            vol = getattr(fi, "last_volume", None) or getattr(fi, "lastVolume", None)
        if ltp is None:
            info = t.info or {}
            ltp = info.get("regularMarketPrice") or info.get("currentPrice")
            vol = vol or info.get("regularMarketVolume") or info.get("volume")
        if ltp is not None:
            return {"ltp": ltp, "last_price": ltp, "volume": vol}
    except Exception as e:
        print(f"  [warn] yfinance quote error for {sym}: {e}")
    return None


def _fetch_jugaad_quote(symbol: str) -> Optional[dict[str, Any]]:
    sym = _nse_symbol(symbol)
    df = _fetch_jugaad_history(sym, days=10)
    if df is None or df.empty:
        return None
    try:
        ltp = float(df["Close"].iloc[-1])
        vol = float(df["Volume"].iloc[-1]) if "Volume" in df.columns else None
        return {"ltp": ltp, "last_price": ltp, "volume": vol}
    except (TypeError, ValueError, IndexError):
        return None


def fetch_quote(symbol: str) -> Optional[dict[str, Any]]:
    q = _fetch_yfinance_quote(symbol)
    if q:
        return q
    return _fetch_jugaad_quote(symbol)


def check_market_data_auth(sample_symbol: str = "RELIANCE") -> tuple[bool, str]:
    sym = _nse_symbol(sample_symbol)
    df = fetch_daily_history(sym, days=30)
    if df is not None and not df.empty:
        src = _last_history_source.get(sym, "yfinance/jugaad-data")
        return True, f"Market data OK ({src})."
    return False, (
        f"Could not fetch history for {sym}. Install yfinance and jugaad-data; "
        "check network and symbol spelling."
    )


def validate_symbols(symbols: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"ok": [], "missing": [], "unreachable": []}
    for sym in symbols:
        try:
            h = fetch_daily_history(sym, days=25)
            if h is not None and not h.empty and "Close" in h.columns:
                out["ok"].append(sym)
            else:
                out["missing"].append(sym)
        except Exception:
            out["unreachable"].append(sym)
    return out
