"""Monte Carlo simulation for trade sequence analysis.

Runs 1000 iterations of shuffled trade sequences to estimate:
- Probability of ruin (hitting 50% drawdown)
- Expected max drawdown distribution
- 5th/50th/95th percentile equity curves
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation."""
    n_iterations: int
    probability_of_ruin: float      # % chance of hitting 50% drawdown
    max_dd_5th: float               # 5th percentile max drawdown
    max_dd_50th: float              # Median max drawdown
    max_dd_95th: float              # 95th percentile max drawdown
    final_equity_5th: float
    final_equity_50th: float
    final_equity_95th: float
    equity_curves_5th: list[float] = field(default_factory=list)
    equity_curves_50th: list[float] = field(default_factory=list)
    equity_curves_95th: list[float] = field(default_factory=list)
    all_max_drawdowns: list[float] = field(default_factory=list)


def run_monte_carlo(
    trade_pnls: list[float],
    starting_capital: float,
    n_iterations: int = 1000,
    ruin_threshold: float = 0.50,
) -> MonteCarloResult:
    """Run Monte Carlo simulation by shuffling the trade sequence.

    Args:
        trade_pnls: List of P&L values from actual trades
        starting_capital: Starting capital
        n_iterations: Number of simulation runs (default 1000)
        ruin_threshold: Drawdown % that constitutes "ruin" (default 50%)
    """
    if not trade_pnls:
        return MonteCarloResult(
            n_iterations=0, probability_of_ruin=0,
            max_dd_5th=0, max_dd_50th=0, max_dd_95th=0,
            final_equity_5th=starting_capital,
            final_equity_50th=starting_capital,
            final_equity_95th=starting_capital,
        )

    pnls = np.array(trade_pnls)
    n_trades = len(pnls)
    ruin_count = 0
    max_drawdowns = []
    final_equities = []
    all_curves = np.zeros((n_iterations, n_trades + 1))

    for sim in range(n_iterations):
        # Shuffle trade order
        shuffled = np.random.permutation(pnls)

        # Build equity curve
        equity = np.zeros(n_trades + 1)
        equity[0] = starting_capital
        for i, p in enumerate(shuffled):
            equity[i + 1] = equity[i] + p

        all_curves[sim] = equity

        # Calculate max drawdown
        peak = np.maximum.accumulate(equity)
        dd = (equity - peak) / np.where(peak > 0, peak, 1)
        max_dd = float(np.min(dd))
        max_drawdowns.append(abs(max_dd))

        # Check ruin
        if abs(max_dd) >= ruin_threshold:
            ruin_count += 1

        final_equities.append(equity[-1])

    max_drawdowns = np.array(max_drawdowns)
    final_equities = np.array(final_equities)

    # Percentile equity curves
    curves_5th = np.percentile(all_curves, 5, axis=0).tolist()
    curves_50th = np.percentile(all_curves, 50, axis=0).tolist()
    curves_95th = np.percentile(all_curves, 95, axis=0).tolist()

    return MonteCarloResult(
        n_iterations=n_iterations,
        probability_of_ruin=round(ruin_count / n_iterations * 100, 1),
        max_dd_5th=round(float(np.percentile(max_drawdowns, 5)) * 100, 1),
        max_dd_50th=round(float(np.percentile(max_drawdowns, 50)) * 100, 1),
        max_dd_95th=round(float(np.percentile(max_drawdowns, 95)) * 100, 1),
        final_equity_5th=round(float(np.percentile(final_equities, 5)), 2),
        final_equity_50th=round(float(np.percentile(final_equities, 50)), 2),
        final_equity_95th=round(float(np.percentile(final_equities, 95)), 2),
        equity_curves_5th=curves_5th,
        equity_curves_50th=curves_50th,
        equity_curves_95th=curves_95th,
        all_max_drawdowns=max_drawdowns.tolist(),
    )
