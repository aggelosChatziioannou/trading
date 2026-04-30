# GOLD TACTIC v7.2 — Adaptive AI Trading System

> **Paper trading system** for daily trading (1–2 trades/day). Runs autonomously via Claude app scheduled tasks. Telegram messages in Greek. No real money is moved.

**Source of truth:** [`GOLD_TACTIC/PROJECT_CONTEXT.md`](GOLD_TACTIC/PROJECT_CONTEXT.md)

---

## What This Is

An adaptive AI trading analyst that runs inside **Claude app scheduled tasks** (Pro subscription, Sonnet 4.6 only). It:

- Scans 12 master assets across forex, indices, metals, and crypto
- Picks the top 4 to actively monitor
- Sends regular Telegram updates with TRS scoring
- Auto-opens paper trades on Tier C signals
- Manages full trade lifecycle: probe / full / confirm sizing → TP1→BE→TP2 runner → optional rocket launch
- Enforces strict risk gates (4h SL caps, daily stop, correlations, kill zones)

**Capital:** 1000€ paper · **Daily target:** 30€ base / 50€ stretch · **Daily stop:** -40€ · **Max risk/trade:** 2% · **Max hold:** 4h

---

## Architecture (v7.2 — 2 prompts, 8 schedules)

```
Asset Selector (4×/week) ──► data/selected_assets.json ──┐
                                                          ├─► Market Monitor (every 20'/40', 24/7)
                              data/briefing_log.md  ◄────┘    ─► Telegram (Greek)
                                                              ─► trade_manager (open/tick/close/launch)
```

**Two active prompts only:**
- `GOLD_TACTIC/prompts/asset_selector.md` (296 LOC) — full-mode news scout, top-4 picker
- `GOLD_TACTIC/prompts/market_monitor.md` (970+ LOC) — light-mode scout, TRS scoring, trade execution

**12 master assets:** EURUSD, GBPUSD, USDJPY, AUDUSD, XAUUSD, NAS100, SPX500, BTC, ETH, SOL, XRP, DXY (reference only).

---

## Setup on a New PC

### 1. Clone
```bash
git clone https://github.com/aggelosChatziioannou/trading.git
cd trading
```

### 2. Python dependencies
```bash
pip install -r requirements.txt
```

### 3. Update hardcoded paths in 3 files
The prompts contain `C:\Users\aggel\Desktop\trading` — replace with your clone path.

```powershell
$old = "C:\Users\aggel\Desktop\trading"
$new = "C:\YOUR\ACTUAL\PATH\trading"

Get-ChildItem "GOLD_TACTIC\prompts\*.md", "GOLD_TACTIC\PROJECT_CONTEXT.md" | ForEach-Object {
    (Get-Content $_.FullName) -replace [regex]::Escape($old), $new | Set-Content $_.FullName
}
```

### 4. Environment variables
Copy `.env.example` to `.env` and fill in:

```ini
TELEGRAM_BOT_TOKEN=your_bot_token         # required (from @BotFather)
TELEGRAM_CHANNEL=-100xxxxxxxxxx           # required
FINNHUB_API_KEY=your_finnhub_key          # required (free tier, finnhub.io)
CRYPTOPANIC_API_KEY=                      # optional (free tier, cryptopanic.com)
```

### 5. Install Claude app scheduled tasks
Give the file [`GOLD_TACTIC/SCHEDULE_SETUP.md`](GOLD_TACTIC/SCHEDULE_SETUP.md) to a Claude Cowork session. It will create the 8 schedules.

### 6. Smoke-test the pipeline
```bash
python GOLD_TACTIC/scripts/news_scout_v2.py --light --summarize
python GOLD_TACTIC/scripts/quick_scan.py
python GOLD_TACTIC/scripts/trade_manager.py list
```

---

## Schedules (8 Claude app tasks)

| Name | When (EET) | Prompt |
|------|------------|--------|
| GT Asset Selector AM | Mon–Fri 08:00 | `asset_selector.md` |
| GT Asset Selector PM | Mon–Fri 15:00 | `asset_selector.md` |
| GT Asset Selector EVE | Mon–Fri 21:00 | `asset_selector.md` (+ briefing log rotation) |
| GT Asset Selector WE | Sat/Sun 10:00 | `asset_selector.md` |
| GT Market Monitor Peak | Mon–Fri 08:05–22:00 every 20' | `market_monitor.md` |
| GT Market Monitor OffPeak | Mon–Fri 22:00–00:00 every 40' | `market_monitor.md` |
| GT Market Monitor Night | Mon–Fri 00:00–07:40 every 40' | `market_monitor.md` |
| GT Market Monitor WE | Sat/Sun 10:00–22:00 every 40' | `market_monitor.md` |

Selector 08:00 → Monitor 08:05 offset avoids race conditions.

---

## TRS — Trade Readiness Score (0–5)

Algorithmic baseline (`trs_calculator.py`) + AI override ±1 with justification.

| # | Criterion | Pass rule |
|---|-----------|-----------|
| 1 | **TF** Timeframe alignment | Daily + 4H same direction |
| 2 | **RSI** | 30–70 toward bias (no extreme against) |
| 3 | **ADR** remaining | ≥ 30% room to move |
| 4 | **News** supportive/neutral | No contra-catalyst (tier-weighted) |
| 5 | **Key** level proximity | Within 1% of entry zone |

**Telegram tier rules:**
| Tier | Trigger | Length |
|------|---------|--------|
| **A — Heartbeat** (silent) | Nothing changed + Δp < 0.3% + no HIGH/MED news | ~450 chars |
| **B — Delta** (normal notify) | TRS bucket changed / Δp ≥ 0.3% / new HIGH-MED news | ~700 chars |
| **C — Full Signal** (🔥 effect on TRS=5) | Asset reached TRS ≥ 4 (optimal KZ) or ≥ 5 (off-hours) | ~1200 chars |

---

## Trade Lifecycle

### Probe / Full / Confirm sizing
| Tag | Trigger | Risk |
|-----|---------|------|
| `full` | TRS=5 fresh setup | 2% (20€) |
| `probe` | TRS=4 in optimal kill-zone | 1% (10€) |
| `confirm` | TRS=5 with active probe | 1% (+half-position) |

### TP1 → BE → TP2 Runner
- TP1 hit → SL → entry (break-even), keeps running
- TP2 hit → close runner (🎯🎯)
- Returns to entry post-TP1 → 🛡️ BE exit (P/L=0)

### 🚀 Launch Protocol
Manual `launch <trade_id> --reason news|momentum|tp2_runner|manual` or opt-in `--auto-launch`. Extends TP/SL/timeout for rocket scenarios. Preserves originals for audit.

### Risk Gates (STEP 4.8 in Monitor)
1. Daily stop (-40€) → halt all signals
2. Max concurrent (2 trades)
3. Kill zone enforcement (Tier C blocked off-hours)
4. Max hold 4h → auto-close at break-even
5. **TP/SL 4h caps** (`validate_sl_distance`) → block swing-scale stops
6. **Correlation clusters** (`correlation_map.json`) → max 2 per cluster

---

## News Pipeline (v3 — 10 sources, tier-aware)

| Tier | Sources | Weight |
|------|---------|--------|
| **1 — Premium** | Reuters · Bloomberg · ForexLive · CoinDesk · WSJ · FT · CNBC | ×1.5 |
| **2 — Standard** | Yahoo · Investing.com · FOREX.com · MarketWatch · Cointelegraph · Reddit-Top · KITCO | ×1.0 |
| **3 — Other** | blogs, generic aggregators | ×0.5 |

**Sources:**
- Finnhub API (general + forex categories)
- CryptoPanic API (optional, free key)
- Google News RSS (per-asset queries for all 12 assets + MACRO)
- ForexLive · Investing.com · ZeroHedge · CoinDesk · Cointelegraph · MarketWatch RSS
- Reddit Atom feeds (r/Forex, r/CryptoCurrency, r/Bitcoin, r/wallstreetbets)

**Light mode** (Monitor): selected 4 + MACRO, ~6 sources, <15s
**Full mode** (Selector): all 12 assets, ~10 sources, ~30-60s

Every Telegram message includes a **transparency footer** showing which sources were polled (✅ ok / ❌ failed) with tier distribution. Every article reference is a clickable HTML link.

---

## Kill Zones (EET / UTC+3)

| Tier | Hours | Tier C signals |
|------|-------|----------------|
| **Optimal** | London KZ 10:00–12:00 / NY KZ 15:30–17:30 / Overlap | ✅ Active (TRS ≥ 4) |
| **Acceptable** | London/NY outside KZ | Tier C only TRS=5 |
| **Off** | Asian / off-hours 18:00–10:00 | ❌ No Tier C |
| **Crypto-only / Weekend** | Sat/Sun | Crypto only + KZ rule |

---

## File Structure

```
trading/
├── README.md                              ← this file
├── .env.example                           ← env template
├── requirements.txt
└── GOLD_TACTIC/
    ├── PROJECT_CONTEXT.md                 ← ⭐ canonical state document
    ├── SCHEDULE_SETUP.md                  ← Cowork install guide
    ├── prompts/
    │   ├── asset_selector.md              (296 LOC)
    │   └── market_monitor.md              (970+ LOC)
    ├── scripts/  (33 Python files, 12k LOC)
    │   ├── trade_manager.py               (937 LOC) — open/tick/close/launch CLI + library
    │   ├── risk_manager.py                (902 LOC) — ASSET_CONFIG, validate_sl, suggest_tp_sl
    │   ├── news_scout_v2.py               (480 LOC) — 10-source v3 with tier system
    │   ├── trs_calculator.py              (748 LOC) — algorithmic TRS baseline
    │   ├── quick_scan.py                  (610 LOC) — RSI/EMA/ADR/regime
    │   ├── dashboard_builder.py           (366 LOC) — pinned dashboard
    │   ├── telegram_sender.py             (514 LOC) — Telegram API
    │   ├── telegram_state.py              (619 LOC) — pinned msg state
    │   ├── chart_generator.py             (863 LOC) — mplfinance charts
    │   ├── price_checker.py               (326 LOC) — dual-source live price
    │   ├── session_check.py               (125 LOC) — kill zone awareness
    │   ├── economic_calendar.py           (186 LOC) — HIGH impact events
    │   ├── news_impact.py                 (298 LOC) — pre/post snapshots
    │   └── ... (backtest_*, news_scout, sentiment, etc)
    ├── data/  (~40 runtime files)
    │   ├── master_assets.json             (committed) — 12 assets + strategies
    │   ├── selected_assets.json           — current top 4 (auto)
    │   ├── portfolio.json                 — balance + closed-trade stats
    │   ├── trade_state.json               — open trades (atomic writes)
    │   ├── trade_journal.jsonl            — audit-trail (append-only)
    │   ├── correlation_map.json           — 4 clusters, max 2/cluster
    │   ├── briefing_log.md                — Telegram coherence log
    │   ├── telegram_state.json            — pinned msg id state
    │   ├── trs_current.json               — TRS snapshot per asset
    │   ├── news_feed.json                 — v3 output with tier/sources
    │   └── ... (quick_scan, live_prices, market_regime, etc)
    └── archive/  (legacy v5/v6, old prompts, windows_schtasks)
```

---

## Key Commands (CLI)

```bash
# Trade management
python GOLD_TACTIC/scripts/trade_manager.py list          # show open trades
python GOLD_TACTIC/scripts/trade_manager.py header        # HTML block for messages
python GOLD_TACTIC/scripts/trade_manager.py tick          # check open trades vs prices
python GOLD_TACTIC/scripts/trade_manager.py close <id>    # manual close
python GOLD_TACTIC/scripts/trade_manager.py suggest XAUUSD LONG 3245 --atr 8.5 --mode typical
python GOLD_TACTIC/scripts/trade_manager.py launch <id> --reason news --timeout-h 6

# News scouting
python GOLD_TACTIC/scripts/news_scout_v2.py --light --summarize       # Monitor cycle
python GOLD_TACTIC/scripts/news_scout_v2.py --full --summarize        # Selector cycle
python GOLD_TACTIC/scripts/news_scout_v2.py --light XAUUSD BTC        # specific assets

# News impact tracking
python GOLD_TACTIC/scripts/news_impact.py --pre "US_CPI"              # ~30min before event
python GOLD_TACTIC/scripts/news_impact.py --post "US_CPI"             # 5min after event
python GOLD_TACTIC/scripts/news_impact.py --report                    # stats per event type

# Pipeline data
python GOLD_TACTIC/scripts/price_checker.py
python GOLD_TACTIC/scripts/quick_scan.py
python GOLD_TACTIC/scripts/economic_calendar.py
python GOLD_TACTIC/scripts/session_check.py > GOLD_TACTIC/data/session_now.json
```

---

## Disclaimer

**Paper trading system for educational purposes.** No real money is traded. The system writes to `data/portfolio.json` and tracks fictional trades. To go live with a real broker requires explicit code changes (see PROJECT_CONTEXT.md → "Future" section for OANDA / IC Markets MT5 plans).
