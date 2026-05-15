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

### Fundamental-style scoring (free market data)
- Uses **yfinance** (Yahoo Finance, NSE `.NS` tickers) with **jugaad-data** (NSE) as fallback.
- 52-week range, price momentum (~6M), volume vs 20-day average, plus optional AI context.
- Classic P/E, ROE, etc. are **not** available from the broker API here; scoring is **market-data-driven**.

### Technical Analysis
- **Trend**: SMA(20), SMA(50), Golden/Death Cross; **EMA(9)** & **EMA(21)** (fast pair; MACD still uses 12/26 internally)
- **Momentum**: RSI(14), **Stochastic (14,3,3)**, MACD (12,26,9) line / signal / histogram
- **Volatility**: Bollinger Bands(20,2), **ATR(14)**
- **Volume**: Latest vs **20-day average**; **OBV** with accumulation/distribution-style read
- **Trend line**: **Supertrend** (configurable length × ATR mult; default 7, 3)
- **ADX**(14): Trend strength; **oscillator signals are damped when ADX ≤ 25** (ranging regime; NSE/BSE-style gate)
- **Technical score (0–100)**: weighted blend — trend **30%**, momentum **30%**, volatility **15%**, volume **15%**, ADX bucket **10%** — plus Buy/Sell/Neutral-style rating

### AI-Powered Deep Analysis (NEW)
- **Provider chosen on the command line** — Pass `--ai --provider anthropic` or `--ai --provider openai` (API keys only in `.env`, not the provider name)
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
- Python 3.12+ (required by `pandas-ta` on PyPI)
- Internet connection (news, market data, optional AI)
- No broker API keys — prices via **yfinance** / **jugaad-data**
- Anthropic and/or OpenAI API key (optional, for `--ai`)

### Installation

```bash
cd trading-agent-india
pip install -r requirements.txt
```

### Configuration

| File | Purpose | Commit? |
|------|---------|--------|
| **`.env`** | Secrets only: API keys, Telegram | No |
| **`app.env`** | Models, sentiment weights, toggles | Yes |

Edit **`.env`** for API keys. Edit **`app.env`** for non-secret settings (default hybrid: **Haiku 4.5** for news sentiment, **Sonnet 4.6** for deep stock/market analysis when using `--ai --provider anthropic`).

```env
# .env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...
```

```env
# app.env (committed defaults)
ANTHROPIC_MODEL_FAST=claude-haiku-4-5
ANTHROPIC_MODEL_DEEP=claude-sonnet-4-6
AI_SENTIMENT_USE_LLM=true
```

Provider is still chosen on the CLI: `--ai --provider anthropic`. Set `AI_SENTIMENT_USE_LLM=false` in `app.env` to keep VADER/`--finbert` for news even when `--ai` is on.

See `.env.example` and `app.env`.

## Usage

### Basic — Analyze all Nifty 50 stocks (VADER sentiment, no AI):
```bash
python main.py
```

### Specific stocks:
```bash
python main.py --stocks RELIANCE INFY TCS HDFCBANK ICICIBANK
```

### Enable AI deep analysis (`--provider` required):
```bash
python main.py --ai --provider anthropic --stocks RELIANCE INFY TCS
```

### Choose AI provider via CLI:
```bash
python main.py --ai --provider openai --stocks RELIANCE INFY TCS
python main.py --ai --provider anthropic --stocks RELIANCE INFY TCS
```

### Full analysis with AI + detailed panels:
```bash
python main.py --ai --detailed --stocks RELIANCE INFY TCS
```

### PDF output path (`--pdf-file`)
Every completed analysis writes a PDF (default `market_report.pdf`) and sends it via Telegram when `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set.

```bash
python main.py --ai --detailed --pdf-file reports/market_report.pdf --stocks RELIANCE INFY TCS
```

## Production Run Commands

### GitHub Actions (scheduled Mon–Fri + manual dispatch + Telegram PDF)
The workflow [`.github/workflows/daily-analysis.yml`](.github/workflows/daily-analysis.yml) runs **Monday–Friday ~08:00 IST** and on **manual dispatch**. Default command:

```bash
python main.py --drop-missing --pdf-file reports/market_report.pdf
```

Then it **uploads the PDF** as a workflow artifact and **sends it to your Telegram bot**.

**Required repo secrets** (Settings → Secrets and variables → Actions):

| Secret | How to get it |
|--------|----------------|
| `TELEGRAM_BOT_TOKEN` | Create a bot with [@BotFather](https://t.me/BotFather), copy the token |
| `TELEGRAM_CHAT_ID` | Message your bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `"chat":{"id":...}` |

Optional: `TELEGRAM_CAPTION`. For AI in CI, enable inputs for `--ai` **and** `--provider anthropic` or `--provider openai`, plus matching API key secrets.

**Test Telegram locally:**

```powershell
$env:TELEGRAM_BOT_TOKEN = "your-token"
$env:TELEGRAM_CHAT_ID = "your-chat-id"
python main.py --skip-news --stocks RELIANCE --pdf-file reports/test.pdf
python scripts/send_telegram.py --file reports/test.pdf --caption "Test report"
```

### Full Nifty50 run (AI + PDF, dated filename)
**PowerShell**
```powershell
$ts = Get-Date -Format "yyyyMMdd_HHmm"
python main.py --ai --provider openai --pdf-file "reports/nifty50_$ts.pdf"
```

### Faster run (skip market news fetch, still computes stocks + AI)
```powershell
$ts = Get-Date -Format "yyyyMMdd_HHmm"
python main.py --ai --provider openai --skip-news --pdf-file "reports/nifty50_fast_$ts.pdf"
```

### Health check before scheduled run
```powershell
python -c "from market_data import check_market_data_auth; print(check_market_data_auth())"
```
Expected output:
```text
(True, 'Market data OK (yfinance).')
```

### Auto-drop missing symbols and continue run
```powershell
# Drop missing/unreachable symbols, continue analysis with valid symbols only
python main.py --ai --drop-missing --pdf-file reports/market_after_drop.pdf
```

### Save validation report to CSV (then continue full analysis)
```powershell
python main.py --symbol-report-csv reports/symbol_validation.csv
python main.py --symbol-report-csv auto
```
Use with `--drop-missing` to filter to valid symbols after writing the CSV.

### Windows Task Scheduler action example
Program/script:
```text
powershell.exe
```
Arguments:
```text
-NoProfile -ExecutionPolicy Bypass -Command "$ts = Get-Date -Format 'yyyyMMdd_HHmm'; cd 'C:\Users\Swati\trading-agent-india'; python main.py --ai --provider openai --pdf-file ('reports/nifty50_'+$ts+'.pdf')"
```

### Use FinBERT + AI for maximum accuracy:
```bash
python main.py --finbert --ai --stocks RELIANCE INFY TCS
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
│  ┌──────────────┐  │ yfinance /   │  │ Weighted      │             │
│  │  config.py   │  │ jugaad-data  │  │ scoring       │             │
│  │  .env        │  │ price-driven │  │ Buy/Sell/Hold │             │
│  │              │  └──────────────┘  │ Confidence    │             │
│  │ AI Provider  │                    └───────────────┘             │
│  │ API Keys     │  ┌──────────────┐                                │
│  │ Nifty 50     │  │  technical   │  ┌───────────────┐             │
│  │ Parameters   │  │    .py       │  │ ai_analyzer   │             │
│  └──────────────┘  │              │  │    .py        │             │
│                     │ RSI, Stoch,  │  │               │             │
│                     │ MACD, BB,    │  │ Claude / GPT  │             │
│                     │ ATR, OBV,    │  │ Market view   │             │
│                     │ Supertrend   │  │ Stock thesis  │             │
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
| Language | Python 3.12+ |
| Stock Data | yfinance + jugaad-data (NSE) |
| Technical Analysis | pandas_ta |
| News Aggregation | feedparser, requests, BeautifulSoup |
| Sentiment (Fast) | VADER + Financial Lexicon |
| Sentiment (Deep) | FinBERT (ProsusAI/finbert) |
| AI Analysis | Anthropic Claude / OpenAI GPT (configurable) |
| Configuration | python-dotenv (.env file) |
| Output | Rich (tables, panels, colors) |
| Data Processing | pandas, numpy |
