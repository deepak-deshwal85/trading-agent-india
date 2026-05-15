"""
PDF report generator for Indian Market Stock Advisory System.
Creates a modern, structured PDF mirroring console output.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.lineplots import LinePlot

from market_data import (
    fetch_daily_history,
    MarketDataReportSummary,
    SymbolFetchReport,
    get_reports_with_fetch_issues,
)

from recommendation import Recommendation
from news_fetcher import NewsItem
from ai_analyzer import AIInsight, MarketOverview


BRAND_NAME = "Trading Agent India"
BRAND_PRIMARY = colors.HexColor("#1D4ED8")
BRAND_ACCENT = colors.HexColor("#0EA5E9")


def _fmt_price(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    try:
        f = float(value)
        if f != f:
            return "N/A"
        return f"INR {f:,.2f}"
    except Exception:
        return "N/A"


def _pdf_match_algo_ai(rec: Recommendation, ins: AIInsight | None) -> str:
    if ins is None:
        return "—"
    a = rec.recommendation.replace("STRONG ", "S.")
    b = ins.ai_recommendation.replace("STRONG ", "S.")
    return "Yes" if a == b else "No"


def _pdf_short_rec(label: str) -> str:
    return label.replace("STRONG ", "S.")


def _fmt_price_compact(value: Optional[float]) -> str:
    if value is None:
        return "—"
    try:
        f = float(value)
        if f != f:
            return "—"
        return f"₹{f:,.2f}"
    except Exception:
        return "—"


def _pdf_fmt_ai_price(value: Optional[str]) -> str:
    if value is None:
        return "—"
    raw = str(value).strip()
    if not raw or raw.lower() in ("null", "none", "n/a"):
        return "—"
    cleaned = raw.replace("₹", "").replace("INR", "").replace(",", "").strip()
    try:
        return f"₹{float(cleaned):,.0f}"
    except ValueError:
        return raw[:14] + ("…" if len(raw) > 14 else "")


def _pdf_horizon_short(horizon: Optional[str]) -> str:
    if not horizon:
        return "—"
    h = horizon.lower()
    if "short" in h:
        return "Short\n(1–3 mo)"
    if "long" in h:
        return "Long\n(1 yr+)"
    if "medium" in h:
        return "Med\n(3–12 mo)"
    return horizon[:16] + ("…" if len(horizon) > 16 else "")


def _stock_rec_col_widths(has_ai: bool, total_w: float) -> list[float]:
    """Proportional widths so Symbol/Price/Horizon don't steal space from narrow score cols."""
    if has_ai:
        weights = (
            1.15, 1.20, 0.95, 0.48, 0.48, 0.48,
            0.68, 0.62, 1.05, 1.00, 0.82, 0.82, 1.55, 0.42,
        )
    else:
        weights = (1.20, 1.25, 1.00, 0.52, 0.52, 0.52, 0.78, 0.72, 1.10)
    scale = total_w / sum(weights)
    return [w * scale for w in weights]


def _pdf_rec_table_styles(base_styles) -> tuple[ParagraphStyle, ParagraphStyle, ParagraphStyle, ParagraphStyle]:
    cell = ParagraphStyle(
        "PdfRecCell",
        parent=base_styles["Normal"],
        fontSize=6,
        leading=7,
        wordWrap="CJK",
    )
    cell_left = ParagraphStyle("PdfRecCellL", parent=cell, alignment=TA_LEFT)
    cell_center = ParagraphStyle("PdfRecCellC", parent=cell, alignment=TA_CENTER)
    hdr = ParagraphStyle(
        "PdfRecHdr",
        parent=cell_center,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )
    return hdr, cell_left, cell_center


def _pdf_table_cell(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def _section_title(text: str, styles):
    return Paragraph(text, styles["Heading2"])


def _fetch_recent_closes(symbol: str, days: int = 30) -> list[float]:
    try:
        hist = fetch_daily_history(symbol, days=max(days + 5, 45))
        if hist is None or hist.empty or "Close" not in hist.columns:
            return []
        closes = [float(v) for v in hist["Close"].dropna().tail(days).tolist()]
        return closes
    except Exception:
        return []


def _sparkline_chart(symbol: str) -> Drawing:
    drawing = Drawing(250, 90)
    data = _fetch_recent_closes(symbol, days=30)
    drawing.add(String(0, 78, f"{symbol} - 30D Trend", fontName="Helvetica-Bold", fontSize=8))

    if len(data) < 2:
        drawing.add(String(0, 40, "Price data unavailable", fontName="Helvetica", fontSize=8, fillColor=colors.grey))
        return drawing

    min_v = min(data)
    max_v = max(data)
    spread = max(max_v - min_v, 1e-6)
    points = [(i, (v - min_v) / spread * 100.0) for i, v in enumerate(data)]

    lp = LinePlot()
    lp.x = 8
    lp.y = 15
    lp.height = 55
    lp.width = 220
    lp.data = [points]
    lp.xValueAxis.valueMin = 0
    lp.xValueAxis.valueMax = max(len(data) - 1, 1)
    lp.xValueAxis.visible = False
    lp.yValueAxis.valueMin = 0
    lp.yValueAxis.valueMax = 100
    lp.yValueAxis.visible = False
    lp.lines[0].strokeColor = BRAND_PRIMARY
    lp.lines[0].strokeWidth = 1.6
    drawing.add(lp)
    drawing.add(String(170, 5, f"{data[-1]:.2f}", fontName="Helvetica", fontSize=7, fillColor=colors.grey))
    return drawing


def _sentiment_pie(title: str, bullish: float, bearish: float, neutral: float) -> Drawing:
    drawing = Drawing(250, 180)
    drawing.add(String(10, 165, title, fontName="Helvetica-Bold", fontSize=11))
    pie = Pie()
    pie.x = 40
    pie.y = 20
    pie.width = 140
    pie.height = 130
    pie.data = [max(0, bullish), max(0, bearish), max(0, neutral)]
    pie.labels = [f"Bullish {bullish:.0f}%", f"Bearish {bearish:.0f}%", f"Neutral {neutral:.0f}%"]
    pie.slices.strokeWidth = 0.5
    pie.slices[0].fillColor = colors.HexColor("#16A34A")
    pie.slices[1].fillColor = colors.HexColor("#DC2626")
    pie.slices[2].fillColor = colors.HexColor("#F59E0B")
    pie.sideLabels = True
    drawing.add(pie)
    return drawing


def _score_bar_chart(recommendations: list[Recommendation]) -> Drawing:
    top = sorted(recommendations, key=lambda r: r.composite_score, reverse=True)[:8]
    labels = [r.symbol for r in top]
    vals = [round(r.composite_score, 1) for r in top]

    drawing = Drawing(500, 230)
    drawing.add(String(10, 210, "Top Composite Scores", fontName="Helvetica-Bold", fontSize=11))
    bc = VerticalBarChart()
    bc.x = 35
    bc.y = 35
    bc.height = 150
    bc.width = 430
    bc.data = [vals or [0]]
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = 100
    bc.valueAxis.valueStep = 20
    bc.categoryAxis.categoryNames = labels or ["-"]
    bc.categoryAxis.labels.angle = 30
    bc.categoryAxis.labels.dy = -12
    bc.bars[0].fillColor = colors.HexColor("#2563EB")
    bc.bars[0].strokeColor = colors.HexColor("#1E40AF")
    drawing.add(bc)
    return drawing


def _recommendation_distribution_chart(recommendations: list[Recommendation]) -> Drawing:
    buckets = {"BUY": 0, "HOLD": 0, "SELL": 0}
    for r in recommendations:
        if "BUY" in r.recommendation:
            buckets["BUY"] += 1
        elif "SELL" in r.recommendation:
            buckets["SELL"] += 1
        else:
            buckets["HOLD"] += 1

    drawing = Drawing(350, 220)
    drawing.add(String(10, 200, "Recommendation Mix", fontName="Helvetica-Bold", fontSize=11))
    pie = Pie()
    pie.x = 50
    pie.y = 20
    pie.width = 180
    pie.height = 160
    pie.data = [buckets["BUY"], buckets["HOLD"], buckets["SELL"]]
    pie.labels = [f"Buy {buckets['BUY']}", f"Hold {buckets['HOLD']}", f"Sell {buckets['SELL']}"]
    pie.slices[0].fillColor = colors.HexColor("#22C55E")
    pie.slices[1].fillColor = colors.HexColor("#FACC15")
    pie.slices[2].fillColor = colors.HexColor("#EF4444")
    pie.sideLabels = True
    drawing.add(pie)
    return drawing


def _draw_page_chrome(canvas, doc):
    canvas.saveState()
    width, height = A4

    # Header line + branding
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.setLineWidth(0.5)
    canvas.line(1.5 * cm, height - 1.15 * cm, width - 1.5 * cm, height - 1.15 * cm)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(BRAND_PRIMARY)
    canvas.drawString(1.5 * cm, height - 0.9 * cm, BRAND_NAME)
    canvas.setFillColor(colors.HexColor("#334155"))
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - 1.5 * cm, height - 0.9 * cm, datetime.now().strftime("%d %b %Y"))

    # Footer line + page number
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.setLineWidth(0.5)
    canvas.line(1.5 * cm, 1.15 * cm, width - 1.5 * cm, 1.15 * cm)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.setFont("Helvetica", 8)
    canvas.drawString(1.5 * cm, 0.85 * cm, "Automated market intelligence report")
    canvas.drawRightString(width - 1.5 * cm, 0.85 * cm, f"Page {doc.page}")
    canvas.restoreState()


def _market_data_outcome_label(r: SymbolFetchReport) -> str:
    if r.both_failed:
        return "FAILED (both)"
    if r.resolved_source == "jugaad-data":
        return "Recovered (jugaad)"
    return r.resolved_source or "—"


def _market_data_report_section(
    summary: MarketDataReportSummary | None,
    reports: list[SymbolFetchReport] | None,
    styles,
) -> list:
    """PDF block: summary counts + table of yfinance/jugaad issues only."""
    if not reports:
        return []

    summary = summary or MarketDataReportSummary(total=len(reports))
    issues = get_reports_with_fetch_issues()

    elements = [
        _section_title("Market Data Issues (yfinance / jugaad-data)", styles),
        Paragraph(
            f"Symbols analyzed: {summary.total}. "
            f"yfinance OK: {summary.ok_yfinance}. "
            f"jugaad fallback used: {summary.ok_jugaad}. "
            f"Both failed: {summary.both_failed}.",
            styles["Normal"],
        ),
        Spacer(1, 8),
    ]

    if not issues:
        elements.append(Paragraph(
            "No yfinance or jugaad-data failures — all symbols fetched cleanly.",
            styles["Normal"],
        ))
        elements.append(Spacer(1, 12))
        return elements

    issue_data = [["Symbol", "Outcome", "yfinance", "jugaad-data"]]
    for r in issues:
        issue_data.append([
            r.symbol,
            _market_data_outcome_label(r),
            r.yfinance.summary()[:100],
            r.jugaad.summary()[:100],
        ])
    issue_tbl = Table(issue_data, repeatRows=1, colWidths=[2 * cm, 2.5 * cm, 5.5 * cm, 5.5 * cm])
    issue_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#B45309")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(issue_tbl)
    elements.append(Spacer(1, 12))
    return elements


def generate_pdf_report(
    output_path: str,
    recommendations: list[Recommendation],
    market_sentiment: dict,
    world_sentiment: dict,
    market_news: list[NewsItem],
    world_news: list[NewsItem],
    ai_insights: dict[str, AIInsight],
    market_overview: MarketOverview | None,
    market_data_summary: MarketDataReportSummary | None = None,
    market_data_reports: list[SymbolFetchReport] | None = None,
    show_ai_extended_columns: bool = False,
    ai_errors: list[str] | None = None,
) -> str:
    """Generate a polished PDF report and return absolute path."""
    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    ai_errors = ai_errors or []

    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Indian Market Advisory Report",
        author="Trading Agent India",
    )

    styles = getSampleStyleSheet()
    styles["Title"].textColor = BRAND_PRIMARY
    styles.add(ParagraphStyle(name="Meta", parent=styles["Normal"], textColor=colors.grey))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=9, leading=12))
    styles["Heading2"].textColor = colors.HexColor("#0F172A")

    story = []
    # Branded cover
    story.append(Spacer(1, 1.2 * cm))
    story.append(Paragraph("Indian Market Stock Advisory Report", styles["Title"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"By {BRAND_NAME}", styles["Heading4"]))
    story.append(Spacer(1, 2))
    story.append(Paragraph(datetime.now().strftime("Generated on %d %B %Y, %I:%M %p"), styles["Meta"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("<b>Logo Placeholder:</b> Add your brand logo at top-right in future customization.", styles["Small"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "This report combines multi-source market news, sentiment, fundamentals, technical indicators, and AI synthesis.",
        styles["Normal"],
    ))
    story.append(Spacer(1, 16))

    story.append(_section_title("Market Sentiment Overview", styles))
    sent_tbl = Table([
        ["Category", "Sentiment", "Avg Score", "Bullish%", "Bearish%", "Neutral%", "Articles"],
        [
            "Indian Market News",
            str(market_sentiment.get("label", "Neutral")),
            f"{market_sentiment.get('avg_score', 0):.3f}",
            f"{market_sentiment.get('bullish_pct', 0)}",
            f"{market_sentiment.get('bearish_pct', 0)}",
            f"{market_sentiment.get('neutral_pct', 0)}",
            f"{market_sentiment.get('count', 0)}",
        ],
        [
            "World / Global News",
            str(world_sentiment.get("label", "Neutral")),
            f"{world_sentiment.get('avg_score', 0):.3f}",
            f"{world_sentiment.get('bullish_pct', 0)}",
            f"{world_sentiment.get('bearish_pct', 0)}",
            f"{world_sentiment.get('neutral_pct', 0)}",
            f"{world_sentiment.get('count', 0)}",
        ],
    ], repeatRows=1)
    sent_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
    ]))
    story.append(sent_tbl)
    story.append(Spacer(1, 14))
    story.extend(_market_data_report_section(market_data_summary, market_data_reports, styles))
    story.append(_section_title("Visual Snapshot", styles))
    story.append(_sentiment_pie(
        "Indian Market Sentiment",
        float(market_sentiment.get("bullish_pct", 0)),
        float(market_sentiment.get("bearish_pct", 0)),
        float(market_sentiment.get("neutral_pct", 0)),
    ))
    story.append(Spacer(1, 8))
    story.append(_score_bar_chart(recommendations))
    story.append(Spacer(1, 8))
    story.append(_recommendation_distribution_chart(recommendations))
    story.append(Spacer(1, 10))

    story.append(_section_title("Top Headlines", styles))
    story.append(Paragraph("Indian Market", styles["Heading4"]))
    for item in market_news[:8]:
        if item.url:
            text = f'• <link href="{item.url}">{item.title}</link> <font color="#64748B">({item.source})</font>'
        else:
            text = f"• {item.title} ({item.source})"
        story.append(Paragraph(text, styles["Small"]))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Global Market", styles["Heading4"]))
    for item in world_news[:5]:
        if item.url:
            text = f'• <link href="{item.url}">{item.title}</link> <font color="#64748B">({item.source})</font>'
        else:
            text = f"• {item.title} ({item.source})"
        story.append(Paragraph(text, styles["Small"]))
    story.append(PageBreak())

    if market_overview:
        story.append(_section_title("AI Market Strategy", styles))
        story.append(Paragraph(f"Provider: {market_overview.provider.upper()}", styles["Meta"]))
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"<b>Overall Outlook:</b> {market_overview.overall_outlook}", styles["Normal"]))
        story.append(Paragraph(f"<b>Nifty View:</b> {market_overview.nifty_view}", styles["Normal"]))
        story.append(Paragraph(f"<b>Global Impact:</b> {market_overview.global_impact}", styles["Normal"]))
        story.append(Paragraph(f"<b>Sector Rotation:</b> {market_overview.sector_rotation}", styles["Normal"]))
        if market_overview.top_picks:
            story.append(Paragraph(f"<b>Top Picks:</b> {', '.join(market_overview.top_picks)}", styles["Normal"]))
        if market_overview.avoid_list:
            story.append(Paragraph(f"<b>Avoid List:</b> {', '.join(market_overview.avoid_list)}", styles["Normal"]))
        story.append(Paragraph(f"<b>Strategy:</b> {market_overview.strategy_advice}", styles["Normal"]))
        story.append(Spacer(1, 12))

    if ai_errors:
        story.append(_section_title("AI API errors", styles))
        truncated = []
        for e in ai_errors[:35]:
            s = escape(str(e))
            if len(s) > 400:
                s = s[:400] + "…"
            truncated.append(s)
        story.append(Paragraph("<br/>".join(truncated), styles["Small"]))
        story.append(Spacer(1, 10))

    story.append(_section_title("Stock Recommendations", styles))
    story.append(Paragraph(
        "Same column layout as console summary: scores, confidence, risk, algo vs AI when --ai is used.",
        styles["Small"],
    ))
    story.append(Spacer(1, 4))
    sorted_recs = sorted(recommendations, key=lambda r: r.composite_score, reverse=True)

    header = [
        "Symbol", "Price", "Sent.", "Fund", "Tech", "Comp.",
        "Conf.", "Risk", "Algo\nRec",
    ]
    if show_ai_extended_columns:
        header.extend(["AI\nRec", "Target", "Stop", "Horizon", "Mtch"])

    usable_w = A4[0] - doc.leftMargin - doc.rightMargin
    col_widths = _stock_rec_col_widths(show_ai_extended_columns, usable_w)
    hdr_style, cell_left, cell_center = _pdf_rec_table_styles(styles)

    rec_data = [[_pdf_table_cell(h, hdr_style) for h in header]]

    for rec in sorted_recs:
        ins = ai_insights.get(rec.symbol) if show_ai_extended_columns else None
        texts = [
            rec.symbol,
            _fmt_price_compact(rec.current_price),
            rec.sentiment_label,
            f"{rec.fundamental_score:.0f}",
            f"{rec.technical_score:.0f}",
            f"{rec.composite_score:.0f}",
            rec.confidence,
            rec.risk_level,
            _pdf_short_rec(rec.recommendation),
        ]
        if show_ai_extended_columns:
            if ins:
                texts.extend([
                    _pdf_short_rec(ins.ai_recommendation),
                    _pdf_fmt_ai_price(ins.target_price),
                    _pdf_fmt_ai_price(ins.stop_loss),
                    _pdf_horizon_short(ins.time_horizon),
                    _pdf_match_algo_ai(rec, ins),
                ])
            else:
                texts.extend(["—", "—", "—", "—", "—"])
        row = [_pdf_table_cell(t, cell_left if i == 0 else cell_center) for i, t in enumerate(texts)]
        rec_data.append(row)

    rec_tbl = Table(rec_data, repeatRows=1, colWidths=col_widths)
    rec_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(rec_tbl)
    story.append(Spacer(1, 12))

    story.append(_section_title("Detailed Stock Notes", styles))
    for rec in sorted_recs:
        story.append(Paragraph(
            f"<b>{rec.symbol}</b> ({rec.sector}) - {rec.recommendation} | Score: {rec.composite_score:.1f}",
            styles["Heading4"],
        ))
        story.append(Paragraph(f"Price: {_fmt_price(rec.current_price)}", styles["Small"]))
        story.append(_sparkline_chart(rec.symbol))
        story.append(Spacer(1, 4))
        if rec.bull_case:
            story.append(Paragraph("Bull Case: " + "; ".join(rec.bull_case[:4]), styles["Small"]))
        if rec.bear_case:
            story.append(Paragraph("Bear Case: " + "; ".join(rec.bear_case[:4]), styles["Small"]))
        ai = ai_insights.get(rec.symbol)
        if ai:
            story.append(Paragraph(f"AI ({ai.provider.upper()}): <b>{ai.ai_recommendation}</b>", styles["Small"]))
            if ai.investment_thesis:
                story.append(Paragraph(f"AI Thesis: {ai.investment_thesis}", styles["Small"]))
            if ai.target_price or ai.stop_loss:
                story.append(Paragraph(f"Target: {ai.target_price or '-'} | Stop Loss: {ai.stop_loss or '-'}", styles["Small"]))
        story.append(Spacer(1, 8))

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Disclaimer: This report is automated and for educational use only. Not investment advice.",
        styles["Meta"],
    ))

    doc.build(story, onFirstPage=_draw_page_chrome, onLaterPages=_draw_page_chrome)
    return str(out)
