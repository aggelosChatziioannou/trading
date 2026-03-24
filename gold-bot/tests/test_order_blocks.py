"""Tests for Order Block detection with volume/range filters."""
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ict.order_blocks import detect_order_blocks


def _make_candles(data, volumes=None):
    df = pd.DataFrame(data, columns=["open", "high", "low", "close"])
    df.index = pd.date_range("2025-01-01", periods=len(data), freq="5min")
    # High volume so they pass the volume filter
    df["volume"] = volumes if volumes is not None else [5000] * len(data)
    return df


def test_bullish_ob():
    # Need 22+ bars for the rolling calculations, pad with neutral candles
    neutral = [(100, 101, 99, 100)] * 20
    candles = neutral + [
        (101, 102, 99, 99.5),  # bearish candle (tight range) = potential OB
        (100, 106, 99, 105),   # bullish impulse
        (105, 110, 104, 109),
    ]
    # High volume on the OB candle
    vols = [1000] * 20 + [5000, 1000, 1000]
    df = _make_candles(candles, volumes=vols)
    obs = detect_order_blocks(df, impulse_min=3.0, vol_multiplier=1.0, range_atr_ratio=2.0)
    bullish = [ob for ob in obs if ob.direction == "bullish"]
    assert len(bullish) >= 1


def test_bearish_ob():
    neutral = [(100, 101, 99, 100)] * 20
    candles = neutral + [
        (99, 101, 98.5, 100.5),  # bullish candle = potential OB
        (100, 101, 94, 95),      # bearish impulse
        (95, 96, 90, 91),
    ]
    vols = [1000] * 20 + [5000, 1000, 1000]
    df = _make_candles(candles, volumes=vols)
    obs = detect_order_blocks(df, impulse_min=3.0, vol_multiplier=1.0, range_atr_ratio=2.0)
    bearish = [ob for ob in obs if ob.direction == "bearish"]
    assert len(bearish) >= 1


def test_volume_filter_rejects_low_volume():
    """OB with low volume should be filtered out."""
    neutral = [(100, 101, 99, 100)] * 20
    candles = neutral + [
        (101, 102, 99, 99.5),
        (100, 106, 99, 105),
        (105, 110, 104, 109),
    ]
    # Low volume on OB candle
    vols = [5000] * 20 + [100, 5000, 5000]
    df = _make_candles(candles, volumes=vols)
    obs = detect_order_blocks(df, impulse_min=3.0, vol_multiplier=1.5, range_atr_ratio=2.0)
    assert len(obs) == 0
