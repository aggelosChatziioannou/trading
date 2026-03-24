"""Fair Value Gap (FVG) detection with ATR-based size filter.

Change 2: FVG must be ≥ 0.3x ATR and ≤ 3.0x ATR to qualify.
Theory: Micro-gaps under 0.3x ATR are noise on gold. Gaps > 3x ATR
won't fill cleanly. Only ATR-relative gaps are institutional.

Consequent Encroachment (CE): 50% midpoint of FVG is used as
precision entry rather than the gap edge.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from config.settings import FVG_MIN_ATR_RATIO, FVG_MAX_ATR_RATIO


@dataclass
class FVG:
    timestamp: datetime
    direction: str          # "bullish" or "bearish"
    top: float              # Upper bound of the gap
    bottom: float           # Lower bound of the gap
    ce: float               # Consequent Encroachment (50% midpoint)
    size: float             # Gap size in $
    index: int
    filled: bool = False
    inverted: bool = False  # IFVG


def detect_fvgs(df: pd.DataFrame, atr: float | None = None) -> list[FVG]:
    """Detect Fair Value Gaps with optional ATR size filter.

    If atr is provided, filters out FVGs smaller than 0.3x ATR
    or larger than 3.0x ATR.
    """
    fvgs = []
    highs = df["high"].values
    lows = df["low"].values

    for i in range(2, len(df)):
        # Bullish FVG: candle[i-2].high < candle[i].low
        if lows[i] > highs[i - 2]:
            top = float(lows[i])
            bottom = float(highs[i - 2])
            size = top - bottom

            # ATR filter
            if atr is not None:
                if size < FVG_MIN_ATR_RATIO * atr or size > FVG_MAX_ATR_RATIO * atr:
                    continue

            fvgs.append(FVG(
                timestamp=df.index[i - 1], direction="bullish",
                top=top, bottom=bottom,
                ce=(top + bottom) / 2,
                size=size, index=i - 1,
            ))

        # Bearish FVG: candle[i-2].low > candle[i].high
        elif highs[i] < lows[i - 2]:
            top = float(lows[i - 2])
            bottom = float(highs[i])
            size = top - bottom

            if atr is not None:
                if size < FVG_MIN_ATR_RATIO * atr or size > FVG_MAX_ATR_RATIO * atr:
                    continue

            fvgs.append(FVG(
                timestamp=df.index[i - 1], direction="bearish",
                top=top, bottom=bottom,
                ce=(top + bottom) / 2,
                size=size, index=i - 1,
            ))

    return fvgs


def update_fvg_status(
    fvgs: list[FVG], current_bar: pd.Series,
    current_index: int, expiry_bars: int = 50,
) -> list[FVG]:
    """Update FVG fill/inversion status."""
    active = []
    for fvg in fvgs:
        age = current_index - fvg.index
        if age > expiry_bars:
            continue
        high = current_bar["high"]
        low = current_bar["low"]
        if not fvg.filled:
            if fvg.direction == "bullish" and low <= fvg.top:
                fvg.filled = True
            elif fvg.direction == "bearish" and high >= fvg.bottom:
                fvg.filled = True
        if fvg.filled and not fvg.inverted:
            if fvg.direction == "bullish" and low < fvg.bottom:
                fvg.inverted = True
            elif fvg.direction == "bearish" and high > fvg.top:
                fvg.inverted = True
        active.append(fvg)
    return active
