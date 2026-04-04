# 24/7 Adaptive Schedule + Smart Cold Start — Design Spec

**Date:** 2026-04-05
**Author:** Aggelos + Claude
**Status:** APPROVED

## Problem

System completely stops outside 08:00-22:00 weekday / 10:00-20:00 weekend.
This means: no overnight crypto monitoring, no Asia range tracking,
no awareness of what happened while the user slept. Additionally, if the
system is restarted after being offline for hours/days, it starts blind.

## Solution: 5-Zone 24/7 + Smart Cold Start

### 5-Zone Schedule

| Zone | Hours (EET) | Interval | Assets | Max Tier | Trades? |
|------|------------|----------|--------|----------|---------|
| NIGHT | 22:00-04:00 | 60min | Crypto only | TIER 1 | Only TRS 5/5 crypto |
| ASIA | 04:00-08:00 | 30min | Crypto + Forex watch | TIER 1-2 | Crypto OK, Forex NO |
| LONDON | 08:00-15:30 | 10min | ALL | TIER 1-3 | Full trading |
| NY | 15:30-20:00 | 10min | ALL | TIER 1-3 | Full trading |
| EVENING | 20:00-22:00 | 20min | Crypto + trade mgmt | TIER 1-2 | Close only, no new |

### Zone Rules

**NIGHT (22:00-04:00):** Watchdog mode. Crypto pulse check every hour.
Trade ONLY on extreme conditions (TRS 5/5 + RSI <20 or >80).
Accumulates overnight_summary data for morning digest.

**ASIA (04:00-08:00):** Range building. Tracks Asia H/L for forex (no trades).
Crypto mean reversion OK. At 07:30 sends Morning Digest with overnight summary.

**LONDON (08:00-15:30):** Full scanner at 08:00 with overnight + Asia data.
Peak trading mode. All strategies active. 10-min intervals.

**NY (15:30-20:00):** Afternoon scanner at 15:30. NAS100 + XAUUSD activate.
Peak trading mode. All strategies active. 10-min intervals.

**EVENING (20:00-22:00):** Wind down. No new trades. Manage open positions.
Crypto monitoring continues. EOD close forex/indices at 21:40.
Crypto can stay overnight if P&L positive.

### Morning Digest (07:30 EET)

Accumulated from NIGHT+ASIA zones:
- Crypto overnight performance (BTC, SOL price changes)
- Asia ranges for forex (EUR, GBP H/L established)
- Overnight news summary
- Regime prediction based on Asia range size

### Smart Cold Start

On startup, detect gap since last cycle:

| Gap | Action |
|-----|--------|
| < 2 hours | Resume normally |
| 2-8 hours | Quick catch-up: scan + news + current zone |
| 8-24 hours | Full scanner immediately + digest |
| > 24 hours | FULL RESET: scanner + portfolio check + news |
| > 7 days | FRESH START: treat as brand new |

Cold start sends Restart Card to Telegram with offline duration and orphaned trade status.

### Orphaned Trade Detection

If system stopped with open trades:
- On restart → check portfolio.json → find open_trades
- Immediately run TIER 3a: check prices, P&L, TP/SL proximity
- If trade > 24h old → suggest close (stale position)

## Implementation

### analyst_runner.py changes:

Replace `is_active_window()` with `get_zone()`:
```python
def get_zone(now=None):
    """Returns (zone_name, interval_minutes, allowed_assets, max_tier, can_trade)"""
    # NIGHT: 22:00-04:00 → ("NIGHT", 60, ["BTC","SOL"], 1, crypto_only)
    # ASIA:  04:00-08:00 → ("ASIA", 30, ["BTC","SOL","EURUSD","GBPUSD"], 2, crypto_only)
    # LONDON: 08:00-15:30 → ("LONDON", 10, ALL, 3, True)
    # NY: 15:30-20:00 → ("NY", 10, ALL, 3, True)
    # EVENING: 20:00-22:00 → ("EVENING", 20, ["BTC","SOL"]+open_trades, 2, close_only)

def cold_start_check():
    """Detect gap, decide bootstrap action, handle orphaned trades."""

def compute_next_interval(zone, tier_hint, has_open_trade):
    """Dynamic interval based on zone + market state."""
```

### telegram_state.py changes:

Add overnight_summary accumulator:
```python
def accumulate_overnight(state, scan_data):
    """Add to overnight buffer during NIGHT/ASIA zones."""

def format_morning_digest(state):
    """Generate morning digest card from accumulated data."""

def clear_overnight(state):
    """Reset after morning digest sent."""
```

### adaptive_analyst.md changes:

- Replace active window references with zone system
- Add zone-specific rules (what scripts/strategies allowed per zone)
- Add cold start protocol
- Add Morning Digest card format
- Add Restart Card format

## Files

| File | Change |
|------|--------|
| `scripts/analyst_runner.py` | get_zone(), cold_start_check(), compute_next_interval() |
| `scripts/telegram_state.py` | overnight accumulator + morning digest |
| `prompts/adaptive_analyst.md` | Zone rules + cold start + new cards |
| `scripts/test_analyst_runner.py` | New tests for zones + cold start |
