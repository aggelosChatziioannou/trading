# Narrative Coherence for Telegram Messages — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add narrative memory and story arc tracking to the GOLD TACTIC analyst so every Telegram message builds on the previous one instead of repeating the same snapshot.

**Architecture:** Two changes — (1) a new `narrative_memory.json` data file that persists arc state per asset across cycles and across sessions, (2) edits to `adaptive_analyst.md` that add a Narrative Rules section and update Βήμα 0, Βήμα 15, EOD, and all three TIER message templates.

**Tech Stack:** Markdown prompt editing, JSON file creation. No Python changes required.

---

## Chunk 1: Create `narrative_memory.json` + register it in the data files list

**Spec:** `docs/superpowers/specs/2026-04-02-narrative-coherence-design.md`

### Task 1: Create `narrative_memory.json` with initial state

**Files:**
- Create: `GOLD_TACTIC/data/narrative_memory.json`

- [ ] **Step 1: Create the file**

```json
{
  "last_updated": null,
  "assets": {
    "EURUSD":  { "arc": "WAITING", "arc_since_session": null, "wait_cycles_today": 0, "last_trs": null, "expected_trigger": null, "session_summary": null, "yesterday_summary": null },
    "GBPUSD":  { "arc": "WAITING", "arc_since_session": null, "wait_cycles_today": 0, "last_trs": null, "expected_trigger": null, "session_summary": null, "yesterday_summary": null },
    "NAS100":  { "arc": "WAITING", "arc_since_session": null, "wait_cycles_today": 0, "last_trs": null, "expected_trigger": null, "session_summary": null, "yesterday_summary": null },
    "XAUUSD":  { "arc": "WAITING", "arc_since_session": null, "wait_cycles_today": 0, "last_trs": null, "expected_trigger": null, "session_summary": null, "yesterday_summary": null },
    "BTC":     { "arc": "WAITING", "arc_since_session": null, "wait_cycles_today": 0, "last_trs": null, "expected_trigger": null, "session_summary": null, "yesterday_summary": null },
    "SOL":     { "arc": "WAITING", "arc_since_session": null, "wait_cycles_today": 0, "last_trs": null, "expected_trigger": null, "session_summary": null, "yesterday_summary": null },
    "ETH":     { "arc": "WAITING", "arc_since_session": null, "wait_cycles_today": 0, "last_trs": null, "expected_trigger": null, "session_summary": null, "yesterday_summary": null }
  }
}
```

- [ ] **Step 2: Verify file is valid JSON**

```bash
cd c:/Users/aggel/Desktop/trading
python -c "import json; json.load(open('GOLD_TACTIC/data/narrative_memory.json')); print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add GOLD_TACTIC/data/narrative_memory.json
git commit -m "feat: add narrative_memory.json — initial arc state for all assets"
```

---

### Task 2: Register `narrative_memory.json` in the data files list

**Files:**
- Modify: `GOLD_TACTIC/prompts/adaptive_analyst.md` lines 38-49 (Αρχεία δεδομένων section)

- [ ] **Step 1: Find the data files block**

The block currently reads (lines 38-49):
```
data\scanner_watchlist.json     → Ποια assets αναλύεις
data\emergency_activations.json → Emergency assets
data\live_prices.json           → Τιμές (από price_checker.py)
...
data\session_log.jsonl          → Κύκλοι ιστορικό
```

- [ ] **Step 2: Add `narrative_memory.json` after `session_log.jsonl`**

In `GOLD_TACTIC/prompts/adaptive_analyst.md`, find:
```
data\session_log.jsonl          → Κύκλοι ιστορικό
```
Replace with:
```
data\session_log.jsonl          → Κύκλοι ιστορικό
data\narrative_memory.json      → Arc state + story history ανά asset (cross-session)
```

- [ ] **Step 3: Verify the section looks correct** — read lines 38-52 and confirm `narrative_memory.json` appears

- [ ] **Step 4: Commit**

```bash
git add GOLD_TACTIC/prompts/adaptive_analyst.md
git commit -m "feat: register narrative_memory.json in data files list"
```

---

## Chunk 2: Add NARRATIVE MEMORY section to `adaptive_analyst.md`

This is the new rules section — arc states, transitions, language patterns. It goes after the `## SESSION LOG` section (after line 812) and before `## TELEGRAM FORMAT` (line 814).

### Task 3: Insert NARRATIVE MEMORY section

**Files:**
- Modify: `GOLD_TACTIC/prompts/adaptive_analyst.md` — insert after line 812 (the `---` after SESSION LOG)

- [ ] **Step 1: Find the insertion point**

Line 812 is `---` (the horizontal rule after SESSION LOG). Line 814 is `## TELEGRAM FORMAT`.

- [ ] **Step 2: Insert the NARRATIVE MEMORY section**

In `GOLD_TACTIC/prompts/adaptive_analyst.md`, find:
```
---

## TELEGRAM FORMAT
```
(the `---` that appears right before `## TELEGRAM FORMAT`)

Replace with:
```
---

## NARRATIVE MEMORY — Αφηγηματική Συνέχεια

Το `data\narrative_memory.json` κρατάει το "story arc" κάθε asset. Διαβάζεται στο startup, ενημερώνεται κάθε TIER 2/3 κύκλο, και γράφεται πλήρως στο EOD.

### Arc States

| Arc | Σημαίνει |
|-----|----------|
| `WAITING` | Setup δεν έχει ακόμα trigger |
| `APPROACHING` | TRS αυξάνεται, πλησιάζει trade |
| `ACTIVE` | Trade ανοιχτό |
| `CLOSED_WIN` | Trade έκλεισε με κέρδος σήμερα |
| `CLOSED_LOSS` | Trade έκλεισε με ζημιά σήμερα |
| `EXPIRED` | Setup ακυρώθηκε (ADR > 90%, trend flip, ή EOD) |

### Arc Transitions

```
WAITING     → APPROACHING  : TRS αυξήθηκε κατά ≥ 1 vs προηγούμενο κύκλο
APPROACHING → WAITING      : TRS μειώθηκε ή κριτήριο χάθηκε
APPROACHING → ACTIVE       : Trade ανοίχτηκε
ACTIVE      → CLOSED_WIN   : Trade έκλεισε κερδοφόρα
ACTIVE      → CLOSED_LOSS  : Trade έκλεισε με ζημιά
WAITING/APPROACHING → EXPIRED : ADR > 90% ή trend αντιστράφηκε ή EOD
EXPIRED/CLOSED_*    → WAITING : Νέα ημέρα — reset, session_summary → yesterday_summary
```

**Κανόνας:** Κάθε arc change αναφέρεται στο Telegram, ακόμα και σε TIER 1.

### Narrative Language — Γλώσσα ανά κατάσταση

**WAITING:**
- Κύκλος 1-2: `"Αναμένω [expected_trigger]"`
- Κύκλος 3-5: `"[X]ος κύκλος αναμονής — αγορά δεν έδωσε ακόμα [expected_trigger]"`
- Κύκλος 6+: `"⚠️ [X] κύκλοι αναμονής — αν δεν γίνει [expected_trigger] ως [ΩΡΑ], setup ακυρώνεται"`

**APPROACHING:**
`"Πλησιάζει — TRS [last_trs]→[new_trs], λείπει μόνο [τελευταίο ❌ κριτήριο]"`

**EXPIRED:**
`"Setup ακυρώθηκε — [λόγος]. Νέο setup αν [condition]."`

**Cross-session (αν υπάρχει yesterday_summary):**
`"Χθες: [yesterday_summary]. Σήμερα [τι διαφέρει]."`

### Update Rules (κάθε TIER 2/3 κύκλος — μετά session log)

Για κάθε active asset:
1. Σύγκρινε νέο TRS με `last_trs` → αν αυξήθηκε ≥ 1: arc `WAITING` → `APPROACHING`
2. Αν trade ανοίχτηκε: arc → `ACTIVE`
3. Αν trade έκλεισε: arc → `CLOSED_WIN` ή `CLOSED_LOSS`
4. Αν ADR > 90% ή trend flip: arc → `EXPIRED`
5. Αν arc = `WAITING`: `wait_cycles_today++`
6. Ενημέρωσε `last_trs`, `expected_trigger`, `last_updated`
7. Γράψε αρχείο

### EOD Write (πριν Daily Summary Telegram)

Για κάθε asset γράψε `session_summary`:
```
"[arc outcome] — [1 γραμμή τι έγινε]"
```
Παραδείγματα:
- `"WAITING x6 — BOS δεν ήρθε, ADR εξαντλήθηκε 14:30"`
- `"CLOSED_WIN — IBB Long +$210, TP1+TP2 hit"`
- `"APPROACHING x3 — Setup ακυρώθηκε EOD, TRS έφτασε 3/5"`

### Νέα ημέρα (startup όταν last_updated < σήμερα)

Για κάθε asset:
- `session_summary` → `yesterday_summary`
- `arc` → `WAITING`
- `wait_cycles_today` → 0
- `arc_since_session`, `last_trs`, `expected_trigger`, `session_summary` → null

---

## TELEGRAM FORMAT
```

- [ ] **Step 3: Verify the section was inserted correctly** — read lines 810-870 and confirm the new section appears between SESSION LOG and TELEGRAM FORMAT

- [ ] **Step 4: Commit**

```bash
git add GOLD_TACTIC/prompts/adaptive_analyst.md
git commit -m "feat: add NARRATIVE MEMORY section to adaptive_analyst.md"
```

---

## Chunk 3: Update Βήμα 0 and Βήμα 15

### Task 4: Update Βήμα 0 — read `narrative_memory.json` on startup

**Files:**
- Modify: `GOLD_TACTIC/prompts/adaptive_analyst.md` lines 730-745 (Βήμα 0 block)

- [ ] **Step 1: Find the current Βήμα 0 block**

The block currently ends at:
```
     - total_trades, winning_trades → ΑΝΤΕΓΡΑΨΕ ακριβώς.
```

- [ ] **Step 2: Add narrative_memory read after the portfolio block**

In the Βήμα 0 code block, find:
```
     - total_trades, winning_trades → ΑΝΤΕΓΡΑΨΕ ακριβώς.

1 → Διάβασε scanner_watchlist.json + emergency_activations.json
```

Replace with:
```
     - total_trades, winning_trades → ΑΝΤΕΓΡΑΨΕ ακριβώς.

     📖 NARRATIVE MEMORY:
     Διάβασε data\narrative_memory.json.
     Αν αρχείο δεν υπάρχει → initialize: arc=WAITING, wait_cycles=0 για όλα.
     Αν last_updated < σήμερα (νέα ημέρα):
       → Για κάθε asset: session_summary → yesterday_summary
       → reset: arc=WAITING, wait_cycles_today=0, arc_since_session=null, last_trs=null
     Αν last_updated = σήμερα → φόρτωσε arc + wait_cycles + yesterday_summary ως context.
     ΓΡΑΨΕ εδώ: "Narrative arcs: [ASSET arc wait_cycles], ..." πριν συνεχίσεις.

1 → Διάβασε scanner_watchlist.json + emergency_activations.json
```

- [ ] **Step 3: Verify Βήμα 0 looks correct** — read the section and confirm it flows logically

- [ ] **Step 4: Commit**

```bash
git add GOLD_TACTIC/prompts/adaptive_analyst.md
git commit -m "feat: update Βήμα 0 to read narrative_memory.json on startup"
```

---

### Task 5: Update Βήμα 15 — add narrative_memory update after session log

**Files:**
- Modify: `GOLD_TACTIC/prompts/adaptive_analyst.md` line 764 (Βήμα 15 line)

- [ ] **Step 1: Find Βήμα 15**

Currently:
```
15 → Session log (ΠΑΝΤΑ — κάθε κύκλο)
```

- [ ] **Step 2: Add Βήμα 15b after Βήμα 15**

Find:
```
15 → Session log (ΠΑΝΤΑ — κάθε κύκλο)
16 → PILOT:
```

Replace with:
```
15 → Session log (ΠΑΝΤΑ — κάθε κύκλο)
15b → Narrative memory update (TIER 2/3 μόνο — ΠΑΝΤΑ μετά το session log):
      Για κάθε active asset:
      - Σύγκρινε new_trs vs last_trs → αν αυξήθηκε ≥ 1: WAITING → APPROACHING
      - Αν trade ανοίχτηκε αυτό το cycle → arc = ACTIVE
      - Αν trade έκλεισε → arc = CLOSED_WIN ή CLOSED_LOSS
      - Αν ADR > 90% ή trend flip → arc = EXPIRED
      - Αν arc = WAITING → wait_cycles_today++
      - Ενημέρωσε last_trs, expected_trigger, last_updated
      - Γράψε data\narrative_memory.json
16 → PILOT:
```

- [ ] **Step 3: Verify Βήμα 15b looks correct** — read lines 760-775 and confirm it's in the right place

- [ ] **Step 4: Commit**

```bash
git add GOLD_TACTIC/prompts/adaptive_analyst.md
git commit -m "feat: add Βήμα 15b — narrative_memory update each TIER 2/3 cycle"
```

---

## Chunk 4: Update EOD and TIER Templates

### Task 6: Update EOD — write `session_summary` before Daily Summary

**Files:**
- Modify: `GOLD_TACTIC/prompts/adaptive_analyst.md` lines 162-171 (Daily Summary section)

- [ ] **Step 1: Find the Daily Summary section**

Currently (line 162):
```
### Daily Summary Telegram (σε stop/EOD)
```

- [ ] **Step 2: Add session_summary write BEFORE the Telegram message**

Find:
```
### Daily Summary Telegram (σε stop/EOD)

```html
📊 <b>ΤΕΛΟΣ ΗΜΕΡΑΣ</b>
```

Replace with:
```
### Daily Summary Telegram (σε stop/EOD)

**Πριν στείλεις το Telegram — γράψε `session_summary` στο `narrative_memory.json`:**
Για κάθε asset στο `assets`:
```
"[arc outcome] — [1 γραμμή τι έγινε σήμερα]"
```
Παραδείγματα:
- `"WAITING x6 — BOS δεν ήρθε, ADR εξαντλήθηκε 14:30"`
- `"CLOSED_WIN — IBB Long +$210, TP1+TP2 hit 18:10"`
- `"APPROACHING x3 — Setup ακυρώθηκε EOD, TRS έφτασε 3/5"`
- `"EXPIRED — Trend αντιστράφηκε 4H 13:00, setup ακυρώθηκε"`
- `null` αν asset ήταν skip ολόκληρη την ημέρα

```html
📊 <b>ΤΕΛΟΣ ΗΜΕΡΑΣ</b>
```

- [ ] **Step 3: Verify** — read lines 162-180 and confirm the pre-Telegram step appears

- [ ] **Step 4: Commit**

```bash
git add GOLD_TACTIC/prompts/adaptive_analyst.md
git commit -m "feat: add session_summary write to EOD procedure"
```

---

### Task 7: Update TIER 1 template — arc change notification

**Files:**
- Modify: `GOLD_TACTIC/prompts/adaptive_analyst.md` lines 819-828 (TIER 1 section)

- [ ] **Step 1: Find current TIER 1 template**

```
⚡ PULSE — [HH:MM] EET
💼 [X]€ | Ανοιχτά: [X]/3
📍 EURUSD [price] ([+/-]p) | BTC [price] ([+/-])
→ Τίποτα νέο. Επόμενο: TIER [X] σε [Y]' ([HH:MM])
```

- [ ] **Step 2: Add arc change line + rule**

Find:
```
```html
⚡ PULSE — [HH:MM] EET
💼 [X]€ | Ανοιχτά: [X]/3
📍 EURUSD [price] ([+/-]p) | BTC [price] ([+/-])
→ Τίποτα νέο. Επόμενο: TIER [X] σε [Y]' ([HH:MM])
```

Αν τίποτα δεν κινήθηκε → ΟΧΙ Telegram μήνυμα.
```

Replace with:
```
```html
⚡ PULSE — [HH:MM] EET
💼 [X]€ | Ανοιχτά: [X]/3
📍 EURUSD [price] ([+/-]p) | BTC [price] ([+/-])
[αν arc άλλαξε σε οποιοδήποτε asset:]
📖 [ASSET]: [OLD_ARC]→[NEW_ARC] — [1 γραμμή λόγος]
→ Τίποτα νέο. Επόμενο: TIER [X] σε [Y]' ([HH:MM])
```

Αν τίποτα δεν κινήθηκε ΚΑΙ κανένα arc δεν άλλαξε → ΟΧΙ Telegram μήνυμα.
Αν arc άλλαξε σε έστω 1 asset → στείλε TIER 1 message με την 📖 γραμμή.
```

- [ ] **Step 3: Verify** — read the TIER 1 section and confirm it's correct

- [ ] **Step 4: Commit**

```bash
git add GOLD_TACTIC/prompts/adaptive_analyst.md
git commit -m "feat: add arc change notification to TIER 1 Telegram template"
```

---

### Task 8: Update TIER 2 template — narrative line per asset

**Files:**
- Modify: `GOLD_TACTIC/prompts/adaptive_analyst.md` lines 830-844 (TIER 2 section)

- [ ] **Step 1: Find current TIER 2 template**

```
🟡 [ASSET] — [price] — Ετοιμότητα [X]/5
  ✅ [criteria met]
  ❌ [criteria missing]
  → [DECISION] — [reason]
```

- [ ] **Step 2: Add 📖 narrative line per asset**

Find:
```
🟡 [ASSET] — [price] — Ετοιμότητα [X]/5
  ✅ [criteria met]
  ❌ [criteria missing]
  → [DECISION] — [reason]
```

Replace with:
```
🟡 [ASSET] — [price] — Ετοιμότητα [X]/5
📖 [Narrative γραμμή βάσει arc + wait_cycles + yesterday_summary:]
   • WAITING κύκλος 1-2: "Αναμένω [expected_trigger]"
   • WAITING κύκλος 3-5: "[X]ος κύκλος αναμονής — αγορά δεν έδωσε ακόμα [expected_trigger]"
   • WAITING κύκλος 6+: "⚠️ [X] κύκλοι — αν δεν γίνει [expected_trigger] ως [ΩΡΑ], setup ακυρώνεται"
   • APPROACHING: "Πλησιάζει — TRS [last_trs]→[new_trs], λείπει μόνο [❌ κριτήριο]"
   • EXPIRED: "Setup ακυρώθηκε — [λόγος]."
   • Αν yesterday_summary: προσθεσε "Χθες: [yesterday_summary]. Σήμερα [τι διαφέρει]."
  ✅ [criteria met]
  ❌ [criteria missing]
  → [DECISION] — [reason]
```

- [ ] **Step 3: Verify** — read the TIER 2 section and confirm the 📖 block appears in the right place

- [ ] **Step 4: Commit**

```bash
git add GOLD_TACTIC/prompts/adaptive_analyst.md
git commit -m "feat: add narrative 📖 line to TIER 2 Telegram template"
```

---

### Task 9: Update TIER 3 ZONE 2 — add 📖 ΙΣΤΟΡΙΚΟ block per asset

**Files:**
- Modify: `GOLD_TACTIC/prompts/adaptive_analyst.md` lines 916-961 (ZONE 2 section)

- [ ] **Step 1: Find ZONE 2 asset block**

Currently:
```
📉/📈 <b>[ASSET]</b> — [τιμή] — Ετοιμότητα [X]/5 [emoji]

📊 Alignment:
```

- [ ] **Step 2: Insert 📖 ΙΣΤΟΡΙΚΟ block BEFORE Alignment**

Find:
```
📉/📈 <b>[ASSET]</b> — [τιμή] — Ετοιμότητα [X]/5 [emoji]

📊 Alignment:
```

Replace with:
```
📉/📈 <b>[ASSET]</b> — [τιμή] — Ετοιμότητα [X]/5 [emoji]

📖 <b>ΙΣΤΟΡΙΚΟ:</b> [Narrative βάσει arc + wait_cycles + yesterday_summary:]
   • WAITING κύκλος 1-2: "[X]ος κύκλος αναμονής. Αναμένω [expected_trigger]."
   • WAITING κύκλος 3-5: "[X]ος κύκλος αναμονής σήμερα. TRS κινήθηκε [history]. Αν [trigger] → APPROACHING."
   • WAITING κύκλος 6+: "⚠️ [X] κύκλοι αναμονής. Setup ακυρώνεται αν [trigger] δεν γίνει ως [ΩΡΑ]."
   • APPROACHING: "Πλησιάζει. TRS [last_trs]→[new_trs] — λείπει μόνο [❌ κριτήριο]."
   • Αν yesterday_summary → προσθεσε: "Χθες: [yesterday_summary]. Σήμερα [τι διαφέρει]."

📊 Alignment:
```

- [ ] **Step 3: Verify** — read ZONE 2 section (lines 916-965) and confirm 📖 ΙΣΤΟΡΙΚΟ appears correctly per asset

- [ ] **Step 4: Commit**

```bash
git add GOLD_TACTIC/prompts/adaptive_analyst.md
git commit -m "feat: add 📖 ΙΣΤΟΡΙΚΟ block to TIER 3 ZONE 2 per asset"
```

---

## Chunk 5: Final verification

### Task 10: End-to-end prompt coherence check

- [ ] **Step 1: Read the full ΣΕΙΡΑ ΚΥΚΛΟΥ section (lines 726-772)** and verify Βήμα 0 and Βήμα 15b are in the right order and the narrative update fits the flow

- [ ] **Step 2: Read the full TELEGRAM FORMAT section** and verify TIER 1, TIER 2, and TIER 3 ZONE 2 all have narrative blocks, and they're consistent in language/format

- [ ] **Step 3: Read the NARRATIVE MEMORY section** and verify it's complete and doesn't contradict anything else in the prompt

- [ ] **Step 4: Validate narrative_memory.json is still valid JSON**

```bash
cd c:/Users/aggel/Desktop/trading
python -c "import json; d=json.load(open('GOLD_TACTIC/data/narrative_memory.json')); print(f'Assets: {list(d[\"assets\"].keys())}')"
```
Expected: `Assets: ['EURUSD', 'GBPUSD', 'NAS100', 'XAUUSD', 'BTC', 'SOL', 'ETH']`

- [ ] **Step 5: Final commit**

```bash
git add GOLD_TACTIC/prompts/adaptive_analyst.md GOLD_TACTIC/data/narrative_memory.json
git commit -m "feat: narrative coherence complete — arc tracking + story-driven Telegram messages"
```
