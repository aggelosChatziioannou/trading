"""
Strategy 4: Volatility Breakout (Keltner Channel).

Theory: After low-volatility consolidation, markets make directional moves
when volatility expands. Low vol = equilibrium; a catalyst breaks it,
triggering stop-loss cascades. Using Keltner (EMA ± ATR) rather than
Bollinger because ATR is more robust to gaps and extreme moves.

Academic basis: Mandelbrot (1963), Cont (2001).
"""

from __future__ import annotations

from strategies.base import BaseStrategy, Signal


class VolatilityBreakoutStrategy(BaseStrategy):
    """Keltner channel breakout strategy."""

    def check_entry(self, features: dict[str, float], current_price: float) -> Signal | None:
        atr = features.get("atr_14", 0.0)
        if atr <= 0:
            return None

        if self._check_long_conditions(features, current_price):
            confidence = self._calculate_confidence(features, "long")
            if confidence >= self.confidence_threshold:
                return self._build_signal(
                    direction="long",
                    confidence=confidence,
                    current_price=current_price,
                    atr=atr,
                    features=features,
                    explanation=(
                        f"Volatility breakout LONG: BB squeeze detected, price broke above "
                        f"upper Keltner ({features.get('upper_keltner', 0):.2f}), "
                        f"trend forming (ADX={features.get('adx_14', 0):.1f}), "
                        f"volume confirms ({features.get('volume_ratio', 0):.1f}x avg)."
                    ),
                )

        if self._check_short_conditions(features, current_price):
            confidence = self._calculate_confidence(features, "short")
            if confidence >= self.confidence_threshold:
                return self._build_signal(
                    direction="short",
                    confidence=confidence,
                    current_price=current_price,
                    atr=atr,
                    features=features,
                    explanation=(
                        f"Volatility breakout SHORT: BB squeeze detected, price broke below "
                        f"lower Keltner ({features.get('lower_keltner', 0):.2f}), "
                        f"trend forming (ADX={features.get('adx_14', 0):.1f}), "
                        f"volume confirms ({features.get('volume_ratio', 0):.1f}x avg)."
                    ),
                )

        return None

    def calculate_stop_loss(self, current_price: float, atr: float, direction: str) -> float:
        # Override: use Keltner midline as stop
        # In real use, caller should provide keltner_mid via features
        # Fallback to 2 ATR if midline not available
        return current_price - (2 * atr) if direction == "long" else current_price + (2 * atr)

    def check_exit(
        self,
        features: dict[str, float],
        current_price: float,
        entry_price: float,
        direction: str,
        holding_days: int,
    ) -> tuple[bool, str]:
        # Exit 1: Trend fading
        if features.get("adx_14", 0) < 15:
            return True, "ADX dropped below 15 — trend fading"

        # Exit 2: Price back inside Keltner (failed breakout)
        upper_k = features.get("upper_keltner", float("inf"))
        lower_k = features.get("lower_keltner", float("-inf"))
        if direction == "long" and current_price < upper_k:
            # Only exit if we've been above for a while then fell back
            if holding_days > 1:
                return True, "Price fell back inside Keltner channel"
        if direction == "short" and current_price > lower_k:
            if holding_days > 1:
                return True, "Price rose back inside Keltner channel"

        if holding_days > 10:
            return True, "Max holding period (10 days) exceeded"

        return False, ""

    def _check_long_conditions(self, f: dict[str, float], price: float) -> bool:
        return (
            f.get("bb_squeeze", 0) > 0
            and price > f.get("upper_keltner", float("inf"))
            and f.get("adx_14", 0) > 20
            and f.get("volume_ratio", 0) > 1.5
            and f.get("sent_24h", 0) >= -0.2
        )

    def _check_short_conditions(self, f: dict[str, float], price: float) -> bool:
        return (
            f.get("bb_squeeze", 0) > 0
            and price < f.get("lower_keltner", float("-inf"))
            and f.get("adx_14", 0) > 20
            and f.get("volume_ratio", 0) > 1.5
            and f.get("sent_24h", 0) <= 0.2
        )

    def _calculate_confidence(self, f: dict[str, float], direction: str) -> float:
        scores: list[float] = []
        scores.append(min(1.0, (f.get("adx_14", 0) - 20) / 30))
        scores.append(min(1.0, (f.get("volume_ratio", 0) - 1.5) / 3.5))
        scores.append(1.0 if f.get("bb_squeeze", 0) > 0 else 0.0)

        raw = sum(max(0, s) for s in scores) / len(scores)
        return 0.5 + 0.5 * raw
