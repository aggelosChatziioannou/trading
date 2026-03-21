"""
Strategy 3: Sentiment-Price Divergence.

Theory: When price and sentiment diverge, the narrative is shifting before
price catches up. News leads price by 1-3 days because journalists have
insider access, analyst sentiment shifts precede downgrades, and social
media captures grassroots changes.

Academic basis: Baker & Wurgler (2006).
"""

from __future__ import annotations

from strategies.base import BaseStrategy, Signal


class SentimentDivergenceStrategy(BaseStrategy):
    """Sentiment-price divergence strategy."""

    def check_entry(self, features: dict[str, float], current_price: float) -> Signal | None:
        atr = features.get("atr_14", 0.0)
        if atr <= 0:
            return None

        if self._check_long_conditions(features):
            confidence = self._calculate_confidence(features, "long")
            if confidence >= self.confidence_threshold:
                return self._build_signal(
                    direction="long",
                    confidence=confidence,
                    current_price=current_price,
                    atr=atr,
                    features=features,
                    explanation=(
                        f"Sentiment divergence LONG: price weak (vs SMA50={features.get('price_vs_sma50', 0):.2f} ATR) "
                        f"but sentiment improving (momentum={features.get('sent_momentum', 0):.2f}). "
                        f"Divergence score: {features.get('price_sent_divergence', 0):.2f}."
                    ),
                )

        if self._check_short_conditions(features):
            confidence = self._calculate_confidence(features, "short")
            if confidence >= self.confidence_threshold:
                return self._build_signal(
                    direction="short",
                    confidence=confidence,
                    current_price=current_price,
                    atr=atr,
                    features=features,
                    explanation=(
                        f"Sentiment divergence SHORT: price strong (vs SMA50={features.get('price_vs_sma50', 0):.2f} ATR) "
                        f"but sentiment deteriorating (momentum={features.get('sent_momentum', 0):.2f}). "
                        f"Divergence score: {features.get('price_sent_divergence', 0):.2f}."
                    ),
                )

        return None

    def check_exit(
        self,
        features: dict[str, float],
        current_price: float,
        entry_price: float,
        direction: str,
        holding_days: int,
    ) -> tuple[bool, str]:
        divergence = features.get("price_sent_divergence", 0)

        # Exit: divergence resolved (crossed zero)
        if direction == "long" and divergence <= 0:
            return True, "Divergence resolved (score crossed zero)"
        if direction == "short" and divergence >= 0:
            return True, "Divergence resolved (score crossed zero)"

        if holding_days > 7:
            return True, "Max holding period (7 days) exceeded"

        return False, ""

    def _check_long_conditions(self, f: dict[str, float]) -> bool:
        return (
            f.get("price_vs_sma50", 0) < -1.0
            and f.get("sent_7d", 0) < 0
            and f.get("sent_momentum", 0) > 0.15
            and f.get("price_sent_divergence", 0) > 0.3
        )

    def _check_short_conditions(self, f: dict[str, float]) -> bool:
        return (
            f.get("price_vs_sma50", 0) > 1.0
            and f.get("sent_7d", 0) > 0
            and f.get("sent_momentum", 0) < -0.15
            and f.get("price_sent_divergence", 0) < -0.3
        )

    def _calculate_confidence(self, f: dict[str, float], direction: str) -> float:
        scores: list[float] = []
        div = abs(f.get("price_sent_divergence", 0))
        scores.append(min(1.0, (div - 0.3) / 0.7))
        scores.append(min(1.0, abs(f.get("sent_momentum", 0)) / 0.5))
        scores.append(min(1.0, abs(f.get("price_vs_sma50", 0)) / 3.0))

        raw = sum(max(0, s) for s in scores) / len(scores)
        return 0.5 + 0.5 * raw
