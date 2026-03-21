"""
Strategy 5: Post-Earnings Announcement Drift (PEAD).

Theory: One of the most well-documented anomalies in finance.
After earnings announcements, stocks continue drifting in the direction
of the earnings surprise for 60-90 days because analysts are slow to
update, institutions have capacity constraints, and behavioral anchoring.

Enhanced with LLM sentiment analysis of earnings calls.
Academic basis: Bernard & Thomas (1989).
"""

from __future__ import annotations

from strategies.base import BaseStrategy, Signal


class EarningsDriftStrategy(BaseStrategy):
    """Post-earnings announcement drift strategy."""

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
                        f"PEAD LONG: earnings surprise >{features.get('earnings_surprise', 0):.1f}%, "
                        f"positive reaction (sent_4h={features.get('sent_4h', 0):.2f}), "
                        f"massive volume ({features.get('volume_ratio', 0):.1f}x), "
                        f"positive guidance sentiment ({features.get('guidance_sentiment', 0):.2f})."
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
                        f"PEAD SHORT: earnings miss <{features.get('earnings_surprise', 0):.1f}%, "
                        f"negative reaction (sent_4h={features.get('sent_4h', 0):.2f}), "
                        f"massive volume ({features.get('volume_ratio', 0):.1f}x), "
                        f"negative guidance sentiment ({features.get('guidance_sentiment', 0):.2f})."
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
        # PEAD plays out over weeks
        if holding_days > 20:
            return True, "Max holding period (20 days) exceeded"

        # Strong sentiment reversal
        sent_mom = features.get("sent_momentum", 0)
        if direction == "long" and sent_mom < -0.3:
            return True, "Strong sentiment reversal (negative momentum)"
        if direction == "short" and sent_mom > 0.3:
            return True, "Strong sentiment reversal (positive momentum)"

        return False, ""

    def _check_long_conditions(self, f: dict[str, float]) -> bool:
        return (
            f.get("earnings_surprise", 0) > 5.0
            and f.get("sent_4h", 0) > 0.4
            and f.get("volume_ratio", 0) > 3.0
            and f.get("roc_5", 0) > 0
            and f.get("guidance_sentiment", 0) > 0.3
        )

    def _check_short_conditions(self, f: dict[str, float]) -> bool:
        return (
            f.get("earnings_surprise", 0) < -5.0
            and f.get("sent_4h", 0) < -0.4
            and f.get("volume_ratio", 0) > 3.0
            and f.get("roc_5", 0) < 0
            and f.get("guidance_sentiment", 0) < -0.3
        )

    def _calculate_confidence(self, f: dict[str, float], direction: str) -> float:
        scores: list[float] = []
        surprise = abs(f.get("earnings_surprise", 0))
        scores.append(min(1.0, (surprise - 5) / 15))
        scores.append(min(1.0, (f.get("volume_ratio", 0) - 3.0) / 7.0))
        scores.append(min(1.0, abs(f.get("sent_4h", 0)) / 1.0))
        scores.append(min(1.0, abs(f.get("guidance_sentiment", 0)) / 1.0))

        raw = sum(max(0, s) for s in scores) / len(scores)
        return 0.5 + 0.5 * raw
