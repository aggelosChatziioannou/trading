"""
Signal ensemble combining price model and sentiment model.

Logic:
1. Get signal from LightGBM (price + all features)
2. Get signal from sentiment-only model
3. If BOTH agree → high conviction, full position size
4. If DISAGREE → low conviction, half position size or skip
5. Final confidence = min(price_conf, sent_conf) * agreement_factor
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from models.lightgbm_model import TradingLGBM
from models.sentiment_model import SentimentModel

logger = logging.getLogger(__name__)


class SignalEnsemble:
    """
    Combine price model and sentiment model signals.

    Agreement between models increases conviction.
    Disagreement reduces position size or skips the trade.
    """

    def __init__(self, price_model: TradingLGBM, sentiment_model: SentimentModel) -> None:
        self.price_model = price_model
        self.sentiment_model = sentiment_model

    def generate_signal(
        self,
        features: pd.DataFrame,
        strategy_name: str,
        hypothesis_id: str,
    ) -> dict:
        """
        Generate final trading signal from ensemble.

        Args:
            features: Feature DataFrame (single row or batch — uses last row).
            strategy_name: Name of the strategy requesting the signal.
            hypothesis_id: Hypothesis ID for logging.

        Returns:
            Dict with:
                action: 'buy' | 'sell' | 'hold'
                confidence: float
                position_size_factor: float (1.0 if agree, 0.5 if disagree)
                strategy: str
                hypothesis_id: str
                explanation: str
                price_model_signal: dict
                sentiment_model_signal: dict
                agreement: bool
        """
        if isinstance(features, pd.Series):
            features = features.to_frame().T

        # Get signals from both models
        price_signals = self.price_model.get_signal(features)
        sent_signals = self.sentiment_model.get_signal(features)

        price_action, price_conf, price_expl = price_signals[-1]
        sent_action, sent_conf, sent_expl = sent_signals[-1]

        # Check agreement
        agreement = price_action == sent_action

        if agreement and price_action != "hold":
            # Both agree on direction → high conviction
            action = price_action
            confidence = min(price_conf, sent_conf)
            position_size_factor = 1.0
            explanation = (
                f"ENSEMBLE AGREE ({action}): "
                f"Price model: {price_expl}. "
                f"Sentiment model: {sent_expl}."
            )
        elif price_action != "hold" and sent_action == "hold":
            # Price model has signal, sentiment is neutral → moderate conviction
            action = price_action
            confidence = price_conf * 0.7  # Reduce confidence
            position_size_factor = 0.5
            explanation = (
                f"PRICE ONLY ({action}): "
                f"Price model: {price_expl}. "
                f"Sentiment: neutral — half position."
            )
        elif sent_action != "hold" and price_action == "hold":
            # Sentiment has signal, price doesn't → low conviction
            action = "hold"  # Don't trade on sentiment alone
            confidence = 0.0
            position_size_factor = 0.0
            explanation = (
                f"SENTIMENT ONLY (skip): "
                f"Sentiment: {sent_expl}. "
                f"Price model: no confirmation — skipping."
            )
        elif price_action != sent_action and price_action != "hold" and sent_action != "hold":
            # Conflicting signals → skip
            action = "hold"
            confidence = 0.0
            position_size_factor = 0.0
            explanation = (
                f"CONFLICT (skip): "
                f"Price says {price_action} ({price_expl}), "
                f"Sentiment says {sent_action} ({sent_expl})."
            )
        else:
            # Both say hold
            action = "hold"
            confidence = 0.0
            position_size_factor = 0.0
            explanation = "Both models: hold. No signal."

        return {
            "action": action,
            "confidence": round(confidence, 4),
            "position_size_factor": position_size_factor,
            "strategy": strategy_name,
            "hypothesis_id": hypothesis_id,
            "explanation": explanation,
            "price_model_signal": {
                "action": price_action,
                "confidence": round(price_conf, 4),
                "explanation": price_expl,
            },
            "sentiment_model_signal": {
                "action": sent_action,
                "confidence": round(sent_conf, 4),
                "explanation": sent_expl,
            },
            "agreement": agreement,
        }
