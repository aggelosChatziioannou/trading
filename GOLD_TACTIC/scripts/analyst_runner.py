#!/usr/bin/env python3
"""
GOLD TACTIC — Analyst Runner (Dual Runtime: Claude + Kimi)
Heartbeat: checks next_cycle.json and calls the preferred AI CLI when scheduled.
Called every 5 minutes by Windows Task Scheduler.

Usage:
  python analyst_runner.py              # Auto-detect available CLI
  python analyst_runner.py --cli claude # Force Claude Code
  python analyst_runner.py --cli kimi   # Force Kimi Code CLI
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
FAILURE_LOG = DATA_DIR / "runner_failures.json"

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


# ── CLI discovery ─────────────────────────────────────────────────────────────

def find_executable(name, candidates=None):
    """
    Locate a CLI executable by name and optional candidate paths.
    Returns path string or None.
    """
    if candidates is None:
        candidates = []
    for c in [name] + candidates:
        found = shutil.which(c)
        if found:
            return found
        if Path(c).exists():
            return c
    return None


def detect_cli(preferred=None):
    """
    Detect available AI CLI. Returns ('claude'| 'kimi', path) or (None, None).
    
    Priority:
      1. explicit preferred argument
      2. GOLD_TACTIC_CLI env variable
      3. First available: claude -> kimi
    """
    env_preference = os.environ.get("GOLD_TACTIC_CLI", "").lower().strip()
    choice = preferred or env_preference or None

    claude_candidates = [
        str(Path.home() / "AppData/Roaming/npm/claude.cmd"),
        str(Path.home() / "AppData/Local/Programs/claude/claude.exe"),
    ]
    kimi_candidates = [
        str(Path.home() / ".local/bin/kimi"),
        str(Path.home() / "AppData/Roaming/Python/Python311/Scripts/kimi.exe"),
        str(Path.home() / "AppData/Local/Programs/Python/Python311/Scripts/kimi.exe"),
    ]

    if choice == "claude" or choice is None:
        path = find_executable("claude", claude_candidates)
        if path:
            return "claude", path
    if choice == "kimi" or choice is None:
        path = find_executable("kimi", kimi_candidates)
        if path:
            return "kimi", path
    if choice == "claude":
        path = find_executable("kimi", kimi_candidates)
        if path:
            return "kimi", path
    return None, None


def build_invoke_args(cli_name, prompt_file, prompt_text):
    """Build subprocess arguments for the selected CLI."""
    rel_prompt = prompt_file.relative_to(BASE_DIR)
    if cli_name == "claude":
        return [
            "-p", prompt_text,
            "--allowedTools", "Bash,Read,Write",
        ]
    elif cli_name == "kimi":
        # Kimi CLI non-interactive mode
        # We use --print + -c with the prompt text
        # Kimi auto-discovers tools; we just need to ensure working dir is set
        return [
            "--print",
            "-c", prompt_text,
        ]
    else:
        raise ValueError(f"Unknown CLI: {cli_name}")


# ── Failure tracking ──────────────────────────────────────────────────────────

def load_failures():
    """Load failure count from runner_failures.json."""
    if FAILURE_LOG.exists():
        try:
            return json.loads(FAILURE_LOG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"count": 0, "last_error": ""}


def save_failures(data):
    """Write failure count to runner_failures.json."""
    FAILURE_LOG.write_text(json.dumps(data, indent=2), encoding="utf-8")


def send_alert(msg):
    """Send Telegram alert via telegram_sender.py."""
    try:
        tg_script = Path(__file__).parent / "telegram_sender.py"
        if tg_script.exists():
            subprocess.run(
                [sys.executable, str(tg_script), "message", msg],
                cwd=str(BASE_DIR),
                timeout=30,
                capture_output=True,
            )
    except Exception:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    now = datetime.now()
    today = date.today().isoformat()

    # Parse optional --cli argument
    preferred_cli = None
    if "--cli" in sys.argv:
        idx = sys.argv.index("--cli")
        if idx + 1 < len(sys.argv):
            preferred_cli = sys.argv[idx + 1].lower().strip()

    # 1. Dead zone check
    if not is_active_window(now):
        return  # silent exit

    # 2. API key safety check — subscription billing requires NO API key for Claude
    cli_name, cli_path = detect_cli(preferred_cli)
    if cli_name == "claude" and os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is set in environment.")
        print("This would bill via Anthropic API (per-token), NOT your Max subscription.")
        print("Unset ANTHROPIC_API_KEY from your environment before running this script.")
        sys.exit(1)

    if cli_name == "kimi" and not os.environ.get("KIMI_API_KEY"):
        print("ERROR: KIMI_API_KEY is not set in environment.")
        print("Kimi Code CLI requires an API key. Add it to your .env file.")
        sys.exit(1)

    if cli_name is None:
        print("ERROR: No AI CLI found (tried claude, kimi).")
        print("Please install Claude Code or Kimi Code CLI and ensure it's on PATH.")
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
    prompt_text = (
        f"Εκτέλεσε cycle. Ώρα: {now.strftime('%H:%M')} EET.\n"
        f"Διάβασε: {rel_prompt} και εκτέλεσε ακριβώς.\n"
        f"Working dir: {BASE_DIR}"
    )

    # 8. Build CLI-specific invoke args
    try:
        invoke_args = build_invoke_args(cli_name, prompt_file, prompt_text)
    except ValueError as e:
        log(f"ERROR: {e}")
        sys.exit(1)

    # 9. Call AI CLI
    log(f"start | {cli_name} | {cycle_type} tier{tier_hint} | timeout={timeout}s")
    t_start = datetime.now()
    failures = load_failures()

    try:
        result = subprocess.run(
            [cli_path] + invoke_args,
            cwd=str(BASE_DIR),
            timeout=timeout,
        )
        duration = int((datetime.now() - t_start).total_seconds())

        if result.returncode == 0:
            if failures["count"] > 0:
                failures = {"count": 0, "last_error": ""}
                save_failures(failures)
            status = "ok"
        else:
            failures["count"] += 1
            failures["last_error"] = f"exit={result.returncode}"
            save_failures(failures)
            status = f"exit={result.returncode}"
            if failures["count"] >= 2:
                send_alert(
                    f"🚨 GOLD TACTIC Alert: {failures['count']} consecutive cycle failures. "
                    f"Last: {failures['last_error']} | {cycle_type} tier{tier_hint}"
                )
        log(f"done | {cli_name} | {cycle_type} tier{tier_hint} | {duration}s | {status}")

    except subprocess.TimeoutExpired:
        duration = int((datetime.now() - t_start).total_seconds())
        failures["count"] += 1
        failures["last_error"] = "timeout"
        save_failures(failures)
        log(f"timeout | {cli_name} | {cycle_type} tier{tier_hint} | {duration}s")
        if failures["count"] >= 2:
            send_alert(
                f"🚨 GOLD TACTIC Alert: {failures['count']} consecutive cycle failures. "
                f"Last: timeout | {cycle_type} tier{tier_hint}"
            )

    # 10. Mark scanner_afternoon as done if applicable
    if cycle_type == "scanner_afternoon":
        mark_scanner_afternoon_ran()


if __name__ == "__main__":
    main()
