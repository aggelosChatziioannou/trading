# GOLD TACTIC v7.2 — Windows Scheduled Tasks Installer

Αυτός ο φάκελος περιέχει τον **ένα-click installer** για τα 7 scheduled tasks του GOLD TACTIC v7.2.
Από τη στιγμή που τρέξει, το σύστημα τρέχει μόνο του **24/7** (Selector 4x/ημέρα + Monitor κάθε 20'/40').

---

## Προαπαιτούμενα (one-time check)

- Windows 10 ή 11
- Python 3.10+ στο PATH
- Claude Code CLI στο PATH (`claude --version`)
- `.env` αρχείο στο `C:\Users\aggel\Desktop\trading\.env` με Telegram token + chat id
- Το project GOLD_TACTIC να είναι ήδη pulled στο `C:\Users\aggel\Desktop\trading\`

---

## Εγκατάσταση — 1 εντολή

1. Πάτα **Start** → γράψε "**PowerShell**" → δεξί κλικ → **"Run as administrator"**.
2. Επικόλλησε την παρακάτω εντολή και Enter:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\aggel\Desktop\trading\GOLD_TACTIC\scripts\schtasks\install-all.ps1"
```

Αν τρέξεις το script από PowerShell χωρίς admin, θα κάνει αυτόματο **self-elevate** και θα σου ζητήσει UAC confirmation.

Όταν τελειώσει (5-10 δευτ.) θα δεις:

```
============================================================
 ✅ 7/7 tasks installed
============================================================
```

…μαζί με πίνακα των 7 tasks και **next-run times**.

---

## Τι εγκαθίσταται

Όλα τα tasks μπαίνουν κάτω από το folder `\GoldTactic\` στο Task Scheduler:

| Task | Πότε τρέχει | Τι κάνει |
|------|-------------|----------|
| `GT-Selector-AM` | Mon-Fri 08:00 EET | Asset Selector πριν το London Kill Zone |
| `GT-Selector-Mid` | Mon-Fri 14:30 EET | Refresh πριν το NY Kill Zone |
| `GT-Selector-EVE` | Mon-Fri 20:00 EET | End-of-day + overnight selection |
| `GT-Selector-WE` | Sat+Sun 10:00 EET | Weekend crypto-only selection |
| `GT-Monitor-Peak` | Mon-Fri 08:00–22:00, κάθε 20' | Header prepend · Tier A/B/C · auto-open · TP1→BE→TP2 tick |
| `GT-Monitor-OffPeak` | Mon-Fri 22:00–08:00, κάθε 40' | Header · Tier A/B · tick open trades |
| `GT-Monitor-Weekend` | Sat+Sun 10:00–22:00, κάθε 40' | Crypto only · header · Tier A/B/C · tick |

**Ώρες:** όλες σε EET (UTC+3), δηλαδή στην ώρα του local PC.

---

## Verification (οποιαδήποτε στιγμή)

Δες τα 7 tasks:

```powershell
Get-ScheduledTask -TaskPath "\GoldTactic\*" | Format-Table TaskName,State
```

Δες το next-run time του καθενός:

```powershell
Get-ScheduledTask -TaskPath "\GoldTactic\*" | Get-ScheduledTaskInfo |
    Format-Table TaskName,NextRunTime,LastRunTime,LastTaskResult
```

Smoke test (τρέχει το Asset Selector χειροκίνητα — 60-90 δευτ.):

```powershell
Start-ScheduledTask -TaskPath "\GoldTactic\" -TaskName "GT-Selector-AM"
```

Και δες το log:

```powershell
Get-Content "$env:USERPROFILE\.claude\logs\gt-asset-selector.log" -Tail 20
```

---

## Rollback (αν θέλεις να σβήσεις ΟΛΑ τα tasks)

```powershell
Get-ScheduledTask -TaskPath "\GoldTactic\*" | Unregister-ScheduledTask -Confirm:$false
```

---

## Επανεγκατάσταση

Το script είναι **idempotent** — αν ξανατρέξεις το `install-all.ps1`, θα σβήσει πρώτα τα παλιά `\GoldTactic\*` tasks και θα τα ξαναφτιάξει καθαρά. Δεν χρειάζεται manual cleanup.

---

## Logs & State

- **Logs:** `%USERPROFILE%\.claude\logs\gt-asset-selector.log` + `%USERPROFILE%\.claude\logs\gt-market-monitor.log`
- **State files:** `GOLD_TACTIC\data\*.json` (portfolio, trade_state, selected_assets, trs_current, session_now)
- **Telegram state:** `GOLD_TACTIC\data\telegram_state.json` (pinned dashboard id)

---

## Troubleshooting

| Πρόβλημα | Λύση |
|----------|------|
| "Access denied" όταν τρέχει το script | Άνοιξε PowerShell **as Administrator** |
| "claude not found" στο log | Βεβαιώσου ότι το `claude` είναι στο system PATH (`where claude` σε cmd) |
| Tasks τρέχουν εκτός παραθύρου (π.χ. 03:00) | Ο Monitor prompt έχει internal session check (STEP 2.5/4.8) και κόβει Tier C. Δεν είναι πρόβλημα. |
| Telegram δεν λαμβάνει messages | `.env` missing/invalid. Test: `python GOLD_TACTIC\scripts\telegram_sender.py detect-chat` |
| Log γράφει `rc=1` | Άνοιξε όλο το log για stacktrace. Συνήθως λείπει script ή data file. |
