"""
Probability of Backtest Overfitting (PBO).

Based on Bailey & Lopez de Prado (2014).

PBO answers: "What is the probability that the strategy we selected
as 'best' during in-sample optimization is actually below-median
out-of-sample?"

PBO < 5%  = Strategy is likely robust
PBO 5-15% = Caution, possible mild overfit
PBO > 15% = Strategy is likely overfit — do NOT trade
"""

from __future__ import annotations

import logging
from itertools import combinations

import numpy as np

from config.settings import settings

logger = logging.getLogger(__name__)


class PBO:
    """
    Calculate the Probability of Backtest Overfitting.

    Uses the CPCV framework to assess whether in-sample performance
    predicts out-of-sample performance.
    """

    def calculate(self, cpcv_results: list[dict]) -> dict:
        """
        Calculate PBO from CPCV fold results.

        Uses the rank-based approach:
        1. For each CPCV split, get the in-sample rank and out-of-sample performance.
        2. PBO = fraction of times the in-sample "winner" underperforms
           out-of-sample vs the median.

        Args:
            cpcv_results: List of dicts from CPCV.run_validation().
                         Each must have 'sharpe' and 'fold' keys.

        Returns:
            Dict with:
                pbo: float [0, 1] — probability of overfitting
                logit_pbo: float — log-odds of overfitting
                is_overfit: bool — True if PBO > threshold
                n_folds: int
        """
        if len(cpcv_results) < 4:
            logger.warning("Too few CPCV results (%d) for reliable PBO", len(cpcv_results))
            return {
                "pbo": 1.0,
                "logit_pbo": float("inf"),
                "is_overfit": True,
                "n_folds": len(cpcv_results),
            }

        sharpes = np.array([r["sharpe"] for r in cpcv_results])
        n = len(sharpes)

        # Split results into paired in-sample and out-of-sample groups
        # We use a combinatorial approach: for each way to split the folds
        # into two halves, check if the better half in-sample is also better OOS.
        mid = n // 2
        n_underperform = 0
        n_total = 0

        # Generate all ways to split folds into two groups
        indices = list(range(n))
        for group_a in combinations(indices, mid):
            group_b = tuple(i for i in indices if i not in group_a)

            # "In-sample" performance: mean Sharpe of group A
            is_sharpe_a = np.mean(sharpes[list(group_a)])
            is_sharpe_b = np.mean(sharpes[list(group_b)])

            # The "selected" strategy is the one with better in-sample performance
            # The "out-of-sample" is the other group
            if is_sharpe_a >= is_sharpe_b:
                # We "selected" group A based on in-sample
                # OOS check: is group A's sharpe below median?
                oos_sharpe = is_sharpe_b  # group B serves as OOS proxy
                selected_sharpe = is_sharpe_a
            else:
                oos_sharpe = is_sharpe_a
                selected_sharpe = is_sharpe_b

            # PBO: does the selected strategy underperform OOS?
            median_sharpe = np.median(sharpes)
            if oos_sharpe < median_sharpe:
                n_underperform += 1
            n_total += 1

            # Limit combinations for large fold counts
            if n_total >= 1000:
                break

        pbo = n_underperform / n_total if n_total > 0 else 1.0

        # Logit transformation for more interpretable metric
        if 0 < pbo < 1:
            logit_pbo = float(np.log(pbo / (1 - pbo)))
        elif pbo == 0:
            logit_pbo = float("-inf")
        else:
            logit_pbo = float("inf")

        is_overfit = pbo > settings.validation.pbo_max_acceptable

        logger.info("PBO = %.2f%% (%s)", pbo * 100, "OVERFIT" if is_overfit else "OK")

        return {
            "pbo": round(float(pbo), 4),
            "logit_pbo": round(logit_pbo, 4) if np.isfinite(logit_pbo) else logit_pbo,
            "is_overfit": is_overfit,
            "n_folds": n,
        }
