"""
Strategy 1: Mean Reversion with Sentiment Confirmation.

Theory: Markets overreact to short-term news, creating temporary mispricings.
When price deviates from mean AND sentiment is disproportionately extreme,
the reversion probability increases because the move was sentiment-driven.

Academic basis: De Bondt & Thaler (1985), Tetlock (2007).
"""

from __future__ import annotations

from strategies.base import BaseStrategy, Signal


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy with sentiment confirmation."""

    def check_entry(self, features: dict[str, float], current_price: float) -> Signal | None:
        atr = features.get("atr_14", 0.0)
        if atr <= 0:
            return None

        # Check for LONG entry
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
                        f"Mean reversion LONG: price near lower BB (pos={features.get('bb_position', 0):.2f}), "
                        f"RSI oversold ({features.get('rsi_14', 0):.1f}), negative sentiment "
                        f"({features.get('sent_24h', 0):.2f}) suggests overreaction. "
                        f"High volume ({features.get('volume_ratio', 0):.1f}x avg) indicates capitulation."
                    ),
                )

        # Check for SHORT entry
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
                        f"Mean reversion SHORT: price near upper BB (pos={features.get('bb_position', 0):.2f}), "
                        f"RSI overbought ({features.get('rsi_14', 0):.1f}), positive sentiment "
                        f"({features.get('sent_24h', 0):.2f}) suggests euphoria. "
                        f"High volume ({features.get('volume_ratio', 0):.1f}x avg) indicates blow-off top."
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
        # Exit 1: Price returns to mean (BB position crosses 0.5)
        bb_pos = features.get("bb_position", 0.5)
        if direction == "long" and bb_pos >= 0.5:
            return True, "Price returned to BB midline"
        if direction == "short" and bb_pos <= 0.5:
            return True, "Price returned to BB midline"

        # Exit 2: RSI normalizes (crosses 50)
        rsi = features.get("rsi_14", 50)
        if direction == "long" and rsi >= 50:
            return True, "RSI normalized above 50"
        if direction == "short" and rsi <= 50:
            return True, "RSI normalized below 50"

        # Exit 3: Time-based (theory: reversion happens within 5 days or not at all)
        if holding_days > 5:
            return True, "Max holding period (5 days) exceeded"

        return False, ""

    def _check_long_conditions(self, f: dict[str, float]) -> bool:
        return (
            f.get("bb_position", 1.0) < 0.1
            and f.get("rsi_14", 100) < 30
            and f.get("sent_24h", 0) < -0.3
            and f.get("sent_momentum", 0) < -0.2
            and f.get("volume_ratio", 0) > 1.5
            and f.get("adx_14", 100) < 25
        )

    def _check_short_conditions(self, f: dict[str, float]) -> bool:
        return (
            f.get("bb_position", 0.0) > 0.9
            and f.get("rsi_14", 0) > 70
            and f.get("sent_24h", 0) > 0.3
            and f.get("sent_momentum", 0) > 0.2
            and f.get("volume_ratio", 0) > 1.5
            and f.get("adx_14", 100) < 25
        )

    def _calculate_confidence(self, f: dict[str, float], direction: str) -> float:
        """
        Calculate signal confidence based on how strongly conditions are met.

        Confidence is a weighted average of how far each condition exceeds its threshold.
        """
        scores: list[float] = []

        if direction == "long":
            # BB position: 0.0 is strongest (at band), 0.1 is threshold
            scores.append(max(0, (0.1 - f.get("bb_position", 0.5)) / 0.1))
            # RSI: 20 is strongest, 30 is threshold
            scores.append(max(0, (30 - f.get("rsi_14", 50)) / 30))
            # Sentiment: -1.0 is strongest, -0.3 is threshold
            scores.append(max(0, (-0.3 - f.get("sent_24h", 0)) / 0.7))
            # Volume: higher is better
            scores.append(min(1.0, max(0, (f.get("volume_ratio", 0) - 1.5) / 3.5)))
        else:
            scores.append(max(0, (f.get("bb_position", 0.5) - 0.9) / 0.1))
            scores.append(max(0, (f.get("rsi_14", 50) - 70) / 30))
            scores.append(max(0, (f.get("sent_24h", 0) - 0.3) / 0.7))
            scores.append(min(1.0, max(0, (f.get("volume_ratio", 0) - 1.5) / 3.5)))

        if not scores:
            return 0.0
        # Scale to [0.5, 1.0] — we already passed threshold checks
        raw = sum(scores) / len(scores)
        return 0.5 + 0.5 * raw
