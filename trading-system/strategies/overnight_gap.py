"""
Strategy 7: Overnight Gap Fade.

Theory: Gaps from overnight/pre-market activity often partially fill
because pre-market has thin liquidity (exaggerated moves), regular session
brings full participation, and market makers profit from fading extremes.

Filter: ONLY fade gaps NOT caused by material news (earnings, M&A).
This exploits the liquidity differential between pre-market and regular hours.
"""

from __future__ import annotations

from strategies.base import BaseStrategy, Signal


class OvernightGapStrategy(BaseStrategy):
    """Overnight gap fade strategy."""

    def check_entry(self, features: dict[str, float], current_price: float) -> Signal | None:
        atr = features.get("atr_14", 0.0)
        if atr <= 0:
            return None

        gap_size = features.get("gap_size", 0.0)

        # Fade gap UP (go short)
        if self._check_fade_gap_up(features, gap_size):
            confidence = self._calculate_confidence(features, gap_size)
            if confidence >= self.confidence_threshold:
                return self._build_signal(
                    direction="short",
                    confidence=confidence,
                    current_price=current_price,
                    atr=atr,
                    features=features,
                    explanation=(
                        f"Gap fade SHORT: +{gap_size:.2f}% gap, "
                        f"low news volume ({features.get('sent_volume_4h', 0):.0f} articles), "
                        f"sentiment not extreme ({features.get('sent_24h', 0):.2f}), "
                        f"likely liquidity-driven gap."
                    ),
                )

        # Fade gap DOWN (go long)
        if self._check_fade_gap_down(features, gap_size):
            confidence = self._calculate_confidence(features, gap_size)
            if confidence >= self.confidence_threshold:
                return self._build_signal(
                    direction="long",
                    confidence=confidence,
                    current_price=current_price,
                    atr=atr,
                    features=features,
                    explanation=(
                        f"Gap fade LONG: {gap_size:.2f}% gap, "
                        f"low news volume ({features.get('sent_volume_4h', 0):.0f} articles), "
                        f"sentiment not extreme ({features.get('sent_24h', 0):.2f}), "
                        f"likely liquidity-driven gap."
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
        # Exit: 50% gap fill achieved
        gap_size = features.get("gap_size", 0.0)
        if gap_size != 0:
            fill_pct = abs((current_price - entry_price) / (entry_price * gap_size / 100))
            if fill_pct >= 0.5:
                return True, "50% gap fill achieved"

        # Time limit: if not filled by ~11 AM, exit
        # (Controlled by execution layer, but holding_days catches overnight)
        if holding_days >= 1:
            return True, "End of gap-fill window"

        return False, ""

    def _check_fade_gap_up(self, f: dict[str, float], gap: float) -> bool:
        return (
            gap > 1.5
            and f.get("sent_24h", 1.0) < 0.4        # Not major positive news
            and f.get("sent_volume_4h", 10) < 3       # Low article count
            and f.get("volume_ratio", 0) > 1.5        # Active open
        )

    def _check_fade_gap_down(self, f: dict[str, float], gap: float) -> bool:
        return (
            gap < -1.5
            and f.get("sent_24h", -1.0) > -0.4       # Not major negative news
            and f.get("sent_volume_4h", 10) < 3
            and f.get("volume_ratio", 0) > 1.5
        )

    def _calculate_confidence(self, f: dict[str, float], gap_size: float) -> float:
        scores: list[float] = []
        # Larger gap = more opportunity (but filter already ensured it's not news-driven)
        scores.append(min(1.0, (abs(gap_size) - 1.5) / 3.5))
        # Lower sentiment = more likely to be noise gap
        scores.append(max(0, 1.0 - abs(f.get("sent_24h", 0)) / 0.4))
        # Higher volume at open = more participants to fade
        scores.append(min(1.0, (f.get("volume_ratio", 0) - 1.5) / 3.5))

        raw = sum(max(0, s) for s in scores) / len(scores)
        return 0.5 + 0.5 * raw
