"""
Sentiment-only model.

Simple logistic regression using only sentiment features.
Acts as a secondary signal source for the ensemble.

Intentionally simple — if sentiment alone has predictive power,
we want to detect it with a model that can't overfit complex patterns.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

logger = logging.getLogger(__name__)

# Sentiment feature names
SENTIMENT_FEATURES = [
    "sent_4h", "sent_24h", "sent_7d",
    "sent_momentum", "sent_volume_4h", "sent_volume_24h",
    "sent_dispersion", "sent_extreme", "sent_source_agreement",
]


class SentimentModel:
    """
    Logistic regression on sentiment features only.

    Uses L2 regularization (C=1.0) to prevent overfitting.
    Simple model by design — complexity comes from the ensemble.
    """

    def __init__(self) -> None:
        self._model: LogisticRegression | None = None

    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        """Train from scratch on sentiment features only."""
        sent_cols = [c for c in SENTIMENT_FEATURES if c in X_train.columns]
        if not sent_cols:
            logger.warning("No sentiment features found in training data")
            return

        X_sent = X_train[sent_cols].fillna(0)

        self._model = LogisticRegression(
            C=1.0,              # Standard regularization
            max_iter=1000,
            multi_class="multinomial",
            solver="lbfgs",
            random_state=42,
        )
        self._model.fit(X_sent, y_train)
        logger.info("Trained sentiment model on %d samples, %d features", len(X_sent), len(sent_cols))

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return probability distribution over 5 classes."""
        if self._model is None:
            # Return uniform distribution if not trained
            n = len(X)
            return np.full((n, 5), 0.2)

        sent_cols = [c for c in SENTIMENT_FEATURES if c in X.columns]
        X_sent = X[sent_cols].fillna(0)
        return self._model.predict_proba(X_sent)

    def get_signal(self, X: pd.DataFrame, threshold: float = 0.60) -> list[tuple[str, float, str]]:
        """Generate trading signals from sentiment model."""
        proba = self.predict_proba(X)
        results: list[tuple[str, float, str]] = []

        for i in range(len(proba)):
            p = proba[i]
            buy_prob = p[3] + p[4]
            sell_prob = p[0] + p[1]

            if buy_prob > threshold:
                results.append(("buy", float(buy_prob), f"Sentiment bullish: P={buy_prob:.3f}"))
            elif sell_prob > threshold:
                results.append(("sell", float(sell_prob), f"Sentiment bearish: P={sell_prob:.3f}"))
            else:
                results.append(("hold", float(p[2]), f"Sentiment neutral"))

        return results
