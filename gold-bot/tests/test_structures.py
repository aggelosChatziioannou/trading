"""Tests for market structure detection."""
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ict.structures import find_swing_highs, find_swing_lows, detect_bos


def _make_candles(highs, lows, closes=None):
    n = len(highs)
    if closes is None:
        closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    return pd.DataFrame({
        "open": closes,
        "high": highs,
        "low": lows,
        "close": closes,
    }, index=pd.date_range("2025-01-01", periods=n, freq="5min"))


def test_swing_high_detection():
    highs = [10, 11, 12, 13, 14, 20, 14, 13, 12, 11, 10]
    lows =  [9,  10, 11, 12, 13, 19, 13, 12, 11, 10, 9]
    df = _make_candles(highs, lows)
    swings = find_swing_highs(df, lookback=5)
    assert len(swings) == 1
    assert swings[0].price == 20


def test_swing_low_detection():
    highs = [20, 19, 18, 17, 16, 11, 16, 17, 18, 19, 20]
    lows =  [19, 18, 17, 16, 15, 10, 15, 16, 17, 18, 19]
    df = _make_candles(highs, lows)
    swings = find_swing_lows(df, lookback=5)
    assert len(swings) == 1
    assert swings[0].price == 10


def test_bullish_bos():
    # Two swing highs with lookback=2: first peak at idx 2, second higher peak at idx 8
    highs = [90, 92, 100, 92, 90, 88, 92, 95, 105, 95, 92, 90]
    lows  = [88, 90, 98,  90, 88, 86, 90, 93, 103, 93, 90, 88]
    df = _make_candles(highs, lows)
    bos_list = detect_bos(df, lookback=2)
    bullish = [b for b in bos_list if b.direction == "bullish"]
    assert len(bullish) >= 1


def test_bearish_bos():
    # Two swing lows with lookback=2: first trough at idx 2, second lower trough at idx 8
    highs = [110, 108, 102, 108, 110, 112, 108, 105, 97,  105, 108, 110]
    lows  = [108, 106, 100, 106, 108, 110, 106, 103, 95,  103, 106, 108]
    df = _make_candles(highs, lows)
    bos_list = detect_bos(df, lookback=2)
    bearish = [b for b in bos_list if b.direction == "bearish"]
    assert len(bearish) >= 1
