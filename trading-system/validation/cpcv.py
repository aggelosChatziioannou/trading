"""
Combinatorial Purged Cross-Validation (CPCV).

The CORE of our anti-overfit approach. Based on Lopez de Prado (2018).

Unlike standard k-fold:
1. Data blocks are CHRONOLOGICAL (no shuffling)
2. Purge window removes observations between train/test to prevent leakage
3. Embargo removes additional samples after each test block
4. Generates C(n, k) unique train-test paths (not just n splits)
5. Each path trains from SCRATCH on raw data

With n_groups=6, n_test_groups=2: C(6,2) = 15 unique paths.
"""

from __future__ import annotations

import logging
from itertools import combinations
from typing import Any, Callable

import numpy as np
import pandas as pd

from config.settings import settings

logger = logging.getLogger(__name__)

_cfg = settings.validation


class CPCV:
    """
    Combinatorial Purged Cross-Validation.

    Generates all C(n_groups, n_test_groups) train-test splits
    with purging and embargo to prevent information leakage.
    """

    def __init__(
        self,
        n_groups: int = _cfg.cpcv_n_groups,
        n_test_groups: int = _cfg.cpcv_n_test_groups,
        purge_window: int = _cfg.cpcv_purge_window,
        embargo_pct: float = _cfg.cpcv_embargo_pct,
    ) -> None:
        """
        Args:
            n_groups: Number of sequential blocks to divide data into.
            n_test_groups: Number of blocks used as test set per split.
            purge_window: Observations to remove between train/test boundaries.
                         Set to max(signal_horizon, label_horizon).
            embargo_pct: Fraction of test size to embargo after test end.
        """
        self.n_groups = n_groups
        self.n_test_groups = n_test_groups
        self.purge_window = purge_window
        self.embargo_pct = embargo_pct

        # Total number of unique paths
        self.n_paths = int(
            np.math.factorial(n_groups)
            / (np.math.factorial(n_test_groups) * np.math.factorial(n_groups - n_test_groups))
        )
        logger.info(
            "CPCV initialized: %d groups, %d test → %d paths, purge=%d, embargo=%.2f",
            n_groups, n_test_groups, self.n_paths, purge_window, embargo_pct,
        )

    def generate_splits(self, data_length: int) -> list[tuple[np.ndarray, np.ndarray]]:
        """
        Generate all combinatorial train-test splits with purging and embargo.

        Args:
            data_length: Total number of observations in the dataset.

        Returns:
            List of (train_indices, test_indices) tuples.
            Each set of indices has gaps where purging/embargo removed data.
        """
        # Divide data into sequential groups
        group_size = data_length // self.n_groups
        group_boundaries = []
        for i in range(self.n_groups):
            start = i * group_size
            end = (i + 1) * group_size if i < self.n_groups - 1 else data_length
            group_boundaries.append((start, end))

        # Generate all combinations of test groups
        splits: list[tuple[np.ndarray, np.ndarray]] = []
        for test_group_ids in combinations(range(self.n_groups), self.n_test_groups):
            train_idx, test_idx = self._make_split(
                data_length, group_boundaries, test_group_ids
            )
            splits.append((train_idx, test_idx))

        logger.info("Generated %d CPCV splits from %d observations", len(splits), data_length)
        return splits

    def _make_split(
        self,
        data_length: int,
        group_boundaries: list[tuple[int, int]],
        test_group_ids: tuple[int, ...],
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Create a single train-test split with purging and embargo.

        Purging: Remove 'purge_window' observations on both sides of
                 each train-test boundary to prevent label leakage.
        Embargo: Remove 'embargo_pct * test_size' observations after
                 each test block to prevent serial correlation leakage.
        """
        all_indices = set(range(data_length))
        test_indices: set[int] = set()
        purge_indices: set[int] = set()

        # Identify test indices
        for gid in test_group_ids:
            start, end = group_boundaries[gid]
            test_indices.update(range(start, end))

        # Calculate embargo size
        embargo_size = max(1, int(len(test_indices) * self.embargo_pct))

        # Apply purging and embargo around test blocks
        for gid in test_group_ids:
            start, end = group_boundaries[gid]

            # Purge BEFORE test block (remove from training data)
            purge_start = max(0, start - self.purge_window)
            purge_indices.update(range(purge_start, start))

            # Purge AFTER test block (remove from training data)
            purge_end = min(data_length, end + self.purge_window)
            purge_indices.update(range(end, purge_end))

            # Embargo AFTER test block (remove from training data)
            embargo_end = min(data_length, end + self.purge_window + embargo_size)
            purge_indices.update(range(purge_end, embargo_end))

        # Training = everything except test + purged + embargoed
        train_indices = all_indices - test_indices - purge_indices

        return (
            np.array(sorted(train_indices)),
            np.array(sorted(test_indices)),
        )

    def run_validation(
        self,
        raw_ohlcv: pd.DataFrame,
        raw_news: pd.DataFrame,
        feature_builder: Any,
        model_factory: Callable,
        strategy: Any,
        label_fn: Callable[[pd.DataFrame], pd.Series],
    ) -> list[dict]:
        """
        Run complete CPCV validation.

        For EACH split:
        1. Compute features from raw data (train portion only for fitting)
        2. Train model from scratch (no warm start)
        3. Generate signals on test set
        4. Calculate performance metrics

        Args:
            raw_ohlcv: Complete OHLCV dataset.
            raw_news: Complete news dataset.
            feature_builder: FeatureBuilder class with build() method.
            model_factory: Callable that returns a fresh model instance.
            strategy: Strategy instance for signal generation.
            label_fn: Function to create target labels from OHLCV data.

        Returns:
            List of result dicts, one per CPCV split.
        """
        splits = self.generate_splits(len(raw_ohlcv))
        results: list[dict] = []

        for i, (train_idx, test_idx) in enumerate(splits):
            logger.info("CPCV fold %d/%d: train=%d, test=%d", i + 1, len(splits), len(train_idx), len(test_idx))

            # 1. Split raw data
            train_ohlcv = raw_ohlcv.iloc[train_idx]
            test_ohlcv = raw_ohlcv.iloc[test_idx]

            # 2. Compute features FROM SCRATCH
            train_features = feature_builder.build(train_ohlcv, raw_news)
            test_features = feature_builder.build(test_ohlcv, raw_news)

            if train_features.empty or test_features.empty:
                logger.warning("Fold %d: empty features, skipping", i + 1)
                continue

            # 3. Create labels
            train_labels = label_fn(raw_ohlcv.iloc[train_idx])
            test_labels = label_fn(raw_ohlcv.iloc[test_idx])

            # Align features and labels
            common_train = train_features.index.intersection(train_labels.index)
            common_test = test_features.index.intersection(test_labels.index)

            if len(common_train) == 0 or len(common_test) == 0:
                logger.warning("Fold %d: no aligned data, skipping", i + 1)
                continue

            X_train = train_features.loc[common_train]
            y_train = train_labels.loc[common_train]
            X_test = test_features.loc[common_test]
            y_test = test_labels.loc[common_test]

            # 4. Train model FROM SCRATCH
            model = model_factory()
            model.train(X_train, y_train)

            # 5. Generate predictions
            predictions = model.predict_proba(X_test)

            # 6. Calculate metrics
            fold_result = self._calculate_fold_metrics(
                y_test, predictions, test_ohlcv, strategy, i
            )
            results.append(fold_result)

        return results

    def _calculate_fold_metrics(
        self,
        y_true: pd.Series,
        y_pred_proba: np.ndarray,
        ohlcv: pd.DataFrame,
        strategy: Any,
        fold_idx: int,
    ) -> dict:
        """Calculate performance metrics for a single CPCV fold."""
        # Convert probabilities to signals
        # y_pred_proba has shape (n_samples, 5) for 5 classes
        # Classes: strong_sell, sell, hold, buy, strong_buy
        buy_prob = y_pred_proba[:, 3] + y_pred_proba[:, 4]  # buy + strong_buy
        sell_prob = y_pred_proba[:, 0] + y_pred_proba[:, 1]  # strong_sell + sell

        # Simple return calculation based on signal direction
        if "close" in ohlcv.columns:
            returns = ohlcv["close"].pct_change().iloc[1:]
        else:
            returns = pd.Series(0.0, index=y_true.index)

        # Align lengths
        min_len = min(len(buy_prob), len(returns))
        buy_prob = buy_prob[:min_len]
        sell_prob = sell_prob[:min_len]
        returns = returns.iloc[:min_len]

        # Position: +1 for buy signal, -1 for sell signal, 0 for hold
        threshold = getattr(strategy, "confidence_threshold", 0.65) if strategy else 0.65
        position = np.where(buy_prob > threshold, 1.0, np.where(sell_prob > threshold, -1.0, 0.0))
        strategy_returns = pd.Series(position * returns.values, index=returns.index)

        # Metrics
        total_return = strategy_returns.sum()
        n_trades = int((np.diff(position) != 0).sum())
        win_trades = int((strategy_returns > 0).sum())
        total_trades = int((strategy_returns != 0).sum())
        win_rate = win_trades / total_trades if total_trades > 0 else 0.0

        # Sharpe ratio (annualized, assuming daily returns)
        if strategy_returns.std() > 0:
            sharpe = (strategy_returns.mean() / strategy_returns.std()) * np.sqrt(252)
        else:
            sharpe = 0.0

        # Max drawdown
        cumulative = (1 + strategy_returns).cumprod()
        rolling_max = cumulative.cummax()
        drawdown = (cumulative - rolling_max) / rolling_max
        max_drawdown = float(drawdown.min()) if len(drawdown) > 0 else 0.0

        # Profit factor
        gross_profit = strategy_returns[strategy_returns > 0].sum()
        gross_loss = abs(strategy_returns[strategy_returns < 0].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        return {
            "fold": fold_idx,
            "sharpe": round(float(sharpe), 4),
            "total_return": round(float(total_return), 4),
            "max_drawdown": round(float(max_drawdown), 4),
            "win_rate": round(float(win_rate), 4),
            "profit_factor": round(float(profit_factor), 4),
            "n_trades": n_trades,
            "train_size": len(y_true),
        }

    @staticmethod
    def calculate_statistics(results: list[dict]) -> dict:
        """
        Calculate aggregate statistics from CPCV results.

        Returns summary across all folds for hypothesis evaluation.
        """
        if not results:
            return {
                "sharpe_mean": 0.0, "sharpe_std": 0.0, "sharpe_median": 0.0,
                "returns_mean": 0.0, "returns_std": 0.0,
                "max_drawdown_mean": 0.0, "max_drawdown_worst": 0.0,
                "win_rate_mean": 0.0, "win_rate_std": 0.0,
                "profit_factor_mean": 0.0,
                "num_paths_profitable": 0, "total_paths": 0,
            }

        sharpes = [r["sharpe"] for r in results]
        returns = [r["total_return"] for r in results]
        drawdowns = [r["max_drawdown"] for r in results]
        win_rates = [r["win_rate"] for r in results]
        profit_factors = [r["profit_factor"] for r in results if r["profit_factor"] != float("inf")]

        return {
            "sharpe_mean": round(float(np.mean(sharpes)), 4),
            "sharpe_std": round(float(np.std(sharpes)), 4),
            "sharpe_median": round(float(np.median(sharpes)), 4),
            "returns_mean": round(float(np.mean(returns)), 4),
            "returns_std": round(float(np.std(returns)), 4),
            "max_drawdown_mean": round(float(np.mean(drawdowns)), 4),
            "max_drawdown_worst": round(float(min(drawdowns)), 4),
            "win_rate_mean": round(float(np.mean(win_rates)), 4),
            "win_rate_std": round(float(np.std(win_rates)), 4),
            "profit_factor_mean": round(float(np.mean(profit_factors)), 4) if profit_factors else 0.0,
            "num_paths_profitable": int(sum(1 for r in returns if r > 0)),
            "total_paths": len(results),
        }
