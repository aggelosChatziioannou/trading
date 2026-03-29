# Emergency News Activation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow the GOLD TACTIC Analyst to detect breaking news during its 20-minute cycle and activate a new asset for full analysis, overriding the Scanner's `active_today` list when warranted.

**Architecture:** A new `emergency_activations.json` file serves as the Analyst's private notepad — the Scanner never touches it. At each cycle start, the Analyst merges Scanner's `active_today` with any emergency activations, running cleanup whenever it detects a new Scanner run via `last_seen_scan_timestamp` comparison. Changes are purely prompt-based (two `.md` instruction files); no Python scripts are modified.

**Tech Stack:** JSON (data file), Markdown (Cowork prompt instructions for the LLM Analyst agent)

---

## Chunk 1: Data File + cowork_analyst.md

### Task 1: Create emergency_activations.json

**Files:**
- Create: `GOLD_TACTIC/data/emergency_activations.json`

- [ ] **Step 1: Create the empty initial-state file**

Write exactly this content to `GOLD_TACTIC/data/emergency_activations.json`:

```json
{
  "last_seen_scan_timestamp": "",
  "activations": []
}
```

- [ ] **Step 2: Verify the file is valid JSON**

Run:
```bash
python -c "import json; json.load(open('GOLD_TACTIC/data/emergency_activations.json')); print('VALID')"
```
Expected output: `VALID`

- [ ] **Step 3: Commit**

```bash
git add GOLD_TACTIC/data/emergency_activations.json
git commit -m "feat: add empty emergency_activations.json for Emergency News Activation"
```

---

### Task 2: Add Emergency Activation section to cowork_analyst.md

**Files:**
- Modify: `GOLD_TACTIC/prompts/cowork_analyst.md`

The section must be added BEFORE the existing "## Σειρά κύκλου" (cycle sequence) and AFTER the "## TRS" section.

- [ ] **Step 0: Verify anchor exists before editing**

Run:
```bash
python -c "
content = open('GOLD_TACTIC/prompts/cowork_analyst.md').read()
assert '## Σειρά κύκλου Analyst' in content, 'ERROR: anchor not found'
print('Anchor found — safe to proceed')
"
```
Expected: `Anchor found — safe to proceed`

- [ ] **Step 1: Add the Emergency Activation System section**

Find the line:
```
## Σειρά κύκλου Analyst
```

Insert the following block BEFORE it:

```markdown
## Emergency Activation System v5.1

Ο Analyst μπορεί να ενεργοποιήσει νέο asset αν ανιχνεύσει breaking news — ακόμα και αν ο Scanner δεν το έβαλε στο active_today.

### Αρχεία
- `data/scanner_watchlist.json` → active_today, scan_timestamp, nas100_afternoon
- `data/emergency_activations.json` → activations list, last_seen_scan_timestamp

### Κάθε κύκλος — START (βήματα 1-4 πριν από οτιδήποτε άλλο)

**1. Διάβασε scanner_watchlist.json** → active_today, scan_timestamp, nas100_afternoon

**2. Διάβασε emergency_activations.json** → activations, last_seen_scan_timestamp

**3. Αν scan_timestamp ≠ last_seen_scan_timestamp → CLEANUP:**
Για κάθε emergency asset:
- ΑΝ υπάρχει στο Scanner's active_today → ΑΦΑΙΡΕΣΕ από emergency (Scanner το πήρε)
- ΑΝ δεν υπάρχει στο active_today ΚΑΙ open_trade=false → ΑΦΑΙΡΕΣΕ
- ΑΝ δεν υπάρχει στο active_today ΚΑΙ open_trade=true → ΚΡΑΤΑ (trade ανοιχτό)
- ΑΝ asset=NAS100 ΚΑΙ nas100_afternoon=true ΚΑΙ ώρα < 16:30 EET → ΚΡΑΤΑ (afternoon eval pending)
Μετά το cleanup: γράψε last_seen_scan_timestamp = τρέχον scan_timestamp στο emergency_activations.json

**4. final_active = scanner active_today + [remaining emergency activations]**
Αναλύσε ΜΟΝΟ final_active assets αυτόν τον κύκλο.

### NEWS STEP — Breaking News Scan (βήμα 6, μετά τη news fetch)

Αν activations.length < 2 (cap: max 2 ταυτόχρονα):

Για κάθε news item στο news_feed.json, κρίνε με 3 ερωτήματα:

**Ερώτημα 1 — IMPACT ≥ 7/10:** Είναι αυτό extraordinary;
- ΝΑΙ: Fed emergency action, war escalation, exchange circuit breaker, major earnings surprise/miss, central bank intervention
- ΟΧΙ: routine data, analyst upgrades, general commentary

**Ερώτημα 2 — ASSET MAPPING:** Υπάρχει συγκεκριμένο asset + clear direction (LONG/SHORT);
- Πρέπει να αναφέρεις συγκεκριμένο ticker (όχι "markets generally")
- Πρέπει να γράψεις 2 προτάσεις: direction + catalyst. Αν δεν μπορείς → ΟΧΙ activation.

**Ερώτημα 3 — WORTHWHILE NOW:** Tradeable αυτή την ώρα;
- Market hours: forex 24/5, crypto 24/7, equities/NAS100 μόνο κατά session
- Fin weekend: forex/equity αυτόματα αποτυγχάνουν εδώ — μόνο crypto μπορεί να περάσει
- Εκτιμώμενο ADR room ≥ 30%

**Αν ΚΑΙ ΤΑ 3 = ΝΑΙ:**
1. Γράψε activation στο emergency_activations.json (asset, activated_at, reason, headline, source, open_trade=false)
2. Πρόσθεσε asset στο final_active ΓΙΑ ΑΥΤΟΝ ΤΟΝ ΚΥΚΛΟ
3. Στείλε 🚨 BREAKING ACTIVATION block πριν από κανονική ανάλυση (βλ. Telegram format)

**Αν cap φτάστηκε (2/2):** Σημείωσε στο Telegram: "⚠️ Emergency cap reached (2/2) — [headline] noted but not activated"

**Eligible assets για emergency activation:**
- Skipped core 5 (EURUSD, GBPUSD, NAS100, SOL, BTC)
- Extended: XAUUSD, ETH, NVDA, AAPL, TSLA, MSFT, GOOGL, AMD, INTC, COIN, PLTR, AMZN, META
- Οποιοδήποτε asset αναφέρεται ρητά στο news με clear price impact

**Charts για emergency assets:** Αν το asset δεν έχει ήδη charts, τρέξε:
```bash
python scripts/chart_generator.py [ASSET]
```
price_checker.py υποστηρίζει οποιοδήποτε Yahoo Finance ticker natively.

### Trade Entry Gate — Emergency Assets

| TRS Score | Regular Asset | Emergency Asset |
|-----------|--------------|-----------------|
| 5/5 🔥 | TRADE | TRADE |
| 4/5 🟢 | TRADE | **MONITOR ONLY — ΟΧΙ entry** |
| 3/5 🟡 | Wait | Wait |
| 0-2/5 ⬜ | Skip | Skip |

### open_trade lifecycle

- Όταν ανοίγεις trade σε emergency asset → άμεσα γράψε `open_trade: true` στο emergency_activations.json
- Όταν κλείνει trade (TP, SL, EOD) → άμεσα γράψε `open_trade: false`
- Και τα δύο γράφονται ΠΡΙΝ σταλεί το Telegram του κύκλου

### Telegram — Breaking Activation format

```
🚨 BREAKING ACTIVATION — [ASSET]

📰 "[headline]" ([source], [ώρα EET])
🧠 Reasoning: [2 προτάσεις: direction + catalyst]
📈 Direction: [LONG/SHORT] — [one-line summary]
⚠️ Override: Scanner είχε [ASSET] ως skip — αυτό το news αλλάζει εικόνα

→ Κάνω full TRS analysis τώρα...
━━━━━━━━━━━━━━━━━━━━━━
[full TRS analysis follows]
```

### Telegram — Analyst footer (κάθε κύκλος)

```
✅ Active: [asset] (scanner) | [asset] 🚨 (breaking news)
⏭️ Skipped: [asset] ([λόγος]) | ...
```

### Telegram — Cleanup notification (μετά από Scanner run που αφαιρεί emergency)

```
🧹 Emergency cleared: [ASSET] — Scanner δεν επιβεβαίωσε, no open trade
```

### Edge cases
- **NAS100 breaking news, nas100_afternoon=true, ώρα < 16:30:** activate + note "monitoring only until IBB window 16:30 EET"
- **NAS100 breaking news, nas100_afternoon=false:** activate + note "outside IBB window — monitoring only, no entry today"
- **Ίδιο asset activated ξανά:** deduplicate — ανανέωσε activated_at + headline, μην προσθέσεις duplicate
- **Trade ανοίγει και κλείνει στον ίδιο κύκλο:** γράψε true στο step 7, false στο step 8
```

- [ ] **Step 2: Replace the "## Σειρά κύκλου Analyst" section**

Find and replace this exact multi-line block (currently lines 86-97 of `cowork_analyst.md`):
```
## Σειρά κύκλου Analyst
1. Διάβασε scanner_watchlist.json → active_today
2. SANITY CHECK τιμών
3. price_checker.py → live_prices.json
4. LADDER MANAGEMENT (open trades)
5. NAS100 afternoon check
6. ΑΝΑΛΥΣΗ active assets (TRS)
7. TRADE EXECUTION (TRS=5/5)
8. NEWS CHECK (τελευταία 20 λεπτά)
9. CHARTS (TRS 4+/5, active only)
10. TELEGRAM
11. JOURNAL update
```

With:
```markdown
## Σειρά κύκλου Analyst
1. Διάβασε scanner_watchlist.json → active_today, scan_timestamp, nas100_afternoon
2. Διάβασε emergency_activations.json → activations, last_seen_scan_timestamp
3. Cleanup emergency activations (αν νέος Scanner run, βλ. Emergency Activation System)
4. Build final_active = active_today + remaining emergency activations
5. SANITY CHECK τιμών
6. price_checker.py → live_prices.json (για final_active assets)
7. LADDER MANAGEMENT (open trades)
8. NAS100 afternoon check
9. ΑΝΑΛΥΣΗ final_active assets (TRS)
10. NEWS CHECK → Breaking News Scan (βλ. Emergency Activation System)
11. TRADE EXECUTION (4-5/5 κανονικά, 5/5 μόνο για emergency assets)
12. Update open_trade σε emergency_activations.json (αν trade άνοιξε/έκλεισε)
13. CHARTS (TRS 4+/5, active only — τρέξε chart_generator.py για νέα emergency assets)
14. TELEGRAM
15. JOURNAL update
```

- [ ] **Step 3: Verify the edited file has no duplicate sections**

Run:
```bash
python -c "
content = open('GOLD_TACTIC/prompts/cowork_analyst.md').read()
checks = [
  ('Emergency Activation System', 1),
  ('Σειρά κύκλου', 1),
  ('open_trade lifecycle', 1),
  ('Breaking News Scan', 1),
]
for phrase, expected in checks:
    count = content.count(phrase)
    status = 'OK' if count == expected else f'ERROR: found {count}, expected {expected}'
    print(f'{phrase}: {status}')
"
```
Expected: all lines print `OK`

- [ ] **Step 4: Commit**

```bash
git add GOLD_TACTIC/prompts/cowork_analyst.md
git commit -m "feat: add Emergency News Activation System to cowork_analyst.md v5.1"
```

---

## Chunk 2: cowork_v5_upgrade.md update

### Task 3: Update cowork_v5_upgrade.md with emergency flow

**Files:**
- Modify: `GOLD_TACTIC/prompts/cowork_v5_upgrade.md`

The v5.0 upgrade document is given to both Scanner and Analyst schedules. The Analyst section needs to reflect the emergency activation flow so both documents are consistent.

- [ ] **Step 0: Verify anchors exist in cowork_v5_upgrade.md**

Run:
```bash
python -c "
content = open('GOLD_TACTIC/prompts/cowork_v5_upgrade.md').read()
checks = [
    '### Αν active_today = [\"EURUSD\", \"BTC\"]:',
    'Skipped: GBPUSD',
    'ΣΥΝΟΨΗ v5.0',
]
missing = [c for c in checks if c not in content]
if missing:
    print('ERROR — not found:', missing)
else:
    print('All anchors found — safe to proceed')
"
```
Expected: `All anchors found — safe to proceed`

- [ ] **Step 1: Update ΑΛΛΑΓΗ 2 — Analyst cycle instructions**

Find the section:
```
### Αν active_today = ["EURUSD", "BTC"]:
- Αναλύει ΜΟΝΟ EURUSD + BTC (full TRS, charts, news, levels)
- GBPUSD, NAS100, SOL: 1 γραμμή "⏭️ Skipped by Scanner: [λόγος]"
- ΔΕΝ φτιάχνει charts για skip assets
- ΔΕΝ υπολογίζει TRS για skip assets
```

Replace with:
```markdown
### Αν active_today = ["EURUSD", "BTC"]:
- Διαβάζει ΕΠΙΣΗΣ emergency_activations.json → final_active = active_today + emergency assets
- Αναλύει ΜΟΝΟ final_active assets (full TRS, charts, news, levels)
- Skipped assets: 1 γραμμή "⏭️ Skipped by Scanner: [λόγος]" (εκτός αν emergency-activated)
- ΔΕΝ φτιάχνει charts για skip assets (εκτός emergency)
- ΔΕΝ υπολογίζει TRS για skip assets (εκτός emergency)
- Emergency assets: full analysis ΑΝ breaking news detected, trade entry ΜΟΝΟ 5/5 TRS
```

- [ ] **Step 2: Update ΑΛΛΑΓΗ 3 — Analyst Telegram format footer**

Find the Analyst Telegram template section. Locate the footer line:
```
⏭️ Skipped: GBPUSD (ADR 75%), NAS100 (IBB 16:30), SOL (follows BTC)
```

Replace with:
```
✅ Active: [asset] (scanner) | [asset] 🚨 (breaking news, αν υπάρχει)
⏭️ Skipped: GBPUSD (ADR 75%), NAS100 (IBB 16:30), SOL (follows BTC)
```

- [ ] **Step 3: Update ΣΥΝΟΨΗ v5.0 table**

Find the summary table and add a row for the emergency feature. Locate the table ending row:
```
| News | Duplicate scanner+analyst | **Scanner: overview, Analyst: live only** |
```

Add after it:
```
| Breaking news | Analyst αγνοεί non-active assets | **Emergency activation αν IMPACT ≥ 7/10** |
```

- [ ] **Step 4: Verify cowork_v5_upgrade.md has no duplicate content**

Run:
```bash
python -c "
content = open('GOLD_TACTIC/prompts/cowork_v5_upgrade.md').read()
checks = [
    ('emergency_activations', 1),
    ('breaking news', 1),
    ('final_active', 1),
]
for phrase, expected in checks:
    count = content.lower().count(phrase.lower())
    status = 'OK' if count == expected else f'ERROR: found {count}, expected {expected}'
    print(f'{phrase}: {status}')
"
```
Expected: all lines print `OK`

- [ ] **Step 5: Commit**

```bash
git add GOLD_TACTIC/prompts/cowork_v5_upgrade.md
git commit -m "feat: update cowork_v5_upgrade.md with emergency activation flow"
```

---

## Chunk 3: End-to-end verification

### Task 4: Verify full integration

**Files:**
- Read: `GOLD_TACTIC/data/emergency_activations.json`
- Read: `GOLD_TACTIC/prompts/cowork_analyst.md`
- Read: `GOLD_TACTIC/prompts/cowork_v5_upgrade.md`

- [ ] **Step 1: Verify emergency_activations.json structure**

Run:
```bash
python -c "
import json
data = json.load(open('GOLD_TACTIC/data/emergency_activations.json'))
assert 'last_seen_scan_timestamp' in data, 'Missing last_seen_scan_timestamp'
assert 'activations' in data, 'Missing activations'
assert isinstance(data['activations'], list), 'activations must be list'
assert data['last_seen_scan_timestamp'] == '', 'Initial value must be empty string'
print('emergency_activations.json: VALID')
"
```
Expected: `emergency_activations.json: VALID`

- [ ] **Step 2: Verify cowork_analyst.md contains all required instruction blocks**

Run:
```bash
python -c "
content = open('GOLD_TACTIC/prompts/cowork_analyst.md').read()
required = [
    'Emergency Activation System',
    'last_seen_scan_timestamp',
    'CLEANUP',
    'final_active',
    'Breaking News Scan',
    'IMPACT',
    'ASSET MAPPING',
    'WORTHWHILE NOW',
    'open_trade lifecycle',
    'BREAKING ACTIVATION',
    'Emergency cleared',
    'cap reached',
    'nas100_afternoon',
    'MONITOR ONLY',
]
missing = [r for r in required if r not in content]
if missing:
    print('MISSING:', missing)
else:
    print('cowork_analyst.md: ALL CHECKS PASS')
"
```
Expected: `cowork_analyst.md: ALL CHECKS PASS`

- [ ] **Step 3: Verify cowork_v5_upgrade.md references emergency system**

Run:
```bash
python -c "
content = open('GOLD_TACTIC/prompts/cowork_v5_upgrade.md').read()
required = [
    'emergency_activations',
    'final_active',
    'breaking news',
    '🚨',
]
missing = [r for r in required if r.lower() not in content.lower()]
if missing:
    print('MISSING:', missing)
else:
    print('cowork_v5_upgrade.md: ALL CHECKS PASS')
"
```
Expected: `cowork_v5_upgrade.md: ALL CHECKS PASS`

- [ ] **Step 4: Final commit and push**

```bash
git status
git log --oneline -5
```

Verify 3 commits appear since feature start (emergency_activations.json, cowork_analyst.md, cowork_v5_upgrade.md). Then:

```bash
git push
```

---

## Summary

| Task | File | Type |
|------|------|------|
| 1 | `data/emergency_activations.json` | Create new |
| 2 | `prompts/cowork_analyst.md` | Add Emergency Activation System section + update cycle sequence |
| 3 | `prompts/cowork_v5_upgrade.md` | Update Analyst section + Telegram footer + summary table |
| 4 | Verification | Python checks + git push |

**No Python scripts are modified.**
