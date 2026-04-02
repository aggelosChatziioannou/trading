#!/usr/bin/env python3
"""
GOLD TACTIC — Analyst Runner
Heartbeat: checks next_cycle.json and calls Claude when scheduled.
Called every 5 minutes by Windows Task Scheduler.

Usage:
  python analyst_runner.py    # normal run (called by Task Scheduler)
"""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent          # trading/
DATA_DIR = Path(__file__).parent.parent / "data"
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

NEXT_CYCLE_FILE = DATA_DIR / "next_cycle.json"
RUNNER_LOG = DATA_DIR / "runner_log.txt"
SCANNER_AFTERNOON_RAN = DATA_DIR / "scanner_afternoon_ran.txt"

PROMPT_MAP = {
    "analyst":           PROMPTS_DIR / "adaptive_analyst.md",
    "scanner_morning":   PROMPTS_DIR / "scanner_morning_v6.md",
    "scanner_afternoon": PROMPTS_DIR / "scanner_afternoon_v6.md",
}

VALID_CYCLE_TYPES = set(PROMPT_MAP.keys())

TIMEOUTS = {1: 60, 2: 180, 3: 480}
DEFAULT_TIMEOUT = 480


# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg):
    """Write timestamped line to stdout and runner_log.txt."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"{ts} | {msg}"
    print(line, flush=True)
    try:
        with open(RUNNER_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ── Pure functions (testable) ─────────────────────────────────────────────────

def is_active_window(now=None):
    """Return True if current time is within the active trading window."""
    if now is None:
        now = datetime.now()
    weekday = now.weekday()  # 0=Mon … 6=Sun
    t = now.time()
    if weekday < 5:          # Mon–Fri
        return time(8, 0) <= t < time(22, 0)
    else:                    # Sat–Sun
        return time(10, 0) <= t < time(20, 0)


def bootstrap_cycle_type(now=None):
    """Determine which cycle_type to run on a fresh start."""
    if now is None:
        now = datetime.now()
    weekday = now.weekday()
    t = now.time()
    if weekday < 5:          # weekday: scanner_morning if before 10:00
        if t < time(10, 0):
            return "scanner_morning"
    else:                    # weekend: scanner_morning only 10:00–10:15
        if time(10, 0) <= t < time(10, 15):
            return "scanner_morning"
    return "analyst"


def parse_run_at(run_at_str):
    """
    Parse and validate a HH:MM time string.
    Returns datetime.time on success, None on any invalid input.
    """
    if not run_at_str:
        return None
    if not re.fullmatch(r'\d{2}:\d{2}', str(run_at_str)):
        return None
    hh, mm = int(run_at_str[:2]), int(run_at_str[3:])
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    return time(hh, mm)


# ── Scanner afternoon tracking ────────────────────────────────────────────────

def scanner_afternoon_ran_today():
    """Return True if scanner_afternoon has already run today."""
    if not SCANNER_AFTERNOON_RAN.exists():
        return False
    try:
        return SCANNER_AFTERNOON_RAN.read_text(encoding="utf-8").strip() == \
               date.today().isoformat()
    except Exception:
        return False


def mark_scanner_afternoon_ran():
    """Write today's date to scanner_afternoon_ran.txt."""
    SCANNER_AFTERNOON_RAN.write_text(date.today().isoformat(), encoding="utf-8")


# ── Claude executable discovery ───────────────────────────────────────────────

def find_claude():
    """
    Locate the claude CLI executable.
    Returns path string or raises RuntimeError.
    """
    candidates = [
        "claude",
        str(Path.home() / "AppData/Roaming/npm/claude.cmd"),
        str(Path.home() / "AppData/Local/Programs/claude/claude.exe"),
    ]
    for c in candidates:
        found = shutil.which(c)
        if found:
            return found
        if Path(c).exists():
            return c
    raise RuntimeError(
        "claude executable not found — is Claude Code installed and on PATH?"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    now = datetime.now()
    today = date.today().isoformat()

    # 1. Dead zone check
    if not is_active_window(now):
        return  # silent exit

    # 2. API key safety check — subscription billing requires NO API key
    if os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is set in environment.")
        print("This would bill via Anthropic API (per-token), NOT your Max subscription.")
        print("Unset ANTHROPIC_API_KEY from your environment before running this script.")
        sys.exit(1)

    # 3. Read and validate next_cycle.json
    cycle_type = None
    tier_hint = 3

    try:
        if not NEXT_CYCLE_FILE.exists():
            raise ValueError("missing file")

        data = json.loads(NEXT_CYCLE_FILE.read_text(encoding="utf-8"))

        if data.get("date") != today:
            raise ValueError(f"stale date: {data.get('date')}")

        run_at = parse_run_at(data.get("run_at", ""))
        if run_at is None:
            raise ValueError(f"malformed run_at: {data.get('run_at')!r}")

        ct = data.get("cycle_type", "")
        if ct not in VALID_CYCLE_TYPES:
            raise ValueError(f"unknown cycle_type: {ct!r}")

        if now.time() < run_at:
            return  # not time yet — silent exit

        cycle_type = ct
        raw_hint = data.get("tier_hint", 3)
        tier_hint = int(raw_hint) if int(raw_hint) in (1, 2, 3) else 3

    except (ValueError, KeyError, json.JSONDecodeError) as e:
        log(f"bootstrap ({e})")
        cycle_type = bootstrap_cycle_type(now)
        tier_hint = 3

    # 4. Scanner afternoon override (runner-level, authoritative)
    if now.weekday() < 5 and time(15, 20) <= now.time() <= time(15, 40):
        if not scanner_afternoon_ran_today():
            log("scanner_afternoon override — runner-level trigger 15:20–15:40")
            cycle_type = "scanner_afternoon"
            tier_hint = 3

    # 5. Select and verify prompt file
    prompt_file = PROMPT_MAP[cycle_type]
    if not prompt_file.exists():
        log(f"ERROR: prompt file not found: {prompt_file}")
        sys.exit(1)

    # 6. Select timeout based on tier_hint
    timeout = TIMEOUTS.get(tier_hint, DEFAULT_TIMEOUT)

    # 7. Build prompt
    rel_prompt = prompt_file.relative_to(BASE_DIR)
    prompt = (
        f"Εκτέλεσε cycle. Ώρα: {now.strftime('%H:%M')} EET.\n"
        f"Διάβασε: {rel_prompt} και εκτέλεσε ακριβώς.\n"
        f"Working dir: {BASE_DIR}"
    )

    # 8. Find Claude executable
    try:
        claude_cmd = find_claude()
    except RuntimeError as e:
        log(f"ERROR: {e}")
        sys.exit(1)

    # 9. Call Claude
    log(f"start | {cycle_type} tier{tier_hint} | timeout={timeout}s")
    t_start = datetime.now()

    try:
        result = subprocess.run(
            [claude_cmd, "-p", prompt, "--allowedTools", "Bash,Read,Write"],
            cwd=str(BASE_DIR),
            timeout=timeout,
        )
        duration = int((datetime.now() - t_start).total_seconds())
        status = "ok" if result.returncode == 0 else f"exit={result.returncode}"
        log(f"done | {cycle_type} tier{tier_hint} | {duration}s | {status}")

    except subprocess.TimeoutExpired:
        duration = int((datetime.now() - t_start).total_seconds())
        log(f"timeout | {cycle_type} tier{tier_hint} | {duration}s")

    # 10. Mark scanner_afternoon as done if applicable
    if cycle_type == "scanner_afternoon":
        mark_scanner_afternoon_ran()


if __name__ == "__main__":
    main()
