"""
Market data via OpenAlgo (Zerodha / broker) — replaces Yahoo Finance for OHLCV and quotes.
Requires OpenAlgo server running and OPENALGO_API_KEY in .env.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

import pandas as pd

from config import (
    OPENALGO_API_KEY,
    OPENALGO_HOST,
    OPENALGO_EXCHANGE,
    OPENALGO_HISTORY_SOURCE,
)

_client: Any = None
_symbol_cache: dict[str, str] = {}
_symbol_aliases: dict[str, str] = {
    # Add manual overrides here if broker symbol differs.
    "M&M": "M_M",
}
_warned_missing_symbols: set[str] = set()


def get_openalgo_client():
    """Lazy singleton OpenAlgo API client."""
    global _client
    if not OPENALGO_API_KEY:
        raise RuntimeError(
            "OPENALGO_API_KEY is missing. Set it in .env (see README)."
        )
    if _client is None:
        from openalgo import api

        host = (OPENALGO_HOST or "http://127.0.0.1:5000").rstrip("/")
        _client = api(api_key=OPENALGO_API_KEY, host=host)
    return _client


def check_openalgo_auth(sample_symbol: str = "RELIANCE") -> tuple[bool, str]:
    """
    Lightweight auth check against quotes endpoint.
    Returns (ok, message).
    """
    try:
        client = get_openalgo_client()
        res = client.quotes(symbol=sample_symbol, exchange=OPENALGO_EXCHANGE)
        if isinstance(res, dict) and res.get("status") == "success":
            return True, "OpenAlgo authentication OK."
        msg = res.get("message", str(res)) if isinstance(res, dict) else str(res)
        if "Incorrect `api_key` or `access_token`" in msg:
            return (
                False,
                "OpenAlgo rejected credentials/token. Verify APP API key and refresh broker access token in OpenAlgo dashboard.",
            )
        return False, f"OpenAlgo auth/data check failed: {msg}"
    except Exception as e:
        return False, f"OpenAlgo connectivity/auth check error: {e}"


def _normalize_hist_df(df: pd.DataFrame) -> pd.DataFrame:
    """Map broker/OpenAlgo columns to yfinance-style names for pandas_ta."""
    if df is None or df.empty:
        return df
    mapping = {}
    for c in df.columns:
        cl = c.lower()
        if cl == "open":
            mapping[c] = "Open"
        elif cl == "high":
            mapping[c] = "High"
        elif cl == "low":
            mapping[c] = "Low"
        elif cl == "close":
            mapping[c] = "Close"
        elif cl == "volume":
            mapping[c] = "Volume"
    return df.rename(columns=mapping)


def _resolve_symbol(raw_symbol: str, refresh: bool = False) -> str:
    """
    Resolve app symbol to broker/OpenAlgo symbol.
    Strategy:
      1) cache hit
      2) hardcoded alias map
      3) exact query search on OpenAlgo
      4) fallback to original symbol
    """
    sym = (raw_symbol or "").strip()
    if not sym:
        return raw_symbol

    if sym in _symbol_cache and not refresh:
        return _symbol_cache[sym]

    if sym in _symbol_aliases:
        resolved = _symbol_aliases[sym]
        _symbol_cache[sym] = resolved
        return resolved

    try:
        client = get_openalgo_client()
        res = client.search(query=sym, exchange=OPENALGO_EXCHANGE)
        if isinstance(res, dict) and res.get("status") == "success":
            data = res.get("data")
            if isinstance(data, list):
                # Prefer exact symbol match when available.
                for item in data:
                    if isinstance(item, dict) and str(item.get("symbol", "")).upper() == sym.upper():
                        resolved = str(item.get("symbol"))
                        _symbol_cache[sym] = resolved
                        return resolved
                if data and isinstance(data[0], dict) and data[0].get("symbol"):
                    resolved = str(data[0]["symbol"])
                    _symbol_cache[sym] = resolved
                    return resolved
    except Exception:
        pass

    _symbol_cache[sym] = sym
    return sym


def fetch_daily_history(symbol: str, days: int = 420) -> Optional[pd.DataFrame]:
    """
    Daily OHLCV DataFrame (Open, High, Low, Close, Volume), newest last.
    Returns None on failure.
    """
    try:
        client = get_openalgo_client()
        end = datetime.now().date()
        start = end - timedelta(days=days)
        resolved_symbol = _resolve_symbol(symbol)

        def _call_history(source: str, use_symbol: str):
            return client.history(
                symbol=use_symbol,
                exchange=OPENALGO_EXCHANGE,
                interval="D",
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                source=source,
            )

        res = _call_history(OPENALGO_HISTORY_SOURCE, resolved_symbol)
        # If broker API token is invalid, db source may still work if Historify is enabled.
        if isinstance(res, dict):
            msg = str(res.get("message", ""))
            if ("Incorrect `api_key` or `access_token`" in msg
                    and OPENALGO_HISTORY_SOURCE != "db"):
                res = _call_history("db", resolved_symbol)
            elif "not found for exchange" in msg.lower() and resolved_symbol == symbol:
                # Retry once with search-resolved symbol.
                retry_symbol = _resolve_symbol(symbol, refresh=True)
                if retry_symbol != resolved_symbol:
                    res = _call_history(OPENALGO_HISTORY_SOURCE, retry_symbol)
                    if (isinstance(res, dict) and OPENALGO_HISTORY_SOURCE != "db"
                            and "Incorrect `api_key` or `access_token`" in str(res.get("message", ""))):
                        res = _call_history("db", retry_symbol)

        if isinstance(res, dict):
            msg = res.get("message", res)
            lowered = str(msg).lower()
            if "not found for exchange" in lowered:
                if symbol not in _warned_missing_symbols:
                    _warned_missing_symbols.add(symbol)
                    print(
                        f"  [warn] OpenAlgo symbol missing: {symbol}. "
                        "Run master contract/instrument sync in OpenAlgo dashboard, "
                        "then retry."
                    )
            else:
                print(f"  [warn] OpenAlgo history failed for {symbol}: {msg}")
            return None
        res = _normalize_hist_df(res)
        if res is None or res.empty or "Close" not in res.columns:
            return None
        return res.dropna(subset=["Close"])
    except Exception as e:
        print(f"  [warn] OpenAlgo history error for {symbol}: {e}")
        return None


def fetch_quote(symbol: str) -> Optional[dict[str, Any]]:
    """Latest quote dict (ltp, high, low, volume, …) or None."""
    try:
        client = get_openalgo_client()
        resolved_symbol = _resolve_symbol(symbol)
        res = client.quotes(symbol=resolved_symbol, exchange=OPENALGO_EXCHANGE)
        if (isinstance(res, dict)
                and res.get("status") != "success"
                and "not found for exchange" in str(res.get("message", "")).lower()
                and resolved_symbol == symbol):
            retry_symbol = _resolve_symbol(symbol, refresh=True)
            if retry_symbol != resolved_symbol:
                res = client.quotes(symbol=retry_symbol, exchange=OPENALGO_EXCHANGE)
        if not isinstance(res, dict) or res.get("status") != "success":
            if isinstance(res, dict):
                msg = res.get("message", res)
                if "Incorrect `api_key` or `access_token`" in str(msg):
                    print(
                        "  [warn] OpenAlgo quotes auth failed. "
                        "Check APP API key and refresh broker access token in OpenAlgo."
                    )
                else:
                    lowered = str(msg).lower()
                    if "not found for exchange" in lowered:
                        if symbol not in _warned_missing_symbols:
                            _warned_missing_symbols.add(symbol)
                            print(
                                f"  [warn] OpenAlgo symbol missing: {symbol}. "
                                "Run master contract/instrument sync in OpenAlgo dashboard, "
                                "then retry."
                            )
                    else:
                        print(f"  [warn] OpenAlgo quotes failed for {symbol}: {msg}")
            return None
        data = res.get("data")
        return data if isinstance(data, dict) else None
    except Exception as e:
        print(f"  [warn] OpenAlgo quotes error for {symbol}: {e}")
        return None


def validate_symbols(symbols: list[str]) -> dict[str, list[str]]:
    """
    Validate a list of symbols against OpenAlgo availability.
    Returns:
      {
        "ok": [symbols...],
        "missing": [symbols...],
        "unreachable": [symbols...],
      }
    """
    out = {"ok": [], "missing": [], "unreachable": []}
    try:
        client = get_openalgo_client()
    except Exception:
        out["unreachable"] = list(symbols)
        return out

    for sym in symbols:
        resolved = _resolve_symbol(sym, refresh=True)
        try:
            res = client.quotes(symbol=resolved, exchange=OPENALGO_EXCHANGE)
            if isinstance(res, dict) and res.get("status") == "success":
                out["ok"].append(sym)
                continue
            if isinstance(res, dict):
                msg = str(res.get("message", "")).lower()
                if "not found for exchange" in msg or "no matching symbols found" in msg:
                    out["missing"].append(sym)
                elif "incorrect `api_key` or `access_token`" in msg:
                    out["unreachable"].append(sym)
                else:
                    # treat unknown broker/API failures as unreachable for safety
                    out["unreachable"].append(sym)
            else:
                out["unreachable"].append(sym)
        except Exception:
            out["unreachable"].append(sym)
    return out
