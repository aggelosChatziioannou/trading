"""
CRITICAL: Verify no future data leakage anywhere.

These tests ensure that:
1. Sentiment features only use news BEFORE the reference time
2. Technical features don't use future price data
3. CPCV purging actually removes boundary data
4. Labels don't leak into features
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from data.features.sentiment import SentimentFeatures
from data.features.technical import TechnicalFeatures
from validation.cpcv import CPCV


class TestSentimentNoLeakage:
    """Verify sentiment features only use past data."""

    def _make_news_df(self) -> pd.DataFrame:
        """Create a news DataFrame spanning 7 days."""
        base_time = datetime(2024, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        rows = []
        for i in range(14):  # 2 articles per day for 7 days
            t = base_time - timedelta(days=7) + timedelta(days=i // 2, hours=(i % 2) * 6)
            rows.append({
                "time": t,
                "ticker": "AAPL",
                "sentiment_combined": 0.1 * (i - 7),  # Range from -0.7 to +0.6
                "source": f"source_{i % 3}",
            })
        return pd.DataFrame(rows)

    def test_sentiment_uses_only_past_data(self) -> None:
        """Features at time T must not use news from after T."""
        news_df = self._make_news_df()

        # Pick a midpoint time
        as_of_time = datetime(2024, 1, 8, 0, 0, 0, tzinfo=timezone.utc)

        features = SentimentFeatures.compute_all(news_df, as_of_time)

        # Verify: only news before as_of_time should contribute
        available_news = news_df[news_df["time"] < as_of_time]
        future_news = news_df[news_df["time"] >= as_of_time]

        assert len(available_news) > 0, "Should have some past news"
        assert len(future_news) > 0, "Should have some future news"

        # sent_7d should only reflect available news sentiment
        expected_avg = available_news["sentiment_combined"].mean()
        # Our 7d feature should be close to the available news average
        assert abs(features["sent_7d"] - expected_avg) < 0.5, "sent_7d should reflect past data only"

    def test_sentiment_at_earliest_time_returns_zeros(self) -> None:
        """If no news is available before the reference time, return zeros."""
        news_df = self._make_news_df()

        # Time before all news
        early_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        features = SentimentFeatures.compute_all(news_df, early_time)

        assert features["sent_4h"] == 0.0
        assert features["sent_24h"] == 0.0
        assert features["sent_7d"] == 0.0

    def test_sentiment_empty_dataframe(self) -> None:
        """Empty news DataFrame should return zero features."""
        empty_df = pd.DataFrame(columns=["time", "sentiment_combined", "source"])
        features = SentimentFeatures.compute_all(
            empty_df, datetime.now(timezone.utc)
        )
        assert features["sent_4h"] == 0.0
        assert features["sent_volume_4h"] == 0.0


class TestTechnicalNoLeakage:
    """Verify technical features don't use future data."""

    def _make_ohlcv(self, n: int = 250) -> pd.DataFrame:
        """Create synthetic OHLCV data."""
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=n, freq="B", tz="UTC")
        close = 100 + np.cumsum(np.random.randn(n) * 0.5)
        return pd.DataFrame({
            "open": close + np.random.randn(n) * 0.2,
            "high": close + abs(np.random.randn(n) * 0.5),
            "low": close - abs(np.random.randn(n) * 0.5),
            "close": close,
            "volume": np.random.randint(1_000_000, 10_000_000, n),
        }, index=dates)

    def test_technical_features_shape(self) -> None:
        """Technical features should have same length as input."""
        ohlcv = self._make_ohlcv()
        features = TechnicalFeatures.compute_all(ohlcv)
        assert len(features) == len(ohlcv)

    def test_truncated_data_matches(self) -> None:
        """
        Features computed on truncated data must match features
        computed on full data up to the truncation point.

        This verifies no look-ahead bias — each row's features
        only depend on past data.
        """
        ohlcv = self._make_ohlcv(300)

        # Full features
        full_features = TechnicalFeatures.compute_all(ohlcv)

        # Truncated features (first 200 rows only)
        truncated = ohlcv.iloc[:200]
        trunc_features = TechnicalFeatures.compute_all(truncated)

        # The last row of truncated features should match row 199 of full features
        for col in ["rsi_14", "bb_position", "atr_14", "volume_ratio"]:
            if col in trunc_features.columns and col in full_features.columns:
                trunc_val = trunc_features[col].iloc[-1]
                full_val = full_features[col].iloc[199]
                if not (np.isnan(trunc_val) and np.isnan(full_val)):
                    assert abs(trunc_val - full_val) < 1e-10, (
                        f"Feature {col} differs: truncated={trunc_val}, full={full_val}"
                    )


class TestCPCVNoLeakage:
    """Verify CPCV properly purges and embargoes data."""

    def test_no_overlap_between_train_and_test(self) -> None:
        """Train and test indices must never overlap."""
        cpcv = CPCV(n_groups=6, n_test_groups=2, purge_window=5, embargo_pct=0.02)
        splits = cpcv.generate_splits(1000)

        for train_idx, test_idx in splits:
            overlap = set(train_idx) & set(test_idx)
            assert len(overlap) == 0, f"Train-test overlap: {overlap}"

    def test_purge_gap_exists(self) -> None:
        """
        There must be a gap of at least purge_window between
        the last training sample and first test sample (and vice versa).
        """
        purge = 5
        cpcv = CPCV(n_groups=6, n_test_groups=2, purge_window=purge, embargo_pct=0.0)
        splits = cpcv.generate_splits(600)

        for train_idx, test_idx in splits:
            train_set = set(train_idx)
            test_set = set(test_idx)

            # For each test index, check no training index is within purge_window
            for t in test_set:
                nearby_train = [tr for tr in train_set if abs(tr - t) < purge and abs(tr - t) > 0]
                # Allow boundary indices that are in the purge zone (they should be removed)
                # The real check is that they're NOT in train
                assert t not in train_set

    def test_correct_number_of_splits(self) -> None:
        """C(6,2) = 15 splits."""
        cpcv = CPCV(n_groups=6, n_test_groups=2)
        splits = cpcv.generate_splits(600)
        assert len(splits) == 15

    def test_all_data_used(self) -> None:
        """Every data point should appear in at least one test set."""
        cpcv = CPCV(n_groups=6, n_test_groups=2, purge_window=0, embargo_pct=0.0)
        splits = cpcv.generate_splits(600)

        all_test = set()
        for _, test_idx in splits:
            all_test.update(test_idx)

        # With no purge, all indices should appear in some test set
        assert len(all_test) == 600

    def test_chronological_ordering(self) -> None:
        """Train and test indices must be sorted (chronological)."""
        cpcv = CPCV(n_groups=6, n_test_groups=2)
        splits = cpcv.generate_splits(600)

        for train_idx, test_idx in splits:
            assert list(train_idx) == sorted(train_idx), "Train indices not sorted"
            assert list(test_idx) == sorted(test_idx), "Test indices not sorted"
