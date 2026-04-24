#!/usr/bin/env python3
"""
news_impact.py — News Event Impact Tracker

Modes:
  --pre  "EVENT_NAME"  : Record price before event (run ~30min before)
  --post "EVENT_NAME"  : Record price after event, calculate impact, save
  --report             : Print stats per event type (requires 10+ entries)

Data saved to: GOLD_TACTIC/data/event_impact_log.jsonl
"""

import json
import sys
import os
import argparse
from datetime import datetime, date
from pathlib import Path

# Windows UTF-8 console fix
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "GOLD_TACTIC" / "data"
PRICES_FILE = DATA_DIR / "live_prices.json"
CALENDAR_FILE = DATA_DIR / "economic_calendar.json"
IMPACT_LOG = DATA_DIR / "event_impact_log.jsonl"
PRE_SNAPSHOT = DATA_DIR / "event_pre_snapshot.json"


# ── Tracked assets for news impact analysis ────────────────────────────────────
TRACKED_ASSETS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTC", "ETH"]

# pip/point values per 0.01 lot
PIP_VALUES = {
    "XAUUSD": 10.0,
    "EURUSD": 10.0,
    "GBPUSD": 10.0,
    "USDJPY": 10.0,
    "BTC":    1.0,
    "ETH":    0.1,
}


def load_json(path: Path) -> dict | list | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_current_prices() -> dict:
    """Read current prices from live_prices.json.
    Handles both list format and dict-of-dicts under 'prices' key.
    """
    data = load_json(PRICES_FILE)
    if not data:
        print("WARNING: live_prices.json not found - run price_checker.py first")
        return {}

    prices = {}

    # Format: {"prices": {"XAUUSD": {"price": 3245.0, ...}, ...}}
    if isinstance(data, dict) and "prices" in data:
        for sym, info in data["prices"].items():
            price = info.get("price") or info.get("last")
            if price:
                prices[sym] = float(price)

    # Format: [{"symbol": "XAUUSD", "price": 3245.0}, ...]
    elif isinstance(data, list):
        for item in data:
            sym = item.get("symbol", "")
            price = item.get("price") or item.get("last")
            if sym and price:
                prices[sym] = float(price)

    # Format: {"assets": [...]}
    elif isinstance(data, dict) and "assets" in data:
        for item in data["assets"]:
            sym = item.get("symbol", "")
            price = item.get("price") or item.get("last")
            if sym and price:
                prices[sym] = float(price)

    return prices


def classify_move(pct: float) -> str:
    """Classify magnitude of price move."""
    a = abs(pct)
    if a < 0.1:
        return "MINIMAL"
    elif a < 0.3:
        return "SMALL"
    elif a < 0.7:
        return "MEDIUM"
    elif a < 1.5:
        return "LARGE"
    else:
        return "EXTREME"


# ── --pre mode ─────────────────────────────────────────────────────────────────
def cmd_pre(event_name: str) -> None:
    prices = get_current_prices()
    if not prices:
        sys.exit(1)

    snapshot = {
        "event": event_name,
        "date": date.today().isoformat(),
        "timestamp_pre": datetime.now().isoformat(),
        "prices_pre": {sym: prices[sym] for sym in TRACKED_ASSETS if sym in prices},
    }

    save_json(PRE_SNAPSHOT, snapshot)
    print(f"✅ Pre-snapshot saved for '{event_name}'")
    print(f"   Assets captured: {', '.join(snapshot['prices_pre'].keys())}")
    print(f"   Time: {snapshot['timestamp_pre'][:16]}")


# ── --post mode ────────────────────────────────────────────────────────────────
def cmd_post(event_name: str) -> None:
    pre = load_json(PRE_SNAPSHOT)
    if not pre:
        print(f"⚠️  No pre-snapshot found — run --pre '{event_name}' first")
        sys.exit(1)

    if pre.get("event") != event_name:
        print(f"⚠️  Pre-snapshot is for '{pre.get('event')}', not '{event_name}'")
        print("   Continuing anyway with mismatched event name...")

    prices_post = get_current_prices()
    if not prices_post:
        sys.exit(1)

    prices_pre = pre.get("prices_pre", {})
    asset_results = {}
    dominant_direction = "NEUTRAL"
    max_abs_pct = 0.0

    for sym in TRACKED_ASSETS:
        if sym not in prices_pre or sym not in prices_post:
            continue
        p_pre = prices_pre[sym]
        p_post = prices_post[sym]
        move = p_post - p_pre
        pct = (move / p_pre) * 100

        result = {"pre": p_pre, "post": p_post, "move": round(move, 5), "pct": round(pct, 3)}

        # pips for forex (not crypto)
        if sym in ("EURUSD", "GBPUSD", "USDJPY", "XAUUSD"):
            result["pips"] = round(abs(move) / 0.0001, 1) if sym != "XAUUSD" else round(abs(move), 1)

        asset_results[sym] = result

        if abs(pct) > max_abs_pct:
            max_abs_pct = abs(pct)
            dominant_direction = "BULLISH" if pct > 0 else "BEARISH"

    magnitude = classify_move(max_abs_pct)

    record = {
        "event": event_name,
        "date": pre.get("date", date.today().isoformat()),
        "timestamp_pre": pre.get("timestamp_pre"),
        "timestamp_post": datetime.now().isoformat(),
        "assets": asset_results,
        "direction": dominant_direction,
        "magnitude": magnitude,
    }

    append_jsonl(IMPACT_LOG, record)

    # Clean up pre-snapshot
    try:
        PRE_SNAPSHOT.unlink()
    except Exception:
        pass

    print(f"✅ Post-analysis saved for '{event_name}'")
    print(f"   Direction: {dominant_direction} | Magnitude: {magnitude}")
    print(f"   Moves:")
    for sym, r in asset_results.items():
        sign = "+" if r["move"] >= 0 else ""
        print(f"     {sym}: {sign}{r['pct']}%  ({sign}{r['move']})")


# ── --report mode ──────────────────────────────────────────────────────────────
def cmd_report() -> None:
    if not IMPACT_LOG.exists():
        print("No event impact data yet. Run --pre / --post after events.")
        return

    records = []
    with open(IMPACT_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass

    if not records:
        print("Event log is empty.")
        return

    print(f"\n📊 NEWS IMPACT REPORT — {len(records)} events logged\n")
    print("=" * 60)

    # Group by event type
    by_event: dict[str, list] = {}
    for r in records:
        evt = r.get("event", "UNKNOWN")
        by_event.setdefault(evt, []).append(r)

    for evt, evts in sorted(by_event.items(), key=lambda x: -len(x[1])):
        n = len(evts)
        print(f"\n🔔 {evt}  ({n} occurrence{'s' if n > 1 else ''})")

        # Direction stats
        bull = sum(1 for e in evts if e.get("direction") == "BULLISH")
        bear = sum(1 for e in evts if e.get("direction") == "BEARISH")
        neu  = n - bull - bear
        print(f"   Direction: {bull}× BULLISH | {bear}× BEARISH | {neu}× NEUTRAL")

        # Magnitude distribution
        mags = [e.get("magnitude", "?") for e in evts]
        mag_counts: dict[str, int] = {}
        for m in mags:
            mag_counts[m] = mag_counts.get(m, 0) + 1
        mag_str = " | ".join(f"{v}× {k}" for k, v in mag_counts.items())
        print(f"   Magnitude: {mag_str}")

        # Per-asset average move
        asset_moves: dict[str, list] = {}
        for e in evts:
            for sym, a in e.get("assets", {}).items():
                asset_moves.setdefault(sym, []).append(a.get("pct", 0))

        if asset_moves:
            print("   Avg % move:")
            for sym in sorted(asset_moves):
                vals = asset_moves[sym]
                avg = sum(vals) / len(vals)
                sign = "+" if avg >= 0 else ""
                print(f"     {sym}: {sign}{avg:.2f}% (n={len(vals)})")

    if len(records) < 10:
        remaining = 10 - len(records)
        print(f"\n⏳ {remaining} more event{'s' if remaining > 1 else ''} needed for reliable patterns.")

    print()


# ── CLI ────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Track price impact of high-impact economic events"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pre",    metavar="EVENT", help="Record pre-event prices")
    group.add_argument("--post",   metavar="EVENT", help="Record post-event prices & calculate impact")
    group.add_argument("--report", action="store_true", help="Print stats per event type")

    args = parser.parse_args()

    if args.pre:
        cmd_pre(args.pre)
    elif args.post:
        cmd_post(args.post)
    elif args.report:
        cmd_report()


if __name__ == "__main__":
    main()
