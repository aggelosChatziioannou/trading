#!/usr/bin/env python3
"""
GOLD TACTIC — Trading Session Check

Returns current session status (optimal / acceptable / off-hours) για το daily trading.

Kill zones (EET / UTC+3):
  - London Kill Zone:  10:00 – 12:00  (peak London open)
  - NY Kill Zone:       15:30 – 17:30  (London/NY overlap — best liquidity)
  - London Session:     10:00 – 18:00  (acceptable)
  - NY Session:         15:30 – 23:00  (acceptable)
  - Asian / Off:        18:00 – 10:00  (avoid forex; crypto ok on weekends)

CLI usage:
  python session_check.py           # prints JSON
  python session_check.py --line    # prints 1-line Telegram-ready tag

Library usage:
  from session_check import current_session
  s = current_session()  # dict with keys: name, tier, emoji, weekend, message
"""

import json
import os
import sys
from datetime import datetime

if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def current_session(now: datetime | None = None) -> dict:
    now = now or datetime.now()
    hour_frac = now.hour + now.minute / 60.0
    weekday = now.weekday()  # 0=Mon, 6=Sun
    is_weekend = weekday >= 5

    # Kill zones (optimal)
    london_kz = 10.0 <= hour_frac < 12.0
    ny_kz = 15.5 <= hour_frac < 17.5

    # Sessions (acceptable)
    london = 10.0 <= hour_frac < 18.0
    ny = 15.5 <= hour_frac < 23.0

    if is_weekend:
        return {
            "name": "Σαββατοκύριακο",
            "tier": "crypto_only",
            "emoji": "🏖️",
            "weekend": True,
            "optimal": False,
            "message": "Crypto μόνο — forex/indices κλειστά",
        }

    if london_kz and ny_kz:
        return {
            "name": "London/NY Overlap",
            "tier": "optimal",
            "emoji": "🔥",
            "weekend": False,
            "optimal": True,
            "message": "Peak liquidity — optimal για Tier C signals",
        }

    if london_kz:
        return {
            "name": "London Kill Zone",
            "tier": "optimal",
            "emoji": "🎯",
            "weekend": False,
            "optimal": True,
            "message": "Optimal window — Tier C signals ενεργά",
        }

    if ny_kz:
        return {
            "name": "NY Kill Zone",
            "tier": "optimal",
            "emoji": "🎯",
            "weekend": False,
            "optimal": True,
            "message": "Optimal window — Tier C signals ενεργά",
        }

    if london or ny:
        return {
            "name": "London Session" if london else "NY Session",
            "tier": "acceptable",
            "emoji": "✅",
            "weekend": False,
            "optimal": False,
            "message": "Acceptable — signals OK αλλά όχι peak",
        }

    return {
        "name": "Asian / Off-hours",
        "tier": "off",
        "emoji": "🌙",
        "weekend": False,
        "optimal": False,
        "message": "Εκτός kill zones — μόνο παρακολούθηση, όχι Tier C",
    }


def session_tag(s: dict | None = None) -> str:
    """One-line HTML tag for Telegram messages."""
    s = s or current_session()
    return f"{s['emoji']} <b>{s['name']}</b> · {s['message']}"


def main():
    s = current_session()
    if "--line" in sys.argv:
        print(session_tag(s))
    else:
        print(json.dumps(s, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
