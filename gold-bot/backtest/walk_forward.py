"""Walk-Forward Analysis for overfit detection.

Split data into in-sample (train) and out-of-sample (test) periods.
Compare Sharpe ratios: if OOS Sharpe < 50% of IS Sharpe, flag as overfit.
"""
from __future__ import annotations

from dataclasses import dataclass

from data.manager import DataManager
from backtest.engine import run_backtest, BacktestResult
from backtest.metrics import compute_metrics


@dataclass
class WalkForwardResult:
    in_sample_metrics: dict
    out_of_sample_metrics: dict
    is_sharpe: float
    oos_sharpe: float
    sharpe_ratio_pct: float  # OOS Sharpe as % of IS Sharpe
    overfit_flag: bool
    in_sample_trades: int
    out_of_sample_trades: int


def run_walk_forward(
    data: DataManager,
    capital: float,
    train_ratio: float = 0.67,  # Train on first 67%, test on last 33%
) -> WalkForwardResult:
    """Run Walk-Forward Analysis.

    Splits the primary timeframe data at the train_ratio point.
    Runs backtest on both halves independently.
    """
    primary = data.primary_tf
    split_idx = int(len(primary) * train_ratio)

    if split_idx < 100 or len(primary) - split_idx < 50:
        return WalkForwardResult(
            in_sample_metrics={"error": "Insufficient data for walk-forward"},
            out_of_sample_metrics={"error": "Insufficient data"},
            is_sharpe=0, oos_sharpe=0, sharpe_ratio_pct=0,
            overfit_flag=False, in_sample_trades=0, out_of_sample_trades=0,
        )

    split_time = primary.index[split_idx]

    # Build in-sample data
    is_gold = {}
    oos_gold = {}

    for tf in ["1m", "5m", "15m", "1h", "4h", "1d"]:
        attr = f"gold_{tf}"
        df = getattr(data, attr, None)
        if df is not None and not df.empty:
            is_gold[tf] = df[df.index <= split_time]
            oos_gold[tf] = df[df.index > split_time]

    # Build DXY splits
    is_dxy = {}
    oos_dxy = {}
    for tf in ["1m", "5m", "1h"]:
        attr = f"dxy_{tf}"
        df = getattr(data, attr, None)
        if df is not None and not df.empty:
            is_dxy[tf] = df[df.index <= split_time]
            oos_dxy[tf] = df[df.index > split_time]

    # Run in-sample backtest
    try:
        is_data = DataManager(gold_data=is_gold, dxy_data=is_dxy)
        is_result = run_backtest(is_data, capital=capital)
        is_metrics = compute_metrics(is_result)
    except Exception:
        is_metrics = {"error": "In-sample backtest failed", "total_trades": 0}
        is_result = None

    # Run out-of-sample backtest
    try:
        oos_data = DataManager(gold_data=oos_gold, dxy_data=oos_dxy)
        oos_result = run_backtest(oos_data, capital=capital)
        oos_metrics = compute_metrics(oos_result)
    except Exception:
        oos_metrics = {"error": "Out-of-sample backtest failed", "total_trades": 0}
        oos_result = None

    is_sharpe = is_metrics.get("sharpe_ratio", 0)
    oos_sharpe = oos_metrics.get("sharpe_ratio", 0)
    ratio = (oos_sharpe / is_sharpe * 100) if is_sharpe != 0 else 0
    overfit = ratio < 50 if is_sharpe > 0 else False

    return WalkForwardResult(
        in_sample_metrics=is_metrics,
        out_of_sample_metrics=oos_metrics,
        is_sharpe=is_sharpe,
        oos_sharpe=oos_sharpe,
        sharpe_ratio_pct=round(ratio, 1),
        overfit_flag=overfit,
        in_sample_trades=is_metrics.get("total_trades", 0),
        out_of_sample_trades=oos_metrics.get("total_trades", 0),
    )
