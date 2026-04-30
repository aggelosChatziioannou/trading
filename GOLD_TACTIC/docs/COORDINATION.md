# GOLD TACTIC v7.2 — Schedule Coordination Contract

> **Pre-go-live document** explaining how the 8 Claude app schedules cooperate.
> If you ever wonder "did the right schedule run? Did they hand off cleanly?" — start here.

**Updated:** 2026-04-29
**Owner:** [cycle_coordinator.py](GOLD_TACTIC/scripts/cycle_coordinator.py)

---

## The 8 Schedules

| # | Schedule | When (EET) | Prompt | Run name |
|---|----------|-----------|--------|----------|
| 1 | GT Asset Selector AM | Mon–Fri 08:00 | asset_selector.md | `morning` |
| 2 | GT Asset Selector PM | Mon–Fri 15:00 | asset_selector.md | `afternoon` |
| 3 | GT Asset Selector EVE | Mon–Fri 21:00 | asset_selector.md | `evening` |
| 4 | GT Asset Selector WE | Sat/Sun 10:00 | asset_selector.md | `weekend` |
| 5 | GT Market Monitor Peak | Mon–Fri 08:05–22:00 every 20' | market_monitor.md | — |
| 6 | GT Market Monitor OffPeak | Mon–Fri 22:00–00:00 every 40' | market_monitor.md | — |
| 7 | GT Market Monitor Night | Mon–Fri 00:00–07:40 every 40' | market_monitor.md | — |
| 8 | GT Market Monitor WE | Sat/Sun 10:00–22:00 every 40' | market_monitor.md | — |

---

## Cooperation Map

```
┌────────────────────────────────────────────────────────────────────┐
│                        SHARED STATE FILES                          │
├────────────────────────────────────────────────────────────────────┤
│  data/selected_assets.json  ← Selector writes (atomic, with ts)    │
│  data/selector_done.json    ← Selector writes summary on success   │
│  data/selector.lock         ← Selector lock (start→end of run)     │
│  data/cycle_log.jsonl       ← BOTH append per-cycle audit          │
│  data/briefing_log.md       ← Monitor appends, EVE rotates         │
│  data/trs_current.json      ← Monitor writes for Dashboard         │
│  data/trade_state.json      ← trade_manager atomic writes          │
│  data/trade_journal.jsonl   ← trade_manager append-only audit      │
│  data/telegram_state.json   ← pinned dashboard ID persistence      │
│  data/data_health.json      ← Both write before Dashboard refresh  │
│  data/embargo_state.json    ← Both write before Dashboard refresh  │
│  data/session_now.json      ← Both regenerate per cycle            │
└────────────────────────────────────────────────────────────────────┘
```

---

## The Lifecycle of a Selector Run

### Selector AM (08:00) example flow:

```
[08:00:00]  STEP 1: cycle_coordinator.py selector-start morning
            → writes data/selector.lock { run_name: morning, started_at: 08:00 }

[08:00:01]  STEP 2: pipeline fetches (price_checker, news_scout --full, quick_scan, calendar)
[08:00:35]  STEP 3-5: analyze 12 assets, score, pick top 4
[08:00:42]  STEP 5: atomic write data/selected_assets.json { timestamp, selector_run, selected[4] }
[08:00:45]  STEP 6: send Telegram selection message
[08:00:48]  STEP 6.5: refresh data_health.json + embargo_state.json + dashboard
[08:00:52]  STEP 7 (AM only): send Battle Plan
[08:00:55]  STEP 6.9: cycle_coordinator.py selector-done morning 4 47.3 9 0
            → writes data/selector_done.json
            → appends data/cycle_log.jsonl entry
            → DELETES data/selector.lock
```

### Edge case: Selector EVE (21:00)
Adds briefing_log rotation between STEP 6 and STEP 6.9:
```
[21:00:42]  Rotate briefing_log → archive briefing_log_2026-04-29.md
            Create fresh briefing_log.md
            cycle_coordinator.py seed-briefing-log → seed entry so Monitor 21:05 has context
```

---

## The Lifecycle of a Monitor Cycle

### Monitor Peak example flow:

```
[08:05:00]  STEP 0: cycle_coordinator.py monitor-start
            → reads data/selector.lock
            → if Selector lock exists & age < 5min:
                  exit code 2 → Monitor sends silent skip message + exits
            → if no lock OR stale: exit code 0 → proceed

[08:05:02]  STEP 1: read selected_assets.json + selector_done.json
            cycle_coordinator.py selector-ref-line > data/selector_ref.txt
            → "🎯 Watched: AM Selector @08:00 (5' ago) — XAU·EUR·BTC·NAS"

[08:05:05]  STEP 2: pipeline (price_checker, news_scout --light, quick_scan, session_check)
[08:05:18]  STEP 2.5: session check
[08:05:19]  STEP 2.7: data_health check (banner if CRITICAL)
[08:05:20]  STEP 3: read all data
[08:05:25]  STEP 4: analyze 4 assets, compute TRS, detect changes
[08:05:30]  STEP 4.7-4.95: news impact, gates, embargo check, open-trades header
[08:05:32]  STEP 5: compose L1/L2/L3/L4 message with selector_ref line at top
[08:05:35]  STEP 5.7: auto-open trade if Tier C signal (with embargo check)
[08:05:38]  STEP 5.8: trade_manager.py tick (close/progress/BE/timeout)
[08:05:40]  STEP 6: append briefing_log
[08:05:42]  STEP 6.5: log TRS history
[08:05:44]  STEP 6.7: refresh data_health.json + embargo_state.json + dashboard
[08:05:47]  STEP 6.7 cont: cycle_coordinator.py monitor-done L1 47.0 --trades-opened=0 --trades-closed=0
            → appends data/cycle_log.jsonl entry
```

---

## Race Condition Scenarios & Handling

### S1: Selector overruns into Monitor cycle (e.g., 08:00–08:07)
```
[08:00] Selector starts → writes lock
[08:05] Monitor Peak starts → reads lock, age=5min, returns exit 2
[08:05] Monitor sends "⏸️ Monitor skip — Selector morning τρέχει (5min). Επόμενο cycle θα διαβάσει τα νέα assets."
[08:07] Selector finishes → done signal + lock cleared
[08:25] Next Monitor cycle proceeds normally
```

### S2: Selector crashed (lock never cleared)
```
[15:00] Selector PM crashes after writing lock, before done signal
[15:05] Monitor Peak: lock age=5min — STALE THRESHOLD met (>5min) → coordinator clears lock + proceeds
[15:25] Next Monitor cycle: lock gone, no impact
```

### S3: Two Monitor cycles overlap (rare — only if previous took >20')
```
[08:25] Monitor cycle A still running at 22'
[08:25] Monitor cycle B starts → no Selector lock check fails this case BUT
                                  cycle_log will show overlap
```
**Note:** Currently no Monitor-vs-Monitor lock. If observed in practice, add monitor.lock similar to selector.lock.

### S4: trade_state.json contention
```
trade_manager uses atomic writes (tmp + rename). Single writer at a time is OK.
If Monitor cycle reads trade_state during a tick() write → reads either pre or post (atomic).
No partial-state corruption.
```

---

## Outputs Emitted by Each Schedule

### Selector outputs (per run):
- `data/selected_assets.json` — top 4 + scores + reasoning
- `data/selector_done.json` — run summary (label, duration, sources)
- `data/selector.lock` — only DURING run
- `data/cycle_log.jsonl` — append entry on success
- `data/news_feed.json` — news_scout output (10 sources)
- `data/economic_calendar.json` — events
- `data/quick_scan.json` — indicators
- `data/data_health.json` + `data/embargo_state.json` — at end before dashboard
- Telegram messages: selection summary + (AM only) Battle Plan + dashboard refresh

### Monitor outputs (per cycle):
- `data/news_feed.json` — refreshed (light mode)
- `data/quick_scan.json` — refreshed
- `data/session_now.json` — refreshed
- `data/data_health.json` — refreshed
- `data/embargo_state.json` — refreshed
- `data/trs_current.json` — TRS snapshot for Dashboard
- `data/trs_history.jsonl` — append TRS log
- `data/briefing_log.md` — append cycle entry
- `data/trade_state.json` + `data/trade_journal.jsonl` (if trade event)
- `data/cycle_log.jsonl` — append entry on success
- Telegram messages: 1 per cycle (L1/L2/L3/L4) + replies for trade events

---

## Verification Commands

### Coordination state
```bash
python GOLD_TACTIC/scripts/cycle_coordinator.py status
```

Output sample:
```
🔓 Lock: clear (no Selector running)
✅ Last Selector: morning @ 08:00 (2h45' ago)
   Selected: EURUSD, AUDUSD, BTC, NAS100
   Duration: 47.3s · Sources: 9/9

🎯 Watched: AM Selector @08:00 (2h45' ago) — EUR·AUD·BTC·NAS
Next Monitor cycle # for today: 9

Last 5 cycle_log entries:
  [10:45:33] GT_Monitor_Peak L=L1 (32s) opened=0 closed=0
  [10:25:21] GT_Monitor_Peak L=L2 (38s) opened=0 closed=0
  [10:05:12] GT_Monitor_Peak L=L3 (45s) opened=0 closed=0
  [10:00:55] GT_Selector_PM → ['EURUSD','AUDUSD','BTC','NAS100'] (51s)
  [09:45:18] GT_Monitor_Peak L=L1 (29s) opened=0 closed=0
```

### Audit trail (last N events)
```bash
tail -20 GOLD_TACTIC/data/cycle_log.jsonl
```

### Selector reference line preview
```bash
python GOLD_TACTIC/scripts/cycle_coordinator.py selector-ref-line
```

---

## Failure Recovery

### "Monitor stuck — keeps reading old assets"
1. `python cycle_coordinator.py status` — check last selector
2. If `Last Selector` was hours ago → run a Selector manually (paste asset_selector.md prompt into fresh Claude session)
3. If lock is stuck → `rm data/selector.lock`

### "Two Selector messages came in 1 minute"
This shouldn't happen with the lock. If it does:
1. Check `cycle_log.jsonl` for both entries
2. Delete one selected_assets.json backup if needed
3. The lock should prevent it; if not, investigate filesystem race (Windows file locks?)

### "Monitor sent 2 messages for same cycle"
- Check `cycle_log.jsonl` — should be 1 entry per cycle
- If 2 entries with same timestamp range → 2 schedule instances ran simultaneously (Claude app schedule misfire)
- Pause the duplicate schedule, keep one

---

## Coordination Health Checks (manual, daily)

Run these once per day (e.g., morning routine):

```bash
# 1. Are all 4 expected schedules running?
python -c "
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime, timedelta, timezone
EET = timezone(timedelta(hours=3))
now = datetime.now(EET)
today = now.date()
expected = []
if now.weekday() < 5:  # Mon-Fri
    expected = ['GT_Selector_AM','GT_Selector_PM','GT_Selector_EVE']
else:
    expected = ['GT_Selector_WE']

with open('GOLD_TACTIC/data/cycle_log.jsonl',encoding='utf-8') as f:
    today_runs = [json.loads(l) for l in f if l.strip() and l.startswith('{\"ts\":\"'+today.strftime('%Y-%m-%d'))]
present = set(r.get('schedule','') for r in today_runs if r.get('type')=='selector')
for sched in expected:
    print(f'  {\"✅\" if sched in present else \"❌\"} {sched}')
"

# 2. Monitor cycle frequency (should be ~3/h peak, ~1.5/h offpeak)
grep '\"type\": \"monitor\"' GOLD_TACTIC/data/cycle_log.jsonl | tail -10
```

---

## Future Improvements (post v7.2)

- **Monitor → Monitor lock** for the rare case of >20min Monitor overrun
- **Telegram → Coordinator alert** if a daily expected Selector run is missing by +5min
- **Health snapshot send to Telegram** at end of day (22:00 EET): cycles ran, errors, recoveries
- **Cron-based watchdog** that checks selector_done.json freshness and pages user if stale >12h
