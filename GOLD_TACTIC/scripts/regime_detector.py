#!/usr/bin/env python3
"""
GOLD TACTIC — Regime Detector (v7.3 Shared Brain)

Synthesizes data/regime_state.json from quick_scan.json + session_now.json.
Provides a single label (bull / bear / chop / squeeze / calm) plus
conviction, age, VIX tier, F&G label, sentiment direction.

Decay logic:
  - If label unchanged → age_hours += elapsed_since_last_write
  - If label changed → reset age + log regime_changed event

CLI:
  regime_detector.py detect            # Full analysis + atomic write. Exit 2 on label change.
  regime_detector.py current           # 1-line summary for prompt injection.
  regime_detector.py json              # Full JSON to stdout.
  regime_detector.py force-reset --label X    # Manual override.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

DATA_DIR = Path(__file__).parent.parent / "data"
QUICK_SCAN = DATA_DIR / "quick_scan.json"
SESSION_NOW = DATA_DIR / "session_now.json"
REGIME_STATE = DATA_DIR / "regime_state.json"
CYCLE_LOG = DATA_DIR / "cycle_log.jsonl"

EET = timezone(timedelta(hours=3))


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


def _atomic_write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, path)


def _append_jsonl(path: Path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ─── Load source data ────────────────────────────────────────────────────
def _load_quick_scan():
    if not QUICK_SCAN.exists():
        return None
    try:
        return json.loads(QUICK_SCAN.read_text(encoding='utf-8'))
    except Exception:
        return None


def _load_session_now():
    if not SESSION_NOW.exists():
        return None
    try:
        return json.loads(SESSION_NOW.read_text(encoding='utf-8'))
    except Exception:
        return None


def _load_existing_state():
    if not REGIME_STATE.exists():
        return None
    try:
        return json.loads(REGIME_STATE.read_text(encoding='utf-8'))
    except Exception:
        return None


# ─── Detection logic ─────────────────────────────────────────────────────
def _classify_vix_tier(vix_value):
    if vix_value is None:
        return "normal"
    try:
        v = float(vix_value)
    except Exception:
        return "normal"
    if v < 15:
        return "calm"
    if v > 22:
        return "volatile"
    return "normal"


def _classify_fg(fg_value, fg_label):
    label = fg_label
    if not label and fg_value is not None:
        try:
            v = int(fg_value)
        except Exception:
            v = 50
        if v <= 24:
            label = "Extreme Fear"
        elif v <= 44:
            label = "Fear"
        elif v <= 55:
            label = "Neutral"
        elif v <= 74:
            label = "Greed"
        else:
            label = "Extreme Greed"
    return {"value": fg_value, "label": label}


def _detect_label(assets, vix_tier):
    """Return regime label from assets list + vix tier.

    Counts TRENDING vs CHOPPY across assets, cross-checks ADX avg,
    derives directional bias from alignment. Squeeze override if VIX
    very calm AND ADX very low across all.
    """
    if not assets:
        return "calm", 0

    trending = 0
    choppy = 0
    bull_align = 0
    bear_align = 0
    adx_values = []

    for a in assets:
        if a.get("error"):
            continue
        reg = (a.get("regime") or "").upper()
        if "TREND" in reg:
            trending += 1
        elif "CHOP" in reg or "RANGE" in reg:
            choppy += 1
        align = (a.get("alignment") or "").upper()
        if align == "BULL":
            bull_align += 1
        elif align == "BEAR":
            bear_align += 1
        adx = a.get("adx")
        if isinstance(adx, (int, float)) and adx > 0:
            adx_values.append(float(adx))

    total = trending + choppy
    adx_avg = (sum(adx_values) / len(adx_values)) if adx_values else 0.0

    # SQUEEZE override: very calm VIX + low ADX everywhere
    if vix_tier == "calm" and adx_values and max(adx_values) < 18:
        return "squeeze", adx_avg

    # Directional trend: majority TRENDING + majority BULL/BEAR alignment
    if total and trending > choppy and adx_avg >= 25:
        if bull_align > bear_align:
            return "bull", adx_avg
        if bear_align > bull_align:
            return "bear", adx_avg
        return "trend_mixed", adx_avg

    # Chop dominant
    if total and choppy >= trending:
        return "chop", adx_avg

    # Low ADX everywhere → calm
    if adx_avg and adx_avg < 18:
        return "calm", adx_avg

    return "chop", adx_avg


def _classify_sentiment_dir(market_regime, fg_value, vix_tier):
    """Map quick_scan.sentiment.market_regime + F&G + VIX to risk_on/risk_off/mixed."""
    mr = (market_regime or "").upper()
    if mr == "RISK_ON":
        return "risk_on"
    if mr == "RISK_OFF":
        return "risk_off"

    # Synthesize from F&G + VIX
    try:
        v = int(fg_value)
    except Exception:
        v = 50
    if vix_tier == "volatile" and v <= 35:
        return "risk_off"
    if vix_tier == "calm" and v >= 60:
        return "risk_on"
    return "mixed"


def _conviction_for(age_hours, transitions_today):
    if transitions_today >= 2:
        return "low"
    if age_hours < 4:
        return "low"
    if age_hours >= 24:
        return "high"
    return "med"


# ─── Main detect ─────────────────────────────────────────────────────────
def cmd_detect(args):
    qs = _load_quick_scan()
    sn = _load_session_now()
    existing = _load_existing_state()

    if not qs:
        print("[error] quick_scan.json missing or unreadable", file=sys.stderr)
        return 1

    assets = qs.get("assets") or []
    sentiment = qs.get("sentiment") or {}
    vix_value = sentiment.get("vix")
    vix_tier = _classify_vix_tier(vix_value)
    fg = _classify_fg(sentiment.get("fear_greed_value"), sentiment.get("fear_greed_label"))

    label, adx_avg = _detect_label(assets, vix_tier)

    sentiment_dir = _classify_sentiment_dir(
        sentiment.get("market_regime"), fg.get("value"), vix_tier
    )

    now = _now()
    today_str = now.strftime("%Y-%m-%d")

    # Decay computation
    transitions_today = 0
    age_hours = 0.0
    previous_label = None
    since_ts = _iso(now)
    label_changed_this_run = False

    if existing and isinstance(existing, dict):
        prev_regime = existing.get("regime") or {}
        prev_label = prev_regime.get("label")
        prev_since = _parse_iso(prev_regime.get("since_ts"))
        prev_transitions = int(prev_regime.get("transitions_today") or 0)
        prev_transitions_date = (existing.get("transitions_date") or today_str)
        if prev_transitions_date != today_str:
            prev_transitions = 0  # reset daily counter

        if prev_label == label:
            # Stayed the same - preserve previous_label, increment age
            previous_label = prev_regime.get("previous_label") or prev_label
            transitions_today = prev_transitions
            since_ts = prev_regime.get("since_ts") or _iso(now)
            if prev_since:
                age_hours = round((now - prev_since).total_seconds() / 3600.0, 2)
            label_changed_this_run = False
        else:
            # Just changed THIS run
            previous_label = prev_label
            transitions_today = prev_transitions + 1
            since_ts = _iso(now)
            age_hours = 0.0
            label_changed_this_run = True
    else:
        # First write — fresh state
        previous_label = None
        transitions_today = 0
        since_ts = _iso(now)
        age_hours = 0.0
        label_changed_this_run = False  # No prior state to change from

    conviction = _conviction_for(age_hours, transitions_today)

    # DXY state — not in quick_scan currently. Try to extract from selected_assets if present.
    dxy_state = _extract_dxy_state()

    state = {
        "schema_version": "v1",
        "last_updated": _iso(now),
        "last_writer": "regime_detector.py",
        "transitions_date": today_str,
        "regime": {
            "label": label,
            "since_ts": since_ts,
            "age_hours": age_hours,
            "conviction": conviction,
            "previous_label": previous_label,
            "transitions_today": transitions_today,
        },
        "vix": {
            "value": vix_value,
            "tier": vix_tier,
            "trend_4h": "flat",
        },
        "fear_greed": {
            "value": fg.get("value"),
            "label": fg.get("label"),
            "delta_24h": None,
        },
        "sentiment_dir": sentiment_dir,
        "dxy_state": dxy_state,
        "indicator_inputs": {
            "adx_avg": round(adx_avg, 2) if adx_avg else 0.0,
            "regimes_per_asset": {
                a.get("asset"): a.get("regime")
                for a in assets if not a.get("error") and a.get("asset")
            },
            "alignment_count": _count_alignment(assets),
        },
        "session_tier": (sn or {}).get("tier"),
        "decay_rules": {
            "reset_on_label_change": True,
            "conviction_high_after_age_h": 24,
        },
    }

    _atomic_write_json(REGIME_STATE, state)

    # Log regime_changed only if label actually changed THIS run
    if label_changed_this_run:
        try:
            _append_jsonl(CYCLE_LOG, {
                "ts": _iso(now),
                "schedule": "regime_detector",
                "type": "regime_changed",
                "from": previous_label,
                "to": label,
                "trigger": _explain_trigger(adx_avg, vix_tier, label),
                "conviction": conviction,
                "previous_age_h": existing["regime"].get("age_hours") if existing else None,
            })
        except Exception:
            pass

    # Status print
    print(f"[detect] regime={label} conviction={conviction} age={age_hours:.2f}h "
          f"vix={vix_tier} fg={fg.get('label')} dir={sentiment_dir} "
          f"adx_avg={adx_avg:.1f}"
          + (f" (changed from {previous_label})" if label_changed_this_run else ""))

    # Exit code 2 signals label change to callers
    return 2 if label_changed_this_run else 0


def _count_alignment(assets):
    out = {"BULL": 0, "BEAR": 0, "MIXED": 0}
    for a in assets:
        if a.get("error"):
            continue
        align = (a.get("alignment") or "").upper()
        if align in out:
            out[align] += 1
    return out


def _extract_dxy_state():
    """Best-effort: pull DXY snapshot if available in quick_scan or recent live_prices."""
    live = DATA_DIR / "live_prices.json"
    if live.exists():
        try:
            data = json.loads(live.read_text(encoding='utf-8'))
            for entry_key in ("DXY", "DXY_USD", "DX-Y.NYB"):
                if entry_key in data:
                    e = data[entry_key]
                    if isinstance(e, dict):
                        return {
                            "value": e.get("price"),
                            "trend": None,
                            "key_break": None,
                        }
        except Exception:
            pass
    return {"value": None, "trend": None, "key_break": None}


def _explain_trigger(adx_avg, vix_tier, new_label):
    if new_label == "squeeze":
        return f"vix_calm + adx_low (adx_avg={adx_avg:.1f})"
    if new_label in ("bull", "bear"):
        return f"trending_majority + alignment (adx_avg={adx_avg:.1f})"
    if new_label == "chop":
        return f"chop_majority_or_low_adx (adx_avg={adx_avg:.1f})"
    if new_label == "calm":
        return f"low_adx_everywhere (adx_avg={adx_avg:.1f})"
    return "auto"


# ─── current / json commands ────────────────────────────────────────────
def cmd_current(args):
    state = _load_existing_state()
    if not state:
        print("regime: unknown · run `regime_detector.py detect` first")
        return 1
    r = state.get("regime", {})
    vix = state.get("vix", {})
    fg = state.get("fear_greed", {})
    sentiment = state.get("sentiment_dir") or "mixed"
    age = r.get("age_hours", 0)
    label = r.get("label", "?")
    conv = r.get("conviction", "?")
    vix_tier = vix.get("tier", "?")
    fg_label = fg.get("label", "?")
    print(f"{label} · {age:.1f}h · {conv} · vix {vix_tier} · F&G {fg_label} · {sentiment}")
    return 0


def cmd_json(args):
    state = _load_existing_state()
    if not state:
        # Empty placeholder, keeps callers safe
        state = {
            "schema_version": "v1",
            "last_updated": None,
            "regime": {"label": "unknown", "age_hours": 0, "conviction": "low",
                       "previous_label": None, "transitions_today": 0,
                       "since_ts": None},
            "vix": {"value": None, "tier": "normal"},
            "fear_greed": {"value": None, "label": "Neutral"},
            "sentiment_dir": "mixed",
        }
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def cmd_force_reset(args):
    state = {
        "schema_version": "v1",
        "last_updated": _iso(_now()),
        "last_writer": "regime_detector.py force-reset",
        "transitions_date": _now().strftime("%Y-%m-%d"),
        "regime": {
            "label": args.label,
            "since_ts": _iso(_now()),
            "age_hours": 0.0,
            "conviction": "low",
            "previous_label": None,
            "transitions_today": 0,
        },
        "vix": {"value": None, "tier": "normal", "trend_4h": "flat"},
        "fear_greed": {"value": None, "label": "Neutral", "delta_24h": None},
        "sentiment_dir": "mixed",
        "dxy_state": {"value": None, "trend": None, "key_break": None},
        "indicator_inputs": {"adx_avg": 0.0, "regimes_per_asset": {}, "alignment_count": {}},
        "session_tier": None,
        "decay_rules": {"reset_on_label_change": True, "conviction_high_after_age_h": 24},
    }
    _atomic_write_json(REGIME_STATE, state)
    print(f"[force-reset] regime label set to '{args.label}'")
    return 0


# ─── CLI ─────────────────────────────────────────────────────────────────
def _build_parser():
    p = argparse.ArgumentParser(prog="regime_detector.py",
                                description="GOLD TACTIC regime detector")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("detect")
    sub.add_parser("current")
    sub.add_parser("json")

    sp = sub.add_parser("force-reset")
    sp.add_argument("--label", required=True,
                    choices=["bull", "bear", "chop", "squeeze", "calm", "trend_mixed"])

    return p


COMMANDS = {
    "detect": cmd_detect,
    "current": cmd_current,
    "json": cmd_json,
    "force-reset": cmd_force_reset,
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
