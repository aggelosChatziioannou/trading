"""
Test feature calculation correctness.

Verifies that technical indicators produce reasonable values
on known synthetic data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data.features.technical import TechnicalFeatures


def _make_trending_up(n: int = 250) -> pd.DataFrame:
    """Create synthetic uptrending OHLCV data."""
    dates = pd.date_range("2023-01-01", periods=n, freq="B", tz="UTC")
    close = 100 + np.arange(n) * 0.1 + np.random.randn(n) * 0.3
    np.random.seed(42)
    return pd.DataFrame({
        "open": close - 0.1,
        "high": close + abs(np.random.randn(n) * 0.3),
        "low": close - abs(np.random.randn(n) * 0.3),
        "close": close,
        "volume": np.random.randint(1_000_000, 5_000_000, n),
    }, index=dates)


def _make_ranging(n: int = 250) -> pd.DataFrame:
    """Create synthetic range-bound OHLCV data."""
    dates = pd.date_range("2023-01-01", periods=n, freq="B", tz="UTC")
    np.random.seed(42)
    close = 100 + np.sin(np.arange(n) * 0.1) * 2 + np.random.randn(n) * 0.2
    return pd.DataFrame({
        "open": close - 0.1,
        "high": close + abs(np.random.randn(n) * 0.3),
        "low": close - abs(np.random.randn(n) * 0.3),
        "close": close,
        "volume": np.random.randint(1_000_000, 5_000_000, n),
    }, index=dates)


class TestTechnicalFeatures:

    def test_rsi_bounded(self) -> None:
        """RSI must be between 0 and 100."""
        ohlcv = _make_trending_up()
        features = TechnicalFeatures.compute_all(ohlcv)
        rsi = features["rsi_14"].dropna()
        assert rsi.min() >= 0, f"RSI below 0: {rsi.min()}"
        assert rsi.max() <= 100, f"RSI above 100: {rsi.max()}"

    def test_bb_position_bounded(self) -> None:
        """BB position should mostly be between 0 and 1."""
        ohlcv = _make_ranging()
        features = TechnicalFeatures.compute_all(ohlcv)
        bb = features["bb_position"].dropna()
        # Allow small excursions outside [0,1] for extreme moves
        assert bb.min() >= -0.5, f"BB position too low: {bb.min()}"
        assert bb.max() <= 1.5, f"BB position too high: {bb.max()}"

    def test_atr_positive(self) -> None:
        """ATR must always be non-negative."""
        ohlcv = _make_trending_up()
        features = TechnicalFeatures.compute_all(ohlcv)
        atr = features["atr_14"].dropna()
        assert (atr >= 0).all(), "ATR has negative values"

    def test_volume_ratio_reasonable(self) -> None:
        """Volume ratio should be around 1.0 on average."""
        ohlcv = _make_ranging()
        features = TechnicalFeatures.compute_all(ohlcv)
        vol_ratio = features["volume_ratio"].dropna()
        # Average should be near 1.0 (by construction)
        assert 0.5 < vol_ratio.mean() < 2.0, f"Volume ratio avg: {vol_ratio.mean()}"

    def test_uptrend_rsi_above_50(self) -> None:
        """In an uptrend, RSI should average above 50."""
        ohlcv = _make_trending_up()
        features = TechnicalFeatures.compute_all(ohlcv)
        rsi_avg = features["rsi_14"].dropna().tail(50).mean()
        assert rsi_avg > 50, f"RSI avg in uptrend: {rsi_avg}"

    def test_all_expected_columns(self) -> None:
        """Verify all expected feature columns are present."""
        ohlcv = _make_ranging()
        features = TechnicalFeatures.compute_all(ohlcv)

        expected = [
            "rsi_14", "macd_signal", "macd_histogram",
            "bb_position", "bb_width", "atr_14", "atr_ratio",
            "obv_slope", "vwap_distance", "volume_ratio",
            "roc_5", "roc_20", "adx_14", "stoch_k", "stoch_d",
            "ema_cross", "price_vs_sma50", "price_vs_sma200",
            "high_low_range", "close_position",
            "upper_keltner", "lower_keltner", "keltner_mid",
            "bb_squeeze",
        ]
        for col in expected:
            assert col in features.columns, f"Missing feature column: {col}"

    def test_no_inf_values(self) -> None:
        """Features should not contain infinite values."""
        ohlcv = _make_ranging()
        features = TechnicalFeatures.compute_all(ohlcv)
        numeric = features.select_dtypes(include=[np.number])
        assert not np.isinf(numeric.values).any(), "Features contain inf values"
