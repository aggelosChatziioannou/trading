# Narrative Coherence for Telegram Messages
**Date:** 2026-04-02  
**Status:** Approved  
**Scope:** GOLD TACTIC Adaptive Analyst — Telegram message coherence upgrade

---

## Problem

The system sends TIER 1/2/3 Telegram messages every cycle, but each message is a standalone snapshot. When nothing significant changes, consecutive messages repeat the same analysis verbatim. The analyst has no "voice" — it doesn't reference what it said before, doesn't track how many cycles it's been waiting, and doesn't connect today's setup to yesterday's outcome.

---

## Solution Overview

Two changes working together:

1. **`data/narrative_memory.json`** — lightweight persistent file that carries "story arc" state per asset across cycles and across sessions
2. **Narrative Rules section in `adaptive_analyst.md`** — instructs the agent how to build and express narrative evolution in every tier

---

## Component 1: `narrative_memory.json`

### Location
`GOLD_TACTIC/data/narrative_memory.json`

### Structure

```json
{
  "last_updated": "2026-04-02 21:30 EET",
  "assets": {
    "EURUSD": {
      "arc": "WAITING",
      "arc_since_session": "09:00",
      "wait_cycles_today": 6,
      "last_trs": 2,
      "expected_trigger": "BOS κλείσιμο < 1.1480",
      "session_summary": "Setup εμφανίστηκε 09:00, έφτασε TRS 3/5, ακυρώθηκε ADR > 90% στις 14:30"
    },
    "NAS100": {
      "arc": "CLOSED_WIN",
      "last_trade": "LONG @ 22953, +$210, έκλεισε 17:45",
      "session_summary": "IBB breakout confirmed 17:32, TP1 hit 18:10, runner έκλεισε EOD"
    }
  }
}
```

### Arc States

| Arc | Σημαίνει |
|-----|----------|
| `WAITING` | Setup δεν έχει ακόμα trigger |
| `APPROACHING` | TRS αυξάνεται, πλησιάζει trade |
| `ACTIVE` | Trade ανοιχτό |
| `CLOSED_WIN` | Trade έκλεισε με κέρδος σήμερα |
| `CLOSED_LOSS` | Trade έκλεισε με ζημιά σήμερα |
| `EXPIRED` | Setup ακυρώθηκε (ADR, trend flip, EOD) |

### Arc Transitions

```
WAITING     → APPROACHING  : TRS αυξήθηκε κατά ≥ 1 vs προηγούμενο κύκλο
APPROACHING → WAITING      : TRS μειώθηκε ή κριτήριο χάθηκε
APPROACHING → ACTIVE       : Trade ανοίχτηκε
ACTIVE      → CLOSED_WIN   : Trade έκλεισε κερδοφόρα
ACTIVE      → CLOSED_LOSS  : Trade έκλεισε με ζημιά
WAITING/APPROACHING → EXPIRED : ADR > 90% ή trend αντιστράφηκε ή EOD
EXPIRED/CLOSED_*    → WAITING : Νέα ημέρα — reset arc, διατήρησε session_summary ως yesterday_summary
```

**Κανόνας:** Κάθε arc change αναφέρεται πάντα στο Telegram, ακόμα και σε TIER 1.

---

## Component 2: Narrative Rules

### Story Arcs — Γλώσσα ανά κατάσταση

**WAITING:**
- Κύκλος 1-2: `"Αναμένω [trigger]"`
- Κύκλος 3-5: `"[X]ος κύκλος αναμονής — αγορά δεν έδωσε ακόμα [trigger]"`
- Κύκλος 6+: `"⚠️ [X] κύκλοι αναμονής — αν δεν γίνει [trigger] ως [ΩΡΑ], setup ακυρώνεται"`

**APPROACHING:**
`"Πλησιάζει — TRS [πριν]→[τώρα], λείπει μόνο [τελευταίο ❌ κριτήριο]"`

**EXPIRED:**
`"Setup ακυρώθηκε — [λόγος]. Νέο setup αν [condition]."`

**Cross-session (από yesterday_summary):**
`"Χθες: [session_summary]. Σήμερα [τι διαφέρει — ADR, RSI, news context]"`

### Per-TIER Εφαρμογή

**TIER 1** — μόνο αν arc άλλαξε, 1 γραμμή:
```
📖 EURUSD: WAITING→APPROACHING — TRS 2→3, λείπει μόνο BOS
```
Αν arc δεν άλλαξε → καμία narrative γραμμή στο TIER 1.

**TIER 2** — πάντα, 1-2 γραμμές per asset πριν το ΑΠΟΦΑΣΗ:
```
📖 EURUSD (3ος κύκλος αναμονής): Αγορά δεν έδωσε ακόμα BOS < 1.1480.
   Χθες ίδιο setup ακυρώθηκε ADR > 90%. Σήμερα ADR 41% — χώρος υπάρχει.
```

**TIER 3** — πλήρες `📖 ΙΣΤΟΡΙΚΟ` block στη ZONE 2 per asset, πριν τα ✅/❌:
```
📖 ΙΣΤΟΡΙΚΟ: 3ος κύκλος αναμονής σήμερα. TRS κινήθηκε 1→2→2.
   Χθες: Setup έφτασε 3/5, ακυρώθηκε ADR > 90% στις 14:30.
   Σήμερα: ADR 41%, χώρος υπάρχει. Αν BOS < 1.1480 → APPROACHING.
```

---

## Lifecycle του `narrative_memory.json`

### Βήμα 0 — Startup (επέκταση)

```
Διάβασε narrative_memory.json
→ Για κάθε active asset: φόρτωσε arc + wait_cycles_today + session_summary
→ Αν αρχείο δεν υπάρχει → initialize: arc=WAITING, wait_cycles=0 για όλα
→ Αν νέα ημέρα (last_updated < σήμερα):
   → Για κάθε asset: session_summary → yesterday_summary, reset arc=WAITING, wait_cycles=0
```

### Κάθε κύκλος TIER 2/3 — Βήμα 15 (επέκταση)

Μετά το session_log entry:
```
→ Update narrative_memory.json:
   - arc per asset (αν άλλαξε)
   - wait_cycles_today++ αν arc=WAITING
   - last_trs per asset
   - expected_trigger per asset (από TRS analysis)
   - last_updated = τώρα
```

### EOD / STOP — Πριν το Daily Summary

```
→ Για κάθε asset γράψε session_summary:
   Format: "[arc outcome] — [1 γραμμή τι έγινε]"
   Π.χ.: "WAITING x6 — BOS δεν ήρθε, ADR εξαντλήθηκε 14:30"
         "CLOSED_WIN — IBB Long +$210, TP1+TP2 hit"
         "APPROACHING x3 — Setup ακυρώθηκε EOD, TRS έφτασε 3/5"
```

---

## Αρχεία που αλλάζουν

| Αρχείο | Αλλαγή |
|--------|--------|
| `GOLD_TACTIC/data/narrative_memory.json` | Νέο αρχείο (δημιουργία + initialization) |
| `GOLD_TACTIC/prompts/adaptive_analyst.md` | 4 σημεία: νέο Narrative Rules section, Βήμα 0, Βήμα 15, EOD block |

**Κανένα άλλο αρχείο δεν αλλάζει.**

---

## Τι ΔΕΝ αλλάζει

- Η λογική των TIER cycles (timing, escalation triggers)
- Τα TRS κριτήρια και η trade execution
- Η δομή του session_log.jsonl
- Τα scripts (telegram_sender.py, quick_scan.py κ.λπ.)
- Οι 10 κανόνες που δεν αλλάζουν ποτέ
