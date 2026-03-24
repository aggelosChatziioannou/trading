"""Backtest performance metrics."""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtest.engine import BacktestResult
from risk.manager import Position


def compute_metrics(result: BacktestResult) -> dict:
    """Compute all performance metrics from backtest results."""
    trades = result.trades
    if not trades:
        return {"error": "No trades generated"}

    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    total_trades = len(trades)
    win_rate = len(wins) / total_trades if total_trades > 0 else 0

    # Profit Factor
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # R:R achieved
    rr_ratios = []
    for t in trades:
        risk = abs(t.entry_price - t.stop_loss) * t.total_oz
        if risk > 0 and t.pnl != 0:
            rr_ratios.append(t.pnl / risk)
    avg_rr = float(np.mean(rr_ratios)) if rr_ratios else 0

    # Equity curve for Sharpe & Drawdown
    eq = pd.DataFrame(result.equity_curve)
    if len(eq) > 1:
        eq["returns"] = eq["equity"].pct_change().dropna()
        std = eq["returns"].std()
        sharpe = float(eq["returns"].mean() / std * np.sqrt(252 * 78)) if std > 0 else 0

        peak = eq["equity"].expanding().max()
        drawdown = (eq["equity"] - peak) / peak
        max_drawdown = float(drawdown.min())
    else:
        sharpe = 0
        max_drawdown = 0

    # Session breakdown
    london_trades = [t for t in trades if t.session == "London"]
    ny_trades = [t for t in trades if t.session == "NY"]

    london_pnl = sum(t.pnl for t in london_trades)
    ny_pnl = sum(t.pnl for t in ny_trades)
    london_wr = len([t for t in london_trades if t.pnl > 0]) / len(london_trades) if london_trades else 0
    ny_wr = len([t for t in ny_trades if t.pnl > 0]) / len(ny_trades) if ny_trades else 0

    # TP hit rates
    tp1_hits = sum(1 for t in trades if t.tp1_hit)
    tp2_hits = sum(1 for t in trades if t.tp2_hit)
    tp3_hits = sum(1 for t in trades if t.tp3_hit)

    # Monthly P&L
    monthly_pnl = {}
    for t in trades:
        month_key = t.signal_timestamp.strftime("%Y-%m")
        monthly_pnl[month_key] = monthly_pnl.get(month_key, 0) + t.pnl

    # Trades per week
    if trades:
        first = min(t.signal_timestamp for t in trades)
        last = max(t.signal_timestamp for t in trades)
        weeks = max((last - first).days / 7, 1)
        trades_per_week = total_trades / weeks
    else:
        trades_per_week = 0

    # Entry type breakdown
    entry_types = {}
    for t in trades:
        et = t.entry_type
        if et not in entry_types:
            entry_types[et] = {"count": 0, "pnl": 0, "wins": 0}
        entry_types[et]["count"] += 1
        entry_types[et]["pnl"] += t.pnl
        if t.pnl > 0:
            entry_types[et]["wins"] += 1

    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate * 100, 1),
        "profit_factor": round(profit_factor, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_drawdown * 100, 1),
        "avg_rr": round(avg_rr, 2),
        "total_pnl": round(sum(pnls), 2),
        "starting_capital": result.starting_capital,
        "ending_capital": round(result.ending_capital, 2),
        "return_pct": round((result.ending_capital / result.starting_capital - 1) * 100, 1),
        "london_pnl": round(london_pnl, 2),
        "london_trades": len(london_trades),
        "london_win_rate": round(london_wr * 100, 1),
        "ny_pnl": round(ny_pnl, 2),
        "ny_trades": len(ny_trades),
        "ny_win_rate": round(ny_wr * 100, 1),
        "tp1_hit_rate": round(tp1_hits / total_trades * 100, 1) if total_trades else 0,
        "tp2_hit_rate": round(tp2_hits / total_trades * 100, 1) if total_trades else 0,
        "tp3_hit_rate": round(tp3_hits / total_trades * 100, 1) if total_trades else 0,
        "trades_per_week": round(trades_per_week, 1),
        "monthly_pnl": monthly_pnl,
        "entry_types": entry_types,
        "avg_win": round(float(np.mean(wins)), 2) if wins else 0,
        "avg_loss": round(float(np.mean(losses)), 2) if losses else 0,
        "best_trade": round(max(pnls), 2) if pnls else 0,
        "worst_trade": round(min(pnls), 2) if pnls else 0,
    }
