"""ATR (Average True Range) calculation for volatility-based sizing.

Change 1: All SL/TP/filter parameters scale with ATR.
Theory: Gold 5-min ATR ≈ $2-$5. Fixed dollar amounts fail because
volatility changes. Professional traders use ATR multiples.
"""
import numpy as np
import pandas as pd

from config.settings import ATR_PERIOD


def calculate_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """Calculate ATR(period) on OHLC data. Returns a Series aligned with df index."""
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values

    tr = np.maximum(
        highs - lows,
        np.maximum(
            np.abs(highs - np.roll(closes, 1)),
            np.abs(lows - np.roll(closes, 1))
        )
    )
    tr[0] = highs[0] - lows[0]

    atr = pd.Series(tr, index=df.index, dtype=float).rolling(period, min_periods=1).mean()
    return atr


def get_current_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> float:
    """Get the current (latest) ATR value."""
    atr = calculate_atr(df, period)
    return float(atr.iloc[-1]) if len(atr) > 0 else 3.0  # Fallback $3
