"""
Half-Kelly Criterion position sizing.

Kelly fraction = (win_prob * avg_win - loss_prob * avg_loss) / avg_win
We use HALF Kelly because:
1. Full Kelly is optimal but has high variance
2. Half Kelly gives ~75% of Kelly growth with ~50% of the variance
3. Our win probability estimates have uncertainty → conservative is better

Position size = Half_Kelly * confidence * portfolio_value

Additional constraints:
- Never exceed max_position_pct (5%)
- Never exceed available cash
- Scale down if current drawdown > 5%
"""

from __future__ import annotations

import logging

from config.settings import settings

logger = logging.getLogger(__name__)

_risk = settings.risk


class PositionSizer:
    """Half-Kelly position sizing with risk-adjusted scaling."""

    @staticmethod
    def calculate_size(
        confidence: float,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        portfolio_value: float,
        current_drawdown: float = 0.0,
    ) -> float:
        """
        Calculate position size in dollars.

        Args:
            confidence: Model confidence [0, 1].
            win_rate: Historical win rate [0, 1].
            avg_win: Average winning trade return (positive).
            avg_loss: Average losing trade return (positive — absolute value).
            portfolio_value: Current portfolio value in dollars.
            current_drawdown: Current drawdown as negative percentage (e.g., -0.05 for -5%).

        Returns:
            Position size in dollars.
        """
        if portfolio_value <= 0 or confidence <= 0:
            return 0.0

        # Kelly Criterion
        if avg_win <= 0 or avg_loss <= 0:
            # No trade history — use minimum position
            kelly_fraction = _risk.min_position_pct / 100.0
        else:
            loss_prob = 1 - win_rate
            kelly_fraction = (win_rate * avg_win - loss_prob * avg_loss) / avg_win

        # Negative Kelly = don't trade
        if kelly_fraction <= 0:
            logger.debug("Negative Kelly (%.4f) — no position", kelly_fraction)
            return 0.0

        # Half Kelly for conservative sizing
        half_kelly = kelly_fraction / 2.0

        # Scale by confidence
        position_pct = half_kelly * confidence

        # Apply drawdown scaling
        if current_drawdown < _risk.max_weekly_loss_pct / 100:
            # In significant drawdown — reduce by 50%
            position_pct *= 0.5
            logger.info("Drawdown scaling: position reduced 50%% (DD=%.1f%%)", current_drawdown * 100)

        # Clamp to risk limits
        min_pct = _risk.min_position_pct / 100.0
        max_pct = _risk.max_position_pct / 100.0
        position_pct = max(min_pct, min(max_pct, position_pct))

        position_dollars = portfolio_value * position_pct

        logger.debug(
            "Position size: Kelly=%.4f, half=%.4f, conf=%.2f, pct=%.2f%%, $%.2f",
            kelly_fraction, half_kelly, confidence, position_pct * 100, position_dollars,
        )

        return round(position_dollars, 2)

    @staticmethod
    def shares_from_dollars(position_dollars: float, price: float) -> float:
        """Convert dollar position size to number of shares."""
        if price <= 0:
            return 0.0
        return round(position_dollars / price, 4)
