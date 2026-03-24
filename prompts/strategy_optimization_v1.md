# GOLD ICT TRADING BOT - STRATEGY OPTIMIZATION PROMPT V1

## Task: Improve Gold ICT Trading Bot - Theory-Driven Optimization

You are working on a gold (XAUUSD) ICT trading bot that uses the Power of 3 methodology (Asia Accumulation -> London Manipulation -> NY Distribution) with FVG entries and liquidity sweeps on 5-minute data.

### CRITICAL RULE: NO CURVE FITTING
- NEVER look at backtest results and then adjust parameters to fit them
- NEVER use statistics like "Tuesday is bad" or "London is better than NY" to filter trades
- Every change MUST be justified by trading theory, market microstructure, or expert methodology BEFORE seeing results
- After making changes, run a CLEAN backtest from scratch
- The backtest validates the theory - it does NOT guide the theory
- If you catch yourself thinking "the backtest shows X, so let's change Y" -- STOP. That is curve fitting.

---

### CURRENT PROBLEMS (from previous backtest)

1. **SL/TP far too small for gold volatility:**
   - Current: SL ~$1.40, TP1 $2.10, TP2 $2.80
   - Gold 5-min ATR(14) = $2-$5. A single candle eats the entire SL.
   - Trades last only 5 minutes (1 bar) because SL/TP get hit instantly
   - This is THE primary reason the strategy loses money

2. **Profit Factor 0.94, Sharpe -0.17** -> strategy is net negative
   - 42% win rate is actually acceptable for ICT (40-55% is realistic)
   - But R:R is terrible because SL and TP are almost the same size
   - With proper 1:2 R:R, even 42% WR gives PF ~1.45

3. **No minimum FVG size filter:**
   - Tiny FVGs on gold are noise, not institutional footprints
   - Need minimum gap size relative to ATR

4. **No HTF (Higher Timeframe) bias confirmation:**
   - Entries happen without knowing if the daily/H4 trend agrees
   - ICT methodology REQUIRES top-down analysis

5. **Sweep detection may be miscalibrated for gold:**
   - Gold sweeps overshoot by $0.50-$2.00, not $0.10-$0.30 like forex

---

### CHANGES TO IMPLEMENT (Theory-Justified)

#### Change 1: ATR-Based SL/TP Sizing
**Theory:** Stop losses must account for instrument volatility. Gold's 5-min ATR is $2-$5, so fixed-dollar stops fail. Professional gold scalpers use 1.5x ATR for SL minimum (source: multiple prop firm training materials, ForexFactory gold threads, LuxAlgo ATR research).

**Implementation:**
```python
atr = calculate_atr(period=14)  # typically $2-$5 for gold 5-min

# Stop Loss: 1.5x ATR below/above entry (minimum $3.00)
stop_loss_distance = max(1.5 * atr, 3.00)

# Take Profit using tiered exits:
# TP1 = 2.0x risk (close 50%, move SL to breakeven)
# TP2 = 3.0x risk (close remaining 50%)
tp1_distance = 2.0 * stop_loss_distance
tp2_distance = 3.0 * stop_loss_distance
```

#### Change 2: FVG Minimum Size Filter
**Theory:** Fair Value Gaps represent institutional imbalances. On gold, micro-gaps under $0.30 are market noise. Only gaps large enough relative to current volatility represent genuine displacement (source: ICT methodology, Edgeful FVG research 60%+ fill rates for filtered FVGs).

**Implementation:**
```python
min_fvg_size = 0.3 * atr  # If ATR=$3, minimum FVG = $0.90
max_fvg_size = 3.0 * atr  # Too large = won't fill cleanly

# Use Consequent Encroachment (CE) - 50% midpoint of FVG as entry
ce_entry = fvg_low + (fvg_high - fvg_low) * 0.5
```

#### Change 3: HTF Bias Filter (Multi-Timeframe Analysis)
**Theory:** ICT requires top-down analysis. Don't take a long on M5 if H4 is bearish. (source: ICT mentorship core principle).

**Implementation:**
```python
# Build HTF candles from 5-min data (H1, H4, Daily)
# Determine bias from H4 swing structure (HH/HL = bullish, LH/LL = bearish)
# Only LONG when HTF bias is bullish
# Only SHORT when HTF bias is bearish
# If neutral (no clear structure) -> NO TRADES
```

#### Change 4: Proper Liquidity Sweep Calibration
**Theory:** Gold sweeps overshoot further than forex due to higher volatility (source: market microstructure, ForexFactory gold traders).

**Implementation:**
```python
sweep_tolerance = 0.5 * atr   # Min overshoot to confirm sweep
max_sweep_overshoot = 2.0 * atr  # Beyond this = breakout, not sweep
# Must close back inside the level
# Must show displacement after sweep
```

#### Change 5: Killzone Time Windows
**Theory:** ICT defines specific institutional activity windows. NOT optimization - these are based on financial center open/close times (source: ICT mentorship, CME volume data).

```python
KILLZONES = {
    "london": {"start": "02:00", "end": "05:00"},      # EST
    "ny_am": {"start": "08:30", "end": "11:00"},        # EST
    "ny_pm": {"start": "13:30", "end": "15:00"},        # EST
}
SILVER_BULLET = {
    "london_sb": {"start": "03:00", "end": "04:00"},
    "ny_am_sb": {"start": "10:00", "end": "11:00"},     # BEST
    "ny_pm_sb": {"start": "14:00", "end": "15:00"},
}
# Asian session = NO ENTRIES, only mark range for sweep detection
```

#### Change 6: Displacement Confirmation After Sweep
**Theory:** A sweep alone doesn't confirm reversal. Need displacement - strong impulsive move creating an FVG (source: ICT core concept).

```python
# After sweep, next 1-3 candles must show:
# - Large body candle (body > 60% of range)
# - Body size > 1.0x ATR
# - Creates a Fair Value Gap
```

#### Change 7: Partial Take Profit
**Theory:** Standard institutional practice - scale out of positions (source: prop firm methodology, ICT scaling).

```python
# TP1 (2R): close 50%, move SL to breakeven
# TP2 (3R): close remaining 50%
# Worst case after TP1: breakeven on remaining
```

#### Change 8: Session Trade Limits
**Theory:** ICT explicitly teaches max 1-2 setups per session. Overtrading = low probability (source: ICT mentorship).

```python
MAX_TRADES_PER_SESSION = 2
MAX_TRADES_PER_DAY = 3
MAX_CONSECUTIVE_LOSSES = 2  # Stop for the day
```

#### Change 9: Order Block Confluence
**Theory:** FVG within an Order Block > standalone FVG (source: ICT OB + FVG confluence concept).

```python
# Bullish OB: Last DOWN candle before impulsive UP move
# Bearish OB: Last UP candle before impulsive DOWN move
# Confluence scoring (theory-based):
# +1: Within HTF Order Block
# +1: FVG present
# +1: Liquidity sweep occurred
# +1: HTF bias aligns
# +1: Silver Bullet window
# +1: DXY inverse movement
# Minimum to trade: 3 out of 6
```

#### Change 10: Spread/Slippage Modeling
**Theory:** Backtests without execution costs are unrealistic (source: market microstructure).

```python
SPREAD = 0.15          # $0.15 per entry (1.5 pips)
SLIPPAGE = 0.10        # $0.10 per trade
TOTAL_COST = (SPREAD + SLIPPAGE) * 2  # $0.50 per round trip
```

---

### COMPREHENSIVE REPORT FORMAT

After backtest, generate a report with these 14 sections:

1. EXECUTIVE SUMMARY (trades, net P&L, verdict)
2. CORE METRICS TABLE (WR, PF, Sharpe, Sortino, MaxDD, Avg Win/Loss, Avg R:R, Duration, Trades/Week, Expectancy, Costs)
3. WIN RATE BY CONFLUENCE SCORE (Score 3/4/5/6)
4. ENTRY TYPE ANALYSIS (FVG vs OB vs OB+FVG)
5. SESSION ANALYSIS (London/NY AM/NY PM/Silver Bullet)
6. DIRECTION ANALYSIS (Long vs Short, HTF aligned vs not)
7. EXIT ANALYSIS (TP1/TP2/SL/Session end/Breakeven counts)
8. RISK ANALYSIS (consecutive wins/losses, drawdown period, recovery factor, Calmar)
9. MONTHLY BREAKDOWN TABLE
10. ATR STATISTICS (avg ATR, min/max, avg SL/TP used)
11. TRADE LOG (first 20 and last 20 trades with full details)
12. PROBLEMS IDENTIFIED
13. COMPARISON WITH PREVIOUS (Before vs After table)
14. NEXT STEPS RECOMMENDATIONS (theory-based only)

Save as `results/optimization_report.txt`

---

### EXECUTION ORDER

1. Read ALL existing strategy files
2. Implement Changes 1-10
3. Print what changed and why
4. Run FULL 6-month backtest
5. Generate comprehensive report
6. Commit changes

### REMINDERS
- ATR must be ROLLING, not fixed
- NO day-of-week or monthly filters
- DXY correlation is WEAK (-0.45) — minor confluence only
- Asian session = mark range only, NO TRADES
- Minimum 50 trades for statistical significance
- If trades still last 1 bar after ATR SL, something is wrong — debug it
