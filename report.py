"""
Rich console report generator for the Indian Market Stock Advisory System.
Produces beautiful, color-coded terminal output with tables and panels.
"""

from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.layout import Layout
from rich import box

from recommendation import Recommendation
from news_fetcher import NewsItem
from sentiment import SentimentResult
from ai_analyzer import AIInsight, MarketOverview


import sys, io, math
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

console = Console(width=140, force_terminal=True)


def _fmt_price(price) -> str:
    if price is None:
        return "N/A"
    try:
        f = float(price)
        if math.isnan(f) or math.isinf(f):
            return "N/A"
        return f"₹{f:,.2f}"
    except (TypeError, ValueError):
        return "N/A"


def _rec_color(rec: str) -> str:
    return {
        "STRONG BUY": "bold bright_green",
        "BUY": "green",
        "HOLD": "yellow",
        "SELL": "red",
        "STRONG SELL": "bold bright_red",
    }.get(rec, "white")


def _score_color(score: float) -> str:
    if score >= 70:
        return "bright_green"
    elif score >= 55:
        return "green"
    elif score >= 45:
        return "yellow"
    elif score >= 30:
        return "red"
    return "bright_red"


def _sentiment_color(label: str) -> str:
    return {"Bullish": "green", "Bearish": "red", "Neutral": "yellow"}.get(label, "white")


def print_header():
    header = Text()
    header.append("  INDIAN MARKET STOCK ADVISORY SYSTEM  ", style="bold white on blue")
    header.append("\n")
    header.append(f"  Report Generated: {datetime.now().strftime('%d %B %Y, %I:%M %p IST')}  ",
                  style="dim")
    console.print(Panel(header, border_style="blue", box=box.DOUBLE))
    console.print()


def print_market_sentiment(market_sentiment: dict, world_sentiment: dict):
    table = Table(title="Market & World Sentiment Overview",
                  box=box.ROUNDED, border_style="cyan", title_style="bold cyan")
    table.add_column("Category", style="bold", width=25)
    table.add_column("Sentiment", justify="center", width=12)
    table.add_column("Avg Score", justify="center", width=12)
    table.add_column("Bullish %", justify="center", width=10)
    table.add_column("Bearish %", justify="center", width=10)
    table.add_column("Neutral %", justify="center", width=10)
    table.add_column("Articles", justify="center", width=10)

    for label, data in [("Indian Market News", market_sentiment),
                        ("World / Global News", world_sentiment)]:
        sl = data.get("label", "Neutral")
        table.add_row(
            label,
            f"[{_sentiment_color(sl)}]{sl}[/]",
            f"[{_sentiment_color(sl)}]{data.get('avg_score', 0):.3f}[/]",
            f"{data.get('bullish_pct', 0):.0f}%",
            f"{data.get('bearish_pct', 0):.0f}%",
            f"{data.get('neutral_pct', 0):.0f}%",
            str(data.get("count", 0)),
        )
    console.print(table)
    console.print()


def print_top_news(news_items: list[NewsItem], title: str = "Top Market Headlines",
                   max_items: int = 10):
    table = Table(title=title, box=box.SIMPLE_HEAVY, border_style="blue",
                  title_style="bold blue")
    table.add_column("#", width=3, justify="right")
    table.add_column("Headline", width=80)
    table.add_column("Source", width=20)

    for i, item in enumerate(news_items[:max_items], 1):
        table.add_row(str(i), item.title[:80], item.source)

    console.print(table)
    console.print()


def print_recommendation_summary(recommendations: list[Recommendation]):
    table = Table(
        title="STOCK RECOMMENDATIONS SUMMARY",
        box=box.HEAVY_HEAD, border_style="bright_blue",
        title_style="bold bright_white on blue",
        caption="Scores: 0-100 | Weights: Sentiment 25%, Fundamental 40%, Technical 35%",
        caption_style="dim",
    )
    table.add_column("Symbol", style="bold", width=14)
    table.add_column("Price (₹)", justify="right", width=12)
    table.add_column("Sentiment", justify="center", width=10)
    table.add_column("Fund. Score", justify="center", width=11)
    table.add_column("Tech. Score", justify="center", width=11)
    table.add_column("Composite", justify="center", width=10)
    table.add_column("Recommendation", justify="center", width=14)
    table.add_column("Confidence", justify="center", width=10)
    table.add_column("Risk", justify="center", width=10)

    sorted_recs = sorted(recommendations, key=lambda r: r.composite_score, reverse=True)

    for rec in sorted_recs:
        table.add_row(
            rec.symbol,
            _fmt_price(rec.current_price),
            f"[{_sentiment_color(rec.sentiment_label)}]{rec.sentiment_label}[/]",
            f"[{_score_color(rec.fundamental_score)}]{rec.fundamental_score:.0f}[/]",
            f"[{_score_color(rec.technical_score)}]{rec.technical_score:.0f}[/]",
            f"[{_score_color(rec.composite_score)}]{rec.composite_score:.0f}[/]",
            f"[{_rec_color(rec.recommendation)}]{rec.recommendation}[/]",
            rec.confidence,
            rec.risk_level,
        )

    console.print(table)
    console.print()


def print_detailed_stock_report(rec: Recommendation):
    """Print a detailed panel for a single stock."""
    title = f"{rec.symbol} — {rec.company_name}"
    subtitle = f"Sector: {rec.sector}"

    content = Text()
    content.append(f"Current Price: {_fmt_price(rec.current_price)}\n", style="bold")
    content.append(f"Recommendation: ", style="dim")
    content.append(f"{rec.recommendation}", style=_rec_color(rec.recommendation))
    content.append(f"  |  Confidence: {rec.confidence}  |  Risk: {rec.risk_level}\n\n")

    content.append("── Scores ──\n", style="bold underline")
    content.append(f"  Sentiment:   {rec.sentiment_score:5.1f}/100  ({rec.sentiment_label})\n")
    content.append(f"  Fundamental: {rec.fundamental_score:5.1f}/100  ({rec.fundamental_rating})\n")
    content.append(f"  Technical:   {rec.technical_score:5.1f}/100  ({rec.technical_rating})\n")
    content.append(f"  Composite:   {rec.composite_score:5.1f}/100\n\n")

    if rec.bull_case:
        content.append("── Bull Case ──\n", style="bold green")
        for point in rec.bull_case:
            content.append(f"  + {point}\n", style="green")
        content.append("\n")

    if rec.bear_case:
        content.append("── Bear Case ──\n", style="bold red")
        for point in rec.bear_case:
            content.append(f"  - {point}\n", style="red")
        content.append("\n")

    if rec.key_levels:
        content.append("── Key Levels ──\n", style="bold cyan")
        for level_name, level_val in rec.key_levels.items():
            content.append(f"  {level_name}: {_fmt_price(level_val)}\n", style="cyan")

    border = "green" if rec.composite_score >= 60 else (
        "red" if rec.composite_score < 40 else "yellow"
    )
    console.print(Panel(content, title=title, subtitle=subtitle,
                        border_style=border, box=box.ROUNDED))


def print_buy_sell_hold_lists(recommendations: list[Recommendation]):
    sorted_recs = sorted(recommendations, key=lambda r: r.composite_score, reverse=True)

    buys = [r for r in sorted_recs if r.recommendation in ("STRONG BUY", "BUY")]
    holds = [r for r in sorted_recs if r.recommendation == "HOLD"]
    sells = [r for r in sorted_recs if r.recommendation in ("SELL", "STRONG SELL")]

    def _make_table(title, recs, color):
        t = Table(title=title, box=box.ROUNDED, border_style=color, title_style=f"bold {color}")
        t.add_column("Symbol", style="bold", width=14)
        t.add_column("Price (₹)", justify="right", width=12)
        t.add_column("Score", justify="center", width=8)
        t.add_column("Confidence", justify="center", width=10)
        for r in recs:
            t.add_row(r.symbol, _fmt_price(r.current_price),
                      f"[{_score_color(r.composite_score)}]{r.composite_score:.0f}[/]",
                      r.confidence)
        return t

    if buys:
        console.print(_make_table(f"BUY LIST ({len(buys)} stocks)", buys, "green"))
    if holds:
        console.print(_make_table(f"HOLD LIST ({len(holds)} stocks)", holds, "yellow"))
    if sells:
        console.print(_make_table(f"SELL LIST ({len(sells)} stocks)", sells, "red"))
    console.print()


def print_disclaimer():
    disclaimer = (
        "[bold red]DISCLAIMER:[/bold red] This is an automated analysis tool for "
        "educational purposes only. It does NOT constitute financial advice. "
        "Always consult a SEBI-registered financial advisor before making "
        "investment decisions. Past performance does not guarantee future results. "
        "The authors are not responsible for any financial losses."
    )
    console.print(Panel(disclaimer, border_style="red", box=box.DOUBLE,
                        title="[!] Important", title_align="left"))
    console.print()


def print_ai_market_overview(overview: MarketOverview):
    """Print AI-generated market overview panel."""
    content = Text()
    provider_label = "Claude (Anthropic)" if overview.provider == "anthropic" else "GPT (OpenAI)"

    content.append(f"AI Provider: {provider_label}\n\n", style="dim italic")

    content.append("── Overall Outlook ──\n", style="bold bright_white")
    content.append(f"  {overview.overall_outlook}\n\n")

    content.append("── Nifty 50 View ──\n", style="bold bright_white")
    content.append(f"  {overview.nifty_view}\n\n")

    content.append("── Global Impact ──\n", style="bold bright_white")
    content.append(f"  {overview.global_impact}\n\n")

    content.append("── Sector Rotation ──\n", style="bold bright_white")
    content.append(f"  {overview.sector_rotation}\n\n")

    if overview.top_picks:
        content.append("── AI Top Picks ──\n", style="bold green")
        content.append(f"  {', '.join(overview.top_picks)}\n\n", style="green")

    if overview.avoid_list:
        content.append("── Avoid / Underweight ──\n", style="bold red")
        content.append(f"  {', '.join(overview.avoid_list)}\n\n", style="red")

    content.append("── Strategy Advice ──\n", style="bold cyan")
    content.append(f"  {overview.strategy_advice}\n", style="cyan")

    console.print(Panel(
        content,
        title="AI MARKET OVERVIEW & STRATEGY",
        title_align="center",
        border_style="bright_magenta",
        box=box.DOUBLE,
    ))
    console.print()


def print_ai_stock_insight(insight: AIInsight):
    """Print AI-generated stock insight panel."""
    provider_label = "Claude" if insight.provider == "anthropic" else "GPT"
    content = Text()

    content.append(f"AI Recommendation: ", style="bold")
    content.append(f"{insight.ai_recommendation}",
                   style=_rec_color(insight.ai_recommendation))
    content.append(f"  (by {provider_label})\n", style="dim")

    if insight.target_price:
        content.append(f"Target Price: ₹{insight.target_price}\n", style="bold bright_green")
    if insight.stop_loss:
        content.append(f"Stop Loss: ₹{insight.stop_loss}\n", style="bold red")
    content.append(f"Time Horizon: {insight.time_horizon}\n\n", style="dim")

    content.append("── Investment Thesis ──\n", style="bold bright_white underline")
    content.append(f"  {insight.investment_thesis}\n\n")

    if insight.key_catalysts:
        content.append("── Key Catalysts ──\n", style="bold green")
        for c in insight.key_catalysts:
            content.append(f"  + {c}\n", style="green")
        content.append("\n")

    if insight.key_risks:
        content.append("── Key Risks ──\n", style="bold red")
        for r in insight.key_risks:
            content.append(f"  - {r}\n", style="red")
        content.append("\n")

    if insight.sector_view:
        content.append("── Sector View ──\n", style="bold cyan")
        content.append(f"  {insight.sector_view}\n\n", style="cyan")

    if insight.confidence_rationale:
        content.append("── Confidence ──\n", style="bold yellow")
        content.append(f"  {insight.confidence_rationale}\n", style="yellow")

    color = _rec_color(insight.ai_recommendation).split()[-1]
    console.print(Panel(
        content,
        title=f"AI DEEP ANALYSIS — {insight.symbol}",
        border_style="bright_magenta",
        box=box.ROUNDED,
    ))


def print_ai_comparison_table(recommendations: list[Recommendation],
                              ai_insights: dict[str, AIInsight]):
    """Show side-by-side comparison of algorithmic vs AI recommendations."""
    if not ai_insights:
        return

    table = Table(
        title="ALGO vs AI RECOMMENDATIONS",
        box=box.HEAVY_HEAD, border_style="bright_magenta",
        title_style="bold bright_white on dark_magenta",
    )
    table.add_column("Symbol", style="bold", width=14)
    table.add_column("Price (₹)", justify="right", width=12)
    table.add_column("Algo Rec", justify="center", width=12)
    table.add_column("AI Rec", justify="center", width=12)
    table.add_column("Target", justify="right", width=12)
    table.add_column("Stop Loss", justify="right", width=12)
    table.add_column("Horizon", justify="center", width=16)
    table.add_column("Agreement", justify="center", width=10)

    sorted_recs = sorted(recommendations, key=lambda r: r.composite_score, reverse=True)
    for rec in sorted_recs:
        insight = ai_insights.get(rec.symbol)
        if not insight:
            continue
        price = _fmt_price(rec.current_price)
        target = f"₹{insight.target_price}" if insight.target_price else "—"
        sl = f"₹{insight.stop_loss}" if insight.stop_loss else "—"

        algo_base = rec.recommendation.replace("STRONG ", "S.")
        ai_base = insight.ai_recommendation.replace("STRONG ", "S.")
        agree = "Yes" if algo_base == ai_base else "No"
        agree_style = "green" if agree == "Yes" else "bright_red"

        table.add_row(
            rec.symbol, price,
            f"[{_rec_color(rec.recommendation)}]{rec.recommendation}[/]",
            f"[{_rec_color(insight.ai_recommendation)}]{insight.ai_recommendation}[/]",
            target, sl, insight.time_horizon,
            f"[{agree_style}]{agree}[/]",
        )

    console.print(table)
    console.print()


def print_footer():
    console.print(
        "[dim]Powered by: OpenAlgo (broker data), pandas_ta, VADER/FinBERT, Anthropic Claude / OpenAI GPT, "
        "Google News RSS, Zerodha Pulse, ET Markets, MoneyControl, LiveMint[/dim]"
    )
    console.print("[dim]Data may be delayed. Use at your own risk.[/dim]")
