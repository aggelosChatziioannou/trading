"""
Feature importance analysis.

Analyzes which features actually matter for the model's predictions.
Helps validate that the model is using interpretable, theoretically
justified features — not just noise.

If the top features don't make theoretical sense, the model may
be overfitting to artifacts.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from models.lightgbm_model import TradingLGBM

logger = logging.getLogger(__name__)


class FeatureImportanceAnalyzer:
    """Analyze and validate feature importance from the trading model."""

    # Features we expect to be important based on theory
    THEORETICALLY_IMPORTANT = {
        "rsi_14",           # Mean reversion core
        "bb_position",      # Overbought/oversold
        "volume_ratio",     # Confirmation
        "sent_24h",         # Sentiment signal
        "sent_momentum",    # Sentiment trend
        "adx_14",           # Trend strength
        "atr_ratio",        # Volatility regime
        "vwap_distance",    # Institutional fair value
        "price_sent_divergence",  # Cross-feature: our edge
    }

    @staticmethod
    def analyze(model: TradingLGBM) -> dict:
        """
        Get feature importance analysis.

        Returns:
            Dict with:
                ranking: List of (feature, importance) sorted descending.
                top_10: Top 10 features.
                theoretical_coverage: Fraction of top 10 that are theoretically justified.
                warnings: List of potential issues.
        """
        importance = model.get_feature_importance()
        if not importance:
            return {"ranking": [], "top_10": [], "theoretical_coverage": 0.0, "warnings": ["Model not trained"]}

        # Sort by importance
        ranking = sorted(importance.items(), key=lambda x: x[1], reverse=True)
        top_10 = ranking[:10]

        # Check theoretical coverage
        top_10_names = {name for name, _ in top_10}
        theoretical_in_top = top_10_names & FeatureImportanceAnalyzer.THEORETICALLY_IMPORTANT
        coverage = len(theoretical_in_top) / min(10, len(ranking))

        warnings: list[str] = []
        if coverage < 0.3:
            warnings.append(
                f"Only {len(theoretical_in_top)}/10 top features are theoretically justified. "
                "Model may be fitting noise."
            )

        # Check for suspiciously dominant features
        if ranking:
            total_imp = sum(v for _, v in ranking)
            if total_imp > 0:
                top_pct = ranking[0][1] / total_imp
                if top_pct > 0.5:
                    warnings.append(
                        f"Top feature '{ranking[0][0]}' accounts for {top_pct:.0%} of importance. "
                        "Model may be overly dependent on a single feature."
                    )

        logger.info("Feature importance: top 3 = %s", [(n, round(v, 2)) for n, v in ranking[:3]])
        if warnings:
            for w in warnings:
                logger.warning(w)

        return {
            "ranking": [(n, round(v, 4)) for n, v in ranking],
            "top_10": [(n, round(v, 4)) for n, v in top_10],
            "theoretical_coverage": round(coverage, 2),
            "warnings": warnings,
        }
