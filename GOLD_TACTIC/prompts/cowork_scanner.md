# Cowork Scheduled Tasks: GOLD TACTIC — Scanner v5.0

## Αρχιτεκτονική
**"Ο Scanner αποφασίζει. Ο Analyst υπακούει."**

Ο Scanner ΔΕΝ στέλνει απλά WATCH/SKIP. **Αποφασίζει ποια assets θα αναλύει ο Analyst.**

## Tasks

### Scanner Morning — `gold-tactic-scanner-morning`
- **Schedule**: 08:00, Δευτέρα-Κυριακή (`0 8 * * *`)
- **Σκοπός**: Αποφασίζει `active_today` για ολόκληρη την ημέρα
- **ΣΚ**: Σκανάρει ΜΟΝΟ BTC + SOL (`weekend_mode: true`)
- **Εβδομάδα**: EURUSD, GBPUSD, NAS100, SOL, BTC

### Scanner Afternoon — `gold-tactic-scanner-afternoon`
- **Schedule**: 15:30, Δευτέρα-Παρασκευή (`30 15 * * 1-5`)
- **Σκοπός**: Ενημερώνει `active_today` + NAS100 IB αξιολόγηση
- **Κύρια δουλειά**: NAS100 afternoon check (IB window 16:30-17:30 EET)

## Core Assets v5.0
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
    "GBPUSD": "ADR 87% consumed, no room",
    "NAS100": "NFP today, extreme risk",
    "SOL": "Choppy, no clear bias"
  },
  "active_reasons": {
    "EURUSD": "Bias aligned SHORT, ADR 42%, Asia Low formed",
    "BTC": "RSI 28 oversold bounce setup, swept lows"
  },
  "analyst_instructions": {
    "EURUSD": "Watch 1.0823 Asia Low sweep. Entry on BOS below. Target 1.0780.",
    "BTC": "Counter-trend LONG only. Entry on BOS above sweep. TP1=1x only."
  },
  "nas100_afternoon": true,
  "active_count": 2
}
```

## Κριτήρια active_today

### Forex: EURUSD, GBPUSD
✅ active αν ΟΛΑ:
- Daily + 4H bias aligned
- ADR < 70%
- Asia range formed + σαφές H/L για sweep
- Δεν υπάρχει high-impact news κατά άνοιγμα

### NAS100
✅ active αν ΟΛΑ:
- Clear daily bias
- ADR < 70%
- Δεν υπάρχει FOMC/NFP/CPI
- → `nas100_afternoon: true` (IB σχηματίζεται 16:30-17:30 EET)

### SOL, BTC
✅ active αν ΤΟΥΛΑΧΙΣΤΟΝ ΕΝΑ:
- RSI 25-75 + ADR < 70% + bias aligned (TJR)
- Ή RSI < 25 + swept lows (Counter-trend)
- ΣΚ: χαλαρότερα (ADR < 80%)

❌ skip αν:
- ADR > 90% ήδη consumed
- Conflicting signals Daily vs 4H
- Choppy/sideways χωρίς clear structure
- Extreme news risk (Fed, CPI, NFP)

## Telegram Format

```
🔍 GOLD TACTIC SCANNER — Πρωί/Απόγευμα [DD/MM EET 🇬🇷]

📊 ΑΓΟΡΑ: [context 1-2 γραμμές]
━━━━━━━━━━━━━━━━━━━

✅ ΠΑΡΑΚΟΛΟΥΘΟΥΜΕ ΣΗΜΕΡΑ (N assets):
• ASSET: active_reason — instruction preview

━━━━━━━━━━━━━━━━━━━

❌ SKIP ΣΗΜΕΡΑ:
• ASSET: skip_reason

━━━━━━━━━━━━━━━━━━━
[αν weekend_mode:] 🏖️ WEEKEND MODE — Crypto only
[αν active_today=[]:] 📭 Κανένα asset active
[αν nas100_afternoon:] ⏰ NAS100: Αναμονή IB 16:30-17:30 EET 🇬🇷
```

## Changelog
- **v2.0**: XAUUSD, NAS100 (TJR), EURUSD — 3 core assets
- **v3.0** (2026-03-26): GBPUSD+SOL+BTC προστέθηκαν, NAS100 → IBB, clickable news links
- **v5.0** (2026-03-29): Scanner αποφασίζει `active_today` — νέο JSON schema, weekend mode (Mon-Sun cron), `analyst_instructions`, max 3 active assets
