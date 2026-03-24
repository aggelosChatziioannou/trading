"""Fair Value Gap (FVG) detection and tracking."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass
class FVG:
    timestamp: datetime    # Time of the middle candle (impulse)
    direction: str         # "bullish" or "bearish"
    top: float             # Upper bound of the gap
    bottom: float          # Lower bound of the gap
    index: int             # Bar index of the middle candle
    filled: bool = False   # Whether price has returned to fill the gap
    inverted: bool = False # Whether this FVG has been inverted (IFVG)


def detect_fvgs(df: pd.DataFrame) -> list[FVG]:
    """Detect all Fair Value Gaps in the data.

    Bullish FVG: candle[i-2].high < candle[i].low
    Bearish FVG: candle[i-2].low > candle[i].high
    """
    fvgs = []
    highs = df["high"].values
    lows = df["low"].values

    for i in range(2, len(df)):
        # Bullish FVG
        if lows[i] > highs[i - 2]:
            fvgs.append(FVG(
                timestamp=df.index[i - 1],
                direction="bullish",
                top=float(lows[i]),
                bottom=float(highs[i - 2]),
                index=i - 1,
            ))
        # Bearish FVG
        elif highs[i] < lows[i - 2]:
            fvgs.append(FVG(
                timestamp=df.index[i - 1],
                direction="bearish",
                top=float(lows[i - 2]),
                bottom=float(highs[i]),
                index=i - 1,
            ))
    return fvgs


def update_fvg_status(
    fvgs: list[FVG],
    current_bar: pd.Series,
    current_index: int,
    expiry_bars: int = 50,
) -> list[FVG]:
    """Update FVG fill/inversion status and remove expired ones.

    Returns the list of still-active FVGs.
    """
    active = []
    for fvg in fvgs:
        age = current_index - fvg.index
        if age > expiry_bars:
            continue  # Expired

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
