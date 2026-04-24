# GOLD TACTIC v7.1 — Automated Trading Intelligence System

Paper trading system powered by Claude AI (Sonnet 4.6) that monitors 12 financial assets 24/7 and delivers real-time Telegram briefings in Greek with a **pinned live dashboard** and smart adaptive signal stream.

## Architecture

```
                    GOLD TACTIC v7
                         |
          +--------------+--------------+
          |                             |
   ASSET SELECTOR              MARKET MONITOR
   (3x daily)                  (every 20-40 min)
          |                             |
   Scans 12 assets             Tracks 4 selected
   Picks top 4                 Fetches prices + news
   Writes JSON                 Analyzes readiness
          |                             |
          +-------→ Telegram ←----------+
                   (Greek updates)
```

### Two Schedules, One Model

| Schedule | Purpose | Frequency | Model |
|----------|---------|-----------|-------|
| **Asset Selector** | Pick best 4 assets from 12 | 3x/day weekdays, 1x weekends | Sonnet 4.6 |
| **Market Monitor** | Analyze + Telegram updates | Every 20min (peak) / 40min (off-peak) | Sonnet 4.6 |

### Market Hours (EET)

| Zone | Hours | Monitor Freq |
|------|-------|-------------|
| Peak (London+NY) | 08:00-22:00 Mon-Fri | Every 20 min |
| Off-peak (Asia) | 22:00-08:00 Mon-Fri | Every 40 min |
| Weekend (crypto) | 10:00-22:00 Sat-Sun | Every 40 min |

## Assets Tracked

| # | Asset | Category | Strategy |
|---|-------|----------|----------|
| 1 | EURUSD | Forex | TJR Asia Sweep |
| 2 | GBPUSD | Forex | TJR Asia Sweep |
| 3 | USDJPY | Forex | TJR Asia Sweep |
| 4 | AUDUSD | Forex | TJR Asia Sweep |
| 5 | XAUUSD | Commodity | Breakout / Trend |
| 6 | NAS100 | Index | IBB Breakout |
| 7 | SPX500 | Index | IBB Breakout |
| 8 | BTC | Crypto | TJR + Counter-trend |
| 9 | ETH | Crypto | TJR + Counter-trend |
| 10 | SOL | Crypto | TJR + Counter-trend |
| 11 | XRP | Crypto | TJR + Counter-trend |
| 12 | DXY | Reference | USD index (not traded) |

## Project Structure

```
GOLD_TACTIC/
├── prompts/
│   ├── asset_selector.md      # Schedule 1 prompt
│   ├── market_monitor.md      # Schedule 2 prompt
│   └── ref_strategies.md      # Trading strategies reference
├── scripts/
│   ├── price_checker.py       # Dual-source price fetcher
│   ├── news_scout_v2.py       # Multi-source news aggregator
│   ├── quick_scan.py          # Technical analysis (RSI, ADR, bias)
│   ├── economic_calendar.py   # Economic events calendar
│   ├── telegram_sender.py     # Telegram message sender
│   └── trade_manager.py        # Trade lifecycle CLI (open/close/tick/suggest)
├── data/
│   ├── master_assets.json     # 12 assets with strategies
│   ├── selected_assets.json   # Current top 4 (auto-generated)
│   ├── live_prices.json       # Latest prices (auto-generated)
│   ├── news_feed.json         # Latest news (auto-generated)
│   ├── quick_scan.json        # Technical data (auto-generated)
│   ├── economic_calendar.json # Events (auto-generated)
│   ├── briefing_log.md        # Today's Telegram history
│   ├── portfolio.json         # Paper trading portfolio
│   └── trade_journal.md       # Trade notes
├── archive/v6/                # Previous version (archived)
├── SCHEDULE_SETUP.md          # Installation guide (give to Cowork)
└── README.md                  # This file
```

## Setup

### Prerequisites
- Windows 11 with Claude Code Desktop (Pro subscription)
- Python 3.10+ with: `yfinance`, `pandas`, `numpy`
- `.env` file in repo root with: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL`
- Computer must stay ON — schedules run inside Claude Code Desktop

### Installation
1. `git clone https://github.com/aggelosChatziioannou/trading.git`
2. Open a Claude Cowork session in the project folder
3. Paste the contents of `SCHEDULE_SETUP.md`
4. The Cowork agent will create 8 Claude app scheduled tasks automatically
5. Verify: check Telegram for first messages

### Manual Test
```bash
# Test price fetching
python GOLD_TACTIC/scripts/price_checker.py --assets XAUUSD,BTC

# Test news fetching
python GOLD_TACTIC/scripts/news_scout_v2.py --light

# Test Telegram
python GOLD_TACTIC/scripts/telegram_sender.py message "Test"
```

## Telegram Output

### Asset Selector (3x/day)
Reports which 4 assets are selected, with scores and reasons. Includes today's economic events.

### Market Monitor (every 20-40 min)
Shows TRS (Trade Readiness Score 0-5) per asset, price changes, news with links, and what changed since last update. Uses coherent narrative (reads previous messages).

## Data Flow

```
Python (prices/news) → JSON files → Claude (analysis) → Telegram
                                  ↓
                           briefing_log.md (coherence)
                           selected_assets.json (state)
```

## Key Concepts

- **TRS (Trade Readiness Score):** 0-5 score indicating how close an asset is to a tradeable setup
- **Asset Rotation:** The Selector picks the 4 most promising assets 3x/day based on technicals + news
- **Coherence:** Every Monitor cycle reads the briefing log to avoid repetition and track changes
- **Graceful degradation:** If a data source fails, the system uses stale data with a warning

## Telegram UX v7.1

Το chat οργανώνεται σε δύο στρώματα:

1. **📌 Pinned Dashboard (always-visible)** — edit-άρεται σε κάθε Monitor cycle. Δείχνει balance, daily P/L progress bar, 4 watched assets με TRS + 5 criteria (✅TF/RSI/ADR/News/Key), open trades, next event countdown, sentiment.
2. **Chronological stream** — Asset Selector messages (rich multi-section) + Monitor messages σε 3 tiers:
   - **Tier A Heartbeat** (silent, ~280 chars) — όταν όλα σταθερά
   - **Tier B Delta** (normal, ~700 chars) — όταν άλλαξε TRS ή price ή νέα
   - **Tier C Full Signal** (~1200 chars, 🔥 fire effect αν TRS=5) — όταν ενεργοποιείται setup

Κάθε νέο αξιολογείται ρητά σε ΚΑΙ τα 4 assets με HIGH/MED/LOW/NONE + 1-φράση αιτιολόγηση (News Reasoning Protocol).

### Private chat ΥΠΟΧΡΕΩΤΙΚΟ για effects
Τα message effects (🔥/🎉) δουλεύουν **μόνο σε private chats** με το bot — όχι σε groups/channels. Αν ο στόχος είναι channel/group, τα effects silent-fail-άρουν (auto-detected στο `telegram_state.json → chat_type`).

### Telegram CLI commands (νέα σε v7.1)
```bash
python scripts/telegram_sender.py message "text" [--reply-to ID] [--effect fire|party] [--silent]
python scripts/telegram_sender.py edit <MSG_ID> "new text"
python scripts/telegram_sender.py pin <MSG_ID>
python scripts/telegram_sender.py react <MSG_ID> 🔥
python scripts/telegram_sender.py dashboard            # stdin HTML → edit pinned (or create+pin)
python scripts/telegram_sender.py detect-chat          # one-time bootstrap
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v7.1 | 2026-04-17 | Telegram UX upgrade: pinned Dashboard + stream, 3-tier Monitor, TRS transparency, News Reasoning Protocol, effects/reactions |
| v7.0 | 2026-04-12 | Simplified to 2 schedules, single model (Sonnet), 12 assets |
| v6.0 | 2026-03-29 | Token optimization, pilot mode, shadow trades |
| v5.0 | 2026-03 | Adaptive loop, tiered cycles |
