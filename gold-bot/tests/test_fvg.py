"""Tests for Fair Value Gap detection."""
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ict.fvg import detect_fvgs


def _make_candles(data):
    df = pd.DataFrame(data, columns=["open", "high", "low", "close"])
    df.index = pd.date_range("2025-01-01", periods=len(data), freq="5min")
    df["volume"] = 100
    return df


def test_bullish_fvg():
    candles = [
        (98, 100, 97, 99),
        (100, 105, 99, 104),
        (104, 107, 102, 106),
    ]
    df = _make_candles(candles)
    fvgs = detect_fvgs(df)
    assert len(fvgs) == 1
    assert fvgs[0].direction == "bullish"
    assert fvgs[0].top == 102
    assert fvgs[0].bottom == 100


def test_bearish_fvg():
    candles = [
        (102, 103, 100, 101),
        (100, 101, 95, 96),
        (96, 98, 94, 95),
    ]
    df = _make_candles(candles)
    fvgs = detect_fvgs(df)
    assert len(fvgs) == 1
    assert fvgs[0].direction == "bearish"
    assert fvgs[0].top == 100
    assert fvgs[0].bottom == 98


def test_no_fvg_when_no_gap():
    candles = [
        (100, 102, 99, 101),
        (101, 103, 100, 102),
        (102, 104, 101, 103),
    ]
    df = _make_candles(candles)
    fvgs = detect_fvgs(df)
    assert len(fvgs) == 0
