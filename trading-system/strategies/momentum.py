"""
Strategy 2: News Momentum.

Theory: Significant news creates information asymmetry. The initial price
reaction often underreacts because liquidity providers widen spreads,
participants wait for confirmation, and institutions take time to act.
This creates a 1-3 day drift in the direction of the initial move.

Academic basis: Chan (2003), Tetlock et al. (2008).
"""

from __future__ import annotations

from strategies.base import BaseStrategy, Signal


class NewsMomentumStrategy(BaseStrategy):
    """News-driven momentum strategy."""

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
                        f"News momentum LONG: strong positive sentiment ({features.get('sent_4h', 0):.2f}) "
                        f"with {features.get('sent_volume_4h', 0):.0f} articles, "
                        f"source agreement {features.get('sent_source_agreement', 0):.2f}, "
                        f"price confirming (ROC5={features.get('roc_5', 0):.2f}%), "
                        f"volume spike ({features.get('volume_ratio', 0):.1f}x)."
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
                        f"News momentum SHORT: strong negative sentiment ({features.get('sent_4h', 0):.2f}) "
                        f"with {features.get('sent_volume_4h', 0):.0f} articles, "
                        f"source agreement {features.get('sent_source_agreement', 0):.2f}, "
                        f"price confirming (ROC5={features.get('roc_5', 0):.2f}%), "
                        f"volume spike ({features.get('volume_ratio', 0):.1f}x)."
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
        # Exit 1: Sentiment momentum reverses
        sent_mom = features.get("sent_momentum", 0)
        if direction == "long" and sent_mom < 0:
            return True, "Sentiment momentum turned negative"
        if direction == "short" and sent_mom > 0:
            return True, "Sentiment momentum turned positive"

        # Exit 2: Volume drying up
        if features.get("volume_ratio", 1.0) < 1.0:
            return True, "Volume dropped below average"

        # Exit 3: Time limit
        if holding_days > 3:
            return True, "Max holding period (3 days) exceeded"

        return False, ""

    def _check_long_conditions(self, f: dict[str, float]) -> bool:
        return (
            f.get("sent_4h", 0) > 0.6
            and f.get("sent_volume_4h", 0) >= 3
            and f.get("sent_source_agreement", 0) > 0.7
            and f.get("roc_5", 0) > 0
            and f.get("volume_ratio", 0) > 2.0
        )

    def _check_short_conditions(self, f: dict[str, float]) -> bool:
        return (
            f.get("sent_4h", 0) < -0.6
            and f.get("sent_volume_4h", 0) >= 3
            and f.get("sent_source_agreement", 0) > 0.7
            and f.get("roc_5", 0) < 0
            and f.get("volume_ratio", 0) > 2.0
        )

    def _calculate_confidence(self, f: dict[str, float], direction: str) -> float:
        scores: list[float] = []
        sent_4h = abs(f.get("sent_4h", 0))
        scores.append(min(1.0, (sent_4h - 0.6) / 0.4))
        scores.append(min(1.0, f.get("sent_volume_4h", 0) / 10.0))
        scores.append(f.get("sent_source_agreement", 0))
        scores.append(min(1.0, (f.get("volume_ratio", 0) - 2.0) / 3.0))

        raw = sum(max(0, s) for s in scores) / len(scores)
        return 0.5 + 0.5 * raw
