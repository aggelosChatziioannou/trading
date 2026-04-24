#!/usr/bin/env python3
"""
GOLD TACTIC — Risk Meter (#12)
Composite 0-100 risk score from VIX, Fear&Greed, news density, ADR consumed.
Writes: data/risk_meter.json. Sends Telegram if HIGH (>70).

Usage:
  python risk_meter.py          # Calculate and save
  python risk_meter.py --alert  # Also send Telegram summary
"""

import sys
import json
from datetime import datetime
from pathlib import Path

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

DATA_DIR    = Path(__file__).parent.parent / "data"
OUTPUT_FILE = DATA_DIR / "risk_meter.json"
sys.path.insert(0, str(Path(__file__).parent))


def score_vix(vix):
    """VIX contribution: 0-30 pts."""
    if vix is None:
        return 10, "VIX: N/A (+10)"
    if vix > 35:
        return 30, f"VIX {vix} PANIC (+30)"
    if vix > 25:
        return 20, f"VIX {vix} elevata (+20)"
    if vix > 18:
        return 10, f"VIX {vix} moderate (+10)"
    return 0,  f"VIX {vix} low (+0)"


def score_fear_greed(fg):
    """Fear&Greed contribution: 0-25 pts."""
    if fg is None:
        return 10, "F&G: N/A (+10)"
    if fg <= 20:
        return 25, f"F&G {fg} Extreme Fear (+25)"
    if fg <= 35:
        return 15, f"F&G {fg} Fear (+15)"
    if fg >= 80:
        return 15, f"F&G {fg} Extreme Greed (+15)"
    if fg >= 65:
        return 5,  f"F&G {fg} Greed (+5)"
    return 0, f"F&G {fg} neutral (+0)"


def score_events(calendar):
    """High-impact events today: 0-25 pts."""
    if not calendar:
        return 0, "Events: N/A (+0)"
    high = [e for e in calendar.get("events", []) if e.get("impact") == "HIGH"]
    count = len(high)
    if count >= 3:
        return 25, f"{count} HIGH events (+25)"
    if count == 2:
        return 15, f"{count} HIGH events (+15)"
    if count == 1:
        return 8,  f"{count} HIGH event (+8)"
    return 0, "No HIGH events (+0)"


def score_adr(quick_scan):
    """ADR consumed for selected assets: 0-20 pts."""
    if not quick_scan:
        return 0, "ADR: N/A (+0)"
    assets = quick_scan.get("assets", [])
    high_adr = [a for a in assets if (a.get("adr_consumed_pct") or 0) > 80]
    if len(high_adr) >= 2:
        return 20, f"{len(high_adr)} assets ADR>80% (+20)"
    if len(high_adr) == 1:
        return 10, f"{len(high_adr)} asset ADR>80% (+10)"
    return 0, "ADR normal (+0)"


def main():
    send_alert = "--alert" in sys.argv

    # Load data sources
    sentiment, calendar, quick_scan = {}, {}, {}
    try:
        qs = json.loads((DATA_DIR / "quick_scan.json").read_text(encoding="utf-8"))
        sentiment  = qs.get("sentiment", {})
        quick_scan = qs
    except Exception:
        pass
    try:
        calendar = json.loads((DATA_DIR / "economic_calendar.json").read_text(encoding="utf-8"))
    except Exception:
        pass

    vix = sentiment.get("vix")
    fg  = sentiment.get("fear_greed_value")

    # Score components
    s_vix,    r_vix    = score_vix(vix)
    s_fg,     r_fg     = score_fear_greed(fg)
    s_events, r_events = score_events(calendar)
    s_adr,    r_adr    = score_adr(quick_scan)

    total = s_vix + s_fg + s_events + s_adr
    total = min(total, 100)

    if total >= 75:
        level, icon = "ΥΨΗΛΟΣ",   "🔴"
        advice = "Μειωμένο μέγεθος θέσεων, περισσότερη επιβεβαίωση"
    elif total >= 50:
        level, icon = "ΜΕΤΡΙΟΣ",  "🟡"
        advice = "Κανονικό μέγεθος, προσοχή σε news"
    else:
        level, icon = "ΧΑΜΗΛΟΣ",  "🟢"
        advice = "Ευνοϊκές συνθήκες, κανονική εκτέλεση"

    result = {
        "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_score": total,
        "level":       level,
        "components": {
            "vix":    {"score": s_vix,    "reason": r_vix},
            "fg":     {"score": s_fg,     "reason": r_fg},
            "events": {"score": s_events, "reason": r_events},
            "adr":    {"score": s_adr,    "reason": r_adr},
        },
        "advice": advice,
    }
    OUTPUT_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{icon} Risk Meter: {total}/100 ({level})")
    print(f"  {r_vix}")
    print(f"  {r_fg}")
    print(f"  {r_events}")
    print(f"  {r_adr}")
    print(f"  → {advice}")

    if send_alert and total >= 70:
        msg = (
            f"{icon} <b>Risk Meter: {total}/100 ({level})</b>\n\n"
            f"• {r_vix}\n"
            f"• {r_fg}\n"
            f"• {r_events}\n"
            f"• {r_adr}\n\n"
            f"<i>→ {advice}</i>"
        )
        from telegram_sender import send_message
        send_message(msg)
        print("[OK] Risk alert sent")


if __name__ == "__main__":
    main()
