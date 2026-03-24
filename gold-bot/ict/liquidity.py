"""Liquidity: session H/L, PDH/PDL, equal levels, sweeps, Asia range."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
import pytz

from config.settings import ALL_SESSIONS, ASIA_SESSION, TIMEZONE, EQUAL_LEVEL_TOLERANCE
from ict.structures import SwingPoint

ET = pytz.timezone(TIMEZONE)


@dataclass
class LiquidityLevel:
    price: float
    type: str       # session_high, session_low, pdh, pdl, equal_highs, equal_lows, swing_high, swing_low
    source: str     # e.g. "Asia", "London", "NY", "1H", "4H", "PDH", "PDL"
    timestamp: datetime
    swept: bool = False


@dataclass
class AsiaRange:
    """Asia session range for Power of 3 model."""
    date: datetime
    high: float
    low: float
    high_swept: bool = False
    low_swept: bool = False


def _ensure_tz(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure index is timezone-aware in ET."""
    if df.index.tz is None:
        df = df.copy()
        df.index = df.index.tz_localize("UTC")
    return df.copy()


def get_session_levels(df: pd.DataFrame) -> list[LiquidityLevel]:
    """Extract session highs/lows for Asia, London, NY sessions."""
    levels = []
    df = _ensure_tz(df)
    df_et = df.copy()
    df_et.index = df_et.index.tz_convert(ET)

    for session in ALL_SESSIONS:
        for date_val in df_et.index.normalize().unique():
            start = date_val.replace(hour=session.start_hour, minute=session.start_minute)
            if session.end_hour <= session.start_hour:
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
                type="session_high", source=session.name,
                timestamp=session_data["high"].idxmax(),
            ))
            levels.append(LiquidityLevel(
                price=float(session_data["low"].min()),
                type="session_low", source=session.name,
                timestamp=session_data["low"].idxmin(),
            ))
    return levels


def get_asia_ranges(df: pd.DataFrame) -> list[AsiaRange]:
    """Extract Asia session ranges for the Power of 3 model.

    Asia: 8PM-12AM EST. The range built here is the accumulation phase.
    """
    ranges = []
    df = _ensure_tz(df)
    df_et = df.copy()
    df_et.index = df_et.index.tz_convert(ET)

    for date_val in df_et.index.normalize().unique():
        start = date_val.replace(hour=ASIA_SESSION.start_hour, minute=0)
        end = (date_val + pd.Timedelta(days=1)).replace(hour=0, minute=0)

        mask = (df_et.index >= start) & (df_et.index < end)
        asia_data = df_et[mask]
        if len(asia_data) < 2:
            continue

        ranges.append(AsiaRange(
            date=date_val,
            high=float(asia_data["high"].max()),
            low=float(asia_data["low"].min()),
        ))
    return ranges


def get_pdh_pdl(df: pd.DataFrame) -> list[LiquidityLevel]:
    """Extract Previous Day High (PDH) and Previous Day Low (PDL)."""
    levels = []
    df = _ensure_tz(df)
    daily = df.resample("1D").agg({"high": "max", "low": "min"}).dropna()

    for i in range(1, len(daily)):
        prev = daily.iloc[i - 1]
        ts = daily.index[i]
        levels.append(LiquidityLevel(
            price=float(prev["high"]), type="pdh", source="PDH", timestamp=ts,
        ))
        levels.append(LiquidityLevel(
            price=float(prev["low"]), type="pdl", source="PDL", timestamp=ts,
        ))
    return levels


def get_swing_liquidity(swings: list[SwingPoint], source: str) -> list[LiquidityLevel]:
    """Convert swing points to liquidity levels."""
    return [
        LiquidityLevel(
            price=s.price, type=f"swing_{s.type}",
            source=source, timestamp=s.timestamp,
        )
        for s in swings
    ]


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
                    price=avg_price, type=ltype, source="equal_levels",
                    timestamp=cluster[-1].timestamp,
                ))
    return levels


def check_liquidity_sweep(
    level: LiquidityLevel, bar: pd.Series, atr: float = 0.0,
) -> bool:
    """Check if a bar sweeps a liquidity level (wick beyond, close back inside).

    Change 4: ATR-calibrated sweep detection.
    Theory: Gold sweeps overshoot $0.50-$2.00. With ATR, we require
    minimum 0.1x ATR overshoot and max 2.0x ATR (beyond = breakout).
    """
    if level.swept:
        return False

    from config.settings import SWEEP_MIN_OVERSHOOT_ATR, SWEEP_MAX_OVERSHOOT_ATR
    min_os = SWEEP_MIN_OVERSHOOT_ATR * atr if atr > 0 else 0.0
    max_os = SWEEP_MAX_OVERSHOOT_ATR * atr if atr > 0 else float("inf")

    if level.type in ("session_high", "pdh", "swing_high", "equal_highs"):
        overshoot = bar["high"] - level.price
        return (overshoot >= min_os and overshoot <= max_os
                and bar["close"] < level.price)
    elif level.type in ("session_low", "pdl", "swing_low", "equal_lows"):
        overshoot = level.price - bar["low"]
        return (overshoot >= min_os and overshoot <= max_os
                and bar["close"] > level.price)
    return False


def check_asia_sweep(
    asia: AsiaRange, bar: pd.Series, atr: float = 0.0,
) -> str | None:
    """Check if a bar sweeps the Asia range high or low.

    Returns 'high' or 'low' if swept, None otherwise.
    """
    from config.settings import SWEEP_MIN_OVERSHOOT_ATR, SWEEP_MAX_OVERSHOOT_ATR
    min_os = SWEEP_MIN_OVERSHOOT_ATR * atr if atr > 0 else 0.0
    max_os = SWEEP_MAX_OVERSHOOT_ATR * atr if atr > 0 else float("inf")

    if not asia.high_swept:
        overshoot = bar["high"] - asia.high
        if min_os <= overshoot <= max_os and bar["close"] < asia.high:
            return "high"
    if not asia.low_swept:
        overshoot = asia.low - bar["low"]
        if min_os <= overshoot <= max_os and bar["close"] > asia.low:
            return "low"
    return None
