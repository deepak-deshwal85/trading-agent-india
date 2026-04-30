# Indian Market Stock Advisory System

A comprehensive stock analysis tool for Indian markets (NSE/BSE) that aggregates news from 10+ sources, performs sentiment/fundamental/technical analysis on Nifty 50 stocks, and uses **AI (Anthropic Claude / OpenAI GPT)** for expert-level **Buy / Sell / Hold** recommendations.

## Features

### News Aggregation (10+ Sources)
- **Google News** — Indian market & stock-specific news
- **Zerodha Pulse** — Curated financial news
- **Economic Times Markets** — Market reports via RSS
- **MoneyControl** — Market analysis RSS
- **LiveMint Markets** — Financial news
- **Broker Research** — ICICI Securities, Motilal Oswal, HDFC Securities, Kotak Securities, Axis Securities
- **NSE/BSE Announcements** — Corporate actions & filings
- **World News** — Fed decisions, oil prices, China economy, trade wars, global markets

### Sentiment Analysis
- **VADER** (fast, no GPU) — Enhanced with 50+ financial-domain terms (FII buying/selling, rate hike/cut, margin expansion, etc.)
- **FinBERT** (optional, deep) — ProsusAI/finbert transformer model for financial-domain NLP

### Fundamental-style scoring (OpenAlgo)
- Uses **OpenAlgo** daily history + live **quotes** (your Zerodha/broker feed — no Yahoo Finance).
- 52-week range, price momentum (~6M), volume vs 20-day average, plus optional AI context.
- Classic P/E, ROE, etc. are **not** available from the broker API here; scoring is **market-data-driven**.

### Technical Analysis
- **Moving Averages**: SMA(20), SMA(50), EMA(12), EMA(26), Golden/Death Cross detection
- **RSI**: Overbought/Oversold signals
- **MACD**: Bullish/Bearish crossover detection
- **Bollinger Bands**: Band position analysis
- **Volume Analysis**: 20-day average comparison
- **ADX**: Trend strength measurement
- Automated scoring (0-100) with rating

### AI-Powered Deep Analysis (NEW)
- **Configurable provider** — Switch between Anthropic Claude and OpenAI GPT via `.env`
- **Market Overview** — AI-generated overall market outlook, Nifty view, sector rotation strategy
- **Per-Stock Analysis** — Investment thesis, target price, stop loss, key catalysts & risks
- **Algo vs AI Comparison** — Side-by-side table comparing algorithmic and AI recommendations
- **Top Picks & Avoid List** — AI curated best and worst stocks from the universe

### Recommendation Engine
- Weighted composite scoring (Sentiment 25% + Fundamental 40% + Technical 35%)
- **STRONG BUY / BUY / HOLD / SELL / STRONG SELL** ratings
- Confidence level (High / Medium / Low)
- Risk assessment (Low / Moderate / High / Very High)
- Bull case and Bear case summaries
- Key support/resistance levels

## Setup

### Prerequisites
- Python 3.10+
- **[OpenAlgo](https://docs.openalgo.in)** running (e.g. `http://127.0.0.1:5000`) with broker (e.g. Zerodha) connected
- `OPENALGO_API_KEY` from the OpenAlgo app (required for prices & history)
- Internet connection (news + AI)
- Anthropic and/or OpenAI API key (optional, for `--ai`)

### Installation

```bash
cd trading-agent-india
pip install -r requirements.txt
```

### Configuration

Edit the `.env` file to set your API keys and preferred AI provider:

```env
# Options: "anthropic" | "openai"
AI_PROVIDER=anthropic

ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...

# Optional model overrides
# ANTHROPIC_MODEL=claude-sonnet-4-20250514
# OPENAI_MODEL=gpt-4o

# OpenAlgo (market data)
OPENALGO_API_KEY=your_openalgo_api_key
OPENALGO_HOST=http://127.0.0.1:5000
OPENALGO_USERNAME=your_login_username
OPENALGO_EXCHANGE=NSE
# Use "db" if you rely on OpenAlgo Historify/DuckDB for daily candles
# OPENALGO_HISTORY_SOURCE=api
```

See also `.env.example`.

## Usage

### Basic — Analyze all Nifty 50 stocks (VADER sentiment, no AI):
```bash
python main.py
```

### Specific stocks:
```bash
python main.py --stocks RELIANCE INFY TCS HDFCBANK ICICIBANK
```

### Enable AI deep analysis (uses provider from .env):
```bash
python main.py --ai --stocks RELIANCE INFY TCS
```

### Use a specific AI provider via CLI:
```bash
python main.py --ai --provider openai --stocks RELIANCE INFY TCS
python main.py --ai --provider anthropic --stocks RELIANCE INFY TCS
```

### Full analysis with AI + detailed panels:
```bash
python main.py --ai --detailed --stocks RELIANCE INFY TCS
```

### Export modern PDF report:
```bash
python main.py --ai --detailed --pdf --pdf-file reports/market_report.pdf --stocks RELIANCE INFY TCS
```

## Production Run Commands

### Full Nifty50 run (AI + PDF, dated filename)
**PowerShell**
```powershell
$ts = Get-Date -Format "yyyyMMdd_HHmm"
python main.py --ai --provider openai --pdf --pdf-file "reports/nifty50_$ts.pdf" --top 20
```

### Faster run (skip market news fetch, still computes stocks + AI)
```powershell
$ts = Get-Date -Format "yyyyMMdd_HHmm"
python main.py --ai --provider openai --skip-news --pdf --pdf-file "reports/nifty50_fast_$ts.pdf" --top 20
```

### Health check before scheduled run
```powershell
python -c "from openalgo_data import check_openalgo_auth; print(check_openalgo_auth())"
```
Expected output:
```text
(True, 'OpenAlgo authentication OK.')
```

### Validate symbol availability before full run
```powershell
# Validate Nifty50 against OpenAlgo
python main.py --validate-symbols

# Validate custom symbols
python main.py --validate-symbols --stocks RELIANCE INFY TATAMOTORS
```

### Auto-drop missing symbols and continue run
```powershell
# Drop missing/unreachable symbols, continue analysis with valid symbols only
python main.py --ai --drop-missing --pdf --pdf-file reports/market_after_drop.pdf
```

### Save validation report to CSV
```powershell
# Save symbol status to an explicit file
python main.py --validate-symbols --symbol-report-csv reports/symbol_validation.csv

# Auto timestamped CSV
python main.py --validate-symbols --symbol-report-csv auto
```

### Windows Task Scheduler action example
Program/script:
```text
powershell.exe
```
Arguments:
```text
-NoProfile -ExecutionPolicy Bypass -Command "$ts = Get-Date -Format 'yyyyMMdd_HHmm'; cd 'C:\Users\Swati\trading-agent-india'; python main.py --ai --provider openai --pdf --pdf-file ('reports/nifty50_'+$ts+'.pdf') --top 20"
```

### Use FinBERT + AI for maximum accuracy:
```bash
python main.py --finbert --ai --stocks RELIANCE INFY TCS
```

### Show top/bottom N stocks only:
```bash
python main.py --top 10
```

### Skip news (faster, for testing):
```bash
python main.py --skip-news --stocks RELIANCE
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       main.py (Orchestrator)                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ news_fetcher │  │  sentiment   │  │    report    │              │
│  │    .py       │  │    .py       │  │     .py      │              │
│  │              │  │              │  │              │              │
│  │ Google News  │  │ VADER        │  │ Rich tables  │              │
│  │ Zerodha      │  │ FinBERT      │  │ Panels       │              │
│  │ ET Markets   │  │ Fin-lexicon  │  │ AI insights  │              │
│  │ MoneyCtrl    │  │              │  │              │              │
│  │ LiveMint     │  └──────────────┘  └──────────────┘              │
│  │ Brokers      │                                                   │
│  │ NSE/BSE      │  ┌──────────────┐  ┌───────────────┐             │
│  │ World News   │  │ fundamental  │  │recommendation │             │
│  └──────────────┘  │    .py       │  │    .py        │             │
│                     │              │  │               │             │
│  ┌──────────────┐  │ OpenAlgo     │  │ Weighted      │             │
│  │  config.py   │  │ P/E, ROE     │  │ scoring       │             │
│  │  .env        │  │ Growth, Debt │  │ Buy/Sell/Hold │             │
│  │              │  └──────────────┘  │ Confidence    │             │
│  │ AI Provider  │                    └───────────────┘             │
│  │ API Keys     │  ┌──────────────┐                                │
│  │ Nifty 50     │  │  technical   │  ┌───────────────┐             │
│  │ Parameters   │  │    .py       │  │ ai_analyzer   │             │
│  └──────────────┘  │              │  │    .py        │             │
│                     │ RSI, MACD    │  │               │             │
│                     │ SMA, EMA     │  │ Claude / GPT  │             │
│                     │ Bollinger    │  │ Market view   │             │
│                     │ Volume, ADX  │  │ Stock thesis  │             │
│                     └──────────────┘  │ Targets       │             │
│                                       └───────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

## Output

The system produces a color-coded terminal report with:
1. Market & World Sentiment overview
2. Top market headlines (Indian + World)
3. AI Market Overview & Strategy (with `--ai`)
4. Full recommendation table (sorted by composite score)
5. Algo vs AI comparison table (with `--ai`)
6. Categorized Buy / Hold / Sell lists
7. Detailed per-stock analysis with AI investment thesis (with `--detailed`)

## Disclaimer

This tool is for **educational and informational purposes only**. It does NOT constitute financial advice. Always consult a SEBI-registered financial advisor before making investment decisions. Past performance does not guarantee future results.

## Technologies

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Stock Data | OpenAlgo (broker API) |
| Technical Analysis | pandas_ta |
| News Aggregation | feedparser, requests, BeautifulSoup |
| Sentiment (Fast) | VADER + Financial Lexicon |
| Sentiment (Deep) | FinBERT (ProsusAI/finbert) |
| AI Analysis | Anthropic Claude / OpenAI GPT (configurable) |
| Configuration | python-dotenv (.env file) |
| Output | Rich (tables, panels, colors) |
| Data Processing | pandas, numpy |
