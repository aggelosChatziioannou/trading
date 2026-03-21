"""
Deflated Sharpe Ratio (DSR).

Based on Bailey & Lopez de Prado (2014).

When we test N hypotheses, the expected maximum Sharpe ratio
increases with N even if ALL hypotheses are worthless (pure noise).
DSR adjusts the observed Sharpe for multiple testing.

DSR > 0 with p-value < 0.05 = Strategy passes the test.
"""

from __future__ import annotations

import logging

import numpy as np
from scipy import stats

from config.settings import settings

logger = logging.getLogger(__name__)


class DeflatedSharpe:
    """
    Adjust Sharpe Ratio for multiple hypothesis testing.

    Accounts for:
    - Number of trials (hypotheses tested)
    - Skewness of returns
    - Kurtosis of returns
    - Sample size
    """

    def calculate(
        self,
        observed_sharpe: float,
        n_trials: int,
        returns_series: np.ndarray | list[float],
    ) -> dict:
        """
        Calculate Deflated Sharpe Ratio.

        Args:
            observed_sharpe: Best Sharpe ratio from CPCV.
            n_trials: Total number of hypotheses ever tested
                     (from hypothesis_log — includes ALL failures).
            returns_series: Return series from the best strategy.

        Returns:
            Dict with:
                deflated_sharpe: float
                p_value: float
                passes_test: bool (p_value < significance level)
                expected_max_sharpe: float (what you'd expect from noise)
        """
        returns = np.array(returns_series, dtype=float)
        returns = returns[np.isfinite(returns)]

        if len(returns) < 10:
            logger.warning("Too few returns (%d) for DSR calculation", len(returns))
            return {
                "deflated_sharpe": 0.0,
                "p_value": 1.0,
                "passes_test": False,
                "expected_max_sharpe": 0.0,
            }

        n = len(returns)
        skew = float(stats.skew(returns))
        kurt = float(stats.kurtosis(returns, fisher=True))  # Excess kurtosis

        # Expected maximum Sharpe ratio under null hypothesis
        # E[max(SR)] ≈ sqrt(2 * log(N)) * (1 - γ/log(N)) + γ/sqrt(2*log(N))
        # where γ is the Euler-Mascheroni constant ≈ 0.5772
        if n_trials <= 1:
            expected_max_sr = 0.0
        else:
            euler_gamma = 0.5772156649
            log_n = np.log(n_trials)
            expected_max_sr = (
                np.sqrt(2 * log_n)
                * (1 - euler_gamma / log_n)
                + euler_gamma / np.sqrt(2 * log_n)
            )

        # Standard error of the Sharpe ratio
        # SE(SR) = sqrt((1 - skew*SR + (kurt-1)/4 * SR^2) / n)
        sr = observed_sharpe
        se_sr = np.sqrt(
            (1 - skew * sr + ((kurt - 1) / 4) * sr ** 2) / n
        )

        if se_sr <= 0:
            se_sr = 1e-10  # Avoid division by zero

        # Deflated Sharpe = (observed_SR - expected_max_SR) / SE(SR)
        dsr = (sr - expected_max_sr) / se_sr

        # p-value from standard normal
        p_value = 1 - stats.norm.cdf(dsr)
        passes = p_value < settings.validation.dsr_significance

        logger.info(
            "DSR = %.4f (observed SR=%.4f, expected max SR=%.4f, n_trials=%d, p=%.4f) → %s",
            dsr, sr, expected_max_sr, n_trials, p_value, "PASS" if passes else "FAIL",
        )

        return {
            "deflated_sharpe": round(float(dsr), 4),
            "p_value": round(float(p_value), 4),
            "passes_test": passes,
            "expected_max_sharpe": round(float(expected_max_sr), 4),
        }
