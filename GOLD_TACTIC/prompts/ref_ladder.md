# Ladder Risk System v4.0 — Reference

## Risk Parameters
- Fixed risk: 100 EUR per trade
- Max concurrent open trades: 3
- Max daily loss: 200 EUR → STOP all trading for the day
- Lot formula: `Lot = 100 / (SL_pips × pip_value)`

## 33/33/33 Split
| Step   | R:R | Action          | P&L   | SL after         |
|--------|-----|-----------------|-------|------------------|
| TP1    | 1:1 | Close 33%       | +33€  | → Entry (BE)     |
| TP2    | 1:2 | Close 33%       | +66€  | → TP1 (+33€)     |
| Runner | ∞   | Trail 33%       | +33€+ | Trailing 1x risk |

## SL Movement Rules
- Before TP1: SL stays at original level — never move back
- After TP1 hit: move SL → Entry immediately (zero risk)
- After TP2 hit: move SL → TP1 level (33€ locked)
- Runner: trail = current_price − 1x_risk_distance. Only move forward, never back.

## P&L Scenarios (100€ risk)
- SL hit full: −100€
- TP1 only: +33€
- TP1 + TP2: +99€
- Full run 3x: +132€
- Full run 5x: +199€

## Entry Calculation
```
SL_distance = Asia High − Asia Low (pips)
TP1 = Entry ± 1× SL_distance
TP2 = Entry ± 2× SL_distance
Initial SL = Entry ∓ SL_distance
```

## EOD Rule
Last cycle ~21:40 EET: if open trade AND TP1 not hit → close at market.
If TP1 was already hit → runner may stay overnight (trader judgement).
