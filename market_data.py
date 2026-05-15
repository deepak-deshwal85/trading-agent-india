"""
Free NSE market data: Yahoo Finance (yfinance) primary, jugaad-data (NSE) fallback.
Tracks per-provider results; final error report shown in console and PDF (no log files).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Optional

import pandas as pd

_last_history_source: dict[str, str] = {}
_fetch_reports: dict[str, "SymbolFetchReport"] = {}


@dataclass
class ProviderAttempt:
    provider: str
    ok: bool = False
    status: str = "not_tried"
    detail: str = ""

    def summary(self) -> str:
        if self.ok:
            return "OK"
        return f"{self.status}: {self.detail}" if self.detail else self.status


@dataclass
class SymbolFetchReport:
    symbol: str
    kind: str = "history"
    yfinance: ProviderAttempt = field(default_factory=lambda: ProviderAttempt("yfinance"))
    jugaad: ProviderAttempt = field(default_factory=lambda: ProviderAttempt("jugaad-data"))
    resolved_source: str = ""
    both_failed: bool = False

    def record_provider(self, attempt: ProviderAttempt) -> None:
        if attempt.provider == "yfinance":
            self.yfinance = attempt
        else:
            self.jugaad = attempt

    def finalize(self) -> None:
        self.both_failed = not self.yfinance.ok and not self.jugaad.ok


@dataclass
class MarketDataReportSummary:
    total: int = 0
    ok_yfinance: int = 0
    ok_jugaad: int = 0
    both_failed: int = 0


def reset_fetch_reports() -> None:
    _fetch_reports.clear()
    _last_history_source.clear()


def get_fetch_reports() -> dict[str, SymbolFetchReport]:
    return dict(_fetch_reports)


def get_history_reports() -> list[SymbolFetchReport]:
    return sorted(
        (r for r in _fetch_reports.values() if r.kind == "history"),
        key=lambda r: r.symbol,
    )


def build_market_data_report() -> tuple[MarketDataReportSummary, list[SymbolFetchReport]]:
    """Summary counts + all per-symbol history fetch reports."""
    reports = get_history_reports()
    summary = MarketDataReportSummary(total=len(reports))
    for r in reports:
        if r.both_failed:
            summary.both_failed += 1
        elif r.resolved_source == "yfinance":
            summary.ok_yfinance += 1
        elif r.resolved_source == "jugaad-data":
            summary.ok_jugaad += 1
    return summary, reports


def get_failed_history_reports() -> list[SymbolFetchReport]:
    return [r for r in get_history_reports() if r.both_failed]


def get_reports_with_fetch_issues() -> list[SymbolFetchReport]:
    """Symbols where yfinance and/or jugaad-data failed (excludes clean yfinance-only success)."""
    issues: list[SymbolFetchReport] = []
    for r in get_history_reports():
        y_failed = not r.yfinance.ok
        j_failed = not r.jugaad.ok and r.jugaad.status != "skipped"
        if y_failed or j_failed:
            issues.append(r)
    return issues


def _nse_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def to_yahoo_symbol(symbol: str) -> str:
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
            out[col] = 0.0 if col == "Volume" else out["Close"]

    keep = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in out.columns]
    out = out[keep].apply(pd.to_numeric, errors="coerce")
    return out.dropna(subset=["Close"]).reset_index(drop=True)


def _fetch_yfinance_history(symbol: str, days: int) -> tuple[Optional[pd.DataFrame], ProviderAttempt]:
    sym = _nse_symbol(symbol)
    yahoo = to_yahoo_symbol(sym)
    attempt = ProviderAttempt(provider="yfinance")

    try:
        import yfinance as yf
    except ImportError as e:
        attempt.status = "import_error"
        attempt.detail = str(e)
        return None, attempt

    end_d = date.today() + timedelta(days=1)
    start_d = end_d - timedelta(days=max(days, 30) + 15)

    try:
        raw = yf.Ticker(yahoo).history(start=start_d, end=end_d, auto_adjust=True)
        if raw is None or raw.empty:
            attempt.status = "empty"
            attempt.detail = f"No rows for {yahoo}"
            return None, attempt

        df = _normalize_ohlcv_df(raw)
        if df.empty:
            attempt.status = "normalize_empty"
            attempt.detail = f"No usable OHLCV for {yahoo}"
            return None, attempt

        attempt.ok = True
        attempt.status = "ok"
        attempt.detail = f"{len(df)} bars"
        _last_history_source[sym] = "yfinance"
        return df, attempt
    except Exception as e:
        attempt.status = "exception"
        attempt.detail = str(e)
        return None, attempt


def _fetch_jugaad_history(symbol: str, days: int) -> tuple[Optional[pd.DataFrame], ProviderAttempt]:
    sym = _nse_symbol(symbol)
    attempt = ProviderAttempt(provider="jugaad-data")

    try:
        from jugaad_data.nse import stock_df
    except ImportError as e:
        attempt.status = "import_error"
        attempt.detail = str(e)
        return None, attempt

    end_d = date.today()
    start_d = end_d - timedelta(days=max(days, 30) + 15)

    try:
        raw = stock_df(sym, start_d, end_d, series="EQ")
        if raw is None or raw.empty:
            attempt.status = "empty"
            attempt.detail = f"No NSE rows for {sym}"
            return None, attempt

        df = _normalize_ohlcv_df(raw)
        if df.empty:
            attempt.status = "normalize_empty"
            attempt.detail = "OHLCV normalization failed"
            return None, attempt

        attempt.ok = True
        attempt.status = "ok"
        attempt.detail = f"{len(df)} bars"
        _last_history_source[sym] = "jugaad-data"
        return df, attempt
    except Exception as e:
        attempt.status = "exception"
        attempt.detail = str(e)
        return None, attempt


def _store_report(report: SymbolFetchReport) -> None:
    _fetch_reports[f"{report.symbol}:{report.kind}"] = report


def fetch_daily_history(symbol: str, days: int = 420) -> Optional[pd.DataFrame]:
    sym = _nse_symbol(symbol)
    report = SymbolFetchReport(symbol=sym, kind="history")

    df, y_attempt = _fetch_yfinance_history(sym, days)
    report.record_provider(y_attempt)

    if df is None or df.empty:
        df, j_attempt = _fetch_jugaad_history(sym, days)
        report.record_provider(j_attempt)
    else:
        report.jugaad.status = "skipped"
        report.jugaad.detail = "yfinance succeeded"
        report.resolved_source = "yfinance"

    if df is not None and not df.empty:
        if not report.resolved_source:
            report.resolved_source = _last_history_source.get(sym, "jugaad-data")
        report.finalize()
        _store_report(report)
        return df

    report.resolved_source = ""
    report.finalize()
    _store_report(report)
    return None


def _fetch_yfinance_quote(symbol: str) -> tuple[Optional[dict[str, Any]], ProviderAttempt]:
    sym = _nse_symbol(symbol)
    attempt = ProviderAttempt(provider="yfinance")

    try:
        import yfinance as yf
    except ImportError as e:
        attempt.status = "import_error"
        attempt.detail = str(e)
        return None, attempt

    yahoo = to_yahoo_symbol(sym)
    try:
        t = yf.Ticker(yahoo)
        fi = getattr(t, "fast_info", None)
        ltp = vol = None
        if fi is not None:
            ltp = getattr(fi, "last_price", None) or getattr(fi, "lastPrice", None)
            vol = getattr(fi, "last_volume", None) or getattr(fi, "lastVolume", None)
        if ltp is None:
            info = t.info or {}
            ltp = info.get("regularMarketPrice") or info.get("currentPrice")
            vol = vol or info.get("regularMarketVolume") or info.get("volume")
        if ltp is not None:
            attempt.ok = True
            attempt.status = "ok"
            return {"ltp": ltp, "last_price": ltp, "volume": vol}, attempt
        attempt.status = "empty"
        attempt.detail = f"No LTP for {yahoo}"
        return None, attempt
    except Exception as e:
        attempt.status = "exception"
        attempt.detail = str(e)
        return None, attempt


def _fetch_jugaad_quote(symbol: str) -> tuple[Optional[dict[str, Any]], ProviderAttempt]:
    sym = _nse_symbol(symbol)
    attempt = ProviderAttempt(provider="jugaad-data")
    df, hist_attempt = _fetch_jugaad_history(sym, days=10)
    if hist_attempt.ok and df is not None and not df.empty:
        try:
            ltp = float(df["Close"].iloc[-1])
            vol = float(df["Volume"].iloc[-1]) if "Volume" in df.columns else None
            attempt.ok = True
            attempt.status = "ok"
            attempt.detail = "from last NSE close"
            return {"ltp": ltp, "last_price": ltp, "volume": vol}, attempt
        except (TypeError, ValueError, IndexError) as e:
            attempt.status = "exception"
            attempt.detail = str(e)
            return None, attempt
    attempt.status = hist_attempt.status
    attempt.detail = hist_attempt.detail or "history fallback failed"
    return None, attempt


def fetch_quote(symbol: str) -> Optional[dict[str, Any]]:
    sym = _nse_symbol(symbol)
    report = SymbolFetchReport(symbol=sym, kind="quote")

    q, y_attempt = _fetch_yfinance_quote(sym)
    report.record_provider(y_attempt)
    if q:
        report.jugaad.status = "skipped"
        report.jugaad.detail = "yfinance succeeded"
        report.resolved_source = "yfinance"
        report.finalize()
        _store_report(report)
        return q

    q, j_attempt = _fetch_jugaad_quote(sym)
    report.record_provider(j_attempt)
    if q:
        report.resolved_source = "jugaad-data"
        report.finalize()
        _store_report(report)
        return q

    report.finalize()
    _store_report(report)
    return None


def check_market_data_auth(sample_symbol: str = "RELIANCE") -> tuple[bool, str]:
    reset_fetch_reports()
    sym = _nse_symbol(sample_symbol)
    df = fetch_daily_history(sym, days=30)
    if df is not None and not df.empty:
        src = _last_history_source.get(sym, "yfinance")
        return True, f"Market data OK ({src})."
    reports = get_fetch_reports()
    key = f"{sym}:history"
    if key in reports:
        r = reports[key]
        return False, (
            f"Market data failed for {sym}. yfinance: {r.yfinance.summary()}; "
            f"jugaad-data: {r.jugaad.summary()}."
        )
    return False, f"Could not fetch history for {sym}."


def validate_symbols(symbols: list[str]) -> dict[str, list[str]]:
    reset_fetch_reports()
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
