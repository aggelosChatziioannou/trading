"""Market structure: swing highs/lows, BOS (candle CLOSE), CHoCH, market structure bias."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd


@dataclass
class SwingPoint:
    timestamp: datetime
    price: float
    type: str       # "high" or "low"
    index: int      # bar index in the dataframe


@dataclass
class BOS:
    timestamp: datetime
    price: float
    direction: str          # "bullish" or "bearish"
    swing_broken: SwingPoint
    is_choch: bool = False  # True if this is a Change of Character


@dataclass
class MarketStructure:
    """Current market structure state."""
    bias: str               # "bullish", "bearish", or "neutral"
    last_hh: SwingPoint | None = None
    last_hl: SwingPoint | None = None
    last_lh: SwingPoint | None = None
    last_ll: SwingPoint | None = None
    last_bos: BOS | None = None


def find_swing_highs(df: pd.DataFrame, lookback: int = 5) -> list[SwingPoint]:
    """Find swing highs: bar where high is highest within lookback bars on each side."""
    swings = []
    highs = df["high"].values
    n = len(df)
    for i in range(lookback, n - lookback):
        window = highs[i - lookback: i + lookback + 1]
        if highs[i] == np.max(window) and np.sum(window == highs[i]) == 1:
            swings.append(SwingPoint(
                timestamp=df.index[i], price=float(highs[i]),
                type="high", index=i,
            ))
    return swings


def find_swing_lows(df: pd.DataFrame, lookback: int = 5) -> list[SwingPoint]:
    """Find swing lows: bar where low is lowest within lookback bars on each side."""
    swings = []
    lows = df["low"].values
    n = len(df)
    for i in range(lookback, n - lookback):
        window = lows[i - lookback: i + lookback + 1]
        if lows[i] == np.min(window) and np.sum(window == lows[i]) == 1:
            swings.append(SwingPoint(
                timestamp=df.index[i], price=float(lows[i]),
                type="low", index=i,
            ))
    return swings


def find_all_swings(df: pd.DataFrame, lookback: int = 5) -> list[SwingPoint]:
    """Find all swing points sorted by time."""
    swings = find_swing_highs(df, lookback) + find_swing_lows(df, lookback)
    swings.sort(key=lambda s: s.timestamp)
    return swings


def detect_bos(df: pd.DataFrame, lookback: int = 5) -> list[BOS]:
    """Detect Break of Structure using candle CLOSE (not wicks).

    TJR rule: BOS requires candle body to close beyond the swing point.
    CHoCH (Change of Character) is detected when structure shifts direction
    for the first time.
    """
    swing_highs = find_swing_highs(df, lookback)
    swing_lows = find_swing_lows(df, lookback)
    bos_list: list[BOS] = []
    closes = df["close"].values

    last_structure_dir = None  # Track for CHoCH detection

    # Bullish BOS: a candle CLOSES above a previous swing high
    for sh in swing_highs:
        for j in range(sh.index + 1, len(df)):
            if closes[j] > sh.price:
                is_choch = last_structure_dir == "bearish"
                bos = BOS(
                    timestamp=df.index[j], price=float(closes[j]),
                    direction="bullish", swing_broken=sh, is_choch=is_choch,
                )
                bos_list.append(bos)
                last_structure_dir = "bullish"
                break

    # Bearish BOS: a candle CLOSES below a previous swing low
    for sl in swing_lows:
        for j in range(sl.index + 1, len(df)):
            if closes[j] < sl.price:
                is_choch = last_structure_dir == "bullish"
                bos = BOS(
                    timestamp=df.index[j], price=float(closes[j]),
                    direction="bearish", swing_broken=sl, is_choch=is_choch,
                )
                bos_list.append(bos)
                last_structure_dir = "bearish"
                break

    bos_list.sort(key=lambda b: b.timestamp)
    return bos_list


def determine_market_structure(df: pd.DataFrame, lookback: int = 5) -> MarketStructure:
    """Determine HTF market structure bias from swing sequence.

    Bullish: Higher Highs (HH) + Higher Lows (HL)
    Bearish: Lower Highs (LH) + Lower Lows (LL)
    Neutral: Mixed or insufficient data
    """
    swing_highs = find_swing_highs(df, lookback)
    swing_lows = find_swing_lows(df, lookback)

    ms = MarketStructure(bias="neutral")

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return ms

    # Check recent swing highs
    h1, h2 = swing_highs[-2], swing_highs[-1]
    hh = h2.price > h1.price
    lh = h2.price < h1.price

    # Check recent swing lows
    l1, l2 = swing_lows[-2], swing_lows[-1]
    hl = l2.price > l1.price
    ll = l2.price < l1.price

    if hh and hl:
        ms.bias = "bullish"
        ms.last_hh = h2
        ms.last_hl = l2
    elif lh and ll:
        ms.bias = "bearish"
        ms.last_lh = h2
        ms.last_ll = l2
    else:
        ms.bias = "neutral"

    # Find most recent BOS
    bos_list = detect_bos(df, lookback)
    if bos_list:
        ms.last_bos = bos_list[-1]

    return ms
