"""Tests for Order Block detection."""
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ict.order_blocks import detect_order_blocks


def _make_candles(data):
    df = pd.DataFrame(data, columns=["open", "high", "low", "close"])
    df.index = pd.date_range("2025-01-01", periods=len(data), freq="5min")
    df["volume"] = 100
    return df


def test_bullish_ob():
    candles = [
        (100, 101, 99, 100),
        (100, 101, 99, 100),
        (101, 102, 99, 99.5),  # bearish candle = OB
        (100, 106, 99, 105),   # bullish impulse
        (105, 110, 104, 109),
        (109, 115, 108, 114),
    ]
    df = _make_candles(candles)
    obs = detect_order_blocks(df, lookback=2, impulse_min=3.0)
    bullish = [ob for ob in obs if ob.direction == "bullish"]
    assert len(bullish) >= 1
    assert bullish[0].zone_low <= 99.5
    assert bullish[0].zone_high >= 101


def test_bearish_ob():
    candles = [
        (100, 101, 99, 100),
        (100, 101, 99, 100),
        (99, 101, 98.5, 100.5),  # bullish candle = OB
        (100, 101, 94, 95),      # bearish impulse
        (95, 96, 90, 91),
        (91, 92, 86, 87),
    ]
    df = _make_candles(candles)
    obs = detect_order_blocks(df, lookback=2, impulse_min=3.0)
    bearish = [ob for ob in obs if ob.direction == "bearish"]
    assert len(bearish) >= 1
