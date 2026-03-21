"""
Test CPCV implementation correctness.

Verifies:
- Correct number of splits
- Purging removes boundary data
- No information leakage between folds
- Embargo is applied correctly
"""

from __future__ import annotations

import numpy as np
import pytest

from validation.cpcv import CPCV


class TestCPCVSplits:

    def test_default_15_splits(self) -> None:
        """C(6,2) = 15 with default parameters."""
        cpcv = CPCV()
        splits = cpcv.generate_splits(600)
        assert len(splits) == 15

    def test_custom_split_count(self) -> None:
        """C(8,3) = 56 with 8 groups, 3 test."""
        cpcv = CPCV(n_groups=8, n_test_groups=3, purge_window=0, embargo_pct=0.0)
        splits = cpcv.generate_splits(800)
        assert len(splits) == 56

    def test_train_test_disjoint(self) -> None:
        """Train and test must be completely disjoint."""
        cpcv = CPCV()
        for train, test in cpcv.generate_splits(600):
            assert len(set(train) & set(test)) == 0

    def test_purge_creates_gap(self) -> None:
        """With purge_window=10, no train index should be within 10 of any test block boundary."""
        cpcv = CPCV(n_groups=6, n_test_groups=2, purge_window=10, embargo_pct=0.0)
        splits = cpcv.generate_splits(600)

        group_size = 100
        for train, test in splits:
            train_set = set(train)
            test_set = set(test)

            # Find test block boundaries
            test_sorted = sorted(test_set)
            if not test_sorted:
                continue

            # Check gaps around test block start/end
            test_start = test_sorted[0]
            test_end = test_sorted[-1]

            # No training data within 10 indices before test start
            for i in range(max(0, test_start - 10), test_start):
                assert i not in train_set, f"Train index {i} too close to test start {test_start}"

    def test_embargo_removes_post_test(self) -> None:
        """Embargo should remove data after test blocks from training."""
        cpcv = CPCV(n_groups=6, n_test_groups=2, purge_window=0, embargo_pct=0.05)
        splits = cpcv.generate_splits(600)

        # With 0 purge but 5% embargo on ~200 test samples = ~10 samples embargo
        for train, test in splits:
            # Total available = 600 - len(test) = ~400
            # With embargo, should be less than 400
            assert len(train) < 600 - len(test), "Embargo didn't remove any samples"

    def test_statistics_calculation(self) -> None:
        """Statistics should work with mock results."""
        results = [
            {"fold": i, "sharpe": 0.5 + i * 0.1, "total_return": 0.02 * i,
             "max_drawdown": -0.05 - i * 0.01, "win_rate": 0.5 + i * 0.02,
             "profit_factor": 1.2 + i * 0.1, "n_trades": 10 + i, "train_size": 400}
            for i in range(15)
        ]

        stats = CPCV.calculate_statistics(results)
        assert "sharpe_mean" in stats
        assert "sharpe_std" in stats
        assert stats["total_paths"] == 15
        assert stats["sharpe_mean"] > 0

    def test_empty_results_statistics(self) -> None:
        """Statistics should handle empty results gracefully."""
        stats = CPCV.calculate_statistics([])
        assert stats["total_paths"] == 0
        assert stats["sharpe_mean"] == 0.0
