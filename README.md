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
- **Default (local)** — **VADER + ProsusAI FinBERT** ensemble (+ optional FinBERT-Tone weights from `app.env`); falls back to VADER if models fail to load

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

Provider is still chosen on the CLI: `--ai --provider anthropic`. Set `AI_SENTIMENT_USE_LLM=false` in `app.env` to use the **local VADER + FinBERT** ensemble for headlines instead of the fast LLM when `--ai` is on.

See `.env.example` and `app.env`.

## Usage

### Basic — Analyze all Nifty 50 stocks (local sentiment ensemble, no AI):
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

### Full analysis with AI
```bash
python main.py --ai --provider anthropic --stocks RELIANCE INFY TCS
```

### PDF report (fixed path)
Every completed analysis writes **`reports/market_report.pdf`** (`config.PDF_REPORT_PATH`) and sends it via Telegram when `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set. The `reports/` folder is created automatically.

```bash
python main.py --ai --provider anthropic --stocks RELIANCE INFY TCS
```

## Production Run Commands

### GitHub Actions (three workflows + Telegram PDF)

There are **three** workflows under [`.github/workflows/`](.github/workflows/), each with **`workflow_dispatch`** (manual run) plus its own schedule:

| Workflow | Schedule | Command |
|----------|----------|---------|
| [`market-analysis-no-ai.yml`](.github/workflows/market-analysis-no-ai.yml) | Every **6 hours** on **IST** wall clock (midnight, 06:00, 12:00, 18:00 IST; expressed as cron in UTC) | `python main.py` |
| [`market-analysis-anthropic.yml`](.github/workflows/market-analysis-anthropic.yml) | **Monday–Friday ~08:00 IST** | `python main.py --ai --provider anthropic` |
| [`market-analysis-openai.yml`](.github/workflows/market-analysis-openai.yml) | **Monday–Friday ~08:00 IST** | `python main.py --ai --provider openai` |

Each run **uploads the PDF** artifact and **sends it** via Telegram when secrets are set. If both AI workflows stay enabled on the same cron, you get **two** reports at that time—disable the workflow you do not use (repository **Actions** tab → workflow → ⋯ → disable).

**Required repo secrets** (Settings → Secrets and variables → Actions):

| Secret | How to get it |
|--------|----------------|
| `TELEGRAM_BOT_TOKEN` | Create a bot with [@BotFather](https://t.me/BotFather), copy the token |
| `TELEGRAM_CHAT_ID` | Message your bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `"chat":{"id":...}` |

Optional: `TELEGRAM_CAPTION`. For scheduled AI runs, set `ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY` to match the workflows you keep enabled.

**Test Telegram locally:**

```powershell
$env:TELEGRAM_BOT_TOKEN = "your-token"
$env:TELEGRAM_CHAT_ID = "your-chat-id"
python main.py --stocks RELIANCE
python scripts/send_telegram.py --file reports/market_report.pdf --caption "Test report"
```

### Full Nifty50 run (AI)
**PowerShell**
```powershell
python main.py --ai --provider openai
```

### Health check before scheduled run
```powershell
python -c "from market_data import check_market_data_auth; print(check_market_data_auth())"
```
Expected output:
```text
(True, 'Market data OK (yfinance).')
```

### Windows Task Scheduler action example
Program/script:
```text
powershell.exe
```
Arguments:
```text
-NoProfile -ExecutionPolicy Bypass -Command "cd 'C:\Users\Swati\trading-agent-india'; python main.py --ai --provider openai"
```

### AI on a small universe (faster API spend)
```bash
python main.py --ai --stocks RELIANCE INFY TCS
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
7. Detailed per-stock panels (algo always; AI thesis when `--ai`)

## Disclaimer

This tool is for **educational and informational purposes only**. It does NOT constitute financial advice. Always consult a SEBI-registered financial advisor before making investment decisions. Past performance does not guarantee future results.

## Technologies

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| Stock Data | yfinance + jugaad-data (NSE) |
| Technical Analysis | pandas_ta |
| News Aggregation | feedparser, requests, BeautifulSoup |
| Sentiment (default) | VADER + FinBERT ensemble (+ optional Tone); LLM batch when `--ai` + `AI_SENTIMENT_USE_LLM` |
| AI Analysis | Anthropic Claude / OpenAI GPT (configurable) |
| Configuration | python-dotenv (.env file) |
| Output | Rich (tables, panels, colors) |
| Data Processing | pandas, numpy |
