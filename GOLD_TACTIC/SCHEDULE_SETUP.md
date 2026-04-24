# GOLD TACTIC v7.2 — Schedule Installation Guide

> **Αυτό το αρχείο είναι self-contained Claude prompt.**
> Δώσ' το σε μια Claude Cowork session. Η session θα διαβάσει τις οδηγίες και θα δημιουργήσει τα 7 Windows scheduled tasks που τρέχουν το σύστημα 24/7.
>
> **Version:** 7.2 (follow-ups shipped 2026-04-17) | **Updated:** 2026-04-17
> **Changes vs 7.0:**
> - Αναβαθμισμένα timings για kill zones (London 10-12 / NY 15:30-17:30 EET)
> - Prerequisites για νέα αρχεία: `trade_manager.py`, `session_check.py`, `correlation_map.json`
> - **Open-trades header (STEP 4.95 στο Monitor):** πριν από ΚΑΘΕ Tier A/B/C ο prompt τρέχει `trade_manager.py header` και κάνει prepend live snapshot των ανοιχτών trades.
> - **Probe/Confirm scale-in (STEP 5.7):** σε optimal KZ, TRS=4 → `--tag probe` (1% risk · μισή θέση). TRS=5 πάνω σε υπάρχον probe → `--tag confirm` (+1% · total 2%). TRS=5 καθαρό → `--tag full` (2%).
> - **TP1 → Break-Even → TP2 runner (STEP 5.8):** το TP1 hit ΔΕΝ κλείνει το trade· μετακινεί SL στο entry και αφήνει runner προς TP2. Αν η τιμή γυρίσει → 🛡️ BE exit (0€). Αν χτυπήσει TP2 → 🎯🎯 full close.
> - Νέα smoke tests: header CLI, probe open, tick idempotency.

---

## ΤΙ ΕΙΣΑΙ

Είσαι **Claude Sonnet session σε Cowork** που εγκαθιστά **7 Windows scheduled tasks** για το GOLD TACTIC v7.2 trading system.

**Working directory (absolute path):** `C:\Users\aggel\Desktop\trading`

**Τι κάνει το σύστημα όταν τελειώσεις:**
- 3 φορές/ημέρα (weekday) + 1 φορά/weekend: τρέχει τον **Asset Selector** που διαλέγει τα top 4 assets για monitoring.
- Κάθε 20 λεπτά (peak) ή 40 λεπτά (off-peak/weekend): τρέχει τον **Market Monitor** που αναλύει τα 4 assets, στέλνει Telegram updates (Tier A/B/C), **ανοίγει αυτόματα paper trades σε Tier C signals**, και **παρακολουθεί τα open trades** (progress pings, TP/SL, 4h timeout).
- Όλα τα χρονικά timings είναι σε **EET (UTC+3)** — η ώρα του local PC.

**Γιατί αυτό το timing (κρίσιμο):**
- **Selector 08:00** → προετοιμασία πριν το **London Kill Zone (10:00-12:00)**.
- **Selector 14:30** → προετοιμασία πριν το **NY Kill Zone (15:30-17:30)**.
- **Selector 20:00** → end-of-day + overnight refresh.
- **Monitor Peak** (08:00-22:00, κάθε 20') → καλύπτει και τα 2 kill zones με συχνά updates.
- **Monitor Off-Peak** (22:00-08:00, κάθε 40') → Asian session, μόνο monitoring, κανένα Tier C.
- **Σημαντικό:** Ο Monitor **ΠΡΕΠΕΙ** να τρέχει συνεχώς γιατί τρέχει το `trade_manager.py tick` που κάνει progress pings / TP-SL / 4h timeout detection για open trades. Αν δεν τρέξει, τα open trades "παγώνουν".

---

## ΒΗΜΑ 0 — Prerequisites Check

Τρέξε αυτά πρώτα. Αν οποιοδήποτε από τα files λείπει, **ΣΤΑΜΑΤΑ** και ζήτα από τον χρήστη να κάνει `git pull`:

```bash
python --version                 # πρέπει >= 3.10
claude --version                 # Claude Code CLI

# Prompts (τα διαβάζει ο Claude κάθε φορά που τρέχει)
ls GOLD_TACTIC/prompts/asset_selector.md
ls GOLD_TACTIC/prompts/market_monitor.md

# Core scripts (αυτά καλούν τα prompts)
ls GOLD_TACTIC/scripts/price_checker.py
ls GOLD_TACTIC/scripts/telegram_sender.py
ls GOLD_TACTIC/scripts/dashboard_builder.py
ls GOLD_TACTIC/scripts/session_check.py
ls GOLD_TACTIC/scripts/trade_manager.py
ls GOLD_TACTIC/scripts/risk_manager.py
ls GOLD_TACTIC/scripts/news_scout_v2.py
ls GOLD_TACTIC/scripts/quick_scan.py
ls GOLD_TACTIC/scripts/auto_chart.py

# Data files (existing state)
ls GOLD_TACTIC/data/portfolio.json
ls GOLD_TACTIC/data/correlation_map.json

# .env (Telegram token + channel)
test -f .env && echo ".env OK" || echo "MISSING .env"
```

Αν όλα OK, προχώρα. Αν οτιδήποτε λείπει → ζήτα από χρήστη να φτιάξει και επανέλαβε.

---

## ΒΗΜΑ 1 — Cleanup (αν υπάρχουν παλιά tasks)

```bash
cmd //c "schtasks /Query /FO CSV /NH" 2>&1 | grep "GoldTactic"
```

Αν βγάλει αποτελέσματα, σβήσε **ΟΛΑ** τα παλιά before you create new ones:

```bash
# Για κάθε task που βρέθηκε:
cmd //c "schtasks /Delete /TN \\GoldTactic\\<task-name> /F"
```

Επαλήθευσε ότι το output του query πάνω πια είναι άδειο:
```bash
cmd //c "schtasks /Query /FO CSV /NH" 2>&1 | grep "GoldTactic" | wc -l
# πρέπει = 0
```

---

## ΒΗΜΑ 2 — Δημιουργία Wrapper Scripts

Φτιάξε το directory και 2 `.cmd` wrappers. Τα wrappers είναι αυτά που θα καλούν τα scheduled tasks — κάνουν `cd` στο working dir, καλούν `claude -p` με το αντίστοιχο prompt, και γράφουν logs.

```bash
mkdir -p GOLD_TACTIC/scripts/schtasks
mkdir -p "$USERPROFILE/.claude/logs"
```

### gt-asset-selector.cmd

Γράψε με το Write tool στο `GOLD_TACTIC/scripts/schtasks/gt-asset-selector.cmd`:

```cmd
@echo off
setlocal
set "GT_BASE=C:\Users\aggel\Desktop\trading"
set "GT_LOG=%USERPROFILE%\.claude\logs\gt-asset-selector.log"
cd /d "%GT_BASE%"
echo [%date% %time%] Asset-Selector START >> "%GT_LOG%" 2>&1
claude --model claude-sonnet-4-6 -p "Read GOLD_TACTIC/prompts/asset_selector.md and execute exactly." --allowedTools "Bash,Read,Write,Grep,Glob" >> "%GT_LOG%" 2>&1
set RC=%ERRORLEVEL%
echo [%date% %time%] Asset-Selector END rc=%RC% >> "%GT_LOG%" 2>&1
exit /b %RC%
```

### gt-market-monitor.cmd

Γράψε με το Write tool στο `GOLD_TACTIC/scripts/schtasks/gt-market-monitor.cmd`:

```cmd
@echo off
setlocal
set "GT_BASE=C:\Users\aggel\Desktop\trading"
set "GT_LOG=%USERPROFILE%\.claude\logs\gt-market-monitor.log"
cd /d "%GT_BASE%"
echo [%date% %time%] Market-Monitor START >> "%GT_LOG%" 2>&1
claude --model claude-sonnet-4-6 -p "Read GOLD_TACTIC/prompts/market_monitor.md and execute exactly." --allowedTools "Bash,Read,Write,Grep,Glob" >> "%GT_LOG%" 2>&1
set RC=%ERRORLEVEL%
echo [%date% %time%] Market-Monitor END rc=%RC% >> "%GT_LOG%" 2>&1
exit /b %RC%
```

**Σημείωση για Cowork:** Χρησιμοποίησε το Write tool για τα `.cmd` αρχεία. Τα Windows CRLF line endings δεν πειράζουν — ο `cmd.exe` τα διαχειρίζεται σωστά.

---

## ΒΗΜΑ 3 — Δημιουργία Scheduled Tasks (7 entries)

**ΣΗΜΑΝΤΙΚΟ:** Κάθε εντολή `schtasks` πρέπει να τυλίγεται σε `cmd //c "..."` λόγω Git Bash path translation. Double-escape backslashes στο task name (`\\GoldTactic\\GT-...`).

### 3a. Asset Selector — 4 tasks

```bash
# GT-Selector-AM — Weekdays 08:00 EET (πριν London KZ 10:00)
cmd //c "schtasks /Create /TN \\GoldTactic\\GT-Selector-AM /TR \"C:\\Users\\aggel\\Desktop\\trading\\GOLD_TACTIC\\scripts\\schtasks\\gt-asset-selector.cmd\" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 08:00 /F"

# GT-Selector-Mid — Weekdays 14:30 EET (πριν NY KZ 15:30)
cmd //c "schtasks /Create /TN \\GoldTactic\\GT-Selector-Mid /TR \"C:\\Users\\aggel\\Desktop\\trading\\GOLD_TACTIC\\scripts\\schtasks\\gt-asset-selector.cmd\" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 14:30 /F"

# GT-Selector-EVE — Weekdays 20:00 EET (end-of-day + overnight)
cmd //c "schtasks /Create /TN \\GoldTactic\\GT-Selector-EVE /TR \"C:\\Users\\aggel\\Desktop\\trading\\GOLD_TACTIC\\scripts\\schtasks\\gt-asset-selector.cmd\" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 20:00 /F"

# GT-Selector-WE — Weekend (Sat+Sun) 10:00 EET (crypto only)
cmd //c "schtasks /Create /TN \\GoldTactic\\GT-Selector-WE /TR \"C:\\Users\\aggel\\Desktop\\trading\\GOLD_TACTIC\\scripts\\schtasks\\gt-asset-selector.cmd\" /SC WEEKLY /D SAT,SUN /ST 10:00 /F"
```

### 3b. Market Monitor — 3 tasks

```bash
# GT-Monitor-Peak — Weekdays 08:00-22:00, κάθε 20 min (καλύπτει London + NY KZ)
cmd //c "schtasks /Create /TN \\GoldTactic\\GT-Monitor-Peak /TR \"C:\\Users\\aggel\\Desktop\\trading\\GOLD_TACTIC\\scripts\\schtasks\\gt-market-monitor.cmd\" /SC MINUTE /MO 20 /ST 08:00 /ET 22:00 /F"

# GT-Monitor-OffPeak — Weekdays 22:00-08:00, κάθε 40 min (Asian, μόνο Tier A/B)
cmd //c "schtasks /Create /TN \\GoldTactic\\GT-Monitor-OffPeak /TR \"C:\\Users\\aggel\\Desktop\\trading\\GOLD_TACTIC\\scripts\\schtasks\\gt-market-monitor.cmd\" /SC MINUTE /MO 40 /ST 22:00 /ET 08:00 /F"

# GT-Monitor-Weekend — Sat+Sun 10:00-22:00, κάθε 40 min (crypto only)
cmd //c "schtasks /Create /TN \\GoldTactic\\GT-Monitor-Weekend /TR \"C:\\Users\\aggel\\Desktop\\trading\\GOLD_TACTIC\\scripts\\schtasks\\gt-market-monitor.cmd\" /SC MINUTE /MO 40 /ST 10:00 /ET 22:00 /F"
```

**Note για `/ET`:** Σε κάποιες versions των Windows, το `/ET` flag αγνοείται ή δεν δουλεύει σωστά. Ο Monitor prompt έχει **εσωτερικό session check** (STEP 2.5 + 4.8) που κάνει auto time-gating — οπότε ακόμα κι αν τρέξει εκτός παραθύρου, θα στείλει Tier A και δεν θα ανοίξει trades. Αν μετά το create δεις ότι το `/ET` αγνοείται, απλά αφαίρεσέ το και αφήσε τον prompt να κάνει gating.

---

## ΒΗΜΑ 4 — Verification

### 4a. Count tasks (πρέπει να είναι ΑΚΡΙΒΩΣ 7)

```bash
cmd //c "schtasks /Query /FO CSV /NH" 2>&1 | grep -c "GoldTactic"
# Expected output: 7
```

### 4b. Show all 7 task names με next run time

```bash
cmd //c "schtasks /Query /FO LIST /V" 2>&1 | grep -A1 "GoldTactic" | head -30
```

Θα δείξει κάθε task + το "Next Run Time". Επιβεβαίωσε:
- Τα 4 Selector tasks έχουν specific ώρες (08:00, 14:30, 20:00 weekday / 10:00 weekend)
- Τα 3 Monitor tasks τρέχουν κάθε N λεπτά

### 4c. Smoke test #1 — Asset Selector

```bash
cmd //c "schtasks /Run /TN \\GoldTactic\\GT-Selector-AM"
```

**Περίμενε 60-90 δευτερόλεπτα**, μετά:
```bash
# 1. Έλεγξε ότι έγραψε selected_assets.json με νέο timestamp
cat GOLD_TACTIC/data/selected_assets.json | head -20

# 2. Έλεγξε ότι το log δεν έχει error
tail -20 "$USERPROFILE/.claude/logs/gt-asset-selector.log"
```

**Επιβεβαίωση επιτυχίας:**
- `selected_assets.json` περιέχει 4 assets με `direction` και `trade_probability`
- Telegram message received ("🎯 ΕΠΙΛΕΓΜΕΝΑ ASSETS")
- Log ends με `rc=0`

### 4d. Smoke test #2 — Market Monitor (full cycle)

```bash
cmd //c "schtasks /Run /TN \\GoldTactic\\GT-Monitor-Peak"
```

**Περίμενε 90-120 δευτερόλεπτα**, μετά:
```bash
# 1. Έλεγξε briefing log για νέο entry
tail -20 GOLD_TACTIC/data/briefing_log.md

# 2. Έλεγξε ότι έγραψε trs_current.json
cat GOLD_TACTIC/data/trs_current.json | python -m json.tool

# 3. Έλεγξε ότι το session_now.json φρεσκάρεται
cat GOLD_TACTIC/data/session_now.json

# 4. Έλεγξε ότι το pinned dashboard έγινε update (via Telegram)
cat GOLD_TACTIC/data/telegram_state.json | python -c "import json,sys; d=json.load(sys.stdin); print('pinned_dashboard_id:', d.get('pinned_dashboard_id'))"

# 5. Log
tail -20 "$USERPROFILE/.claude/logs/gt-market-monitor.log"
```

**Επιβεβαίωση επιτυχίας:**
- Telegram μήνυμα received (Tier A/B/C ανάλογα με το τι βρήκε)
- Pinned dashboard updated στο top του chat (session badge, 4 assets, open trades section)
- `briefing_log.md` έχει νέο entry
- `session_now.json` έχει `tier`, `name`, `emoji`

### 4e. Smoke test #3 — Trade Manager CLI (χωρίς open trades)

```bash
# Tick με άδειο state
python GOLD_TACTIC/scripts/trade_manager.py tick
# Expected: [] (άδειο array όταν δεν υπάρχουν open trades)

# List
python GOLD_TACTIC/scripts/trade_manager.py list
# Expected: "No open trades"

# Header (κρίσιμο — αυτό καλεί ο Monitor STEP 4.95 σε ΚΑΘΕ cycle)
python GOLD_TACTIC/scripts/trade_manager.py header
# Expected: κενό output όταν δεν υπάρχουν open trades
```

Αν και τα 3 commands δεν βγάλουν error → το trade_manager είναι wired σωστά για τον Monitor να τα καλεί σε STEP 4.95 (header), STEP 5.7 (open) και STEP 5.8 (tick).

---

## ΒΗΜΑ 5 — Post-Install Report (στείλε στον χρήστη)

Στείλε στον χρήστη ένα Telegram message ότι όλα έγιναν:

```bash
python GOLD_TACTIC/scripts/telegram_sender.py message "✅ <b>GOLD TACTIC v7.2 Schedules Installed</b>
━━━━━━━━━━━━━━━━━━━━━━
📅 7 scheduled tasks ενεργά:
• Selector: 08:00, 14:30, 20:00 (weekday) + 10:00 (weekend)
• Monitor: peak every 20' / off-peak every 40' / weekend every 40'

🎯 Στόχος: 30€/day · Max 2 trades · Max hold 4h
🌍 Kill zones: London 10-12 · NY 15:30-17:30 EET

Το σύστημα τρέχει ήδη. Επόμενο auto-run: δες schtasks query."
```

---

## ΒΗΜΑ 6 — Troubleshooting (αν κάτι χάλασε)

| Symptom | Διάγνωση | Fix |
|---------|----------|-----|
| `schtasks /Create` βγάζει "Access denied" | Το Cowork δεν τρέχει as admin | Τρέξε Claude Code ως admin ή ζήτα από χρήστη |
| Task τρέχει αλλά το log γράφει "claude not found" | PATH issue στο wrapper | Σιγουρέψου ότι `claude` είναι στο system PATH (`where claude` στο cmd) |
| Log λέει "rc=1" ή "rc=2" | Error στο prompt execution | Διάβασε το full log στο `.claude/logs/gt-*.log` για stacktrace |
| Telegram δεν λαμβάνει messages | `.env` missing ή invalid token | `ls -la .env` + test `python GOLD_TACTIC/scripts/telegram_sender.py detect-chat` |
| `trade_manager.py` import error | Missing `risk_manager.py` | Έλεγξε ΒΗΜΑ 0 — γίνε sure όλα τα scripts υπάρχουν |
| Dashboard δεν δείχνει Open Trades | `trade_state.json` δεν υπάρχει ακόμα | Κανονικό αν δεν έχει γίνει open trade ακόμα. Θα εμφανιστεί auto την πρώτη φορά που fires Tier C signal |
| Monitor tasks τρέχουν εκτός peak hours | `/ET` αγνοήθηκε από Windows | Ο internal time-gating του prompt (STEP 4.8) κόβει Tier C. Δεν είναι πρόβλημα. |

---

## SUMMARY — Τι έχεις τώρα

| Component | Πότε τρέχει | Τι κάνει |
|-----------|-------------|----------|
| **GT-Selector-AM** | Weekday 08:00 | Διαλέγει 4 assets για London KZ |
| **GT-Selector-Mid** | Weekday 14:30 | Refresh πριν NY KZ |
| **GT-Selector-EVE** | Weekday 20:00 | End-of-day + overnight |
| **GT-Selector-WE** | Sat+Sun 10:00 | Weekend crypto-only |
| **GT-Monitor-Peak** | Weekday 08:00-22:00 κάθε 20' | Header prepend · Tier A/B/C · probe/full/confirm auto-open · TP1→BE→TP2 tick |
| **GT-Monitor-OffPeak** | Weekday 22:00-08:00 κάθε 40' | Header prepend · Tier A/B · tick open trades (BE/TP2/SL/max-hold) |
| **GT-Monitor-Weekend** | Sat+Sun 10:00-22:00 κάθε 40' | Crypto only · header · Tier A/B/C · tick |

**Logs:** `%USERPROFILE%\.claude\logs\gt-*.log`
**State files:** `GOLD_TACTIC/data/*.json` (portfolio, trade_state, selected_assets, trs_current, session_now, ...)
**Telegram state:** `GOLD_TACTIC/data/telegram_state.json` (pinned dashboard id, last message ids)

Από εδώ και πέρα το σύστημα τρέχει μόνο του 24/7. Ο χρήστης βλέπει όλα μέσω Telegram (pinned dashboard + real-time messages).
