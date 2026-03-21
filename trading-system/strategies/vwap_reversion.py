"""
Strategy 6: VWAP Mean Reversion (Intraday).

Theory: VWAP represents "fair value" for institutional traders.
When price deviates significantly, institutional buy/sell programs
create gravitational pull back to VWAP. Works best during institutional
activity windows (first 2 hours, last 1.5 hours).

This is a market microstructure play, not a fundamental view.
"""

from __future__ import annotations

from strategies.base import BaseStrategy, Signal


class VWAPReversionStrategy(BaseStrategy):
    """Intraday VWAP mean reversion strategy."""

    def check_entry(self, features: dict[str, float], current_price: float) -> Signal | None:
        atr = features.get("atr_14", 0.0)
        if atr <= 0:
            return None

        # Note: Time-of-day filtering is handled by the execution layer,
        # which only calls this during institutional windows.

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
                        f"VWAP reversion LONG: price {features.get('vwap_distance', 0):.2f} ATR below VWAP, "
                        f"volume active ({features.get('volume_ratio', 0):.1f}x), "
                        f"not trending (ADX={features.get('adx_14', 0):.1f})."
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
                        f"VWAP reversion SHORT: price {features.get('vwap_distance', 0):.2f} ATR above VWAP, "
                        f"volume active ({features.get('volume_ratio', 0):.1f}x), "
                        f"not trending (ADX={features.get('adx_14', 0):.1f})."
                    ),
                )

        return None

    def calculate_take_profit(self, current_price: float, atr: float, direction: str) -> float:
        # Target is VWAP itself (distance = 0)
        # Approximate: move half the current distance back toward VWAP
        # The actual VWAP target is tracked by the execution layer
        distance = atr * 1.5  # Expected move back to VWAP
        if direction == "long":
            return current_price + distance
        else:
            return current_price - distance

    def check_exit(
        self,
        features: dict[str, float],
        current_price: float,
        entry_price: float,
        direction: str,
        holding_days: int,
    ) -> tuple[bool, str]:
        vwap_dist = features.get("vwap_distance", 0)

        # Exit: price returned to VWAP
        if direction == "long" and vwap_dist >= 0:
            return True, "Price returned to VWAP"
        if direction == "short" and vwap_dist <= 0:
            return True, "Price returned to VWAP"

        # Intraday strategy: always close before market close
        # (handled by execution layer with time check, but holding_days > 0 catches it)
        if holding_days >= 1:
            return True, "End of day — closing intraday position"

        return False, ""

    def _check_long_conditions(self, f: dict[str, float]) -> bool:
        return (
            f.get("vwap_distance", 0) < -1.5
            and f.get("volume_ratio", 0) > 1.2
            and f.get("adx_14", 100) < 30
        )

    def _check_short_conditions(self, f: dict[str, float]) -> bool:
        return (
            f.get("vwap_distance", 0) > 1.5
            and f.get("volume_ratio", 0) > 1.2
            and f.get("adx_14", 100) < 30
        )

    def _calculate_confidence(self, f: dict[str, float], direction: str) -> float:
        scores: list[float] = []
        dist = abs(f.get("vwap_distance", 0))
        scores.append(min(1.0, (dist - 1.5) / 2.5))
        scores.append(min(1.0, (f.get("volume_ratio", 0) - 1.2) / 2.8))
        scores.append(max(0, 1.0 - f.get("adx_14", 30) / 30))

        raw = sum(max(0, s) for s in scores) / len(scores)
        return 0.5 + 0.5 * raw
