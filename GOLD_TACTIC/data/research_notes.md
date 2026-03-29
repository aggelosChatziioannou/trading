# GOLD TACTIC - Research Notes

## TJR Strategy Research

### Core TJR Model: Asia Session Sweep
- Source: TJR Trades (Tyler J. Riches), 7-figure trader
- Website: jointjrtrades.com
- Bootcamp on Whop platform

### TJR Entry Process (Multi-Timeframe)
1. Mark key levels on 1H/4H (PDH/PDL, session H/L, equal H/L)
2. Wait for price to hit key level
3. Scale to 5min: wait for BOS/CHOCH, iFVG, SMT confirmation
4. Wait for 5min retrace into OB/BB/EQ/FVG
5. Drop to 1min for precise entry (BOS/CHOCH + iFVG)
6. SL where trade idea invalidated
7. TP at opposite key levels

### TJR Daily Bias (3 Profiles)
- Profile A: Asia=Consolidation, London=Manipulation, NY=Reversal
- Profile B: London=Manipulation, NY=Reversal->Continuation
- Profile C: London=Manipulation+Reversal, NY=Continuation

### TJR Backtest (Scribd)
- Starting: 100 units, 1% risk/trade
- Final P&L: +17.36%
- Max balance: 119.33
- Min balance: 108.85

### TJR TradingView Implementations
- "TJR Trades Strategy" by gabegab1 - automates Asia sweep + MSS
- "TJR SEEK AND DESTROY" by SwiftEdge - OB, FVG, BOS during US hours
- "TJR-Style Sessions" by POVLiquidity - session H/L + bias table
- "TJR Asia Session Sweep" by Leonardoxfrr - full strategy

## Gold-Specific Research

### Average Daily Range (ADR)
- 2024-2025 typical: $30-$45 (300-450 pips)
- 90% Rule: When 90%+ of ADR consumed, avoid new trades
- London/NY overlap completes 70-80% of daily ADR

### ADR-Based Risk Management
- SL formula: 0.15 x ADR
- TP1: 75% of ADR (high probability)
- TP2: 90% of ADR (exhaustion zone)

### Session Kill Zones (EST)
- Asia: 7:00 PM - 2:00 AM (consolidation, range)
- London KZ: 2:00 AM - 5:00 AM (manipulation, Judas Swing)
- NY KZ: 7:00 AM - 10:00 AM (continuation/reversal)
- London-NY Overlap: 8:00 AM - 12:00 PM (PEAK volatility)

### Gold Sweep Characteristics
- Deep sweeps: 10-20 pips ($1-$2) past obvious levels
- Stops need 20-30 pip buffer beyond structure
- Position sizing 30-50% smaller than forex pairs

### Gold-DXY Correlation
- Inverse relationship: strong USD = weak gold
- Peak reliability: London-NY overlap
- When both rise = decoupling event (extreme fear)
- US Treasury yields more reliable than DXY alone

### Backtested Strategy Results (Independent)
| Strategy | WR | PF | Trades | Period |
|----------|-----|------|--------|--------|
| Pullback Window (EMA) | 55.4% | 1.64 | 175 | 5 years |
| Initial Balance Breakout | ~50% | ~1.8 | 1/day | 1 year |
| Gold Breakout (Donchian) | 40.4% | 1.85 | 104 | 28 years |
| ICT Silver Bullet (filtered) | 72-83% | 2.5+ | 1-3/day | unverified |

### Gold-Bot Existing Performance (for reference)
- PF 1.72, WR 49.6%, Sharpe 1.93
- 129 trades over 6 months
- OTE entry at 70.5% fib: +1.8% PF improvement
- Trailing stop after TP1: +9.8% PF improvement
- Confluence min 5: +10.1% PF improvement

## Sources
- https://www.scribd.com/document/851903802/TJR-STRAT
- https://www.scribd.com/document/974337900/TJR-Daily-Bias-Trading-Guide
- https://www.scribd.com/document/923956853/TJR-Strategy-backtested
- https://www.scribd.com/document/916439470/TJR-Liquidity-Sweep-Strategy
- https://www.tradingview.com/script/M6EyQhlQ-TJR-Trades-Strategy/
- https://www.tradingview.com/script/9yqF7p26-TJR-SEEK-AND-DESTROY/
- https://www.tradingview.com/script/jJiF9kgr-TJR-Style-Sessions/
- https://www.tradingview.com/script/i5ANdaSG/ (TJR Asia Session Sweep)
- https://coconote.app/notes/12bb34cc-95bf-4878-a877-852abf81eb56
- https://www.jointjrtrades.com/philosophy
- https://www.oreateai.com/blog/unlocking-the-tjr-trading-strategy
- https://github.com/ilahuerta-IA/backtrader-pullback-window-xauusd
- https://fxnx.com/en/blog/trading-xauusd-adr
- https://fxnx.com/en/blog/ict-power-3-xauusd-master-midnight-pivot
