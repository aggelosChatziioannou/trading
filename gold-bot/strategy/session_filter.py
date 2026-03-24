"""Session and news filters."""
from __future__ import annotations

from datetime import datetime

import pytz

from config.settings import KILLZONES, TIMEZONE
from config.news_calendar import is_news_blackout

ET = pytz.timezone(TIMEZONE)


def is_in_killzone(dt: datetime) -> str | None:
    """Return killzone name if dt is within a trading killzone, else None."""
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    dt_et = dt.astimezone(ET)

    for kz in KILLZONES:
        start = dt_et.replace(hour=kz.start_hour, minute=kz.start_minute, second=0, microsecond=0)
        end = dt_et.replace(hour=kz.end_hour, minute=kz.end_minute, second=0, microsecond=0)
        if start <= dt_et < end:
            return kz.name
    return None


def should_trade(dt: datetime) -> tuple[bool, str]:
    """Check if we should trade at this time.

    Returns (can_trade, reason_or_session_name).
    """
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    dt_et = dt.astimezone(ET)

    if is_news_blackout(dt_et.date()):
        return False, "News blackout day"

    kz = is_in_killzone(dt)
    if kz is None:
        return False, "Outside killzone"

    return True, kz
