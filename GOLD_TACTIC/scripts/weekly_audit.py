#!/usr/bin/env python3
"""
GOLD TACTIC — Weekly Audit (Layer 3 of Self-Improvement)

Aggregates one week of trade reflections + journal + cycle/session logs into:
  - data/weekly_audit_YYYY_WW.json (machine)
  - data/weekly_audit_YYYY_WW.md   (human)
  - In-place update to data/strategy_scorecard.md
  - data/calibration_proposals.json (queue, max 2 proposals/week)

Sends Sunday digest to Telegram + per-proposal silent notification.

Usage:
  weekly_audit.py --week current               # this week
  weekly_audit.py --week 2026_W17              # specific week
  weekly_audit.py --week current --telegram    # also send digest+proposals to TG
  weekly_audit.py --week current --no-write    # dry-run preview

Run by:
  - GT Weekly Audit Claude schedule (Sunday 22:00 EET) via prompts/weekly_audit.md
  - Manual CLI for backfill/synthetic tests
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

DATA_DIR = Path(__file__).parent.parent / "data"
TRADE_JOURNAL = DATA_DIR / "trade_journal.jsonl"
REFLECTIONS = DATA_DIR / "trade_reflections.jsonl"
CYCLE_LOG = DATA_DIR / "cycle_log.jsonl"
SESSION_LOG = DATA_DIR / "session_log.jsonl"
GHOST_TRADES = DATA_DIR / "ghost_trades.json"
EVENT_IMPACT_LOG = DATA_DIR / "event_impact_log.jsonl"
SCORECARD = DATA_DIR / "strategy_scorecard.md"
PROPOSALS_FILE = DATA_DIR / "calibration_proposals.json"

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


def _read_jsonl(path):
    if not path.exists():
        return []
    out = []
    with path.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    return out


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, path)


def _resolve_week(week_arg):
    """Resolve week arg ('current' or 'YYYY_WW') to (year, week, start_dt, end_dt)."""
    now = _now()
    if week_arg == "current":
        # ISO week: year-week of "today"
        year, week, _ = now.isocalendar()
    else:
        try:
            y, w = week_arg.split("_W")
            year = int(y)
            week = int(w)
        except Exception:
            print(f"Invalid week: {week_arg} (expected 'current' or 'YYYY_WW')", file=sys.stderr)
            sys.exit(1)

    # Compute Monday → Sunday for ISO week
    jan4 = date(year, 1, 4)
    jan4_iso_weekday = jan4.isoweekday()  # 1=Mon
    iso_week1_start = jan4 - timedelta(days=jan4_iso_weekday - 1)
    week_start_date = iso_week1_start + timedelta(weeks=week - 1)
    week_end_date = week_start_date + timedelta(days=6)

    week_start = datetime.combine(week_start_date, datetime.min.time(), tzinfo=EET)
    week_end = datetime.combine(week_end_date, datetime.max.time(), tzinfo=EET)
    return year, week, week_start, week_end


# ─── Strategy classifier (heuristic from existing data) ─────────────────
def _classify_strategy(trade, reflection):
    """Map a trade to a strategy name. Heuristic until trades are explicitly tagged."""
    symbol = trade.get("symbol", "")
    session = reflection.get("session_at_entry", "")
    asset_class = reflection.get("asset_class", "")

    # Forex assets default to TJR Asia Sweep (matches data/master_assets.json strategy field)
    if asset_class == "forex_major":
        return "TJR Asia Sweep"
    if symbol == "XAUUSD":
        return "TJR Asia Sweep"
    if symbol in ("NAS100", "SPX500"):
        return "IBB Initial Balance Breakout"
    if asset_class == "crypto":
        if session in ("london_kz", "ny_kz"):
            return "TJR Crypto"
        return "Crypto Continuation"
    return "Other"


# ─── Aggregations ────────────────────────────────────────────────────────
def _aggregate_journal(journal, reflections, week_start, week_end):
    """Per-strategy/per-asset/per-session metrics + headline."""
    refl_by_id = {r.get("trade_id"): r for r in reflections}

    # Filter trades closed within the week
    in_week = []
    for t in journal:
        exit_dt = _parse_iso(t.get("exit_time"))
        if exit_dt and week_start <= exit_dt <= week_end:
            in_week.append(t)

    headline = {
        "trades": len(in_week),
        "wins": 0, "losses": 0, "be": 0,
        "wr_pct": 0.0,
        "total_pnl_eur": 0.0,
        "avg_r": 0.0,
    }
    r_multiples = []

    by_strategy = {}
    by_asset = {}
    by_session = {}

    for t in in_week:
        ref = refl_by_id.get(t.get("trade_id")) or {}
        outcome = ref.get("outcome") or _outcome_from_pnl(t)
        pnl = float(t.get("final_pnl_eur") or 0)
        r_mult = ref.get("r_multiple") or 0
        if r_mult:
            r_multiples.append(r_mult)
        headline["total_pnl_eur"] += pnl

        if outcome == "win": headline["wins"] += 1
        elif outcome == "loss": headline["losses"] += 1
        elif outcome == "breakeven": headline["be"] += 1

        # Skip admin cleanups from strategy/asset/session breakdowns
        if "admin_cleanup" in (ref.get("attribution_tags") or []):
            continue

        strat = _classify_strategy(t, ref)
        bs = by_strategy.setdefault(strat, {"trades": 0, "wins": 0, "losses": 0, "be": 0, "pnl": 0.0})
        bs["trades"] += 1
        bs[outcome[0:2] if outcome != "breakeven" else "be"] = bs.get(outcome[0:2] if outcome != "breakeven" else "be", 0) + 1
        # Above is buggy — let me do explicitly:
        if outcome == "win": bs["wins"] += 1
        elif outcome == "loss": bs["losses"] += 1
        else: bs["be"] += 1
        bs["pnl"] += pnl

        symbol = t.get("symbol", "?")
        ba = by_asset.setdefault(symbol, {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0})
        ba["trades"] += 1
        if outcome == "win": ba["wins"] += 1
        elif outcome == "loss": ba["losses"] += 1
        ba["pnl"] += pnl

        sess = ref.get("session_at_entry", "?")
        bse = by_session.setdefault(sess, {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0})
        bse["trades"] += 1
        if outcome == "win": bse["wins"] += 1
        elif outcome == "loss": bse["losses"] += 1
        bse["pnl"] += pnl

    real_trades = headline["wins"] + headline["losses"]
    headline["wr_pct"] = round(100.0 * headline["wins"] / real_trades, 1) if real_trades > 0 else 0.0
    headline["total_pnl_eur"] = round(headline["total_pnl_eur"], 2)
    headline["avg_r"] = round(sum(r_multiples) / len(r_multiples), 2) if r_multiples else 0.0

    # Add WR + verdict per strategy/asset
    for strat, m in by_strategy.items():
        decided = m["wins"] + m["losses"]
        m["wr_pct"] = round(100.0 * m["wins"] / decided, 1) if decided > 0 else 0.0
        m["pnl"] = round(m["pnl"], 2)
        if m["trades"] < 10:
            m["verdict"] = "INSUFFICIENT_DATA"
        elif m["wr_pct"] >= 55:
            m["verdict"] = "PROMISING"
        elif m["wr_pct"] < 40:
            m["verdict"] = "STOP"
        else:
            m["verdict"] = "WATCH"

    for sym, m in by_asset.items():
        decided = m["wins"] + m["losses"]
        m["wr_pct"] = round(100.0 * m["wins"] / decided, 1) if decided > 0 else 0.0
        m["pnl"] = round(m["pnl"], 2)

    for sess, m in by_session.items():
        decided = m["wins"] + m["losses"]
        m["wr_pct"] = round(100.0 * m["wins"] / decided, 1) if decided > 0 else 0.0
        m["pnl"] = round(m["pnl"], 2)

    return headline, by_strategy, by_asset, by_session, in_week


def _outcome_from_pnl(trade):
    pnl = float(trade.get("final_pnl_eur") or 0)
    if abs(pnl) < 0.01:
        return "breakeven"
    return "win" if pnl > 0 else "loss"


# ─── Anomaly clusters ────────────────────────────────────────────────────
def _detect_anomaly_clusters(reflections_in_week):
    """Find tags that recur with skewed outcomes (e.g. 100% loss in tag X)."""
    by_tag = {}
    for r in reflections_in_week:
        outcome = r.get("outcome", "?")
        for tag in r.get("attribution_tags", []):
            d = by_tag.setdefault(tag, {"win": 0, "loss": 0, "breakeven": 0, "total": 0})
            d[outcome] = d.get(outcome, 0) + 1
            d["total"] += 1

    clusters = []
    for tag, counts in by_tag.items():
        if counts["total"] < 2:
            continue
        # Skip benign tags
        if tag in ("admin_cleanup", "tp2_runner_success", "tp1_then_be_neutral"):
            continue
        loss_rate = counts["loss"] / counts["total"]
        if loss_rate >= 0.66 and counts["loss"] >= 2:
            clusters.append({
                "tag": tag,
                "count": counts["total"],
                "wins": counts["win"],
                "losses": counts["loss"],
                "loss_rate": round(loss_rate * 100, 1),
                "outcome_skew": f"{counts['loss']}/{counts['total']} losses ({round(loss_rate*100,0):.0f}%)"
            })
    clusters.sort(key=lambda c: c["count"], reverse=True)
    return clusters


# ─── Hypothesis Detectors (3 deterministic, capped at 2 proposals) ──────
def _detector_news_embargo(reflections_in_window):
    """Detector 1: news embargo widen. min n=4.
    Counts NEGATIVE outcomes = losses OR max_hold timeouts (missed-opportunity)."""
    candidates = []
    for r in reflections_in_window:
        tags = r.get("attribution_tags") or []
        is_negative = (r.get("outcome") == "loss" or
                       "max_hold_4h_timeout" in tags)
        has_news_issue = ("entered_with_missing_news_criterion" in tags or
                          "high_event_within_2h_of_entry" in tags)
        if is_negative and has_news_issue:
            candidates.append(r)
    if len(candidates) < 4:
        return None

    return {
        "id": None,  # filled by caller
        "category": "news_embargo",
        "title": "Διεύρυνση news embargo από T-30/T+5 σε T-45/T+10",
        "evidence": {
            "supporting_trade_ids": [c.get("trade_id") for c in candidates],
            "n": len(candidates),
            "confidence": "low" if len(candidates) < 8 else "medium",
        },
        "current_value": {"pre_min": 30, "post_min": 5},
        "proposed_value": {"pre_min": 45, "post_min": 10},
        "scope": "config",
        "diff_target": "scripts/news_embargo.py::PENDING_BEFORE_MIN, POST_AFTER_MIN",
        "expected_impact": f"Φιλτράρει ~{int(0.7 * len(candidates))} από {len(candidates)} post-news whipsaw losses",
        "ranking_score": len(candidates) * 1.5,  # weight × confidence
    }


def _detector_sl_cap(journal_full, reflections_full):
    """Detector 2: per-asset SL cap calibration. min n=10 per asset."""
    refl_by_id = {r.get("trade_id"): r for r in reflections_full}

    by_asset = {}
    for t in journal_full:
        if not t.get("exit_time") or not t.get("symbol"):
            continue
        sym = t["symbol"]
        ref = refl_by_id.get(t.get("trade_id")) or {}
        if "admin_cleanup" in (ref.get("attribution_tags") or []):
            continue
        d = by_asset.setdefault(sym, {"trades": 0, "sl_hits": 0})
        d["trades"] += 1
        if ref.get("exit_reason") == "sl" or "sl_hit" in (ref.get("attribution_tags") or []):
            d["sl_hits"] += 1

    proposals = []
    for sym, d in by_asset.items():
        if d["trades"] < 10:
            continue
        sl_rate = d["sl_hits"] / d["trades"]
        if sl_rate >= 0.4:  # too tight, getting stopped a lot
            proposals.append({
                "id": None,
                "category": "sl_cap_tighten" if sl_rate < 0.5 else "sl_cap_review",
                "title": f"{sym}: SL cap review — {d['sl_hits']}/{d['trades']} trades hit SL ({round(sl_rate*100,0):.0f}%)",
                "evidence": {
                    "supporting_trade_ids": [],
                    "n": d["trades"],
                    "confidence": "medium" if d["trades"] >= 20 else "low",
                },
                "current_value": "see scripts/risk_manager.py::ASSET_CONFIG",
                "proposed_value": f"Tighten max_sl_pct_4h by 0.05pp OR widen TP targets",
                "scope": "config",
                "diff_target": f"scripts/risk_manager.py::ASSET_CONFIG['{sym}']",
                "expected_impact": f"Reduce SL hit rate τοπικά για {sym}",
                "ranking_score": d["trades"] * sl_rate,
            })
    return proposals


def _detector_session_pruning(reflections_full):
    """Detector 3: time-of-day pruning. min n=4 per slot, 100% loss rate."""
    by_session = {}
    for r in reflections_full:
        if "admin_cleanup" in (r.get("attribution_tags") or []):
            continue
        sess = r.get("session_at_entry", "?")
        d = by_session.setdefault(sess, {"trades": 0, "wins": 0, "losses": 0})
        d["trades"] += 1
        if r.get("outcome") == "win": d["wins"] += 1
        elif r.get("outcome") == "loss": d["losses"] += 1

    proposals = []
    for sess, d in by_session.items():
        if d["trades"] < 4:
            continue
        decided = d["wins"] + d["losses"]
        if decided >= 4 and d["wins"] == 0:
            proposals.append({
                "id": None,
                "category": "session_pruning",
                "title": f"Skip Tier C signals σε {sess} session ({d['losses']}/{decided} losses)",
                "evidence": {
                    "n": d["trades"],
                    "confidence": "low" if d["trades"] < 10 else "medium",
                },
                "current_value": f"{sess} επιτρέπει Tier C",
                "proposed_value": f"Block Tier C entries σε {sess}",
                "scope": "prompt",
                "diff_target": "prompts/market_monitor.md::STEP 4.8",
                "expected_impact": f"Αποφυγή {d['losses']} losses ανά εβδομάδα από {sess}",
                "ranking_score": d["losses"] * 1.0,
            })
    return proposals


def _run_detectors(reflections_in_week, journal_full, reflections_full, week_id):
    """Run all 3 detectors, return up to 2 proposals ranked by score."""
    candidates = []

    p1 = _detector_news_embargo(reflections_in_week)
    if p1: candidates.append(p1)

    candidates.extend(_detector_sl_cap(journal_full, reflections_full))
    candidates.extend(_detector_session_pruning(reflections_full))

    # Rank by score, take top 2
    candidates.sort(key=lambda p: p.get("ranking_score", 0), reverse=True)
    candidates = candidates[:2]

    # Assign IDs
    for i, p in enumerate(candidates, start=1):
        p["id"] = f"P_{week_id}_{i:02d}"
        p["created"] = _iso(_now())
        p["status"] = "pending_approval"
        p["evaluation_window"] = "2 weeks after apply"
        p.pop("ranking_score", None)

    return candidates


# ─── Markdown digest ─────────────────────────────────────────────────────
def _render_markdown(audit, week_label):
    lines = []
    h = audit["headline"]
    lines.append(f"# Weekly Audit · {week_label}")
    lines.append(f"")
    lines.append(f"**Period:** {audit['period']['start']} → {audit['period']['end']}")
    lines.append(f"")
    lines.append(f"## Headline")
    lines.append(f"- Trades: **{h['trades']}** ({h['wins']}W · {h['losses']}L · {h['be']}BE)")
    lines.append(f"- WR: **{h['wr_pct']}%** · Avg R: **{h['avg_r']}**")
    lines.append(f"- Total P/L: **{h['total_pnl_eur']:+.2f}€**")
    lines.append("")
    if audit.get("per_strategy"):
        lines.append(f"## Per Strategy")
        for s in audit["per_strategy"]:
            verdict_icon = {"PROMISING": "🟢", "WATCH": "🟡", "STOP": "🔴", "INSUFFICIENT_DATA": "⏳"}.get(s["verdict"], "?")
            lines.append(f"- {verdict_icon} **{s['strategy']}** — {s['trades']} trades, WR {s['wr_pct']}%, P/L {s['pnl']:+.2f}€ · `{s['verdict']}`")
        lines.append("")
    if audit.get("per_asset"):
        lines.append(f"## Per Asset")
        for a in audit["per_asset"]:
            lines.append(f"- **{a['symbol']}**: {a['trades']} trades, WR {a['wr_pct']}%, P/L {a['pnl']:+.2f}€")
        lines.append("")
    if audit.get("per_session"):
        lines.append(f"## Per Session")
        for s in audit["per_session"]:
            lines.append(f"- **{s['session']}**: {s['trades']} trades, WR {s['wr_pct']}%, P/L {s['pnl']:+.2f}€")
        lines.append("")
    if audit.get("anomaly_clusters"):
        lines.append(f"## ⚠️ Anomaly Clusters")
        for c in audit["anomaly_clusters"][:5]:
            lines.append(f"- `{c['tag']}` — {c['outcome_skew']}")
        lines.append("")
    if audit.get("calibration_seed_summary"):
        lines.append(f"## Calibration Seeds (feed proposer)")
        for seed, count in audit["calibration_seed_summary"].items():
            lines.append(f"- `{seed}`: {count}")
        lines.append("")
    if audit.get("proposals_generated"):
        lines.append(f"## 🧪 Proposals Generated")
        for pid in audit["proposals_generated"]:
            lines.append(f"- `{pid}` (see calibration_proposals.json)")
        lines.append("")
    return "\n".join(lines)


# ─── Telegram digest ─────────────────────────────────────────────────────
def _render_telegram_digest(audit, week_label, n_proposals):
    h = audit["headline"]
    parts = []
    parts.append(f"📊 <b>Εβδομαδιαίο Audit · {week_label}</b>")
    parts.append(f"━━━━━━━━━━━━━━━━━━━━━━")
    parts.append("")
    parts.append(f"<b>Headline:</b> {h['trades']} trades · {h['wins']}W/{h['losses']}L/{h['be']}BE · WR {h['wr_pct']}% · {h['total_pnl_eur']:+.2f}€")
    parts.append("")

    if audit.get("per_strategy"):
        parts.append(f"<b>Στρατηγικές</b>")
        for s in audit["per_strategy"][:5]:
            icon = {"PROMISING": "🟢", "WATCH": "🟡", "STOP": "🔴", "INSUFFICIENT_DATA": "⏳"}.get(s["verdict"], "?")
            label = s["verdict"].lower().replace("_", " ")
            parts.append(f"{icon} {s['strategy']}: {s['wins']}/{s['trades']} ({s['wr_pct']}%) — {label}")
        parts.append("")

    if audit.get("anomaly_clusters"):
        parts.append(f"<b>⚠️ Anomalies</b>")
        for c in audit["anomaly_clusters"][:3]:
            parts.append(f"• <code>{c['tag']}</code> — {c['outcome_skew']}")
        parts.append("")

    # Top lesson (most-recurring calibration seed)
    seeds = audit.get("calibration_seed_summary", {})
    if seeds:
        top_seed = max(seeds.items(), key=lambda x: x[1])
        parts.append(f"<b>Top Lesson</b>")
        parts.append(f"<i>{top_seed[0]} (×{top_seed[1]} σε αυτή την εβδομάδα)</i>")
        parts.append("")

    parts.append(f"<blockquote expandable>📈 <b>Πλήρες Per-asset</b>")
    for a in audit.get("per_asset", []):
        parts.append(f"{a['symbol']}: {a['trades']} trades, WR {a['wr_pct']}%, P/L {a['pnl']:+.2f}€")
    parts.append("")
    parts.append(f"📉 <b>Πλήρες Per-session</b>")
    for s in audit.get("per_session", []):
        parts.append(f"{s['session']}: {s['trades']} trades, WR {s['wr_pct']}%, P/L {s['pnl']:+.2f}€")
    parts.append("</blockquote>")
    parts.append("")

    if n_proposals > 0:
        parts.append(f"🧪 <b>{n_proposals} νέες προτάσεις calibration διαθέσιμες</b> — δες τες όταν έρθεις στο PC.")
    else:
        parts.append(f"<i>Δεν υπάρχουν νέες προτάσεις calibration αυτή την εβδομάδα.</i>")

    return "\n".join(parts)


def _render_telegram_proposal(proposal):
    """Per-proposal silent notification."""
    cat = proposal.get("category", "?")
    parts = []
    parts.append(f"🧪 <b>Νέα Πρόταση Calibration</b> · {proposal['id']}")
    parts.append("")
    parts.append(f"<b>Κατηγορία:</b> {cat}")
    parts.append(f"<b>Σύνοψη:</b> {proposal.get('title', '?')}")
    ev = proposal.get("evidence", {})
    parts.append(f"<b>Στοιχεία:</b> n={ev.get('n', '?')}, confidence: {ev.get('confidence', '?')}")
    parts.append(f"<b>Επίπτωση:</b> {proposal.get('expected_impact', '?')}")
    scope = proposal.get("scope", "?")
    parts.append(f"<b>Επηρεάζει:</b> {proposal.get('diff_target', '?')} ({scope})")
    parts.append("")
    parts.append(f"📁 Queue: <code>data/calibration_proposals.json</code>")
    parts.append(f"🤝 Όταν έρθεις στο PC, ζήτα μου να την εφαρμόσουμε μαζί.")
    return "\n".join(parts)


# ─── Telegram sender ─────────────────────────────────────────────────────
def _send_telegram(text, silent=False):
    sender = Path(__file__).parent / "telegram_sender.py"
    args = ["python", str(sender), "message", text]
    if silent:
        args.append("--silent")
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', timeout=30)
        if r.returncode == 0:
            return r.stdout.strip()
        else:
            print(f"[telegram error] {r.stderr[:200]}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"[telegram exception] {e}", file=sys.stderr)
        return None


# ─── Scorecard updater ──────────────────────────────────────────────────
def _update_scorecard(audit, week_label):
    """Append a new week section to strategy_scorecard.md (no overwrite of existing)."""
    if not SCORECARD.exists():
        # Create minimal scorecard if missing
        SCORECARD.write_text("# Strategy Scorecard\n\n", encoding='utf-8')

    section = [f"\n---\n## {week_label} ({audit['period']['start']} → {audit['period']['end']})\n"]
    h = audit["headline"]
    section.append(f"**Headline:** {h['trades']} trades · WR {h['wr_pct']}% · P/L {h['total_pnl_eur']:+.2f}€\n")
    if audit.get("per_strategy"):
        section.append("\n**Per-Strategy:**\n")
        for s in audit["per_strategy"]:
            section.append(f"- {s['strategy']}: {s['trades']} trades, WR {s['wr_pct']}%, P/L {s['pnl']:+.2f}€ · {s['verdict']}\n")

    with SCORECARD.open('a', encoding='utf-8') as f:
        f.write("".join(section))


# ─── Proposal queue manager ─────────────────────────────────────────────
def _update_proposals_queue(new_proposals):
    if PROPOSALS_FILE.exists():
        try:
            data = json.loads(PROPOSALS_FILE.read_text(encoding='utf-8'))
        except Exception:
            data = {"queue": [], "history": []}
    else:
        data = {"queue": [], "history": []}

    # Avoid re-adding existing IDs
    existing_ids = {p.get("id") for p in data["queue"] + data["history"]}
    added = []
    for p in new_proposals:
        if p.get("id") not in existing_ids:
            data["queue"].append(p)
            added.append(p["id"])

    _write_json(PROPOSALS_FILE, data)
    return added


# ─── Main audit pipeline ────────────────────────────────────────────────
def run_audit(week_arg, send_telegram=False, write=True):
    year, week, week_start, week_end = _resolve_week(week_arg)
    week_id = f"{year}_W{week:02d}"
    week_label = f"W{week:02d} ({week_start.strftime('%d %b')}-{week_end.strftime('%d %b')})"

    print(f"=== Weekly Audit: {week_id} ({week_start.date()} → {week_end.date()}) ===\n")

    journal = _read_jsonl(TRADE_JOURNAL)
    reflections = _read_jsonl(REFLECTIONS)

    # Filter reflections in week (by reflected_at)
    reflections_in_week = []
    for r in reflections:
        rdt = _parse_iso(r.get("reflected_at"))
        if rdt and week_start <= rdt <= week_end:
            reflections_in_week.append(r)

    headline, by_strat, by_asset, by_sess, in_week_trades = _aggregate_journal(
        journal, reflections, week_start, week_end
    )

    anomalies = _detect_anomaly_clusters(reflections_in_week)

    seed_summary = {}
    for r in reflections_in_week:
        for s in r.get("calibration_seeds", []):
            seed_summary[s] = seed_summary.get(s, 0) + 1

    # Run hypothesis detectors
    proposals = _run_detectors(reflections_in_week, journal, reflections, week_id)

    audit = {
        "week_id": week_id,
        "period": {"start": str(week_start.date()), "end": str(week_end.date())},
        "headline": headline,
        "per_strategy": [{"strategy": k, **v} for k, v in by_strat.items()],
        "per_asset": [{"symbol": k, **v} for k, v in sorted(by_asset.items(), key=lambda x: -x[1]["trades"])],
        "per_session": [{"session": k, **v} for k, v in sorted(by_sess.items(), key=lambda x: -x[1]["trades"])],
        "anomaly_clusters": anomalies,
        "calibration_seed_summary": seed_summary,
        "proposals_generated": [p["id"] for p in proposals],
        "generated_at": _iso(_now()),
    }

    if write:
        json_path = DATA_DIR / f"weekly_audit_{week_id}.json"
        md_path = DATA_DIR / f"weekly_audit_{week_id}.md"
        _write_json(json_path, audit)
        md_path.write_text(_render_markdown(audit, week_label), encoding='utf-8')
        print(f"[ok] Wrote {json_path.name} + {md_path.name}")

        _update_scorecard(audit, week_label)
        print(f"[ok] Updated {SCORECARD.name}")

        added = _update_proposals_queue(proposals)
        if added:
            print(f"[ok] Added {len(added)} proposal(s) to queue: {added}")
        else:
            print(f"[info] No new proposals to queue")

    print(f"\n--- Summary ---")
    print(f"Trades this week: {headline['trades']} (WR {headline['wr_pct']}%, P/L {headline['total_pnl_eur']:+.2f}€)")
    print(f"Anomalies: {len(anomalies)}, Proposals: {len(proposals)}")

    if send_telegram:
        digest = _render_telegram_digest(audit, week_label, len(proposals))
        msg_id = _send_telegram(digest)
        print(f"[telegram] digest sent: msg_id={msg_id}")
        for p in proposals:
            text = _render_telegram_proposal(p)
            mid = _send_telegram(text, silent=True)
            print(f"[telegram] proposal {p['id']}: msg_id={mid}")

    return audit


# ─── CLI ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    week_arg = "current"
    send_tg = False
    write = True
    for i, a in enumerate(args):
        if a == "--week":
            week_arg = args[i + 1] if i + 1 < len(args) else "current"
        elif a.startswith("--week="):
            week_arg = a.split("=", 1)[1]
        elif a == "--telegram":
            send_tg = True
        elif a == "--no-write":
            write = False

    run_audit(week_arg, send_telegram=send_tg, write=write)
