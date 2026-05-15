"""
Indian Market Stock Advisory System
====================================
Aggregates news from 10+ sources, performs sentiment / fundamental / technical
analysis on Nifty 50 stocks, and uses AI (Claude / GPT) for expert-level
investment recommendations.

Usage:
    python main.py                                  # Analyze all Nifty 50 (VADER, no AI)
    python main.py --stocks RELIANCE INFY TCS       # Specific stocks
    python main.py --ai --provider anthropic          # AI via Claude (provider required)
    python main.py --ai --provider openai           # AI via GPT
    python main.py --ai --detailed                   # AI + detailed per-stock panels
    python main.py --top 10                          # Show top/bottom 10 only
    python main.py --finbert                         # Ensemble: VADER + FinBERT (+ optional Tone)
"""

import argparse
import sys
import time
import os
import csv
from datetime import datetime
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel

import config
from config import (
    NIFTY_50,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_CAPTION,
)
from market_data import (
    check_market_data_auth,
    validate_symbols,
    reset_fetch_reports,
    build_market_data_report,
)
from news_fetcher import (
    fetch_all_market_news, fetch_world_news,
    fetch_stock_specific_news, NewsItem,
)
from sentiment import analyze_news_sentiment, aggregate_sentiment
from fundamental import fetch_fundamentals, FundamentalData
from technical import fetch_technical, TechnicalData
from recommendation import generate_recommendation, Recommendation
from ai_analyzer import (
    analyze_stock_with_ai, generate_market_overview,
    AIInsight, MarketOverview,
)
from pdf_report import generate_pdf_report
from report import (
    console, print_header, print_market_sentiment, print_market_data_fetch_report,
    print_recommendation_summary,
    print_detailed_stock_report, print_buy_sell_hold_lists,
    print_disclaimer, print_footer,
    print_ai_market_overview, print_ai_stock_insight,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Indian Market Stock Advisory System — Nifty 50 Analysis"
    )
    parser.add_argument(
        "--stocks", nargs="+", default=None,
        help="Specific stock symbols to analyze (e.g., RELIANCE INFY TCS). "
             "Defaults to all Nifty 50.",
    )
    parser.add_argument(
        "--top", type=int, default=None,
        help="Show only top N and bottom N stocks in summary.",
    )
    parser.add_argument(
        "--finbert", action="store_true",
        help="Use ensemble sentiment: VADER + ProsusAI FinBERT (+ FinBERT-Tone if available).",
    )
    parser.add_argument(
        "--ai", action="store_true",
        help="Enable AI deep analysis (requires --provider and API key in .env).",
    )
    parser.add_argument(
        "--provider", type=str, default=None, choices=["anthropic", "openai"],
        help="AI provider: anthropic or openai (required when using --ai).",
    )
    parser.add_argument(
        "--detailed", action="store_true",
        help="Print detailed analysis panel for each stock.",
    )
    parser.add_argument(
        "--skip-news", action="store_true",
        help="Skip news fetching (faster re-runs for testing).",
    )
    parser.add_argument(
        "--pdf", action="store_true",
        help="Export report as a modern PDF file.",
    )
    parser.add_argument(
        "--pdf-file", type=str, default="market_report.pdf",
        help="Output PDF file path (default: market_report.pdf).",
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="Do not send the PDF to Telegram (default: send when TELEGRAM_* is set in .env).",
    )
    parser.add_argument(
        "--validate-symbols", action="store_true",
        help="Validate symbols (yfinance / jugaad-data) and exit (no analysis run).",
    )
    parser.add_argument(
        "--drop-missing", action="store_true",
        help="Validate symbols first and auto-drop missing/unreachable symbols from analysis.",
    )
    parser.add_argument(
        "--symbol-report-csv", type=str, default=None,
        help="Optional CSV path to save symbol validation result (status per symbol).",
    )
    args = parser.parse_args()
    if args.ai and not args.provider:
        parser.error("--ai requires --provider (anthropic or openai)")
    if args.provider and not args.ai:
        parser.error("--provider is only valid together with --ai")
    return args


def _send_pdf_to_telegram(pdf_path: str) -> None:
    """Send PDF via Telegram if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are in .env."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        console.print(
            "[dim]Telegram: skipped — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env "
            "to auto-send the PDF (or run: python scripts/send_telegram.py --file ...).[/dim]"
        )
        return

    scripts_dir = Path(__file__).resolve().parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from send_telegram import send_document  # noqa: E402

    caption = TELEGRAM_CAPTION or (
        f"Indian Market Advisory — {datetime.now().strftime('%d %b %Y, %H:%M IST')}"
    )
    try:
        send_document(
            pdf_path,
            token=TELEGRAM_BOT_TOKEN,
            chat_id=TELEGRAM_CHAT_ID,
            caption=caption,
        )
        console.print(f"[bold green]PDF sent to Telegram[/] (chat {TELEGRAM_CHAT_ID})")
    except Exception as e:
        console.print(f"[bold red]Telegram send failed:[/] {e}")
        console.print(
            "[dim]Fix .env credentials or run manually: "
            f"python scripts/send_telegram.py --file {pdf_path}[/dim]"
        )


def main():
    args = parse_args()
    start_time = time.time()

    if args.provider:
        config.AI_PROVIDER = args.provider.lower().strip()

    symbols = args.stocks if args.stocks else NIFTY_50

    use_finbert = args.finbert
    use_ai = args.ai
    use_llm_sentiment = (
        use_ai
        and config.AI_SENTIMENT_USE_LLM
        and bool(config.AI_PROVIDER)
    )

    def _write_symbol_report_csv(path: str, base_symbols: list[str], result: dict[str, list[str]]):
        rows = []
        status_map = {}
        for s in result.get("ok", []):
            status_map[s] = "ok"
        for s in result.get("missing", []):
            status_map[s] = "missing"
        for s in result.get("unreachable", []):
            status_map[s] = "unreachable"
        for s in base_symbols:
            rows.append({"symbol": s, "status": status_map.get(s, "unknown")})

        out_path = path
        if out_path.lower() == "auto":
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            out_path = f"reports/symbol_validation_{ts}.csv"
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["symbol", "status"])
            writer.writeheader()
            writer.writerows(rows)
        console.print(f"[green]Symbol validation CSV saved:[/] {os.path.abspath(out_path)}")

    provider_name = config.AI_PROVIDER
    ok, msg = check_market_data_auth()
    if not ok:
        console.print(f"[bold yellow][warn][/bold yellow] {msg}\n")

    if args.validate_symbols or args.drop_missing:
        console.print("[bold cyan]Symbol data validation[/bold cyan]")
        result = validate_symbols(symbols)
        ok_syms = result["ok"]
        missing_syms = result["missing"]
        bad_syms = result["unreachable"]

        console.print(
            f"[green]Valid:[/] {len(ok_syms)}  "
            f"[yellow]Missing:[/] {len(missing_syms)}  "
            f"[red]Unreachable/Error:[/] {len(bad_syms)}"
        )
        if missing_syms:
            console.print("[yellow]Missing symbols:[/] " + ", ".join(missing_syms))
        if bad_syms:
            console.print("[red]Unreachable/Error symbols:[/] " + ", ".join(bad_syms))
            console.print(
                "[dim]Hint: confirm NSE symbol spelling (e.g. M&M, BAJAJ-AUTO); "
                "install yfinance and jugaad-data.[/dim]"
            )
        if args.symbol_report_csv:
            _write_symbol_report_csv(args.symbol_report_csv, symbols, result)

        if args.validate_symbols:
            return

        if args.drop_missing:
            symbols = ok_syms
            if not symbols:
                console.print("[bold red]No valid symbols left after dropping missing/unreachable symbols.[/bold red]")
                return
            console.print(f"[green]Proceeding with {len(symbols)} valid symbols after drop.[/green]\n")

    print_header()
    print_disclaimer()

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 1: News Aggregation
    # ══════════════════════════════════════════════════════════════════════════
    market_news: list[NewsItem] = []
    world_news: list[NewsItem] = []
    stock_news: dict[str, list[NewsItem]] = {}

    if not args.skip_news:
        market_news = fetch_all_market_news()
        world_news = fetch_world_news()
        stock_news = fetch_stock_specific_news(symbols)

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 2: Sentiment Analysis
    # ══════════════════════════════════════════════════════════════════════════
    if use_llm_sentiment:
        console.print(
            f"[bold cyan]News sentiment:[/] LLM fast model "
            f"[dim]({config.resolve_ai_model('fast')})[/]\n"
        )
    elif use_ai and not config.AI_SENTIMENT_USE_LLM:
        console.print(
            "[dim]News sentiment: VADER/FinBERT "
            "(AI_SENTIMENT_USE_LLM=false in app.env)[/]\n"
        )

    market_sentiments = analyze_news_sentiment(
        market_news, use_finbert=use_finbert, use_llm=use_llm_sentiment,
    )
    market_sentiment_agg = aggregate_sentiment(market_sentiments)

    world_sentiments = analyze_news_sentiment(
        world_news, use_finbert=use_finbert, use_llm=use_llm_sentiment,
    )
    world_sentiment_agg = aggregate_sentiment(world_sentiments)

    stock_sentiment_aggs: dict[str, dict] = {}
    for sym in symbols:
        news_for_stock = stock_news.get(sym, [])
        if news_for_stock:
            results = analyze_news_sentiment(
                news_for_stock, use_finbert=use_finbert, use_llm=use_llm_sentiment,
            )
            stock_sentiment_aggs[sym] = aggregate_sentiment(results)
        else:
            stock_sentiment_aggs[sym] = aggregate_sentiment([])

    print_market_sentiment(market_sentiment_agg, world_sentiment_agg)

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 3 & 4: Fundamental + Technical Analysis
    # ══════════════════════════════════════════════════════════════════════════
    reset_fetch_reports()
    recommendations: list[Recommendation] = []
    fundamentals: dict[str, FundamentalData] = {}
    technicals: dict[str, TechnicalData] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing stocks...", total=len(symbols))

        for sym in symbols:
            fund_data = fetch_fundamentals(sym)
            tech_data = fetch_technical(sym)
            sent_agg = stock_sentiment_aggs.get(sym, aggregate_sentiment([]))

            if fund_data:
                fundamentals[sym] = fund_data
            if tech_data:
                technicals[sym] = tech_data

            rec = generate_recommendation(sym, sent_agg, fund_data, tech_data)
            recommendations.append(rec)

            progress.update(task, advance=1)

    console.print()
    md_summary, md_reports = build_market_data_report()
    print_market_data_fetch_report(md_summary, md_reports)

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 5: AI Deep Analysis (optional)
    # ══════════════════════════════════════════════════════════════════════════
    ai_insights: dict[str, AIInsight] = {}
    market_overview: MarketOverview | None = None
    ai_api_errors: list[str] = []

    if use_ai:
        console.print(
            f"[bold bright_magenta]AI provider: {provider_name.upper()}[/] "
            f"[dim](from --provider)[/]\n"
            f"[dim]Deep analysis: {config.resolve_ai_model('deep')} | "
            f"News sentiment: "
            f"{config.resolve_ai_model('fast') if use_llm_sentiment else 'VADER/FinBERT'}[/]\n"
        )
        market_overview, overview_err = generate_market_overview(
            recommendations, market_sentiment_agg, world_sentiment_agg,
            market_news, world_news,
        )
        if overview_err:
            ai_api_errors.append(f"Market overview: {overview_err}")
        elif market_overview:
            print_ai_market_overview(market_overview)

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold magenta]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task("AI analysis...", total=len(symbols))

            for rec in recommendations:
                sym = rec.symbol
                insight, err = analyze_stock_with_ai(
                    sym, rec,
                    fundamentals.get(sym),
                    technicals.get(sym),
                    stock_news.get(sym, []),
                    market_sentiment_agg,
                    world_sentiment_agg,
                )
                if err:
                    ai_api_errors.append(err)
                elif insight:
                    ai_insights[sym] = insight

                progress.update(task, advance=1)

        if ai_api_errors:
            preview = ai_api_errors[:20]
            body = "\n".join(preview)
            if len(ai_api_errors) > 20:
                body += f"\n… and {len(ai_api_errors) - 20} more error(s)."
            console.print(
                Panel(
                    body,
                    title="AI API errors (check model name, quota, billing, API key)",
                    border_style="red",
                    expand=False,
                )
            )

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 6: Generate Report
    # ══════════════════════════════════════════════════════════════════════════
    if args.top:
        sorted_recs = sorted(recommendations, key=lambda r: r.composite_score, reverse=True)
        top_n = sorted_recs[:args.top]
        bottom_n = sorted_recs[-args.top:]
        display_recs = list({r.symbol: r for r in (top_n + bottom_n)}.values())
        display_recs.sort(key=lambda r: r.composite_score, reverse=True)
        print_recommendation_summary(
            display_recs,
            include_ai_columns=use_ai,
            ai_insights=ai_insights if use_ai else None,
        )
    else:
        display_recs = recommendations
        print_recommendation_summary(
            recommendations,
            include_ai_columns=use_ai,
            ai_insights=ai_insights if use_ai else None,
        )

    print_buy_sell_hold_lists(recommendations)

    if args.detailed:
        console.print("[bold bright_white on blue]  DETAILED STOCK ANALYSIS  [/]\n")
        sorted_recs = sorted(recommendations, key=lambda r: r.composite_score, reverse=True)
        for rec in sorted_recs:
            print_detailed_stock_report(rec)
            if rec.symbol in ai_insights:
                print_ai_stock_insight(ai_insights[rec.symbol])
            console.print()

    if args.pdf:
        pdf_path = generate_pdf_report(
            output_path=args.pdf_file,
            recommendations=display_recs,
            market_sentiment=market_sentiment_agg,
            world_sentiment=world_sentiment_agg,
            market_news=market_news,
            world_news=world_news,
            ai_insights=ai_insights,
            market_overview=market_overview,
            market_data_summary=md_summary,
            market_data_reports=md_reports,
            show_ai_extended_columns=use_ai,
            ai_errors=ai_api_errors,
        )
        console.print(f"[bold green]PDF exported:[/] {pdf_path}")
        if not args.no_telegram:
            _send_pdf_to_telegram(pdf_path)

    # ── Timing ──
    elapsed = time.time() - start_time
    console.print(f"\n[dim]Analysis completed in {elapsed:.1f} seconds.[/dim]")
    print_footer()
    print_disclaimer()


if __name__ == "__main__":
    main()
