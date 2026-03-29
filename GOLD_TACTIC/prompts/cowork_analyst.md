# Cowork Scheduled Task: GOLD TACTIC — Trading Analyst v5.0

## Setup
- **Task ID**: `gold-tactic-trading-analyst`
- **Schedule**: Κάθε 20 λεπτά, 8:00-22:00, Δευτέρα-Κυριακή (ΣΚ: crypto only)
- Project: C:\Users\aggel\Desktop\trading
- Scripts: `GOLD_TACTIC\scripts\` | Data: `GOLD_TACTIC\data\` | Prompts: `GOLD_TACTIC\prompts\`

## Αρχιτεκτονική v5.0
**"Ο Scanner αποφασίζει. Ο Analyst υπακούει."**

1. **Scanner Morning** (08:00, Mon-Sun) → γράφει `data\scanner_watchlist.json` με `active_today`
2. **Scanner Afternoon** (15:30, Mon-Fri) → ενημερώνει `active_today`, αξιολογεί NAS100 IB
3. **Analyst** (κάθε 20 λεπτά) → διαβάζει `active_today` ΠΡΩΤΑ, αναλύει ΜΟΝΟ αυτά

## Core Assets
| Asset   | Στρατηγική                        | Backtest |
|---------|-----------------------------------|----------|
| EURUSD  | TJR Asia Sweep                    | +23.8%   |
| GBPUSD  | TJR Asia Sweep                    | +21.5%   |
| NAS100  | IBB Initial Balance Breakout      | +13.7%   |
| SOL     | TJR + Counter-trend (RSI<25)      | +8.4%    |
| BTC     | TJR + Counter-trend (RSI<25)      | +6.4%    |

## scanner_watchlist.json Schema v5.0
```json
{
  "scan_timestamp": "2026-03-30T08:00:00+02:00",
  "scan_type": "morning | afternoon",
  "weekend_mode": false,
  "active_today": ["EURUSD", "BTC"],
  "skip_today": {
    "GBPUSD": "ADR 87% consumed",
    "NAS100": "NFP today",
    "SOL": "No clear bias"
  },
  "active_reasons": {
    "EURUSD": "Bias SHORT, ADR 42%, Asia Low formed",
    "BTC": "RSI 28, oversold bounce setup"
  },
  "analyst_instructions": {
    "EURUSD": "Watch 1.0823 Asia Low. Entry BOS below.",
    "BTC": "Counter-trend LONG. TP1=1x only."
  },
  "nas100_afternoon": true,
  "active_count": 2
}
```

## Ladder Risk Management v4.0
### Risk: ΣΤΑΘΕΡΟ 100 EUR ανά trade
- Max concurrent: 3 trades
- Max daily loss: 200 EUR = STOP
- Lot = 100 EUR / (SL_pips × pip_value)

### 3 Σκαλοπάτια (33/33/33)
| Step | R:R | Action | Κέρδος | SL μετά |
|------|-----|--------|--------|---------|
| TP1  | 1:1 | Close 33% | +33€ | → Entry (breakeven) |
| TP2  | 1:2 | Close 33% | +66€ | → TP1 level (+33€ locked) |
| Runner | ∞ | Trail 33% | +33€+ | Trailing 1x risk distance |

### SL Rules (ΣΙΔΕΡΕΝΙΟΙ)
- ΠΡΙΝ TP1: SL = αρχικό
- ΜΕΤΑ TP1: SL → Entry (ZERO RISK)
- ΜΕΤΑ TP2: SL → TP1 (locked +33€)
- RUNNER: trailing 1x risk, ΜΟΝΟ forward

### Σενάρια P&L (100€ risk)
- SL hit: −100€ | TP1 only: +33€ | TP1+TP2: +99€ | Full run 3x: +132€ | Full run 5x: +199€

## Weekend Mode
- Scanner morning τρέχει Σαββατοκύριακο (cron: `0 8 * * *`)
- ΣΚ: ΜΟΝΟ BTC + SOL σκανάρονται
- `weekend_mode: true` → Analyst αγνοεί Forex + NAS100
- Analyst τρέχει κανονικά (cron: `*/20 8-21 * * *`)

## NAS100 Afternoon Flow
- Morning scan: `nas100_afternoon: true` (IB δεν έχει σχηματιστεί ακόμα)
- Afternoon scan (15:30): αξιολογεί αν NAS100 μένει active
- Analyst: αναλύει NAS100 ΜΟΝΟ αν ώρα > 16:30 EET 🇬🇷

## TRS (Trade Readiness Score)
⬜ 0-1/5 COLD | 🟡 2-3/5 WARM | 🟢 4/5 HOT | 🔥 5/5 TRADE!

## emergency_activations.json Schema
```json
{
  "last_seen_scan_timestamp": "",
  "activations": [
    {
      "asset": "XAUUSD",
      "activated_at": "2026-03-30 11:20 EET",
      "reason": "[direction + catalyst, 2 sentences]",
      "headline": "[triggering headline]",
      "source": "[source]",
      "open_trade": false
    }
  ]
}
```

**Emergency TRS Gate:** 5/5 required for entry (vs 4/5 for regular scanner assets)
**Cap:** Max 2 emergency activations simultaneously
**Cleanup:** On each new Scanner run — removes resolved activations, keeps open trades

## Σειρά κύκλου Analyst v5.1
1. Διάβασε scanner_watchlist.json + emergency_activations.json
2. Cleanup emergency (αν νέος Scanner run) → build `final_active`
3. SANITY CHECK τιμών
4. price_checker.py → live_prices.json
5. LADDER MANAGEMENT (open trades)
6. NAS100 afternoon check
7. ΑΝΑΛΥΣΗ final_active assets (TRS)
8. NEWS CHECK → Breaking News Scan (Ε1/Ε2/Ε3 gate)
9. Update open_trade αν χρειάζεται
10. TRADE EXECUTION (5/5 → trade | 4+/5 κανονικά → trade | 4/5 emergency → monitor)
11. CHARTS (TRS 4+/5 scanner | πάντα emergency)
12. TELEGRAM (🚨 BREAKING ΠΡΩΤΑ)
13. JOURNAL update

## Changelog
- **v2.0**: XAUUSD, NAS100 (TJR), EURUSD — 3 assets, TJR only
- **v2.1** (2026-03-26): Telegram improvements
- **v3.0** (2026-03-26): 5 assets, NAS100 → IBB
- **v3.1** (2026-03-27): TRS, News Impact, Trade Monitor, Decision Reasoning
- **v3.2** (2026-03-27): Sanity check, Trailing, Journal, Weekly summary, Dual-source price, EET 🇬🇷
- **v4.0** (2026-03-27): LADDER RISK SYSTEM — 100€ fixed risk, 33/33/33 split
- **v5.0** (2026-03-29): Scanner leads Analyst — active_today JSON, skip assets 1 line, weekend crypto mode, Mon-Sun schedule
- **v5.1** (2026-03-29): Emergency News Activation System — Breaking News Scan (Ε1/Ε2/Ε3 gate), emergency_activations.json, cap 2/2, cleanup lifecycle, TRS gate (5/5 only for emergency entry), open_trade tracking, 🚨 Telegram block
