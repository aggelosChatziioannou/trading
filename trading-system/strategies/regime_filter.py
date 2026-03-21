"""
Market regime detection.

Classifies the current market environment to help strategies
adapt or abstain during unfavorable conditions.

Regimes:
- Bull: trending up, low vol
- Bear: trending down, high vol
- Sideways: range-bound
- High Volatility: crisis-like conditions
- Low Volatility: complacent market

This is NOT a strategy itself — it's a filter applied to all strategies.
Some strategies work better in certain regimes (e.g., mean reversion
in sideways, momentum in trending markets).
"""

from __future__ import annotations

import logging
from enum import Enum

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOL = "high_vol"
    LOW_VOL = "low_vol"


# Which strategies are allowed in which regimes.
# If a regime isn't listed, the strategy is allowed by default.
STRATEGY_REGIME_RULES: dict[str, set[MarketRegime]] = {
    "MRS-001": {MarketRegime.SIDEWAYS, MarketRegime.LOW_VOL},          # Mean reversion: range-bound only
    "NM-001":  {MarketRegime.BULL, MarketRegime.BEAR, MarketRegime.SIDEWAYS},  # News momentum: all except extreme vol
    "SD-001":  {MarketRegime.BULL, MarketRegime.BEAR, MarketRegime.SIDEWAYS},  # Divergence: needs some trend
    "VB-001":  {MarketRegime.BULL, MarketRegime.BEAR, MarketRegime.SIDEWAYS},  # Breakout: needs vol expansion from low
    "PEAD-001": {MarketRegime.BULL, MarketRegime.BEAR, MarketRegime.SIDEWAYS, MarketRegime.LOW_VOL},  # PEAD: broad
    "VWAP-001": {MarketRegime.SIDEWAYS, MarketRegime.LOW_VOL, MarketRegime.BULL},  # VWAP: needs reversion
    "GAP-001": {MarketRegime.SIDEWAYS, MarketRegime.LOW_VOL, MarketRegime.BULL},   # Gap fade: needs normalization
}


class RegimeFilter:
    """
    Detect current market regime from broad market data.

    Uses SPY (or market proxy) to classify the regime based on
    trend direction, momentum, and volatility metrics.
    """

    @staticmethod
    def detect(market_ohlcv: pd.DataFrame) -> MarketRegime:
        """
        Detect the current market regime.

        Args:
            market_ohlcv: SPY (or proxy) OHLCV data, at least 200 bars.
                         Must have columns: close, high, low, volume.

        Returns:
            Current MarketRegime.
        """
        if len(market_ohlcv) < 60:
            logger.warning("Insufficient data for regime detection (%d bars)", len(market_ohlcv))
            return MarketRegime.SIDEWAYS

        close = market_ohlcv["close"]
        returns = close.pct_change().dropna()

        # 60-day return (trend direction)
        rolling_return = float(close.iloc[-1] / close.iloc[-60] - 1) if len(close) >= 60 else 0.0

        # Realized volatility (annualized)
        recent_vol = float(returns.tail(20).std() * np.sqrt(252))
        long_vol = float(returns.tail(60).std() * np.sqrt(252))

        # Vol ratio
        vol_ratio = recent_vol / long_vol if long_vol > 0 else 1.0

        # SMA trend
        sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else float(close.iloc[-1])
        sma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else sma_50
        current = float(close.iloc[-1])

        # Classification logic
        if vol_ratio > 1.5 and recent_vol > 0.25:
            regime = MarketRegime.HIGH_VOL
        elif vol_ratio < 0.7 and recent_vol < 0.12:
            regime = MarketRegime.LOW_VOL
        elif rolling_return > 0.05 and current > sma_50:
            regime = MarketRegime.BULL
        elif rolling_return < -0.05 and current < sma_50:
            regime = MarketRegime.BEAR
        else:
            regime = MarketRegime.SIDEWAYS

        logger.info(
            "Market regime: %s (60d return=%.2f%%, vol=%.2f%%, vol_ratio=%.2f)",
            regime.value, rolling_return * 100, recent_vol * 100, vol_ratio,
        )

        return regime

    @staticmethod
    def is_strategy_allowed(hypothesis_id: str, regime: MarketRegime) -> bool:
        """
        Check if a strategy is allowed to trade in the current regime.

        Args:
            hypothesis_id: Strategy's hypothesis ID.
            regime: Current market regime.

        Returns:
            True if strategy can trade, False if it should abstain.
        """
        allowed_regimes = STRATEGY_REGIME_RULES.get(hypothesis_id)

        # If no rules defined, strategy is allowed in all regimes
        if allowed_regimes is None:
            return True

        return regime in allowed_regimes
