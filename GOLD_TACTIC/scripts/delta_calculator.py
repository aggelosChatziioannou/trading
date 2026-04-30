#!/usr/bin/env python3
"""GOLD TACTIC — Delta Calculator (B2 improvement, 30/04/2026)

Computes "what changed since last cycle" deterministically so the Monitor LLM
doesn't have to derive deltas from briefing_log alone (which is error-prone).

Snapshots `trs_current.json` + `live_prices.json` per cycle into
`data/delta_state.jsonl` (append-only). Compares latest vs previous snapshot
and writes plain-Greek delta description to `data/delta_since_last_cycle.json`.

L2 WATCH template reads this for the 📖 continuity narrative — no need to
reverse-engineer changes from text logs.

Usage:
  python delta_calculator.py snapshot   # take snapshot + compute delta
  python delta_calculator.py --json     # print latest delta JSON
  python delta_calculator.py --line     # 1-line summary
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

EET = timezone(timedelta(hours=3))
ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
SNAPSHOTS = DATA / "delta_state.jsonl"
DELTA_OUT = DATA / "delta_since_last_cycle.json"

# Plain-Greek labels for the 5 criteria — matches L2 WATCH template
CRITERION_LABELS = {
    "TF": "τάση",
    "RSI": "ορμή RSI",
    "ADR": "εύρος ADR",
    "News": "νέα",
    "Key": "επίπεδο τιμής",
}


def _now():
    return datetime.now(EET)


def _read_json(name, default=None):
    p = DATA / name
    if not p.exists():
        return default if default is not None else {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def take_snapshot():
    """Capture current state of TRS + prices into delta_state.jsonl."""
    trs = _read_json("trs_current.json")
    prices_raw = _read_json("live_prices.json")
    prices = prices_raw.get("prices", {})

    snapshot = {
        "ts": _now().isoformat(timespec="seconds"),
        "trs_assets": trs.get("assets", {}),
        "prices": {sym: info.get("price") for sym, info in prices.items() if isinstance(info, dict)},
    }
    SNAPSHOTS.parent.mkdir(parents=True, exist_ok=True)
    with open(SNAPSHOTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
    return snapshot


def _read_last_two_snapshots():
    """Return (previous, current) snapshots from the JSONL file. Either may be None."""
    if not SNAPSHOTS.exists():
        return None, None
    lines = SNAPSHOTS.read_text(encoding="utf-8").strip().split("\n")
    if not lines or lines == [""]:
        return None, None
    snapshots = []
    for line in lines[-2:]:
        try:
            snapshots.append(json.loads(line))
        except Exception:
            continue
    if len(snapshots) == 0:
        return None, None
    if len(snapshots) == 1:
        return None, snapshots[0]
    return snapshots[0], snapshots[1]


def _fmt_pct(prev, now):
    if prev in (None, 0) or now is None:
        return None
    try:
        return round((now - prev) / abs(prev) * 100, 2)
    except Exception:
        return None


def _format_price(sym, val):
    if val is None:
        return "—"
    if sym in ("EURUSD", "GBPUSD", "AUDUSD", "XRP"):
        return f"{val:.4f}"
    if sym in ("USDJPY", "DXY"):
        return f"{val:.2f}"
    if sym == "BTC":
        return f"${val:,.0f}"
    if sym == "NAS100":
        return f"{val:,.2f}"
    if sym == "SPX500":
        return f"{val:,.2f}"
    if sym == "XAUUSD":
        return f"{val:,.2f}"
    return f"${val:.2f}"


def compute_delta():
    """Compare last two snapshots, build per-asset delta + plain-Greek summary."""
    prev, cur = _read_last_two_snapshots()
    out = {
        "computed_at": _now().isoformat(timespec="seconds"),
        "prev_ts": (prev or {}).get("ts"),
        "cur_ts": (cur or {}).get("ts"),
        "elapsed_minutes": None,
        "per_asset": {},
        "summary_line": "",
        "any_change": False,
        "stable_streak": False,
    }
    if not cur:
        out["summary_line"] = "Δεν υπάρχει snapshot ακόμα."
        return out
    if not prev:
        out["summary_line"] = "Πρώτος cycle — δεν υπάρχει προηγούμενο snapshot για σύγκριση."
        out["per_asset"] = {
            sym: {"first_seen": True, "price_now": cur["prices"].get(sym),
                  "trs_now": (cur["trs_assets"].get(sym) or {}).get("trs")}
            for sym in cur.get("prices", {})
        }
        return out

    # Elapsed time between snapshots
    try:
        prev_dt = datetime.fromisoformat(prev["ts"])
        cur_dt = datetime.fromisoformat(cur["ts"])
        out["elapsed_minutes"] = round((cur_dt - prev_dt).total_seconds() / 60, 1)
    except Exception:
        pass

    # Per-asset diff
    all_syms = set(cur.get("prices", {}).keys()) | set(prev.get("prices", {}).keys())
    movers = []  # for summary line
    for sym in sorted(all_syms):
        prev_price = prev.get("prices", {}).get(sym)
        cur_price = cur.get("prices", {}).get(sym)
        prev_trs_data = prev.get("trs_assets", {}).get(sym, {}) or {}
        cur_trs_data = cur.get("trs_assets", {}).get(sym, {}) or {}

        prev_trs = prev_trs_data.get("trs")
        cur_trs = cur_trs_data.get("trs")
        prev_crit = prev_trs_data.get("criteria", {}) or {}
        cur_crit = cur_trs_data.get("criteria", {}) or {}

        delta_pct = _fmt_pct(prev_price, cur_price)

        # Criteria flips: only report if a criterion CHANGED truth value
        flips_now_true = []
        flips_now_false = []
        for k in ("TF", "RSI", "ADR", "News", "Key"):
            p = prev_crit.get(k)
            c = cur_crit.get(k)
            if p is None or c is None:
                continue
            if p != c:
                label = CRITERION_LABELS.get(k, k)
                if c is True and p is False:
                    flips_now_true.append(label)
                elif c is False and p is True:
                    flips_now_false.append(label)

        # TRS bucket flip
        trs_change = None
        if prev_trs is not None and cur_trs is not None and prev_trs != cur_trs:
            trs_change = f"{prev_trs}→{cur_trs}"

        any_change = bool(
            (delta_pct is not None and abs(delta_pct) >= 0.1) or
            trs_change or flips_now_true or flips_now_false
        )

        out["per_asset"][sym] = {
            "price_prev": prev_price,
            "price_now": cur_price,
            "price_prev_fmt": _format_price(sym, prev_price),
            "price_now_fmt": _format_price(sym, cur_price),
            "delta_pct": delta_pct,
            "trs_prev": prev_trs,
            "trs_now": cur_trs,
            "trs_change": trs_change,
            "criteria_now_true": flips_now_true,
            "criteria_now_false": flips_now_false,
            "any_change": any_change,
        }
        if any_change and delta_pct is not None:
            sign = "+" if delta_pct > 0 else ""
            movers.append(f"{sym} {sign}{delta_pct}%")

    out["any_change"] = any(d["any_change"] for d in out["per_asset"].values())

    # Stable streak detection (3+ consecutive cycles with no change)
    if not out["any_change"]:
        out["stable_streak"] = True

    # Build a 1-line summary in plain Greek
    if not out["any_change"]:
        out["summary_line"] = "Καμία ουσιαστική αλλαγή σε τιμές, TRS, ή κριτήρια από τον προηγούμενο cycle."
    else:
        parts = []
        if movers:
            parts.append(", ".join(movers[:3]))
        # Mention the most significant TRS change if any
        for sym, d in out["per_asset"].items():
            if d.get("trs_change"):
                parts.append(f"{sym} TRS {d['trs_change']}")
                break
        # Mention any criterion flips on top mover
        if out["per_asset"]:
            top_mover_sym = max(
                out["per_asset"].keys(),
                key=lambda s: abs(out["per_asset"][s]["delta_pct"] or 0),
            )
            top_mover = out["per_asset"][top_mover_sym]
            if top_mover["criteria_now_true"]:
                parts.append(f"{top_mover_sym} πέρασε: {', '.join(top_mover['criteria_now_true'])}")
            if top_mover["criteria_now_false"]:
                parts.append(f"{top_mover_sym} έχασε: {', '.join(top_mover['criteria_now_false'])}")
        out["summary_line"] = " · ".join(parts) if parts else "Μικρές κινήσεις χωρίς αλλαγή κριτηρίων."

    return out


def main():
    args = sys.argv[1:]
    if "snapshot" in args or not args:
        # Default behavior: take snapshot first, then compute delta
        take_snapshot()

    delta = compute_delta()
    DELTA_OUT.write_text(
        json.dumps(delta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if "--json" in args:
        print(json.dumps(delta, ensure_ascii=False, indent=2))
    elif "--line" in args:
        print(delta.get("summary_line", "—"))
    else:
        # Human-readable
        elapsed = delta.get("elapsed_minutes")
        elapsed_str = f"({elapsed}min ago)" if elapsed is not None else ""
        print(f"=== Delta since last cycle {elapsed_str} ===")
        print(f"Summary: {delta.get('summary_line')}")
        print()
        for sym, d in delta.get("per_asset", {}).items():
            mark = "★" if d.get("any_change") else " "
            line = f"  {mark} {sym:8s}"
            if d.get("price_prev") is not None and d.get("price_now") is not None:
                line += f"  {d['price_prev_fmt']} → {d['price_now_fmt']}"
                if d.get("delta_pct") is not None:
                    sign = "+" if d["delta_pct"] > 0 else ""
                    line += f"  ({sign}{d['delta_pct']}%)"
            if d.get("trs_change"):
                line += f"  TRS {d['trs_change']}"
            if d.get("criteria_now_true"):
                line += f"  ✓+{','.join(d['criteria_now_true'])}"
            if d.get("criteria_now_false"):
                line += f"  ✓-{','.join(d['criteria_now_false'])}"
            print(line)
        print()
        print(f"Saved to: {DELTA_OUT.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    main()
