"""
Regime robustness analysis.

Evaluates strategy performance across different market regimes
(bull, bear, sideways, high-vol, low-vol) to ensure the strategy
isn't just profiting from a single regime type.

A robust strategy should not have dramatically different performance
across regimes — otherwise it's a regime bet, not alpha.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class RegimeRobustness:
    """
    Analyze strategy performance across market regimes.

    Regimes are detected from SPY (or market proxy) returns and volatility.
    """

    @staticmethod
    def detect_regimes(
        market_ohlcv: pd.DataFrame,
        lookback: int = 60,
    ) -> pd.Series:
        """
        Classify each day into a market regime.

        Regimes:
        - 'bull': 60-day return > 5% AND volatility below average
        - 'bear': 60-day return < -5% AND volatility above average
        - 'high_vol': Volatility > 1.5x average (regardless of direction)
        - 'low_vol': Volatility < 0.7x average
        - 'sideways': Everything else

        Args:
            market_ohlcv: Market proxy (e.g., SPY) OHLCV data.
            lookback: Rolling window for regime detection.

        Returns:
            Series of regime labels, indexed same as input.
        """
        close = market_ohlcv["close"]
        returns = close.pct_change()

        # Rolling metrics
        rolling_return = close.pct_change(lookback)
        rolling_vol = returns.rolling(lookback).std() * np.sqrt(252)
        avg_vol = rolling_vol.expanding().mean()

        # Classify
        regime = pd.Series("sideways", index=market_ohlcv.index)

        # High volatility regime (takes priority)
        regime[rolling_vol > 1.5 * avg_vol] = "high_vol"
        # Low volatility regime
        regime[rolling_vol < 0.7 * avg_vol] = "low_vol"
        # Bull market
        regime[(rolling_return > 0.05) & (rolling_vol <= avg_vol)] = "bull"
        # Bear market
        regime[(rolling_return < -0.05) & (rolling_vol >= avg_vol)] = "bear"

        return regime

    @staticmethod
    def analyze_by_regime(
        strategy_returns: pd.Series,
        regimes: pd.Series,
    ) -> dict[str, dict]:
        """
        Calculate performance metrics for each regime.

        Args:
            strategy_returns: Daily strategy returns.
            regimes: Regime labels aligned with returns.

        Returns:
            Dict mapping regime name to performance metrics.
        """
        # Align
        common = strategy_returns.index.intersection(regimes.index)
        returns = strategy_returns.loc[common]
        regs = regimes.loc[common]

        results: dict[str, dict] = {}
        for regime in regs.unique():
            mask = regs == regime
            r = returns[mask]

            if len(r) < 5:
                continue

            sharpe = (r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else 0.0
            cumulative = (1 + r).cumprod()
            max_dd = ((cumulative - cumulative.cummax()) / cumulative.cummax()).min()

            results[regime] = {
                "n_days": int(len(r)),
                "mean_return": round(float(r.mean()), 6),
                "sharpe": round(float(sharpe), 4),
                "max_drawdown": round(float(max_dd), 4),
                "win_rate": round(float((r > 0).mean()), 4),
                "total_return": round(float(r.sum()), 4),
            }

        return results

    @staticmethod
    def is_regime_robust(regime_results: dict[str, dict], min_regimes: int = 3) -> bool:
        """
        Check if strategy is robust across regimes.

        Criteria:
        - Must have data in at least min_regimes regimes
        - Sharpe must be positive in the majority of regimes
        - No regime should have Sharpe < -0.5 (catastrophic underperformance)
        """
        if len(regime_results) < min_regimes:
            logger.warning("Only %d regimes detected (need %d)", len(regime_results), min_regimes)
            return False

        sharpes = [v["sharpe"] for v in regime_results.values()]
        positive_count = sum(1 for s in sharpes if s > 0)
        catastrophic = any(s < -0.5 for s in sharpes)

        is_robust = positive_count >= len(sharpes) / 2 and not catastrophic

        logger.info(
            "Regime robustness: %d/%d positive Sharpe, catastrophic=%s → %s",
            positive_count, len(sharpes), catastrophic, "ROBUST" if is_robust else "NOT ROBUST",
        )

        return is_robust
