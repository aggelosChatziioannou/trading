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
from datetime import datetime, timezone, timedelta

# EET timezone for ALL timestamps — fixes UTC-vs-EET 3h drift bug (2026-04-29)
EET = timezone(timedelta(hours=3))
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

# Health thresholds (minutes) — match data_health.py
HEALTH_MONITOR_MAX_AGE = 45   # Monitor cycle every 20-40min, allow 45 grace
HEALTH_SELECTOR_MAX_AGE = 600  # Selector 4×/day, max 9h (08:00→15:00 = 7h, 21:00→08:00 = 11h, but EVE→AM Sat-Mon weekend = stretchy)

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


def _parse_iso_or_naive(ts_str):
    """Best-effort parse for various timestamp formats. Return naive datetime in EET-equivalent."""
    if not ts_str or ts_str == "?":
        return None
    try:
        if 'T' in ts_str and ('+' in ts_str or ts_str.endswith('Z')):
            from datetime import timezone, timedelta
            if ts_str.endswith('Z'):
                ts_str = ts_str[:-1] + '+00:00'
            dt = datetime.fromisoformat(ts_str)
            return dt.replace(tzinfo=None) + timedelta(hours=3) - dt.utcoffset()
        if ' ' in ts_str:
            return datetime.strptime(ts_str[:19], '%Y-%m-%d %H:%M:%S')
    except Exception:
        return None
    return None


def _health_line():
    """Render system health line: Monitor cycle age + Selector cycle age + data freshness."""
    now = datetime.now(EET).replace(tzinfo=None)  # naive EET for comparison with parsed naive ts
    parts = []

    # Monitor last cycle from news_feed.json timestamp (written every Monitor cycle)
    news_feed = _load("news_feed.json") or {}
    monitor_ts = _parse_iso_or_naive(news_feed.get("timestamp"))
    if monitor_ts:
        if monitor_ts.tzinfo is not None:
            monitor_ts = monitor_ts.replace(tzinfo=None)
        age_min = (now - monitor_ts).total_seconds() / 60
        if age_min < HEALTH_MONITOR_MAX_AGE:
            mon_icon = "💚"
        elif age_min < HEALTH_MONITOR_MAX_AGE * 2:
            mon_icon = "🟡"
        else:
            mon_icon = "🔴"
        parts.append(f"{mon_icon} Monitor {monitor_ts.strftime('%H:%M')} ({age_min:.0f}' ago)")
    else:
        parts.append("🔴 Monitor: never")

    # Selector last cycle from selected_assets.json timestamp
    selected = _load("selected_assets.json") or {}
    sel_ts = _parse_iso_or_naive(selected.get("timestamp"))
    if sel_ts:
        age_min = (now - sel_ts).total_seconds() / 60
        if age_min < HEALTH_SELECTOR_MAX_AGE:
            sel_icon = "💚"
        elif age_min < HEALTH_SELECTOR_MAX_AGE * 1.5:
            sel_icon = "🟡"
        else:
            sel_icon = "🔴"
        # Format: HH:MM if today, else "Mon 08:00"
        days_ago = (now.date() - sel_ts.date()).days
        if days_ago == 0:
            ts_str = sel_ts.strftime('%H:%M')
        elif days_ago == 1:
            ts_str = "yesterday " + sel_ts.strftime('%H:%M')
        else:
            ts_str = sel_ts.strftime('%a %H:%M')
        parts.append(f"{sel_icon} Selector {ts_str}")
    else:
        parts.append("🔴 Selector: never")

    # Data health from data_health.json
    health = _load("data_health.json") or {}
    overall = health.get("overall_status", "UNKNOWN")
    files = health.get("files", [])
    fresh = sum(1 for f in files if not f.get("stale"))
    total = len(files)
    if overall == "HEALTHY":
        parts.append(f"💚 Data {fresh}/{total} fresh")
    elif overall == "DEGRADED":
        parts.append(f"🟡 Data {fresh}/{total} fresh")
    elif overall == "CRITICAL":
        parts.append(f"🔴 Data {fresh}/{total} STALE")
    else:
        parts.append("⚪ Data: ?")

    return "🩺 " + " · ".join(parts)


def _learning_stats_lines():
    """Render Learning Stats panel from latest weekly_audit + calibration_proposals queue.
    Returns list of lines (empty if nothing to show)."""
    # Find latest weekly_audit_*.json
    audit_files = sorted(DATA.glob("weekly_audit_*.json"), reverse=True)
    if not audit_files:
        return ["🧠 <b>Learning</b>: αναμονή πρώτου weekly audit (Κυρ 22:00)"]

    try:
        audit = json.loads(audit_files[0].read_text(encoding='utf-8'))
    except Exception:
        return ["🧠 <b>Learning</b>: audit file unreadable"]

    h = audit.get("headline", {})
    week_id = audit.get("week_id", "?")
    period = audit.get("period", {})

    lines = []
    period_short = ""
    if period.get("start") and period.get("end"):
        try:
            s = datetime.fromisoformat(period["start"]).strftime("%d %b")
            e = datetime.fromisoformat(period["end"]).strftime("%d %b")
            period_short = f"({s}-{e})"
        except Exception:
            pass
    lines.append(f"🧠 <b>Learning Stats</b> · {week_id} {period_short}".strip())
    if h.get("trades", 0) == 0:
        lines.append(f"   Trades: 0 · αναμονή live data")
    else:
        lines.append(
            f"   Trades: {h.get('trades',0)} · WR {h.get('wr_pct',0)}% · R {h.get('avg_r',0):+.2f} · P/L {h.get('total_pnl_eur',0):+.2f}€"
        )
        # Best/worst strategy
        strats = audit.get("per_strategy", []) or []
        if strats:
            best = max(strats, key=lambda s: (s.get("wr_pct", 0), s.get("trades", 0)))
            worst = min(strats, key=lambda s: (s.get("wr_pct", 0), -s.get("trades", 0)))
            if best is worst:
                lines.append(f"   📊 {best.get('strategy','?')}: {best.get('wins',0)}W/{best.get('trades',0)}T")
            else:
                lines.append(
                    f"   📊 Best: {best.get('strategy','?')[:20]} ({best.get('wins',0)}W/{best.get('trades',0)}T) · Worst: {worst.get('strategy','?')[:20]} ({worst.get('wins',0)}W/{worst.get('trades',0)}T)"
                )

    # Pending proposals
    proposals_path = DATA / "calibration_proposals.json"
    pending = 0
    last_applied_age = None
    if proposals_path.exists():
        try:
            pdata = json.loads(proposals_path.read_text(encoding='utf-8'))
            pending = len([p for p in pdata.get("queue", []) if p.get("status") == "pending_approval"])
            applied = [p for p in pdata.get("history", []) if p.get("action") == "approved"]
            if applied:
                last_ts = max((datetime.fromisoformat(p.get("applied_at","").replace('Z','+00:00')) for p in applied if p.get("applied_at")), default=None)
                if last_ts:
                    days = (datetime.now(EET) - (last_ts.astimezone(EET).replace(tzinfo=None) if last_ts.tzinfo else last_ts)).days
                    last_applied_age = f"{days}d ago"
        except Exception:
            pass

    if pending > 0 or last_applied_age:
        bits = []
        if pending > 0:
            bits.append(f"🔬 Pending: <b>{pending}</b>")
        if last_applied_age:
            bits.append(f"Last applied: {last_applied_age}")
        lines.append(f"   {' · '.join(bits)}")

    return lines


def _embargo_line():
    """Render embargo state line. Empty if file missing or CLEAR with no upcoming."""
    embargo = _load("embargo_state.json") or {}
    if not embargo:
        return ""
    state = embargo.get("overall_state", "CLEAR")
    if state == "CLEAR":
        nxt = embargo.get("next_high_event")
        if nxt and nxt.get("minutes_until", 999) < 240:
            return f"📅 Next HIGH: {nxt['title'][:40]} σε {nxt['minutes_until']:.0f}'"
        return ""
    if state == "PENDING":
        be = embargo.get("blocking_event") or {}
        return f"🛑 EMBARGO PENDING: {be.get('title','?')[:40]} σε {abs(be.get('delta_minutes',0)):.0f}'"
    if state == "EVENT":
        be = embargo.get("blocking_event") or {}
        return f"⚡ HIGH EVENT NOW: {be.get('title','?')[:50]}"
    if state == "POST":
        be = embargo.get("blocking_event") or {}
        return f"🚧 POST-EVENT: {be.get('title','?')[:40]} ({abs(be.get('delta_minutes',0)):.0f}' ago)"
    return ""


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
        now = datetime.now(EET)
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
    now = datetime.now(EET)
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
        # Normalize to EET-aware for comparison with `now`
        if et.tzinfo is None:
            et = et.replace(tzinfo=EET)
        else:
            et = et.astimezone(EET)
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

    now = datetime.now(EET).strftime("%H:%M")

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

    # T1.3 — System health heartbeat (Monitor cycle, Selector cycle, data freshness)
    health_line = _health_line()
    if health_line:
        lines.append(health_line)

    # T1.2 — News embargo state line (only if active or upcoming HIGH)
    emb_line = _embargo_line()
    if emb_line:
        lines.append(emb_line)

    # Self-Improvement v1 — Learning Stats panel (Layer 3 weekly audit summary)
    learning = _learning_stats_lines()
    for ln in learning:
        lines.append(ln)

    return "\n".join(lines)


if __name__ == "__main__":
    print(build())
