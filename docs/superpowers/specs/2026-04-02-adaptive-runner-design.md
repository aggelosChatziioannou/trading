# Adaptive Runner Design
**Date:** 2026-04-02
**Status:** Draft
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

1. **One Windows Task Scheduler entry** — calls `analyst_runner.py` every 5 minutes (08:00–22:00)
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
| `run_at` | `HH:MM` EET | When to run next cycle |
| `cycle_type` | `analyst` / `scanner_morning` / `scanner_afternoon` | Which prompt to load |
| `tier_hint` | `1` / `2` / `3` | For logging only — Claude decides final tier |
| `reason` | free text | Why this timing (1 line) |

### Bootstrap (file missing or `date < today`)

```
If 08:00–09:00 EET → cycle_type: scanner_morning, run_at: now
Else               → cycle_type: analyst, tier_hint: 3, run_at: now
```

### .gitignore

Add `GOLD_TACTIC/data/next_cycle.json` to the ignore section (operational/transient state).

---

## Component 2: `scripts/analyst_runner.py`

### Logic (pseudocode)

```
1. If now < 08:00 or now >= 22:00 → exit (dead zone)

2. SAFETY CHECK: if ANTHROPIC_API_KEY in environment → print warning + exit
   (prevents accidental API billing instead of subscription usage)

3. Read data/next_cycle.json
   → If missing or date < today → bootstrap (see above)
   → If run_at > now → exit (not time yet)
   → If run_at <= now → proceed

4. Select prompt file based on cycle_type:
   analyst           → GOLD_TACTIC/prompts/adaptive_analyst.md
   scanner_morning   → GOLD_TACTIC/prompts/scanner_morning_v6.md
   scanner_afternoon → GOLD_TACTIC/prompts/scanner_afternoon_v6.md

5. Build prompt:
   "Εκτέλεσε cycle. Ώρα: {HH:MM} EET.
    Διάβασε: GOLD_TACTIC/prompts/{prompt_file} και εκτέλεσε ακριβώς.
    Working dir: C:\Users\aggel\Desktop\trading"

6. Call Claude:
   subprocess.run(
     ["claude", "-p", prompt, "--allowedTools", "Bash,Read,Write"],
     cwd="C:\\Users\\aggel\\Desktop\\trading",
     timeout=300
   )

7. Log result to data/runner_log.txt:
   "2026-04-02 14:37 | analyst tier2 | 45s | ok"

8. Exit
```

### Error handling

| Condition | Action |
|-----------|--------|
| `claude` not found in PATH | Log error + exit (runner tries again in 5 min) |
| Timeout (>300s) | Log timeout + exit |
| `next_cycle.json` not updated after call | Log warning — next heartbeat will bootstrap |
| `ANTHROPIC_API_KEY` set | Print warning + exit immediately |

### Key property: stateless

The runner has no internal state. Every 5-minute invocation is independent. If a cycle fails to write `next_cycle.json`, the next heartbeat detects the stale date and bootstraps automatically. No cycle failure can break the system permanently.

---

## Component 3: Prompt additions

### `adaptive_analyst.md` — new step 15d

After step 15c (news digest update), add:

```
15d → Schedule next cycle (ΠΑΝΤΑ — κάθε TIER, ΥΠΟΧΡΕΩΤΙΚΟ):
      Βάσει της "Απόφαση Wait Time" απόφασης:
      - Γράψε data\next_cycle.json:
        {
          "date": "<σήμερα YYYY-MM-DD>",
          "run_at": "<HH:MM EET επόμενου cycle>",
          "cycle_type": "analyst",
          "tier_hint": <1/2/3>,
          "reason": "<γιατί αυτό το timing — 1 γραμμή>"
        }
      Κανόνες:
      - Αν 15:20–15:35 EET και scanner_afternoon δεν έχει τρέξει σήμερα:
          cycle_type: "scanner_afternoon", run_at: "15:30", tier_hint: 3
      - Ακόμα και αν TIER 1 silence (δεν στάλθηκε Telegram) → ΓΡΑΨΕ το αρχείο
      - Ποτέ run_at εκτός 08:00–22:00
```

### `scanner_morning_v6.md` — new final step

```
Τελευταίο βήμα — γράψε data\next_cycle.json:
{
  "date": "<σήμερα>",
  "run_at": "<08:15 ή +15 λεπτά από τώρα>",
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
| Action | `python C:\Users\aggel\Desktop\trading\GOLD_TACTIC\scripts\analyst_runner.py` |
| If task is already running | Skip (do not start second instance) |
| Run whether user is logged on or not | No (only when logged on — PC must be active) |

---

## Files Changed

| File | Change |
|------|--------|
| `GOLD_TACTIC/scripts/analyst_runner.py` | NEW |
| `GOLD_TACTIC/data/next_cycle.json` | NEW (initial state) |
| `GOLD_TACTIC/prompts/adaptive_analyst.md` | +step 15d |
| `GOLD_TACTIC/prompts/scanner_morning_v6.md` | +final step |
| `GOLD_TACTIC/prompts/scanner_afternoon_v6.md` | +final step |
| `.gitignore` | ignore `next_cycle.json` and `runner_log.txt` |

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

The savings come from: Claude scheduling TIER 1 (500 tokens) or long waits during dead zones instead of running full analysis every 45 minutes.
