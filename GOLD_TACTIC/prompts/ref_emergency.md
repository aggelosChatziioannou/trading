# Emergency News Activation — Reference

## Three-Gate Check (Ε1 → Ε2 → Ε3, all must pass)

### Ε1 — IMPACT ≥ 7/10 (Is this extraordinary?)
✅ PASS examples:
- Fed emergency rate decision (unscheduled)
- War escalation / geopolitical shock
- Exchange circuit breaker / trading halt
- Major earnings surprise (>10% gap)
- Central bank intervention in FX
- Sovereign default / credit event

❌ FAIL examples:
- Routine CPI / NFP / PMI releases (scheduled)
- Analyst rating upgrades/downgrades
- General market commentary
- Scheduled Fed speeches (no surprise)
- Crypto influencer posts

### Ε2 — ASSET MAPPING (Specific asset + clear direction?)
Requirements:
- Must name a specific tradeable ticker (not "markets broadly")
- Must write exactly 2 sentences: (1) direction, (2) catalyst
- If you cannot write these 2 sentences clearly → FAIL

Example PASS: "BTC likely to drop sharply. Bitcoin exchange Binance announced emergency halt of withdrawals."
Example FAIL: "Markets are nervous due to geopolitical tensions."

### Ε3 — WORTHWHILE NOW (Tradeable right now?)
- Forex: 24/5 (Mon 00:00 – Fri 22:00 EET)
- Crypto (BTC, SOL, ETH): 24/7
- Equities / NAS100: only during NY session (16:30–22:00 EET)
- **Weekend rule:** Forex and equities AUTOMATICALLY FAIL Ε3 on Sat/Sun
- ADR room remaining must be ≥ 30% (asset has not already run its range)

---

## Cap & Deduplication
- Maximum 2 emergency activations simultaneously
- If asset already activated: update `activated_at` + `headline`, do not create duplicate
- If cap reached: log in Telegram but do not activate

---

## Eligible Assets

### Core 5 (if scanner marked skip):
EURUSD, GBPUSD, NAS100, SOL, BTC

### Extended universe:
| Category | Assets |
|----------|--------|
| Metals | XAUUSD, XAGUSD |
| Crypto | ETH, BNB, XRP |
| Tech stocks | NVDA, AAPL, TSLA, MSFT, GOOGL, AMD, INTC, AMZN, META |
| Fintech/Crypto stocks | COIN, PLTR, MSTR |

Any asset explicitly named in a news headline with a clear, measurable price impact is eligible.

---

## Cleanup Logic (runs on each new Scanner timestamp)

| Condition | Action |
|-----------|--------|
| Asset now in Scanner's active_today | Remove from emergency (Scanner handles it) |
| Asset NOT in active_today AND open_trade=false | Remove (no longer relevant) |
| Asset NOT in active_today AND open_trade=true | Keep (must manage open trade) |
| NAS100 + nas100_afternoon=true + time < 16:30 EET | Keep (IB evaluation still pending) |

After cleanup: write `last_seen_scan_timestamp = current scan_timestamp`

---

## open_trade Lifecycle
- Trade opens on emergency asset → write `"open_trade": true` BEFORE sending Telegram
- Trade closes (TP/SL/EOD) → write `"open_trade": false` BEFORE sending Telegram
