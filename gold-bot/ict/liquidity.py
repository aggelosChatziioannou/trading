"""Liquidity level detection: session highs/lows, equal levels, sweeps."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import pytz

from config.settings import SESSIONS, TIMEZONE, EQUAL_LEVEL_TOLERANCE
from ict.structures import SwingPoint

ET = pytz.timezone(TIMEZONE)


@dataclass
class LiquidityLevel:
    price: float
    type: str          # "session_high", "session_low", "equal_highs", "equal_lows", "swing_high", "swing_low"
    source: str        # e.g. "London", "NY", "1H", "4H"
    timestamp: datetime
    swept: bool = False


def get_session_levels(df: pd.DataFrame) -> list[LiquidityLevel]:
    """Extract session highs/lows for Asian, London, NY sessions."""
    levels = []
    if df.index.tz is None:
        df = df.copy()
        df.index = df.index.tz_localize("UTC")

    df_et = df.copy()
    df_et.index = df_et.index.tz_convert(ET)

    for session in SESSIONS:
        for date_val in df_et.index.normalize().unique():
            start = date_val.replace(hour=session.start_hour, minute=session.start_minute)
            if session.end_hour < session.start_hour:
                end = (date_val + pd.Timedelta(days=1)).replace(
                    hour=session.end_hour, minute=session.end_minute
                )
            else:
                end = date_val.replace(hour=session.end_hour, minute=session.end_minute)

            mask = (df_et.index >= start) & (df_et.index < end)
            session_data = df_et[mask]
            if len(session_data) < 2:
                continue

            levels.append(LiquidityLevel(
                price=float(session_data["high"].max()),
                type="session_high",
                source=session.name,
                timestamp=session_data["high"].idxmax(),
            ))
            levels.append(LiquidityLevel(
                price=float(session_data["low"].min()),
                type="session_low",
                source=session.name,
                timestamp=session_data["low"].idxmin(),
            ))
    return levels


def get_swing_liquidity(swings: list[SwingPoint], source: str) -> list[LiquidityLevel]:
    """Convert swing points to liquidity levels."""
    levels = []
    for s in swings:
        levels.append(LiquidityLevel(
            price=s.price,
            type=f"swing_{s.type}",
            source=source,
            timestamp=s.timestamp,
        ))
    return levels


def find_equal_levels(
    swings: list[SwingPoint],
    tolerance: float = EQUAL_LEVEL_TOLERANCE,
) -> list[LiquidityLevel]:
    """Find equal highs/lows where 2+ swings cluster near the same price."""
    levels = []
    highs = [s for s in swings if s.type == "high"]
    lows = [s for s in swings if s.type == "low"]

    for group, ltype in [(highs, "equal_highs"), (lows, "equal_lows")]:
        used = set()
        for i, a in enumerate(group):
            if i in used:
                continue
            cluster = [a]
            for j, b in enumerate(group):
                if j != i and j not in used and abs(a.price - b.price) <= tolerance:
                    cluster.append(b)
                    used.add(j)
            if len(cluster) >= 2:
                used.add(i)
                avg_price = sum(s.price for s in cluster) / len(cluster)
                levels.append(LiquidityLevel(
                    price=avg_price,
                    type=ltype,
                    source="equal_levels",
                    timestamp=cluster[-1].timestamp,
                ))
    return levels


def check_liquidity_sweep(
    level: LiquidityLevel,
    bar: pd.Series,
) -> bool:
    """Check if a bar sweeps a liquidity level (wick beyond, close back inside)."""
    if level.swept:
        return False

    if "high" in level.type or level.type == "equal_highs":
        # Price wicks above but closes below
        if bar["high"] > level.price and bar["close"] < level.price:
            return True
    elif "low" in level.type or level.type == "equal_lows":
        # Price wicks below but closes above
        if bar["low"] < level.price and bar["close"] > level.price:
            return True
    return False
