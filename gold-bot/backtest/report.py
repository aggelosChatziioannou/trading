"""Generate complete backtest report: summary, charts, CSV trade log."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import numpy as np

from backtest.engine import BacktestResult
from backtest.metrics import compute_metrics
from backtest.monte_carlo import run_monte_carlo, MonteCarloResult
from backtest.walk_forward import run_walk_forward, WalkForwardResult
from backtest.charts import generate_all_charts
from data.manager import DataManager


def generate_report(
    result: BacktestResult,
    data: DataManager | None = None,
    capital: float = 500.0,
    output_dir: str = "results",
) -> dict:
    """Generate full backtest report."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    metrics = compute_metrics(result)

    if "error" in metrics and metrics.get("total_trades", 0) == 0:
        print(f"No trades to report: {metrics['error']}")
        return metrics

    # Monte Carlo simulation
    mc_result = None
    if result.trades:
        pnls = [t.pnl for t in result.trades]
        mc_result = run_monte_carlo(pnls, result.starting_capital)
        metrics["monte_carlo"] = {
            "probability_of_ruin": mc_result.probability_of_ruin,
            "max_dd_5th": mc_result.max_dd_5th,
            "max_dd_50th": mc_result.max_dd_50th,
            "max_dd_95th": mc_result.max_dd_95th,
            "final_equity_5th": mc_result.final_equity_5th,
            "final_equity_50th": mc_result.final_equity_50th,
            "final_equity_95th": mc_result.final_equity_95th,
        }

    # Walk-Forward Analysis
    wf_result = None
    if data is not None:
        try:
            wf_result = run_walk_forward(data, capital=capital)
            metrics["walk_forward"] = {
                "is_sharpe": wf_result.is_sharpe,
                "oos_sharpe": wf_result.oos_sharpe,
                "sharpe_ratio_pct": wf_result.sharpe_ratio_pct,
                "overfit_flag": wf_result.overfit_flag,
                "is_trades": wf_result.in_sample_trades,
                "oos_trades": wf_result.out_of_sample_trades,
            }
        except Exception as e:
            print(f"  Walk-forward analysis failed: {e}")

    _print_summary(metrics, mc_result, wf_result)
    generate_all_charts(result, metrics, mc_result, out)
    _export_trade_log_csv(result, metrics, out / "trade_log.csv")

    print(f"\nBACKTEST COMPLETE")
    print(f"Report saved to {out.resolve()}")
    return metrics


def _print_summary(m: dict, mc: MonteCarloResult | None = None, wf: WalkForwardResult | None = None):
    print("\n" + "=" * 70)
    print("         GOLD ICT BOT - TJR STRATEGY BACKTEST RESULTS")
    print("=" * 70)

    if m.get("sample_warning"):
        print(f"  *** {m['sample_warning']} ***")
    print(f"  Data: {m.get('data_start', 'N/A')} to {m.get('data_end', 'N/A')}")
    print(f"  Base TF: {m.get('base_tf', 'N/A')}")
    print()

    print(f"  Starting Capital:    ${m['starting_capital']:,.2f}")
    print(f"  Ending Capital:      ${m['ending_capital']:,.2f}")
    print(f"  Total Return:        {m['return_pct']}%")
    print(f"  Total P&L:           ${m['total_pnl']:,.2f}")
    print("-" * 70)

    print(f"  1.  Total Trades:           {m['total_trades']}")
    print(f"  2.  Win Rate:               {m['win_rate']}% (95% CI: {m['win_rate_ci_low']}-{m['win_rate_ci_high']}%)")
    print(f"  3.  Profit Factor:          {m['profit_factor']}")
    print(f"  4.  Sharpe Ratio:           {m['sharpe_ratio']}")
    print(f"  5.  Sortino Ratio:          {m['sortino_ratio']}")
    print(f"  6.  Max Drawdown:           {m['max_drawdown_pct']}% (${m['max_drawdown_dollars']:,.2f})")
    print(f"  7.  Max DD Duration:        {m['max_drawdown_duration_days']} days")
    print(f"  8.  Avg R:R Achieved:       {m['avg_rr']}")
    print(f"  9.  Avg Win / Avg Loss:     ${m['avg_win']:,.2f} / ${m['avg_loss']:,.2f}")
    print(f"  10. Expectancy (per R):     {m['expectancy_r']}")
    print(f"  11. CAGR:                   {m['cagr']}%")
    print(f"  12. Calmar Ratio:           {m['calmar_ratio']}")
    print(f"  13. Recovery Factor:        {m['recovery_factor']}")
    print(f"  14. Max Consec W/L:         {m['max_consecutive_wins']} / {m['max_consecutive_losses']}")
    print(f"  15. Gross Profit/Loss:      ${m['gross_profit']:,.2f} / ${m['gross_loss']:,.2f}")
    print("-" * 70)

    print("  TP HIT RATES:")
    print(f"    TP1 (1.5R):   {m['tp1_hit_rate']}%")
    print(f"    TP2 (2R):     {m['tp2_hit_rate']}%")
    print(f"    TP3 (Key Lvl):{m['tp3_hit_rate']}%")
    print("-" * 70)

    print("  SESSION BREAKDOWN:")
    print(f"    London: {m['london_trades']} trades, ${m['london_pnl']:,.2f} P&L, {m['london_win_rate']}% WR")
    print(f"    NY:     {m['ny_trades']} trades, ${m['ny_pnl']:,.2f} P&L, {m['ny_win_rate']}% WR")
    print("-" * 70)

    print("  ENTRY TYPES:")
    for et, stats in m.get("entry_types", {}).items():
        wr = round(stats["wins"] / stats["count"] * 100, 1) if stats["count"] > 0 else 0
        print(f"    {et}: {stats['count']} trades, ${stats['pnl']:,.2f}, {wr}% WR")
    print("-" * 70)

    print("  CONFLUENCE SCORE vs WIN RATE:")
    for score, data in sorted(m.get("confluence_vs_winrate", {}).items()):
        print(f"    Score {score}: {data['win_rate']}% WR ({data['total']} trades)")
    print("-" * 70)

    print("  DAY OF WEEK:")
    for day, data in m.get("day_of_week", {}).items():
        wr = round(data["wins"] / data["count"] * 100, 1) if data["count"] > 0 else 0
        print(f"    {day}: {data['count']} trades, ${data['pnl']:,.2f}, {wr}% WR")
    print("-" * 70)

    print(f"  No-Trade Days:     {m.get('no_trade_days', 0)}")
    print(f"  Trades/Week:       {m['trades_per_week']}")
    print(f"  Best Trade:        ${m['best_trade']:,.2f}")
    print(f"  Worst Trade:       ${m['worst_trade']:,.2f}")
    print("-" * 70)

    print("  MONTHLY P&L:")
    for month, pnl in sorted(m.get("monthly_pnl", {}).items()):
        bar_len = int(abs(pnl) / max(abs(v) for v in m["monthly_pnl"].values()) * 20) if m["monthly_pnl"] else 0
        bar = ("+" * bar_len) if pnl > 0 else ("-" * bar_len)
        print(f"    {month}: ${pnl:>10,.2f}  {bar}")

    if mc is not None and mc.n_iterations > 0:
        print("-" * 70)
        print(f"  MONTE CARLO ({mc.n_iterations} iterations):")
        print(f"    P(Ruin - 50% DD):  {mc.probability_of_ruin}%")
        print(f"    Max DD 5th/50th/95th:  {mc.max_dd_5th}% / {mc.max_dd_50th}% / {mc.max_dd_95th}%")
        print(f"    Final Eq 5th/50th/95th:  ${mc.final_equity_5th:,.0f} / ${mc.final_equity_50th:,.0f} / ${mc.final_equity_95th:,.0f}")

    if wf is not None:
        print("-" * 70)
        print("  WALK-FORWARD ANALYSIS:")
        print(f"    In-Sample Sharpe:   {wf.is_sharpe}")
        print(f"    Out-of-Sample Sharpe: {wf.oos_sharpe}")
        print(f"    OOS/IS Ratio:       {wf.sharpe_ratio_pct}%")
        print(f"    IS trades: {wf.in_sample_trades}, OOS trades: {wf.out_of_sample_trades}")
        if wf.overfit_flag:
            print("    *** OVERFIT WARNING: OOS Sharpe < 50% of IS Sharpe ***")

    print("=" * 70)


def _export_trade_log_csv(result: BacktestResult, metrics: dict, filepath: Path):
    """Export trade log as CSV with all required fields."""
    rows = []
    running_equity = result.starting_capital

    for t in sorted(result.trades, key=lambda x: x.signal_timestamp):
        running_equity += t.pnl
        risk = abs(t.entry_price - t.original_sl) * t.total_oz
        rr_achieved = t.pnl / risk if risk > 0 else 0

        rows.append({
            "Entry Time": t.signal_timestamp,
            "Exit Time": t.exit_time,
            "Direction": t.direction,
            "Entry Price": round(t.entry_price, 2),
            "SL Price": round(t.original_sl, 2),
            "TP1 Price": round(t.tp1, 2),
            "TP2 Price": round(t.tp2, 2),
            "TP3 Price": round(t.tp3, 2),
            "Exit Price": round(t.exit_price, 2),
            "R:R Planned": t.planned_rr,
            "R:R Achieved": round(rr_achieved, 2),
            "Confluences": "; ".join(t.confluences),
            "Session": t.session,
            "Confluence Score": t.confluence_score,
            "P&L ($)": round(t.pnl, 2),
            "P&L (%)": round(t.pnl / result.starting_capital * 100, 3),
            "Running Equity": round(running_equity, 2),
            "HTF Bias": t.htf_bias,
            "Entry Type": t.entry_type,
            "Size (oz)": round(t.total_oz, 2),
            "TP1 Hit": t.tp1_hit,
            "TP2 Hit": t.tp2_hit,
            "TP3 Hit": t.tp3_hit,
            "SL Hit": t.sl_hit,
        })

    df = pd.DataFrame(rows)
    # Remove timezone for CSV compatibility
    for col in ["Entry Time", "Exit Time"]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: x.tz_localize(None) if hasattr(x, "tz_localize") and x is not pd.NaT and getattr(x, "tzinfo", None) is not None else x
            )
    df.to_csv(filepath, index=False)
    print(f"  Trade log saved: {filepath}")
