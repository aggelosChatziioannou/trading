"""Comprehensive backtest performance metrics - all 22 required metrics."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from backtest.engine import BacktestResult
from risk.manager import Position


def compute_metrics(result: BacktestResult) -> dict:
    """Compute all 22 performance metrics from backtest results."""
    trades = result.trades
    if not trades:
        return {"error": "No trades generated", "total_trades": 0}

    pnls = np.array([t.pnl for t in trades])
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    total = len(trades)

    # 1. Total trades
    # 2. Win rate with 95% CI
    win_rate = len(wins) / total
    # Wilson score interval for binomial proportion
    z = 1.96
    n = total
    p_hat = win_rate
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    margin = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n) / denom
    wr_ci_low = max(0, center - margin)
    wr_ci_high = min(1, center + margin)

    # 3. Profit Factor
    gross_profit = float(np.sum(wins)) if len(wins) > 0 else 0
    gross_loss = float(np.abs(np.sum(losses))) if len(losses) > 0 else 0.001
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Equity curve metrics
    eq = pd.DataFrame(result.equity_curve)
    sharpe = sortino = max_dd_pct = max_dd_dollars = max_dd_duration = cagr = 0
    calmar = recovery_factor = 0

    if len(eq) > 1:
        eq["returns"] = eq["equity"].pct_change().dropna()
        returns = eq["returns"].dropna()

        # 4. Sharpe Ratio (annualized, ~252 trading days, ~78 5-min bars/day)
        bars_per_year = 252 * 78
        std = returns.std()
        sharpe = float(returns.mean() / std * np.sqrt(bars_per_year)) if std > 0 else 0

        # 5. Sortino Ratio
        downside = returns[returns < 0]
        downside_std = downside.std() if len(downside) > 0 else 0.001
        sortino = float(returns.mean() / downside_std * np.sqrt(bars_per_year)) if downside_std > 0 else 0

        # 6+7. Max Drawdown (% and $) + Duration
        peak = eq["equity"].expanding().max()
        dd = (eq["equity"] - peak) / peak
        max_dd_pct = float(dd.min())
        max_dd_dollars = float((eq["equity"] - peak).min())

        # Drawdown duration
        in_dd = dd < 0
        dd_groups = (in_dd != in_dd.shift()).cumsum()
        if in_dd.any():
            dd_lengths = in_dd.groupby(dd_groups).sum()
            max_dd_bars = int(dd_lengths.max())
            # Approximate days (78 5-min bars per trading day)
            max_dd_duration = round(max_dd_bars / 78, 1)

        # 11. CAGR
        total_days = (eq["timestamp"].iloc[-1] - eq["timestamp"].iloc[0]).total_seconds() / 86400
        total_years = max(total_days / 365.25, 0.01)
        total_return = result.ending_capital / result.starting_capital
        cagr = (total_return ** (1 / total_years) - 1) if total_return > 0 else 0

        # 12. Calmar Ratio
        calmar = cagr / abs(max_dd_pct) if max_dd_pct != 0 else 0

        # 13. Recovery Factor
        net_profit = result.ending_capital - result.starting_capital
        recovery_factor = net_profit / abs(max_dd_dollars) if max_dd_dollars != 0 else 0

    # 8. Average R:R achieved
    rr_ratios = []
    for t in trades:
        risk = abs(t.entry_price - t.original_sl) * t.total_oz
        if risk > 0:
            rr_ratios.append(t.pnl / risk)
    avg_rr = float(np.mean(rr_ratios)) if rr_ratios else 0

    # 9. Avg winner vs avg loser
    avg_win = float(np.mean(wins)) if len(wins) > 0 else 0
    avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0

    # 10. Expectancy per trade (in R)
    expectancy_r = float(np.mean(rr_ratios)) if rr_ratios else 0

    # 14. Consecutive wins/losses
    max_consec_wins = max_consec_losses = current_streak = 0
    streak_type = None
    for p in pnls:
        if p > 0:
            if streak_type == "win":
                current_streak += 1
            else:
                current_streak = 1
                streak_type = "win"
            max_consec_wins = max(max_consec_wins, current_streak)
        else:
            if streak_type == "loss":
                current_streak += 1
            else:
                current_streak = 1
                streak_type = "loss"
            max_consec_losses = max(max_consec_losses, current_streak)

    # 15. TP hit rates
    tp1_hits = sum(1 for t in trades if t.tp1_hit)
    tp2_hits = sum(1 for t in trades if t.tp2_hit)
    tp3_hits = sum(1 for t in trades if t.tp3_hit)

    # 16. Session breakdown
    london = [t for t in trades if t.session == "London"]
    ny = [t for t in trades if t.session == "NY"]
    london_pnl = sum(t.pnl for t in london)
    ny_pnl = sum(t.pnl for t in ny)
    london_wr = len([t for t in london if t.pnl > 0]) / len(london) if london else 0
    ny_wr = len([t for t in ny if t.pnl > 0]) / len(ny) if ny else 0

    # 17. Confluence score vs win rate
    score_wr = {}
    for t in trades:
        s = t.confluence_score
        if s not in score_wr:
            score_wr[s] = {"total": 0, "wins": 0}
        score_wr[s]["total"] += 1
        if t.pnl > 0:
            score_wr[s]["wins"] += 1
    for s in score_wr:
        score_wr[s]["win_rate"] = round(score_wr[s]["wins"] / score_wr[s]["total"] * 100, 1)

    # 18. Monthly P&L
    monthly_pnl = {}
    for t in trades:
        month_key = t.signal_timestamp.strftime("%Y-%m")
        monthly_pnl[month_key] = monthly_pnl.get(month_key, 0) + t.pnl

    # 19. Day of week performance
    dow_pnl = {}
    dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for t in trades:
        dow = t.signal_timestamp.weekday()
        name = dow_names[dow]
        if name not in dow_pnl:
            dow_pnl[name] = {"pnl": 0, "count": 0, "wins": 0}
        dow_pnl[name]["pnl"] += t.pnl
        dow_pnl[name]["count"] += 1
        if t.pnl > 0:
            dow_pnl[name]["wins"] += 1

    # 21. Trades per week
    if trades:
        first = min(t.signal_timestamp for t in trades)
        last = max(t.signal_timestamp for t in trades)
        weeks = max((last - first).days / 7, 1)
        trades_per_week = total / weeks
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

    # Sample size warning
    sample_warning = ""
    if total < 30:
        sample_warning = "WARNING: Insufficient sample size (<30 trades) for statistical significance"
    elif total < 50:
        sample_warning = "CAUTION: Sample size is marginal (30-50 trades)"

    return {
        "total_trades": total,
        "win_rate": round(win_rate * 100, 1),
        "win_rate_ci_low": round(wr_ci_low * 100, 1),
        "win_rate_ci_high": round(wr_ci_high * 100, 1),
        "profit_factor": round(profit_factor, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "max_drawdown_pct": round(max_dd_pct * 100, 1),
        "max_drawdown_dollars": round(max_dd_dollars, 2),
        "max_drawdown_duration_days": max_dd_duration,
        "avg_rr": round(avg_rr, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy_r": round(expectancy_r, 3),
        "cagr": round(cagr * 100, 1),
        "calmar_ratio": round(calmar, 2),
        "recovery_factor": round(recovery_factor, 2),
        "max_consecutive_wins": max_consec_wins,
        "max_consecutive_losses": max_consec_losses,
        "total_pnl": round(float(np.sum(pnls)), 2),
        "starting_capital": result.starting_capital,
        "ending_capital": round(result.ending_capital, 2),
        "return_pct": round((result.ending_capital / result.starting_capital - 1) * 100, 1),
        "tp1_hit_rate": round(tp1_hits / total * 100, 1) if total else 0,
        "tp2_hit_rate": round(tp2_hits / total * 100, 1) if total else 0,
        "tp3_hit_rate": round(tp3_hits / total * 100, 1) if total else 0,
        "london_trades": len(london),
        "london_pnl": round(london_pnl, 2),
        "london_win_rate": round(london_wr * 100, 1),
        "ny_trades": len(ny),
        "ny_pnl": round(ny_pnl, 2),
        "ny_win_rate": round(ny_wr * 100, 1),
        "confluence_vs_winrate": score_wr,
        "monthly_pnl": monthly_pnl,
        "day_of_week": dow_pnl,
        "no_trade_days": result.no_trade_days,
        "trades_per_week": round(trades_per_week, 1),
        "entry_types": entry_types,
        "best_trade": round(float(np.max(pnls)), 2),
        "worst_trade": round(float(np.min(pnls)), 2),
        "data_start": result.data_start,
        "data_end": result.data_end,
        "base_tf": result.base_tf,
        "sample_warning": sample_warning,
        "rr_ratios": [round(r, 2) for r in rr_ratios],
    }
