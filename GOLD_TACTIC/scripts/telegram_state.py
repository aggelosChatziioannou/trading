#!/usr/bin/env python3
"""
GOLD TACTIC — Telegram State Manager
Tracks what was last sent to Telegram to enable delta-based messaging.
Each message shows ONLY what CHANGED since the previous one.

File: data/last_telegram_state.json

Usage (by the AI Analyst — not run standalone):
  from telegram_state import load_state, save_state, compute_deltas, format_price_delta

The Analyst:
  1. Calls load_state() BEFORE formatting Telegram message
  2. Calls compute_deltas(current, previous) to find what changed
  3. Formats message based on deltas only
  4. Sends message via telegram_sender.py
  5. Calls save_state(current) to update the state file
"""

import json
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

DATA_DIR = Path(__file__).parent.parent / "data"
STATE_FILE = DATA_DIR / "last_telegram_state.json"

# Movement thresholds — below these, we say "stable"
# Same thresholds as quick_scan.py TIER 1 escalation
PRICE_THRESHOLDS = {
    "EURUSD": {"pips": 5, "pip_size": 0.0001, "format": "p"},      # 5 pips
    "GBPUSD": {"pips": 5, "pip_size": 0.0001, "format": "p"},
    "XAUUSD": {"pips": 5, "pip_size": 0.01,   "format": "$"},      # $5
    "NAS100": {"pips": 30, "pip_size": 1.0,    "format": "pts"},    # 30 points
    "BTC":    {"pips": 150, "pip_size": 1.0,   "format": "$"},      # $150
    "SOL":    {"pips": 0.50, "pip_size": 0.01, "format": "$"},      # $0.50
    "ETH":    {"pips": 25, "pip_size": 1.0,    "format": "$"},      # $25
}

# Narrative escalation messages by wait cycle count
WAIT_MESSAGES = {
    (1, 2):  "Anameno {trigger}",
    (3, 4):  "{count}os kyklos — timi {distance} makriya, den kinithe",
    (5, 6):  "{count}os kyklos — arxizei na argei",
    (7, 99): "{count}os kyklos — setup pithano akyronetai an den gini mexri {deadline}",
}


# ══════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_STATE = {
    "last_sent_at": None,
    "last_tier": None,
    "last_prices": {},
    "last_trs": {},
    "last_balance": None,
    "last_daily_pnl": None,
    "last_arcs": {},
    "last_news_headlines": [],
    "last_open_trades": [],
    "last_drawdown_level": "SAFE",
    "messages_sent_today": 0,
    "messages_date": None,
    "tier_counts": {"1": 0, "2": 0, "3a": 0, "3b": 0},
    # Card System tracking
    "last_card_type": None,
    "last_asset_cards_sent": {},   # {asset: "timestamp"}
    "asset_wait_cycles": {},       # {asset: int}
    "last_trade_card_pnl": 0.0,
    "cards_sent_today": 0,
    "expired_assets": [],          # assets that got "expired" card — silence until scanner
}


def load_state():
    """Load last Telegram state from file. Returns default if missing/corrupt."""
    try:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            # Reset daily counters if new day
            today = datetime.now().strftime("%Y-%m-%d")
            if data.get("messages_date") != today:
                data["messages_sent_today"] = 0
                data["messages_date"] = today
                data["tier_counts"] = {"1": 0, "2": 0, "3a": 0, "3b": 0}
            return data
    except (json.JSONDecodeError, Exception):
        pass
    state = DEFAULT_STATE.copy()
    state["messages_date"] = datetime.now().strftime("%Y-%m-%d")
    return state


def save_state(state):
    """Save current state to file after sending Telegram message."""
    state["last_sent_at"] = datetime.now().strftime("%Y-%m-%d %H:%M EET")
    state["messages_sent_today"] = state.get("messages_sent_today", 0) + 1
    state["messages_date"] = datetime.now().strftime("%Y-%m-%d")

    try:
        STATE_FILE.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"WARNING: Could not save telegram state: {e}", file=sys.stderr)


def update_tier_count(state, tier_name):
    """Increment tier counter. tier_name: '1', '2', '3a', '3b'."""
    counts = state.get("tier_counts", {"1": 0, "2": 0, "3a": 0, "3b": 0})
    counts[str(tier_name)] = counts.get(str(tier_name), 0) + 1
    state["tier_counts"] = counts


# ══════════════════════════════════════════════════════════════════════════════
# DELTA COMPUTATION
# ══════════════════════════════════════════════════════════════════════════════

def compute_deltas(current_prices, current_trs, current_arcs,
                   current_balance, current_daily_pnl, current_open_trades,
                   current_drawdown_level, previous_state):
    """
    Compare current data vs previous state.

    Returns dict:
    {
        "price_changes": {asset: {prev, now, delta, delta_formatted, significant}},
        "trs_changes": {asset: {prev, now, changed}},
        "arc_changes": {asset: {prev, now}},
        "balance_changed": bool,
        "balance_delta": float,
        "daily_pnl_changed": bool,
        "trades_changed": bool,
        "new_trades": [...],
        "closed_trades": [...],
        "drawdown_changed": bool,
        "anything_changed": bool,
        "significant_count": int,  # how many assets had significant price moves
        "time_since_last": str,    # "25'" or "1h 30'"
    }
    """
    prev = previous_state or DEFAULT_STATE

    result = {
        "price_changes": {},
        "trs_changes": {},
        "arc_changes": {},
        "balance_changed": False,
        "balance_delta": 0.0,
        "daily_pnl_changed": False,
        "trades_changed": False,
        "new_trades": [],
        "closed_trades": [],
        "drawdown_changed": False,
        "anything_changed": False,
        "significant_count": 0,
        "time_since_last": _time_since(prev.get("last_sent_at")),
    }

    # Price changes
    prev_prices = prev.get("last_prices", {})
    for asset, price in current_prices.items():
        prev_price = prev_prices.get(asset)
        if prev_price is None:
            result["price_changes"][asset] = {
                "prev": None, "now": price, "delta": 0,
                "delta_formatted": "new", "significant": True
            }
            result["significant_count"] += 1
            continue

        delta = price - prev_price
        formatted = format_price_delta(asset, prev_price, price)
        significant = _is_significant_move(asset, delta)

        result["price_changes"][asset] = {
            "prev": prev_price, "now": price, "delta": delta,
            "delta_formatted": formatted, "significant": significant
        }
        if significant:
            result["significant_count"] += 1

    # TRS changes
    prev_trs = prev.get("last_trs", {})
    for asset, trs in current_trs.items():
        prev_t = prev_trs.get(asset)
        changed = prev_t is not None and prev_t != trs
        result["trs_changes"][asset] = {
            "prev": prev_t, "now": trs, "changed": changed
        }
        if changed:
            result["anything_changed"] = True

    # Arc changes
    prev_arcs = prev.get("last_arcs", {})
    for asset, arc in current_arcs.items():
        prev_a = prev_arcs.get(asset)
        if prev_a is not None and prev_a != arc:
            result["arc_changes"][asset] = {"prev": prev_a, "now": arc}
            result["anything_changed"] = True

    # Balance
    prev_balance = prev.get("last_balance")
    if prev_balance is not None and current_balance is not None:
        delta = current_balance - prev_balance
        if abs(delta) >= 0.01:  # More than 1 cent
            result["balance_changed"] = True
            result["balance_delta"] = round(delta, 2)
            result["anything_changed"] = True

    # Daily P&L
    prev_pnl = prev.get("last_daily_pnl")
    if prev_pnl is not None and current_daily_pnl is not None:
        if abs(current_daily_pnl - prev_pnl) >= 0.01:
            result["daily_pnl_changed"] = True
            result["anything_changed"] = True

    # Open trades
    prev_trade_assets = {t.get("asset") for t in prev.get("last_open_trades", [])}
    curr_trade_assets = {t.get("asset") for t in (current_open_trades or [])}
    new_trades = curr_trade_assets - prev_trade_assets
    closed_trades = prev_trade_assets - curr_trade_assets
    if new_trades or closed_trades:
        result["trades_changed"] = True
        result["new_trades"] = list(new_trades)
        result["closed_trades"] = list(closed_trades)
        result["anything_changed"] = True

    # Drawdown
    prev_dd = prev.get("last_drawdown_level", "SAFE")
    if prev_dd != current_drawdown_level:
        result["drawdown_changed"] = True
        result["anything_changed"] = True

    # Overall
    if result["significant_count"] > 0:
        result["anything_changed"] = True

    return result


# ══════════════════════════════════════════════════════════════════════════════
# FORMATTING HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def format_price_delta(asset, prev_price, now_price):
    """
    Format price change in human-readable form.

    Examples: "+3p", "-$120", "+15pts", "stable"
    """
    if prev_price is None or now_price is None:
        return "N/A"

    config = PRICE_THRESHOLDS.get(asset)
    if not config:
        delta = now_price - prev_price
        return f"{delta:+.2f}" if abs(delta) > 0 else "stable"

    pip_size = config["pip_size"]
    fmt = config["format"]
    delta_raw = now_price - prev_price

    if fmt == "p":
        # Forex pips
        pips = delta_raw / pip_size
        if abs(pips) < 1:
            return "stable"
        return f"{pips:+.0f}p"
    elif fmt == "$":
        if abs(delta_raw) < 0.01:
            return "stable"
        return f"{delta_raw:+.0f}$" if abs(delta_raw) >= 1 else f"{delta_raw:+.2f}$"
    elif fmt == "pts":
        if abs(delta_raw) < 1:
            return "stable"
        return f"{delta_raw:+.0f}pts"

    return f"{delta_raw:+.4f}"


def _is_significant_move(asset, delta):
    """Check if price moved more than the threshold for this asset."""
    config = PRICE_THRESHOLDS.get(asset)
    if not config:
        return abs(delta) > 0

    pip_size = config["pip_size"]
    threshold_pips = config["pips"]
    delta_in_pips = abs(delta) / pip_size if pip_size > 0 else 0

    return delta_in_pips >= threshold_pips


def _time_since(last_sent_str):
    """Calculate human-readable time since last message."""
    if not last_sent_str:
        return "first msg"

    try:
        # Parse "2026-04-04 14:30 EET" format
        dt_str = last_sent_str.replace(" EET", "").strip()
        last_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        diff = datetime.now() - last_dt
        minutes = int(diff.total_seconds() / 60)

        if minutes < 1:
            return "just now"
        elif minutes < 60:
            return f"{minutes}'"
        else:
            hours = minutes // 60
            remaining_mins = minutes % 60
            if remaining_mins > 0:
                return f"{hours}h {remaining_mins}'"
            return f"{hours}h"
    except (ValueError, TypeError):
        return "?"


def should_show_asset(asset, deltas):
    """
    Decide if an asset deserves mention in the message.

    Show if:
    - Price moved significantly
    - TRS changed
    - Arc changed
    - Has an open trade

    Don't show if nothing changed.
    """
    price_info = deltas.get("price_changes", {}).get(asset, {})
    trs_info = deltas.get("trs_changes", {}).get(asset, {})
    arc_changed = asset in deltas.get("arc_changes", {})

    if price_info.get("significant"):
        return True
    if trs_info.get("changed"):
        return True
    if arc_changed:
        return True
    if asset in deltas.get("new_trades", []):
        return True

    return False


def get_wait_cycle_message(wait_cycles, expected_trigger, distance_info=""):
    """
    Return escalating wait message based on cycle count.

    Avoids repeating "Waiting for BOS" 10 times in a row.
    Instead: gradually escalates urgency. Messages in proper Greek.
    """
    count = wait_cycles or 0

    if count <= 2:
        return f"\u0391\u03bd\u03b1\u03bc\u03ad\u03bd\u03c9 {expected_trigger}"
    elif count <= 4:
        dist = f", \u03c4\u03b9\u03bc\u03ae {distance_info} \u03bc\u03b1\u03ba\u03c1\u03b9\u03ac" if distance_info else ""
        return f"{count}\u03bf\u03c2 \u03ba\u03cd\u03ba\u03bb\u03bf\u03c2 \u2014 \u03b1\u03b3\u03bf\u03c1\u03ac \u03b4\u03b5\u03bd \u03ad\u03b4\u03c9\u03c3\u03b5 {expected_trigger}{dist}"
    elif count <= 6:
        return f"\u26a0\ufe0f {count}\u03bf\u03c2 \u03ba\u03cd\u03ba\u03bb\u03bf\u03c2 \u2014 \u03b1\u03c1\u03c7\u03af\u03b6\u03b5\u03b9 \u03bd\u03b1 \u03b1\u03c1\u03b3\u03b5\u03af \u03c4\u03bf {expected_trigger}"
    else:
        return f"\u274c {count}\u03bf\u03c2 \u03ba\u03cd\u03ba\u03bb\u03bf\u03c2 \u2014 setup \u03c0\u03b9\u03b8\u03b1\u03bd\u03ac \u03b1\u03ba\u03c5\u03c1\u03ce\u03bd\u03b5\u03c4\u03b1\u03b9"


# ══════════════════════════════════════════════════════════════════════════════
# CARD SYSTEM HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def should_send_asset_card(asset, deltas, state):
    """
    Decide if an asset deserves its own Asset Card.

    YES if: TRS changed, significant price move, arc changed, has open trade
    NO if: expired asset, nothing changed
    """
    # Expired = silence
    if asset in state.get("expired_assets", []):
        return False

    price_info = deltas.get("price_changes", {}).get(asset, {})
    trs_info = deltas.get("trs_changes", {}).get(asset, {})
    arc_changed = asset in deltas.get("arc_changes", {})

    if trs_info.get("changed"):
        return True
    if price_info.get("significant"):
        return True
    if arc_changed:
        return True
    if asset in deltas.get("new_trades", []):
        return True

    return False


def increment_wait_cycle(state, asset):
    """Increment wait cycle counter for an asset."""
    cycles = state.get("asset_wait_cycles", {})
    cycles[asset] = cycles.get(asset, 0) + 1
    state["asset_wait_cycles"] = cycles
    return cycles[asset]


def reset_wait_cycle(state, asset):
    """Reset wait cycle when asset arc changes or trade opens."""
    cycles = state.get("asset_wait_cycles", {})
    cycles[asset] = 0
    state["asset_wait_cycles"] = cycles


def reset_expired_assets(state):
    """Clear expired list. Called by scanner to give assets a fresh chance."""
    state["expired_assets"] = []


def mark_asset_expired(state, asset):
    """Mark asset as expired. One final card, then silence."""
    expired = state.get("expired_assets", [])
    if asset not in expired:
        expired.append(asset)
    state["expired_assets"] = expired


def get_proximity_summary(trs_scores):
    """
    Generate 1-line proximity summary for Status Card.

    Example: "EURUSD (TRS 4/5 — ~30')" or "κανένα"
    """
    near_trade = []
    for asset, data in trs_scores.items():
        score = data.get("trs_score", 0)
        if score >= 3:
            time_est = data.get("estimated_time", "")
            if score >= 4:
                near_trade.append(f"{asset} (TRS {score}/5 — {time_est})")
            elif score == 3:
                near_trade.append(f"{asset} ({score}/5)")

    if not near_trade:
        return "κανένα"
    return ", ".join(near_trade[:3])  # Max 3 assets in summary


# ══════════════════════════════════════════════════════════════════════════════
# CLI (for testing)
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """Show current state and simulate delta computation."""
    import json

    state = load_state()
    print("Current Telegram State:")
    print(json.dumps(state, indent=2, ensure_ascii=False))
    print()

    # Simulate deltas
    current_prices = {"EURUSD": 1.0848, "BTC": 66820, "NAS100": 19465}
    current_trs = {"EURUSD": 3, "BTC": 2}
    current_arcs = {"EURUSD": "WAITING", "BTC": "WAITING"}

    deltas = compute_deltas(
        current_prices=current_prices,
        current_trs=current_trs,
        current_arcs=current_arcs,
        current_balance=998.80,
        current_daily_pnl=0.0,
        current_open_trades=[],
        current_drawdown_level="SAFE",
        previous_state=state,
    )

    print("Deltas vs last state:")
    print(f"  Anything changed: {deltas['anything_changed']}")
    print(f"  Significant moves: {deltas['significant_count']}")
    print(f"  Time since last: {deltas['time_since_last']}")
    print()

    for asset, info in deltas["price_changes"].items():
        show = should_show_asset(asset, deltas)
        print(f"  {asset}: {info['delta_formatted']} {'SHOW' if show else 'skip'}")

    # Test wait cycle messages
    print()
    print("Wait cycle messages:")
    for i in [1, 3, 5, 8]:
        msg = get_wait_cycle_message(i, "BOS sto 1.0823", "12 pips")
        print(f"  Cycle {i}: {msg}")


if __name__ == "__main__":
    main()
