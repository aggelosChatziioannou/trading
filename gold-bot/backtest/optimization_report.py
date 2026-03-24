"""Generate the comprehensive 14-section optimization report."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import numpy as np

from backtest.engine import BacktestResult
from ict.atr import calculate_atr


def generate_optimization_report(
    result: BacktestResult,
    metrics: dict,
    gold_5m: pd.DataFrame,
    output_dir: str = "results",
) -> str:
    """Generate the full 14-section report as text."""
    lines = []
    m = metrics
    trades = result.trades

    def p(s=""):
        lines.append(s)

    p("=" * 70)
    p("GOLD ICT TRADING BOT - OPTIMIZATION REPORT")
    p("Strategy: Power of 3 (Asia Accumulation -> London Manipulation -> NY Distribution)")
    p(f"Data: XAUUSD 5-min, {m.get('data_start', 'N/A')} to {m.get('data_end', 'N/A')}")
    p("=" * 70)

    # 1. Executive Summary
    p("\n1. EXECUTIVE SUMMARY")
    p(f"   Total trades: {m['total_trades']}")
    pnl = m['total_pnl']
    p(f"   Net P&L: ${pnl:,.2f}")
    verdict = "PROFITABLE" if pnl > 0 else ("BREAKEVEN" if abs(pnl) < 5 else "UNPROFITABLE")
    p(f"   Verdict: {verdict}")
    p(f"   Return: {m['return_pct']}% over 6 months")

    # 2. Core Metrics
    p("\n2. CORE METRICS")
    p("   +---------------------+--------------+-----------------+")
    p("   | Metric              | Value        | Assessment      |")
    p("   +---------------------+--------------+-----------------+")

    def row(name, val, assess=""):
        p(f"   | {name:<19} | {str(val):>12} | {assess:<15} |")

    row("Total Trades", m['total_trades'], "Min 80 for sig." if m['total_trades'] < 80 else "OK")
    row("Win Rate", f"{m['win_rate']}%", "Target: 40-55%")
    row("Profit Factor", m['profit_factor'], "GOOD" if m['profit_factor'] >= 1.5 else ("OK" if m['profit_factor'] >= 1.2 else "LOW"))
    row("Sharpe Ratio", m['sharpe_ratio'], "GOOD" if m['sharpe_ratio'] >= 0.5 else "LOW")
    row("Sortino Ratio", m['sortino_ratio'], "Target: >0.70")
    row("Max Drawdown $", f"${m['max_drawdown_dollars']:,.2f}", "")
    row("Max Drawdown %", f"{m['max_drawdown_pct']}%", "GOOD" if abs(m['max_drawdown_pct']) < 15 else "HIGH")
    row("Avg Win", f"${m['avg_win']:,.2f}", "")
    row("Avg Loss", f"${m['avg_loss']:,.2f}", "")
    row("Avg R:R", m['avg_rr'], "Target: >1.5:1")
    row("Largest Win", f"${m['best_trade']:,.2f}", "")
    row("Largest Loss", f"${m['worst_trade']:,.2f}", "")

    # Trade duration
    durations = []
    for t in trades:
        if t.exit_time and t.signal_timestamp:
            dur = (t.exit_time - t.signal_timestamp).total_seconds() / 60
            durations.append(dur)
    avg_dur = np.mean(durations) if durations else 0
    avg_bars = avg_dur / 5 if avg_dur > 0 else 0
    row("Avg Duration", f"{avg_dur:.0f} min", "")
    row("Avg Bars", f"{avg_bars:.1f}", "")
    row("Trades/Week", m['trades_per_week'], "Target: 3-8")
    row("Expectancy/Trade", f"${pnl / m['total_trades']:.2f}" if m['total_trades'] > 0 else "$0", "")

    # Total costs
    total_costs = sum(0.50 * t.total_oz for t in trades)
    row("Total Costs", f"${total_costs:.2f}", "")
    p("   +---------------------+--------------+-----------------+")

    # 3. Win Rate by Confluence Score
    p("\n3. WIN RATE BY SETUP QUALITY (Confluence Score)")
    for score, data in sorted(m.get("confluence_vs_winrate", {}).items()):
        score_trades = [t for t in trades if t.confluence_score == score]
        avg_pnl = np.mean([t.pnl for t in score_trades]) if score_trades else 0
        p(f"   Score {score}: {data['total']} trades, {data['win_rate']}% WR, ${avg_pnl:.2f} avg P&L")

    # 4. Entry Type Analysis
    p("\n4. ENTRY TYPE ANALYSIS")
    for et, stats in m.get("entry_types", {}).items():
        wr = round(stats["wins"] / stats["count"] * 100, 1) if stats["count"] > 0 else 0
        et_trades = [t for t in trades if t.entry_type == et]
        avg_r = np.mean([abs(t.pnl) / abs(t.entry_price - t.original_sl) / t.total_oz
                        for t in et_trades if abs(t.entry_price - t.original_sl) * t.total_oz > 0]) if et_trades else 0
        p(f"   {et}: {stats['count']} trades, {wr}% WR, avg R={avg_r:.2f}")

    # 5. Session Analysis
    p("\n5. SESSION ANALYSIS")
    p(f"   London:    {m['london_trades']} trades, {m['london_win_rate']}% WR, ${m['london_pnl']:,.2f} P&L")
    p(f"   NY AM:     {m.get('ny_am_trades', 0)} trades, {m.get('ny_am_win_rate', 0)}% WR, ${m.get('ny_am_pnl', 0):,.2f} P&L")
    p(f"   NY PM:     {m.get('ny_pm_trades', 0)} trades, {m.get('ny_pm_win_rate', 0)}% WR, ${m.get('ny_pm_pnl', 0):,.2f} P&L")
    sb_trades = [t for t in trades if "silver_bullet" in t.confluences]
    sb_wins = len([t for t in sb_trades if t.pnl > 0])
    sb_wr = round(sb_wins / len(sb_trades) * 100, 1) if sb_trades else 0
    sb_pnl = sum(t.pnl for t in sb_trades)
    p(f"   Silver Bullet: {len(sb_trades)} trades, {sb_wr}% WR, ${sb_pnl:,.2f} P&L")

    # 6. Direction Analysis
    p("\n6. DIRECTION ANALYSIS")
    longs = [t for t in trades if t.direction == "long"]
    shorts = [t for t in trades if t.direction == "short"]
    long_wr = round(len([t for t in longs if t.pnl > 0]) / len(longs) * 100, 1) if longs else 0
    short_wr = round(len([t for t in shorts if t.pnl > 0]) / len(shorts) * 100, 1) if shorts else 0
    p(f"   Long:  {len(longs)} trades, {long_wr}% WR, ${sum(t.pnl for t in longs):,.2f} P&L")
    p(f"   Short: {len(shorts)} trades, {short_wr}% WR, ${sum(t.pnl for t in shorts):,.2f} P&L")

    # 7. Exit Analysis
    p("\n7. EXIT ANALYSIS")
    tp1 = sum(1 for t in trades if t.tp1_hit)
    tp2 = sum(1 for t in trades if t.tp2_hit)
    sl = sum(1 for t in trades if t.sl_hit)
    be = sum(1 for t in trades if t.tp1_hit and t.sl_hit)  # TP1 hit then BE stop hit
    p(f"   TP1 hit (2R):     {tp1} trades ({round(tp1/len(trades)*100,1)}%)")
    p(f"   TP2 hit (3R):     {tp2} trades ({round(tp2/len(trades)*100,1)}%)")
    p(f"   SL hit:           {sl} trades ({round(sl/len(trades)*100,1)}%)")
    p(f"   Breakeven exits:  {be} trades ({round(be/len(trades)*100,1)}%)")

    # 8. Risk Analysis
    p("\n8. RISK ANALYSIS")
    p(f"   Max consecutive wins:  {m['max_consecutive_wins']}")
    p(f"   Max consecutive losses: {m['max_consecutive_losses']}")
    p(f"   Max DD duration:       {m['max_drawdown_duration_days']} days")
    p(f"   Recovery factor:       {m['recovery_factor']}")
    p(f"   Calmar ratio:          {m['calmar_ratio']}")

    # 9. Monthly Breakdown
    p("\n9. MONTHLY BREAKDOWN")
    p("   +----------+--------+--------+--------+")
    p("   | Month    | Trades | WR     | P&L    |")
    p("   +----------+--------+--------+--------+")
    monthly_trades = {}
    monthly_wins = {}
    for t in trades:
        mk = t.signal_timestamp.strftime("%Y-%m")
        monthly_trades[mk] = monthly_trades.get(mk, 0) + 1
        if t.pnl > 0:
            monthly_wins[mk] = monthly_wins.get(mk, 0) + 1
    for month in sorted(m.get("monthly_pnl", {}).keys()):
        mt = monthly_trades.get(month, 0)
        mw = monthly_wins.get(month, 0)
        mwr = round(mw / mt * 100, 1) if mt > 0 else 0
        mpnl = m["monthly_pnl"][month]
        p(f"   | {month}  | {mt:>6} | {mwr:>5}% | ${mpnl:>6.2f} |")
    p("   +----------+--------+--------+--------+")

    # 10. ATR Statistics
    p("\n10. ATR STATISTICS")
    atr_series = calculate_atr(gold_5m)
    atr_vals = atr_series.dropna()
    p(f"    Average ATR(14) on 5-min: ${atr_vals.mean():.2f}")
    p(f"    Min ATR: ${atr_vals.min():.2f} | Max ATR: ${atr_vals.max():.2f}")
    sl_distances = [abs(t.entry_price - t.original_sl) for t in trades]
    p(f"    Average SL used: ${np.mean(sl_distances):.2f}" if sl_distances else "    No trades")
    tp1_distances = [abs(t.tp1 - t.entry_price) for t in trades]
    tp2_distances = [abs(t.tp2 - t.entry_price) for t in trades]
    p(f"    Average TP1 distance: ${np.mean(tp1_distances):.2f}" if tp1_distances else "")
    p(f"    Average TP2 distance: ${np.mean(tp2_distances):.2f}" if tp2_distances else "")

    # 11. Trade Log (first 10 + last 10)
    p("\n11. TRADE LOG (first 10 and last 10)")
    p("    Entry Time          | Dir   | Sess   | Type   | Conf | Entry $  | SL $     | TP1 $    | Exit $   | Exit   | P&L $  | R")
    p("    " + "-" * 120)
    sorted_trades = sorted(trades, key=lambda x: x.signal_timestamp)
    show = sorted_trades[:10] + (sorted_trades[-10:] if len(sorted_trades) > 20 else [])
    if len(sorted_trades) > 20:
        show = sorted_trades[:10]
        p("    ... (showing first 10)")
    for t in show:
        risk = abs(t.entry_price - t.original_sl) * t.total_oz
        r_mult = round(t.pnl / risk, 2) if risk > 0 else 0
        exit_reason = "TP2" if t.tp2_hit else ("TP1+SL" if t.tp1_hit and t.sl_hit else ("TP1" if t.tp1_hit else ("SL" if t.sl_hit else "EOD")))
        p(f"    {t.signal_timestamp} | {t.direction:>5} | {t.session:>6} | {t.entry_type:>6} | {t.confluence_score:>4} | {t.entry_price:>8.2f} | {t.original_sl:>8.2f} | {t.tp1:>8.2f} | {t.exit_price:>8.2f} | {exit_reason:>6} | {t.pnl:>6.2f} | {r_mult}")
    if len(sorted_trades) > 20:
        p("    ...")
        for t in sorted_trades[-10:]:
            risk = abs(t.entry_price - t.original_sl) * t.total_oz
            r_mult = round(t.pnl / risk, 2) if risk > 0 else 0
            exit_reason = "TP2" if t.tp2_hit else ("TP1+SL" if t.tp1_hit and t.sl_hit else ("TP1" if t.tp1_hit else ("SL" if t.sl_hit else "EOD")))
            p(f"    {t.signal_timestamp} | {t.direction:>5} | {t.session:>6} | {t.entry_type:>6} | {t.confluence_score:>4} | {t.entry_price:>8.2f} | {t.original_sl:>8.2f} | {t.tp1:>8.2f} | {t.exit_price:>8.2f} | {exit_reason:>6} | {t.pnl:>6.2f} | {r_mult}")

    # 12. Problems Identified
    p("\n12. PROBLEMS IDENTIFIED")
    one_bar = sum(1 for d in durations if d <= 5)
    p(f"    - 1-bar trades (SL/TP hit within 5min): {one_bar}/{len(trades)} ({round(one_bar/len(trades)*100,1)}%)")
    if one_bar > len(trades) * 0.5:
        p("      WARNING: More than 50% of trades are 1-bar. SL may still be too tight.")
    else:
        p("      OK: Less than 50% are 1-bar trades — ATR sizing is working.")

    outside_kz = [t for t in trades if t.session not in ("London", "NY_AM", "NY_PM")]
    p(f"    - Trades outside killzones: {len(outside_kz)} (should be 0)")

    # 13. Comparison
    p("\n13. COMPARISON WITH PREVIOUS VERSION")
    p("    +-------------------+-----------+-----------+")
    p("    | Metric            | Before    | After     |")
    p("    +-------------------+-----------+-----------+")

    def cmp_row(name, before, after):
        p(f"    | {name:<17} | {str(before):>9} | {str(after):>9} |")

    cmp_row("Trades", 102, m['total_trades'])
    cmp_row("Win Rate", "42.2%", f"{m['win_rate']}%")
    cmp_row("Profit Factor", 0.94, m['profit_factor'])
    cmp_row("Sharpe", -0.17, m['sharpe_ratio'])
    cmp_row("Max DD", "-2.6%", f"{m['max_drawdown_pct']}%")
    cmp_row("Avg R:R", "~0.01", m['avg_rr'])
    cmp_row("Avg Duration", "5 min", f"{avg_dur:.0f} min")
    cmp_row("Total P&L", "-$2.12", f"${m['total_pnl']:,.2f}")
    cmp_row("CAGR", "-0.9%", f"{m['cagr']}%")
    p("    +-------------------+-----------+-----------+")

    # 14. Next Steps
    p("\n14. NEXT STEPS RECOMMENDATIONS")
    p("    1. Trailing stop after TP1: Instead of fixed TP2, trail SL at 1.5x ATR")
    p("       Theory: ICT mentorship trailing methodology captures extended moves")
    p("       Expected: Higher avg win, lower TP2 hit rate but bigger winners")
    p("    2. Session-specific ATR: Use London ATR for London entries, NY ATR for NY")
    p("       Theory: London volatility differs from NY (CME volume data)")
    p("       Expected: Better calibrated SL for each session")
    p("    3. Premium/Discount zones: Only enter longs in discount (below 50% range),")
    p("       shorts in premium (above 50% range)")
    p("       Theory: ICT Premium/Discount concept — institutional accumulation zones")
    p("       Expected: Higher win rate, fewer trades")
    p("    4. Optimal Trade Entry (OTE): Use 62-79% fib retracement of impulse")
    p("       Theory: ICT OTE is the institutional reload zone")
    p("       Expected: Better entries, wider SL tolerance")

    p("\n" + "=" * 70)
    p("END OF REPORT")
    p("=" * 70)

    report_text = "\n".join(lines)

    # Save to file
    out = Path(output_dir) / "optimization_report.txt"
    out.write_text(report_text, encoding="utf-8")
    print(f"  Optimization report saved: {out}")

    # Print to console
    print(report_text)

    return report_text
