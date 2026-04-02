# News Intelligence Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add intelligent news classification, cross-cycle deduplication via `news_digest.json`, and Telegram daily cleanup to the GOLD TACTIC trading system.

**Architecture:** A new `news_digest.json` file persists which articles have been shown today (cross-session dedup). `telegram_sender.py` saves every sent message ID to `telegram_log.json`; `telegram_cleanup.py` deletes the previous day's messages on startup. The analyst prompt (`adaptive_analyst.md`) gets a new NEWS CLASSIFICATION section plus updated ZONE 3, TIER 1, and TIER 2 news blocks.

**Tech Stack:** Python 3 (stdlib only — urllib.request, json, pathlib), Telegram Bot API (sendMessage, deleteMessage), adaptive_analyst.md (markdown prompt file)

**Spec:** `docs/superpowers/specs/2026-04-02-news-intelligence-design.md`

---

## Chunk 1: Python changes — data files, telegram_sender, telegram_cleanup

### Task 1: Create `news_digest.json` and update `.gitignore`

**Files:**
- Create: `GOLD_TACTIC/data/news_digest.json`
- Modify: `.gitignore`

- [ ] **Step 1: Create `news_digest.json` initial state**

Create the file `GOLD_TACTIC/data/news_digest.json` with this exact content:

```json
{
  "date": null,
  "last_updated": null,
  "shown_ids": []
}
```

- [ ] **Step 2: Verify the file is valid JSON**

Run:
```bash
python -c "import json; print(json.load(open('GOLD_TACTIC/data/news_digest.json')))"
```
Expected: `{'date': None, 'last_updated': None, 'shown_ids': []}`

- [ ] **Step 3: Update `.gitignore` — whitelist `news_digest.json`, ignore `telegram_log.json`**

In `.gitignore`, find the whitelist section (around line 29, after `!GOLD_TACTIC/data/narrative_memory.json`). Add the whitelist entry immediately after that line:
```
!GOLD_TACTIC/data/news_digest.json
```

Then find the ignore section (around line 44, near `GOLD_TACTIC/data/live_prices.json`). Add:
```
GOLD_TACTIC/data/telegram_log.json
```

- [ ] **Step 4: Verify `news_digest.json` is tracked and `telegram_log.json` is ignored**

Run:
```bash
git check-ignore -v GOLD_TACTIC/data/news_digest.json
git check-ignore -v GOLD_TACTIC/data/telegram_log.json
```
Expected:
- First command: no output (file is NOT ignored → tracked ✅)
- Second command: `.gitignore:NN:GOLD_TACTIC/data/telegram_log.json  GOLD_TACTIC/data/telegram_log.json` (file IS ignored ✅)

- [ ] **Step 5: Commit**

```bash
git add GOLD_TACTIC/data/news_digest.json .gitignore
git commit -m "feat: add news_digest.json and update .gitignore for news intelligence"
```

---

### Task 2: Modify `telegram_sender.py` — save message IDs

**Files:**
- Modify: `GOLD_TACTIC/scripts/telegram_sender.py`

The goal: after every successful send (text, photo, media group), save the returned `message_id` to `data/telegram_log.json`.

- [ ] **Step 1: Add `DATA_DIR` and `LOG_FILE` constants + `_save_message_id()` helper**

In `GOLD_TACTIC/scripts/telegram_sender.py`, after the existing `SCREENSHOTS_DIR` constant (line 22), add:

```python
DATA_DIR = Path(__file__).parent.parent / "data"
LOG_FILE = DATA_DIR / "telegram_log.json"


def _save_message_id(message_id):
    """Append a sent message_id to telegram_log.json for daily cleanup."""
    from datetime import date
    today = date.today().isoformat()
    # Re-read on every call — never cache
    if LOG_FILE.exists():
        try:
            log = json.loads(LOG_FILE.read_text(encoding='utf-8'))
        except Exception:
            log = {}
    else:
        log = {}
    if log.get("date") != today:
        log = {"date": today, "message_ids": []}
    log["message_ids"].append(message_id)
    LOG_FILE.write_text(json.dumps(log, indent=2), encoding='utf-8')
```

- [ ] **Step 2: Call `_save_message_id()` in `send_message()`**

In `send_message()`, find the line `return result` (line 38). Just before it, add:

```python
    if result.get("ok") and "result" in result:
        _save_message_id(result["result"]["message_id"])
```

So the end of `send_message()` becomes:
```python
    result = json.loads(resp.read().decode())
    if result.get("ok") and "result" in result:
        _save_message_id(result["result"]["message_id"])
    return result
```

- [ ] **Step 3: Call `_save_message_id()` in `send_photo()`**

In `send_photo()`, find the line `return result` (line 82). Just before it, add:

```python
    if result.get("ok") and "result" in result:
        _save_message_id(result["result"]["message_id"])
```

- [ ] **Step 4: Call `_save_message_id()` in `send_media_group()`**

`send_media_group()` returns a list of messages in `result["result"]`. In `send_media_group()`, find `return result` (line 132). Just before it, add:

```python
    if result.get("ok") and isinstance(result.get("result"), list):
        for msg in result["result"]:
            if "message_id" in msg:
                _save_message_id(msg["message_id"])
```

- [ ] **Step 5: Verify the file looks correct after edits**

Run:
```bash
python -c "import ast, sys; ast.parse(open('GOLD_TACTIC/scripts/telegram_sender.py').read()); print('Syntax OK')"
```
Expected: `Syntax OK`

- [ ] **Step 6: Commit**

```bash
git add GOLD_TACTIC/scripts/telegram_sender.py
git commit -m "feat: save sent message IDs to telegram_log.json after every send"
```

---

### Task 3: Create `telegram_cleanup.py`

**Files:**
- Create: `GOLD_TACTIC/scripts/telegram_cleanup.py`

- [ ] **Step 1: Create `telegram_cleanup.py`**

Create `GOLD_TACTIC/scripts/telegram_cleanup.py` with this content:

```python
#!/usr/bin/env python3
"""
GOLD TACTIC — Telegram Cleanup
Deletes previous day's Telegram messages at start of new trading day.
Reads message IDs from data/telegram_log.json.

Usage:
  python telegram_cleanup.py    # Run cleanup if date < today
"""

import urllib.request
import json
import sys
import os
from datetime import date
from pathlib import Path

if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

TOKEN = '8621254551:AAF3z5R-5JrAzTKaZQ31E3pmXxtlvQ10wFc'
CHAT_ID = '-1003767339297'
DATA_DIR = Path(__file__).parent.parent / "data"
LOG_FILE = DATA_DIR / "telegram_log.json"


def delete_message(message_id):
    """Delete a single Telegram message. Returns True on success or safe failure."""
    url = f'https://api.telegram.org/bot{TOKEN}/deleteMessage'
    payload = json.dumps({
        'chat_id': CHAT_ID,
        'message_id': message_id,
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload,
                                  headers={'Content-Type': 'application/json'})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read().decode())
        return result.get("ok", False)
    except urllib.error.HTTPError as e:
        if e.code == 400:
            # Message already deleted or not found — safe to ignore
            return True
        print(f"  [WARN] deleteMessage {message_id} failed: HTTP {e.code}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  [WARN] deleteMessage {message_id} error: {e}", file=sys.stderr)
        return False


def run_cleanup():
    """Delete previous day's messages if log date < today."""
    today = date.today().isoformat()

    if not LOG_FILE.exists():
        print("Cleanup: no telegram_log.json found — nothing to clean.")
        return

    try:
        log = json.loads(LOG_FILE.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"Cleanup: failed to read log: {e}")
        return

    log_date = log.get("date")
    message_ids = log.get("message_ids", [])

    if not log_date or log_date >= today:
        print(f"Cleanup: log date={log_date}, today={today} — nothing to clean.")
        return

    if not message_ids:
        print(f"Cleanup: log date={log_date} < today but no message IDs — resetting log.")
        LOG_FILE.write_text(json.dumps({"date": today, "message_ids": []}, indent=2),
                            encoding='utf-8')
        return

    print(f"Cleanup: deleting {len(message_ids)} messages from {log_date}...")
    deleted = 0
    for mid in message_ids:
        if delete_message(mid):
            deleted += 1

    print(f"Cleanup: done — {deleted}/{len(message_ids)} deleted.")
    LOG_FILE.write_text(json.dumps({"date": today, "message_ids": []}, indent=2),
                        encoding='utf-8')


if __name__ == "__main__":
    run_cleanup()
```

- [ ] **Step 2: Verify syntax**

Run:
```bash
python -c "import ast; ast.parse(open('GOLD_TACTIC/scripts/telegram_cleanup.py').read()); print('Syntax OK')"
```
Expected: `Syntax OK`

- [ ] **Step 3: Dry-run test — no log file case**

Run:
```bash
python GOLD_TACTIC/scripts/telegram_cleanup.py
```
Expected output (if `telegram_log.json` doesn't exist yet):
```
Cleanup: no telegram_log.json found — nothing to clean.
```

- [ ] **Step 4: Dry-run test — same-day case**

Create a test log file with today's date:
```bash
python -c "
import json, datetime
from pathlib import Path
log = {'date': datetime.date.today().isoformat(), 'message_ids': [99999]}
Path('GOLD_TACTIC/data/telegram_log.json').write_text(json.dumps(log))
print('Test log written')
"
python GOLD_TACTIC/scripts/telegram_cleanup.py
```
Expected: `Cleanup: log date=2026-04-02, today=2026-04-02 — nothing to clean.`

Remove test file:
```bash
python -c "from pathlib import Path; Path('GOLD_TACTIC/data/telegram_log.json').unlink(missing_ok=True)"
```

- [ ] **Step 5: Commit**

```bash
git add GOLD_TACTIC/scripts/telegram_cleanup.py
git commit -m "feat: add telegram_cleanup.py — delete previous day's messages on startup"
```

---

## Chunk 2: Prompt changes — adaptive_analyst.md (6 locations)

### Task 4: Update data files list in `adaptive_analyst.md`

**Files:**
- Modify: `GOLD_TACTIC/prompts/adaptive_analyst.md` (~line 49)

- [ ] **Step 1: Add `news_digest.json` and `telegram_log.json` to the data files list**

Find the line:
```
data\narrative_memory.json      → Arc state + story history ανά asset (cross-session)
```

Replace it with:
```
data\narrative_memory.json      → Arc state + story history ανά asset (cross-session)
data\news_digest.json           → Shown news IDs σήμερα + dedup state (cross-session)
data\telegram_log.json          → Message IDs για daily cleanup (operational)
```

- [ ] **Step 2: Verify**

Run:
```bash
grep -n "news_digest" "GOLD_TACTIC/prompts/adaptive_analyst.md"
```
Expected: one line with `data\news_digest.json`.

- [ ] **Step 3: Commit**

```bash
git add "GOLD_TACTIC/prompts/adaptive_analyst.md"
git commit -m "feat: add news_digest.json and telegram_log.json to data files list"
```

---

### Task 5: Update Βήμα 0 — news_digest init + telegram cleanup

**Files:**
- Modify: `GOLD_TACTIC/prompts/adaptive_analyst.md` (~lines 758-765)

- [ ] **Step 1: Add news_digest init block to Βήμα 0**

Find the existing NARRATIVE MEMORY block in Βήμα 0:
```
     📖 NARRATIVE MEMORY:
     Διάβασε data\narrative_memory.json.
     Αν αρχείο δεν υπάρχει → initialize: arc=WAITING, wait_cycles=0 για όλα.
     Αν last_updated < σήμερα (νέα ημέρα):
       → Για κάθε asset: session_summary → yesterday_summary
       → reset: arc=WAITING, wait_cycles_today=0, arc_since_session=null, last_trs=null
     Αν last_updated = σήμερα → φόρτωσε arc + wait_cycles + yesterday_summary ως context.
     ΓΡΑΨΕ εδώ: "Narrative arcs: [ASSET arc/wait_cycles], ..." πριν συνεχίσεις.
```

Replace it with:
```
     📖 NARRATIVE MEMORY:
     Διάβασε data\narrative_memory.json.
     Αν αρχείο δεν υπάρχει → initialize: arc=WAITING, wait_cycles=0 για όλα.
     Αν last_updated < σήμερα (νέα ημέρα):
       → Για κάθε asset: session_summary → yesterday_summary
       → reset: arc=WAITING, wait_cycles_today=0, arc_since_session=null, last_trs=null
     Αν last_updated = σήμερα → φόρτωσε arc + wait_cycles + yesterday_summary ως context.
     ΓΡΑΨΕ εδώ: "Narrative arcs: [ASSET arc/wait_cycles], ..." πριν συνεχίσεις.

     📰 NEWS DIGEST:
     Διάβασε data\news_digest.json.
     Αν αρχείο δεν υπάρχει ή date < σήμερα (νέα ημέρα):
       → Τρέξε: python GOLD_TACTIC\scripts\telegram_cleanup.py
       → Reset: {date: σήμερα, last_updated: τώρα, shown_ids: []}
       → Γράψε data\news_digest.json
     Αν date = σήμερα → φόρτωσε shown_ids ως context.
```

- [ ] **Step 2: Verify**

Run:
```bash
grep -n "NEWS DIGEST" "GOLD_TACTIC/prompts/adaptive_analyst.md"
```
Expected: one line containing `NEWS DIGEST` in the Βήμα 0 section.

- [ ] **Step 3: Commit**

```bash
git add "GOLD_TACTIC/prompts/adaptive_analyst.md"
git commit -m "feat: add news_digest init and telegram cleanup to Βήμα 0"
```

---

### Task 6: Update Βήμα 15b — add news_digest update

**Files:**
- Modify: `GOLD_TACTIC/prompts/adaptive_analyst.md` (~lines 785-793)

- [ ] **Step 1: Add news_digest update to Βήμα 15b**

Find the end of the Βήμα 15b block:
```
      - Ενημέρωσε last_trs, expected_trigger, last_updated
      - Γράψε data\narrative_memory.json
```

Replace it with:
```
      - Ενημέρωσε last_trs, expected_trigger, last_updated
      - Γράψε data\narrative_memory.json
15c → News digest update (TIER 2/3 μόνο — ΠΑΝΤΑ μετά το narrative memory):
      - shown_ids += [IDs των articles που εμφανίστηκαν σε αυτό το cycle]
        (ID = url αν υπάρχει, αλλιώς headline[:20].lower().replace(" ","_"))
      - last_updated = τώρα
      - Γράψε data\news_digest.json
```

- [ ] **Step 2: Verify**

Run:
```bash
grep -in "news digest update" "GOLD_TACTIC/prompts/adaptive_analyst.md"
```
Expected: one line containing `News digest update` in the step sequence (note: use `-i` for case-insensitive match).

- [ ] **Step 3: Commit**

```bash
git add "GOLD_TACTIC/prompts/adaptive_analyst.md"
git commit -m "feat: add news_digest update as step 15c after narrative_memory"
```

---

### Task 7: Add NEWS CLASSIFICATION section to `adaptive_analyst.md`

**Files:**
- Modify: `GOLD_TACTIC/prompts/adaptive_analyst.md` (~line 918, after NARRATIVE MEMORY section)

The new section goes after the `---` that closes the NARRATIVE MEMORY section (line ~918) and before the TELEGRAM FORMAT section (line ~920). **Note:** The spec says "before NEWS GUARD section" — NEWS GUARD is at line ~1151, so this location (before TELEGRAM FORMAT) satisfies that requirement and is also architecturally optimal since classification rules should precede the format templates that reference them.

- [ ] **Step 1: Insert NEWS CLASSIFICATION section**

Find this exact text (the end of NARRATIVE MEMORY section and start of TELEGRAM FORMAT):
```
---

## TELEGRAM FORMAT
```

Replace it with:
```
---

## NEWS CLASSIFICATION — Κατάταξη Ειδήσεων

Εφαρμόζεται κάθε TIER 2/3 κύκλο όταν διαβάζεις `data\news_feed.json`.

### Βήμα 1 — Importance

| Level | Criteria |
|-------|----------|
| 🔴 HIGH | Fed/ECB/BOE απόφαση ή δήλωση, CPI/NFP/PPI, geopolitical escalation, crypto exchange event, flash crash/rally |
| 🟡 MEDIUM | PMI, retail sales, housing data, earnings, analyst upgrades, regulatory news |
| ⚪ LOW | Routine commentary, opinion pieces, minor analyst notes |

### Βήμα 2 — Asset Impact

Για κάθε active asset στα slots:
```
BULLISH / BEARISH / NEUTRAL
```
Αποφάσισε βάσει: current price bias + TRS state + περιεχόμενο νέου + macro context.

### Βήμα 3 — 1-line Greek conclusion (ΥΠΟΧΡΕΩΤΙΚΟ)

Κάθε άρθρο που εμφανίζεται πρέπει να έχει ΑΚΡΙΒΩΣ ΜΙΑ γραμμή συμπέρασμα:
```
"Fed αύξησε επιτόκια → USD δυνατό → XAUUSD πίεση ↓, EURUSD αδύναμο ↓"
"Gold ETF inflows ↑ → XAUUSD ανοδική στήριξη ✅"
"PMI ελαφρά χαμηλότερο — neutral για assets μας"
```
**Αν δεν μπορείς να γράψεις αυτή τη γραμμή → το νέο ΔΕΝ εμφανίζεται.**

### Deduplication

- Article ID: `url` αν υπάρχει — αλλιώς `headline[:20].lower().replace(" ","_")`
- Αν ID ΕΝ shown_ids → παράλειψε (ήδη δείχθηκε σήμερα)
- Αν ID ΟΧΙ σε shown_ids → εμφάνισε + πρόσθεσε στα shown_ids (step 15c)

### Escalation — Παλιό νέο τώρα κάνει impact

Γράψε escalation line όταν ισχύουν ΚΑΙ ΤΑ ΤΡΙΑ:
1. Άρθρο ήδη στο shown_ids (δειχθηκε σε προηγούμενο κύκλο)
2. Είχε BULLISH ή BEARISH prediction για active asset
3. Τρέχουσα τιμή κινήθηκε στην κατεύθυνση αυτή (ορατό από ΤΙ ΑΛΛΑΞΕ zone)

Format:
```
📌 Νέο [ΩΩ:ΛΛ] επιβεβαιώνεται — "[τίτλος]"
   → [τιμή] κινήθηκε [+X pips] σύμφωνα με [BULLISH/BEARISH call]
```
Εμφανίζεται ΠΑΝΩ από νέα νέα.

---

## TELEGRAM FORMAT
```

- [ ] **Step 2: Verify**

Run:
```bash
grep -n "NEWS CLASSIFICATION" "GOLD_TACTIC/prompts/adaptive_analyst.md"
```
Expected: one line with `NEWS CLASSIFICATION`.

Run:
```bash
grep -n "## TELEGRAM FORMAT" "GOLD_TACTIC/prompts/adaptive_analyst.md"
```
Expected: one line — confirm it still exists immediately after the new section.

- [ ] **Step 3: Commit**

```bash
git add "GOLD_TACTIC/prompts/adaptive_analyst.md"
git commit -m "feat: add NEWS CLASSIFICATION section with dedup and escalation rules"
```

---

### Task 8: Rewrite ZONE 3 (TIER 3) news format

**Files:**
- Modify: `GOLD_TACTIC/prompts/adaptive_analyst.md` (~lines 1088-1106)

**Note:** This task uses two separate edits because the ZONE 3 block contains HTML code fences. Each edit targets content that does NOT contain triple-backtick sequences.

- [ ] **Step 1a: Replace the inner HTML template content (lines 1091-1098)**

Find this exact text (inside the HTML code block, no fences):
```
📰 <b>ΝΕΑ</b>

🆕 "[τίτλος σε απλά ελληνικά]" ([πηγή], [ΩΩ:ΛΛ])
   → [ΤΙ ΣΗΜΑΙΝΕΙ για τα assets μας] [🔴/🟢]
   → <a href="[url]">Διάβασε</a>

📊 Sentiment: Crypto Fear [X] | Markets [X]
📅 Επόμενο event: [EVENT] σε [Xh] ([HIGH/MEDIUM])
```

Replace with:
```
📰 <b>ΝΕΑ</b> (vs [last_cycle_time] EET)

[📌 escalation αν ισχύουν και τα 3 κριτήρια — εμφανίζεται ΠΡΩΤΟ]
📌 Νέο [ΩΩ:ΛΛ] επιβεβαιώνεται — "[τίτλος αρχικού νέου]"
   → [τιμή] κινήθηκε [+X pips] σύμφωνα με [BULLISH/BEARISH call]

[Νέα άρθρα — ΟΧΙ στο shown_ids — ταξινομημένα HIGH → MEDIUM → LOW]
🔴 "[τίτλος]" ([πηγή], [ΩΩ:ΛΛ])
   → [1-line Greek conclusion] [🟢/🔴 per active asset]
   → <a href="[url]">Διάβασε</a>   [παράλειψε αυτή τη γραμμή αν δεν υπάρχει url]

🟡 "[τίτλος]" ([πηγή], [ΩΩ:ΛΛ])
   → [1-line Greek conclusion]
   [χωρίς link αν δεν υπάρχει url]

[⚪ LOW παραλείπονται αν υπάρχουν HIGH ή MEDIUM]
[Αν ΟΛΑ τα άρθρα στο shown_ids:]
📰 Καμία νέα είδηση από [last_updated]. Κλίμα: [1 γραμμή sentiment]

📊 Sentiment: Crypto Fear [X] | Markets [X]
📅 Επόμενο event: [EVENT] σε [Xh] ([HIGH/MEDIUM])
```

- [ ] **Step 1b: Replace the Κανόνες νέων block (lines 1101-1106)**

Find this exact text:
```
**Κανόνες νέων:**
- Δείξε ΜΟΝΟ νέα που αφορούν ΤΑ ASSETS ΜΑΣ
- ΜΗΝ αναφέρεις νέο που ήδη ανέφερες σε προηγούμενο κύκλο
- Κράτα ΜΟΝΟ νέα με timestamp ΜΕΤΑ από τον τελευταίο κύκλο
- Αν ΟΛΑ παλαιότερα → `📰 Καμία νέα είδηση. Κλίμα: [1 γραμμή]`
- Κάθε νέο να έχει clickable link `<a href>` αν διαθέσιμο
```

Replace with:
```
**Κανόνες:**
- Χρησιμοποίησε `shown_ids` από `news_digest.json` για dedup (όχι timestamps)
- Sorting: 🔴 HIGH → 🟡 MEDIUM → ⚪ LOW
- ⚪ LOW εμφανίζονται ΜΟΝΟ αν δεν υπάρχουν HIGH/MEDIUM νέα
- Link rule: αν `url` κενό ή απόν → παράλειψε τη γραμμή `→ <a href>`
- Κάθε εμφανιζόμενο άρθρο ΠΡΕΠΕΙ να έχει 1-line conclusion (αλλιώς παράλειψε)
```

- [ ] **Step 2: Verify**

Run:
```bash
grep -n "shown_ids" "GOLD_TACTIC/prompts/adaptive_analyst.md"
```
Expected: multiple lines — at least one in the NEWS CLASSIFICATION section and one in ZONE 3.

```bash
grep -n "vs \[last_cycle_time\]" "GOLD_TACTIC/prompts/adaptive_analyst.md"
```
Expected: one line in ZONE 3 confirming the HTML template was updated.

- [ ] **Step 3: Commit**

```bash
git add "GOLD_TACTIC/prompts/adaptive_analyst.md"
git commit -m "feat: rewrite ZONE 3 news format with classification, dedup, and escalation"
```

---

### Task 9: Update TIER 1 and TIER 2 news blocks

**Files:**
- Modify: `GOLD_TACTIC/prompts/adaptive_analyst.md` (~lines 933-960)

- [ ] **Step 1a: Add HIGH news line inside TIER 1 HTML template**

Find this exact text (inside the TIER 1 HTML template, no fences):
```
[αν arc άλλαξε σε οποιοδήποτε asset:]
📖 [ASSET]: [OLD_ARC]→[NEW_ARC] — [1 γραμμή λόγος]
→ Τίποτα νέο. Επόμενο: TIER [X] σε [Y]' ([HH:MM])
```

Replace with:
```
[αν arc άλλαξε σε οποιοδήποτε asset:]
📖 [ASSET]: [OLD_ARC]→[NEW_ARC] — [1 γραμμή λόγος]
[αν HIGH νέο ΟΧΙ στο shown_ids:]
📰 "[τίτλος]" — [1-line Greek conclusion]
→ Τίποτα νέο. Επόμενο: TIER [X] σε [Y]' ([HH:MM])
```

- [ ] **Step 1b: Update TIER 1 silence rule**

Find this exact text (the TIER 1 silence rules after the HTML block):
```
Αν τίποτα δεν κινήθηκε ΚΑΙ κανένα arc δεν άλλαξε → ΟΧΙ Telegram μήνυμα.
Αν arc άλλαξε σε έστω 1 asset → στείλε TIER 1 message με την 📖 γραμμή.
```

Replace with:
```
Αν τίποτα δεν κινήθηκε ΚΑΙ κανένα arc δεν άλλαξε ΚΑΙ κανένα HIGH νέο ΟΧΙ στο shown_ids → ΟΧΙ Telegram μήνυμα.
Αν arc άλλαξε σε έστω 1 asset → στείλε TIER 1 message με την 📖 γραμμή.
Αν HIGH νέο ΟΧΙ στο shown_ids → στείλε TIER 1 message με 📰 γραμμή, ακόμα και αν δεν κινήθηκε τίποτα.
```

- [ ] **Step 2: Update TIER 2 template — replace `📰 [Top news]` line**

Find this exact line in the TIER 2 template:
```
📰 [Top news αν υπάρχει, με clickable link]
```

Replace it with:
```
[αν HIGH νέο ΟΧΙ στο shown_ids:]
📰 "[τίτλος]" ([πηγή]) → [1-line conclusion]
[αν κανένα HIGH νέο:]
📰 Καμία νέα είδηση από [last_updated time]
```

- [ ] **Step 3: Verify all changes**

Run:
```bash
grep -n "HIGH νέο ΟΧΙ" "GOLD_TACTIC/prompts/adaptive_analyst.md"
```
Expected: at least 2 lines (TIER 1 template + TIER 1 silence rule + TIER 2).

```bash
grep -n "Καμία νέα είδηση" "GOLD_TACTIC/prompts/adaptive_analyst.md"
```
Expected: at least 2 lines (TIER 2 + ZONE 3).

- [ ] **Step 4: Commit**

```bash
git add "GOLD_TACTIC/prompts/adaptive_analyst.md"
git commit -m "feat: update TIER 1 and TIER 2 news blocks with shown_ids dedup logic"
```

---

## End-to-End Verification

- [ ] **Verify all 6 adaptive_analyst.md change points are present**

Run each check:
```bash
grep -n "news_digest.json" "GOLD_TACTIC/prompts/adaptive_analyst.md"
```
Expected: change #1 (data files list) — at least 1 result.

```bash
grep -n "NEWS DIGEST" "GOLD_TACTIC/prompts/adaptive_analyst.md"
```
Expected: change #2 (Βήμα 0) — at least 1 result.

```bash
grep -n "15c" "GOLD_TACTIC/prompts/adaptive_analyst.md"
```
Expected: change #3 (Βήμα 15c) — at least 1 result.

```bash
grep -n "NEWS CLASSIFICATION" "GOLD_TACTIC/prompts/adaptive_analyst.md"
```
Expected: change #4 (new section) — at least 1 result.

```bash
grep -n "vs \[last_cycle_time\]" "GOLD_TACTIC/prompts/adaptive_analyst.md"
```
Expected: change #5 (ZONE 3 rewrite) — 1 result.

```bash
grep -n "HIGH νέο ΟΧΙ" "GOLD_TACTIC/prompts/adaptive_analyst.md"
```
Expected: change #6 (TIER 1 + TIER 2) — at least 3 results (TIER 1 template, TIER 1 silence rule, TIER 2 — one per location).

- [ ] **Verify JSON files are valid**

```bash
python -c "import json; json.load(open('GOLD_TACTIC/data/news_digest.json')); print('news_digest OK')"
```
Expected: `news_digest OK`

- [ ] **Verify Python scripts have no syntax errors**

```bash
python -c "import ast; ast.parse(open('GOLD_TACTIC/scripts/telegram_sender.py').read()); print('sender OK')"
python -c "import ast; ast.parse(open('GOLD_TACTIC/scripts/telegram_cleanup.py').read()); print('cleanup OK')"
```
Expected: `sender OK` then `cleanup OK`

- [ ] **Verify git status is clean**

```bash
git status
```
Expected: `nothing to commit, working tree clean`
