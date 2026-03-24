"""Tests for data download and management."""
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.manager import DataManager


def test_data_manager_resample():
    """Verify 1-min data can be resampled to 5m, 1H, 4H."""
    idx = pd.date_range("2025-01-02 08:00", periods=240, freq="1min")
    df = pd.DataFrame({
        "open": range(240),
        "high": [x + 1 for x in range(240)],
        "low": [x - 1 for x in range(240)],
        "close": [x + 0.5 for x in range(240)],
        "volume": [100] * 240,
    }, index=idx)

    mgr = DataManager(gold_1m=df)
    assert len(mgr.gold_5m) == 48
    assert len(mgr.gold_1h) == 4


def test_data_manager_slice():
    """Test getting a slice of data."""
    idx = pd.date_range("2025-01-02 08:00", periods=120, freq="1min")
    df = pd.DataFrame({
        "open": range(120),
        "high": [x + 1 for x in range(120)],
        "low": [x - 1 for x in range(120)],
        "close": [x + 0.5 for x in range(120)],
        "volume": [100] * 120,
    }, index=idx)

    mgr = DataManager(gold_1m=df)
    end = idx[60]
    sliced = mgr.get_gold_slice("5m", end, 5)
    assert len(sliced) == 5
    assert sliced.index[-1] <= end
