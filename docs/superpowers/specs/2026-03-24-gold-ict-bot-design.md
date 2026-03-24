# Gold (XAUUSD) ICT Trading Bot — Design Spec

## Overview

A rules-based Gold day trading bot implementing ICT/Smart Money Concepts. Completely separate system from the existing stock trading bot. Lives in `gold-bot/` at the repo root.

## Architecture

```
gold-bot/
├── config/
│   ├── settings.py          # Sessions, risk params, spread/commission
│   └── news_calendar.py     # CPI/PPI/FOMC/NFP blackout dates
├── data/
│   ├── downloader.py        # Download XAUUSD + DXY multi-timeframe
│   └── manager.py           # Multi-TF data alignment & caching
├── ict/
│   ├── structures.py        # Swing highs/lows, BOS detection
│   ├── liquidity.py         # Session highs/lows, equal H/L, liquidity pools
│   ├── fvg.py               # Fair Value Gaps (+ Inversion FVG)
│   ├── order_blocks.py      # OB, Breaker Blocks
│   ├── smt.py               # SMT divergence (Gold vs DXY)
│   └── equilibrium.py       # 50% retracement of impulse moves
├── strategy/
│   ├── entry_model.py       # Multi-TF entry logic (HTF→5m→1m)
│   ├── session_filter.py    # London/NY killzone time filter
│   └── signal.py            # Signal dataclass
├── risk/
│   ├── position_sizer.py    # 1% risk per trade, leverage calc
│   └── manager.py           # Max trades/day, daily loss limit, TP1/2/3
├── backtest/
│   ├── engine.py            # Event-driven bar-by-bar backtester
│   ├── metrics.py           # Sharpe, PF, drawdown, R:R, session stats
│   └── report.py            # Equity curve, monthly P&L, Excel export
├── main.py                  # CLI entry point
├── requirements.txt         # Dependencies
└── tests/
    ├── test_structures.py   # Test swing detection, BOS
    ├── test_fvg.py          # Test FVG detection
    ├── test_order_blocks.py # Test OB detection
    └── test_backtest.py     # Integration test
```

## ICT Concepts Implementation

### 1. Market Structure (structures.py)
- **Swing Detection**: Identify swing highs/lows using N-bar lookback (default N=5)
- **BOS (Break of Structure)**: Higher high in uptrend = bullish BOS, lower low in downtrend = bearish BOS
- **Market Structure Shift (MSS)**: When BOS occurs against the prevailing trend

### 2. Liquidity (liquidity.py)
- **Session Highs/Lows**: Track Asian, London, NY session extremes
- **1H/4H Highs/Lows**: Rolling window of recent 1H and 4H swing points
- **Equal Highs/Lows**: Detect price levels where 2+ swing points cluster (within tolerance)
- **Liquidity Sweep**: Price takes out a liquidity level then reverses (wick beyond level, close back inside)

### 3. Fair Value Gaps (fvg.py)
- **Bullish FVG**: candle[i-2].high < candle[i].low (gap between candle 1 and 3)
- **Bearish FVG**: candle[i-2].low > candle[i].high
- **IFVG (Inversion FVG)**: A previously bearish FVG that gets filled and now acts as support (or vice versa)
- Track unfilled FVGs as potential entry zones
- FVGs expire after N bars (configurable, default 50)

### 4. Order Blocks (order_blocks.py)
- **Bullish OB**: Last bearish candle before a bullish impulse move (impulse = move that creates BOS)
- **Bearish OB**: Last bullish candle before a bearish impulse move
- **Breaker Block**: A broken OB that now acts as S/R in the opposite direction
- OB zone = [low, high] of the candle body

### 5. SMT Divergence (smt.py)
- Compare Gold swing points vs DXY swing points
- Bullish SMT: Gold makes lower low but DXY doesn't make higher high
- Bearish SMT: Gold makes higher high but DXY doesn't make lower low
- Requires synchronized timestamps between Gold and DXY data

### 6. Equilibrium (equilibrium.py)
- 50% retracement level of the most recent impulse move
- Impulse = the move from the swing point that caused BOS to the BOS point itself

## Entry Model (entry_model.py)

Sequential gate system — ALL must pass:

```
Gate 1: SESSION FILTER
  → Is current time within London (3:00-4:00 AM EST) or NY (9:50-10:30 AM EST)?
  → If no → SKIP

Gate 2: NEWS FILTER
  → Is today a CPI/PPI/FOMC/NFP day?
  → If yes → SKIP entire day

Gate 3: HTF LIQUIDITY SWEEP
  → Has price swept a 1H/4H liquidity level in the current session?
  → Check: price wick beyond level + close back inside
  → If no → WAIT

Gate 4: 5-MIN BOS
  → After the sweep, has there been a BOS on the 5-min chart?
  → Direction must be OPPOSITE to the sweep (sweep longs → bearish BOS → short setup)
  → If no → WAIT

Gate 5: 5-MIN ENTRY ZONE
  → Is there a valid entry zone? Check in priority order:
    1. FVG in the direction of the BOS
    2. OB (last opposing candle before the BOS impulse)
    3. Breaker Block
    4. Equilibrium of the impulse
  → If no → WAIT

Gate 6 (OPTIONAL): 1-MIN CONFIRMATION
  → BOS on 1-min within the 5-min entry zone
  → IFVG on 1-min for precision

ENTRY:
  → Enter at the entry zone level
  → SL below/above the entry zone structure
  → TP at the next opposing HTF liquidity level
```

## Risk Management

```python
RISK_PER_TRADE = 0.01      # 1% of capital
MAX_TRADES_PER_DAY = 2
MAX_DAILY_LOSS = 0.02      # 2% of capital
LEVERAGE = 3
SPREAD = 0.30              # $0.30 for XAUUSD
COMMISSION = 5.0           # $5 per lot round trip

# Multi-TP system
TP1_RATIO = 1.0            # 1:1 R:R, close 50%
TP2_RATIO = 2.0            # 2:1 R:R, close 30%
TP3_TARGET = "next_level"  # Trail 20% to next key level
# After TP1 hit → move SL to breakeven
```

## Backtest Engine (engine.py)

Event-driven, bar-by-bar processing:

1. Load multi-TF data (1m, 5m, 1H, 4H)
2. Iterate through 5-min bars chronologically
3. At each bar:
   - Update HTF context (which 1H/4H bar are we in?)
   - Update ICT structures (new swings, FVGs, OBs, etc.)
   - Run entry model gates
   - Manage open positions (check SL/TP hits using 1-min data for accuracy)
4. Use 1-min data within each 5-min bar for precise SL/TP execution
5. Apply spread on entry, commission on round trip

## Data Strategy

### Primary: yfinance
- `GC=F` (Gold Futures) — proxy for XAUUSD
- `DX-Y.NYB` (Dollar Index) — for SMT divergence
- Limitation: yfinance only provides ~7 days of intraday data at 1-min resolution

### CSV Import System
- Support importing CSV data from MT5, TradingView, or other sources
- Expected format: datetime, open, high, low, close, volume
- This enables 6+ month backtests with sub-hourly data

### Timeframe Construction
- Store base data at 1-min resolution
- Construct 5-min, 1H, 4H candles by resampling
- Ensures perfect alignment across timeframes

## Output Deliverables

1. **Equity curve** — matplotlib chart saved as PNG
2. **Monthly P&L breakdown** — table in console + saved to report
3. **Key metrics**: Win rate, Profit Factor, Sharpe ratio, Max Drawdown, Avg R:R
4. **Session comparison**: London vs NY performance breakdown
5. **Trade log**: Excel file (.xlsx) with all trades, entry/exit times, R:R, TP level hit
6. **Weekly stats**: Average trades per week
7. **TP hit rates**: TP1/TP2/TP3 individual hit percentages

## Dependencies

- pandas, numpy — data handling
- yfinance — data download
- matplotlib — charting
- openpyxl — Excel export
- pytz — timezone handling

## Starting Capital & Backtest Config

- Capital: $500
- Period: 6 months out-of-sample
- Spread: $0.30
- Commission: $5/lot round trip
- Slippage: simulated 1 pip
