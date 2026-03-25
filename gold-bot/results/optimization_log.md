# Gold ICT Bot — Optimization Log

---

## Run 1: 2026-03-25 15:19 UTC

### Memory Analysis Summary
- Past runs analyzed: 0 (FIRST RUN)
- Blacklisted approaches: None
- Today's strategy: Analyze baseline performance, identify weakest segments, apply highest-impact quality filter

### Current Baseline (before this run)
- Trades: 142 | WR: 43.7% | PF: 1.38 | Sharpe: 1.14 | MaxDD: -2.1% | P&L: $31.97
- Change from last baseline: N/A — first optimization run

### Key Baseline Observations
- EQ entries underperform: 32 trades, 28.1% WR, -$6.49 P&L (drag on overall)
- Score 4 confluence: 42 trades, 33.3% WR, -$0.13 avg P&L (below 40% WR target)
- Score 5+: ~100 trades, ~48% WR, consistently profitable
- FVG entries strong: 110 trades, 48.2% WR, +$38.46
- NY PM best session (53.6% WR), London weakest (41.1%)
- Max consecutive losses: 11 (concerning)
- TP2 hit only 27.5% of time — many TP1+breakeven exits

### Attempt 1: Raise Minimum Confluence Score from 3 to 5
- Priority source: New analysis of baseline data + ICT theory
- Theory: ICT methodology emphasizes that higher confluence = higher probability setups. Score-4 trades have only the bare minimum (1 reversal + 1 confirmation + 1 continuation + htf_bias). Requiring score ≥ 5 means at least one EXTRA confirmation factor (e.g., displacement + BOS + FVG, or silver_bullet bonus). This is consistent with ICT mentorship emphasis on "stacking confluences" and the "Golden Overlap" concept from professional ICT traders.
- Relationship to past attempts: First attempt — establishing the quality filter baseline
- Change: `config/settings.py` line 100: `MIN_CONFLUENCES = 3` → `MIN_CONFLUENCES = 5`
- Result:

```
┌─────────────────┬───────────┬───────────┬──────────────────────┐
│ Metric          │ Original  │ Variant   │ Change               │
├─────────────────┼───────────┼───────────┼──────────────────────┤
│ Total Trades    │ 142       │ 127       │ -10.6%               │
│ Win Rate        │ 43.7%     │ 46.5%     │ +2.8pp               │
│ Profit Factor   │ 1.38      │ 1.52      │ +10.1%               │
│ Sharpe Ratio    │ 1.14      │ 1.44      │ +26.3%               │
│ Sortino Ratio   │ 0.38      │ 0.47      │ +23.7%               │
│ Max Drawdown    │ -2.1%     │ -2.3%     │ +0.2pp (slightly ↑)  │
│ Net P&L         │ $31.97    │ $38.46    │ +20.3%               │
│ Avg R:R         │ 0.21      │ 0.29      │ +38.1%               │
│ Expectancy/Trade│ $0.23     │ $0.30     │ +30.4%               │
│ Max Consec Loss │ 11        │ 5         │ Massive improvement   │
│ CAGR            │ 13.4%     │ 16.2%     │ +20.9%               │
│ Calmar Ratio    │ 6.24      │ 6.89      │ +10.4%               │
└─────────────────┴───────────┴───────────┴──────────────────────┘
```

- Verdict: **BETTER**
- Applied: **YES**
- **Why it worked:** Score-4 trades had only the bare minimum confluences and a 33.3% WR — below the 40% viability threshold. By filtering them out, we removed ~15 net-negative trades (not all 42, because some daily trade slots opened for higher-quality later entries). The filter also improved EQ entries from 28.1% → 37.5% WR, suggesting many of the worst EQ trades were low-confluence. The dramatic improvement in max consecutive losses (11→5) shows the filter prevents the worst losing streaks — those extended losing runs were driven by marginal setups.
- **Retry potential:** SUCCESSFUL — now part of baseline. Future runs should NOT lower this back to 3.
- **Key insight:** The minimum confluence check in `is_valid` was permissive enough to let through trades with barely-qualifying setups. The real quality threshold for gold ICT is 5 confluences, not 3.

### Cumulative Progress
- Total optimization runs: 1
- Successful improvements: 1
- Failed attempts: 0
- Blacklisted approaches: 0
- Current best PF: 1.52 (started at 1.38, originally 0.94)
- Current best Sharpe: 1.44 (started at 1.14, originally -0.17)
- Areas explored: Entry quality filtering (confluence score)
- Areas untouched: Exit optimization, Premium/Discount zones, Session-specific ATR, OTE entries, Trailing stops, Volatility regime filters, News filtering enhancement, Multi-instrument confluence refinement

### Ranked Ideas for Next Run
1. **[PRIORITY 1 — Untested, from report]** Trailing stop after TP1: Instead of fixed TP2, trail SL using market structure or 1.5x ATR. Theory: ICT mentorship trailing methodology. Currently TP2 only hit 29.1%, many trades exit at breakeven after TP1. Trailing could capture more from extended moves.
2. **[PRIORITY 2 — Untested, from report]** Premium/Discount zone filter: Only enter longs in discount zone (below 50% of daily range), shorts in premium. Theory: Core ICT concept — institutional accumulation/distribution zones. Web research confirms this is a well-validated ICT filter. Expected: Higher WR, slightly fewer trades.
3. **[PRIORITY 3 — Untested, from report]** Session-specific ATR: Use session-local ATR for SL sizing instead of global ATR. Theory: London and NY have different volatility profiles (CME volume data). Expected: Better calibrated SL per session.
4. **[PRIORITY 4 — Untested, from report]** OTE entry: Use 62-79% fib retracement of displacement impulse for entries. Theory: ICT Optimal Trade Entry is the "institutional reload zone." Expected: Tighter SL, better entries.
5. **[PRIORITY 5 — Refinement]** EQ entry improvement: EQ entries still underperform at 37.5% WR vs FVG 49.5%. Consider requiring EQ entries to have confluence ≥ 6, or adding an additional filter (e.g., must be inside a discount/premium zone).
6. **[PRIORITY 6 — New research]** Volatility regime filter: Don't trade when ATR is abnormally low (<50th percentile) or high (>95th percentile). Theory: Low-vol environments lack displacement, extreme vol causes erratic fills.

### Anti-Pattern Watch
- No patterns to watch yet (first run). Will monitor for oscillation and diminishing returns in future runs.

---

## Run 2: 2026-03-25 (Trading Schedule — First Manual Iteration)

### Current Baseline (before this run)
- Trades: 127 | WR: 46.5% | PF: 1.54 | Sharpe: 1.50 | MaxDD: -2.3% | P&L: $79.80 (at $1000 capital)

### Attempt 1: Premium/Discount Zone Filter
- Theory: ICT teaches only buy in discount (below 50% of dealing range), sell in premium. Source: innercircletrader.net, equiti.com, opofinance.com
- Change: Added Gate 3.5 in entry_model.py — used last 24 H1 candles to define dealing range, filtered longs above equilibrium and shorts below
- Result: Trades: 77 | WR: 35.1% | PF: 1.00 | Sharpe: 0.02 | MaxDD: -3.5%
- Verdict: **WORSE** — Filter too aggressive, rejected 39% of trades including many winners. The 24-hour dealing range is too narrow for gold's trending nature.
- Applied: **NO**
- Learning: P/D zones may work better with a wider dealing range (H4 or Daily swing range) rather than rolling 24H candles. Gold trends strongly and the equilibrium shifts quickly.

### Attempt 2: Market Structure Trailing Stop after TP1
- Theory: ICT mentorship teaches trailing stop behind market structure after first take profit. Instead of fixed TP2, trail SL 1x original risk behind best price since TP1. This captures extended Power of 3 distribution moves. Sources: ICT mentorship trailing methodology, ForexFactory ICT threads, tradingfinder.com
- Change: Modified `risk/manager.py` — after TP1 hit, track best_price_since_tp1 and trail SL at 1x original risk distance behind it. TP2 hard target kept as max exit.
- Result:

```
+-------------------+-----------+-----------+---------+
| Metric            | Baseline  | Trailing  | Better? |
+-------------------+-----------+-----------+---------+
| Total Trades      | 127       | 129       | YES     |
| Win Rate          | 46.5%     | 47.3%     | YES     |
| Profit Factor     | 1.54      | 1.69      | YES     |
| Sharpe Ratio      | 1.50      | 1.87      | YES     |
| Max Drawdown      | -2.3%     | -2.1%     | YES     |
| Net P&L           | +$79.80   | +$96.55   | YES     |
| CAGR              | 16.9%     | 20.6%     | YES     |
| Avg R:R           | 0.29      | 0.33      | YES     |
| Expectancy/Trade  | $0.63     | $0.75     | YES     |
| Recovery Factor   | 3.21      | 4.26      | YES     |
+-------------------+-----------+-----------+---------+
```

- Verdict: **BETTER** — ALL metrics improved
- Applied: **YES**
- Why it worked: The fixed TP2 at 3R was too far for most trades — only 29.1% reached it. With trailing, winners that moved past TP1 but couldn't reach TP2 now capture partial profits (trailing exit) instead of reverting to breakeven. TP2 hit rate dropped to 17.1% but breakeven exits increased from 17.3% to 30.2%, with most of those "breakeven" exits actually being trailing exits above breakeven. Net effect: +21% more profit.

### Cumulative Progress
- Total optimization runs: 2
- Successful improvements: 2 (confluence filter + trailing stop)
- Failed attempts: 1 (Premium/Discount zone — too aggressive)
- Blacklisted approaches: P/D zone with 24H dealing range (too narrow for gold)
- Current best PF: 1.69 (started at 0.94)
- Current best Sharpe: 1.87 (started at -0.17)

### Ideas for Next Run
1. **Premium/Discount with wider range** — Use H4 or Daily swing high/low instead of 24H rolling, may work better
2. **Session-specific ATR** — London and NY have different volatility, session-local ATR for SL
3. **OTE entry (62-79% fib retracement)** — ICT Optimal Trade Entry for tighter SL
4. **Volatility regime filter** — Skip trades when ATR is abnormally low or extreme
5. **H1 FVG as additional confluence** — Research shows H1 FVGs have higher fill rates than M5

---

## Run 3: 2026-03-25 (Trading Schedule — Queued Improvements)

### Baseline (after Run 2)
- Trades: 129 | WR: 47.3% | PF: 1.69 | Sharpe: 1.87 | MaxDD: -2.1% | P&L: $96.55

### Attempt 1: OTE Entry (70.5% fib retracement of FVG)
- Theory: ICT Optimal Trade Entry — the 62-79% fib retracement of an impulse move is where institutions reload orders. The precise OTE is 0.705. Entering deeper in the FVG gives a better price and tighter SL. Source: innercircletrader.net OTE tutorial, ForexFactory OTE guide, howtotrade.com
- Change: Modified FVG entry from CE (50%) to OTE (70.5% retracement within FVG zone). For bullish FVGs, entry is 70.5% from top toward bottom (deeper = better price). For bearish, 70.5% from bottom toward top.
- Result: Trades: 129 | WR: 49.6% | PF: 1.72 | Sharpe: 1.93 | MaxDD: -2.2% | P&L: $105.84
- Verdict: **BETTER** — WR +2.3pp, PF +0.03, Sharpe +0.06, P&L +$9.29
- Applied: **YES**

### Attempt 2: Volatility Regime Filter (skip low/high ATR)
- Theory: Low ATR = no displacement possible, FVGs are noise. Extreme ATR = erratic execution. Source: market microstructure, quantvps.com
- Change: Skip trades when ATR < 25th percentile or > 95th percentile of rolling ATR
- Result: Trades: 103 | WR: 48.5% | PF: 1.67 | Sharpe: 1.67 | MaxDD: -2.9% | P&L: $102.99
- Verdict: **WORSE** — removed 20% of trades, PF and Sharpe dropped
- Applied: **NO**
- Learning: The ATR percentile approach is too crude. Gold's ATR distribution is wide and the filter catches too many valid setups. A better approach might be minimum absolute ATR floor ($2) instead of percentile.

### Attempt 3: H1 FVG as Additional Confluence
- Theory: Higher timeframe FVGs have higher fill rates and institutional significance. M5 entry within an unfilled H1 FVG adds quality. Source: edgeful.com FVG research, tradervue.com
- Change: Added h1_fvg confluence type — detect FVGs on 1H data, if current price is within an unfilled H1 FVG matching trade direction, add +1 confluence score
- Result: Trades: 132 | WR: 46.2% | PF: 1.46 | Sharpe: 1.38 | MaxDD: -2.9% | P&L: $68.55
- Verdict: **WORSE** — PF dropped 1.72→1.46, Sharpe 1.93→1.38
- Applied: **NO**
- Learning: The H1 FVGs on resampled data may not be clean enough. The additional trades at Score 6/7 weren't actually higher quality. H1 FVG detection may need separate ATR calibration for H1 timeframe.

### Attempt 4: Session-Specific ATR
- Theory: London and NY have different volatility profiles. Session-local ATR gives better calibrated SL per session. Source: CME Group volume data
- Change: Filter ATR calculation history to only same-session bars (London hours for London entries, NY hours for NY entries)
- Result: Trades: 129 | WR: 49.6% | PF: 1.72 | Sharpe: 1.93 | MaxDD: -2.2% | P&L: $105.87
- Verdict: **NEUTRAL** — essentially identical, marginally better session-level WR
- Applied: **YES** (theoretically sounder, zero downside)

### Final State After Run 3
- Trades: 129 | WR: 49.6% | PF: 1.72 | Sharpe: 1.93 | MaxDD: -2.2% | P&L: $105.87
- CAGR: 22.7% | Calmar: 10.2 | Recovery: 4.43

### Cumulative Progress
- Total optimization runs: 3
- Successful improvements: 4 (confluence filter, trailing stop, OTE entry, session ATR)
- Failed attempts: 3 (P/D zone 24H, vol regime filter, H1 FVG confluence)
- Current best PF: 1.72 (started at 0.94)
- Current best Sharpe: 1.93 (started at -0.17)
- Progression: 0.94 → 1.38 → 1.54 → 1.69 → 1.72

### Ideas for Next Run
1. **Premium/Discount with H4 swing range** — Use H4 swing high/low as dealing range instead of 24H rolling
2. **Minimum absolute ATR floor** — Skip trades when ATR < $2.00 (too quiet for displacement)
3. **EQ entry quality** — EQ entries still at 38.7% WR vs FVG 50%. Consider requiring EQ entries to have confluence >= 6
4. **Trailing stop optimization** — Test different trail distances (0.75x risk, 1.25x risk)
5. **Asian range width filter** — If Asian range > 2x median, manipulation may be done already
