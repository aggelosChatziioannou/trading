#!/usr/bin/env python3
"""
GOLD TACTIC — Dashboard Builder (v7.1)

Reads current state files and prints the HTML body for the pinned Telegram dashboard.

Consumes:
  data/portfolio.json       — balance, W/L, daily_pnl
  data/selected_assets.json — currently watched 4 assets
  data/trs_current.json     — latest TRS + 5 criteria per asset (written by Monitor)
  data/quick_scan.json      — sentiment footer (F&G, VIX, regime)
  data/economic_calendar.json — next event

Output: HTML text to stdout. Pipe into:
  python telegram_sender.py dashboard < <(python dashboard_builder.py)
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path

if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent))
try:
    from session_check import current_session, session_tag
except Exception:
    def current_session(now=None):
        return {"name": "—", "tier": "off", "emoji": "🌙", "weekend": False, "optimal": False, "message": ""}
    def session_tag(s=None):
        s = s or current_session()
        return f"{s['emoji']} <b>{s['name']}</b>"

DATA = Path(__file__).parent.parent / "data"

REGIME_EMOJI = {"RISK_ON": "⚡", "RISK_OFF": "🛡️", "NEUTRAL": "😐"}
ARROW = {"up": "🔼", "down": "🔽", "flat": "➡️"}

try:
    from risk_manager import ASSET_CONFIG
except Exception:
    ASSET_CONFIG = {}


def _load(fname, default=None):
    p = DATA / fname
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return default


def _trs_color(trs):
    if trs >= 4:
        return "🟢"
    if trs >= 3:
        return "🟡"
    return "⚪"


def _criteria_line(criteria, has_data=True):
    """Render ✅/❌ inline for 5 criteria; if no data, dim to ➖."""
    order = ["TF", "RSI", "ADR", "News", "Key"]
    if not has_data:
        return " ".join(f"➖{k}" for k in order)
    parts = []
    for k in order:
        v = criteria.get(k) if isinstance(criteria, dict) else None
        mark = "✅" if v is True else "❌"
        parts.append(f"{mark}{k}")
    return " ".join(parts)


def _live_prices():
    doc = _load("live_prices.json") or {}
    out = {}
    for sym, info in (doc.get("prices") or {}).items():
        if isinstance(info, dict) and info.get("price") is not None:
            try:
                out[sym] = float(info["price"])
            except Exception:
                continue
    return out


def _trade_pnl_eur(trade, price):
    sym = trade["symbol"]
    cfg = ASSET_CONFIG.get(sym) or {}
    pip_size = cfg.get("pip_size", 0.0001)
    pip_value = cfg.get("pip_value_per_lot", 10.0)
    if trade["direction"] == "LONG":
        pips = (price - trade["entry"]) / pip_size
    else:
        pips = (trade["entry"] - price) / pip_size
    return round(pips * pip_value * trade["lot"], 2)


def _trade_progress_pct(trade, price):
    entry = trade["entry"]
    tp1 = trade["tp1"]
    span = tp1 - entry
    if span == 0:
        return 0.0
    prog = price - entry
    if trade["direction"] == "SHORT":
        prog = -prog
        span = -span
    return round((prog / span) * 100.0, 1)


def _countdown(iso_ts):
    try:
        expires = datetime.fromisoformat(iso_ts)
    except Exception:
        return "—"
    if expires.tzinfo is not None:
        now = datetime.now(expires.tzinfo)
    else:
        now = datetime.now()
    delta = expires - now
    total = int(delta.total_seconds())
    if total <= 0:
        return "0'"
    hrs = total // 3600
    mins = (total % 3600) // 60
    return f"{hrs}h{mins:02d}'" if hrs else f"{mins}'"


def _render_open_trades(max_concurrent):
    state = _load("trade_state.json") or {}
    trades = state.get("open_trades") or []
    if not trades:
        return None
    prices = _live_prices()
    lines = [f"<b>📥 Ανοιχτά Trades ({len(trades)}/{max_concurrent})</b>"]
    for t in trades:
        sym = t.get("symbol", "?")
        direction = t.get("direction", "")
        price = prices.get(sym)
        if price is None:
            pnl = 0.0
            prog = 0.0
            price_str = "—"
        else:
            pnl = _trade_pnl_eur(t, price)
            prog = max(-100.0, min(150.0, _trade_progress_pct(t, price)))
            price_str = _fmt_price(price)
        if pnl > 0.05:
            dot = "🟢"
        elif pnl < -0.05:
            dot = "🔴"
        else:
            dot = "🟡"
        dir_tag = "📈 LONG" if direction == "LONG" else "📉 SHORT"
        clamped = max(0.0, min(100.0, prog))
        filled = round(clamped / 10)
        bar = "█" * filled + "░" * (10 - filled)
        countdown = _countdown(t.get("max_hold_expires", ""))
        lines.append(f"{dot} <b>{sym}</b> {dir_tag} @ {t.get('entry')}")
        lines.append(f"   {bar} {int(prog)}% → TP1 · P/L <b>{pnl:+.2f}€</b> · τώρα {price_str}")
        lines.append(f"   ⏳ {countdown} remaining (max 4h)")
    return lines


def _fmt_price(p):
    if p is None:
        return "—"
    try:
        v = float(p)
    except Exception:
        return str(p)
    if v >= 1000:
        return f"${v:,.0f}" if v >= 10000 else f"${v:,.1f}"
    if v >= 10:
        return f"{v:.2f}"
    return f"{v:.4f}"


def _next_event():
    cal = _load("economic_calendar.json") or {}
    candidates = []
    if isinstance(cal, dict):
        if isinstance(cal.get("events"), list):
            candidates.extend(cal["events"])
        if isinstance(cal.get("high_impact_today"), list):
            candidates.extend(cal["high_impact_today"])
        cb = cal.get("central_banks", {})
        if isinstance(cb, dict):
            for src, items in cb.items():
                if isinstance(items, list):
                    for ev in items:
                        if isinstance(ev, dict):
                            candidates.append({**ev, "source": src})
    elif isinstance(cal, list):
        candidates = cal
    if not candidates:
        return "—"
    from email.utils import parsedate_to_datetime
    now = datetime.now()
    upcoming = []
    for ev in candidates:
        t = ev.get("time") or ev.get("datetime") or ev.get("ts") or ev.get("date")
        if not t:
            continue
        et = None
        try:
            et = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        except Exception:
            try:
                et = parsedate_to_datetime(str(t))
            except Exception:
                continue
        if et is None:
            continue
        if et.tzinfo is not None:
            et = et.replace(tzinfo=None)
        if et >= now:
            upcoming.append((et, ev))
    if not upcoming:
        return "—"
    upcoming.sort(key=lambda x: x[0])
    et, ev = upcoming[0]
    delta = et - now
    hrs = int(delta.total_seconds() // 3600)
    mins = int((delta.total_seconds() % 3600) // 60)
    cd = f"{hrs}h{mins:02d}'" if hrs else f"{mins}'"
    label = ev.get("event") or ev.get("name") or ev.get("title") or "event"
    if len(label) > 35:
        label = label[:32] + "..."
    return f"{et.strftime('%H:%M')} {label} (σε {cd})"


def build():
    portfolio = _load("portfolio.json") or {}
    selected = _load("selected_assets.json") or {"selected": []}
    trs_cur = _load("trs_current.json") or {"assets": {}}
    scan = _load("quick_scan.json") or {}

    balance = portfolio.get("current_balance", 0)
    initial = portfolio.get("initial_capital", 1000)
    wins = portfolio.get("winning_trades", 0)
    losses = portfolio.get("losing_trades", 0)
    total = wins + losses
    win_rate = int(100 * wins / total) if total else 0
    trades_today = portfolio.get("trades_today", 0)
    daily = portfolio.get("daily_pnl", 0) or 0
    target = portfolio.get("daily_target") or 15  # EUR default
    pct = int(100 * max(0, daily) / target) if target else 0
    pct = min(pct, 100)
    filled = round(pct / 12.5)  # 8 blocks
    bar = "█" * filled + "░" * (8 - filled)

    max_daily_loss = portfolio.get("max_daily_loss_eur", 40)
    max_concurrent = portfolio.get("max_concurrent_trades", 2)
    daily_stop_hit = daily <= -abs(max_daily_loss)
    sess = current_session()

    open_trades = portfolio.get("open_trades", []) or []
    if open_trades:
        open_str = " · ".join(
            f"{t.get('symbol','?')} {t.get('direction','?')}"
            for t in open_trades
        )
    else:
        open_str = "—"

    sentiment = scan.get("sentiment") if isinstance(scan, dict) else {}
    sentiment = sentiment or {}
    fg = sentiment.get("fear_greed_value") or sentiment.get("fear_greed") or sentiment.get("fg") or "—"
    fg_label = sentiment.get("fear_greed_label") or ""
    vix = sentiment.get("vix") or sentiment.get("VIX") or "—"
    regime = (sentiment.get("market_regime") or sentiment.get("regime") or "NEUTRAL").upper()
    regime_em = REGIME_EMOJI.get(regime, "😐")

    now = datetime.now().strftime("%H:%M")

    lines = []
    lines.append(f"📌 <b>DASHBOARD</b> · {now}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    total_pnl = balance - initial
    pnl_pct = (total_pnl / initial * 100) if initial else 0
    lines.append(
        f"💼 <b>{balance:.2f}€</b> (αρχικό {initial:.0f}€ · {total_pnl:+.2f}€ / {pnl_pct:+.1f}%)"
    )
    lines.append(
        f"📊 Συνολικά: <b>{total}</b> trades · {wins}W-{losses}L · Win rate <b>{win_rate}%</b>"
    )
    lines.append(
        f"📅 Σήμερα: <b>{trades_today}</b> trades · P/L <b>{daily:+.2f}€</b> / {target}€  {bar} {pct}%"
    )
    if daily_stop_hit:
        lines.append(
            f"🛑 <b>DAILY STOP HIT</b> ({daily:+.2f}€ ≤ -{max_daily_loss}€) — κανένα νέο σήμα σήμερα"
        )
    lines.append(session_tag(sess))
    lines.append("")
    lines.append("<b>👀 Παρακολουθούμε:</b>")

    scan_prices = {}
    if isinstance(scan, dict) and isinstance(scan.get("assets"), list):
        for a in scan["assets"]:
            if isinstance(a, dict) and a.get("asset"):
                scan_prices[a["asset"]] = a.get("price")

    watched = selected.get("selected", []) if isinstance(selected, dict) else []
    if not watched:
        lines.append("<i>Δεν υπάρχουν επιλεγμένα assets</i>")
    else:
        for entry in watched[:4]:
            sym = entry.get("symbol", "?")
            direction = (entry.get("direction") or entry.get("direction_bias") or "").upper()
            if direction in ("BUY", "LONG"):
                dir_tag = "📈 LONG"
            elif direction in ("SELL", "SHORT"):
                dir_tag = "📉 SHORT"
            else:
                dir_tag = "➖"
            prob = entry.get("trade_probability")
            cur = trs_cur.get("assets", {}).get(sym, {}) or {}
            has_data = bool(cur)
            trs = cur.get("trs") if has_data else None
            trs_str = f"{trs}/5" if isinstance(trs, int) else "—/5"
            # Boost display probability when TRS is live
            if isinstance(prob, (int, float)) and isinstance(trs, int):
                eff_prob = max(prob, int(trs * 20))
            else:
                eff_prob = prob if isinstance(prob, (int, float)) else None
            prob_str = f" · 🎲 {int(eff_prob)}%" if eff_prob is not None else ""
            criteria = cur.get("criteria", {})
            price_val = cur.get("price") if has_data else scan_prices.get(sym)
            price = _fmt_price(price_val)
            arrow = ARROW.get(cur.get("arrow", "flat"), "") if has_data else ""
            color = _trs_color(trs if isinstance(trs, int) else 0)
            lines.append(
                f"{color} <b>{sym}</b> · {dir_tag}{prob_str}"
            )
            lines.append(
                f"   TRS {trs_str} · {price} {arrow}".rstrip()
            )
            lines.append(f"   {_criteria_line(criteria, has_data=has_data)}")

    open_block = _render_open_trades(max_concurrent)
    lines.append("")
    if open_block:
        lines.extend(open_block)
    else:
        lines.append(f"<b>Open:</b> {open_str}")
    lines.append(f"⏰ Next: {_next_event()}")
    fg_suffix = f" ({fg_label})" if fg_label else ""
    lines.append(
        f"🌡️ F&amp;G {fg}{fg_suffix} · {regime_em} {regime}"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    print(build())
