# News Intelligence Design
**Date:** 2026-04-02
**Status:** Approved
**Scope:** GOLD TACTIC Adaptive Analyst — Intelligent news classification, cross-cycle deduplication, Telegram daily cleanup

---

## Problem

The current news system fetches articles and dumps raw headlines into the Telegram message. Problems:

1. **No impact conclusion** — user sees a headline but has no idea if it's bullish/bearish for their active assets
2. **Repeated news** — same article shown every cycle until the news file is refreshed
3. **No importance ranking** — a routine market comment sits alongside a Fed announcement
4. **No cross-session memory** — if the session restarts, dedup state is lost
5. **Telegram accumulates** — yesterday's messages pile up with today's, making it hard to follow

---

## Solution Overview

Three changes working together:

1. **`data/news_digest.json`** — lightweight persistent file tracking which articles have been shown today
2. **News Classification Rules in `adaptive_analyst.md`** — analyst classifies each article: importance + asset impact + 1-line Greek conclusion
3. **Telegram cleanup** — `telegram_sender.py` saves message IDs; `telegram_cleanup.py` deletes previous day's messages at start of new day

---

## Component 1: `news_digest.json`

### Location
`GOLD_TACTIC/data/news_digest.json`

### Structure

```json
{
  "date": "2026-04-02",
  "last_updated": "2026-04-02 14:30 EET",
  "shown_ids": ["url_or_slug_1", "url_or_slug_2", "url_or_slug_3"]
}
```

### Fields

| Field | Purpose |
|-------|---------|
| `date` | Daily reset trigger — if `date < today`, reset all |
| `shown_ids` | All article IDs shown today across all cycles and sessions |
| `last_updated` | Timestamp of last write |

### Article ID

- **Primary:** full `url` field from the news_feed.json item (if present and non-empty)
- **Fallback:** `headline[:20].lower().replace(" ", "_")` — e.g., `"fed raises rates by 25"` → `"fed_raises_rates_by_2"`. The analyst computes this as a simple string slice, no hashing required.

This scheme is deterministic (same article always produces the same ID), and unique enough for ~20-50 daily articles.

### Daily Reset (Βήμα 0)

If `date < today` or file does not exist:
```
→ shown_ids = []
→ date = today
→ last_updated = now
```

---

## Component 2: News Classification Rules

### Classification per Article

The analyst applies three steps to every article from `news_feed.json`:

**Step 1 — Importance**

| Level | Criteria |
|-------|----------|
| 🔴 HIGH | Fed/ECB/BOE decision or statement, CPI/NFP/PPI release, geopolitical escalation, crypto exchange event, flash crash/rally |
| 🟡 MEDIUM | PMI, retail sales, housing data, earnings, analyst upgrades, regulatory news |
| ⚪ LOW | Routine commentary, opinion pieces, minor analyst notes |

**Step 2 — Asset Impact**

For each active asset in current slots:
```
BULLISH / BEARISH / NEUTRAL
```
Analyst decides based on: current price bias + TRS state + news content + macro context.

**Step 3 — 1-line Greek conclusion (ΥΠΟΧΡΕΩΤΙΚΟ)**

Every displayed article must have exactly one conclusion line:
```
"Fed αύξησε επιτόκια → USD δυνατό → XAUUSD πίεση ↓, EURUSD αδύναμο ↓"
"Gold ETF inflows ↑ → XAUUSD ανοδική στήριξη ✅"
"PMI ελαφρά χαμηλότερο — neutral για assets μας"
```

**Κανόνας:** Αν ο analyst δεν μπορεί να γράψει αυτή τη γραμμή → το νέο ΔΕΝ εμφανίζεται στο Telegram (silently dropped — no audit trail required).

---

## Component 3: Cross-cycle News Logic

### Per-article decision each cycle

```
article.id ΟΧΙ σε shown_ids                → ΝΕΟΝ — εμφάνισε, πρόσθεσε στο shown_ids
article.id ΣΤΗ shown_ids                   → παράλειψε (ήδη δείχθηκε)
article.id ΣΤΗ shown_ids + price confirms  → 📌 escalation line (βλ. παρακάτω)
```

### "Καμία νέα είδηση" (όλα ήδη στο shown_ids)

```
📰 Καμία νέα είδηση από [last_updated time]. Κλίμα: [1 γραμμή sentiment]
```

### "Παλιό νέο τώρα κάνει impact" (📌 escalation)

**Escalation trigger** — ο analyst γράφει escalation line όταν ισχύουν ΚΑΙ ΤΑ ΤΡΙΑ:
1. Το άρθρο είναι ήδη στο `shown_ids` (έχει δειχτεί σε προηγούμενο κύκλο σήμερα)
2. Το άρθρο είχε BULLISH ή BEARISH prediction για active asset (όχι NEUTRAL)
3. Η τρέχουσα τιμή κινήθηκε στην προβλεπόμενη κατεύθυνση — διαπιστώνεται από τα δεδομένα του ΤΙ ΑΛΛΑΞΕ zone (price vs previous cycle)

Ο analyst εφαρμόζει αυτό ως qualitative reasoning check — δεν απαιτείται ακριβές threshold pips. Αρκεί να είναι ορατή κατευθυντήρια κίνηση.

```
📌 Νέο [ΩΩ:ΛΛ] επιβεβαιώνεται — "[τίτλος αρχικού νέου]"
   → [τιμή] κινήθηκε [+X pips] σύμφωνα με [BULLISH/BEARISH call]
```
Εμφανίζεται **πάνω από** τα νέα νέα — είναι confirmation signal.

---

## Component 4: ZONE 3 Telegram Format

### TIER 3 — Full format

```
📰 ΝΕΑ (vs [last_cycle_time] EET)

[📌 escalation αν υπάρχει]
📌 Νέο 10:00 επιβεβαιώνεται — "[τίτλος]"
   → [τιμή] κινήθηκε [+X pips] — [BULLISH/BEARISH confirmed]

🔴 "[τίτλος]" ([πηγή], [ΩΩ:ΛΛ])
   → [1-line Greek conclusion] [🟢/🔴 per active asset]
   → <a href="[url]">Διάβασε</a>    [παράλειψε αυτή τη γραμμή αν url απούσιαζε]

🟡 "[τίτλος]" ([πηγή], [ΩΩ:ΛΛ])
   → [1-line Greek conclusion]
   [χωρίς link αν δεν υπάρχει url]

[⚪ LOW νέα παραλείπονται αν υπάρχουν HIGH/MEDIUM]

📊 Sentiment: Crypto Fear [X] | Markets [X]
📅 Επόμενο event: [EVENT] σε [Xh] ([HIGH/MEDIUM])
```

**URL rule:** Αν το `url` field είναι κενό ή απούσιαζε → παράλειψε τη γραμμή `→ <a href>`. Μόνο ο τίτλος + 1-line conclusion.

Sorting: 🔴 HIGH → 🟡 MEDIUM → ⚪ LOW (low omitted when high/medium present)

### TIER 2 — Condensed

Μόνο 🔴 HIGH νέα που ΔΕΝ είναι στο `shown_ids`:
```
📰 [τίτλος] ([πηγή]) → [1-line conclusion]
```
Αν κανένα HIGH νέο: `📰 Καμία νέα είδηση από [time]`

### TIER 1 — Alert only

Μόνο αν HIGH νέο που ΔΕΝ έχει δειχτεί:
```
📰 [τίτλος] — [1-line conclusion]
```
Αν τίποτα νέο HIGH: κανένα news block στο TIER 1.

---

## Component 5: Telegram Cleanup

### `data/telegram_log.json` (νέο αρχείο)

```json
{
  "date": "2026-04-02",
  "message_ids": [12345, 12346, 12347]
}
```

### `telegram_sender.py` change

After every successful `sendMessage` API call:
- **Re-read** `telegram_log.json` on every call (no caching — ensures the file state is current)
- If file missing → create: `{date: today, message_ids: []}`
- If `date ≠ today` → reset: `date = today, message_ids = []`
- Append returned `message_id` to `message_ids`
- Write back

### `telegram_cleanup.py` (νέο script)

```
1. Read telegram_log.json — if missing or empty message_ids, exit (nothing to clean)
2. If date < today:
   → For each message_id:
      - Call deleteMessage API
      - If HTTP 400 (message already deleted / not found): continue silently
      - If other error (network timeout, etc.): print warning, continue to next ID
   → Write telegram_log.json: {date: today, message_ids: []}
   → Print: "Cleanup: deleted [N] messages from [date]"
3. If date = today or date is missing: exit (nothing to clean)
```

### Integration — Βήμα 0 extension

```
Αν νέα ημέρα (news_digest.date < σήμερα ή αρχείο δεν υπάρχει):
→ Τρέξε: python GOLD_TACTIC\scripts\telegram_cleanup.py
→ Reset news_digest.json (date=today, shown_ids=[])
→ Reset narrative_memory.json (ήδη υπάρχει από προηγούμενο spec)
```

---

## Lifecycle του `news_digest.json`

### Βήμα 0 — Startup

```
Διάβασε news_digest.json
→ Αν αρχείο δεν υπάρχει → initialize: date=today, shown_ids=[]
→ Αν date < today → daily reset (date=today, shown_ids=[])
→ Φόρτωσε shown_ids για χρήση στο cycle
```

### Κάθε κύκλος TIER 2/3 — Βήμα 15b extension

Μετά το session_log entry και narrative_memory update:
```
→ Update news_digest.json:
   - shown_ids += [IDs των articles που εμφανίστηκαν σε αυτόν τον κύκλο]
   - last_updated = τώρα
```

---

## Αρχεία που αλλάζουν

| Αρχείο | Αλλαγή |
|--------|--------|
| `GOLD_TACTIC/data/news_digest.json` | ΝΕΟ — daily news dedup state |
| `GOLD_TACTIC/data/telegram_log.json` | ΝΕΟ — message IDs για cleanup |
| `GOLD_TACTIC/scripts/telegram_cleanup.py` | ΝΕΟ — script διαγραφής μηνυμάτων |
| `GOLD_TACTIC/scripts/telegram_sender.py` | ΑΛΛΑΓΗ — αποθήκευση message IDs μετά από κάθε send |
| `GOLD_TACTIC/prompts/adaptive_analyst.md` | ΑΛΛΑΓΗ — 6 σημεία (βλ. παρακάτω) |
| `.gitignore` | ΑΛΛΑΓΗ — whitelist `news_digest.json`, ignore `telegram_log.json` |

### .gitignore αλλαγές

- **Whitelist (track):** `!GOLD_TACTIC/data/news_digest.json` — προστέθηκε στο whitelist section (μετά από `!GOLD_TACTIC/data/narrative_memory.json`)
- **Ignore (do not track):** `GOLD_TACTIC/data/telegram_log.json` — προστέθηκε στο ignore section (operational/transient state, no value in git history)

### adaptive_analyst.md — 6 σημεία αλλαγών

| # | Σημείο | Τι αλλάζει | Τοποθεσία |
|---|--------|------------|-----------|
| 1 | Data files list | Προσθήκη `news_digest.json` + `telegram_log.json` | ~γρ. 44 |
| 2 | Βήμα 0 | Προσθήκη news_digest init + telegram cleanup step | Βήμα 0 block |
| 3 | Βήμα 15b | Προσθήκη news_digest update (μετά από narrative_memory update) | Βήμα 15b block |
| 4 | Νέο section "NEWS CLASSIFICATION" | Κανόνες classification (importance + asset impact + 1-liner + escalation trigger) | Μετά το NARRATIVE MEMORY section, πριν το NEWS GUARD section |
| 5 | ZONE 3 (TIER 3) | Πλήρης αντικατάσταση format + url fallback rule + sorting rule | ZONE 3 block |
| 6 | TIER 1 + TIER 2 news blocks | Ενημέρωση βάσει shown_ids logic | TIER 1 template + TIER 2 template |

## Τι ΔΕΝ αλλάζει

- Η λογική των TIER cycles (timing, escalation triggers)
- Τα TRS κριτήρια και η trade execution
- Τα scripts news_scout_v2.py, quick_scan.py (δεν προ-classifyάρουν)
- Η δομή του session_log.jsonl
- Οι 10 κανόνες που δεν αλλάζουν ποτέ
- Το narrative_memory.json (ήδη υλοποιημένο)
