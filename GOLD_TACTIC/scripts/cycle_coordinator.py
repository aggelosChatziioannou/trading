#!/usr/bin/env python3
"""
GOLD TACTIC — Schedule Cycle Coordinator (G1-G7 fixes)

Centralized coordination between the 8 Claude app schedules:
  - 4 Asset Selector runs (AM/PM/EVE/WE)
  - 4 Market Monitor runs (Peak/OffPeak/Night/WE)

Provides:
  - Lock-file mechanism (G2/G6) — prevents race when Selector overruns into Monitor cycle
  - Done-signal (G7) — Selector writes selector_done.json with run summary
  - Per-cycle audit log (G3) — both schedules append to data/cycle_log.jsonl
  - Cycle counter (G4) — persistent across restarts, derived from log
  - Seed entry post-rotation (G5) — fresh briefing_log gets context header
  - Selector reference renderer (G1) — "Watched by AM @08:00 (4h12' ago)" line

CLI:
  cycle_coordinator.py selector-start <run_name>    # Write lock at run start
  cycle_coordinator.py selector-done <run_name> <selected_count> <duration_s>
  cycle_coordinator.py monitor-start                # Returns 0 if safe to proceed,
                                                     2 if Selector is locked (>2min hold)
  cycle_coordinator.py monitor-done <level> <duration_s> [--trades-opened N --trades-closed N]
  cycle_coordinator.py current-cycle               # Returns next cycle number for today
  cycle_coordinator.py selector-ref-line           # Renders "🎯 Watched by AM Selector @08:00 (4h12' ago)" line
  cycle_coordinator.py status                      # Human-readable status of all coordination files
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

DATA_DIR = Path(__file__).parent.parent / "data"
LOCK_FILE = DATA_DIR / "selector.lock"
DONE_FILE = DATA_DIR / "selector_done.json"
CYCLE_LOG = DATA_DIR / "cycle_log.jsonl"
SELECTED_FILE = DATA_DIR / "selected_assets.json"
BRIEFING_LOG = DATA_DIR / "briefing_log.md"

EET = timezone(timedelta(hours=3))

# Lock is "stale" after 5 minutes (Selector should never legitimately take >5min)
LOCK_STALE_AFTER_SEC = 300

# Pretty names for selector_run codes
SELECTOR_RUN_LABELS = {
    "morning": "AM",
    "afternoon": "PM",
    "evening": "EVE",
    "weekend": "WE",
}


def _now():
    return datetime.now(EET)


def _iso(dt):
    return dt.isoformat(timespec='seconds')


def _atomic_write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, path)


def _append_jsonl(path: Path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _parse_iso(s):
    if not s:
        return None
    try:
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        return datetime.fromisoformat(s)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Selector — start (G2/G6: write lock)
# ═══════════════════════════════════════════════════════════════════════════
def selector_start(run_name: str):
    now = _now()
    lock_data = {
        "schedule": f"GT_Selector_{SELECTOR_RUN_LABELS.get(run_name, run_name).upper()}",
        "run_name": run_name,
        "pid": os.getpid(),
        "started_at": _iso(now),
        "expected_max_duration_s": 90,
    }
    _atomic_write_json(LOCK_FILE, lock_data)
    print(f"[selector-start] Lock written: {run_name} @ {_iso(now)}")
    return lock_data


# ═══════════════════════════════════════════════════════════════════════════
# Selector — done (G7: write done signal + clear lock + log cycle)
# ═══════════════════════════════════════════════════════════════════════════
def selector_done(run_name: str, selected_count: int, duration_s: float, sources_ok: int = 0, sources_fail: int = 0):
    now = _now()
    label = SELECTOR_RUN_LABELS.get(run_name, run_name).upper()

    # Read selected_assets.json to capture symbols
    selected_symbols = []
    if SELECTED_FILE.exists():
        try:
            data = json.loads(SELECTED_FILE.read_text(encoding='utf-8'))
            selected_symbols = [s.get("symbol") for s in data.get("selected", [])]
        except Exception:
            pass

    done_data = {
        "schedule": f"GT_Selector_{label}",
        "run_name": run_name,
        "completed_at": _iso(now),
        "duration_s": round(duration_s, 1),
        "selected_count": selected_count,
        "selected_symbols": selected_symbols,
        "sources_ok": sources_ok,
        "sources_fail": sources_fail,
    }
    _atomic_write_json(DONE_FILE, done_data)

    # Audit log entry
    _append_jsonl(CYCLE_LOG, {
        "ts": _iso(now),
        "schedule": done_data["schedule"],
        "type": "selector",
        "status": "ok",
        "duration_s": done_data["duration_s"],
        "selected": selected_symbols,
        "sources_ok": sources_ok,
        "sources_fail": sources_fail,
    })

    # Clear the lock
    if LOCK_FILE.exists():
        try:
            LOCK_FILE.unlink()
        except Exception:
            pass

    print(f"[selector-done] {label} OK · {selected_count} selected · {duration_s:.1f}s · sources {sources_ok}/{sources_ok+sources_fail}")
    return done_data


# ═══════════════════════════════════════════════════════════════════════════
# Monitor — start (G2/G6: check Selector lock)
# ═══════════════════════════════════════════════════════════════════════════
def monitor_start():
    """Returns (proceed: bool, reason: str). Proceed=False if Selector lock active and fresh."""
    if not LOCK_FILE.exists():
        return True, "no lock"

    try:
        lock_data = json.loads(LOCK_FILE.read_text(encoding='utf-8'))
        started = _parse_iso(lock_data.get("started_at"))
        if started is None:
            # Malformed lock — clean it up
            LOCK_FILE.unlink()
            return True, "malformed lock cleared"

        age_sec = (_now() - started).total_seconds()
        if age_sec > LOCK_STALE_AFTER_SEC:
            # Stale lock — Selector probably crashed. Clear and proceed.
            print(f"[monitor-start] Stale lock ({age_sec:.0f}s > {LOCK_STALE_AFTER_SEC}s) — clearing and proceeding")
            LOCK_FILE.unlink()
            return True, f"stale lock ({age_sec:.0f}s) cleared"

        # Active lock — wait
        return False, f"Selector {lock_data.get('run_name','?')} running ({age_sec:.0f}s elapsed). Defer."
    except Exception as e:
        # Can't read lock — best effort, proceed
        return True, f"unreadable lock: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# Weekly Audit — start/done (Self-Improvement Layer 3)
# ═══════════════════════════════════════════════════════════════════════════
def weekly_audit_start():
    """Called at start of weekly_audit run. Yields to selector if conflicting lock."""
    if LOCK_FILE.exists():
        try:
            lock_data = json.loads(LOCK_FILE.read_text(encoding='utf-8'))
            started = _parse_iso(lock_data.get("started_at"))
            if started and (_now() - started).total_seconds() < LOCK_STALE_AFTER_SEC:
                return False, f"Selector {lock_data.get('run_name','?')} active — defer audit"
        except Exception:
            pass
    print(f"[weekly-audit-start] Beginning audit @ {_iso(_now())}")
    return True, "ok"


def weekly_audit_done(week_id: str, trades_count: int, proposals_count: int, duration_s: float):
    now = _now()
    record = {
        "ts": _iso(now),
        "schedule": "GT_Weekly_Audit",
        "type": "weekly_audit",
        "status": "ok",
        "week_id": week_id,
        "trades_in_week": trades_count,
        "proposals_generated": proposals_count,
        "duration_s": round(duration_s, 1),
    }
    _append_jsonl(CYCLE_LOG, record)
    print(f"[weekly-audit-done] {week_id} · {trades_count} trades · {proposals_count} proposals · {duration_s:.1f}s")
    return record


# ═══════════════════════════════════════════════════════════════════════════
# Monitor — done (G3: log cycle to audit trail)
# ═══════════════════════════════════════════════════════════════════════════
def monitor_done(level: str, duration_s: float, trades_opened: int = 0, trades_closed: int = 0,
                 schedule_label: str = "GT_Monitor"):
    now = _now()
    record = {
        "ts": _iso(now),
        "schedule": schedule_label,
        "type": "monitor",
        "status": "ok",
        "level": level,
        "duration_s": round(duration_s, 1),
        "trades_opened": trades_opened,
        "trades_closed": trades_closed,
    }
    _append_jsonl(CYCLE_LOG, record)
    print(f"[monitor-done] {level} · {duration_s:.1f}s · opened={trades_opened} closed={trades_closed}")
    return record


# ═══════════════════════════════════════════════════════════════════════════
# G4 — Persistent cycle counter
# ═══════════════════════════════════════════════════════════════════════════
def current_cycle_number():
    """Count Monitor entries in cycle_log.jsonl for today's date. Return next cycle # (1-based)."""
    if not CYCLE_LOG.exists():
        return 1
    today = _now().date()
    count = 0
    with CYCLE_LOG.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("type") != "monitor":
                    continue
                ts = _parse_iso(rec.get("ts"))
                if ts and ts.date() == today:
                    count += 1
            except Exception:
                pass
    return count + 1


# ═══════════════════════════════════════════════════════════════════════════
# G1 — Selector reference renderer (USER'S MAIN ASK)
# ═══════════════════════════════════════════════════════════════════════════
def selector_ref_line():
    """Render '🎯 Watched: AM Selector @08:00 (4h12' ago) — XAU·EUR·BTC·NAS' line for Monitor messages."""
    if not SELECTED_FILE.exists():
        return "⚠️ <i>Watched: κανένας Selector δεν έτρεξε ακόμα — αναμονή</i>"

    try:
        data = json.loads(SELECTED_FILE.read_text(encoding='utf-8'))
    except Exception:
        return "⚠️ <i>Watched: selected_assets.json δεν διαβάζεται</i>"

    ts = _parse_iso(data.get("timestamp"))
    run = data.get("selector_run", "?")
    label = SELECTOR_RUN_LABELS.get(run, run.upper())
    selected = data.get("selected", [])
    symbols = [s.get("symbol", "?") for s in selected[:4]]
    symbols_compact = "·".join(_short(s) for s in symbols)

    if ts is None:
        return f"🎯 <i>Watched: {label} Selector — {symbols_compact}</i>"

    age_sec = (_now() - ts).total_seconds()
    age_str = _format_age(age_sec)
    time_str = ts.strftime('%H:%M')

    # Fresh selector (<9h) = green, older = yellow, very old (>12h) = red
    if age_sec < 9 * 3600:
        icon = "🎯"
    elif age_sec < 12 * 3600:
        icon = "🟡"
    else:
        icon = "🔴"

    return f"{icon} <i>Watched: <b>{label} Selector</b> @{time_str} ({age_str} ago) — {symbols_compact}</i>"


def _short(symbol):
    """XAUUSD → XAU, EURUSD → EUR, BTC → BTC, NAS100 → NAS."""
    s = (symbol or "?").upper()
    if s.endswith("USD") and len(s) > 3:
        return s[:-3]
    if s.endswith("100") or s.endswith("500"):
        return s[:-3]
    return s


def _format_age(sec):
    """45min ago, 4h12' ago, 1d 3h ago."""
    if sec < 3600:
        return f"{int(sec/60)}'"
    if sec < 86400:
        h = int(sec / 3600)
        m = int((sec % 3600) / 60)
        return f"{h}h{m:02d}'"
    d = int(sec / 86400)
    h = int((sec % 86400) / 3600)
    return f"{d}d {h}h"


# ═══════════════════════════════════════════════════════════════════════════
# G5 — Seed entry after briefing_log rotation
# ═══════════════════════════════════════════════════════════════════════════
def seed_briefing_log(date_str: str = None, last_4_assets=None):
    """Called by Selector EVE after briefing_log rotation. Writes a context-seed entry
    so Monitor's next-cycle 'last 30 lines' read isn't empty."""
    if date_str is None:
        date_str = _now().strftime('%Y-%m-%d')
    if last_4_assets is None and SELECTED_FILE.exists():
        try:
            data = json.loads(SELECTED_FILE.read_text(encoding='utf-8'))
            last_4_assets = [
                f"{s.get('symbol')} ({s.get('direction_bias')}) — {s.get('reason','')[:60]}"
                for s in data.get("selected", [])
            ]
        except Exception:
            last_4_assets = []

    seed = [
        f"# Briefing Log — Daily Telegram History",
        f"",
        f"> Auto-generated by Market Monitor. Rotated nightly at 21:00 by Asset Selector EVE.",
        f"> Each entry = one Telegram message sent. Used for coherence (no repetition).",
        f"",
        f"---",
        f"## {date_str} 21:00 EET | EVE Rotation Seed",
        f"Καθαρό briefing log για την επόμενη ημέρα.",
        f"Προηγούμενη μέρα archived. Watched assets για overnight crypto:",
    ]
    if last_4_assets:
        for a in last_4_assets:
            seed.append(f"- {a}")
    seed.extend(["---", ""])

    BRIEFING_LOG.write_text("\n".join(seed), encoding='utf-8')
    print(f"[seed-briefing-log] Wrote seed entry to {BRIEFING_LOG}")
    return BRIEFING_LOG


# ═══════════════════════════════════════════════════════════════════════════
# Status (human-readable summary of coordination state)
# ═══════════════════════════════════════════════════════════════════════════
def status():
    print("=== Schedule Coordination Status ===\n")

    # Lock state
    if LOCK_FILE.exists():
        try:
            lock = json.loads(LOCK_FILE.read_text(encoding='utf-8'))
            started = _parse_iso(lock.get("started_at"))
            age = (_now() - started).total_seconds() if started else 0
            stale_str = " (STALE)" if age > LOCK_STALE_AFTER_SEC else ""
            print(f"🔒 Lock: ACTIVE{stale_str} — {lock.get('run_name')} for {age:.0f}s")
        except Exception:
            print(f"🔒 Lock: present but unreadable")
    else:
        print(f"🔓 Lock: clear (no Selector running)")

    # Done state
    if DONE_FILE.exists():
        try:
            done = json.loads(DONE_FILE.read_text(encoding='utf-8'))
            ts = _parse_iso(done.get("completed_at"))
            age = (_now() - ts).total_seconds() if ts else 0
            print(f"✅ Last Selector: {done.get('run_name')} @ {ts.strftime('%H:%M') if ts else '?'} ({_format_age(age)} ago)")
            print(f"   Selected: {', '.join(done.get('selected_symbols', []))}")
            print(f"   Duration: {done.get('duration_s')}s · Sources: {done.get('sources_ok')}/{done.get('sources_ok',0)+done.get('sources_fail',0)}")
        except Exception:
            print(f"⚠️  Done file unreadable")
    else:
        print(f"⚠️  Done file: missing (no Selector ever completed)")

    # Selector ref line preview
    print(f"\n{selector_ref_line()}")

    # Cycle counter
    print(f"\nNext Monitor cycle # for today: {current_cycle_number()}")

    # Recent cycle log entries
    if CYCLE_LOG.exists():
        with CYCLE_LOG.open(encoding='utf-8') as f:
            lines = f.readlines()
        print(f"\nLast 5 cycle_log entries:")
        for line in lines[-5:]:
            try:
                rec = json.loads(line)
                ts = _parse_iso(rec.get("ts"))
                ts_str = ts.strftime('%H:%M:%S') if ts else '?'
                if rec.get("type") == "selector":
                    print(f"  [{ts_str}] {rec.get('schedule')} → {rec.get('selected')} ({rec.get('duration_s')}s)")
                else:
                    print(f"  [{ts_str}] {rec.get('schedule')} L={rec.get('level')} ({rec.get('duration_s')}s) opened={rec.get('trades_opened')} closed={rec.get('trades_closed')}")
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0]

    if cmd == "selector-start":
        run = args[1] if len(args) > 1 else "morning"
        selector_start(run)

    elif cmd == "selector-done":
        run = args[1]
        selected_count = int(args[2])
        duration = float(args[3])
        sources_ok = int(args[4]) if len(args) > 4 else 0
        sources_fail = int(args[5]) if len(args) > 5 else 0
        selector_done(run, selected_count, duration, sources_ok, sources_fail)

    elif cmd == "monitor-start":
        proceed, reason = monitor_start()
        print(reason)
        sys.exit(0 if proceed else 2)

    elif cmd == "monitor-done":
        level = args[1]
        duration = float(args[2])
        opened = 0
        closed = 0
        for a in args[3:]:
            if a.startswith("--trades-opened="):
                opened = int(a.split("=",1)[1])
            elif a.startswith("--trades-closed="):
                closed = int(a.split("=",1)[1])
        monitor_done(level, duration, opened, closed)

    elif cmd == "weekly-audit-start":
        proceed, reason = weekly_audit_start()
        print(reason)
        sys.exit(0 if proceed else 2)

    elif cmd == "weekly-audit-done":
        week_id = args[1]
        trades = int(args[2])
        proposals = int(args[3])
        duration = float(args[4])
        weekly_audit_done(week_id, trades, proposals, duration)

    elif cmd == "current-cycle":
        print(current_cycle_number())

    elif cmd == "selector-ref-line":
        print(selector_ref_line())

    elif cmd == "seed-briefing-log":
        seed_briefing_log()

    elif cmd == "status":
        status()

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
