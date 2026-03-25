# TRADING SCHEDULE - Gold Bot Iterative Optimization

## What This Is
A repeatable optimization workflow for the XAUUSD ICT trading bot. Each run:
1. Reads all code thoroughly
2. Runs a baseline backtest
3. Researches online for theory-based improvements
4. Implements ONE improvement in a variant copy
5. Runs comparison backtest
6. Exports detailed trade log (every trade with entry/exit/time/P&L)
7. Prints before/after comparison table
8. If better: applies the change. If worse: discards it.

**Starting capital: $1,000**

---

## CRITICAL: Environment
- **Working directory:** `c:\Users\aggel\Desktop\trading`
- **Gold bot:** `c:\Users\aggel\Desktop\trading\gold-bot`
- **Real data:** `gold-bot/data/xauusd_5m.csv` (34,697 candles, Dukascopy)
- **DXY data:** `gold-bot/data/dxy_5m.csv` (34,635 candles, Twelve Data)
- **Date range:** 2025-09-01 to 2026-02-28
- **Every bash command:** `cd c:/Users/aggel/Desktop/trading/gold-bot && [command]`

## CRITICAL: The Bot Already Exists
- 38 Python files, fully built and working
- NEVER recreate files, generate synthetic data, or build from scratch
- If anything is missing: STOP and report the error

## CRITICAL: No Curve Fitting
- NEVER adjust parameters based on backtest statistics
- EVERY change must have a theoretical justification from ICT methodology, market microstructure, or professional trading practice
- "Our Tuesday trades lose" = NOT a reason to skip Tuesdays
- "ICT teaches entering at FVG 50% level" = VALID reason to change entry logic
- The backtest VALIDATES theory. It does NOT generate theory.

---

## STEP-BY-STEP EXECUTION

### Phase 0: Verify Environment (30 seconds)
```bash
cd c:/Users/aggel/Desktop/trading && ls gold-bot/main.py gold-bot/data/xauusd_5m.csv gold-bot/data/dxy_5m.csv && wc -l gold-bot/data/xauusd_5m.csv gold-bot/data/dxy_5m.csv
```
- If xauusd_5m.csv has >30,000 lines: PROCEED
- If missing: **ABORT** - print "ERROR: Data files missing"

### Phase 1: Read Current Code (5 minutes)
1. Read ALL key files in `gold-bot/`:
   - `config/settings.py` - parameters
   - `strategy/entry_model.py` - signal generation
   - `backtest/engine.py` - backtest loop
   - `risk/manager.py` - position management
   - `ict/*.py` - all ICT concept modules
2. Print a brief summary of current strategy logic

### Phase 2: Run Baseline (2 minutes)
```bash
cd c:/Users/aggel/Desktop/trading/gold-bot && python main.py --gold-csv data/xauusd_5m.csv --dxy-csv data/dxy_5m.csv --capital 1000 --output results --no-walk-forward 2>&1
```
Record baseline metrics:
- Total Trades, Win Rate, Profit Factor, Sharpe, Max Drawdown
- Avg R:R, Avg Trade Duration, Net P&L, CAGR

### Phase 3: Read Optimization Log (1 minute)
```bash
cd c:/Users/aggel/Desktop/trading/gold-bot && cat results/optimization_log.md 2>/dev/null || echo "No log yet"
```
- Check what was tried before so we don't repeat failures
- Note ideas queued for this run

### Phase 4: Online Research (10 minutes)
Search the web for theory-based improvements. Focus on:
- ICT methodology updates (innercircletrader.net, YouTube ICT mentorship)
- Professional gold trader insights (ForexFactory gold threads, TradingView)
- Academic research on gold microstructure
- Prop firm gold trading strategies
- ATR-based optimization techniques
- Smart Money Concepts research papers

Identify 1-3 potential improvements. Each MUST have:
- **What:** The specific change to make
- **Theory/Source:** Why this should work (external source, not our data)
- **Expected Impact:** What metric should improve and why

### Phase 5: Implement and Test (15 minutes)

1. **Create variant copy:**
```bash
cd c:/Users/aggel/Desktop/trading && cp -r gold-bot/ gold-bot-variant/
```

2. **Apply ONE change** to the variant (in the copied files only)

3. **Run variant backtest:**
```bash
cd c:/Users/aggel/Desktop/trading/gold-bot-variant && python main.py --gold-csv data/xauusd_5m.csv --dxy-csv data/dxy_5m.csv --capital 1000 --output results --no-walk-forward 2>&1
```

4. **Print comparison table:**
```
+-------------------+-----------+-----------+---------+
| Metric            | Baseline  | Variant   | Better? |
+-------------------+-----------+-----------+---------+
| Total Trades      |           |           |         |
| Win Rate          |           |           |         |
| Profit Factor     |           |           |         |
| Sharpe Ratio      |           |           |         |
| Max Drawdown      |           |           |         |
| Net P&L           |           |           |         |
| Avg R:R           |           |           |         |
| CAGR              |           |           |         |
| Expectancy/Trade  |           |           |         |
+-------------------+-----------+-----------+---------+
```

### Phase 6: Decision

**Variant is BETTER if ALL true:**
- Profit Factor improved OR stayed same AND is > 1.0
- Sharpe Ratio improved OR stayed same
- Max Drawdown did not increase > 50%
- Trade count did not decrease > 30%
- Improvement is not suspiciously large (>100% = likely overfit)

**If BETTER:**
```bash
cd c:/Users/aggel/Desktop/trading
rm -rf gold-bot-backup-prev/
mv gold-bot/ gold-bot-backup-prev/
mv gold-bot-variant/ gold-bot/
```
Then commit:
```bash
cd c:/Users/aggel/Desktop/trading && git add gold-bot/ && git commit -m "improve: [description] - theory: [source]"
```

**If WORSE:**
```bash
cd c:/Users/aggel/Desktop/trading && rm -rf gold-bot-variant/
```

### Phase 7: Export Detailed Trade Log (MANDATORY every run)

After the final backtest, generate a detailed CSV with these EXACT columns:

| Column | Description |
|--------|-------------|
| Trade # | Sequential number |
| Date | YYYY-MM-DD |
| Entry Time | HH:MM:SS (EST) |
| Exit Time | HH:MM:SS (EST) |
| Direction | Long / Short |
| Session | London / NY_AM / NY_PM |
| Entry Type | FVG / OB / OB+FVG / BB / EQ |
| Entry Price | Exact price |
| Stop Loss | SL price |
| TP1 Price | TP1 target |
| TP2 Price | TP2 target |
| Exit Price | Actual exit price |
| Exit Reason | TP1 / TP2 / SL / Breakeven / Session End |
| P&L ($) | Dollar profit/loss |
| P&L (%) | Percentage of current equity |
| R Multiple | How many R achieved |
| Running Equity | Account balance after this trade |
| Confluence Score | Number of confluences |
| Confluences Used | List of specific confluences |
| HTF Bias | Bullish / Bearish |
| Trade Duration | Minutes |
| ATR at Entry | Current ATR(14) value |

Save as: `gold-bot/results/detailed_trade_log.csv`

Also print summary:
```
=== TRADE LOG SUMMARY ===
Total trades: X
Date range: YYYY-MM-DD to YYYY-MM-DD
Starting equity: $1,000.00
Final equity: $X,XXX.XX
Best trade: $XX.XX (Trade #X, [date])
Worst trade: -$XX.XX (Trade #X, [date])
Longest winning streak: X trades
Longest losing streak: X trades
```

### Phase 8: Update Optimization Log
Append to `gold-bot/results/optimization_log.md`:
```markdown
## Run: [DATE] [TIME]

### Baseline
- Trades: X | WR: X% | PF: X.XX | Sharpe: X.XX | MaxDD: X% | P&L: $X.XX

### Attempt: [Name of change]
- Theory: [source and reasoning]
- Change: [what was modified]
- Result: Trades: X | WR: X% | PF: X.XX | Sharpe: X.XX | MaxDD: X%
- Verdict: BETTER / WORSE / NEUTRAL
- Applied: YES / NO

### Ideas for Next Run
- [Idea 1 with theory basis]
- [Idea 2 with theory basis]
```

---

## STRICT RULES

1. **NO CURVE FITTING** - Changes must be theory-based, not statistics-based
2. **PROTECT THE ORIGINAL** - Always work on a copy, never modify gold-bot/ directly during testing
3. **ONE CHANGE AT A TIME** - Can't know what helped if you change everything at once
4. **MINIMUM 50 TRADES** - Results with <50 trades are inconclusive
5. **REALISTIC EXPECTATIONS** - ICT gold: 40-55% WR, PF 1.3-2.0, Sharpe 0.5-1.5
6. **NEVER BUILD FROM SCRATCH** - The bot is complete, just optimize it
7. **ALWAYS ABSOLUTE PATHS** - Start every command with `cd c:/Users/aggel/Desktop/trading/gold-bot`
8. **ALWAYS EXPORT TRADE LOG** - Every run must produce detailed_trade_log.csv

## GOLD KNOWLEDGE BASE

| Parameter | Value | Source |
|-----------|-------|--------|
| Gold 5-min ATR(14) | $2-$6 (avg ~$5.68) | Our real data |
| SL distance | ~1.5x ATR ($8-$10) | ATR-based sizing |
| TP1 at 2R | ~$16-$20 | 2x SL distance |
| TP2 at 3R | ~$24-$30 | 3x SL distance |
| Avg trade duration | ~138 min | Current backtest |
| Spread + slippage | $0.50 round trip | Conservative estimate |
| Killzones (EST) | London 2-5AM, NY AM 8:30-11, NY PM 1:30-3 | ICT methodology |
| Asian session | 8PM-12AM EST (range only, NO trades) | ICT Power of 3 |
| Silver Bullet | 3-4AM, 10-11AM, 2-3PM EST | ICT methodology |
| Min confluence score | 5 | Theory-driven threshold |
| DXY correlation | -0.45 (weak) | Use as minor confluence only |

## THEORETICAL IMPROVEMENT AREAS

These are pre-approved research directions (all theory-based):

1. **Trailing Stop after TP1** - ICT trailing methodology for extended moves
2. **Premium/Discount Zones** - Only buy below 50% of range, sell above
3. **Optimal Trade Entry (OTE)** - 62-79% fib retracement of impulse
4. **Session VWAP** - Volume-weighted average price as additional confluence
5. **Volatility Regime Filter** - Don't trade during abnormally low/high ATR
6. **Asian Range Width Filter** - Skip if Asia range is too wide (manipulation done)
7. **Displacement Quality Filter** - Higher body-to-wick ratio requirement
8. **M15 FVG Confirmation** - Use 15-min FVGs instead of 5-min (higher fill rate)
9. **HTF FVG as TP Target** - Target unfilled H1/H4 FVGs instead of fixed R multiples
10. **Market Structure Trailing** - Move SL to last swing low/high after TP1
