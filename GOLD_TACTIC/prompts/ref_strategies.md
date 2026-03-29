# Trading Strategies Reference

## Core Assets
| Asset   | Strategy                          | Backtest |
|---------|-----------------------------------|----------|
| EURUSD  | TJR Asia Sweep                    | +23.8%   |
| GBPUSD  | TJR Asia Sweep                    | +21.5%   |
| NAS100  | IBB Initial Balance Breakout      | +13.7%   |
| SOL     | TJR + Counter-trend (RSI<25)      | +8.4%    |
| BTC     | TJR + Counter-trend (RSI<25)      | +6.4%    |

---

## TJR Asia Sweep (EURUSD, GBPUSD, SOL, BTC)

**Setup conditions (all required):**
1. Daily bias is clear (bull or bear)
2. 4H bias aligned with Daily
3. Asia session formed a clear range (H + L identifiable)
4. Price sweeps either the Asia High (bear setup) or Asia Low (bull setup)
5. After the sweep: BOS (Break of Structure) confirms new direction
6. ADR remaining ≥ 10% (room to move after entry)

**Entry:** On the BOS candle close, or on retracement to BOS level
**SL:** Behind the swept extreme (Asia H or L)
**Bias filter:** Do not trade against Daily bias unless Counter-trend exception applies

**RSI filter:** RSI 25–75. Outside this range → skip unless Counter-trend exception.

---

## IBB — Initial Balance Breakout (NAS100 only)

**Initial Balance definition:**
- IB High = highest price during 16:30–17:30 EET 🇬🇷 (first NY hour)
- IB Low = lowest price during 16:30–17:30 EET 🇬🇷

**Trade window:** 16:30–22:00 EET 🇬🇷 (NY session)

**Setup conditions:**
1. Daily bias is clear
2. Price breaks above IB High (long) or below IB Low (short)
3. After breakout: wait for retracement back toward IB level
4. Entry on retracement, SL behind IB level

**Do not trade:**
- Inside IB range (wait for breakout)
- After 22:00 EET (session close)
- On FOMC/NFP/CPI days (skip entirely)

---

## Counter-trend Exception (SOL, BTC only)

**Conditions (all required):**
- Daily RSI < 25 (deeply oversold)
- Price has swept recent lows (liquidity grab)
- BOS to the upside confirms buyers stepping in

**Trade parameters:**
- Direction: LONG only
- Risk: 100€ as usual
- Targets: TP1 only (1:1 R:R) — no TP2, no runner
- Rationale: counter-trend = take quick profit, do not overstay

**Note:** This overrides the usual Daily bias alignment requirement.
