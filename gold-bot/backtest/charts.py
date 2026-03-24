"""Generate all 9 required charts for backtest report."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from backtest.engine import BacktestResult
from backtest.monte_carlo import MonteCarloResult


def generate_all_charts(
    result: BacktestResult,
    metrics: dict,
    mc_result: MonteCarloResult | None,
    output_dir: Path,
):
    """Generate all 9 charts and save to output directory."""
    plt.rcParams.update({
        "figure.facecolor": "#1a1a2e",
        "axes.facecolor": "#16213e",
        "axes.edgecolor": "#e0e0e0",
        "text.color": "#e0e0e0",
        "axes.labelcolor": "#e0e0e0",
        "xtick.color": "#e0e0e0",
        "ytick.color": "#e0e0e0",
        "grid.color": "#2a2a4a",
        "grid.alpha": 0.5,
        "font.size": 10,
    })

    _chart_equity_curve(result, output_dir / "1_equity_curve.png")
    _chart_monthly_heatmap(metrics, output_dir / "2_monthly_heatmap.png")
    _chart_drawdown(result, output_dir / "3_drawdown.png")
    _chart_hourly_distribution(result, output_dir / "4_hourly_distribution.png")
    _chart_rr_histogram(metrics, output_dir / "5_rr_histogram.png")
    _chart_confluence_winrate(metrics, output_dir / "6_confluence_winrate.png")
    _chart_rolling_winrate(result, output_dir / "7_rolling_winrate.png")
    if mc_result and mc_result.n_iterations > 0:
        _chart_monte_carlo(mc_result, output_dir / "8_monte_carlo.png")
    _chart_session_pnl(result, output_dir / "9_session_pnl.png")


def _chart_equity_curve(result: BacktestResult, filepath: Path):
    """Chart 1: Equity curve with drawdown overlay."""
    eq = pd.DataFrame(result.equity_curve)
    if eq.empty:
        return
    eq["timestamp"] = pd.to_datetime(eq["timestamp"])

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 9), gridspec_kw={"height_ratios": [3, 1]})

    ax1.plot(eq["timestamp"], eq["equity"], color="#00d4ff", linewidth=1.2, label="Equity")
    ax1.axhline(y=result.starting_capital, color="#ff6b6b", linestyle="--", alpha=0.5, label="Starting Capital")
    ax1.fill_between(eq["timestamp"], result.starting_capital, eq["equity"],
                     where=eq["equity"] >= result.starting_capital, alpha=0.15, color="#00ff88")
    ax1.fill_between(eq["timestamp"], result.starting_capital, eq["equity"],
                     where=eq["equity"] < result.starting_capital, alpha=0.15, color="#ff6b6b")

    # Mark trades
    for t in result.trades:
        color = "#00ff88" if t.pnl > 0 else "#ff6b6b"
        marker = "^" if t.direction == "long" else "v"
        ax1.scatter(t.signal_timestamp, t.entry_price if False else None, c=color, marker=marker, s=20, alpha=0.7, zorder=5)

    ax1.set_title("Gold ICT Bot - Equity Curve (TJR Strategy)", fontsize=14, fontweight="bold")
    ax1.set_ylabel("Equity ($)")
    ax1.legend(loc="upper left")
    ax1.grid(True)

    # Drawdown
    peak = eq["equity"].expanding().max()
    dd = (eq["equity"] - peak) / peak * 100
    ax2.fill_between(eq["timestamp"], dd, 0, color="#ff6b6b", alpha=0.4)
    ax2.set_ylabel("Drawdown (%)")
    ax2.set_xlabel("Date")
    ax2.grid(True)

    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()


def _chart_monthly_heatmap(metrics: dict, filepath: Path):
    """Chart 2: Monthly returns heatmap."""
    monthly = metrics.get("monthly_pnl", {})
    if not monthly:
        return

    # Build year-month matrix
    data = {}
    for ym, pnl in monthly.items():
        year, month = ym.split("-")
        if year not in data:
            data[year] = {}
        data[year][int(month)] = pnl

    years = sorted(data.keys())
    months = list(range(1, 13))
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    matrix = np.zeros((len(years), 12))
    for i, y in enumerate(years):
        for j, m in enumerate(months):
            matrix[i, j] = data.get(y, {}).get(m, 0)

    fig, ax = plt.subplots(figsize=(14, max(3, len(years) * 1.5)))
    vmax = max(abs(matrix.max()), abs(matrix.min()), 1)
    im = ax.imshow(matrix, cmap="RdYlGn", aspect="auto", vmin=-vmax, vmax=vmax)

    ax.set_xticks(range(12))
    ax.set_xticklabels(month_names)
    ax.set_yticks(range(len(years)))
    ax.set_yticklabels(years)

    for i in range(len(years)):
        for j in range(12):
            val = matrix[i, j]
            if val != 0:
                ax.text(j, i, f"${val:.0f}", ha="center", va="center",
                       color="black" if abs(val) < vmax * 0.5 else "white", fontsize=9)

    plt.colorbar(im, ax=ax, label="P&L ($)")
    ax.set_title("Monthly Returns Heatmap", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()


def _chart_drawdown(result: BacktestResult, filepath: Path):
    """Chart 3: Underwater drawdown plot."""
    eq = pd.DataFrame(result.equity_curve)
    if eq.empty:
        return
    eq["timestamp"] = pd.to_datetime(eq["timestamp"])

    peak = eq["equity"].expanding().max()
    dd = (eq["equity"] - peak) / peak * 100

    fig, ax = plt.subplots(figsize=(16, 5))
    ax.fill_between(eq["timestamp"], dd, 0, color="#ff6b6b", alpha=0.6)
    ax.plot(eq["timestamp"], dd, color="#ff3333", linewidth=0.8)
    ax.set_title("Underwater Drawdown Plot", fontsize=14, fontweight="bold")
    ax.set_ylabel("Drawdown (%)")
    ax.set_xlabel("Date")
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()


def _chart_hourly_distribution(result: BacktestResult, filepath: Path):
    """Chart 4: Trade distribution by hour of day."""
    if not result.trades:
        return

    hours = [t.signal_timestamp.hour for t in result.trades]
    pnls_by_hour = {}
    for t in result.trades:
        h = t.signal_timestamp.hour
        if h not in pnls_by_hour:
            pnls_by_hour[h] = {"count": 0, "pnl": 0}
        pnls_by_hour[h]["count"] += 1
        pnls_by_hour[h]["pnl"] += t.pnl

    all_hours = sorted(pnls_by_hour.keys())
    counts = [pnls_by_hour[h]["count"] for h in all_hours]
    pnls = [pnls_by_hour[h]["pnl"] for h in all_hours]
    colors = ["#00ff88" if p > 0 else "#ff6b6b" for p in pnls]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8))

    ax1.bar(all_hours, counts, color="#00d4ff", alpha=0.7, edgecolor="#00d4ff")
    ax1.set_title("Trade Count by Hour (EST)", fontsize=14, fontweight="bold")
    ax1.set_ylabel("Number of Trades")
    ax1.grid(True)

    ax2.bar(all_hours, pnls, color=colors, alpha=0.7)
    ax2.axhline(y=0, color="white", linewidth=0.5)
    ax2.set_title("P&L by Hour (EST)", fontsize=12)
    ax2.set_ylabel("P&L ($)")
    ax2.set_xlabel("Hour (EST)")
    ax2.grid(True)

    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()


def _chart_rr_histogram(metrics: dict, filepath: Path):
    """Chart 5: R:R distribution histogram."""
    rr = metrics.get("rr_ratios", [])
    if not rr:
        return

    fig, ax = plt.subplots(figsize=(12, 6))
    bins = np.arange(min(rr) - 0.5, max(rr) + 0.5, 0.25)
    colors_arr = ["#00ff88" if r > 0 else "#ff6b6b" for r in rr]

    ax.hist(rr, bins=bins, color="#00d4ff", alpha=0.7, edgecolor="white", linewidth=0.5)
    ax.axvline(x=0, color="#ff6b6b", linestyle="--", linewidth=1.5, label="Breakeven")
    ax.axvline(x=np.mean(rr), color="#ffff00", linestyle="-", linewidth=1.5,
              label=f"Avg R:R = {np.mean(rr):.2f}")
    ax.set_title("R:R Distribution", fontsize=14, fontweight="bold")
    ax.set_xlabel("R:R Achieved")
    ax.set_ylabel("Frequency")
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()


def _chart_confluence_winrate(metrics: dict, filepath: Path):
    """Chart 6: Win rate by confluence score."""
    score_wr = metrics.get("confluence_vs_winrate", {})
    if not score_wr:
        return

    scores = sorted(score_wr.keys())
    win_rates = [score_wr[s]["win_rate"] for s in scores]
    counts = [score_wr[s]["total"] for s in scores]

    fig, ax1 = plt.subplots(figsize=(12, 6))
    bars = ax1.bar([str(s) for s in scores], win_rates, color="#00d4ff", alpha=0.7,
                   edgecolor="white", linewidth=0.5)
    ax1.set_ylabel("Win Rate (%)", color="#00d4ff")
    ax1.set_xlabel("Confluence Score")
    ax1.set_title("Win Rate by Confluence Score", fontsize=14, fontweight="bold")

    ax2 = ax1.twinx()
    ax2.plot([str(s) for s in scores], counts, "o-", color="#ffff00", linewidth=2)
    ax2.set_ylabel("Trade Count", color="#ffff00")

    ax1.grid(True)
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()


def _chart_rolling_winrate(result: BacktestResult, filepath: Path):
    """Chart 7: Rolling 20-trade win rate."""
    if len(result.trades) < 20:
        return

    wins = [1 if t.pnl > 0 else 0 for t in result.trades]
    rolling = pd.Series(wins).rolling(20).mean() * 100

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(range(len(rolling)), rolling, color="#00d4ff", linewidth=1.5)
    ax.axhline(y=50, color="#ffff00", linestyle="--", alpha=0.5, label="50% WR")
    ax.fill_between(range(len(rolling)), 50, rolling,
                    where=rolling >= 50, alpha=0.15, color="#00ff88")
    ax.fill_between(range(len(rolling)), 50, rolling,
                    where=rolling < 50, alpha=0.15, color="#ff6b6b")
    ax.set_title("Rolling 20-Trade Win Rate", fontsize=14, fontweight="bold")
    ax.set_xlabel("Trade Number")
    ax.set_ylabel("Win Rate (%)")
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()


def _chart_monte_carlo(mc: MonteCarloResult, filepath: Path):
    """Chart 8: Monte Carlo equity curves (5th/50th/95th percentile)."""
    n = len(mc.equity_curves_50th)
    x = range(n)

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.fill_between(x, mc.equity_curves_5th, mc.equity_curves_95th,
                    alpha=0.2, color="#00d4ff", label="5th-95th percentile")
    ax.plot(x, mc.equity_curves_50th, color="#00ff88", linewidth=2, label="Median (50th)")
    ax.plot(x, mc.equity_curves_5th, color="#ff6b6b", linewidth=1, linestyle="--", label="5th percentile")
    ax.plot(x, mc.equity_curves_95th, color="#00d4ff", linewidth=1, linestyle="--", label="95th percentile")

    ax.set_title(f"Monte Carlo Simulation ({mc.n_iterations} iterations)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Trade Number")
    ax.set_ylabel("Equity ($)")
    ax.legend(loc="upper left")
    ax.grid(True)

    # Add text box with key stats
    textstr = (f"P(Ruin): {mc.probability_of_ruin}%\n"
               f"Max DD 50th: {mc.max_dd_50th}%\n"
               f"Final Eq 50th: ${mc.final_equity_50th:,.0f}")
    props = dict(boxstyle="round", facecolor="#1a1a2e", alpha=0.8, edgecolor="#00d4ff")
    ax.text(0.02, 0.98, textstr, transform=ax.transAxes, fontsize=10,
            verticalalignment="top", bbox=props)

    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()


def _chart_session_pnl(result: BacktestResult, filepath: Path):
    """Chart 9: Cumulative P&L by session (London vs NY)."""
    if not result.trades:
        return

    london_cum = []
    ny_cum = []
    london_total = ny_total = 0

    for t in sorted(result.trades, key=lambda x: x.signal_timestamp):
        if t.session == "London":
            london_total += t.pnl
            london_cum.append(london_total)
        elif t.session == "NY":
            ny_total += t.pnl
            ny_cum.append(ny_total)

    fig, ax = plt.subplots(figsize=(14, 6))
    if london_cum:
        ax.plot(range(len(london_cum)), london_cum, color="#ff9500", linewidth=2, label=f"London (${london_total:,.2f})")
    if ny_cum:
        ax.plot(range(len(ny_cum)), ny_cum, color="#00d4ff", linewidth=2, label=f"NY (${ny_total:,.2f})")

    ax.axhline(y=0, color="white", linewidth=0.5)
    ax.set_title("Cumulative P&L by Session", fontsize=14, fontweight="bold")
    ax.set_xlabel("Trade Number (per session)")
    ax.set_ylabel("Cumulative P&L ($)")
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()
