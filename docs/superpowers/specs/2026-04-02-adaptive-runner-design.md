# Adaptive Runner Design
**Date:** 2026-04-02
**Status:** Approved
**Scope:** GOLD TACTIC — Automated cycle execution via Claude Code CLI + Windows Task Scheduler

---

## Problem

The current system relies on manual Cowork scheduled tasks with **fixed intervals** (8 tasks, PRIME every 15', MIDDAY every 45', NY every 15', etc.). Problems:

1. **Not adaptive** — runs full analysis even during dead markets
2. **High rate limit consumption** — ~40 fixed cycles/day regardless of market activity
3. **Manual setup** — 8 separate Cowork tasks to maintain
4. **No self-awareness** — Claude cannot decide "I need to run again in 5 minutes, trade is close"

---

## Solution Overview

Replace all 8 Cowork schedules with:

1. **One Windows Task Scheduler entry** — calls `analyst_runner.py` every 5 minutes (08:00–22:00 weekdays, 08:00–22:00 weekends — dead-zone filtering is done inside the runner)
2. **`analyst_runner.py`** — lightweight heartbeat: checks `next_cycle.json`, calls `claude -p` if time has come
3. **`data/next_cycle.json`** — Claude writes this at the end of every cycle, scheduling its own next run
4. **Prompt additions** — all three prompt files get a final step instructing Claude to write `next_cycle.json`

Claude controls its own cadence. The Python script only executes what Claude scheduled.

---

## Component 1: `data/next_cycle.json`

### Location
`GOLD_TACTIC/data/next_cycle.json`

### Structure

```json
{
  "date": "2026-04-02",
  "run_at": "14:37",
  "cycle_type": "analyst",
  "tier_hint": 2,
  "reason": "TRS 4 — XAUUSD approaching setup"
}
```

### Fields

| Field | Values | Purpose |
|-------|--------|---------|
| `date` | `YYYY-MM-DD` | If `date < today` → new day bootstrap |
| `run_at` | `HH:MM` EET (validated as `\d{2}:\d{2}`) | When to run next cycle |
| `cycle_type` | `analyst` / `scanner_morning` / `scanner_afternoon` | Which prompt to load |
| `tier_hint` | `1` / `2` / `3` | For timeout selection + logging — Claude decides final tier |
| `reason` | free text | Why this timing (1 line) |

### Bootstrap (file missing, `date < today`, or malformed `run_at`)

```
Weekday:
  If now < 10:00 EET → cycle_type: scanner_morning, run_at: now
  Else               → cycle_type: analyst, tier_hint: 3, run_at: now

Weekend (Saturday / Sunday):
  If now < 10:00 EET → exit (outside weekend window — wait)
  If now >= 10:00 and now < 10:15 → cycle_type: scanner_morning, run_at: now
  Else               → cycle_type: analyst, tier_hint: 3, run_at: now
```

**Rationale for 10:00 weekday window (not 09:00):** Covers multi-day gaps where PC was off — on resume any time before 10:00 on a trading day, the morning scanner should still run to refresh the watchlist.

**Rationale for 10:15 weekend scanner_morning cutoff:** After 10:15 on a weekend, the crypto markets are already active and an immediate analyst cycle is more valuable than a scanner setup. The scanner_morning window on weekends is deliberately narrow (10:00–10:15).

**Note on `run_at` time validation:** The regex `\d{2}:\d{2}` should also range-check `00 <= HH <= 23` and `00 <= MM <= 59` to guard against arithmetic overflow producing values like `25:99`.

### .gitignore

Add to ignore section (operational/transient — no value in git history):
- `GOLD_TACTIC/data/next_cycle.json`
- `GOLD_TACTIC/data/runner_log.txt`
- `GOLD_TACTIC/data/scanner_afternoon_ran.txt`

---

## Component 2: `scripts/analyst_runner.py`

### Dead zone rules

| Day | Active window | Dead zone |
|-----|--------------|-----------|
| Weekday (Mon–Fri) | 08:00–22:00 EET | before 08:00, from 22:00 |
| Weekend (Sat–Sun) | 10:00–20:00 EET | before 10:00, from 20:00 |

Outside active window → exit immediately (Task Scheduler fires but runner does nothing).

### Logic (pseudocode)

```
1. Determine if weekday or weekend (datetime.weekday())
   Apply dead-zone rule above → exit if outside active window

2. SAFETY CHECK:
   if os.environ.get("ANTHROPIC_API_KEY"):  # non-empty = API key is set
       print("ERROR: ANTHROPIC_API_KEY is set — this would bill via API, not subscription.")
       print("Unset ANTHROPIC_API_KEY from environment before running.")
       sys.exit(1)

3. Read data/next_cycle.json
   → If missing → bootstrap
   → If date < today → bootstrap
   → If run_at does not match \d{2}:\d{2} → log "malformed run_at" + bootstrap
   → If cycle_type not in ["analyst","scanner_morning","scanner_afternoon"]
       → log "unknown cycle_type" + bootstrap
   → If run_at > now → exit (not time yet)
   → If run_at <= now → proceed

4. Scanner afternoon override (runner-level, not Claude-level):
   If weekday AND now is 15:20–15:40 EET:
     Check if scanner_afternoon ran today:
       → Read next_cycle.json history or check data/scanner_afternoon_ran.txt
       → If NOT run today → force cycle_type: scanner_afternoon

5. Select prompt file based on cycle_type:
   analyst           → GOLD_TACTIC/prompts/adaptive_analyst.md
   scanner_morning   → GOLD_TACTIC/prompts/scanner_morning_v6.md
   scanner_afternoon → GOLD_TACTIC/prompts/scanner_afternoon_v6.md

6. Select timeout based on tier_hint:
   tier_hint 1 → 60s
   tier_hint 2 → 180s
   tier_hint 3 (or missing) → 480s

7. Build prompt:
   "Εκτέλεσε cycle. Ώρα: {HH:MM} EET.
    Διάβασε: GOLD_TACTIC/prompts/{prompt_file} και εκτέλεσε ακριβώς.
    Working dir: ."

8. Call Claude (full path to avoid PATH issues in Task Scheduler):
   CLAUDE_CMD = find_claude_executable()  # checks known install paths
   subprocess.run(
     [CLAUDE_CMD, "-p", prompt, "--allowedTools", "Bash,Read,Write"],
     cwd="C:\\Users\\aggel\\Desktop\\trading",
     timeout=timeout
   )

9. If scanner_afternoon ran: write data/scanner_afternoon_ran.txt with today's date

10. Log result to data/runner_log.txt:
    "2026-04-02 14:37 | analyst tier2 | 45s | ok"

11. Exit
```

### `find_claude_executable()` logic

```python
# Try in order:
candidates = [
    "claude",                                          # if in PATH
    r"C:\Users\aggel\AppData\Roaming\npm\claude.cmd",  # npm global install
    r"C:\Users\aggel\AppData\Local\Programs\claude\claude.exe",
]
for c in candidates:
    if shutil.which(c) or Path(c).exists():
        return c
raise RuntimeError("claude executable not found")
```

### Error handling

| Condition | Action |
|-----------|--------|
| `ANTHROPIC_API_KEY` set | Print financial risk warning + `sys.exit(1)` |
| `claude` not found | Log error + exit (runner tries again in 5 min) |
| Timeout (tier-specific) | Log timeout + exit (next heartbeat bootstraps) |
| `next_cycle.json` not updated after call | Detected on next heartbeat → bootstrap |
| Malformed `run_at` | Log "malformed" + bootstrap |
| Unknown `cycle_type` | Log "unknown cycle_type" + bootstrap |

### Key property: stateless

Every 5-minute invocation is fully independent. No cycle failure can break the system permanently — the next heartbeat detects a stale/missing `next_cycle.json` and self-heals via bootstrap.

### Note on Task Scheduler session requirement

The Task Scheduler entry is set to "Run only when user is logged on" because Claude Code CLI requires an active user session — it uses OAuth credentials tied to the claude.ai Max subscription, not a headless API key. It cannot run in a background session without a logged-in user.

---

## Component 3: Prompt additions

### `adaptive_analyst.md` — new step 15d

Executes **after step 18** (Απόφαση Wait Time) — the tier decision must be made first, then encoded into `next_cycle.json`.

```
15d → Schedule next cycle (ΠΑΝΤΑ — κάθε TIER, ΥΠΟΧΡΕΩΤΙΚΟ):
      Εκτελείται ΜΕΤΑ το βήμα 18 (αφού αποφασίστηκε το επόμενο TIER + wait time):
      - Γράψε data\next_cycle.json:
        {
          "date": "<σήμερα YYYY-MM-DD>",
          "run_at": "<HH:MM EET επόμενου cycle>",
          "cycle_type": "analyst",
          "tier_hint": <1/2/3 — βάσει απόφασης βήματος 18>,
          "reason": "<γιατί αυτό το timing — 1 γραμμή>"
        }
      Κανόνες:
      - Ακόμα και αν TIER 1 silence (δεν στάλθηκε Telegram) → ΓΡΑΨΕ το αρχείο
      - Ποτέ run_at εκτός active window (08:00–22:00 weekday, 10:00–20:00 weekend)
      - Σε weekday: αν η ώρα είναι 14:00–15:20 και scanner_afternoon δεν έχει τρέξει
          → schedule run_at: "15:30", cycle_type: "analyst" (ο runner θα ανακατευθύνει)
```

**Note:** The `scanner_afternoon` trigger is handled at the runner level (step 4 in runner logic) as a safety net. The prompt rule above is advisory — the runner override is authoritative.

### `scanner_morning_v6.md` — new final step

```
Τελευταίο βήμα — γράψε data\next_cycle.json:
{
  "date": "<σήμερα>",
  "run_at": "<τώρα + 15 λεπτά, format HH:MM>",
  "cycle_type": "analyst",
  "tier_hint": 3,
  "reason": "post morning scanner — full cycle"
}
```

### `scanner_afternoon_v6.md` — new final step

```
Τελευταίο βήμα — γράψε data\next_cycle.json:
{
  "date": "<σήμερα>",
  "run_at": "15:45",
  "cycle_type": "analyst",
  "tier_hint": 3,
  "reason": "post afternoon scanner — NY open"
}
```

---

## Component 4: Windows Task Scheduler

**One single task** replaces all 8 Cowork schedules:

| Setting | Value |
|---------|-------|
| Name | `GOLD TACTIC Runner` |
| Trigger | Every 5 minutes, 08:00–22:00, every day |
| Action | `python GOLD_TACTIC\scripts\analyst_runner.py` |
| If task is already running | **Skip** (do not start second instance) |
| Run whether user is logged on or not | **No** — requires active user session (Max subscription OAuth) |

The runner's internal dead-zone logic handles the finer-grained time windows (e.g., weekend 10:00–20:00). The Task Scheduler boundary (08:00–22:00) is just the outer safety net.

---

## Additional Files

| File | Purpose |
|------|---------|
| `GOLD_TACTIC/data/scanner_afternoon_ran.txt` | Single-line date file: `"2026-04-02"`. Runner writes after scanner_afternoon completes. Checked in runner step 4 to prevent double-run. Ignored by git. |

---

## Files Changed

| File | Change |
|------|--------|
| `GOLD_TACTIC/scripts/analyst_runner.py` | NEW |
| `GOLD_TACTIC/data/next_cycle.json` | NEW (initial state: `{"date": null, ...}`) |
| `GOLD_TACTIC/data/scanner_afternoon_ran.txt` | NEW (auto-created by runner) |
| `GOLD_TACTIC/prompts/adaptive_analyst.md` | +step 15d (after step 18) |
| `GOLD_TACTIC/prompts/scanner_morning_v6.md` | +final step |
| `GOLD_TACTIC/prompts/scanner_afternoon_v6.md` | +final step |
| `.gitignore` | ignore `next_cycle.json`, `runner_log.txt`, `scanner_afternoon_ran.txt` |

---

## What Does NOT Change

- TIER 1/2/3 criteria and logic in `adaptive_analyst.md`
- TRS scoring, trade execution rules
- Telegram message formats
- All other data files and scripts
- The 10 rules that never change

---

## Token Efficiency vs Old Cowork Schedules

| | Old Cowork (fixed) | New Adaptive Runner |
|---|---|---|
| Cycles/day (quiet) | ~40 | ~15–20 |
| Cycles/day (active trading) | ~40 | ~30–40 |
| Rate limit usage (quiet day) | 100% | ~40–50% |
| Rate limit usage (active day) | 100% | ~80–90% |

Savings come from: Claude scheduling TIER 1 (500 tokens) or long waits during dead zones instead of running full analysis every 45 minutes regardless of market conditions.
