# GOLD TACTIC — Trading Methodology v2.0 Design

**Date:** 2026-04-04
**Author:** Aggelos + Claude
**Goal:** Aggressive growth (1000€→2000€) with 4-8 trades/week
**Status:** APPROVED

## Why This Redesign

Backtest analysis revealed critical weaknesses:
- 100% trend-following strategies in a 70% ranging market
- NAS100 TJR losing money (-0.2€/trade on 24 trades)
- XAUUSD TJR consistently losing (-9.7€/trade)
- Risk sizing contradictory (10% stated vs 1.5% in config)
- Fake diversification (EUR+GBP = 95% correlated)
- 33/33/33 ladder sub-optimal for 27-37% win rates

---

## 1. STRATEGY PORTFOLIO v2.0

### REMOVED (proven losers)
- NAS100 TJR: -0.2€/trade (coin flip, not edge)
- XAUUSD TJR: -9.7€/trade (consistent loser)
- Counter-trend SOL/BTC: Doesn't outperform trend-following

### KEPT (proven edge, tightened filters)

#### A. TJR Asia Sweep (EURUSD *or* GBPUSD — NEVER both)
- **Edge:** +10.8€/trade (EURUSD), +9.8€/trade (GBPUSD)
- **New filters:**
  - ONLY when ADX > 25 (trending regime)
  - ONLY during London session 09:00-11:00 EET (peak momentum)
  - Volume on sweep candle must be > 20-day average
  - Spread must be < 20% of SL distance
  - Correlation gate: if EUR active, GBP blocked (and vice versa)
- **Entry precision (tightened):**
  - "Retracement" = price closes within 50% of BOS distance from BOS level
  - BOS must be confirmed on 5min close, not just wick

#### B. IBB Initial Balance Breakout (NAS100)
- **Edge:** +3.2€/trade, 60% WR (best strategy in backtest)
- **New filters:**
  - IB window: 16:30-17:30 EET (first hour NY)
  - Entry ONLY after 17:30 when IB breaks
  - Wait for 15-min close above/below IB to confirm (not just wick)
  - No entry if FOMC/NFP/CPI today
  - No entry after 20:00 EET (not enough time for targets)
- **Research backing:** ORB/IB strategies show 55% follow-through rate
  on NAS100, with 60-80 point average move after breakout.
  Source: quantamentaltrader.substack.com

### NEW STRATEGIES

#### C. Session High/Low Fade (EURUSD/GBPUSD — ranging days)
- **Research:** London session high/low broken 97% of the time.
  Source: tradethatswing.com
- **Edge concept:** On RANGING days (ADX < 20), price oscillates
  between session boundaries. Buy near session low, sell near session high.
- **Rules:**
  - ONLY when regime = RANGING (ADX < 20)
  - Identify London session H/L (09:00-12:00 EET range)
  - If price returns to session low after establishing high → LONG
  - If price returns to session high after establishing low → SHORT
  - SL: 10 pips beyond session H/L
  - TP: 1:1 R:R only (quick exit, no runners)
  - Max 2 trades per session (not over-trading)
- **Expected:** 60-70% WR, small per-trade profit, HIGH frequency

#### D. Crypto Mean Reversion (BTC *or* SOL — NEVER both)
- **Research:** Mean reversion with Bollinger Bands + RSI works in
  range-bound crypto. Source: 3commas.io, kraken.com
- **Rules:**
  - ONLY when ADX < 20 AND price within Bollinger Bands
  - LONG when: RSI(4H) < 30 + price touches lower BB + volume spike
  - SHORT when: RSI(4H) > 70 + price touches upper BB + volume spike
  - SL: Beyond Bollinger Band (1-2 ATR)
  - TP: Middle band (SMA20) = 1:1 R:R
  - NOT during strong trends (ADX > 25 = disabled)
  - Correlation gate: BTC or SOL, never both
- **Expected:** 60-65% WR, moderate per-trade profit

#### E. Gold NY Killzone (XAUUSD — replaces TJR)
- **Research:** Gold's highest movement occurs during NY AM session
  (15:00-18:00 EET), driven by US macro data. Asian session defines
  consolidation range that London/NY target.
  Source: acy.com, thinkmarkets.com
- **Rules:**
  - ONLY during NY session (15:30-18:30 EET)
  - Identify Asian session range (previous night H/L)
  - Wait for sweep of Asian H or L during NY
  - Entry on BOS after sweep confirmation (5min close)
  - SL: Behind swept extreme
  - TP1: 1:1, TP2: 2:1
  - No entry 2 hours before/after FOMC or major USD data
- **Expected:** 45-55% WR, high R:R (gold has large ranges)

---

## 2. REGIME-FIRST DAILY FLOW

Every day starts with REGIME detection, then strategy selection.

### Morning Scanner (08:00 EET) Decision Tree:

```
FOR EACH ASSET:
  1. Compute ADX (daily)
  2. IF ADX > 25 → TRENDING
     → Activate: TJR (forex), IBB (NAS100), Crypto Trend (BTC/SOL)
  3. IF ADX 15-25 → RANGING
     → Activate: Session H/L Fade (forex), Mean Reversion (crypto)
  4. IF ADX < 15 → CHOPPY
     → NO TRADING for this asset today
     → Send: "💤 [ASSET] choppy — no setups"
```

### Daily Asset Allocation (max 2 concurrent trades):

| Slot | Asset Class | Strategy (trending) | Strategy (ranging) |
|------|------------|--------------------|--------------------|
| Slot 1 | Forex | TJR (EUR or GBP) | Session H/L Fade |
| Slot 2 | Index/Crypto/Gold | IBB (NAS100) or Gold NK | Mean Reversion (crypto) |

**Rule:** Max 1 trade per slot. Total max 2 trades open.

---

## 3. RISK MANAGEMENT v2.0

### Position Sizing: ATR-Based

```
base_risk = 2% of current balance (20€ on 1000€)

volatility_modifier = current_ATR(14) / SMA(ATR(14), 20)
  - If ATR normal: modifier = 1.0
  - If ATR high (>1.3x avg): modifier = 0.7 (reduce size)
  - If ATR low (<0.7x avg): modifier = 1.2 (increase size)

confidence_modifier:
  - TRS 5/5: × 1.0
  - TRS 4/5: × 0.85
  - TRS 3/5: NO TRADE (wait)

final_risk = base_risk × volatility_modifier × confidence_modifier
  - Min: 10€
  - Max: 40€ (4% of initial capital)
```

### Daily Loss Limit

```
max_daily_loss = 4% of balance (40€ on 1000€)
  - After 40€ loss → STOP for the day
  - No more entries, only management of open trades
```

### Concurrent Trades

```
max_open = 2 (was 3)
max_per_class = 1 forex + 1 non-forex
correlation_gate: NEVER both EUR+GBP or BTC+SOL
```

### Quality-Based Ladder

| Setup | TP1 (%) | @ R:R | TP2 (%) | @ R:R | Runner (%) | Logic |
|-------|---------|-------|---------|-------|-----------|-------|
| **5/5 Trend** | 25% | 1:1 | 50% | 2:1 | 25% trail | High conviction → big runner |
| **4/5 Trend** | 33% | 1:1 | 33% | 1.5:1 | 33% trail | Standard |
| **Range Bounce** | 50% | 0.8:1 | 50% | 1:1 | NONE | Quick in-out, no runner |
| **Mean Reversion** | 50% | 1:1 | 50% | SMA20 | NONE | Target = middle band |

### SL Rules (UNCHANGED — iron rules)
- Before TP1: NEVER move SL
- After TP1: Move to entry (breakeven)
- After TP2: Move to TP1 (profit locked)
- Runner: Trail forward only

---

## 4. ENTRY PRECISION (tightened definitions)

### "Retracement" (was vague):
NOW: "Price CLOSES within 50% of BOS distance from BOS level on 5min timeframe"

### "Recent lows" for mean reversion:
NOW: "5-period swing low on H1 timeframe"

### "BOS confirmation":
NOW: "5min candle CLOSES beyond the structure level (not just wick)"

### "Asia sweep":
NOW: "Price moves beyond Asia H or L by at least 3 pips (forex) / $5 (gold) / $50 (BTC)"

---

## 5. NEW ANALYSIS FILTERS

### Spread Filter
```
IF current_spread > 20% of planned_SL → SKIP trade
Example: SL = 15 pips, spread = 4 pips (27%) → SKIP
```

### Volume Confirmation
```
Sweep candle volume must be > 1.2x 20-period average
BOS candle volume must be > 1.0x average
IF volume low → treat as false breakout → SKIP
```

### Post-News Filter
```
IF high-impact event (NFP/FOMC/CPI) happened < 2 hours ago → SKIP
Markets need time to digest data before reliable setups form
```

### Session Windows (optimized per research)

| Asset | Best Window | Why |
|-------|------------|-----|
| EURUSD/GBPUSD (trend) | 09:00-11:00 EET | London momentum peak |
| EURUSD/GBPUSD (range) | 09:00-15:00 EET | Full London session oscillation |
| NAS100 IBB | 16:30-20:00 EET | NY open + follow-through |
| XAUUSD Gold NK | 15:30-18:30 EET | NY AM killzone for gold |
| BTC/SOL trend | 14:00-22:00 EET | US hours = highest crypto volume |
| BTC/SOL range | 24/7 (avoid NY open) | Mean reversion works outside events |

---

## 6. TRS v2.0 — STRATEGY-SPECIFIC SCORING

TRS is no longer one-size-fits-all. Each strategy has its own 5 criteria:

### TJR Asia Sweep TRS:
1. Daily bias clear (BULL/BEAR)
2. 4H aligned with daily
3. Asia sweep confirmed (price > PDH or < PDL by 3+ pips)
4. Volume on sweep > 1.2x avg
5. ADX > 25 + ADR < 85%

### IBB TRS:
1. IB range formed (16:30-17:30)
2. IB broken (price closed beyond IB H/L)
3. Time within window (17:30-20:00)
4. No high-impact news today
5. ADR < 85%

### Session H/L Fade TRS:
1. ADX < 20 (ranging confirmed)
2. Session H/L established (>30 pips range)
3. Price returned to session extreme (within 5 pips)
4. RSI(1H) showing reversal (>70 or <30)
5. Volume declining (not new breakout)

### Crypto Mean Reversion TRS:
1. ADX < 20
2. RSI(4H) < 30 or > 70
3. Price at Bollinger Band boundary
4. Volume spike on reversal candle
5. No major crypto news in last 4 hours

### Gold NY Killzone TRS:
1. Asian range identified (H/L)
2. NY session active (15:30-18:30 EET)
3. Sweep of Asian H/L confirmed
4. BOS after sweep (5min close)
5. No FOMC/USD data in ±2 hours

---

## 7. PERFORMANCE TRACKING (new)

### Weekly Review (automated, every Friday 22:00):
```
- Win rate by strategy (not just overall)
- Average R:R achieved vs planned
- Regime accuracy: how many days correctly identified as trending/ranging?
- Runner efficiency: % of runners that hit TP2 vs stopped at BE
- Cost analysis: estimated spread + slippage per trade
```

### Monthly Review:
```
- Strategy P&L breakdown
- Drawdown analysis (max consecutive losses, max peak-to-trough)
- Regime distribution: % trending vs ranging vs choppy days
- Recommendation: disable strategies with <0€ P&L after 20+ trades
```

---

## 8. EXPECTED PERFORMANCE

### Conservative Estimate (after costs):

| Strategy | Trades/week | WR | Avg €/trade | Weekly € |
|----------|------------|-----|-------------|----------|
| TJR (EUR/GBP) | 1-2 | 35% | +8€ | +8-16€ |
| IBB (NAS100) | 1-2 | 55% | +2€ | +2-4€ |
| Session Fade | 1-2 | 60% | +4€ | +4-8€ |
| Crypto MR | 0-1 | 60% | +3€ | +0-3€ |
| Gold NK | 0-1 | 45% | +5€ | +0-5€ |
| **TOTAL** | **4-8** | | | **+14-36€/week** |

### 6-Month Projection:
- Conservative: +14€/week × 26 weeks = **+364€** (1000→1364€)
- Moderate: +25€/week × 26 weeks = **+650€** (1000→1650€)
- Optimistic: +36€/week × 26 weeks = **+936€** (1000→1936€)

### vs Current System:
- Current backtest: +734€ over ~60 days BUT with 10% risk (unsustainable)
- v2.0 with 2% risk: slower growth BUT survivable drawdowns
- Key difference: v2.0 trades in ranging markets too (70% more opportunity)

---

## Files to Modify

| File | Change |
|------|--------|
| `prompts/ref_strategies.md` | REPLACE with v2.0 strategies |
| `prompts/ref_ladder.md` | REPLACE with quality-based ladder + ATR sizing |
| `prompts/ref_strategies_pilot.md` | RETIRE (strategies now either active or removed) |
| `prompts/adaptive_analyst.md` | Update regime-first flow, TRS v2.0, new filters |
| `scripts/trs_calculator.py` | Add strategy-specific TRS criteria |
| `scripts/quick_scan.py` | Add Bollinger Bands, session H/L detection |

## Sources

- [EURUSD Session H/L Strategy](https://tradethatswing.com/eurusd-session-high-low-day-trading-strategy/)
- [EUR/USD Volatility Analysis](https://tradethatswing.com/analyzing-eur-usd-volatility-for-day-trading-purposes/)
- [ORB Strategy Performance](https://tradethatswing.com/opening-range-breakout-strategy-up-400-this-year/)
- [IB Breakout Analysis](https://quantamentaltrader.substack.com/p/understanding-the-initial-balance)
- [Mean Reversion Crypto](https://3commas.io/mean-reversion-trading-bot)
- [Crypto Day Trading Strategies](https://www.kraken.com/learn/day-trading-strategies)
- [Gold SMC Trading Guide](https://acy.com/en/market-news/education/complete-stepbystep-guide-to-day-trading-gold-xauusd-with-smart-money-concepts-smc-j-o-161926/)
- [Gold Strategy 2026](https://www.thinkmarkets.com/en/trading-academy/commodities/gold-trading-strategy-2026/)
- [Smart Money Gold Kill Zones](https://www.tradingview.com/script/5zAdLu8t-Smart-Money-Gold-Map-XAUUSD-Kill-Zones-Liquidity-Sweeps/)
