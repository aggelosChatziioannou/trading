"""Integration test for the backtest engine."""
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.manager import DataManager
from backtest.engine import run_backtest


def test_backtest_runs_without_error():
    """Smoke test: backtest completes on synthetic data without crashing."""
    np.random.seed(42)
    n = 5000  # ~3.5 days of 1-min data

    # Generate random walk price data around $2000
    returns = np.random.normal(0, 0.0002, n)
    prices = 2000 * np.cumprod(1 + returns)

    idx = pd.date_range("2025-09-15 00:00", periods=n, freq="1min", tz="UTC")
    gold_1m = pd.DataFrame({
        "open": prices,
        "high": prices * (1 + np.random.uniform(0, 0.001, n)),
        "low": prices * (1 - np.random.uniform(0, 0.001, n)),
        "close": prices * (1 + np.random.normal(0, 0.0001, n)),
        "volume": np.random.randint(100, 10000, n),
    }, index=idx)

    data = DataManager(gold_1m=gold_1m)
    result = run_backtest(data, capital=500)

    assert result.starting_capital == 500
    assert result.ending_capital > 0
    assert len(result.equity_curve) > 0


def test_backtest_empty_data():
    """Test that backtest handles insufficient data gracefully."""
    idx = pd.date_range("2025-09-15 00:00", periods=10, freq="1min", tz="UTC")
    gold_1m = pd.DataFrame({
        "open": [2000] * 10,
        "high": [2001] * 10,
        "low": [1999] * 10,
        "close": [2000] * 10,
        "volume": [100] * 10,
    }, index=idx)

    data = DataManager(gold_1m=gold_1m)
    result = run_backtest(data, capital=500)

    assert result.starting_capital == 500
    assert result.ending_capital == 500
    assert len(result.trades) == 0
