#!/usr/bin/env python3
"""
GOLD TACTIC — News Embargo State Machine (T1.2 / Phase B1)

Determines if a HIGH-impact economic event makes new trades unsafe.

States (per latest relevant event):
  CLEAR    — no HIGH event in T-30..T+5 window → new trades allowed
  PENDING  — HIGH event in T-30..T-1min → new trades BLOCKED, existing OK
  EVENT    — HIGH event happening now (T-1..T+1min) → new BLOCKED, alert
  POST     — HIGH event 1-5min ago → new BLOCKED, observe spread/volatility
  RESUMED  — last HIGH event >5min ago → CLEAR

Reads:
  data/economic_calendar.json (forexfactory_events + central_banks)

Outputs:
  --json         → full state machine JSON
  --line         → 1-liner for footer
  --banner       → HTML banner if BLOCKED (else empty)
  --allow-trade  → exit code 0 if trades allowed, 1 if blocked

Append-only audit:
  data/embargo_log.jsonl

Usage in Monitor STEP 4.85:
  python news_embargo.py --json > GOLD_TACTIC/data/embargo_state.json
  python news_embargo.py --allow-trade  # check via exit code

Per-asset relevance: this v1 blocks ALL new trades regardless of asset.
Phase 2 enhancement: per-asset relevance map (e.g. ECB only blocks EUR pairs).
"""

import json
import os
import sys
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

DATA_DIR = Path(__file__).parent.parent / "data"
CALENDAR_FILE = DATA_DIR / "economic_calendar.json"
LOG_FILE = DATA_DIR / "embargo_log.jsonl"

EET = timezone(timedelta(hours=3))
UTC = timezone.utc

# Embargo window definitions (minutes)
PENDING_BEFORE_MIN = 30   # T-30 → T-1
EVENT_WINDOW_MIN = 1      # T-1 → T+1
POST_AFTER_MIN = 5        # T+1 → T+5

# Per-asset relevance — for Phase 2; v1 blocks ALL
PER_ASSET_RELEVANCE = {
    # Default: a HIGH event matching any of these keywords blocks the asset
    "EURUSD": ["ECB", "EUR", "EURO", "EUROZONE", "GERMAN", "FRENCH"],
    "GBPUSD": ["BOE", "UK", "GBP", "POUND", "BRITISH"],
    "USDJPY": ["BOJ", "JAPAN", "JPY", "YEN"],
    "AUDUSD": ["RBA", "AUSTRALIA", "AUD", "AUSSIE"],
    "XAUUSD": ["FED", "CPI", "PCE", "FOMC", "POWELL", "INFLATION", "JOBS", "NFP"],
    "NAS100": ["FED", "CPI", "PCE", "FOMC", "POWELL", "JOBS", "NFP", "EARNINGS", "TECH"],
    "SPX500": ["FED", "CPI", "PCE", "FOMC", "POWELL", "JOBS", "NFP", "EARNINGS"],
    "BTC": ["FED", "CPI", "FOMC", "SEC", "ETF", "REGULATION"],
    "ETH": ["FED", "CPI", "FOMC", "SEC", "ETF"],
    "SOL": ["FED", "SEC", "ETF"],
    "XRP": ["FED", "SEC", "RIPPLE"],
    "DXY": ["FED", "CPI", "PCE", "FOMC", "JOBS", "NFP", "TREASURY"],
}

# Always-block events (regardless of asset)
GLOBAL_BLOCK_KEYWORDS = ["FED", "FOMC", "CPI", "NFP", "PCE", "POWELL"]


def _parse_event_datetime(date_str):
    """Parse various date formats from economic_calendar.json. Return timezone-aware datetime."""
    if not date_str:
        return None

    # Format 1: RFC 2822-ish "Thu, 16 Apr 2026 15:00:00 GMT"
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        if dt:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
    except Exception:
        pass

    # Format 2: ISO "2026-04-17T15:00:00+03:00"
    try:
        if 'T' in date_str:
            if date_str.endswith('Z'):
                date_str = date_str[:-1] + '+00:00'
            return datetime.fromisoformat(date_str)
    except Exception:
        pass

    # Format 3: ForexFactory "2026-04-17 15:00:00" (assume EET)
    try:
        if ' ' in date_str:
            dt = datetime.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S')
            return dt.replace(tzinfo=EET)
    except Exception:
        pass

    return None


def _gather_high_events():
    """Return all HIGH-impact events with parsed datetimes."""
    if not CALENDAR_FILE.exists():
        return []
    try:
        data = json.loads(CALENDAR_FILE.read_text(encoding='utf-8'))
    except Exception:
        return []

    events = []

    # ForexFactory events
    for ev in data.get("forexfactory_events", []):
        if str(ev.get("impact", "")).upper() == "HIGH":
            dt = _parse_event_datetime(ev.get("date") or ev.get("datetime"))
            if dt:
                events.append({
                    "title": ev.get("title") or ev.get("event") or "Unknown",
                    "datetime": dt,
                    "impact": "HIGH",
                    "source": "ForexFactory",
                    "country": ev.get("country", ""),
                })

    # Central bank RSS — only HIGH
    for bank, items in (data.get("central_banks", {}) or {}).items():
        if not isinstance(items, list):
            continue
        for ev in items:
            if str(ev.get("impact", "")).upper() == "HIGH":
                dt = _parse_event_datetime(ev.get("date"))
                if dt:
                    events.append({
                        "title": ev.get("title", "Unknown"),
                        "datetime": dt,
                        "impact": "HIGH",
                        "source": bank,
                        "country": "",
                    })

    # high_impact_today (some flows write here)
    for ev in data.get("high_impact_today", []):
        dt = _parse_event_datetime(ev.get("date") or ev.get("datetime"))
        if dt:
            events.append({
                "title": ev.get("title") or ev.get("event") or "Unknown",
                "datetime": dt,
                "impact": "HIGH",
                "source": ev.get("source", "calendar"),
                "country": ev.get("country", ""),
            })

    # Dedupe by (title, datetime)
    seen = set()
    unique = []
    for e in events:
        key = (e["title"][:80], e["datetime"].isoformat())
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def _classify_event(event_dt, now):
    """Return state for a single event based on minutes-from-now."""
    delta_sec = (event_dt - now).total_seconds()
    delta_min = delta_sec / 60.0

    if delta_min > PENDING_BEFORE_MIN:
        return "FUTURE_FAR", delta_min  # > T-30 — outside window
    if EVENT_WINDOW_MIN < delta_min <= PENDING_BEFORE_MIN:
        return "PENDING", delta_min      # T-30 → T-1
    if -EVENT_WINDOW_MIN <= delta_min <= EVENT_WINDOW_MIN:
        return "EVENT", delta_min        # T-1 → T+1
    if -POST_AFTER_MIN <= delta_min < -EVENT_WINDOW_MIN:
        return "POST", delta_min         # T+1 → T+5
    return "PAST", delta_min             # > T+5 — outside window


def _event_blocks_asset(event, asset):
    """Phase 2 helper: does this event block this specific asset?
    v1 caller passes asset=None which blocks all assets unconditionally."""
    if asset is None:
        return True
    title_upper = (event.get("title", "") + " " + event.get("country", "")).upper()
    # Global blockers (Fed/CPI etc) block everything
    if any(kw in title_upper for kw in GLOBAL_BLOCK_KEYWORDS):
        return True
    keywords = PER_ASSET_RELEVANCE.get(asset, [])
    return any(kw in title_upper for kw in keywords)


def compute_embargo(asset=None):
    """
    Compute embargo state. Returns dict.
    asset=None → block on ANY HIGH event (conservative default for v1).
    """
    now = datetime.now(EET)
    all_events = _gather_high_events()

    relevant = []
    for ev in all_events:
        ev_state, delta_min = _classify_event(ev["datetime"], now)
        if ev_state in ("FUTURE_FAR", "PAST"):
            continue
        # Filter by asset relevance
        if not _event_blocks_asset(ev, asset):
            continue
        relevant.append({
            **ev,
            "datetime": ev["datetime"].isoformat(timespec='seconds'),
            "state": ev_state,
            "delta_minutes": round(delta_min, 1),
        })

    # Determine overall state — worst case wins
    state_priority = {"EVENT": 4, "POST": 3, "PENDING": 2, "CLEAR": 1}
    overall = "CLEAR"
    blocking_event = None
    for e in relevant:
        if state_priority.get(e["state"], 0) > state_priority.get(overall, 0):
            overall = e["state"]
            blocking_event = e

    # Find next upcoming HIGH event for countdown (even if CLEAR)
    upcoming = [e for e in all_events if e["datetime"] > now]
    upcoming.sort(key=lambda e: e["datetime"])
    next_event = None
    if upcoming:
        nxt = upcoming[0]
        next_event = {
            "title": nxt["title"],
            "datetime": nxt["datetime"].isoformat(timespec='seconds'),
            "minutes_until": round((nxt["datetime"] - now).total_seconds() / 60, 1),
            "source": nxt["source"],
        }

    allow_trade = (overall == "CLEAR")

    return {
        "checked_at": now.isoformat(timespec='seconds'),
        "asset_filter": asset or "ALL",
        "overall_state": overall,
        "allow_trade": allow_trade,
        "blocking_event": blocking_event,
        "next_high_event": next_event,
        "active_events": relevant,
        "total_events_today": len(all_events),
    }


def render_line(state):
    """1-liner for footer."""
    s = state["overall_state"]
    if s == "CLEAR":
        nxt = state.get("next_high_event")
        if nxt and nxt.get("minutes_until", 999) < 240:  # < 4h
            return f"📅 Next HIGH: {nxt['title'][:30]} σε {nxt['minutes_until']:.0f}'"
        return "📅 News: clear"
    if s == "PENDING":
        be = state["blocking_event"]
        return f"🛑 EMBARGO PENDING: {be['title'][:40]} σε {abs(be['delta_minutes']):.0f}' (block νέα trades)"
    if s == "EVENT":
        be = state["blocking_event"]
        return f"⚡ HIGH EVENT NOW: {be['title'][:50]} (block νέα trades)"
    if s == "POST":
        be = state["blocking_event"]
        return f"🚧 POST-EVENT: {be['title'][:40]} ({abs(be['delta_minutes']):.0f}' ago) — observe volatility"
    return "📅 News: ?"


def render_banner(state):
    """HTML banner if blocked, else empty."""
    if state["allow_trade"]:
        return ""
    s = state["overall_state"]
    be = state["blocking_event"]
    title = be["title"][:80]
    src = be.get("source", "?")

    if s == "PENDING":
        return (
            f"🛑 <b>NEWS EMBARGO ACTIVE</b> — PENDING\n"
            f"<b>{title}</b> <i>({src})</i>\n"
            f"σε {abs(be['delta_minutes']):.0f} λεπτά · ΟΧΙ νέα trades μέχρι T+5"
        )
    if s == "EVENT":
        return (
            f"⚡ <b>HIGH-IMPACT EVENT NOW</b>\n"
            f"<b>{title}</b> <i>({src})</i>\n"
            f"🛑 Block νέα trades · διατήρηση open με προσοχή στο spread"
        )
    if s == "POST":
        return (
            f"🚧 <b>POST-EVENT WINDOW</b> ({abs(be['delta_minutes']):.0f}' ago)\n"
            f"<b>{title}</b> <i>({src})</i>\n"
            f"Παρακολούθηση volatility · ΟΧΙ νέα trades μέχρι T+5"
        )
    return ""


def append_log_entry(state):
    """Append state transition to audit log if BLOCKED."""
    if state["allow_trade"]:
        return
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open('a', encoding='utf-8') as f:
        f.write(json.dumps({
            "timestamp": state["checked_at"],
            "state": state["overall_state"],
            "event_title": state["blocking_event"]["title"] if state["blocking_event"] else "",
            "delta_minutes": state["blocking_event"]["delta_minutes"] if state["blocking_event"] else None,
        }, ensure_ascii=False) + "\n")


def render_human(state):
    print(f"=== Embargo State: {state['overall_state']} ({'ALLOW' if state['allow_trade'] else 'BLOCKED'}) ===")
    print(f"Asset filter: {state['asset_filter']}")
    print(f"Total HIGH events today: {state['total_events_today']}")
    print(f"Active in window: {len(state['active_events'])}")
    print()
    if state['blocking_event']:
        be = state['blocking_event']
        print(f"🛑 Blocking event:")
        print(f"   {be['title']}")
        print(f"   Source: {be.get('source', '?')}, Delta: {be['delta_minutes']:+.1f}min, State: {be['state']}")
    if state['next_high_event']:
        ne = state['next_high_event']
        print(f"\n📅 Next HIGH:")
        print(f"   {ne['title']}")
        print(f"   in {ne['minutes_until']:.0f} minutes ({ne['datetime']})")
    if state['active_events']:
        print(f"\nAll active in window:")
        for e in state['active_events']:
            print(f"  [{e['state']}] {e['delta_minutes']:+.1f}min {e['title'][:60]} ({e['source']})")


if __name__ == "__main__":
    args = sys.argv[1:]
    asset = None
    for a in args:
        if a.startswith('--asset='):
            asset = a.split('=', 1)[1].upper()

    state = compute_embargo(asset=asset)

    if "--json" in args:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    elif "--line" in args:
        print(render_line(state))
    elif "--banner" in args:
        b = render_banner(state)
        if b:
            print(b)
    elif "--allow-trade" in args:
        # silent — exit code says everything
        sys.exit(0 if state["allow_trade"] else 1)
    else:
        render_human(state)

    # Always log if blocked (audit trail)
    append_log_entry(state)

    # Default exit code
    sys.exit(0 if state["allow_trade"] else 1)
