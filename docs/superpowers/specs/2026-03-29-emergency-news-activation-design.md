# Emergency News Activation — Design Spec
**Date:** 2026-03-29
**Status:** Approved
**System:** GOLD TACTIC v5.0 — Analyst Enhancement

---

## Overview

The Analyst currently analyzes only assets decided by the Scanner (`active_today` in `scanner_watchlist.json`). This feature allows the Analyst to detect breaking/extraordinary news during its 20-minute cycle and activate a new asset for full analysis — even if the Scanner had skipped it or it wasn't in the core 5.

---

## Scope

**In scope:**
- Detection of breaking news during Analyst cycle
- Activation of skipped core assets (EURUSD, GBPUSD, NAS100, SOL, BTC) via breaking news
- Activation of extended assets (XAUUSD, ETH, NVDA, AAPL, TSLA, MSFT, GOOGL, AMD, INTC, COIN, PLTR, AMZN, META)
- Persistence across Analyst cycles until next Scanner run
- Cleanup after Scanner run (unless open trade)

**Out of scope:**
- Scanner detecting breaking news (Scanner runs only 2x/day — Analyst handles real-time)
- Automatic trade execution without TRS gate
- User confirmation/approval flow (full activation, no escalation)

---

## Architecture

### New File: `GOLD_TACTIC/data/emergency_activations.json`

```json
{
  "last_seen_scan_timestamp": "2026-03-30 08:09",
  "activations": [
    {
      "asset": "XAUUSD",
      "activated_at": "2026-03-30 11:20",
      "reason": "Fed emergency 50bp cut — USD shock, XAUUSD breaking $2400 resistance",
      "headline": "Fed announces emergency inter-meeting rate cut",
      "source": "Reuters",
      "open_trade": false
    }
  ]
}
```

**Fields:**
| Field | Type | Purpose |
|-------|------|---------|
| `last_seen_scan_timestamp` | string | Last Scanner timestamp seen by Analyst — used to detect Scanner runs. Updated at end of every Analyst cycle. |
| `asset` | string | Ticker symbol |
| `activated_at` | string | EET timestamp of activation |
| `reason` | string | LLM reasoning (2+ sentences required) |
| `headline` | string | The triggering news headline |
| `source` | string | News source |
| `open_trade` | boolean | `true` when a trade is open on this asset; `false` when no trade or trade closed |

**`open_trade` lifecycle:**
- Set to `true`: Analyst updates this field immediately after executing a trade entry on an emergency asset (between step 7 analysis and step 8 Telegram)
- Set to `false`: Analyst updates this field immediately after closing a trade (TP hit, SL hit, or EOD close) on an emergency asset
- Both updates happen in-cycle, writing to `emergency_activations.json` before the next cycle begins

**Cap:** Maximum 2 simultaneous emergency activations. If already at 2, the Analyst notes the news but does NOT activate. Prevents overloading a 20-minute cycle.

**No other files are modified** — Scanner writes only to `scanner_watchlist.json` and never touches `emergency_activations.json`.

---

## Breaking News Detection

### When it runs
During the NEWS STEP of every Analyst cycle, immediately after news_feed.json is read. Runs on all news regardless of day/mode — weekend filtering is handled naturally by Question 3 (WORTHWHILE NOW).

### Three-question LLM judgment gate

The Analyst evaluates **each news item** against:

1. **IMPACT ≥ 7/10** — Is this extraordinary?
   - Examples that qualify: Fed emergency action, war escalation, exchange circuit breaker, major earnings surprise, central bank intervention
   - Examples that don't qualify: routine data releases, analyst upgrades, general market commentary

2. **ASSET MAPPING** — Is there a clear primary asset affected AND a clear directional bias (LONG/SHORT)?
   - Must identify specific ticker, not just "markets generally"
   - Must imply direction: "USD collapse" → XAUUSD LONG, "exchange halted" → asset SHORT

3. **WORTHWHILE NOW** — Is the asset tradeable at this moment?
   - Market hours (forex 24/5, crypto 24/7, equities/NAS100 during session only)
   - On weekends: forex and equity questions auto-fail here — only crypto can pass
   - Estimated ADR room available
   - Sufficient liquidity

**All 3 must be YES.** If the Analyst cannot write 2 concrete sentences explaining the direction + catalyst, it does NOT activate.

### Eligible assets
- Any of the 5 core assets currently in `skip_today`
- Extended list: XAUUSD, ETH, NVDA, AAPL, TSLA, MSFT, GOOGL, AMD, INTC, COIN, PLTR, AMZN, META
- Any asset explicitly named in news with clear price impact

### Chart generation for emergency assets
Emergency assets may not have pre-generated charts. The Analyst calls `chart_generator.py [ASSET]` at step 7 to generate charts on-the-fly. `price_checker.py` uses yfinance and supports any valid Yahoo Finance ticker — no additional configuration needed for extended assets.

---

## Analyst Cycle Flow (Updated)

```
CYCLE START
│
├─ 1. Read scanner_watchlist.json
│       → active_today, scan_timestamp, nas100_afternoon
│
├─ 2. Read emergency_activations.json
│       → activations list, last_seen_scan_timestamp
│
├─ 3. Has scan_timestamp changed vs last_seen_scan_timestamp?
│   ├─ YES → CLEANUP:
│   │   For each emergency asset:
│   │   • IN Scanner's active_today → REMOVE from emergency (now handled by Scanner normally)
│   │   • NOT in active_today AND open_trade=false → REMOVE
│   │   • NOT in active_today AND open_trade=true → KEEP (trade open, can't abandon)
│   │   • NAS100 special rule: if nas100_afternoon=true AND time < 16:30 EET
│   │     → KEEP even if NOT in active_today (afternoon evaluation pending)
│   │   Update last_seen_scan_timestamp = current scan_timestamp
│   └─ NO → skip cleanup
│
├─ 4. final_active = scanner active_today + [remaining emergency activations]
│
├─ 5. Run price_checker.py for final_active assets
│
├─ 6. NEWS STEP → Breaking News Scan
│   If emergency cap not reached (< 2 activations):
│     For each news item in news_feed.json:
│       Apply 3-question gate → if all YES:
│       • Write activation to emergency_activations.json
│       • Add asset to final_active for THIS cycle
│       • Queue 🚨 BREAKING ACTIVATION Telegram block
│
├─ 7. Analyze ONLY final_active assets (full TRS, charts, levels)
│       For emergency assets not in charts_meta.json:
│       → Run chart_generator.py [ASSET] to generate charts on-the-fly
│       If trade executed on emergency asset → set open_trade=true in emergency_activations.json
│
├─ 8. If any trade closed on emergency asset → set open_trade=false in emergency_activations.json
│
└─ 9. Send Telegram
```

---

## Trade Entry Gate for Emergency Assets

Emergency-activated assets have a **stricter entry threshold** than regular active assets:

| TRS Score | Regular Asset | Emergency Asset |
|-----------|--------------|-----------------|
| 5/5 🔥 | TRADE | TRADE |
| 4/5 🟢 | TRADE | **MONITOR ONLY** |
| 3/5 🟡 | Wait | Wait |
| 0-2/5 ⬜ | Skip | Skip |

Rationale: Emergency activation overrides Scanner's judgment — requires maximum confidence before committing 100 EUR.

---

## Telegram Format

### When emergency activation fires (sent BEFORE regular analysis):

```
🚨 BREAKING ACTIVATION — XAUUSD

📰 "Fed announces emergency inter-meeting 50bp cut" (Reuters, 11:18)
🧠 Reasoning: USD collapse imminent → Gold safe-haven bid + $2400 breakout
📈 Direction: LONG — strong bullish catalyst
⚠️ Override: Scanner had XAUUSD as skip — this news changes the picture

→ Κάνω full TRS analysis τώρα...
━━━━━━━━━━━━━━━━━━━━━━
[full TRS analysis for XAUUSD follows]
```

### Analyst footer (every cycle) — updated to include emergency label:

```
✅ Active: EURUSD (scanner) | BTC (scanner) | XAUUSD 🚨 (breaking news)
⏭️ Skipped: GBPUSD (ADR 75%) | NAS100 (IBB 16:30) | SOL (follows BTC)
```

### When cleanup removes an emergency asset (after Scanner run):

```
🧹 Emergency cleared: XAUUSD — Scanner δεν επιβεβαίωσε, no open trade
```

---

## Files Changed

| File | Change |
|------|--------|
| `data/emergency_activations.json` | **NEW** — created with empty `activations: []` and `last_seen_scan_timestamp: ""` on first run |
| `prompts/cowork_analyst.md` | Add Emergency Activation section (cycle flow, 3-question gate, TRS gate, open_trade lifecycle) |
| `prompts/cowork_v5_upgrade.md` | Update Analyst cycle flow + Telegram footer format to include 🚨 emergency label |

No changes to: `scanner_watchlist.json` format, `cowork_scanner.md`, any Python scripts.

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Same asset activated twice | Deduplicate — update `activated_at` and `headline` of existing entry, don't add duplicate |
| Emergency asset gets open trade, then Scanner runs | `open_trade=true` → kept in emergency list until trade closes, then removed on next Scanner run check |
| Scanner runs and confirms same asset | Remove from emergency, Scanner now owns it in `active_today` |
| No news in news_feed.json | Skip breaking news scan silently |
| Already at 2 emergency activations | Note the news in Telegram but do not activate: "⚠️ Emergency cap reached (2/2) — [headline] noted but not activated" |
| NAS100 breaking news, nas100_afternoon=true, time < 16:30 EET | Activate but note: "monitoring only until IBB window 16:30 EET, entry only if setup forms" |
| NAS100 breaking news outside IBB window AND nas100_afternoon=false | Activate with note: "outside IBB window — monitoring only, no entry today" |
| Emergency asset, XAUUSD or other not in charts_meta.json | Run chart_generator.py on-the-fly for that asset; price_checker.py supports any Yahoo Finance ticker natively |
| Weekend: forex/equity breaking news | Question 3 (WORTHWHILE NOW) fails for forex/equity → no activation. Crypto only can pass on weekends. |
| trade closes same cycle it opened | Steps 7 and 8 handle both: open_trade set true at entry, set false at close, both in same cycle write |
