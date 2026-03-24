"""Market structure: swing highs/lows, break of structure (BOS)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass
class SwingPoint:
    timestamp: datetime
    price: float
    type: str  # "high" or "low"
    index: int  # bar index in the dataframe


@dataclass
class BOS:
    timestamp: datetime
    price: float
    direction: str  # "bullish" or "bearish"
    swing_broken: SwingPoint


def find_swing_highs(df: pd.DataFrame, lookback: int = 5) -> list[SwingPoint]:
    """Find swing highs: bar where high is highest within lookback bars on each side."""
    swings = []
    highs = df["high"].values
    for i in range(lookback, len(df) - lookback):
        window = highs[i - lookback : i + lookback + 1]
        if highs[i] == max(window) and list(window).count(highs[i]) == 1:
            swings.append(SwingPoint(
                timestamp=df.index[i],
                price=float(highs[i]),
                type="high",
                index=i,
            ))
    return swings


def find_swing_lows(df: pd.DataFrame, lookback: int = 5) -> list[SwingPoint]:
    """Find swing lows: bar where low is lowest within lookback bars on each side."""
    swings = []
    lows = df["low"].values
    for i in range(lookback, len(df) - lookback):
        window = lows[i - lookback : i + lookback + 1]
        if lows[i] == min(window) and list(window).count(lows[i]) == 1:
            swings.append(SwingPoint(
                timestamp=df.index[i],
                price=float(lows[i]),
                type="low",
                index=i,
            ))
    return swings


def find_all_swings(df: pd.DataFrame, lookback: int = 5) -> list[SwingPoint]:
    """Find all swing points sorted by time."""
    swings = find_swing_highs(df, lookback) + find_swing_lows(df, lookback)
    swings.sort(key=lambda s: s.timestamp)
    return swings


def detect_bos(df: pd.DataFrame, lookback: int = 5) -> list[BOS]:
    """Detect Break of Structure events.

    Bullish BOS: price breaks above a previous swing high.
    Bearish BOS: price breaks below a previous swing low.
    """
    swing_highs = find_swing_highs(df, lookback)
    swing_lows = find_swing_lows(df, lookback)
    bos_list = []

    for i in range(1, len(swing_highs)):
        prev = swing_highs[i - 1]
        curr = swing_highs[i]
        if curr.price > prev.price:
            bos_list.append(BOS(
                timestamp=curr.timestamp,
                price=curr.price,
                direction="bullish",
                swing_broken=prev,
            ))

    for i in range(1, len(swing_lows)):
        prev = swing_lows[i - 1]
        curr = swing_lows[i]
        if curr.price < prev.price:
            bos_list.append(BOS(
                timestamp=curr.timestamp,
                price=curr.price,
                direction="bearish",
                swing_broken=prev,
            ))

    bos_list.sort(key=lambda b: b.timestamp)
    return bos_list
