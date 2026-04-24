#!/usr/bin/env python3
"""
GOLD TACTIC — Kill Zone Tracker
Detects upcoming/active kill zones and alerts via Telegram.

Kill Zones (EET = UTC+3):
  Asia KZ:      02:00–05:00 EET  (sweeps + reversals)
  London Open:  10:00–11:00 EET  (trend continuation)
  NY Open:      16:00–17:00 EET  (highest volatility)
  London Close: 19:00–20:00 EET  (fakeouts)

Sends alert if:
  - We are 15 min BEFORE a kill zone starts, OR
  - We just entered a kill zone (within first 5 min)

Throttle: 1 alert per kill zone per day (data/killzone_log.json)

Usage:
  python kill_zone_tracker.py          # Check and alert if needed
  python kill_zone_tracker.py --status # Print current status only
"""

import sys
import json
from datetime import datetime, date
from pathlib import Path

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

DATA_DIR = Path(__file__).parent.parent / "data"
LOG_FILE  = DATA_DIR / "killzone_log.json"

sys.path.insert(0, str(Path(__file__).parent))

# Kill zones: name → (start_hour_EET, end_hour_EET, description)
KILL_ZONES = {
    "Asia":         (2,  5,  "🌏 Asia KZ — Sweeps & reversals (02:00–05:00)"),
    "LondonOpen":   (10, 11, "🇬🇧 London Open — Trend continuation (10:00–11:00)"),
    "NYOpen":       (16, 17, "🗽 NY Open — Max volatility (16:00–17:00)"),
    "LondonClose":  (19, 20, "🔔 London Close — Fakeout zone (19:00–20:00)"),
}

ALERT_BEFORE_MIN = 15   # Alert N minutes before KZ starts
ALERT_ENTRY_MIN  = 5    # Alert if within first N minutes of KZ


def load_log():
    if not LOG_FILE.exists():
        return {}
    try:
        return json.loads(LOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_log(log):
    LOG_FILE.write_text(json.dumps(log, indent=2), encoding="utf-8")


def already_alerted(log, kz_name):
    """True if we already alerted for this kill zone today."""
    today = date.today().isoformat()
    return log.get(today, {}).get(kz_name) == "alerted"


def mark_alerted(log, kz_name):
    today = date.today().isoformat()
    if today not in log:
        log[today] = {}
    log[today][kz_name] = "alerted"
    # Keep only last 7 days
    all_dates = sorted(log.keys())
    for old in all_dates[:-7]:
        del log[old]


def get_kz_status(now_hour, now_min):
    """Return list of (kz_name, status, description) for current time.
    status: 'approaching' | 'active' | None
    """
    results = []
    now_total = now_hour * 60 + now_min

    for name, (start_h, end_h, desc) in KILL_ZONES.items():
        start_min = start_h * 60
        end_min   = end_h   * 60

        # Check if approaching (within ALERT_BEFORE_MIN)
        mins_until = start_min - now_total
        if 0 < mins_until <= ALERT_BEFORE_MIN:
            results.append((name, "approaching", desc, mins_until))
            continue

        # Check if just entered (within first ALERT_ENTRY_MIN)
        mins_into = now_total - start_min
        if 0 <= mins_into < ALERT_ENTRY_MIN and now_total < end_min:
            results.append((name, "active", desc, mins_into))

    return results


def read_selected_assets():
    """Read selected assets for context in the alert."""
    sel_file = DATA_DIR / "selected_assets.json"
    if not sel_file.exists():
        return []
    try:
        sel = json.loads(sel_file.read_text(encoding="utf-8"))
        return sel.get("selected", [])
    except Exception:
        return []


def build_message(kz_name, status, desc, mins, selected):
    """Build Telegram alert message for a kill zone."""
    if status == "approaching":
        header = f"⏰ <b>Kill Zone σε {mins} λεπτά</b>"
    else:
        header = f"🔥 <b>Kill Zone ΑΝΟΙΧΤΟ τώρα</b>"

    # Find relevant assets for this KZ
    kz_assets = []
    for s in selected:
        sym = s.get("symbol", "")
        bias = s.get("direction_bias", "")
        trs  = s.get("trs", "?")
        # All selected assets are relevant for London/NY opens
        kz_assets.append(f"• {sym} ({bias}) TRS {trs}/5")

    assets_str = "\n".join(kz_assets) if kz_assets else "• Χωρίς επιλεγμένα assets"

    msg = (
        f"{header}\n"
        f"{desc}\n\n"
        f"<b>Επιλεγμένα assets:</b>\n"
        f"{assets_str}"
    )
    return msg


def main():
    status_only = "--status" in sys.argv

    # EET = UTC+3
    now = datetime.utcnow()
    now_eet_hour = (now.hour + 3) % 24
    now_eet_min  = now.minute

    if status_only:
        print(f"Current EET time: {now_eet_hour:02d}:{now_eet_min:02d}")
        for name, (sh, eh, desc) in KILL_ZONES.items():
            total = now_eet_hour * 60 + now_eet_min
            in_kz = (sh * 60) <= total < (eh * 60)
            mins_until = sh * 60 - total
            state = "ACTIVE" if in_kz else (f"in {mins_until}min" if 0 < mins_until <= 60 else "—")
            print(f"  {name:15s}: {desc[:40]}  [{state}]")
        return

    triggers = get_kz_status(now_eet_hour, now_eet_min)

    if not triggers:
        print(f"[{now_eet_hour:02d}:{now_eet_min:02d} EET] No kill zone approaching or active.")
        sys.exit(0)

    log = load_log()
    selected = read_selected_assets()
    sent = 0

    from telegram_sender import send_message
    for kz_name, status, desc, mins in triggers:
        if already_alerted(log, kz_name):
            print(f"[SKIP] {kz_name}: already alerted today")
            continue

        msg = build_message(kz_name, status, desc, mins, selected)
        send_message(msg)
        mark_alerted(log, kz_name)
        print(f"[OK] Alert sent: {kz_name} ({status})")
        sent += 1

    if sent > 0:
        save_log(log)
    else:
        print("No new alerts to send (all already sent today).")


if __name__ == "__main__":
    main()
