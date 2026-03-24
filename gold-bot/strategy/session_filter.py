"""Session and news filters - ICT standard killzones.

Change 5: Proper ICT killzones from mentorship + CME volume data.
Asia = range only, London/NY AM/NY PM = trade windows.
Silver Bullet windows tracked for confluence bonus.
"""
from __future__ import annotations

from datetime import datetime

import pytz

from config.settings import KILLZONES, SILVER_BULLETS, ASIA_SESSION, TIMEZONE
from config.news_calendar import is_news_blackout

ET = pytz.timezone(TIMEZONE)


def _to_et(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(ET)


def _in_window(dt_et: datetime, window) -> bool:
    curr_mins = dt_et.hour * 60 + dt_et.minute
    start_mins = window.start_hour * 60 + window.start_minute
    end_mins = window.end_hour * 60 + window.end_minute
    return start_mins <= curr_mins < end_mins


def is_in_killzone(dt: datetime) -> str | None:
    """Return killzone name if dt is within a trading killzone, else None."""
    dt_et = _to_et(dt)
    for kz in KILLZONES:
        if _in_window(dt_et, kz):
            return kz.name
    return None


def is_silver_bullet(dt: datetime) -> bool:
    """Check if dt is within a Silver Bullet window (highest probability)."""
    dt_et = _to_et(dt)
    return any(_in_window(dt_et, sb) for sb in SILVER_BULLETS)


def is_in_asia(dt: datetime) -> bool:
    dt_et = _to_et(dt)
    return dt_et.hour >= ASIA_SESSION.start_hour or dt_et.hour < ASIA_SESSION.end_hour


def should_trade(dt: datetime) -> tuple[bool, str]:
    """Check if we should trade at this time.

    Returns (can_trade, session_name_or_reason).
    """
    dt_et = _to_et(dt)

    if is_news_blackout(dt_et.date()):
        return False, "News blackout"

    kz = is_in_killzone(dt)
    if kz is None:
        return False, "Outside killzone"

    return True, kz
