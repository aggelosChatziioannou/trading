# GOLD TACTIC — Adaptive AI Trading System v6

> **For Claude Code:** This is the latest version. Clone this repo and load `GOLD_TACTIC/prompts/adaptive_analyst.md` as your prompt to start the trading analyst.

---

## Setup on a New PC

**After cloning, you MUST update the hardcoded paths in 3 prompt files.**

The prompts contain `C:\Users\aggel\Desktop\trading` — replace with your actual clone path.

**Quick way (PowerShell):**
```powershell
$old = "C:\Users\aggel\Desktop\trading"
$new = "C:\YOUR\ACTUAL\PATH\trading"   # <-- change this

Get-ChildItem "GOLD_TACTIC\prompts\*.md" | ForEach-Object {
    (Get-Content $_.FullName) -replace [regex]::Escape($old), $new | Set-Content $_.FullName
}
```

**Also update `.mcp.json`** — change the tradingview-mcp path:
```json
"args": ["C:/YOUR/PATH/tradingview-mcp/src/server.js"]
```
Install the MCP server: `git clone https://github.com/tradesdontlie/tradingview-mcp && cd tradingview-mcp && npm install`

**Python dependencies:**
```bash
pip install yfinance pandas numpy mplfinance requests python-dotenv
```

That's it — `.env` with all keys is included in the repo.

---

## What This Is

An adaptive AI trading analyst that runs inside **Claude Code** as an autonomous agent. It monitors markets, scores setups, manages open trades, and sends alerts via Telegram — all driven by a single large prompt (`adaptive_analyst.md`) that contains the complete decision-making logic.

**Paper trading only.** No real money is moved.

**Language:** Greek (the analyst communicates in Greek, but all code is in English)

---

## How to Start (Claude Code)

```bash
# 1. Clone
git clone https://github.com/aggelosChatziioannou/trading.git
cd trading

# 2. Install Python dependencies
pip install yfinance pandas numpy mplfinance requests python-dotenv

# 3. Copy env and fill in your keys
cp .env.example .env

# 4. Start TradingView MCP (required for live data — see MCP section below)
# Double-click TradingView-MCP.bat on your Desktop, OR run:
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%APPDATA%\ChromeMCP" "https://www.tradingview.com/chart/"

# 5. Open Claude Code in this directory
# The .mcp.json file auto-loads the TradingView MCP

# 6. Load the prompt
# Tell Claude Code: "load GOLD_TACTIC/prompts/adaptive_analyst.md and start"
```

---

## Environment Variables (`.env`)

```ini
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHANNEL=-100xxxxxxxxxx
FINNHUB_API_KEY=your_finnhub_key
```

---

## Architecture

```
Claude Code (AI Agent)
│
├── READS:  GOLD_TACTIC/prompts/adaptive_analyst.md   ← main brain
│
├── CALLS (TradingView MCP):
│   ├── tv_health_check()                            ← verify connection
│   ├── chart_set_symbol() + chart_set_timeframe()  ← navigate chart
│   └── data_get_ohlcv(count=100)                   ← fetch candles
│       └── saves → data/tv_ohlcv_raw.json
│
├── RUNS (Python scripts):
│   ├── quick_scan.py --from-file --json            ← compute RSI/EMA/ADR from TV data
│   ├── price_checker.py                            ← live price validation
│   ├── news_scout_v2.py                            ← news feed
│   ├── economic_calendar.py                        ← upcoming events
│   ├── sentiment.py                                ← market sentiment
│   ├── telegram_sender.py                          ← send alerts
│   └── telegram_cleanup.py                         ← clean old messages daily
│
└── WRITES (data files):
    ├── data/quick_scan.json                        ← computed indicators
    ├── data/tv_ohlcv_raw.json                      ← raw candles from TradingView
    ├── data/live_prices.json                       ← current prices
    ├── data/scanner_watchlist.json                 ← asset scores + status
    ├── data/portfolio.json                         ← balance + positions
    ├── data/trade_state.json                       ← open trade details
    └── data/trade_journal.md                       ← trade history log
```

---

## TradingView MCP Integration

The system uses the [tradingview-mcp](https://github.com/tradesdontlie/tradingview-mcp) server to fetch **real-time OHLCV candles** directly from TradingView, replacing the old yfinance data source.

**How it works:**
1. Claude Code connects to TradingView via Chrome DevTools Protocol (port 9222)
2. Calls `data_get_ohlcv()` for each asset × 3 timeframes (D / 4H / 1H)
3. Saves raw bars to `data/tv_ohlcv_raw.json`
4. `quick_scan.py --from-file` reads that file and computes all indicators

**The MCP server is already installed** at `C:/Users/aggel/tradingview-mcp/` and configured in `.mcp.json`.

**To activate:** Open TradingView in Chrome with `--remote-debugging-port=9222` (use `TradingView-MCP.bat` on Desktop), then restart Claude Code.

**Fallback:** If TradingView is not running, `quick_scan.py` falls back to yfinance automatically.

**TradingView symbol map:**
| Asset | TV Symbol |
|-------|-----------|
| EURUSD | FX:EURUSD |
| GBPUSD | FX:GBPUSD |
| NAS100 | CAPITALCOM:US100 |
| XAUUSD | OANDA:XAUUSD |
| BTC | BITSTAMP:BTCUSD |
| SOL | BINANCE:SOLUSDT |
| DXY | TVC:DXY |

---

## The TIER System (Adaptive Cycles)

The analyst runs in cycles with variable depth based on market activity:

| Tier | Name | Token Cost | When |
|------|------|-----------|------|
| **TIER 1** | Pulse Check | ~500 tokens | Market quiet, no open trades |
| **TIER 2** | Quick Analysis | ~3,000 tokens | Price moved, news, TRS ≥ 4 |
| **TIER 3** | Full Cycle | ~15,000 tokens | Scanner sessions, trade execution |

**Wait times between cycles:**
- Open trade near TP/SL → TIER 3 in 5 min
- Open trade stable → TIER 2 in 10 min
- Any asset TRS ≥ 4 → TIER 2 in 10 min
- All quiet → TIER 1 in 30 min
- Outside trading hours → TIER 1 in 60 min

---

## Asset Universe

**Primary (Forex + Indices):**
- EURUSD, GBPUSD (forex pairs)
- NAS100 (US tech index)
- XAUUSD (gold)
- DXY (dollar index — context only)

**Secondary (Crypto):**
- BTC, SOL (weekdays + weekends)
- ETH (weekends only)

---

## Scripts Reference

| Script | Purpose | Output |
|--------|---------|--------|
| `quick_scan.py` | RSI, EMA bias, ADR%, regime, correlations | `data/quick_scan.json` |
| `quick_scan.py --from-file` | Same but reads TV MCP data instead of yfinance | same |
| `price_checker.py` | Dual-source live price (yfinance + Yahoo web) | `data/live_prices.json` |
| `news_scout_v2.py` | Fetch news from Finnhub + RSS feeds | `data/news_feed.json` |
| `economic_calendar.py` | Upcoming high-impact events | `data/economic_calendar.json` |
| `sentiment.py` | Fear & Greed, VIX, put/call ratio | `data/sentiment.json` |
| `telegram_sender.py` | Send messages/photos/albums to Telegram | — |
| `telegram_cleanup.py` | Delete yesterday's messages | — |
| `chart_generator.py` | Generate mplfinance charts (fallback if MCP unavailable) | `screenshots/*.png` |
| `analyst_runner.py` | Heartbeat runner — calls Claude Code on a schedule | — |

---

## Data Files Reference

| File | Description |
|------|-------------|
| `data/scanner_watchlist.json` | Asset list with status (ACTIVE/STANDBY/SKIP), TRS scores, analyst instructions |
| `data/emergency_activations.json` | Hot assets activated outside normal schedule |
| `data/portfolio.json` | Current balance, total trades, winning trades, win rate |
| `data/trade_state.json` | Open trade: asset, direction, entry, SL, TP, size, P&L |
| `data/trade_history.json` | Closed trades history |
| `data/quick_scan.json` | Latest scan: RSI, bias (BULL/BEAR/MIXED), ADR%, regime, PDH/PDL |
| `data/tv_ohlcv_raw.json` | Raw OHLCV bars from TradingView MCP (D/4H/1H per asset) |
| `data/live_prices.json` | Current prices with source and validation |
| `data/market_regime.json` | ADX-based regime per asset (TRENDING/RANGING/CHOPPY) |
| `data/correlation_matrix.json` | 20-day rolling correlations between pairs |
| `data/news_feed.json` | Recent news articles with impact scoring |
| `data/narrative_memory.json` | Story arc state per asset (cross-session persistence) |
| `data/news_digest.json` | Shown news IDs today (prevents Telegram duplicates) |
| `data/telegram_log.json` | Sent message IDs (for daily cleanup) |
| `data/trade_journal.md` | Human-readable trade log |

---

## Trade Scoring (TRS — Trade Readiness Score)

Scored 0–7. Entry requires TRS ≥ 5 (TRENDING regime) or TRS ≥ 6 (RANGING).

| Factor | Points |
|--------|--------|
| Multi-timeframe alignment (all 3 TF same direction) | +2 |
| RSI not extreme (not overbought/oversold on entry) | +1 |
| ADR < 70% consumed | +1 |
| News alignment | +1 |
| Session timing (London/NY open) | +1 |
| Market regime is TRENDING | +1 |

---

## Risk Management Rules

- Max risk per trade: 2% of current balance
- Max 3 active slots simultaneously
- Correlated pairs (EURUSD + GBPUSD corr > 0.80): max 1 trade
- ADR > 90%: skip entry (unless TRENDING regime + volume > 1.5x avg)
- Losing streak ≥ 3: reduce size to 1%
- Winning streak ≥ 3: stay at 2% (no martingale)

---

## Daily Schedule

| Time (EET) | Event |
|-----------|-------|
| 08:00 | Morning Scanner — TIER 3 Full Cycle |
| 08:00–15:30 | Adaptive cycles (TIER 1/2/3 as needed) |
| 15:30 | Afternoon Scanner — NAS100 reassessment |
| 15:30–22:00 | Adaptive cycles continue |
| 22:00 | End of day — close positions, report |
| 10:00–20:00 Sat/Sun | Weekend mode — crypto only |

---

## Prompts

| File | Role |
|------|------|
| `prompts/adaptive_analyst.md` | **Main prompt** — complete analyst logic, all rules, TIER system, TRS, risk management, Telegram format |
| `prompts/scanner_morning_v6.md` | Morning scanner session (integrated into adaptive_analyst.md) |
| `prompts/scanner_afternoon_v6.md` | Afternoon scanner session (integrated into adaptive_analyst.md) |

**To run the system:** Load `adaptive_analyst.md` as the Claude Code prompt. Everything else is automated.

---

## File Structure

```
trading/
├── .mcp.json                          ← TradingView MCP config (auto-loaded by Claude Code)
├── TradingView-MCP.bat                ← Launch Chrome with debug port (run before Claude Code)
├── .env                               ← API keys (not committed)
├── .env.example                       ← Template
├── requirements.txt                   ← Python dependencies
└── GOLD_TACTIC/
    ├── prompts/
    │   ├── adaptive_analyst.md        ← MAIN PROMPT ⭐
    │   ├── scanner_morning_v6.md
    │   └── scanner_afternoon_v6.md
    ├── scripts/
    │   ├── analyst_runner.py          ← Heartbeat runner
    │   ├── quick_scan.py              ← Indicators (yfinance + TV MCP)
    │   ├── price_checker.py           ← Live prices
    │   ├── news_scout_v2.py           ← News
    │   ├── economic_calendar.py       ← Calendar events
    │   ├── sentiment.py               ← Market sentiment
    │   ├── chart_generator.py         ← Chart images (fallback)
    │   ├── telegram_sender.py         ← Telegram API
    │   └── telegram_cleanup.py        ← Daily message cleanup
    ├── data/                          ← Runtime data (most gitignored)
    │   ├── scanner_watchlist.json     ← Asset watchlist (committed)
    │   ├── portfolio.json             ← Balance tracker (committed)
    │   └── emergency_activations.json ← Hot assets (committed)
    └── screenshots/                   ← Chart images (gitignored)
```

---

## Disclaimer

Paper trading system for educational purposes. No real money is traded.
