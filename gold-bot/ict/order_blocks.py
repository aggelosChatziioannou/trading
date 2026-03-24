"""Order Block (OB) and Breaker Block (BB) detection.

TJR rules:
- OB must have volume > 1.5x 20-period SMA of volume
- OB candle range must be < 0.5x ATR(20) (tight candle before expansion)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from config.settings import OB_VOLUME_MULTIPLIER, OB_RANGE_ATR_RATIO, OB_IMPULSE_MIN_MOVE


@dataclass
class OB:
    timestamp: datetime
    direction: str      # "bullish" or "bearish"
    zone_high: float
    zone_low: float
    index: int
    volume: float = 0.0
    broken: bool = False  # Becomes a Breaker Block when broken


def detect_order_blocks(
    df: pd.DataFrame,
    impulse_min: float = OB_IMPULSE_MIN_MOVE,
    vol_multiplier: float = OB_VOLUME_MULTIPLIER,
    range_atr_ratio: float = OB_RANGE_ATR_RATIO,
) -> list[OB]:
    """Detect Order Blocks with volume and range filters.

    Bullish OB: Last bearish candle before a bullish impulse move
    Bearish OB: Last bullish candle before a bearish impulse move
    """
    obs = []
    if len(df) < 22:
        return obs

    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    volumes = df["volume"].values if "volume" in df.columns else np.ones(len(df))

    # Pre-compute 20-period SMA of volume and ATR
    vol_sma = pd.Series(volumes, dtype=float).rolling(20, min_periods=1).mean().values
    tr = np.maximum(
        highs - lows,
        np.maximum(
            np.abs(highs - np.roll(closes, 1)),
            np.abs(lows - np.roll(closes, 1))
        )
    )
    tr[0] = highs[0] - lows[0]
    atr_20 = pd.Series(tr, dtype=float).rolling(20, min_periods=1).mean().values

    for i in range(1, len(df) - 1):
        candle_range = highs[i] - lows[i]
        is_bearish = closes[i] < opens[i]
        is_bullish = closes[i] > opens[i]

        # Volume filter: skip if volume too low
        if vol_sma[i] > 0 and volumes[i] > 0:
            if volumes[i] < vol_multiplier * vol_sma[i]:
                continue

        # Range filter: OB candle should be tight (< 0.5x ATR)
        if atr_20[i] > 0 and candle_range > range_atr_ratio * atr_20[i]:
            continue

        next_move = closes[i + 1] - closes[i]

        # Bullish OB: bearish candle followed by bullish impulse
        if is_bearish and next_move > impulse_min:
            obs.append(OB(
                timestamp=df.index[i], direction="bullish",
                zone_high=float(max(opens[i], closes[i])),
                zone_low=float(min(opens[i], closes[i])),
                index=i, volume=float(volumes[i]),
            ))

        # Bearish OB: bullish candle followed by bearish impulse
        elif is_bullish and next_move < -impulse_min:
            obs.append(OB(
                timestamp=df.index[i], direction="bearish",
                zone_high=float(max(opens[i], closes[i])),
                zone_low=float(min(opens[i], closes[i])),
                index=i, volume=float(volumes[i]),
            ))

    return obs


def update_ob_status(obs: list[OB], current_bar: pd.Series) -> list[OB]:
    """Check if OBs have been broken (becoming Breaker Blocks)."""
    for ob in obs:
        if ob.broken:
            continue
        if ob.direction == "bullish" and current_bar["close"] < ob.zone_low:
            ob.broken = True
        elif ob.direction == "bearish" and current_bar["close"] > ob.zone_high:
            ob.broken = True
    return obs
