"""Order Block (OB) and Breaker Block detection."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass
class OB:
    timestamp: datetime
    direction: str       # "bullish" or "bearish"
    zone_high: float     # Upper bound of OB (candle body high)
    zone_low: float      # Lower bound of OB (candle body low)
    index: int
    broken: bool = False # Becomes a Breaker Block if broken


def detect_order_blocks(
    df: pd.DataFrame,
    lookback: int = 5,
    impulse_min: float = 1.0,
) -> list[OB]:
    """Detect Order Blocks.

    Bullish OB: last bearish candle before a bullish impulse (strong up move).
    Bearish OB: last bullish candle before a bearish impulse (strong down move).
    """
    obs = []
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values

    for i in range(1, len(df) - 2):
        # Bullish impulse at i+1
        impulse_move = highs[i + 1] - lows[i]
        if impulse_move >= impulse_min and closes[i + 1] > opens[i + 1]:
            for j in range(i, max(i - lookback - 1, -1), -1):
                if closes[j] < opens[j]:  # bearish candle
                    body_high = max(opens[j], closes[j])
                    body_low = min(opens[j], closes[j])
                    obs.append(OB(
                        timestamp=df.index[j],
                        direction="bullish",
                        zone_high=float(body_high),
                        zone_low=float(body_low),
                        index=j,
                    ))
                    break

        # Bearish impulse at i+1
        impulse_move = highs[i] - lows[i + 1]
        if impulse_move >= impulse_min and closes[i + 1] < opens[i + 1]:
            for j in range(i, max(i - lookback - 1, -1), -1):
                if closes[j] > opens[j]:  # bullish candle
                    body_high = max(opens[j], closes[j])
                    body_low = min(opens[j], closes[j])
                    obs.append(OB(
                        timestamp=df.index[j],
                        direction="bearish",
                        zone_high=float(body_high),
                        zone_low=float(body_low),
                        index=j,
                    ))
                    break
    return obs


def update_ob_status(obs: list[OB], current_bar: pd.Series) -> list[OB]:
    """Check if OBs have been broken (becoming Breaker Blocks)."""
    for ob in obs:
        if ob.broken:
            continue
        if ob.direction == "bullish" and current_bar["low"] < ob.zone_low:
            ob.broken = True
        elif ob.direction == "bearish" and current_bar["high"] > ob.zone_high:
            ob.broken = True
    return obs
