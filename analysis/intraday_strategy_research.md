# Intraday/Day Trading Strategy Research for Automation
## Compiled: 2026-03-21 | Evidence-Based Findings

---

## 1. Best Intraday Strategies for Automation

### 1.1 Opening Range Breakout (ORB)

**How it works:** Define the high and low of the first N minutes after market open (5, 15, or 30 min). Enter long when price closes above the range high; enter short when price closes below the range low.

**Backtested results:**
- Edgeful ORB (5-min candle close outside 15-min range): **74.56% win rate**, profit factor 2.512, 114 trades, max drawdown ~12%
- 60-minute ORB on 0DTE options: **89.4% win rate**, profit factor 1.44, nearly 3x higher P/L vs 15/30-min ranges
- QuantConnect study on "stocks in play" (abnormally high volume): **2.4 Sharpe ratio**, beta close to zero

**Best timeframes:**
- **5-min range**: More signals, more false breakouts. Best for fast scalpers.
- **15-min range**: Sweet spot for most day traders. Filters initial noise.
- **30-min range**: Most conservative. More reliable but fewer opportunities.

**Key filters to add:**
- VWAP alignment (price above VWAP for longs, below for shorts)
- Relative Volume (RVOL) > 1.5x on breakout bar
- Candle strength: close in upper/lower 30% of bar range
- ATR-based stops (stop inside the range, target = range height)

**Automation difficulty:** LOW - Very rule-based, easy to code.

---

### 1.2 VWAP Trading Strategies

**Core concept:** VWAP = Volume Weighted Average Price. Institutional traders view it as "fair value" for the day. Price above VWAP = bullish bias; below = bearish.

**Key strategies:**
1. **VWAP Bounce (Mean Reversion):** Buy at VWAP when price pulls back in an uptrend; sell at VWAP in a downtrend. Best during first 2 hours after open.
2. **VWAP Breakout:** Enter when price decisively breaks through VWAP with volume confirmation. Signals shift in intraday sentiment.
3. **VWAP + ORB Combo:** Only take ORB longs when price is above VWAP; only take shorts when below.

**Best conditions:** First 2 hours of trading when institutional order flow is highest. Loses effectiveness in the afternoon when volume drops.

**Automation difficulty:** LOW - VWAP is a standard indicator on all platforms.

---

### 1.3 ICT / Smart Money Concepts (SMC)

**Key components:**
- **Order Blocks (OB):** Candles where institutional orders were placed. Act as future support/resistance.
- **Fair Value Gaps (FVG):** 3-candle pattern showing market imbalance. FVGs fill ~70% of the time.
- **Break of Structure (BOS):** Higher high/higher low sequence breaks = trend change signal.
- **Liquidity Sweeps:** Price raids above/below obvious swing points to trigger stops before reversing.

**Backtest results (2,600 trades across 10 assets, Jan 2024 - Mar 2026):**
- **61% win rate**, profit factor 2.17, +2.27R average return
- Tested on Gold, BTC, ETH, EUR/USD, GBP/USD, NAS100, SOL, USD/JPY, SPX500, XRP
- Note: Study by a commercial indicator creator - interpret with caution

**Automation tools:**
- Python: `smart-money-concepts` package on GitHub (github.com/joshyattridge/smart-money-concepts)
- TradingView: FluxCharts ICT indicators with built-in backtesting
- TrendSpider: Automated FVG/IFVG detection with alerts

**Automation difficulty:** HIGH - Requires multi-timeframe context analysis. Partial automation possible (detect OBs/FVGs mechanically), but full discretionary context is hard to replicate.

---

### 1.4 Session-Based Trading

**Session times (all EST):**

| Session | Time (EST) | Kill Zone (EST) | Character |
|---------|-----------|-----------------|-----------|
| Asian | 8 PM - 4 AM | 7 PM - 10 PM | Range-bound, low liquidity |
| London | 3 AM - 11 AM | 2 AM - 5 AM | Sets daily trend, highest probability of large move |
| New York | 8 AM - 4 PM | 7 AM - 10 AM | Most volatile, overlap with London |
| London Close | 11 AM - 12 PM | - | Continuation or reversal point |

**Key insight:** The London-New York overlap (8 AM - 12 PM EST) generates **70% of daily trading volume** for major pairs.

**Dead zones to avoid:**
- NY close to Tokyo open (very quiet)
- European lunch: 7-8 AM EST
- US lunch: 11:30 AM - 1:30 PM EST

**Automation approach:** Time-based filters that only allow trades during kill zones. Simple to implement.

---

### 1.5 Mean Reversion on Intraday Timeframes

**How it works:** Identify when price has stretched too far from a mean (VWAP, 20-50 SMA, Bollinger Bands) and trade the snap-back.

**Best setup (RSI + Bollinger Bands):**
- Long: RSI < 30 AND price touches lower Bollinger Band AND bullish reversal candle
- Short: RSI > 70 AND price touches upper Bollinger Band AND bearish reversal candle
- Stop loss: 3 standard deviations from mean
- Target 1: The mean (moving average). Target 2: Opposite band.

**Key findings:**
- High win rate strategy (many small wins)
- Occasional large losses when trend overrides mean reversion
- Works best in **sideways/ranging markets**, fails in strong trends
- 4H and daily charts give cleaner signals than 1-min/5-min
- Major forex pairs and large-cap indices are best; thin crypto altcoins and news-driven small caps trend too much

**Critical risk:** Cutting winners short, letting losers run. Need hard stops.

**Automation difficulty:** MEDIUM - Rules are clear but need market regime detection (trending vs. ranging) to avoid losses.

---

### 1.6 EMA Crossover Scalping (1-min / 5-min)

**Setup:** 9 EMA crosses above 21 EMA = long; 9 EMA crosses below 21 EMA = short.

**Harsh reality from backtests:**
- S&P 500 (1960-2025): Basic MA crossover systems produce **57-76% false signal rate**
- Standalone EMA crossover is NOT profitable without additional filters
- Ed Seykota's guideline: Slow EMA should be >= 3x the fast EMA (so 9/27 is better than 9/21)

**Required enhancements for profitability:**
- ADX filter (only trade when ADX > 20-25, confirming trend strength)
- RSI confirmation (avoid overbought longs, oversold shorts)
- Volume filter (higher volume on crossover bar)
- Wait for candle CLOSE before entering (mid-candle crossovers often reverse)
- Higher timeframe trend alignment (only trade 1-min longs when 15-min is also bullish)

**Risk management:** 0.7% stop loss, minimum 1:2 risk-reward ratio.

**Automation difficulty:** LOW to code, but profitability requires extensive filter tuning per asset.

---

## 2. Asset Selection by Strategy

### 2.1 Best Stocks for ORB

**Selection criteria:**
| Filter | Recommended Setting |
|--------|-------------------|
| Minimum Price | > $5-$10 |
| Average Daily Volume | > 500,000 shares |
| Relative Volume (RVOL) | > 1.5x normal on breakout |
| Beta | > 1.0 |
| ATR | > $0.50 |
| Catalyst | Earnings, news, SEC filings |

**"Stocks in Play" method:** Each morning, identify the 20 stocks with the highest ratio of (current first-5-min volume) / (average first-5-min volume over prior 14 days). These have abnormally high institutional participation.

**Screening tools:** TradingView high-beta screener, Yahoo Finance highest-beta stocks page, pre-market scanners (Trade Ideas, Benzinga).

### 2.2 Best Crypto for Session Trading

| Pair | Daily Volume | Character | Best For |
|------|-------------|-----------|----------|
| BTC/USDT | ~$47B | Deepest liquidity, smoothest execution | All strategies, safest for automation |
| ETH/USDT | ~$20B | 3-5% daily swings, good liquidity | Balanced volatility/liquidity |
| SOL/USDT | ~$5B | High beta, double-digit weekly volatility | Momentum/breakout strategies |

**Peak crypto session:** 13:00-17:00 UTC (London-NY overlap) for maximum volume.

**Position sizing warning:** Crypto volatility is 5-10x higher than forex. Reduce position sizes proportionally.

### 2.3 Strategy-Asset Matching

| Strategy | Best Assets | Avoid |
|----------|------------|-------|
| ORB | High-RVOL stocks with catalysts, ES/NQ futures | Low-volume stocks, crypto (no defined open) |
| VWAP | Large-cap stocks, ES/NQ futures | Assets without institutional participation |
| ICT/SMC | BTC, ETH, Gold, NAS100, EUR/USD, GBP/USD | Low-liquidity altcoins |
| Session Trading | Forex majors, BTC, ETH, SOL | Stocks (only one session) |
| Mean Reversion | Large-cap indices, major forex pairs | Small caps, news-driven stocks, thin altcoins |
| EMA Scalping | Liquid futures (ES, NQ), major forex | Low-volume stocks, wide-spread instruments |

---

## 3. News Filtering for Day Trading

### 3.1 Highest-Impact Events (Must Filter)

**Tier 1 (Market-Moving):**
1. **FOMC Rate Decisions** - 8 times/year, 2:00 PM EST. Biggest single-event volatility.
2. **Non-Farm Payrolls (NFP)** - First Friday of each month, 8:30 AM EST.
3. **CPI (Consumer Price Index)** - Monthly, 8:30 AM EST. Inflation data = rate hike speculation.

**Tier 2 (Significant):**
- PPI (Producer Price Index)
- GDP releases
- Unemployment Claims (weekly)
- FOMC Meeting Minutes (released 3 weeks after each meeting)
- Earnings reports (for individual stocks)

**Tier 3 (Moderate):**
- ISM Manufacturing/Services PMI
- Retail Sales
- Fed Chair speeches
- Consumer Confidence

### 3.2 Buffer Times Around News

| Approach | Before Event | After Event |
|----------|-------------|-------------|
| Minimum (prop firms) | 1 minute | 1 minute |
| Conservative | 2 minutes | 2 minutes |
| Professional recommendation | 5-15 minutes | 5-15 minutes |
| Safest approach | 30 minutes | 30-90 minutes |

**Key data point:** FOMC day is ~23% more volatile than average. The day AFTER FOMC is also significantly more volatile (1.6% SPX move vs 1.3% average).

**Implementation:** Block new entries during [event_time - buffer, event_time + buffer]. Never block trailing stops, break-even logic, or exits.

### 3.3 Best Economic Calendar APIs

| API | Free Tier | Best For | Key Feature |
|-----|----------|----------|-------------|
| Trading Economics | Limited | Most comprehensive (196 countries) | Importance field (1-3 scale) |
| Finnhub | Yes | Algo traders | Free, clean JSON |
| FXStreet | Limited | Forex traders | AI-powered Fedspeak analysis |
| Financial Modeling Prep | Yes | Stock traders | Broad financial data |
| MT5 Native Calendar | Free (in MT5) | MetaTrader users | Synced with broker server |

**Free non-API options:** TradingView economic calendar, Investing.com calendar, ForexFactory calendar.

---

## 4. Realistic Daily Returns

### 4.1 What the Evidence Shows

**Annual returns:**
- Realistic target for disciplined automated systems: **10-20% annually**
- Exceptional systems: 30-50% annually (with higher drawdown risk)
- The ORB backtest showing 170-400% is an outlier year, not sustainable long-term

**The hard truth:** Only ~4% of day traders make consistent profits. Automation improves consistency but does not guarantee profits.

### 4.2 Win Rate vs Risk-Reward Matrix

| Win Rate | R:R Ratio | Outcome (10 trades, $100 risk each) |
|----------|----------|--------------------------------------|
| 50% | 1:1 | Break even (-fees) |
| 50% | 1:2 | +$500 profit |
| 40% | 1:2 | +$200 profit |
| 33% | 1:5 | +$650 profit |
| 60% | 1:2.5 | +$900 profit |
| 75% | 1:1 | +$500 profit |

**Key insight:** Win rate alone is meaningless. A 33% win rate with 1:5 R:R beats a 75% win rate with 1:1 R:R.

### 4.3 Small Account Expectations ($1,000-$5,000)

**Risk per trade:** 1% of account (max 2%)
- $1,000 account: Risk $10-$20 per trade
- $5,000 account: Risk $50-$100 per trade

**Realistic monthly P&L (assuming 20 trading days, 1-3 trades/day):**

| Account Size | Monthly Target (5-10%) | Daily Average |
|-------------|----------------------|---------------|
| $1,000 | $50-$100 | $2.50-$5.00 |
| $2,500 | $125-$250 | $6.25-$12.50 |
| $5,000 | $250-$500 | $12.50-$25.00 |

**Commission impact warning:** At $1,000 account size, commission/spread costs can eat 20-40% of profits. Consider futures micro contracts or commission-free platforms.

**Compounding example (10% monthly, starting $5,000):**
- Month 6: ~$8,857
- Month 12: ~$15,692
- Month 24: ~$49,268
- (Assumes consistent 10% monthly which is optimistic but possible in good conditions)

---

## 5. Best Times to Trade

### 5.1 Stocks / Indices (EST)

| Time Window | Quality | Notes |
|------------|---------|-------|
| **9:30-10:30 AM** | BEST | Opening volatility, highest volume, ORB setups |
| **10:30-11:30 AM** | GOOD | Trends establish, follow-through moves |
| 11:30 AM-1:30 PM | POOR | Lunch doldrums, choppy, low volume |
| **1:30-3:00 PM** | MODERATE | Afternoon continuation or reversal |
| **3:00-4:00 PM** | GOOD | Power hour, institutional rebalancing |

### 5.2 Forex (EST)

| Time Window | Quality | Notes |
|------------|---------|-------|
| 2:00-5:00 AM | GOOD | London Kill Zone, sets daily direction |
| **8:00 AM-12:00 PM** | BEST | London-NY overlap, 70% of daily volume |
| 12:00-3:00 PM | MODERATE | NY session continues |
| 7:00-10:00 PM | MODERATE | Asian Kill Zone, range strategies |

### 5.3 Crypto (EST/UTC)

| Time Window (EST) | Quality | Notes |
|-------------------|---------|-------|
| **8:00 AM-12:00 PM** | BEST | Overlap with US + EU markets, peak volume |
| 3:00-5:00 AM | GOOD | London open creates breakout from Asian range |
| 8:00-10:00 PM | MODERATE | Asian session, can see unexpected moves due to low liquidity |

---

## 6. Candlestick Pattern Recognition

### 6.1 What Actually Works (Backtested)

**Overall finding from backtest of 23 patterns (25 years of data):**
- Only 12 patterns had profit factor > 1.5
- Best 12 combined: 975 trades, **12.89% CAGR**, 0.36% avg gain, max drawdown 25%, profit factor 2.02
- Beat buy-and-hold (9.9%) over same period

### 6.2 Individual Pattern Performance

**Engulfing Patterns:**
- Counterintuitive: Bearish Engulfing actually performed as one of the best BULLISH signals (75.76% win rate, 2.73 profit factor when traded long on ES futures)
- Bullish Engulfing: 68% win rate on BTC 4H, but only 42% on EUR/USD 15m
- Effectiveness varies wildly by instrument and timeframe

**Pin Bars / Hammers / Shooting Stars:**
- Work best with additional confirmation (RSI divergence, support/resistance levels)
- Standalone pin bars produce too many false signals
- Adding RSI filter can improve win rate by 10-15%

**Doji at Support/Resistance:**
- Represents indecision; in a trend = pause (continuation likely); at S/R = potential reversal
- On AAPL: 97 trades generated, but quantity did not equal quality
- Needs context (where in the trend, at what level) to be useful

**Inside Bars:**
- Signify consolidation, setup for breakout
- Best used as entry triggers when aligned with higher-timeframe direction
- Trade the breakout of the inside bar range with stop on the other side

### 6.3 Key Takeaways on Candlesticks

1. **No pattern works universally** - must backtest per asset and timeframe
2. **Daily timeframes are far more reliable** than intraday for candlestick signals
3. **Volume confirmation improves win rates by 10-15%** across all patterns
4. **Context > Pattern**: A pattern at a key level with volume confirmation is completely different from the same pattern in no-man's-land
5. **Counterintuitive results are common**: Always backtest, never assume a "bearish" pattern is bearish
6. Academic literature is divided: Some studies show predictive power, others show none. The difference is usually whether filters and context were applied.

---

## 7. Strategy Ranking for Automation (Summary)

| Strategy | Ease of Automation | Expected Edge | Recommended Priority |
|----------|-------------------|---------------|---------------------|
| ORB (15-min) | Easy | High (backtested) | **#1 - Start here** |
| VWAP Bounce/Break | Easy | Medium-High | **#2** |
| Session-based filtering | Easy (time filter) | Medium (enhances other strategies) | **#3 - Add to all strategies** |
| Mean Reversion (RSI+BB) | Medium | Medium (high WR, risky tails) | **#4** |
| ICT/SMC (FVG + OB) | Hard | Potentially high | **#5 - Partial automation** |
| EMA Crossover Scalping | Easy to code, hard to profit | Low standalone | **#6 - Only with heavy filtering** |

---

## 8. Implementation Recommendations

1. **Start with ORB + VWAP + Session Filter** as a combined system
2. **Always include a news filter** using Finnhub or Trading Economics API
3. **Backtest on at least 200 trades** across different months before going live
4. **Risk 1% per trade maximum** on small accounts
5. **Focus on 2-3 liquid assets** rather than scanning hundreds
6. **Use walk-forward optimization** (build on one period, verify on another) to avoid overfitting
7. **Account for costs**: Spread, slippage, commissions. A strategy profitable in backtest can be unprofitable after costs on small accounts.
8. **Paper trade for at least 1 month** before risking real capital
