#!/usr/bin/env python3
"""
GOLD TACTIC — Data Health Check (T1.1 stale detection)

Checks freshness of critical runtime data files. Used by Market Monitor
to display a ⚠️ stale-data banner when fetches fail silently.

Critical files + expected max age (minutes):
  - quick_scan.json     30   (Monitor cycle every 20-40min)
  - live_prices.json    25
  - news_feed.json      30
  - economic_calendar   180  (Selector 4×/day, max 9h gap, allow 3h slack)
  - session_now.json    25
  - selected_assets     540  (Selector max 9h between EVE→AM)

Usage:
  python data_health.py                    # Human-readable
  python data_health.py --json             # Machine-readable JSON
  python data_health.py --line             # 1-liner for Telegram
  python data_health.py --banner           # HTML banner if any stale (else empty)
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

DATA_DIR = Path(__file__).parent.parent / "data"
EET = timezone(timedelta(hours=3))

# (filename, max_age_minutes, criticality, source_script)
WATCHED_FILES = [
    ("live_prices.json",       25,   "critical", "price_checker.py"),
    ("quick_scan.json",        30,   "critical", "quick_scan.py"),
    ("news_feed.json",         30,   "critical", "news_scout_v2.py --light"),
    ("session_now.json",       25,   "critical", "session_check.py"),
    ("selected_assets.json",   540,  "critical", "Asset Selector schedule"),
    ("economic_calendar.json", 180,  "warn",     "economic_calendar.py"),
    ("trs_current.json",       30,   "warn",     "Monitor cycle"),
    ("trade_state.json",       1440, "info",     "trade_manager.py tick"),
]


def _parse_timestamp(value, file_path):
    """Best-effort parse a timestamp. Returns datetime or None."""
    if not value or value == "?":
        return None
    if isinstance(value, str):
        # Try ISO format first
        try:
            # Handle "2026-04-17T11:05:00+03:00"
            if 'T' in value and ('+' in value or value.endswith('Z')):
                if value.endswith('Z'):
                    value = value[:-1] + '+00:00'
                return datetime.fromisoformat(value)
            # Handle "2026-04-17 15:40:30" (assume EET)
            if ' ' in value and len(value) >= 16:
                dt = datetime.strptime(value[:19], '%Y-%m-%d %H:%M:%S')
                return dt.replace(tzinfo=EET)
            if ' ' in value and len(value) >= 13:
                dt = datetime.strptime(value[:16], '%Y-%m-%d %H:%M')
                return dt.replace(tzinfo=EET)
        except (ValueError, TypeError):
            pass
    return None


def _file_timestamp(path: Path):
    """Get timestamp from file: try JSON internal field first, fall back to mtime."""
    if not path.exists():
        return None, "missing"

    # Try internal timestamp field
    try:
        if path.suffix == '.json':
            data = json.loads(path.read_text(encoding='utf-8'))
            for key in ('timestamp', 'updated', 'generated_at', 'last_tick'):
                if key in data:
                    parsed = _parse_timestamp(data[key], path)
                    if parsed:
                        return parsed, f"json:{key}"
    except Exception:
        pass

    # Fall back to mtime
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=EET)
        return mtime, "mtime"
    except Exception:
        return None, "error"


def check_freshness():
    """Return list of file health records."""
    now = datetime.now(EET)
    records = []
    for filename, max_age_min, criticality, source in WATCHED_FILES:
        path = DATA_DIR / filename
        ts, ts_source = _file_timestamp(path)
        if ts is None:
            records.append({
                "file": filename,
                "exists": path.exists(),
                "age_minutes": None,
                "max_age_minutes": max_age_min,
                "stale": True,
                "criticality": criticality,
                "source_script": source,
                "ts_source": ts_source,
                "status": "MISSING" if not path.exists() else "UNREADABLE",
            })
            continue
        age_seconds = (now - ts).total_seconds()
        age_minutes = round(age_seconds / 60, 1)
        is_stale = age_minutes > max_age_min
        records.append({
            "file": filename,
            "exists": True,
            "age_minutes": age_minutes,
            "max_age_minutes": max_age_min,
            "stale": is_stale,
            "criticality": criticality,
            "source_script": source,
            "ts_source": ts_source,
            "status": "STALE" if is_stale else "OK",
        })
    return records


def overall_status(records):
    """Aggregate status: HEALTHY / DEGRADED / CRITICAL."""
    critical_stale = [r for r in records if r["stale"] and r["criticality"] == "critical"]
    warn_stale = [r for r in records if r["stale"] and r["criticality"] == "warn"]

    if critical_stale:
        return "CRITICAL", critical_stale, warn_stale
    if warn_stale:
        return "DEGRADED", critical_stale, warn_stale
    return "HEALTHY", critical_stale, warn_stale


def render_banner(records):
    """HTML banner for Telegram if any stale. Empty string if healthy."""
    status, critical_stale, warn_stale = overall_status(records)
    if status == "HEALTHY":
        return ""

    lines = []
    if status == "CRITICAL":
        lines.append("⚠️ <b>STALE DATA</b> — οι παρακάτω πηγές απέτυχαν να ενημερωθούν:")
        for r in critical_stale:
            age = f"{r['age_minutes']:.0f}'" if r['age_minutes'] is not None else "missing"
            lines.append(f"• <code>{r['file']}</code> — {age} (limit {r['max_age_minutes']}') · τρέξε <code>{r['source_script']}</code>")

    if warn_stale:
        if not lines:
            lines.append("⚠️ Παλαιά δεδομένα (warn):")
        for r in warn_stale:
            age = f"{r['age_minutes']:.0f}'" if r['age_minutes'] is not None else "missing"
            lines.append(f"• {r['file']} — {age} (limit {r['max_age_minutes']}')")

    return "\n".join(lines)


def render_line(records):
    """1-liner for Telegram footer (Tier A)."""
    status, critical_stale, warn_stale = overall_status(records)
    total = len(records)
    fresh = sum(1 for r in records if not r["stale"])
    if status == "HEALTHY":
        return f"💚 Data: {fresh}/{total} fresh"
    if status == "DEGRADED":
        return f"🟡 Data: {fresh}/{total} fresh ({len(warn_stale)} warn)"
    return f"🔴 Data: {fresh}/{total} fresh — {len(critical_stale)} critical stale"


def render_human(records):
    """Human-readable terminal output."""
    status, critical_stale, warn_stale = overall_status(records)
    print(f"=== Data Health: {status} ===")
    for r in records:
        icon = "✅" if not r["stale"] else ("🔴" if r["criticality"] == "critical" else "🟡")
        age_str = f"{r['age_minutes']:.1f}min" if r['age_minutes'] is not None else "MISSING"
        print(f"  {icon} {r['file']:30s} age={age_str:>12s} max={r['max_age_minutes']}min [{r['criticality']}] via {r['ts_source']}")
    print()
    print(f"Critical stale: {len(critical_stale)} · Warn stale: {len(warn_stale)}")
    if status != "HEALTHY":
        print("\nRemediation:")
        for r in critical_stale + warn_stale:
            print(f"  → {r['source_script']}")


if __name__ == "__main__":
    records = check_freshness()
    if "--json" in sys.argv:
        status, _, _ = overall_status(records)
        out = {
            "overall_status": status,
            "checked_at": datetime.now(EET).isoformat(timespec='seconds'),
            "files": records,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    elif "--line" in sys.argv:
        print(render_line(records))
    elif "--banner" in sys.argv:
        banner = render_banner(records)
        if banner:
            print(banner)
        # Empty stdout if healthy → easy to detect from prompt
    else:
        render_human(records)

    # Exit code: 0 healthy, 1 degraded, 2 critical (for shell scripting)
    status, _, _ = overall_status(records)
    sys.exit({"HEALTHY": 0, "DEGRADED": 1, "CRITICAL": 2}[status])
