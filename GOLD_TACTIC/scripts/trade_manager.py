#!/usr/bin/env python3
"""
GOLD TACTIC — Trade Manager (v7.2 Phase A)

Lifecycle core for paper trades. Dual-purpose: library + CLI.

Flow:
  1. Monitor emits Tier C signal → calls `trade_manager.py open ...`
  2. Manager writes trade to trade_state.json + portfolio.open_trades[]
  3. Sends 📥 Telegram reply to entry message
  4. Every Monitor cycle calls `trade_manager.py tick`
  5. Tick reads live_prices.json, computes P/L, fires milestones
     (25/50/75% toward TP1 → ⏱️ reply, TP1 hit → 🎯 reply + close,
      SL hit → 💀 reply + close, 4h timeout → ⌛ reply + close)
  6. On close: updates portfolio daily_pnl/wins/losses + appends to
     trade_journal.jsonl

CLI:
  python trade_manager.py open XAUUSD LONG 3245.20 3238.50 3260 3275 \\
      --entry-msg-id 734 --trs 5 --context "London KZ, RSI cooled"
  python trade_manager.py tick
  python trade_manager.py list
  python trade_manager.py close <trade_id> [reason] [exit_price]
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

SCRIPTS = Path(__file__).parent
DATA = SCRIPTS.parent / "data"
PORTFOLIO_FILE = DATA / "portfolio.json"
TRADE_STATE_FILE = DATA / "trade_state.json"
TRADE_JOURNAL_FILE = DATA / "trade_journal.jsonl"
LIVE_PRICES_FILE = DATA / "live_prices.json"
CORRELATION_MAP_FILE = DATA / "correlation_map.json"

sys.path.insert(0, str(SCRIPTS))
try:
    from risk_manager import ASSET_CONFIG, calculate_position_size, suggest_tp_sl
except Exception:
    ASSET_CONFIG = {}
    calculate_position_size = None
    suggest_tp_sl = None

TELEGRAM_SENDER = SCRIPTS / "telegram_sender.py"
EET = timezone(timedelta(hours=3))


# ---------- JSON helpers ----------

def _load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def _atomic_write(path, data):
    """Write JSON atomically via tmp + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, path)


def _append_jsonl(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _now_eet():
    return datetime.now(EET)


def _iso(dt):
    return dt.isoformat(timespec='seconds')


# ---------- Telegram reply wrapper ----------

def _tg_reply(text, reply_to=None, silent=False):
    """Spawn telegram_sender.py to send a message. Returns message_id or None."""
    if not TELEGRAM_SENDER.exists():
        return None
    cmd = [sys.executable, str(TELEGRAM_SENDER), "message", text]
    if reply_to is not None:
        cmd += ["--reply-to", str(reply_to)]
    if silent:
        cmd += ["--silent"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=30)
        if result.returncode == 0:
            out = (result.stdout or "").strip()
            try:
                return int(out.splitlines()[-1]) if out else None
            except Exception:
                return None
    except Exception:
        pass
    return None


# ---------- P/L + progress math ----------

def _pip_size(symbol):
    return (ASSET_CONFIG.get(symbol) or {}).get("pip_size", 0.0001)


def _pip_value(symbol):
    return (ASSET_CONFIG.get(symbol) or {}).get("pip_value_per_lot", 10.0)


def _compute_pnl_eur(trade, price):
    """Unrealized P/L in EUR for trade at current price."""
    symbol = trade["symbol"]
    direction = trade["direction"]
    lot = trade["lot"]
    entry = trade["entry"]
    pip_size = _pip_size(symbol)
    pip_value = _pip_value(symbol)
    if direction == "LONG":
        pips = (price - entry) / pip_size
    else:
        pips = (entry - price) / pip_size
    return round(pips * pip_value * lot, 2)


def _progress_pct(trade, price):
    """% of distance covered entry → TP1 (0-100+, can be negative if reversed)."""
    entry = trade["entry"]
    tp1 = trade["tp1"]
    span = tp1 - entry
    if span == 0:
        return 0.0
    progressed = price - entry
    if trade["direction"] == "SHORT":
        progressed = -progressed
        span = -span
    return round((progressed / span) * 100.0, 1)


def _sl_hit(trade, price):
    if trade["direction"] == "LONG":
        return price <= trade["sl"]
    return price >= trade["sl"]


def _tp1_hit(trade, price):
    if trade["direction"] == "LONG":
        return price >= trade["tp1"]
    return price <= trade["tp1"]


def _tp2_hit(trade, price):
    if trade["direction"] == "LONG":
        return price >= trade["tp2"]
    return price <= trade["tp2"]


def _fmt_pnl(pnl):
    return f"{pnl:+.2f}€"


# ---------- correlation check (stub, populated by Phase B2) ----------

def _correlation_block(symbol, direction, open_trades):
    """Return (blocked: bool, cluster: str|None, count: int, max: int)."""
    cmap = _load_json(CORRELATION_MAP_FILE, None)
    if not cmap or not isinstance(cmap, dict):
        return False, None, 0, 0
    clusters = cmap.get("clusters", {})
    max_per = int(cmap.get("max_per_cluster", 2))
    key = f"{symbol}_{direction}"
    for cluster_name, members in clusters.items():
        if key in members:
            count = sum(
                1 for t in open_trades
                if f"{t.get('symbol')}_{t.get('direction')}" in members
            )
            if count >= max_per:
                return True, cluster_name, count, max_per
    return False, None, 0, 0


# ---------- portfolio + state sync ----------

def _load_portfolio():
    return _load_json(PORTFOLIO_FILE, {})


def _save_portfolio(p):
    p["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S EET")
    _atomic_write(PORTFOLIO_FILE, p)


def _load_state():
    return _load_json(TRADE_STATE_FILE, {"open_trades": [], "last_tick": None})


def _save_state(state):
    state["last_tick"] = _iso(_now_eet())
    _atomic_write(TRADE_STATE_FILE, state)


def _load_live_prices():
    doc = _load_json(LIVE_PRICES_FILE, {}) or {}
    out = {}
    for sym, info in (doc.get("prices") or {}).items():
        if isinstance(info, dict) and info.get("price") is not None:
            try:
                out[sym] = float(info["price"])
            except Exception:
                continue
    return out


# ---------- public API: open_trade ----------

def open_trade(symbol, direction, entry, sl, tp1, tp2,
               lot=None, entry_msg_id=None, trs=None, context="", tag="full",
               auto_launch=False):
    """
    Open a new paper trade. Returns (trade_dict, error_str_or_None).
    If lot is None, calculates from portfolio risk_per_trade_pct.

    tag: "full" (default, 2% risk) | "probe" (TRS=4, 1% risk)
         | "confirm" (TRS=5 upgrade on active probe, +1% → total 2%)
    """
    symbol = symbol.upper()
    direction = direction.upper()
    tag = (tag or "full").lower()
    if tag not in ("full", "probe", "confirm"):
        return None, f"tag must be full|probe|confirm (got {tag})"
    if direction not in ("LONG", "SHORT"):
        return None, f"Direction must be LONG or SHORT (got {direction})"
    entry = float(entry); sl = float(sl); tp1 = float(tp1); tp2 = float(tp2)

    portfolio = _load_portfolio()
    state = _load_state()

    # Gate: daily stop
    daily_pnl = float(portfolio.get("daily_pnl", 0) or 0)
    max_daily_loss = abs(float(portfolio.get("max_daily_loss_eur", 40)))
    if daily_pnl <= -max_daily_loss:
        return None, f"Daily stop hit ({daily_pnl:+.2f}€ ≤ -{max_daily_loss}€)"

    # Gate: max concurrent (confirm on same symbol as active probe does NOT count)
    max_concurrent = int(portfolio.get("max_concurrent_trades", 2))
    has_probe_on_symbol = any(
        t for t in state.get("open_trades", [])
        if t["symbol"] == symbol and t["direction"] == direction
        and (t.get("tag") or "full") == "probe"
    )
    concurrent_count = len(state.get("open_trades", []))
    if tag == "confirm" and has_probe_on_symbol:
        # Scale-in upgrade — does not consume a new slot
        pass
    elif concurrent_count >= max_concurrent:
        return None, f"Max concurrent trades reached ({concurrent_count}/{max_concurrent})"

    # Gate: duplicate symbol — allow confirm after probe (same direction)
    for t in state.get("open_trades", []):
        if t["symbol"] == symbol and t["direction"] == direction:
            existing_tag = t.get("tag") or "full"
            if existing_tag == "probe" and tag == "confirm":
                continue  # explicit scale-in upgrade
            return None, f"Already open trade on {symbol} {direction} (tag={existing_tag})"
        elif t["symbol"] == symbol:
            return None, f"Already open trade on {symbol} (opposite direction)"

    # Gate: correlation
    blocked, cluster, count, mx = _correlation_block(symbol, direction, state.get("open_trades", []))
    if blocked:
        return None, f"Correlation block: {count}/{mx} in cluster {cluster}"

    # Position sizing (probe/confirm each use half risk → combined = full 2%)
    risk_divider = 2.0 if tag in ("probe", "confirm") else 1.0
    if lot is None:
        if calculate_position_size is None or symbol not in ASSET_CONFIG:
            return None, f"Cannot auto-size lot for {symbol} (no ASSET_CONFIG / risk_manager)"
        sizing, err = calculate_position_size(portfolio, symbol, entry, sl)
        if err:
            return None, f"Sizing error: {err}"
        lot = round(sizing["lot_size"] / risk_divider, 2)
        risk_eur = round(sizing["actual_risk_eur"] / risk_divider, 2)
    else:
        lot = float(lot)
        pip_size = _pip_size(symbol)
        pip_value = _pip_value(symbol)
        sl_pips = abs(entry - sl) / pip_size if pip_size else 0
        risk_eur = round(sl_pips * pip_value * lot, 2)

    # Risk guard: reject if lot exceeds allowed risk per trade
    # (probe/confirm each get half the max; full gets the whole max)
    balance = float(portfolio.get("current_balance", 0) or 0)
    risk_pct = float(portfolio.get("risk_per_trade_pct", 2.0))
    max_risk_eur = round(balance * risk_pct / 100.0 / risk_divider, 2)
    if max_risk_eur > 0 and risk_eur > max_risk_eur * 1.1:  # 10% tolerance
        return None, (
            f"Lot {lot} exceeds {tag} max risk: €{risk_eur} > €{max_risk_eur} "
            f"(tag={tag}, base {risk_pct}% of €{balance}). Reduce lot or widen SL."
        )

    # Planned rewards
    pip_size = _pip_size(symbol)
    pip_value = _pip_value(symbol)
    tp1_pips = abs(tp1 - entry) / pip_size if pip_size else 0
    tp2_pips = abs(tp2 - entry) / pip_size if pip_size else 0
    reward_tp1 = round(tp1_pips * pip_value * lot, 2)
    reward_tp2 = round(tp2_pips * pip_value * lot, 2)

    now = _now_eet()
    max_hold_hours = int(portfolio.get("max_hold_hours", 4))
    expires = now + timedelta(hours=max_hold_hours)

    trade_id = f"{symbol}_{tag}_{now.strftime('%Y%m%dT%H%M%S')}"
    trade = {
        "trade_id": trade_id,
        "symbol": symbol,
        "direction": direction,
        "entry": entry,
        "entry_time": _iso(now),
        "sl": sl,
        "sl_original": sl,
        "tp1": tp1,
        "tp2": tp2,
        "lot": lot,
        "risk_eur": risk_eur,
        "tag": tag,
        "planned_reward_tp1_eur": reward_tp1,
        "planned_reward_tp2_eur": reward_tp2,
        "trs_at_entry": trs,
        "entry_msg_id": entry_msg_id,
        "context": context,
        "progress_milestones_fired": {"25": False, "50": False, "75": False},
        "tp1_hit": False,
        "be_moved": False,
        "max_hold_expires": _iso(expires),
        "auto_launch": bool(auto_launch),
        "launched": False,
    }

    # Update state + portfolio
    state.setdefault("open_trades", []).append(trade)
    _save_state(state)

    portfolio.setdefault("open_trades", []).append({
        "trade_id": trade_id,
        "symbol": symbol,
        "direction": direction,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "lot": lot,
        "risk_eur": risk_eur,
        "entry_time": trade["entry_time"],
    })
    portfolio["trades_today"] = int(portfolio.get("trades_today", 0)) + 1
    portfolio["total_trades"] = int(portfolio.get("total_trades", 0)) + 1
    _save_portfolio(portfolio)

    # Telegram 📥 reply — header differs per tag
    arrow = "📈 LONG" if direction == "LONG" else "📉 SHORT"
    trs_line = f"TRS {trs}/5 · " if trs else ""
    if tag == "probe":
        header = (
            f"🧪 <b>PROBE TRADE OPEN</b> · {symbol} {arrow}\n"
            f"<i>(Μισό μέγεθος — περιμένουμε confirmation για upgrade σε TRS=5)</i>"
        )
    elif tag == "confirm":
        header = (
            f"🔥 <b>CONFIRMED · SCALE-IN</b> · {symbol} {arrow}\n"
            f"<i>(Το probe επιβεβαιώθηκε — προσθέτουμε τη 2η μισή θέση)</i>"
        )
    else:
        header = f"📥 <b>PAPER TRADE OPEN</b> · {symbol} {arrow}"
    reply = (
        f"{header}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Entry: <b>{entry}</b> · Lot: {lot}\n"
        f"🛑 SL: {sl} (risk {risk_eur:.2f}€)\n"
        f"✅ TP1: {tp1} (+{reward_tp1:.2f}€) · TP2: {tp2} (+{reward_tp2:.2f}€)\n"
        f"⏳ Max hold: {max_hold_hours}h · λήγει {expires.strftime('%H:%M')}\n"
        f"{trs_line}id <code>{trade_id}</code>"
    )
    if context:
        reply += f"\n💡 {context}"
    _tg_reply(reply, reply_to=entry_msg_id)

    return trade, None


# ---------- public API: tick ----------

def tick():
    """
    Iterate open trades, fire milestones, close on TP/SL/timeout.
    Returns list of events.
    """
    state = _load_state()
    trades = state.get("open_trades", []) or []
    if not trades:
        _save_state(state)
        return []

    prices = _load_live_prices()
    events = []
    now = _now_eet()
    closed_ids = set()

    for trade in list(trades):
        symbol = trade["symbol"]
        price = prices.get(symbol)
        if price is None:
            continue

        trade["last_price"] = price
        trade["last_pnl_eur"] = _compute_pnl_eur(trade, price)
        trade["last_progress_pct"] = _progress_pct(trade, price)

        # Check timeout first (closing reason takes priority over mid-milestone)
        try:
            expires = datetime.fromisoformat(trade["max_hold_expires"])
        except Exception:
            expires = None
        if expires and now >= expires:
            _close(trade, reason="max_hold", exit_price=price, events=events)
            closed_ids.add(trade["trade_id"])
            continue

        # SL hit — if be_moved, close as BE (0 P/L) with 🛡️; else full SL with 💀
        if _sl_hit(trade, price):
            reason = "be" if trade.get("be_moved") else "sl"
            _close(trade, reason=reason, exit_price=price, events=events)
            closed_ids.add(trade["trade_id"])
            continue

        # TP2 hit (only after TP1 already hit + BE moved)
        if trade.get("tp1_hit") and _tp2_hit(trade, price):
            # Auto-launch: extend runner if opted in AND not already launched
            if trade.get("auto_launch") and not trade.get("launched"):
                _, lerr = _apply_launch(trade, reason="tp2_auto",
                                        new_tp=None, new_sl=None, extra_hours=4)
                if lerr is None:
                    _emit_launch(trade, extra_hours=4)
                    events.append({"type": "launch_auto", "trade_id": trade["trade_id"]})
                    # Sync portfolio mirror inline (tick will save state at end)
                    portfolio = _load_portfolio()
                    for pt in portfolio.get("open_trades", []):
                        if pt.get("trade_id") == trade["trade_id"]:
                            pt["sl"] = trade["sl"]
                            pt["tp2"] = trade["tp2"]
                            break
                    _save_portfolio(portfolio)
                    continue  # stay open with new targets
            # Default behavior: close at TP2 as runner success
            _close(trade, reason="tp2", exit_price=price, events=events)
            closed_ids.add(trade["trade_id"])
            continue

        # TP1 hit (first time) → move SL to entry (break-even), keep running to TP2
        if _tp1_hit(trade, price) and not trade.get("tp1_hit"):
            trade["tp1_hit"] = True
            trade["be_moved"] = True
            trade["sl"] = trade["entry"]  # break-even stop
            _emit_tp1_be(trade, price)
            events.append({"type": "tp1_be", "trade_id": trade["trade_id"]})
            continue

        # Progress milestones 25/50/75 toward TP1 — fire only the HIGHEST newly-crossed
        # milestone per tick (avoids triple-ping when price jumps past 75% in one cycle).
        prog = trade.get("last_progress_pct", 0)
        fired = trade.setdefault("progress_milestones_fired", {"25": False, "50": False, "75": False})
        highest_new = None
        for thr_key, thr in (("25", 25), ("50", 50), ("75", 75)):
            if not fired[thr_key] and prog >= thr:
                fired[thr_key] = True
                highest_new = thr
        if highest_new is not None:
            _emit_progress(trade, highest_new, price)
            events.append({"type": f"progress_{highest_new}", "trade_id": trade["trade_id"]})

    # Remove closed from state
    state["open_trades"] = [t for t in trades if t["trade_id"] not in closed_ids]
    _save_state(state)
    return events


def _emit_progress(trade, milestone, price):
    pnl = trade["last_pnl_eur"]
    symbol = trade["symbol"]
    arrow = "📈" if trade["direction"] == "LONG" else "📉"
    reply = (
        f"⏱️ <b>{symbol}</b> · {milestone}% προς TP1 {arrow}\n"
        f"Τιμή: {price} · P/L {_fmt_pnl(pnl)}"
    )
    _tg_reply(reply, reply_to=trade.get("entry_msg_id"), silent=True)


def _emit_tp1_be(trade, price):
    """TP1 hit → SL moved to entry, runner heading to TP2."""
    symbol = trade["symbol"]
    pnl = trade["last_pnl_eur"]
    arrow = "📈" if trade["direction"] == "LONG" else "📉"
    reply = (
        f"🎯 <b>{symbol}</b> · TP1 HIT {arrow}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔄 SL → <b>Break-Even</b> (στο entry {trade['entry']}) — δεν μπορούμε να χάσουμε πλέον\n"
        f"🎯 Συνεχίζουμε προς <b>TP2 {trade['tp2']}</b> (planned +{trade.get('planned_reward_tp2_eur', 0):.2f}€)\n"
        f"Τιμή: {price} · P/L {_fmt_pnl(pnl)}"
    )
    _tg_reply(reply, reply_to=trade.get("entry_msg_id"))


def _close(trade, reason, exit_price, events):
    """Close a trade: write portfolio, journal, send final reply."""
    pnl = _compute_pnl_eur(trade, exit_price)
    now = _now_eet()
    trade["exit_price"] = exit_price
    trade["exit_time"] = _iso(now)
    trade["exit_reason"] = reason
    trade["final_pnl_eur"] = pnl

    # Journal append
    _append_jsonl(TRADE_JOURNAL_FILE, trade)

    # Update portfolio
    portfolio = _load_portfolio()
    portfolio["open_trades"] = [
        t for t in portfolio.get("open_trades", []) if t.get("trade_id") != trade["trade_id"]
    ]
    portfolio["daily_pnl"] = round(float(portfolio.get("daily_pnl", 0) or 0) + pnl, 2)
    portfolio["total_pnl"] = round(float(portfolio.get("total_pnl", 0) or 0) + pnl, 2)
    portfolio["current_balance"] = round(float(portfolio.get("current_balance", 0) or 0) + pnl, 2)
    portfolio["total_equity"] = portfolio["current_balance"]
    # BE exit (reason="be") is neutral — neither win nor loss
    if reason == "be" or abs(pnl) < 0.01:
        portfolio["breakeven_trades"] = int(portfolio.get("breakeven_trades", 0)) + 1
        # streak counters unchanged
    elif pnl > 0:
        portfolio["winning_trades"] = int(portfolio.get("winning_trades", 0)) + 1
        portfolio["consecutive_wins"] = int(portfolio.get("consecutive_wins", 0)) + 1
        portfolio["consecutive_losses"] = 0
    else:
        portfolio["losing_trades"] = int(portfolio.get("losing_trades", 0)) + 1
        portfolio["consecutive_losses"] = int(portfolio.get("consecutive_losses", 0)) + 1
        portfolio["consecutive_wins"] = 0
    _save_portfolio(portfolio)

    # Telegram reply
    symbol = trade["symbol"]
    if reason == "tp1":
        emoji, label = "🎯", "TP1 HIT"
    elif reason == "tp2":
        emoji, label = "🎯🎯", "TP2 HIT — runner πέτυχε"
    elif reason == "be":
        emoji, label = "🛡️", "BREAK-EVEN EXIT — έκλεισε στο entry μετά το TP1"
    elif reason == "sl":
        emoji, label = "💀", "SL HIT"
    elif reason == "max_hold":
        emoji, label = "⌛", "MAX HOLD (4h) — close at market"
    elif reason == "advisor_exit":
        emoji, label = "🚪", "ADVISOR EXIT — early close (contra signals)"
    elif reason == "news_counter":
        emoji, label = "🚨", "NEWS COUNTER — closed on adverse news"
    else:
        emoji, label = "✅", f"CLOSED ({reason})"

    # L6 EXIT v3 (30/04/2026): plain-Greek with daily-target progress, portfolio
    # update, and forward outlook (per IDEAL_DAY_WALKTHROUGH.md Message G).
    daily_target = float(portfolio.get("daily_target", 30.0))
    daily_pnl = portfolio.get("daily_pnl", 0.0)
    daily_progress_pct = (daily_pnl / daily_target * 100) if daily_target > 0 else 0
    target_reached = daily_pnl >= daily_target
    progress_bar_filled = max(0, min(20, int(round(daily_progress_pct / 5))))
    progress_bar = "█" * progress_bar_filled + "░" * (20 - progress_bar_filled)
    daily_target_emoji = "🎉" if target_reached else "📊"
    daily_total_trades = portfolio.get("trades_today", 0)
    daily_wins = portfolio.get("wins_today", 0)
    daily_losses = portfolio.get("losses_today", 0)

    # Holding period
    try:
        opened_dt = datetime.fromisoformat(str(trade.get("opened_at", "")).replace("Z", "+00:00"))
        hold_min = int((datetime.now(timezone.utc) - opened_dt).total_seconds() / 60)
        hold_str = f"{hold_min // 60}ω {hold_min % 60}λ" if hold_min >= 60 else f"{hold_min}λ"
    except Exception:
        hold_str = "—"

    # Forward outlook (only on TP wins or break-even — losses get a more sober message)
    if reason in ("tp1", "tp2") and target_reached:
        outlook = (
            "\n\n🔮 <b>Τι κάνουμε τώρα</b>\n"
            "🛑 Όχι νέο trade σήμερα — ημερήσιος στόχος επιτεύχθηκε, capital protection.\n"
            "🎯 Παρακολούθηση μόνο για τα άλλα assets χωρίς execution.\n"
            "🎯 Επόμενος Selector run: επανεκτίμηση για επόμενη συνεδρία."
        )
    elif reason in ("tp1", "tp2"):
        outlook = (
            "\n\n🔮 <b>Τι κάνουμε τώρα</b>\n"
            f"🎯 Συνεχίζουμε παρακολούθηση — απομένουν {daily_target - daily_pnl:.2f}€ για ημερήσιο στόχο.\n"
            "🎯 Νέο trade επιτρέπεται αν setup ώριμο."
        )
    elif reason == "sl":
        outlook = (
            "\n\n🔮 <b>Τι κάνουμε τώρα</b>\n"
            "📉 Ένα κανονικό loss — μέρος του game. Μη revenge trading.\n"
            f"🎯 Επόμενο setup θα αξιολογηθεί κανονικά (απομένουν {daily_target - daily_pnl:.2f}€ για στόχο)."
        )
    elif reason == "max_hold":
        outlook = (
            "\n\n🔮 <b>Τι κάνουμε τώρα</b>\n"
            "⌛ Trade έληξε στο 4ωρο cap χωρίς clear move — δομικό issue, όχι entry mistake.\n"
            "🎯 Επόμενο setup θα αξιολογηθεί με την ίδια δομή."
        )
    elif reason == "advisor_exit":
        outlook = (
            "\n\n🔮 <b>Τι κάνουμε τώρα</b>\n"
            "🚪 Έκλεισε νωρίς γιατί contra signals εμφανίστηκαν — προστατεύσαμε κεφάλαιο.\n"
            "🎯 Συνεχίζουμε παρακολούθηση κανονικά."
        )
    else:
        outlook = ""

    reply = (
        f"{emoji} <b>{symbol}</b> · {label}\n"
        f"Exit: {exit_price} · P/L <b>{_fmt_pnl(pnl)}</b> · Holding: {hold_str}\n"
        f"\n"
        f"📊 <b>Portfolio after this trade</b>\n"
        f"Balance: {portfolio['current_balance']:.2f}€\n"
        f"Trades σήμερα: {daily_total_trades} ({daily_wins}W / {daily_losses}L)\n"
        f"{daily_target_emoji} Στόχος ημέρας: {progress_bar} {daily_progress_pct:.0f}% "
        f"({daily_pnl:+.2f}€ / {daily_target:.0f}€)"
        f"{outlook}"
    )
    _tg_reply(reply, reply_to=trade.get("entry_msg_id"))

    events.append({"type": f"close_{reason}", "trade_id": trade["trade_id"], "pnl_eur": pnl})


# ---------- public API: launch_trade (extension for rocket scenarios) ----------

def _apply_launch(trade, reason, new_tp, new_sl, extra_hours):
    """
    Pure in-place mutation of a trade dict for launch. No state save, no Telegram.
    Returns (trade, error).

    Defaults:
      - new_tp: entry ± 3R where R = |entry - sl_original|
      - new_sl: old tp1 if tp1_hit; else current sl (unchanged)
      - extra_hours: caller decides, added to max_hold_expires from NOW
    """
    direction = trade["direction"]
    entry = float(trade["entry"])
    sl_current = float(trade["sl"])
    sl_original = float(trade.get("sl_original", sl_current))
    r_distance = abs(entry - sl_original)
    if r_distance <= 0:
        return None, "Invalid R distance (entry == sl_original)"

    if new_tp is None:
        new_tp = entry + 3 * r_distance if direction == "LONG" else entry - 3 * r_distance
    new_tp = float(new_tp)

    if new_sl is None:
        new_sl = float(trade["tp1"]) if trade.get("tp1_hit") else sl_current
    new_sl = float(new_sl)

    if direction == "LONG" and new_sl >= new_tp:
        return None, f"LONG: new_sl {new_sl} must be below new_tp {new_tp}"
    if direction == "SHORT" and new_sl <= new_tp:
        return None, f"SHORT: new_sl {new_sl} must be above new_tp {new_tp}"
    if direction == "LONG" and new_tp <= entry:
        return None, f"LONG: new_tp {new_tp} must be > entry {entry}"
    if direction == "SHORT" and new_tp >= entry:
        return None, f"SHORT: new_tp {new_tp} must be < entry {entry}"

    if not trade.get("launched"):
        trade["tp2_original"] = trade["tp2"]
        trade["sl_at_launch"] = sl_current
        trade["max_hold_expires_original"] = trade["max_hold_expires"]

    now = _now_eet()
    new_expires = now + timedelta(hours=int(extra_hours))

    trade["tp2"] = new_tp
    trade["sl"] = new_sl
    trade["max_hold_expires"] = _iso(new_expires)
    trade["launched"] = True
    trade["launch_time"] = _iso(now)
    trade["launch_reason"] = reason
    if direction == "LONG" and new_sl > entry:
        trade["be_moved"] = False
        trade["profit_locked"] = True
    elif direction == "SHORT" and new_sl < entry:
        trade["be_moved"] = False
        trade["profit_locked"] = True

    symbol = trade["symbol"]
    pip_size = _pip_size(symbol)
    pip_value = _pip_value(symbol)
    lot = trade["lot"]
    if pip_size:
        trade["planned_reward_tp2_eur"] = round(abs(new_tp - entry) / pip_size * pip_value * lot, 2)

    return trade, None


def _emit_launch(trade, extra_hours):
    """Send 🚀 Telegram reply for a just-launched trade."""
    symbol = trade["symbol"]
    direction = trade["direction"]
    entry = float(trade["entry"])
    new_tp = trade["tp2"]
    new_sl = trade["sl"]
    arrow = "📈" if direction == "LONG" else "📉"
    pl_lock = ""
    if trade.get("profit_locked"):
        pip_size = _pip_size(symbol)
        pip_value = _pip_value(symbol)
        lot = trade["lot"]
        locked_pips = abs(new_sl - entry) / pip_size if pip_size else 0
        locked_eur = round(locked_pips * pip_value * lot, 2)
        pl_lock = f"\n💰 Profit locked: +{locked_eur:.2f}€ minimum (SL > entry)"
    try:
        new_expires = datetime.fromisoformat(trade["max_hold_expires"])
        exp_str = new_expires.strftime('%H:%M')
    except Exception:
        exp_str = "—"
    reply = (
        f"🚀 <b>{symbol}</b> · LAUNCHED {arrow}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Νέο TP: <b>{new_tp}</b> (planned +{trade.get('planned_reward_tp2_eur', 0):.2f}€)\n"
        f"🛡️ Νέο SL: <b>{new_sl}</b>{pl_lock}\n"
        f"⏳ Νέο timeout: +{extra_hours}h · λήγει {exp_str}\n"
        f"📰 Λόγος: {trade.get('launch_reason', 'manual')}"
    )
    _tg_reply(reply, reply_to=trade.get("entry_msg_id"))


def launch_trade(trade_id, reason="manual", new_tp=None, new_sl=None,
                 extra_hours=4, silent=False):
    """
    CLI-facing launch: loads state, mutates, saves, sends Telegram.
    For tick-internal auto-launch, use _apply_launch + _emit_launch directly.
    """
    state = _load_state()
    trades = state.get("open_trades", []) or []
    trade = next((t for t in trades if t["trade_id"] == trade_id), None)
    if trade is None:
        return None, f"No open trade with id {trade_id}"

    _, err = _apply_launch(trade, reason, new_tp, new_sl, extra_hours)
    if err:
        return None, err

    # Sync portfolio mirror
    portfolio = _load_portfolio()
    for pt in portfolio.get("open_trades", []):
        if pt.get("trade_id") == trade_id:
            pt["sl"] = trade["sl"]
            pt["tp2"] = trade["tp2"]
            break
    _save_portfolio(portfolio)
    _save_state(state)

    if not silent:
        _emit_launch(trade, extra_hours)

    return trade, None


# ---------- public API: close_trade (manual) ----------

def close_trade(trade_id, reason="manual", exit_price=None):
    state = _load_state()
    trades = state.get("open_trades", []) or []
    target = next((t for t in trades if t["trade_id"] == trade_id), None)
    if target is None:
        return None, f"No open trade with id {trade_id}"
    if exit_price is None:
        price = _load_live_prices().get(target["symbol"])
        if price is None:
            return None, f"No live price for {target['symbol']}, pass exit_price explicitly"
        exit_price = float(price)
    events = []
    _close(target, reason=reason, exit_price=float(exit_price), events=events)
    state["open_trades"] = [t for t in trades if t["trade_id"] != trade_id]
    _save_state(state)
    return target, None


# ---------- public API: list_open ----------

def list_open():
    state = _load_state()
    return state.get("open_trades", []) or []


# ---------- public API: header (open-trades block for Monitor messages) ----------

def render_header():
    """Return an HTML block summarizing open trades. Empty string if no trades.
    Used by market_monitor.md to prepend to every Tier A/B/C message."""
    trades = list_open()
    if not trades:
        return ""
    prices = _load_live_prices()
    lines = [f"📥 <b>Ανοιχτά Trades ({len(trades)})</b>"]
    now = _now_eet()
    for t in trades:
        symbol = t["symbol"]
        direction = t["direction"]
        entry = t["entry"]
        price = prices.get(symbol, t.get("last_price") or entry)
        pnl = _compute_pnl_eur(t, price)
        prog = _progress_pct(t, price)
        dot = "🟢" if pnl > 0 else ("🔴" if pnl < 0 else "🟡")
        arrow = "📈" if direction == "LONG" else "📉"
        tag = (t.get("tag") or "full").lower()
        tag_badge = " 🧪" if tag == "probe" else (" 🔥" if tag == "confirm" else "")
        # Status line: pre-TP1 = "% → TP1"; post-TP1 (BE runner) = "TP1 ✓ → TP2"
        if t.get("tp1_hit"):
            # Progress toward TP2 now (entry → TP2)
            span2 = t["tp2"] - t["entry"] if direction == "LONG" else t["entry"] - t["tp2"]
            progressed2 = (price - t["entry"]) if direction == "LONG" else (t["entry"] - price)
            prog2 = round((progressed2 / span2) * 100.0, 0) if span2 else 0.0
            status = f"🎯 TP1 ✓ · runner @ {prog2:.0f}% → TP2 · SL=BE"
        else:
            status = f"{prog:.0f}% → TP1"
        try:
            expires = datetime.fromisoformat(t["max_hold_expires"])
            remaining = expires - now
            mins = max(0, int(remaining.total_seconds() // 60))
            countdown = f"{mins // 60}h{mins % 60:02d}'"
        except Exception:
            countdown = "—"
        lines.append(
            f"{dot} <b>{symbol}</b>{tag_badge} {arrow} @ <code>{entry}</code> · "
            f"{status} · P/L <b>{_fmt_pnl(pnl)}</b> · ⏳ {countdown}"
        )
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ---------- CLI ----------

def _cli():
    p = argparse.ArgumentParser(prog="trade_manager")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_open = sub.add_parser("open", help="Open a paper trade")
    p_open.add_argument("symbol")
    p_open.add_argument("direction", choices=["LONG", "SHORT", "long", "short"])
    p_open.add_argument("entry", type=float)
    p_open.add_argument("sl", type=float)
    p_open.add_argument("tp1", type=float)
    p_open.add_argument("tp2", type=float)
    p_open.add_argument("lot", nargs="?", type=float, default=None)
    p_open.add_argument("--entry-msg-id", type=int, default=None)
    p_open.add_argument("--trs", type=int, default=None)
    p_open.add_argument("--context", default="")
    p_open.add_argument("--tag", choices=["full", "probe", "confirm"], default="full",
                        help="probe=TRS4 half-size; confirm=TRS5 scale-in on active probe")
    p_open.add_argument("--auto-launch", action="store_true",
                        help="On TP2 hit: extend runner to 3R instead of closing (rocket mode)")

    sub.add_parser("tick", help="Run one tick cycle")
    sub.add_parser("list", help="List open trades")
    sub.add_parser("header", help="Print HTML block of open trades (for Monitor messages)")

    p_close = sub.add_parser("close", help="Manually close a trade")
    p_close.add_argument("trade_id")
    p_close.add_argument("reason", nargs="?", default="manual")
    p_close.add_argument("exit_price", nargs="?", type=float, default=None)

    p_suggest = sub.add_parser("suggest", help="Compute realistic TP/SL for 4h day trading")
    p_suggest.add_argument("symbol")
    p_suggest.add_argument("direction", choices=["LONG", "SHORT", "long", "short"])
    p_suggest.add_argument("entry", type=float)
    p_suggest.add_argument("--atr", type=float, default=None,
                           help="4h ATR (preferred). Omit for typical_sl_pct_4h fallback.")
    p_suggest.add_argument("--mode", choices=["tight", "typical", "wide"], default="typical")
    p_suggest.add_argument("--json", action="store_true", help="Emit JSON instead of text block")

    p_launch = sub.add_parser("launch",
        help="Rocket: extend open trade with new TP/SL/timeout (news catalyst, momentum)")
    p_launch.add_argument("trade_id")
    p_launch.add_argument("--reason", default="manual",
                          help="news|momentum|tp2_runner|manual — stored for audit")
    p_launch.add_argument("--tp", type=float, default=None,
                          help="New TP (default: entry ± 3R)")
    p_launch.add_argument("--sl", type=float, default=None,
                          help="New SL (default: old TP1 if TP1 hit, else current SL)")
    p_launch.add_argument("--timeout-h", type=int, default=4,
                          help="Extend timeout by N hours from NOW (default 4)")
    p_launch.add_argument("--silent", action="store_true", help="Suppress Telegram reply")

    args = p.parse_args()

    if args.cmd == "open":
        trade, err = open_trade(
            args.symbol, args.direction, args.entry, args.sl, args.tp1, args.tp2,
            lot=args.lot, entry_msg_id=args.entry_msg_id, trs=args.trs,
            context=args.context, tag=args.tag, auto_launch=args.auto_launch,
        )
        if err:
            print(f"ERROR: {err}", file=sys.stderr)
            return 1
        print(trade["trade_id"])
        return 0

    if args.cmd == "tick":
        events = tick()
        print(json.dumps(events, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "list":
        trades = list_open()
        if not trades:
            print("No open trades")
            return 0
        for t in trades:
            print(
                f"{t['trade_id']} | {t['symbol']} {t['direction']} @ {t['entry']} "
                f"· SL {t['sl']} · TP1 {t['tp1']} · lot {t['lot']} "
                f"· expires {t['max_hold_expires']}"
            )
        return 0

    if args.cmd == "close":
        trade, err = close_trade(args.trade_id, args.reason, args.exit_price)
        if err:
            print(f"ERROR: {err}", file=sys.stderr)
            return 1
        print(f"Closed {trade['trade_id']} · P/L {trade.get('final_pnl_eur')}")
        return 0

    if args.cmd == "header":
        block = render_header()
        if block:
            print(block)
        return 0

    if args.cmd == "suggest":
        if suggest_tp_sl is None:
            print("ERROR: risk_manager.suggest_tp_sl unavailable", file=sys.stderr)
            return 1
        r = suggest_tp_sl(args.symbol.upper(), args.entry, args.direction.upper(),
                          atr_4h=args.atr, sl_mode=args.mode)
        if not r.get("ok"):
            print(f"ERROR: {r.get('error')}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            arrow = "📈" if args.direction.upper() == "LONG" else "📉"
            print(f"💡 Suggested TP/SL · {args.symbol.upper()} {arrow} @ {args.entry}")
            print(f"   🛡️  SL:  {r['sl']}   ({r['sl_pct']:.2f}% · {r['sl_distance']} distance)")
            print(f"   ✅ TP1: {r['tp1']}   (+{r['tp1_pct']:.2f}% · 1R)")
            print(f"   ✅ TP2: {r['tp2']}   (+{r['tp2_pct']:.2f}% · 2R)")
            print(f"   📐 {r['rationale']}")
            if r.get("clamped"):
                print(f"   ⚠️  Clamped to 4h cap — analyst may widen SL via wider setup")
        return 0

    if args.cmd == "launch":
        trade, err = launch_trade(
            args.trade_id,
            reason=args.reason,
            new_tp=args.tp,
            new_sl=args.sl,
            extra_hours=args.timeout_h,
            silent=args.silent,
        )
        if err:
            print(f"ERROR: {err}", file=sys.stderr)
            return 1
        print(f"LAUNCHED {trade['trade_id']} · TP {trade['tp2']} · SL {trade['sl']} "
              f"· expires {trade['max_hold_expires']}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(_cli())
