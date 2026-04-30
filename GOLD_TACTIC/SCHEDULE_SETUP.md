# GOLD TACTIC v7.2 — Claude App Schedule Installation Guide

> **Αυτό το αρχείο είναι self-contained Claude prompt.**
> Δώσ' το σε μια Claude Cowork session. Η session θα διαβάσει τις οδηγίες και θα δημιουργήσει τα 8 Claude app scheduled tasks που τρέχουν το σύστημα 24/7.
>
> **Version:** 7.2 | **Updated:** 2026-04-24
> **Runtime:** Claude Code Desktop (Pro subscription) — ΟΧΙ Windows Task Scheduler

---

## ΤΙ ΕΙΣΑΙ

Είσαι **Claude Cowork session** που εγκαθιστά **8 Claude app scheduled tasks** για το GOLD TACTIC v7.2 trading system.

**Working directory (absolute path):** `C:\Users\aggel\Desktop\trading`

**Τι κάνει το σύστημα όταν τελειώσεις:**
- **3 φορές/ημέρα (weekday) + 1 φορά/weekend:** τρέχει τον **Asset Selector** που σαρώνει 12 assets, επιλέγει top 4 για το επόμενο παράθυρο.
- **Κάθε 20' (peak) ή 40' (off-peak/weekend):** τρέχει τον **Market Monitor** που αναλύει τα 4 selected assets, στέλνει Telegram updates (Tier A/B/C), ανοίγει paper trades σε Tier C signals, παρακολουθεί open trades (progress pings, TP/SL, 4h timeout).
- Όλα σε **EET (UTC+3)**.

**Γιατί αυτά τα timings:**
- **Selector 08:00** → πριν London Kill Zone (10:00-12:00)
- **Selector 15:00** → πριν NY Kill Zone (15:30-17:30)
- **Selector 21:00** → end-of-day refresh
- **Monitor 08:05** offset → αποφεύγει race condition με Selector 08:00

---

## ΒΗΜΑ 0 — Prerequisites Check

```bash
# Python + Claude Code CLI
python --version            # >= 3.10
claude --version            # Claude Code CLI

# Prompts (2 ενεργά prompts — τα διαβάζει ο Claude κάθε φορά)
ls GOLD_TACTIC/prompts/asset_selector.md
ls GOLD_TACTIC/prompts/market_monitor.md

# Core scripts
ls GOLD_TACTIC/scripts/price_checker.py
ls GOLD_TACTIC/scripts/telegram_sender.py
ls GOLD_TACTIC/scripts/dashboard_builder.py
ls GOLD_TACTIC/scripts/session_check.py
ls GOLD_TACTIC/scripts/trade_manager.py
ls GOLD_TACTIC/scripts/risk_manager.py
ls GOLD_TACTIC/scripts/news_scout_v2.py
ls GOLD_TACTIC/scripts/quick_scan.py

# .env (Telegram credentials)
test -f .env && echo ".env OK" || echo "MISSING .env"
cat .env | grep TELEGRAM  # πρέπει να δείξει TELEGRAM_BOT_TOKEN + TELEGRAM_CHANNEL
```

Αν κάτι λείπει → `git pull` και ξαναέλεγξε.

---

## ΒΗΜΑ 1 — Δημιουργία Scheduled Tasks

Χρησιμοποίησε το **`schedule` skill** ή το **`CronCreate` tool** για να δημιουργήσεις τα 8 scheduled tasks παρακάτω.

Κάθε task χρειάζεται:
- **name:** το όνομα του task
- **schedule:** cron expression (EET timezone)
- **prompt:** ακριβώς αυτό που θα δοθεί στον agent όταν τρέξει

---

### Task 1 — GT Asset Selector AM

```
Name:     GT Asset Selector AM
Cron:     0 8 * * 1-5
Prompt:   Read GOLD_TACTIC/prompts/asset_selector.md and execute exactly. Working dir: C:\Users\aggel\Desktop\trading
```

### Task 2 — GT Asset Selector PM

```
Name:     GT Asset Selector PM
Cron:     0 15 * * 1-5
Prompt:   Read GOLD_TACTIC/prompts/asset_selector.md and execute exactly. Working dir: C:\Users\aggel\Desktop\trading
```

### Task 3 — GT Asset Selector EVE

```
Name:     GT Asset Selector EVE
Cron:     0 21 * * 1-5
Prompt:   Read GOLD_TACTIC/prompts/asset_selector.md and execute exactly. Working dir: C:\Users\aggel\Desktop\trading
```

### Task 4 — GT Asset Selector WE

```
Name:     GT Asset Selector WE
Cron:     0 10 * * 0,6
Prompt:   Read GOLD_TACTIC/prompts/asset_selector.md and execute exactly. Working dir: C:\Users\aggel\Desktop\trading
```

### Task 5 — GT Market Monitor Peak

Τρέχει κάθε 20 λεπτά, Δευτέρα-Παρασκευή, 08:05–22:00 EET.

```
Name:     GT Market Monitor Peak
Cron:     5-59/20 8 * * 1-5
Prompt:   Read GOLD_TACTIC/prompts/market_monitor.md and execute exactly. Working dir: C:\Users\aggel\Desktop\trading
```

> **Σημείωση:** Αν ο CronCreate δεν υποστηρίζει step ranges, δημιούργησε ξεχωριστό task:
> - `*/20 9-21 * * 1-5` (09:00 to 21:40) + `0,20,40 22 * * 1-5` (τελευταίο fire 22:00)

### Task 6 — GT Market Monitor OffPeak

Τρέχει κάθε 40 λεπτά, Δευτέρα-Παρασκευή, 22:00–00:00 EET.

```
Name:     GT Market Monitor OffPeak
Cron:     0,40 22-23 * * 1-5
Prompt:   Read GOLD_TACTIC/prompts/market_monitor.md and execute exactly. Working dir: C:\Users\aggel\Desktop\trading
```

### Task 7 — GT Market Monitor Night

Τρέχει κάθε 40 λεπτά, Δευτέρα-Παρασκευή, 00:00–07:40 EET.

```
Name:     GT Market Monitor Night
Cron:     0,40 0-7 * * 2-6
Prompt:   Read GOLD_TACTIC/prompts/market_monitor.md and execute exactly. Working dir: C:\Users\aggel\Desktop\trading
```

### Task 8 — GT Market Monitor WE

Τρέχει κάθε 40 λεπτά, Σαββατοκύριακο, 10:00–22:00 EET.

```
Name:     GT Market Monitor WE
Cron:     0,40 10-22 * * 0,6
Prompt:   Read GOLD_TACTIC/prompts/market_monitor.md and execute exactly. Working dir: C:\Users\aggel\Desktop\trading
```

### Task 9 — GT Weekly Audit (Self-Improvement Layer 3)

Τρέχει **μια φορά την εβδομάδα** Κυριακή 22:00 EET. Aggregates trade outcomes, runs 3 hypothesis detectors, sends weekly digest + calibration proposals.

```
Name:     GT Weekly Audit
Cron:     0 22 * * 0
Prompt:   Read GOLD_TACTIC/prompts/weekly_audit.md and execute exactly. Working dir: C:\Users\aggel\Desktop\trading
```

**Τι κάνει:** Aggregates `trade_journal.jsonl` + `trade_reflections.jsonl` της εβδομάδας → παράγει `weekly_audit_YYYY_WW.json/md` + ενημερώνει `strategy_scorecard.md` + queue calibration proposals (max 2/εβδομάδα) στο `calibration_proposals.json`. Στέλνει Telegram digest στις 22:30 + per-proposal silent notification.

**Δες:** [docs/SELF_IMPROVEMENT.md](docs/SELF_IMPROVEMENT.md) για το πλήρες workflow.

---

## ΒΗΜΑ 2 — Verification

### 2a. Λίστα tasks (πρέπει να είναι ΑΚΡΙΒΩΣ 9)

Χρησιμοποίησε το `CronList` tool ή `/schedule list`. Επιβεβαίωσε:
- 4 Asset Selector tasks (AM, PM, EVE, WE)
- 4 Market Monitor tasks (Peak, OffPeak, Night, WE)
- 1 Weekly Audit task (Sunday 22:00)

### 2b. Smoke test — Asset Selector

Τρέξε manually μια φορά:

```bash
claude --model claude-sonnet-4-6 -p "Read GOLD_TACTIC/prompts/asset_selector.md and execute exactly. Working dir: C:\Users\aggel\Desktop\trading" --allowedTools "Bash,Read,Write,Grep,Glob"
```

Περίμενε 60-90 δευτερόλεπτα. Επιβεβαίωσε:
- `GOLD_TACTIC/data/selected_assets.json` έχει 4 assets με `direction` + `trade_probability`
- Telegram message received "🎯 ΕΠΙΛΕΓΜΕΝΑ ASSETS"

### 2c. Smoke test — Market Monitor

```bash
claude --model claude-sonnet-4-6 -p "Read GOLD_TACTIC/prompts/market_monitor.md and execute exactly. Working dir: C:\Users\aggel\Desktop\trading" --allowedTools "Bash,Read,Write,Grep,Glob"
```

Περίμενε 90-120 δευτερόλεπτα. Επιβεβαίωσε:
- Telegram message received (Tier A/B/C)
- Pinned Dashboard updated
- `GOLD_TACTIC/data/briefing_log.md` έχει νέο entry

### 2d. Trade Manager sanity check

```bash
python GOLD_TACTIC/scripts/trade_manager.py list    # "No open trades"
python GOLD_TACTIC/scripts/trade_manager.py header  # κενό output (φυσιολογικό)
python GOLD_TACTIC/scripts/trade_manager.py tick    # []
```

---

## ΒΗΜΑ 3 — Post-Install Telegram notification

```bash
python GOLD_TACTIC/scripts/telegram_sender.py message "✅ <b>GOLD TACTIC v7.2 Schedules Installed</b>
━━━━━━━━━━━━━━━━━━━━━━
📅 8 Claude app scheduled tasks ενεργά:
• Selector: 08:00, 15:00, 21:00 (weekday) + 10:00 (weekend)
• Monitor Peak: κάθε 20' (08:05–22:00 Mon–Fri)
• Monitor OffPeak: κάθε 40' (22:00–00:00 Mon–Fri)
• Monitor Night: κάθε 40' (00:00–07:40 Mon–Fri)
• Monitor WE: κάθε 40' (10:00–22:00 Sat–Sun)

🎯 Στόχος: 30€/day · Max 2 trades · Max hold 4h
🌍 Kill zones: London 10-12 · NY 15:30-17:30 EET"
```

---

## Troubleshooting

| Symptom | Διάγνωση | Fix |
|---------|----------|-----|
| Task δεν εκτελείται | Schedule δεν αποθηκεύτηκε | `CronList` → επαλήθευσε ότι εμφανίζεται |
| `selected_assets.json` παλιό | Asset Selector δεν τρέχει | Manual smoke test (ΒΗΜΑ 2b) |
| Telegram σιωπή | `.env` λείπει ή λάθος token | `cat .env` + `python GOLD_TACTIC/scripts/telegram_sender.py detect-chat` |
| `trade_manager.py` error | Python path issue | Τρέξε από `C:\Users\aggel\Desktop\trading` root |
| Dashboard δεν δείχνει Open Trades | Κανένα open trade ακόμα | Φυσιολογικό — εμφανίζεται μόλις fire Tier C signal |
| Monitor τρέχει εκτός ωραρίου | Cron ανοιχτό | Ο prompt έχει internal time-gating (STEP 2.5) — Tier C ΜΟΝΟ σε optimal zone |

---

## Summary — 8 Claude App Schedules

| Task | Cron | Πότε | Τι κάνει |
|------|------|------|----------|
| **GT Asset Selector AM** | `0 8 * * 1-5` | Mon–Fri 08:00 | Επιλέγει top 4 πριν London KZ |
| **GT Asset Selector PM** | `0 15 * * 1-5` | Mon–Fri 15:00 | Refresh πριν NY KZ |
| **GT Asset Selector EVE** | `0 21 * * 1-5` | Mon–Fri 21:00 | End-of-day rotation |
| **GT Asset Selector WE** | `0 10 * * 0,6` | Sat/Sun 10:00 | Crypto-only |
| **GT Monitor Peak** | `5-59/20 8 * * 1-5` | Mon–Fri 08:05–22 / 20' | Tier A/B/C · open trades · tick |
| **GT Monitor OffPeak** | `0,40 22-23 * * 1-5` | Mon–Fri 22–00 / 40' | Tier A/B · tick open trades |
| **GT Monitor Night** | `0,40 0-7 * * 2-6` | Mon–Fri 00–08 / 40' | Watchdog · Tier A |
| **GT Monitor WE** | `0,40 10-22 * * 0,6` | Sat/Sun 10–22 / 40' | Crypto Tier A/B/C |

**State files:** `GOLD_TACTIC/data/` (portfolio.json, selected_assets.json, trs_current.json, telegram_state.json, briefing_log.md)
**Prompts:** `GOLD_TACTIC/prompts/asset_selector.md` + `market_monitor.md`
