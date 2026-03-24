"""Displacement detection after liquidity sweep.

Change 6: ICT teaches that after a sweep, you need "displacement" —
a strong impulsive move away that creates an FVG. This confirms
institutional order flow, not just stop hunting noise.

Theory: Displacement candle has:
- Body > 60% of total range (strong close, not doji)
- Body > 1.0x ATR (conviction)
- Creates an FVG (gap = institutional footprint)
"""
from __future__ import annotations

import pandas as pd

from config.settings import DISPLACEMENT_BODY_RATIO, DISPLACEMENT_ATR_RATIO


def check_displacement(
    df: pd.DataFrame,
    start_idx: int,
    direction: str,
    atr: float,
    max_candles: int = 3,
) -> bool:
    """Check if displacement occurred in the expected direction after start_idx.

    Looks at the next max_candles bars for a strong impulsive move.
    """
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values

    for i in range(start_idx + 1, min(start_idx + max_candles + 1, len(df))):
        body = abs(closes[i] - opens[i])
        total_range = highs[i] - lows[i]

        if total_range <= 0:
            continue

        body_ratio = body / total_range
        body_vs_atr = body / atr if atr > 0 else 0

        # Direction check
        if direction == "bullish" and closes[i] <= opens[i]:
            continue
        if direction == "bearish" and closes[i] >= opens[i]:
            continue

        # Displacement criteria
        if body_ratio >= DISPLACEMENT_BODY_RATIO and body_vs_atr >= DISPLACEMENT_ATR_RATIO:
            # Check if it creates an FVG (gap between candle i-1 and i+1)
            if i >= 2 and i < len(df) - 1:
                if direction == "bullish" and lows[i + 1] > highs[i - 1]:
                    return True  # Bullish FVG created
                elif direction == "bearish" and highs[i + 1] < lows[i - 1]:
                    return True  # Bearish FVG created

            # Even without FVG, strong body + ATR = valid displacement
            if body_vs_atr >= 1.5:
                return True

    return False
