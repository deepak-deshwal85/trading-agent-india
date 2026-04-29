"""
Indian Market Stock Advisory System
====================================
Aggregates news from 10+ sources, performs sentiment / fundamental / technical
analysis on Nifty 50 stocks, and uses AI (Claude / GPT) for expert-level
investment recommendations.

Usage:
    python main.py                                  # Analyze all Nifty 50 (VADER, no AI)
    python main.py --stocks RELIANCE INFY TCS       # Specific stocks
    python main.py --ai                             # Enable AI deep analysis
    python main.py --ai --provider openai            # Use OpenAI instead
    python main.py --ai --detailed                   # AI + detailed per-stock panels
    python main.py --top 10                          # Show top/bottom 10 only
    python main.py --finbert                         # FinBERT sentiment model
"""

import argparse
import time
import os

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from config import NIFTY_50, AI_PROVIDER
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
from report import (
    console, print_header, print_market_sentiment,
    print_top_news, print_recommendation_summary,
    print_detailed_stock_report, print_buy_sell_hold_lists,
    print_disclaimer, print_footer,
    print_ai_market_overview, print_ai_stock_insight,
    print_ai_comparison_table,
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
        help="Use FinBERT model for sentiment (slower, more accurate).",
    )
    parser.add_argument(
        "--ai", action="store_true",
        help="Enable AI-powered deep analysis (uses API key from .env).",
    )
    parser.add_argument(
        "--provider", type=str, default=None, choices=["anthropic", "openai"],
        help="Override AI_PROVIDER from .env (e.g., --provider openai).",
    )
    parser.add_argument(
        "--detailed", action="store_true",
        help="Print detailed analysis panel for each stock.",
    )
    parser.add_argument(
        "--skip-news", action="store_true",
        help="Skip news fetching (faster re-runs for testing).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    start_time = time.time()

    # Override AI provider if specified via CLI
    if args.provider:
        import config
        config.AI_PROVIDER = args.provider
        os.environ["AI_PROVIDER"] = args.provider
        import ai_analyzer
        ai_analyzer.AI_PROVIDER = args.provider  # noqa — runtime override

    symbols = args.stocks if args.stocks else NIFTY_50
    use_finbert = args.finbert
    use_ai = args.ai

    provider_name = args.provider or AI_PROVIDER
    if use_ai:
        console.print(f"[bold bright_magenta]AI Mode: ON  |  Provider: {provider_name.upper()}[/]\n")

    print_header()
    print_disclaimer()

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 1: News Aggregation
    # ══════════════════════════════════════════════════════════════════════════
    market_news: list[NewsItem] = []
    world_news: list[NewsItem] = []
    stock_news: dict[str, list[NewsItem]] = {}

    if not args.skip_news:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching market news...", total=3)

            console.print("[dim]  Fetching Indian market news from all sources...[/dim]")
            market_news = fetch_all_market_news()
            progress.update(task, advance=1)

            console.print("[dim]  Fetching world/global news...[/dim]")
            world_news = fetch_world_news()
            progress.update(task, advance=1)

            console.print(f"[dim]  Fetching stock-specific news for {len(symbols)} stocks...[/dim]")
            stock_news = fetch_stock_specific_news(symbols)
            progress.update(task, advance=1)

        console.print(
            f"[green]  Collected {len(market_news)} market articles, "
            f"{len(world_news)} world articles, "
            f"stock-specific news for {len(stock_news)} stocks[/green]\n"
        )

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 2: Sentiment Analysis
    # ══════════════════════════════════════════════════════════════════════════
    console.print("[bold cyan]Phase 2: Sentiment Analysis[/bold cyan]")
    mode_label = "FinBERT" if use_finbert else "VADER"
    console.print(f"[dim]  Using {mode_label} model...[/dim]")

    market_sentiments = analyze_news_sentiment(market_news, use_finbert=use_finbert)
    market_sentiment_agg = aggregate_sentiment(market_sentiments)

    world_sentiments = analyze_news_sentiment(world_news, use_finbert=use_finbert)
    world_sentiment_agg = aggregate_sentiment(world_sentiments)

    stock_sentiment_aggs: dict[str, dict] = {}
    for sym in symbols:
        news_for_stock = stock_news.get(sym, [])
        if news_for_stock:
            results = analyze_news_sentiment(news_for_stock, use_finbert=use_finbert)
            stock_sentiment_aggs[sym] = aggregate_sentiment(results)
        else:
            stock_sentiment_aggs[sym] = aggregate_sentiment([])

    print_market_sentiment(market_sentiment_agg, world_sentiment_agg)

    if market_news:
        print_top_news(market_news, title="Top Indian Market Headlines", max_items=8)
    if world_news:
        print_top_news(world_news, title="Top World News Impacting Markets", max_items=5)

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 3 & 4: Fundamental + Technical Analysis
    # ══════════════════════════════════════════════════════════════════════════
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
        task = progress.add_task(
            "Analyzing stocks (fundamentals + technicals)...", total=len(symbols)
        )

        for sym in symbols:
            progress.update(task, description=f"Analyzing {sym}...")

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

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 5: AI Deep Analysis (optional)
    # ══════════════════════════════════════════════════════════════════════════
    ai_insights: dict[str, AIInsight] = {}
    market_overview: MarketOverview | None = None

    if use_ai:
        console.print("[bold bright_magenta]Phase 5: AI Deep Analysis[/bold bright_magenta]")
        console.print(f"[dim]  Sending data to {provider_name.upper()} for expert analysis...[/dim]\n")

        # Market overview first
        console.print("[dim]  Generating AI market overview...[/dim]")
        market_overview = generate_market_overview(
            recommendations, market_sentiment_agg, world_sentiment_agg,
            market_news, world_news,
        )
        if market_overview:
            print_ai_market_overview(market_overview)

        # Per-stock AI analysis
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold magenta]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "AI analyzing stocks...", total=len(symbols)
            )

            for rec in recommendations:
                sym = rec.symbol
                progress.update(task, description=f"AI analyzing {sym}...")

                insight = analyze_stock_with_ai(
                    sym, rec,
                    fundamentals.get(sym),
                    technicals.get(sym),
                    stock_news.get(sym, []),
                    market_sentiment_agg,
                    world_sentiment_agg,
                )
                if insight:
                    ai_insights[sym] = insight

                progress.update(task, advance=1)

        console.print(f"\n[green]  AI analysis complete for {len(ai_insights)}/{len(symbols)} stocks[/green]\n")

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 6: Generate Report
    # ══════════════════════════════════════════════════════════════════════════
    if args.top:
        sorted_recs = sorted(recommendations, key=lambda r: r.composite_score, reverse=True)
        top_n = sorted_recs[:args.top]
        bottom_n = sorted_recs[-args.top:]
        display_recs = list({r.symbol: r for r in (top_n + bottom_n)}.values())
        display_recs.sort(key=lambda r: r.composite_score, reverse=True)
        print_recommendation_summary(display_recs)
    else:
        print_recommendation_summary(recommendations)

    if ai_insights:
        print_ai_comparison_table(recommendations, ai_insights)

    print_buy_sell_hold_lists(recommendations)

    if args.detailed:
        console.print("[bold bright_white on blue]  DETAILED STOCK ANALYSIS  [/]\n")
        sorted_recs = sorted(recommendations, key=lambda r: r.composite_score, reverse=True)
        for rec in sorted_recs:
            print_detailed_stock_report(rec)
            if rec.symbol in ai_insights:
                print_ai_stock_insight(ai_insights[rec.symbol])
            console.print()

    # ── Timing ──
    elapsed = time.time() - start_time
    console.print(f"\n[dim]Analysis completed in {elapsed:.1f} seconds.[/dim]")
    print_footer()
    print_disclaimer()


if __name__ == "__main__":
    main()
