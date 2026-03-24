"""Session and news filters for TJR strategy.

Sessions (EST):
  Asia: 8PM-12AM (mark range only, NO trading)
  London Killzone: 2AM-5AM (trade: manipulation -> reversal)
  NY Killzone: 7AM-10AM (trade: reversal -> continuation)
"""
from __future__ import annotations

from datetime import datetime

import pytz

from config.settings import KILLZONES, ASIA_SESSION, TIMEZONE
from config.news_calendar import is_news_blackout

ET = pytz.timezone(TIMEZONE)


def _to_et(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(ET)


def is_in_killzone(dt: datetime) -> str | None:
    """Return killzone name if dt is within a trading killzone, else None."""
    dt_et = _to_et(dt)
    for kz in KILLZONES:
        h, m = dt_et.hour, dt_et.minute
        start_mins = kz.start_hour * 60 + kz.start_minute
        end_mins = kz.end_hour * 60 + kz.end_minute
        curr_mins = h * 60 + m
        if start_mins <= curr_mins < end_mins:
            return kz.name
    return None


def is_in_asia(dt: datetime) -> bool:
    """Check if dt is within the Asia session (8PM-12AM EST)."""
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
