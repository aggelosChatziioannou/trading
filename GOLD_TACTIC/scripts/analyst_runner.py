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
import urllib.request
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
    """Return True if current time is within the active trading window.
    LEGACY — kept for backward compatibility. Always returns True in 24/7 mode.
    Use get_zone() for zone-specific logic instead."""
    return True  # 24/7 mode — system never fully stops


# ── 5-Zone System (24/7 Adaptive Schedule) ───────────────────────────────────

# Zone definitions: (name, interval_minutes, max_tier, can_open_new_trades)
ZONES = {
    "NIGHT":   {"interval": 60, "max_tier": 1, "can_trade": False, "assets": ["BTC", "SOL"]},
    "ASIA":    {"interval": 30, "max_tier": 2, "can_trade": False, "assets": ["BTC", "SOL", "EURUSD", "GBPUSD"]},
    "LONDON":  {"interval": 10, "max_tier": 3, "can_trade": True,  "assets": "ALL"},
    "NY":      {"interval": 10, "max_tier": 3, "can_trade": True,  "assets": "ALL"},
    "EVENING": {"interval": 20, "max_tier": 2, "can_trade": False, "assets": ["BTC", "SOL"]},
}


def get_zone(now=None):
    """
    Determine current trading zone based on time.

    Returns: dict {name, interval, max_tier, can_trade, assets}

    Zones (EET, all days):
      NIGHT:   22:00 - 04:00  (crypto only, 60min, watchdog)
      ASIA:    04:00 - 08:00  (crypto+forex watch, 30min)
      LONDON:  08:00 - 15:30  (all, 10min, full trading)
      NY:      15:30 - 20:00  (all, 10min, full trading)
      EVENING: 20:00 - 22:00  (crypto+close only, 20min)
    """
    if now is None:
        now = datetime.now()
    t = now.time()

    if time(22, 0) <= t or t < time(4, 0):
        zone_name = "NIGHT"
    elif time(4, 0) <= t < time(8, 0):
        zone_name = "ASIA"
    elif time(8, 0) <= t < time(15, 30):
        zone_name = "LONDON"
    elif time(15, 30) <= t < time(20, 0):
        zone_name = "NY"
    else:  # 20:00 - 22:00
        zone_name = "EVENING"

    zone = ZONES[zone_name].copy()
    zone["name"] = zone_name

    # Weekend: crypto-only regardless of zone (forex markets closed)
    if now.weekday() >= 5:  # Sat, Sun
        zone["assets"] = ["BTC", "SOL", "ETH"]
        if zone_name in ("LONDON", "NY"):
            zone["can_trade"] = True   # Crypto can trade on weekends
            zone["max_tier"] = 3
        else:
            zone["can_trade"] = False

    return zone


def cold_start_check(now=None):
    """
    Detect if system was offline and decide bootstrap action.

    Returns: dict {gap_hours, action, reason, has_orphaned_trades}

    Actions:
      "resume"      — gap < 2h, continue normally
      "catch_up"    — gap 2-8h, quick scan + current zone
      "full_scan"   — gap 8-24h, full scanner immediately
      "full_reset"  — gap > 24h, complete reset
      "fresh_start" — gap > 7 days, brand new
    """
    if now is None:
        now = datetime.now()

    # Find last cycle time from session_log.jsonl
    session_log = DATA_DIR / "session_log.jsonl"
    last_cycle_time = None

    if session_log.exists():
        try:
            lines = session_log.read_text(encoding="utf-8").strip().split("\n")
            for line in reversed(lines):
                if line.strip():
                    entry = json.loads(line.strip())
                    time_str = entry.get("time", "")
                    # Parse "2026-04-04 14:30 EET" format
                    dt_str = time_str.replace(" EET", "").strip()
                    if dt_str:
                        last_cycle_time = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                        break
        except Exception:
            pass

    # Check for orphaned trades
    portfolio_file = DATA_DIR / "portfolio.json"
    has_orphaned = False
    if portfolio_file.exists():
        try:
            portfolio = json.loads(portfolio_file.read_text(encoding="utf-8"))
            has_orphaned = len(portfolio.get("open_trades", [])) > 0
        except Exception:
            pass

    # Determine gap
    if last_cycle_time is None:
        gap_hours = 999
    else:
        gap = now - last_cycle_time
        gap_hours = gap.total_seconds() / 3600

    # Decide action
    if gap_hours < 2:
        action = "resume"
        reason = f"Gap {gap_hours:.1f}h — resuming normally"
    elif gap_hours < 8:
        action = "catch_up"
        reason = f"Gap {gap_hours:.1f}h — quick catch-up scan"
    elif gap_hours < 24:
        action = "full_scan"
        reason = f"Gap {gap_hours:.1f}h — full scanner needed"
    elif gap_hours < 168:  # 7 days
        action = "full_reset"
        reason = f"Gap {gap_hours:.0f}h ({gap_hours/24:.0f} days) — full reset"
    else:
        action = "fresh_start"
        reason = f"Gap {gap_hours:.0f}h ({gap_hours/24:.0f} days) — fresh start"

    return {
        "gap_hours": round(gap_hours, 1),
        "action": action,
        "reason": reason,
        "has_orphaned_trades": has_orphaned,
        "last_cycle": last_cycle_time.strftime("%Y-%m-%d %H:%M") if last_cycle_time else None,
    }


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


# ── Health check (FIX #3) ────────────────────────────────────────────────────

def health_check():
    """
    Ελέγχει βασικές υπηρεσίες πριν τρέξει κύκλος.
    Returns: (ok: bool, errors: list[str])

    Checks:
      1. Data directory exists (BLOCKING)
      2. Python imports (yfinance, pandas, numpy)
      3. Telegram bot connectivity
      4. Portfolio file exists (warning)
    """
    errors = []

    # Check 1: Data directory (BLOCKING — χωρίς αυτό δεν τρέχει τίποτα)
    if not DATA_DIR.exists() or not DATA_DIR.is_dir():
        errors.append(f"CRITICAL: Data directory missing: {DATA_DIR}")
        return False, errors

    # Check 2: Python imports
    for module_name in ("yfinance", "pandas", "numpy"):
        try:
            __import__(module_name)
        except ImportError:
            errors.append(f"Missing Python module: {module_name}")

    # Check 3: Telegram bot
    try:
        # Φόρτωσε token από .env αν υπάρχει
        env_file = BASE_DIR / ".env"
        tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not tg_token and env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    tg_token = line.split("=", 1)[1].strip().strip("'\"")
                    break
        if tg_token:
            url = f"https://api.telegram.org/bot{tg_token}/getMe"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                if not data.get("ok"):
                    errors.append("Telegram bot: API returned ok=false")
        else:
            errors.append("Telegram bot: token not found in .env or environment")
    except Exception as e:
        errors.append(f"Telegram bot unreachable: {type(e).__name__}: {e}")

    # Check 4: Portfolio file (warning only)
    portfolio_file = DATA_DIR / "portfolio.json"
    if not portfolio_file.exists():
        errors.append("Warning: portfolio.json not found (will use defaults)")

    ok = not any("CRITICAL" in e for e in errors)
    return ok, errors


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

    # 1. Zone detection (24/7 — no dead zone, just different intensity)
    zone = get_zone(now)
    log(f"zone: {zone['name']} | interval: {zone['interval']}min | trade: {zone['can_trade']}")

    # 1b. Cold start check
    cold_start = cold_start_check(now)
    if cold_start["action"] != "resume":
        log(f"COLD START: {cold_start['reason']}")
        if cold_start["has_orphaned_trades"]:
            log("ORPHANED TRADES detected — forcing TIER 3")

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

    # 2b. Health check (FIX #3)
    ok, health_errors = health_check()
    if health_errors:
        for err in health_errors:
            log(f"HEALTH: {err}")
    if not ok:
        log(f"HEALTH CHECK FAILED — aborting cycle")
        send_alert(f"🏥 GOLD TACTIC Health: {'; '.join(health_errors)}")
        sys.exit(1)

    # 3. Read and validate next_cycle.json
    cycle_type = None
    tier_hint = 3

    try:
        if not NEXT_CYCLE_FILE.exists():
            raise ValueError("missing file")

        # FIX #4: Backup πριν το parsing
        try:
            shutil.copy2(NEXT_CYCLE_FILE, str(NEXT_CYCLE_FILE) + ".bak")
        except Exception:
            pass

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
        # FIX #4: TIER 2 κατά το bootstrap (εξοικονόμηση tokens)
        # TIER 3 μόνο για scanner_morning ή αν δεν είμαστε σε active window
        tier_hint = 3 if cycle_type == "scanner_morning" else 2

        # Track bootstrap metadata
        failures = load_failures()
        failures["last_bootstrap_reason"] = str(e)
        failures["last_bootstrap_time"] = now.strftime("%Y-%m-%d %H:%M")
        save_failures(failures)

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

    # 7. Build prompt (includes zone + cold start info)
    rel_prompt = prompt_file.relative_to(BASE_DIR)
    zone_info = f"Zone: {zone['name']} | Interval: {zone['interval']}min | Can trade: {zone['can_trade']}"
    cold_info = ""
    if cold_start["action"] != "resume":
        cold_info = f"\nCOLD START: {cold_start['reason']}. Action: {cold_start['action']}."
        if cold_start["has_orphaned_trades"]:
            cold_info += " ORPHANED TRADES found — check portfolio immediately."

    prompt_text = (
        f"Εκτέλεσε cycle. Ώρα: {now.strftime('%H:%M')} EET.\n"
        f"{zone_info}\n"
        f"Διάβασε: {rel_prompt} και εκτέλεσε ακριβώς.\n"
        f"Working dir: {BASE_DIR}"
        f"{cold_info}"
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
            failures = {
                "count": 0,
                "last_error": "",
                "last_successful_cycle": f"{cycle_type} tier{tier_hint} @ {now.strftime('%H:%M')}",
            }
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
