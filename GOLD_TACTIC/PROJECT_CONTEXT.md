# GOLD TACTIC — Project Context
Τελευταία ενημέρωση: 2026-03-29

**Διάβασε αυτό αν ξεκινάς νέο session.** Περιέχει το σκεπτικό, τους στόχους, και τι κάνουμε.

---

## Τι είναι

Paper trading σύστημα που τρέχει μέσω Claude Cowork scheduled tasks. Στέλνει αναλύσεις
στο Telegram κάθε 20 λεπτά. Στόχος: **1-2 trades/ημέρα** (daily trading, ΟΧΙ investing).

## Πώς δουλεύει

```
Scanner Morning (08:00) → Αποφασίζει ποια assets παρακολουθούνται
Scanner Afternoon (15:30) → Ενημερώνει, αξιολογεί NAS100
Trading Analyst (κάθε 20') → Αναλύει, ανοίγει/κλείνει trades, Telegram
```

Κάθε scheduled task φορτώνει ένα .md αρχείο ως prompt:
- `prompts/analyst_core_v6.md` → Gold tactic trading analyst
- `prompts/scanner_morning_v6.md` → Gold tactic scanner morning
- `prompts/scanner_afternoon_v6.md` → Gold tactic scanner afternoon

## Κρίσιμος κανόνας

**ΟΛΕΣ οι αλλαγές γίνονται στα .md αρχεία** στο `GOLD_TACTIC/prompts/`.
Ο χρήστης τα κάνει copy-paste στα Cowork schedules.
ΜΗΝ κάνεις αλλαγές "στον αέρα" — πάντα persist σε αρχείο.

## Ενεργές στρατηγικές (Real Trades)

| Στρατηγική | Assets | Ώρα | Status |
|-----------|--------|-----|--------|
| TJR Asia Sweep | EURUSD, GBPUSD, SOL, BTC | Μετά Asia (09:00+) | ✅ Ενεργή |
| IBB | NAS100 | 16:30-22:00 EET | ✅ Ενεργή |
| Counter-trend | SOL, BTC | Όταν RSI < 25 | ✅ Ενεργή |

## Pilot στρατηγικές (Shadow Trades — δοκιμάζονται)

| Στρατηγική | Assets | Ώρα | Status |
|-----------|--------|-----|--------|
| London Killzone | EURUSD, GBPUSD | 09:00-11:00 EET | 🧪 Pilot |
| NY AM Momentum | NAS100, XAUUSD | 17:30-19:00 EET | 🧪 Pilot |
| Late Continuation | NAS100 | 19:00-21:30 EET | 🧪 Pilot |
| Crypto Weekend Momentum | BTC, SOL, ETH | ΣΚ 10:00-20:00 EET | 🧪 Pilot |

## Token Optimization (v6.0)

Πρόβλημα: 40% token limit per 5 hours.
Λύση: Split prompt σε CORE (κάθε κύκλο) + REFERENCE (on-demand).
Reference files φορτώνονται ΜΟΝΟ αν TRS ≥ 4 ή open trade.

## Pilot Mode — Σκεπτικό

Τα mechanical backtests δεν δουλεύουν γιατί η στρατηγική χρειάζεται discretionary judgement
+ live news context. Αντί backward backtest, κάνουμε **forward test με shadow trades**:

1. Ο Agent σημειώνει "θα έμπαινα εδώ" (shadow trade) χωρίς ρίσκο
2. Κάθε κύκλο ελέγχει αν θα κέρδιζε ή θα έχανε
3. Καταγράφει σε `data/shadow_trades.json`
4. Κάθε Παρασκευή αξιολογεί σε `data/strategy_scorecard.md`
5. Agent γράφει παρατηρήσεις σε `data/pilot_notes.md` (μνήμη)
6. Στρατηγική > 55% WR μετά 10+ trades → upgrade σε real

## Τρέχουσα κατάσταση

- Portfolio: ~998.80€ (1 trade, 1 νίκη: GBPUSD +11.70€)
- Pilot: Δεν έχει ξεκινήσει ακόμα (ξεκινάει Δευτέρα 31/3)
- Telegram: Αναμένεται copy-paste νέων prompts στα Cowork schedules

## Αρχεία reference

```
prompts/
├── analyst_core_v6.md          ← Analyst CORE prompt
├── scanner_morning_v6.md       ← Scanner morning prompt
├── scanner_afternoon_v6.md     ← Scanner afternoon prompt
├── ref_strategies.md           ← Ενεργές στρατηγικές (on-demand)
├── ref_ladder.md               ← Ladder risk system (on-demand)
├── ref_emergency.md            ← Emergency activation (on-demand)
├── ref_strategies_pilot.md     ← Pilot στρατηγικές (on-demand)
└── MASTER_ANALYST_PROMPT.md    ← ΠΑΛΙΟ v5.1 (backup, θα γίνει archive)

data/
├── shadow_trades.json          ← Shadow trade καταγραφή
├── strategy_scorecard.md       ← Performance ανά στρατηγική
├── pilot_notes.md              ← Agent μνήμη/παρατηρήσεις
├── scanner_watchlist.json      ← Τι assets είναι active
├── portfolio.json              ← Capital + positions
├── trade_journal.md            ← Journal trades
└── ...
```

## Ιστορικό αποφάσεων

- **2026-03-29:** v6.0 redesign — token optimization, Telegram zones, pilot mode
- **2026-03-29:** Cleanup repo — διαγράφτηκαν gold-bot, trading-system, variants, κτλ
- **2026-03-27:** Πρώτο live trade: GBPUSD SHORT +11.70€ (TRS 5/5, EOD close)
- **2026-03-26:** v5.1 — Emergency News Activation system
- **2026-03-26:** Αρχικό deployment, 5 core assets, TJR + IBB + Counter-trend
