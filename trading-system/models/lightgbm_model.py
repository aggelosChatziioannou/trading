"""
LightGBM classifier for signal generation.

INTENTIONALLY SIMPLE configuration to prevent overfitting.
Parameters are FIXED and NOT tuned per CPCV fold.
They are set based on general ML best practices for tabular financial data.
Changing them requires a THEORETICAL justification, not an empirical one.

Target: next-day return bucket (5 classes).
Output: probability distribution used for signal confidence.
"""

from __future__ import annotations

import logging
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from config.settings import settings

logger = logging.getLogger(__name__)

_cfg = settings.model


class TradingLGBM:
    """
    LightGBM multiclass classifier for trading signals.

    FIXED parameters — not tuned per fold. See ModelConfig for rationale.
    """

    FIXED_PARAMS: dict[str, Any] = {
        "objective": "multiclass",
        "num_class": 5,
        "max_depth": _cfg.max_depth,
        "num_leaves": _cfg.num_leaves,
        "n_estimators": _cfg.n_estimators,
        "learning_rate": _cfg.learning_rate,
        "subsample": _cfg.subsample,
        "colsample_bytree": _cfg.colsample_bytree,
        "min_child_samples": _cfg.min_child_samples,
        "reg_alpha": _cfg.reg_alpha,
        "reg_lambda": _cfg.reg_lambda,
        "random_state": _cfg.random_state,
        "verbose": -1,
    }

    def __init__(self) -> None:
        self._model: lgb.LGBMClassifier | None = None
        self._feature_names: list[str] = []

    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        """
        Train from scratch. No warm-starting.

        Args:
            X_train: Feature matrix.
            y_train: Target labels (0-4 for 5 return buckets).
        """
        self._feature_names = list(X_train.columns)
        self._model = lgb.LGBMClassifier(**self.FIXED_PARAMS)
        self._model.fit(X_train, y_train)
        logger.info("Trained LightGBM on %d samples, %d features", len(X_train), len(self._feature_names))

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Return probability distribution over 5 classes.

        Args:
            X: Feature matrix.

        Returns:
            Array of shape (n_samples, 5) with class probabilities.
        """
        if self._model is None:
            raise RuntimeError("Model not trained. Call train() first.")
        return self._model.predict_proba(X)

    def get_signal(
        self, X: pd.DataFrame, threshold: float = 0.65
    ) -> list[tuple[str, float, str]]:
        """
        Generate trading signals with confidence.

        Args:
            X: Feature matrix (can be single row or batch).
            threshold: Minimum probability to act.

        Returns:
            List of (signal, confidence, explanation) tuples.
            signal: 'buy', 'sell', or 'hold'
            confidence: float [0, 1]
            explanation: human-readable string
        """
        proba = self.predict_proba(X)
        results: list[tuple[str, float, str]] = []

        labels = list(_cfg.bucket_labels)

        for i in range(len(proba)):
            p = proba[i]
            buy_prob = p[3] + p[4]    # buy + strong_buy
            sell_prob = p[0] + p[1]   # strong_sell + sell
            hold_prob = p[2]

            if buy_prob > threshold:
                signal = "buy"
                confidence = float(buy_prob)
                top_class = labels[3] if p[3] > p[4] else labels[4]
                explanation = f"Buy signal: P(buy+strong_buy)={buy_prob:.3f} (top: {top_class}={p[np.argmax(p)]:.3f})"
            elif sell_prob > threshold:
                signal = "sell"
                confidence = float(sell_prob)
                top_class = labels[0] if p[0] > p[1] else labels[1]
                explanation = f"Sell signal: P(sell+strong_sell)={sell_prob:.3f} (top: {top_class}={p[np.argmax(p)]:.3f})"
            else:
                signal = "hold"
                confidence = float(hold_prob)
                explanation = f"Hold: no strong conviction (buy={buy_prob:.3f}, sell={sell_prob:.3f})"

            results.append((signal, confidence, explanation))

        return results

    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importance scores from the trained model."""
        if self._model is None:
            return {}
        importance = self._model.feature_importances_
        return dict(zip(self._feature_names, importance.tolist()))


def create_labels(ohlcv: pd.DataFrame) -> pd.Series:
    """
    Create target labels from OHLCV data.

    Maps next-day returns to 5 buckets:
    0: strong_sell (return < -1.5%)
    1: sell (-1.5% ≤ return < -0.5%)
    2: hold (-0.5% ≤ return < 0.5%)
    3: buy (0.5% ≤ return < 1.5%)
    4: strong_buy (return ≥ 1.5%)
    """
    next_day_return = ohlcv["close"].pct_change().shift(-1) * 100  # Percentage

    buckets = _cfg.return_buckets
    labels = pd.cut(
        next_day_return,
        bins=[float("-inf")] + list(buckets) + [float("inf")],
        labels=[0, 1, 2, 3, 4],
    ).astype(float)

    return labels
