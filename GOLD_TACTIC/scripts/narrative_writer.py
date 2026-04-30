#!/usr/bin/env python3
"""
GOLD TACTIC — Narrative Memory Writer (v7.3 Shared Brain)

Maintains data/narrative_memory.json — the cross-cycle "brain" that lets
schedules collaborate and the Telegram agent remember what it just said.

Schema (v2):
  {
    "schema_version": "v2",
    "last_updated": "<ISO EET>",
    "last_writer": "<schedule_name>",
    "cycles": [<= 5 entries: ts, schedule, trs_summary, note],
    "last_messages": [<= 3 entries: ts, level, tier_msg_id, summary, asset_focus],
    "hypotheses": [<= 6 open: id, condition, then, expires_ts, added_ts],
    "narratives_per_asset": {"<SYMBOL>": "1-paragraph thread"},
    "voice_avoid_phrases": [<= 10 strings auto-populated],
    "limits": {...}
  }

CLI:
  narrative_writer.py append-cycle --schedule X --trs-json '{}' --note "..."
  narrative_writer.py log-message --tier-msg-id N --level L4 --text-file path
                                  [--summary "..."] [--asset-focus "X,Y"]
  narrative_writer.py add-hypothesis --asset X --condition "..." --then "..." --expires-h 6
  narrative_writer.py update-narrative --asset X --thread-append "..."
  narrative_writer.py learn-phrase --text "..."
  narrative_writer.py refresh-avoid-phrases [--window-hours 4] [--min-occurrences 2]
  narrative_writer.py read [--max-bytes N] [--asset X]
  narrative_writer.py prune
  narrative_writer.py reset

All writes are atomic (.tmp + os.replace). Lock-aware: if selector.lock is
fresh, retry 3× × 200ms before giving up (logs narrative_write_skipped event).
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

DATA_DIR = Path(__file__).parent.parent / "data"
MEMORY_FILE = DATA_DIR / "narrative_memory.json"
LOCK_FILE = DATA_DIR / "selector.lock"
CYCLE_LOG = DATA_DIR / "cycle_log.jsonl"

EET = timezone(timedelta(hours=3))

LOCK_STALE_AFTER_SEC = 300
LOCK_RETRY_COUNT = 3
LOCK_RETRY_DELAY_SEC = 0.2

DEFAULT_LIMITS = {
    "cycles_max": 5,
    "messages_max": 3,
    "hypotheses_max": 6,
    "phrases_max": 10,
    "narrative_max_chars": 300,
    "note_max_chars": 200,
    "summary_max_chars": 220,
}

EMPTY_MEMORY = {
    "schema_version": "v2",
    "last_updated": None,
    "last_writer": None,
    "cycles": [],
    "last_messages": [],
    "hypotheses": [],
    "narratives_per_asset": {},
    "voice_avoid_phrases": [],
    "limits": dict(DEFAULT_LIMITS),
}


# ─── Time helpers ────────────────────────────────────────────────────────
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


# ─── IO helpers ──────────────────────────────────────────────────────────
def _atomic_write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, path)


def _append_jsonl(path: Path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ─── Lock awareness ──────────────────────────────────────────────────────
def _selector_lock_active() -> bool:
    """True if selector.lock exists and is fresh (<5min old)."""
    if not LOCK_FILE.exists():
        return False
    try:
        data = json.loads(LOCK_FILE.read_text(encoding='utf-8'))
        started = _parse_iso(data.get("started_at"))
        if not started:
            return False
        age = (_now() - started).total_seconds()
        return age < LOCK_STALE_AFTER_SEC
    except Exception:
        return False


def _wait_for_lock_release() -> bool:
    """Try LOCK_RETRY_COUNT times with delay. Return True if safe to write."""
    for i in range(LOCK_RETRY_COUNT):
        if not _selector_lock_active():
            return True
        if i < LOCK_RETRY_COUNT - 1:
            time.sleep(LOCK_RETRY_DELAY_SEC)
    return not _selector_lock_active()


def _log_skip(reason: str, command: str):
    try:
        _append_jsonl(CYCLE_LOG, {
            "ts": _iso(_now()),
            "schedule": "narrative_writer",
            "type": "narrative_write_skipped",
            "reason": reason,
            "command": command,
        })
    except Exception:
        pass


# ─── Memory load / save ──────────────────────────────────────────────────
def _load_memory() -> dict:
    if not MEMORY_FILE.exists():
        return dict(EMPTY_MEMORY, narratives_per_asset={}, cycles=[],
                    last_messages=[], hypotheses=[], voice_avoid_phrases=[],
                    limits=dict(DEFAULT_LIMITS))
    try:
        data = json.loads(MEMORY_FILE.read_text(encoding='utf-8'))
    except Exception:
        # Corrupt file — fall back to empty defaults
        return dict(EMPTY_MEMORY, narratives_per_asset={}, cycles=[],
                    last_messages=[], hypotheses=[], voice_avoid_phrases=[],
                    limits=dict(DEFAULT_LIMITS))

    # Migrate legacy / fill missing fields
    if data.get("schema_version") != "v2":
        # Legacy file — start fresh but keep any narratives_per_asset if present
        narratives = data.get("narratives_per_asset") or {}
        return dict(EMPTY_MEMORY, narratives_per_asset=narratives, cycles=[],
                    last_messages=[], hypotheses=[], voice_avoid_phrases=[],
                    limits=dict(DEFAULT_LIMITS))

    # Ensure all fields exist
    for k, v in EMPTY_MEMORY.items():
        if k not in data:
            data[k] = v if not isinstance(v, (dict, list)) else (
                dict(v) if isinstance(v, dict) else list(v)
            )
    if not isinstance(data.get("limits"), dict):
        data["limits"] = dict(DEFAULT_LIMITS)
    else:
        # Fill missing limits keys
        for k, v in DEFAULT_LIMITS.items():
            data["limits"].setdefault(k, v)
    return data


def _save_memory(data: dict, writer: str, command: str, ignore_lock: bool = False) -> bool:
    """Lock-aware atomic save. Returns True on success.

    If ignore_lock=True, skip the selector.lock check. Used by Selector itself
    (which holds the lock) so its own narrative writes don't deadlock.
    """
    if not ignore_lock and not _wait_for_lock_release():
        _log_skip("selector_lock_active", command)
        return False
    data["last_updated"] = _iso(_now())
    data["last_writer"] = writer or "unknown"
    _prune_in_place(data)
    _atomic_write_json(MEMORY_FILE, data)

    # Log success event
    try:
        size = MEMORY_FILE.stat().st_size
        fields_changed = command  # caller-supplied command name as proxy
        _append_jsonl(CYCLE_LOG, {
            "ts": _iso(_now()),
            "schedule": writer or "narrative_writer",
            "type": "narrative_written",
            "command": command,
            "size_bytes": size,
        })
    except Exception:
        pass
    return True


# ─── Pruning + window enforcement ────────────────────────────────────────
def _prune_in_place(data: dict):
    """Trim arrays to limits + drop expired hypotheses + cap narrative lengths."""
    limits = data.get("limits") or DEFAULT_LIMITS
    cycles_max = int(limits.get("cycles_max", DEFAULT_LIMITS["cycles_max"]))
    messages_max = int(limits.get("messages_max", DEFAULT_LIMITS["messages_max"]))
    hypotheses_max = int(limits.get("hypotheses_max", DEFAULT_LIMITS["hypotheses_max"]))
    phrases_max = int(limits.get("phrases_max", DEFAULT_LIMITS["phrases_max"]))
    narrative_max = int(limits.get("narrative_max_chars", DEFAULT_LIMITS["narrative_max_chars"]))

    # Cycles + messages: keep newest N (assumed prepended)
    data["cycles"] = (data.get("cycles") or [])[:cycles_max]
    data["last_messages"] = (data.get("last_messages") or [])[:messages_max]

    # Hypotheses: drop expired, then cap
    now = _now()
    fresh = []
    for h in (data.get("hypotheses") or []):
        exp = _parse_iso(h.get("expires_ts"))
        if exp and exp < now:
            continue
        fresh.append(h)
    data["hypotheses"] = fresh[:hypotheses_max]

    # Voice avoid phrases: keep newest N (last appended), dedupe preserving order
    seen = set()
    deduped = []
    for p in (data.get("voice_avoid_phrases") or []):
        if p and p not in seen:
            seen.add(p)
            deduped.append(p)
    data["voice_avoid_phrases"] = deduped[-phrases_max:]

    # Per-asset narrative length cap
    napa = data.get("narratives_per_asset") or {}
    for sym, txt in list(napa.items()):
        if not isinstance(txt, str):
            napa[sym] = ""
            continue
        if len(txt) > narrative_max:
            napa[sym] = txt[-narrative_max:].lstrip()
    data["narratives_per_asset"] = napa


# ─── Commands ────────────────────────────────────────────────────────────
def cmd_append_cycle(args):
    data = _load_memory()
    note = (args.note or "").strip()
    note_max = int(data["limits"].get("note_max_chars", DEFAULT_LIMITS["note_max_chars"]))
    if len(note) > note_max:
        note = note[:note_max - 1] + "…"

    trs_summary = {}
    if args.trs_json:
        try:
            parsed = json.loads(args.trs_json)
            if isinstance(parsed, dict):
                trs_summary = {str(k): int(v) if isinstance(v, (int, float)) else v
                               for k, v in parsed.items()}
        except Exception:
            print(f"[warn] --trs-json could not be parsed; storing as empty", file=sys.stderr)

    entry = {
        "ts": _iso(_now()),
        "schedule": args.schedule or "unknown",
        "trs_summary": trs_summary,
        "note": note,
    }

    # Skip if last cycle has identical note (within 5min) — dedupe
    cycles = data.get("cycles") or []
    if cycles:
        last = cycles[0]
        last_ts = _parse_iso(last.get("ts"))
        if (last.get("note") == note
                and last.get("schedule") == entry["schedule"]
                and last_ts and (_now() - last_ts).total_seconds() < 300):
            print(f"[skip] Duplicate cycle note (same as last entry <5min ago)")
            return 0

    data["cycles"] = [entry] + (cycles or [])
    ok = _save_memory(data, args.schedule, "append-cycle", ignore_lock=getattr(args, "ignore_lock", False))
    if not ok:
        return 2
    print(f"[ok] append-cycle · {args.schedule} · note='{note[:60]}'")
    return 0


def cmd_log_message(args):
    data = _load_memory()
    text = ""
    if args.text_file:
        path = Path(args.text_file)
        if path.exists():
            try:
                text = path.read_text(encoding='utf-8')
            except Exception as e:
                print(f"[warn] could not read text file: {e}", file=sys.stderr)
    if args.text and not text:
        text = args.text

    summary = (args.summary or "").strip() or _auto_summarize(text)
    sum_max = int(data["limits"].get("summary_max_chars", DEFAULT_LIMITS["summary_max_chars"]))
    if len(summary) > sum_max:
        summary = summary[:sum_max - 1] + "…"

    asset_focus = []
    if args.asset_focus:
        asset_focus = [a.strip().upper() for a in args.asset_focus.split(",") if a.strip()]

    entry = {
        "ts": _iso(_now()),
        "level": args.level or "?",
        "tier_msg_id": args.tier_msg_id,
        "summary": summary,
        "asset_focus": asset_focus,
    }

    # Dedupe: skip if identical summary as last
    msgs = data.get("last_messages") or []
    if msgs and msgs[0].get("summary") == summary:
        print(f"[skip] Identical message summary (same as previous send)")
        return 0

    data["last_messages"] = [entry] + msgs
    ok = _save_memory(data, args.schedule or "Monitor", "log-message", ignore_lock=getattr(args, "ignore_lock", False))
    if not ok:
        return 2
    print(f"[ok] log-message · {args.level} · {summary[:60]}")
    return 0


def cmd_add_hypothesis(args):
    data = _load_memory()
    expires_h = float(args.expires_h or 6)
    expires_ts = _now() + timedelta(hours=expires_h)
    h_id = f"h{int(time.time())}"
    entry = {
        "id": h_id,
        "asset": (args.asset or "").upper(),
        "condition": (args.condition or "").strip(),
        "then": (args.then or "").strip(),
        "added_ts": _iso(_now()),
        "expires_ts": _iso(expires_ts),
    }
    if not entry["condition"] or not entry["then"]:
        print("[error] --condition and --then are required", file=sys.stderr)
        return 1

    # Dedupe: skip if identical (asset, condition, then) already open
    existing = data.get("hypotheses") or []
    for h in existing:
        if (h.get("asset") == entry["asset"]
                and h.get("condition") == entry["condition"]
                and h.get("then") == entry["then"]):
            print(f"[skip] Identical hypothesis already open: {h.get('id')}")
            return 0

    data["hypotheses"] = existing + [entry]
    ok = _save_memory(data, args.schedule or "Monitor", "add-hypothesis", ignore_lock=getattr(args, "ignore_lock", False))
    if not ok:
        return 2
    try:
        _append_jsonl(CYCLE_LOG, {
            "ts": _iso(_now()),
            "schedule": args.schedule or "Monitor",
            "type": "hypothesis_added",
            "id": h_id,
            "asset": entry["asset"],
            "expires_h": expires_h,
        })
    except Exception:
        pass
    print(f"[ok] add-hypothesis · {h_id} · {entry['asset']} · expires {expires_h}h")
    return 0


def cmd_update_narrative(args):
    data = _load_memory()
    asset = (args.asset or "").upper().strip()
    if not asset:
        print("[error] --asset required", file=sys.stderr)
        return 1
    text = (args.thread_append or "").strip()
    if not text:
        print("[error] --thread-append required", file=sys.stderr)
        return 1

    napa = data.get("narratives_per_asset") or {}
    current = napa.get(asset, "")
    sep = " " if not current.endswith((".", "!", "?", "—")) else " "
    if not current:
        merged = text
    else:
        merged = (current + sep + text).strip()

    napa[asset] = merged
    data["narratives_per_asset"] = napa
    ok = _save_memory(data, args.schedule or "Monitor", "update-narrative", ignore_lock=getattr(args, "ignore_lock", False))
    if not ok:
        return 2
    print(f"[ok] update-narrative · {asset} · {len(merged)} chars")
    return 0


def cmd_learn_phrase(args):
    data = _load_memory()
    txt = (args.text or "").strip()
    if not txt:
        print("[error] --text required", file=sys.stderr)
        return 1
    phrases = data.get("voice_avoid_phrases") or []
    if txt not in phrases:
        phrases.append(txt)
    data["voice_avoid_phrases"] = phrases
    ok = _save_memory(data, args.schedule or "Monitor", "learn-phrase", ignore_lock=getattr(args, "ignore_lock", False))
    if not ok:
        return 2
    print(f"[ok] learn-phrase · '{txt[:60]}'")
    return 0


def cmd_refresh_avoid_phrases(args):
    """Auto-detect repeated n-grams in last_messages summaries.

    Looks for 4-7 word phrases repeated >= --min-occurrences in the last
    --window-hours window. Adds them to voice_avoid_phrases (deduplicated).
    """
    data = _load_memory()
    window_h = float(args.window_hours or 4)
    min_occ = int(args.min_occurrences or 2)
    cutoff = _now() - timedelta(hours=window_h)

    summaries = []
    for m in (data.get("last_messages") or []):
        ts = _parse_iso(m.get("ts"))
        if ts and ts >= cutoff:
            s = m.get("summary") or ""
            if s:
                summaries.append(s)

    # Tokenize words (Greek + Latin), collect n-grams
    counts = Counter()
    for s in summaries:
        # Normalize whitespace, strip punctuation that breaks phrases but keep Greek chars
        normalized = re.sub(r'[^\w\sͰ-Ͽἀ-῿—–-]', ' ', s)
        tokens = [t for t in normalized.split() if len(t) >= 2]
        for n in (5, 6, 4):  # try 5-grams first, then 6, then 4
            for i in range(len(tokens) - n + 1):
                phrase = " ".join(tokens[i:i + n]).lower()
                counts[phrase] += 1

    new_phrases = [p for p, c in counts.items() if c >= min_occ]

    existing = set(data.get("voice_avoid_phrases") or [])
    added = []
    for p in new_phrases:
        if p not in existing:
            existing.add(p)
            added.append(p)
    data["voice_avoid_phrases"] = list(existing)

    ok = _save_memory(data, args.schedule or "Monitor", "refresh-avoid-phrases", ignore_lock=getattr(args, "ignore_lock", False))
    if not ok:
        return 2
    print(f"[ok] refresh-avoid-phrases · scanned {len(summaries)} summaries · added {len(added)} new")
    for p in added[:5]:
        print(f"     + '{p[:60]}'")
    return 0


def cmd_read(args):
    data = _load_memory()
    if args.asset:
        asset = args.asset.upper().strip()
        out = {
            "schema_version": data.get("schema_version"),
            "last_updated": data.get("last_updated"),
            "narrative": (data.get("narratives_per_asset") or {}).get(asset, ""),
            "cycles_for_asset": [
                c for c in (data.get("cycles") or [])
                if asset in (c.get("trs_summary") or {})
            ],
            "hypotheses_for_asset": [
                h for h in (data.get("hypotheses") or [])
                if h.get("asset") == asset
            ],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    payload = json.dumps(data, ensure_ascii=False, indent=2)
    if args.max_bytes:
        max_b = int(args.max_bytes)
        if len(payload.encode('utf-8')) > max_b:
            # Drop oldest cycles + oldest avoid phrases + truncate narratives
            truncated = dict(data)
            truncated["cycles"] = (truncated.get("cycles") or [])[:3]
            truncated["last_messages"] = (truncated.get("last_messages") or [])[:2]
            truncated["voice_avoid_phrases"] = (truncated.get("voice_avoid_phrases") or [])[-5:]
            payload = json.dumps(truncated, ensure_ascii=False, indent=2)
    sys.stdout.write(payload)
    if not payload.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def cmd_prune(args):
    data = _load_memory()
    _prune_in_place(data)
    ok = _save_memory(data, args.schedule or "narrative_writer", "prune", ignore_lock=getattr(args, "ignore_lock", False))
    if not ok:
        return 2
    size = MEMORY_FILE.stat().st_size if MEMORY_FILE.exists() else 0
    print(f"[ok] prune · cycles={len(data.get('cycles') or [])} · "
          f"msgs={len(data.get('last_messages') or [])} · "
          f"hyp={len(data.get('hypotheses') or [])} · "
          f"phrases={len(data.get('voice_avoid_phrases') or [])} · "
          f"size={size}B")
    return 0


def cmd_reset(args):
    data = dict(EMPTY_MEMORY)
    data["narratives_per_asset"] = {}
    data["cycles"] = []
    data["last_messages"] = []
    data["hypotheses"] = []
    data["voice_avoid_phrases"] = []
    data["limits"] = dict(DEFAULT_LIMITS)
    ok = _save_memory(data, args.schedule or "narrative_writer", "reset", ignore_lock=getattr(args, "ignore_lock", False))
    if not ok:
        return 2
    print(f"[ok] reset · narrative_memory.json wiped to schema v2 defaults")
    return 0


# ─── Auto-summarize helper ───────────────────────────────────────────────
def _auto_summarize(text: str, max_chars: int = 220) -> str:
    """Best-effort: take first non-empty line(s) up to max_chars."""
    if not text:
        return ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out = ""
    for ln in lines:
        clean = re.sub(r'<[^>]+>', '', ln)  # strip HTML tags
        clean = clean.strip()
        if not clean:
            continue
        if not out:
            out = clean
        else:
            out = out + " · " + clean
        if len(out) >= max_chars:
            break
    return out[:max_chars]


# ─── CLI ─────────────────────────────────────────────────────────────────
def _build_parser():
    p = argparse.ArgumentParser(prog="narrative_writer.py",
                                description="GOLD TACTIC narrative memory writer")
    sub = p.add_subparsers(dest="command", required=True)

    def _add_ignore_lock(sp):
        sp.add_argument("--ignore-lock", action="store_true",
                        help="Bypass selector.lock check (use only when caller IS the lock holder)")

    sp = sub.add_parser("append-cycle")
    sp.add_argument("--schedule", required=True)
    sp.add_argument("--trs-json", default="{}")
    sp.add_argument("--note", default="")
    _add_ignore_lock(sp)

    sp = sub.add_parser("log-message")
    sp.add_argument("--tier-msg-id", default=None)
    sp.add_argument("--level", default="?")
    sp.add_argument("--text-file", default=None)
    sp.add_argument("--text", default=None)
    sp.add_argument("--summary", default=None)
    sp.add_argument("--asset-focus", default=None)
    sp.add_argument("--schedule", default="Monitor")
    _add_ignore_lock(sp)

    sp = sub.add_parser("add-hypothesis")
    sp.add_argument("--asset", required=True)
    sp.add_argument("--condition", required=True)
    sp.add_argument("--then", required=True)
    sp.add_argument("--expires-h", default=6)
    sp.add_argument("--schedule", default="Monitor")
    _add_ignore_lock(sp)

    sp = sub.add_parser("update-narrative")
    sp.add_argument("--asset", required=True)
    sp.add_argument("--thread-append", required=True)
    sp.add_argument("--schedule", default="Monitor")
    _add_ignore_lock(sp)

    sp = sub.add_parser("learn-phrase")
    sp.add_argument("--text", required=True)
    sp.add_argument("--schedule", default="Monitor")
    _add_ignore_lock(sp)

    sp = sub.add_parser("refresh-avoid-phrases")
    sp.add_argument("--window-hours", default=4)
    sp.add_argument("--min-occurrences", default=2)
    sp.add_argument("--schedule", default="Monitor")
    _add_ignore_lock(sp)

    sp = sub.add_parser("read")
    sp.add_argument("--max-bytes", default=None)
    sp.add_argument("--asset", default=None)

    sp = sub.add_parser("prune")
    sp.add_argument("--schedule", default="narrative_writer")
    _add_ignore_lock(sp)

    sp = sub.add_parser("reset")
    sp.add_argument("--schedule", default="narrative_writer")
    _add_ignore_lock(sp)

    return p


COMMANDS = {
    "append-cycle": cmd_append_cycle,
    "log-message": cmd_log_message,
    "add-hypothesis": cmd_add_hypothesis,
    "update-narrative": cmd_update_narrative,
    "learn-phrase": cmd_learn_phrase,
    "refresh-avoid-phrases": cmd_refresh_avoid_phrases,
    "read": cmd_read,
    "prune": cmd_prune,
    "reset": cmd_reset,
}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    parser = _build_parser()
    args = parser.parse_args()
    handler = COMMANDS.get(args.command)
    if not handler:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)
    sys.exit(handler(args))


if __name__ == "__main__":
    main()
