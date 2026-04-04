# Telegram Card System — Design Spec

**Date:** 2026-04-04
**Author:** Aggelos + Claude
**Status:** APPROVED

## Problem

Telegram messages are long walls of text (2,000-4,500 chars) that repeat the same information every cycle. The user reads on mobile, wants to know in 3 seconds: "Is a trade coming?" Messages feel spammy and redundant.

## Solution: Card-Based Messaging

Replace monolithic TIER messages with small, focused **cards** — each card has one purpose, one topic, and fits on one mobile screen.

---

## 5 Card Types

### 1. Status Card (every 30 minutes, ALWAYS)

**Purpose:** "The bot is alive. Here's the snapshot."
**Max:** 5 lines / ~250 chars

```html
📊 14:30 | 💼 998€ | 0/3 trades
📍 EUR +3p | BTC -$120 | NAS σταθ.
🎯 Κοντά σε trade: EURUSD (TRS 4/5 — ~30')
💰 Drawdown: SAFE ✅
→ 15:00
```

**Rules:**
- Line 1: Time + balance + open trades
- Line 2: Price deltas only (not absolute prices)
- Line 3: **PROXIMITY SUMMARY** — which assets are closest to trade + estimated time
- Line 4: Drawdown level (only if not SAFE)
- Line 5: Next update time
- Balance: ONLY if changed vs last card (trade open/close)
- If nothing changed and no assets near trade: `🎯 Κοντά σε trade: κανένα`

### 2. Asset Card (only when asset CHANGED)

**Purpose:** "This specific asset moved. Here's what it means for a trade."
**Max:** 8 lines / ~400 chars
**Sent:** Only when TRS changed, or price moved > threshold, or arc changed

```html
🎯 EURUSD — TRS 3→4 ⬆️

📍 1.0870 (+25p) | ADR: 65%
📖 Πλησιάζει! Λείπει μόνο:
   ❌ BOS στο 1.0823 (47 pips μακριά)

⏱️ Εκτίμηση: ~30-60 λεπτά
🔥 Αν σπάσει 1.0823 → TRADE LONG
[▓▓▓▓▓▓▓▓░░] 80% — σχεδόν εκεί!
```

**Proximity Meter (ΥΠΟΧΡΕΩΤΙΚΟ σε κάθε Asset Card):**

| TRS | Meter | Label | Emoji |
|-----|-------|-------|-------|
| 0-1/5 | `[░░░░░░░░░░]` 0-20% | Μακριά | ⬜ |
| 2/5 | `[▓▓░░░░░░░░]` 20-40% | Νωρίς | 🟡 |
| 3/5 | `[▓▓▓▓▓░░░░░]` 40-60% | Μισός δρόμος | 🟡 |
| 4/5 | `[▓▓▓▓▓▓▓▓░░]` 60-80% | Πλησιάζει! | 🟢 |
| 5/5 | `[▓▓▓▓▓▓▓▓▓▓]` 100% | TRADE! | 🔥 |

Modifier: ADR > 85% → -20% | Correlation block → 0% | Breaking news → +10%

**Time Estimation Logic:**

| Condition | Estimate |
|-----------|----------|
| TRS 4/5, trigger < 10 pips away | "~15-30 λεπτά" |
| TRS 4/5, trigger 10-30 pips away | "~30-60 λεπτά" |
| TRS 3/5, approaching | "~1-2 ώρες" |
| TRS 3/5, stable | "~2-4 ώρες (αν κινηθεί)" |
| TRS 2/5 | "Δεν βλέπω trade σύντομα" |
| TRS 0-1/5 | Δεν εμφανίζεται (no card) |

**Narrative Escalation (wait cycle counter):**

| Cycles | Message |
|--------|---------|
| 1-2 | "Αναμένω {trigger}" |
| 3-4 | "{N}ος κύκλος — τιμή {X}p μακριά" |
| 5-6 | "⚠️ {N}ος κύκλος — αρχίζει να αργεί" |
| 7+ | "❌ {N}ος κύκλος — πιθανά ακυρώνεται" |

**Expired asset:** One final card, then silence:
```html
❌ GBPUSD — Ακυρώθηκε
📖 ADR 92% — δεν υπάρχει χώρος
→ Δεν ξαναστέλνω μέχρι νέο scanner
```

### 3. News Card (only on HIGH impact news)

**Purpose:** "A news event just happened. Here's what it means for YOUR assets."
**Max:** 6 lines / ~300 chars
**Sent:** Immediately when HIGH impact news detected

```html
📰 Fed: "Παύση επιτοκίων" (Reuters)

→ EURUSD ⬆️ +8p | XAUUSD ⬆️ +$12
→ USD αδυναμία — ευνοεί LONG EUR/GBP/XAU

💡 Αν SHORT EUR → ΠΡΟΣΟΧΗ
⚡ Αν TRS ≥ 4 → πιθανό trigger!
```

**Format rules:**
- Line 1: Headline + source (max 60 chars)
- Line 2: **ASSET IMPACT** — immediate price effect per asset with direction arrows
- Line 3: **Plain Greek explanation** — what it means overall
- Line 4: **Action alert** — what it means for current/potential trades
- NO long summaries, NO educational "lessons"
- ONLY HIGH impact news get a card. MEDIUM/LOW: mentioned in Status Card only

### 4. Trade Card (only when trade is open)

**Purpose:** "Your trade is running. Here's how it's going."
**Max:** 8 lines / ~400 chars
**Sent:** Every 30' while trade open, or on significant P&L change

```html
🔴 GBPUSD SHORT — +22p ✅ ΒΕΛΤΙΩΝΕΤΑΙ

📍 Entry: 1.3312 → Τώρα: 1.3290
🎯 TP1: 1.3247 [████░░░░░░] 56%
🛡️ SL: 1.3355 (αρχικό, ρίσκο: 12.9€)
💰 P&L: +6.60€ | Ρίσκο: 12.9€

⏱️ Εκτίμηση TP1: ~30-60 λεπτά
💡 Momentum ισχυρό — ΚΡΑΤΑΜΕ
```

**When to send Trade Card:**
- Every 30' (replaces normal Status Card frequency)
- If P&L changed > 10 pips
- If price within 30% of TP1 or SL
- If new contrary news arrived
- On TP1/TP2 hit (celebration card)
- On SL hit (loss card)

**Trade TP1 hit card:**
```html
🎉 GBPUSD — TP1 HIT! +39p

📍 1.3312→1.3273 | Κλείσαμε 50%
💰 +11.70€ κλειδωμένα!
🛡️ SL → Breakeven (μηδέν ρίσκο)
→ Runner: 50% τρέχει ακόμα → TP2 1.3182
```

### 5. Scanner Card (2x daily: 08:00 + 15:30)

**Purpose:** "Here's today's game plan."
**Max:** 20 lines / ~800 chars
**Sent:** Morning (08:00/10:00) and afternoon (15:30)

```html
🔍 SCANNER ΠΡΩΙΝΟΣ — Τρίτη 08:00

⭐ TOP: EURUSD SHORT (Score 8/10)
📈 BTC LONG (Score 7/10)
📈 SOL LONG (Score 7/10)
❌ GBPUSD, NAS100, XAUUSD, ETH

📅 15:30 US NFP — προσοχή EUR/GBP/XAU
📊 Crypto Fear: 42 (Fear) | Markets: 51

💲 DXY: 100.25 BEAR → EUR/GBP ⬆️ | XAU ⬆️

💼 998€ | Streak: 2W | Μήνας: 21.6/100€
→ Πρώτος analyst κύκλος σε 15'
```

**Afternoon scanner:**
```html
🔍 SCANNER 15:30 — ΑΛΛΑΓΕΣ

🆕 NAS100 ΕΝΕΡΓΟΠΟΙΗΘΗΚΕ (IBB window 16:30)
📈 EURUSD: παραμένει ✅ (ADR 65%)
📉 BTC: αδύναμο σήμερα (ADR 88%)
→ Πρώτος NY κύκλος σε 15'
```

---

## Card Sending Rules

### Timing

| Event | Cards Sent | Max Messages |
|-------|-----------|-------------|
| Every 30' (quiet) | Status Card only | 1 |
| Every 30' (trade open) | Status + Trade | 2 |
| Asset changed | Status + Asset Card(s) | 3 max |
| Breaking news | News Card (immediate) | 1 |
| Scanner | Scanner Card | 1 |
| Trade opened | Trade Card | 1 |
| Trade closed | Trade close Card | 1 |

### Deduplication Rules

- **Same asset, same TRS, same arc:** No Asset Card (mentioned in Status only)
- **Same news already sent:** No duplicate News Card
- **Trade P&L < 10 pips change:** No Trade Card update (wait for next 30' cycle)
- **Status Card identical to last:** Still send (user wants heartbeat every 30')

### Message Ordering (when multiple cards)

1. News Card (if breaking) — URGENT first
2. Trade Card (if active) — P&L important
3. Asset Cards (changed only) — opportunities
4. Status Card — always last (summary)

---

## Proximity & Time Estimation System

### Proximity Score Formula

```
base_proximity = (TRS / 5) * 100

modifiers:
  ADR > 85% AND regime != TRENDING → -20%
  correlation_block → set to 0%
  adr_block → set to 0%
  trigger_distance < 10 pips → +10%
  breaking_news_supports → +10%
  CHOPPY regime → -30%

final_proximity = clamp(base_proximity + modifiers, 0, 100)
```

### Time Estimation Rules

```python
def estimate_trade_time(trs, trigger_distance_pips, regime, adr_pct):
    if trs >= 5:
        return "ΤΩΡΑ — trade ready!"
    if trs == 4 and trigger_distance_pips < 10:
        return "~15-30 λεπτά"
    if trs == 4:
        return "~30-60 λεπτά"
    if trs == 3 and regime == "TRENDING":
        return "~1-2 ώρες"
    if trs == 3:
        return "~2-4 ώρες (αν κινηθεί)"
    if trs == 2:
        return "Δεν βλέπω σύντομα"
    return None  # Don't show for TRS 0-1
```

---

## Data Files

### `data/last_telegram_state.json` (existing, enhanced)

Add fields:
```json
{
  "last_card_type": "status",
  "last_asset_cards_sent": {"EURUSD": "2026-04-04 14:30 EET"},
  "asset_wait_cycles": {"EURUSD": 3, "BTC": 1},
  "last_trade_card_pnl": 0.0,
  "cards_sent_today": 12,
  "expired_assets": ["GBPUSD"]
}
```

### Expired assets: silence after 1 final card
Once an asset sends an "expired" card, it's added to `expired_assets` list. No more Asset Cards until next scanner resets the list.

---

## Files to Modify

| File | Action | What |
|------|--------|------|
| `prompts/adaptive_analyst.md` | REPLACE | All TIER 1/2/3 Telegram format sections → Card formats |
| `scripts/telegram_state.py` | ENHANCE | Add proximity calc, time estimation, card type tracking |
| `scripts/trs_calculator.py` | ENHANCE | Add proximity_score and estimated_time to output |

## Verification

1. Simulate 5 Status Cards in a row → verify 3-5 lines each, no repeat
2. Simulate TRS 3→4 change → verify Asset Card with proximity meter + time estimate
3. Simulate breaking news → verify News Card with per-asset impact arrows
4. Simulate Trade Card every 30' → verify P&L delta shown
5. Verify on actual Telegram mobile client → fits one screen per card?
6. Verify expired asset sends 1 card then goes silent
