"""Generate backtest reports: equity curve, trade log, metrics summary."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

from backtest.engine import BacktestResult
from backtest.metrics import compute_metrics


def generate_report(result: BacktestResult, output_dir: str = "results") -> dict:
    """Generate full backtest report: charts, Excel trade log, metrics summary."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    metrics = compute_metrics(result)

    if "error" in metrics:
        print(f"No trades to report: {metrics['error']}")
        return metrics

    _print_summary(metrics)
    _plot_equity_curve(result, out / "equity_curve.png")
    _plot_monthly_pnl(metrics["monthly_pnl"], out / "monthly_pnl.png")
    _export_trade_log(result.trades, out / "trade_log.xlsx")

    print(f"\nReport saved to {out.resolve()}")
    return metrics


def _print_summary(m: dict):
    print("\n" + "=" * 60)
    print("        GOLD ICT BOT - BACKTEST RESULTS")
    print("=" * 60)
    print(f"  Starting Capital:   ${m['starting_capital']:,.2f}")
    print(f"  Ending Capital:     ${m['ending_capital']:,.2f}")
    print(f"  Total Return:       {m['return_pct']}%")
    print(f"  Total P&L:          ${m['total_pnl']:,.2f}")
    print("-" * 60)
    print(f"  Total Trades:       {m['total_trades']}")
    print(f"  Win Rate:           {m['win_rate']}%")
    print(f"  Profit Factor:      {m['profit_factor']}")
    print(f"  Sharpe Ratio:       {m['sharpe_ratio']}")
    print(f"  Max Drawdown:       {m['max_drawdown_pct']}%")
    print(f"  Avg R:R:            {m['avg_rr']}")
    print(f"  Trades/Week:        {m['trades_per_week']}")
    print("-" * 60)
    print(f"  Avg Win:            ${m['avg_win']:,.2f}")
    print(f"  Avg Loss:           ${m['avg_loss']:,.2f}")
    print(f"  Best Trade:         ${m['best_trade']:,.2f}")
    print(f"  Worst Trade:        ${m['worst_trade']:,.2f}")
    print("-" * 60)
    print("  SESSION BREAKDOWN:")
    print(f"    London:  {m['london_trades']} trades, ${m['london_pnl']:,.2f} P&L, {m['london_win_rate']}% WR")
    print(f"    NY:      {m['ny_trades']} trades, ${m['ny_pnl']:,.2f} P&L, {m['ny_win_rate']}% WR")
    print("-" * 60)
    print("  TP HIT RATES:")
    print(f"    TP1 (1:1 R:R):   {m['tp1_hit_rate']}%")
    print(f"    TP2 (2:1 R:R):   {m['tp2_hit_rate']}%")
    print(f"    TP3 (Key Level): {m['tp3_hit_rate']}%")
    print("-" * 60)
    print("  ENTRY TYPE BREAKDOWN:")
    for et, stats in m.get("entry_types", {}).items():
        wr = round(stats["wins"] / stats["count"] * 100, 1) if stats["count"] > 0 else 0
        print(f"    {et}: {stats['count']} trades, ${stats['pnl']:,.2f} P&L, {wr}% WR")
    print("-" * 60)
    print("  MONTHLY P&L:")
    for month, pnl in sorted(m.get("monthly_pnl", {}).items()):
        bar = "+" * int(abs(pnl) / 5) if pnl > 0 else "-" * int(abs(pnl) / 5)
        print(f"    {month}: ${pnl:>8,.2f}  {bar}")
    print("=" * 60)


def _plot_equity_curve(result: BacktestResult, filepath: Path):
    eq = pd.DataFrame(result.equity_curve)
    eq["timestamp"] = pd.to_datetime(eq["timestamp"])

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={"height_ratios": [3, 1]})

    ax1.plot(eq["timestamp"], eq["equity"], color="#2196F3", linewidth=1.5)
    ax1.axhline(y=result.starting_capital, color="gray", linestyle="--", alpha=0.5)
    ax1.fill_between(eq["timestamp"], result.starting_capital, eq["equity"],
                     where=eq["equity"] >= result.starting_capital, alpha=0.2, color="green")
    ax1.fill_between(eq["timestamp"], result.starting_capital, eq["equity"],
                     where=eq["equity"] < result.starting_capital, alpha=0.2, color="red")
    ax1.set_title("Gold ICT Bot - Equity Curve", fontsize=14, fontweight="bold")
    ax1.set_ylabel("Equity ($)")
    ax1.grid(True, alpha=0.3)

    # Drawdown subplot
    peak = eq["equity"].expanding().max()
    dd = (eq["equity"] - peak) / peak * 100
    ax2.fill_between(eq["timestamp"], dd, 0, color="red", alpha=0.3)
    ax2.set_ylabel("Drawdown (%)")
    ax2.set_xlabel("Date")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Equity curve saved: {filepath}")


def _plot_monthly_pnl(monthly_pnl: dict, filepath: Path):
    if not monthly_pnl:
        return

    months = sorted(monthly_pnl.keys())
    pnls = [monthly_pnl[m] for m in months]
    colors = ["green" if p > 0 else "red" for p in pnls]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(months, pnls, color=colors, alpha=0.7, edgecolor="black", linewidth=0.5)
    ax.axhline(y=0, color="black", linewidth=0.5)
    ax.set_title("Monthly P&L", fontsize=14, fontweight="bold")
    ax.set_ylabel("P&L ($)")
    ax.grid(True, alpha=0.3, axis="y")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Monthly P&L chart saved: {filepath}")


def _export_trade_log(trades: list, filepath: Path):
    rows = []
    for t in trades:
        risk = abs(t.entry_price - t.stop_loss)
        rr = t.pnl / (risk * t.total_oz) if risk > 0 and t.total_oz > 0 else 0
        rows.append({
            "Entry Time": t.signal_timestamp,
            "Exit Time": t.exit_time,
            "Direction": t.direction,
            "Session": t.session,
            "Entry Type": t.entry_type,
            "Entry Price": round(t.entry_price, 2),
            "Stop Loss": round(t.stop_loss, 2),
            "TP1": round(t.tp1, 2),
            "TP2": round(t.tp2, 2),
            "TP3": round(t.tp3, 2),
            "Exit Price": round(t.exit_price, 2),
            "Size (oz)": round(t.total_oz, 2),
            "P&L ($)": round(t.pnl, 2),
            "R:R Achieved": round(rr, 2),
            "TP1 Hit": t.tp1_hit,
            "TP2 Hit": t.tp2_hit,
            "TP3 Hit": t.tp3_hit,
            "SL Hit": t.sl_hit,
        })

    df = pd.DataFrame(rows)
    # Excel doesn't support timezone-aware datetimes
    for col in ["Entry Time", "Exit Time"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: x.tz_localize(None) if hasattr(x, 'tz_localize') and x is not pd.NaT and x.tzinfo is not None else x)
    df.to_excel(filepath, index=False, sheet_name="Trade Log")
    print(f"  Trade log saved: {filepath}")
