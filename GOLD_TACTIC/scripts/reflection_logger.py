#!/usr/bin/env python3
"""
GOLD TACTIC — Reflection Logger (Layer 2 of Self-Improvement)

Generates structured reflections after every closed trade.
Inspired by CryptoTrade's Reflection Analyst + TradingAgents post-trade pattern.

What it captures per closed trade:
  - Quantitative facts: R-multiple, hold time, MAE/MFE, TP1-then-BE flag
  - Qualitative narrative: 2-3 sentence reflection citing TRS criteria + exit reason
  - Attribution tags: rule-based labels (e.g. entered_with_missing_news_criterion)
  - Lesson one-liner: short Greek phrase shown in L6 EXIT message
  - Calibration seeds: tags that feed weekly_audit hypothesis detectors

Usage:
  reflection_logger.py post-trade <trade_id>      # Generate for one trade
  reflection_logger.py recent --symbol BTC --limit 3   # Get recent reflections (used by selector)
  reflection_logger.py replay <date_from>         # Backfill reflections retroactively
  reflection_logger.py latest-lesson              # Print latest lesson_one_liner (for L6 EXIT)
  reflection_logger.py stats                      # Counts + summary
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
TRADE_JOURNAL = DATA_DIR / "trade_journal.jsonl"
REFLECTIONS_FILE = DATA_DIR / "trade_reflections.jsonl"
ERRORS_FILE = DATA_DIR / "reflection_errors.jsonl"
ECONOMIC_CALENDAR = DATA_DIR / "economic_calendar.json"
SESSION_LOG = DATA_DIR / "session_log.jsonl"
CYCLE_LOG = DATA_DIR / "cycle_log.jsonl"

EET = timezone(timedelta(hours=3))


# ─── Helpers ─────────────────────────────────────────────────────────────
def _now():
    return datetime.now(EET)


def _iso(dt):
    return dt.isoformat(timespec='seconds')


def _parse_iso(s):
    if not s:
        return None
    try:
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _append_jsonl(path: Path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_journal():
    """Return list of all closed trade records."""
    if not TRADE_JOURNAL.exists():
        return []
    trades = []
    with TRADE_JOURNAL.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                trades.append(json.loads(line))
            except Exception:
                continue
    return trades


def _read_reflections():
    if not REFLECTIONS_FILE.exists():
        return []
    out = []
    with REFLECTIONS_FILE.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    return out


def _trade_already_reflected(trade_id):
    return any(r.get("trade_id") == trade_id for r in _read_reflections())


# ─── Asset class classifier ──────────────────────────────────────────────
ASSET_CLASS = {
    "EURUSD": "forex_major", "GBPUSD": "forex_major",
    "USDJPY": "forex_major", "AUDUSD": "forex_major",
    "XAUUSD": "metals", "DXY": "forex_index",
    "NAS100": "index", "SPX500": "index",
    "BTC": "crypto", "ETH": "crypto", "SOL": "crypto", "XRP": "crypto",
}


# ─── Session classifier ──────────────────────────────────────────────────
def _session_for(dt: datetime) -> str:
    """Classify entry time into kill-zone / session bucket (EET)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=EET)
    et = dt.astimezone(EET)
    weekday = et.weekday()  # 0=Mon, 6=Sun
    h = et.hour + et.minute / 60.0

    if weekday >= 5:  # Sat/Sun
        return "weekend"
    if 10.0 <= h < 12.0:
        return "london_kz"
    if 15.5 <= h < 17.5:
        return "ny_kz"
    if 12.0 <= h < 15.5 or 17.5 <= h < 22.0:
        return "acceptable"
    return "off"


# ─── HIGH event proximity check ──────────────────────────────────────────
def _high_event_near(entry_dt: datetime, window_hours: float = 2.0) -> bool:
    """Return True if any HIGH-impact event is within ±window_hours of entry_dt."""
    if not ECONOMIC_CALENDAR.exists():
        return False
    try:
        cal = json.loads(ECONOMIC_CALENDAR.read_text(encoding='utf-8'))
    except Exception:
        return False

    from email.utils import parsedate_to_datetime

    def _try_parse(s):
        if not s:
            return None
        try:
            if 'T' in s:
                return _parse_iso(s)
            dt = parsedate_to_datetime(s)
            if dt and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    high_events = []
    for ev in cal.get("forexfactory_events", []) or []:
        if str(ev.get("impact", "")).upper() == "HIGH":
            dt = _try_parse(ev.get("date") or ev.get("datetime"))
            if dt:
                high_events.append(dt)
    for items in (cal.get("central_banks", {}) or {}).values():
        for ev in items if isinstance(items, list) else []:
            if str(ev.get("impact", "")).upper() == "HIGH":
                dt = _try_parse(ev.get("date"))
                if dt:
                    high_events.append(dt)
    for ev in cal.get("high_impact_today", []) or []:
        dt = _try_parse(ev.get("date") or ev.get("datetime"))
        if dt:
            high_events.append(dt)

    if entry_dt.tzinfo is None:
        entry_dt = entry_dt.replace(tzinfo=EET)

    for ev_dt in high_events:
        delta = abs((ev_dt - entry_dt).total_seconds()) / 3600.0
        if delta <= window_hours:
            return True
    return False


# ─── Attribution tagger ──────────────────────────────────────────────────
def _tag_trade(trade) -> list:
    """Apply rule-based labels for downstream calibration detectors."""
    tags = []
    crit = trade.get("criteria_at_entry") or {}
    missing = [k for k, v in crit.items() if v is False]
    if "News" in missing:
        tags.append("entered_with_missing_news_criterion")
    if "Key" in missing:
        tags.append("entered_with_missing_key_criterion")
    if "ADR" in missing:
        tags.append("entered_with_missing_adr_criterion")
    if "RSI" in missing:
        tags.append("entered_with_missing_rsi_criterion")
    if "TF" in missing:
        tags.append("entered_with_missing_tf_criterion")

    if trade.get("tag") == "probe":
        tags.append("probe_entry")
    if trade.get("tag") == "confirm":
        tags.append("confirm_scale_in")

    exit_reason = trade.get("exit_reason", "")
    if exit_reason == "max_hold":
        tags.append("max_hold_4h_timeout")
    elif exit_reason == "sl":
        tags.append("sl_hit")
    elif exit_reason == "be":
        tags.append("be_exit_after_tp1")
    elif exit_reason == "tp2":
        tags.append("tp2_runner_success")
    elif exit_reason == "tp1":
        tags.append("tp1_close_legacy")
    elif exit_reason and "cleanup" in exit_reason:
        tags.append("admin_cleanup")

    entry_dt = _parse_iso(trade.get("entry_time"))
    if entry_dt and _high_event_near(entry_dt, window_hours=2.0):
        tags.append("high_event_within_2h_of_entry")

    if trade.get("tp1_hit") and trade.get("be_moved") and exit_reason == "be":
        tags.append("tp1_then_be_neutral")

    last_pnl = trade.get("last_pnl_eur") or 0
    risk = trade.get("risk_eur") or 1
    if abs(last_pnl) >= 1.5 * risk:
        tags.append("pnl_swing_above_1_5R")

    return tags


# ─── R-multiple + lifecycle ──────────────────────────────────────────────
def _compute_r_multiple(trade):
    pnl = float(trade.get("final_pnl_eur") or 0)
    risk = float(trade.get("risk_eur") or 0)
    if risk <= 0:
        return 0.0
    return round(pnl / risk, 2)


def _compute_hold_minutes(trade):
    entry = _parse_iso(trade.get("entry_time"))
    exit_ = _parse_iso(trade.get("exit_time"))
    if not entry or not exit_:
        return None
    return int((exit_ - entry).total_seconds() / 60)


def _classify_outcome(trade):
    pnl = float(trade.get("final_pnl_eur") or 0)
    if abs(pnl) < 0.01:
        return "breakeven"
    return "win" if pnl > 0 else "loss"


# ─── Narrative generator (Greek, deterministic from facts) ──────────────
def _generate_narrative(trade, tags):
    symbol = trade.get("symbol", "?")
    direction = trade.get("direction", "?")
    tag = trade.get("tag", "full")
    exit_reason = trade.get("exit_reason", "?")
    pnl = float(trade.get("final_pnl_eur") or 0)
    crit = trade.get("criteria_at_entry") or {}
    missing = [k for k, v in crit.items() if v is False]
    session = _session_for(_parse_iso(trade.get("entry_time")) or _now())
    hold_min = _compute_hold_minutes(trade) or 0

    # Open phrase
    tag_label = {"full": "Full position", "probe": "Probe", "confirm": "Confirm scale-in"}.get(tag, tag)
    sess_label = {"london_kz": "London KZ", "ny_kz": "NY KZ", "acceptable": "session OK",
                  "off": "off-hours", "weekend": "weekend"}.get(session, session)
    parts = [f"{tag_label} {direction} {symbol} σε {sess_label}"]

    # Criteria summary
    if not missing:
        parts.append("όλα τα κριτήρια ήταν καλυμμένα")
    else:
        parts.append(f"χωρίς {' & '.join(missing)}")

    # Outcome
    outcome_phrases = {
        "tp2": f"έφτασε TP2 +{pnl:.2f}€ ({hold_min}min)",
        "tp1": f"έκλεισε TP1 +{pnl:.2f}€",
        "be": f"επέστρεψε στο entry post-TP1 (BE exit, {hold_min}min)",
        "sl": f"χτύπησε SL {pnl:.2f}€",
        "max_hold": f"4h timeout χωρίς TP/SL ({pnl:+.2f}€)",
    }
    parts.append(outcome_phrases.get(exit_reason, f"closed reason={exit_reason} ({pnl:+.2f}€)"))

    # Pattern flag from tags
    if "high_event_within_2h_of_entry" in tags and exit_reason in ("max_hold", "sl"):
        parts.append("HIGH event εντός 2h — pre-event compression πιθανό αίτιο")
    if "entered_with_missing_news_criterion" in tags and exit_reason in ("sl", "max_hold"):
        parts.append("το missing News κριτήριο φαίνεται να συνδέεται με το αρνητικό outcome")

    return ". ".join(parts) + "."


# ─── Lesson one-liner generator (for L6 EXIT) ───────────────────────────
def _generate_lesson(trade, tags):
    """Short Greek phrase shown in L6 EXIT message."""
    exit_reason = trade.get("exit_reason", "")
    has_news_miss = "entered_with_missing_news_criterion" in tags
    has_high_event = "high_event_within_2h_of_entry" in tags
    is_probe = trade.get("tag") == "probe"

    if exit_reason == "tp2":
        return "Setup ωρίμασε όπως αναμενόταν — runner πέτυχε"
    if exit_reason == "tp1":
        return "TP1 πέτυχε — εξετάζουμε αν runner θα πιάσει TP2 σε επόμενα setups"
    if exit_reason == "be":
        return "BE exit μετά από TP1 — η κίνηση δεν συνέχισε, neutral τρέξιμο"
    if exit_reason == "sl":
        if has_news_miss:
            return "SL hit με missing News — επανέλεγξε news embargo timing"
        return "SL hit — επιβεβαίωση ότι το SL placement είναι σωστό για το asset"
    if exit_reason == "max_hold":
        if has_high_event and is_probe:
            return "Probes με HIGH event εντός 2h → υψηλός κίνδυνος timeout"
        if has_news_miss:
            return "4h timeout με missing News — πιθανώς widening news embargo"
        return "4h timeout — setup δεν ωρίμασε στον προβλεπόμενο χρόνο"
    if exit_reason and "cleanup" in exit_reason:
        return "admin cleanup — δεν αξιολογείται ως πραγματικό trade"
    return f"Closed: {exit_reason}"


# ─── Calibration seeds (feed weekly_audit detectors) ────────────────────
def _calibration_seeds(trade, tags, outcome):
    seeds = []
    if outcome == "loss":
        if "entered_with_missing_news_criterion" in tags or "high_event_within_2h_of_entry" in tags:
            seeds.append("news_embargo_widen")
        if "probe_entry" in tags and "max_hold_4h_timeout" in tags:
            seeds.append("probe_during_pre_event_block")
        if "sl_hit" in tags:
            seeds.append("sl_cap_calibrate")
    if outcome == "win" and "tp2_runner_success" in tags:
        seeds.append("auto_launch_candidate")
    return seeds


# ─── Main reflection generator ───────────────────────────────────────────
def generate_reflection(trade):
    """Build the full reflection JSON record from a closed trade."""
    tags = _tag_trade(trade)
    outcome = _classify_outcome(trade)
    crit = trade.get("criteria_at_entry") or {}
    missing = [k for k, v in crit.items() if v is False]
    entry_dt = _parse_iso(trade.get("entry_time")) or _now()

    return {
        "trade_id": trade.get("trade_id"),
        "reflected_at": _iso(_now()),
        "outcome": outcome,
        "r_multiple": _compute_r_multiple(trade),
        "hold_minutes": _compute_hold_minutes(trade),
        "tp1_hit_then_be": bool(trade.get("tp1_hit") and trade.get("exit_reason") == "be"),
        "trs_at_entry": trade.get("trs_at_entry"),
        "criteria_at_entry": crit,
        "missing_criteria": missing,
        "exit_reason": trade.get("exit_reason"),
        "session_at_entry": _session_for(entry_dt),
        "asset_class": ASSET_CLASS.get(trade.get("symbol"), "unknown"),
        "tag": trade.get("tag", "full"),
        "attribution_tags": tags,
        "narrative": _generate_narrative(trade, tags),
        "lesson_one_liner": _generate_lesson(trade, tags),
        "calibration_seeds": _calibration_seeds(trade, tags, outcome),
    }


# ─── CLI commands ────────────────────────────────────────────────────────
def cmd_post_trade(trade_id):
    if _trade_already_reflected(trade_id):
        print(f"[skip] Reflection for {trade_id} already exists.")
        return 0

    trades = _read_journal()
    target = next((t for t in trades if t.get("trade_id") == trade_id), None)
    if not target:
        err = f"Trade {trade_id} not found in trade_journal.jsonl"
        print(f"[error] {err}", file=sys.stderr)
        _append_jsonl(ERRORS_FILE, {"ts": _iso(_now()), "trade_id": trade_id, "error": err})
        return 1

    try:
        reflection = generate_reflection(target)
        _append_jsonl(REFLECTIONS_FILE, reflection)
        print(f"[ok] Reflection logged for {trade_id}")
        print(f"  outcome={reflection['outcome']} r_multiple={reflection['r_multiple']}")
        print(f"  tags={reflection['attribution_tags']}")
        print(f"  lesson: {reflection['lesson_one_liner']}")
        return 0
    except Exception as e:
        _append_jsonl(ERRORS_FILE, {"ts": _iso(_now()), "trade_id": trade_id, "error": str(e)})
        print(f"[error] {e}", file=sys.stderr)
        return 1


def cmd_recent(symbol=None, limit=3):
    refs = _read_reflections()
    if symbol:
        refs = [r for r in refs if r.get("trade_id", "").startswith(symbol.upper())]
    refs.sort(key=lambda r: r.get("reflected_at", ""), reverse=True)
    refs = refs[:limit]
    if not refs:
        print(json.dumps({"reflections": []}, ensure_ascii=False, indent=2))
        return
    print(json.dumps({"reflections": refs}, ensure_ascii=False, indent=2))


def cmd_replay(date_from=None):
    """Backfill reflections for any closed trades since date_from."""
    cutoff = None
    if date_from:
        try:
            cutoff = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=EET)
        except Exception:
            print(f"Invalid date format. Use YYYY-MM-DD.", file=sys.stderr)
            return 1

    trades = _read_journal()
    backfilled = 0
    skipped = 0
    for t in trades:
        if not t.get("exit_time"):
            continue
        if cutoff:
            exit_dt = _parse_iso(t.get("exit_time"))
            if not exit_dt or exit_dt < cutoff:
                continue
        if _trade_already_reflected(t.get("trade_id", "")):
            skipped += 1
            continue
        try:
            ref = generate_reflection(t)
            _append_jsonl(REFLECTIONS_FILE, ref)
            backfilled += 1
            print(f"  + {t.get('trade_id')} ({ref['outcome']})")
        except Exception as e:
            print(f"  ! {t.get('trade_id')} error: {e}", file=sys.stderr)
    print(f"\n[replay] {backfilled} backfilled, {skipped} already had reflections")
    return 0


def cmd_latest_lesson():
    """Print the most recent lesson_one_liner. Used by L6 EXIT message."""
    refs = _read_reflections()
    if not refs:
        return
    refs.sort(key=lambda r: r.get("reflected_at", ""), reverse=True)
    print(refs[0].get("lesson_one_liner", ""))


def cmd_stats():
    refs = _read_reflections()
    if not refs:
        print("No reflections yet.")
        return
    outcomes = {"win": 0, "loss": 0, "breakeven": 0}
    seeds = {}
    sessions = {}
    for r in refs:
        outcomes[r.get("outcome", "?")] = outcomes.get(r.get("outcome", "?"), 0) + 1
        for s in r.get("calibration_seeds", []):
            seeds[s] = seeds.get(s, 0) + 1
        sessions[r.get("session_at_entry", "?")] = sessions.get(r.get("session_at_entry", "?"), 0) + 1
    print(f"=== Reflections Stats ({len(refs)} entries) ===")
    print(f"Outcomes: {outcomes}")
    print(f"Sessions: {sessions}")
    print(f"Calibration seeds (feed weekly_audit): {seeds}")
    print(f"\nRecent (last 5):")
    refs.sort(key=lambda r: r.get("reflected_at", ""), reverse=True)
    for r in refs[:5]:
        print(f"  [{r.get('outcome', '?'):8s}] {r.get('trade_id', '?'):40s} R={r.get('r_multiple', '?')} · {r.get('lesson_one_liner', '')[:60]}")


# ─── Entry point ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0]

    if cmd == "post-trade":
        if len(args) < 2:
            print("Usage: reflection_logger.py post-trade <trade_id>", file=sys.stderr)
            sys.exit(1)
        sys.exit(cmd_post_trade(args[1]))

    elif cmd == "recent":
        symbol = None
        limit = 3
        for a in args[1:]:
            if a.startswith("--symbol="):
                symbol = a.split("=", 1)[1]
            elif a == "--symbol":
                idx = args.index(a) + 1
                symbol = args[idx] if idx < len(args) else None
            elif a.startswith("--limit="):
                limit = int(a.split("=", 1)[1])
            elif a == "--limit":
                idx = args.index(a) + 1
                limit = int(args[idx]) if idx < len(args) else 3
        cmd_recent(symbol=symbol, limit=limit)

    elif cmd == "replay":
        date_from = args[1] if len(args) > 1 else None
        sys.exit(cmd_replay(date_from))

    elif cmd == "latest-lesson":
        cmd_latest_lesson()

    elif cmd == "stats":
        cmd_stats()

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)
