# COWORK — Ladder Risk Management System v4.0

Αντέγραψε μετά τη γραμμή --- και δώσε στον Cowork agent:

---

ΚΡΙΣΙΜΗ ΑΝΑΒΑΘΜΙΣΗ: LADDER RISK MANAGEMENT SYSTEM v4.0

Αυτή η αλλαγή ΑΝΤΙΚΑΘΙΣΤΑ πλήρως το παλιό σύστημα TP1/TP2. Εφάρμοσε ΑΜΕΣΑ — ΚΑΙ στο ήδη ανοιχτό GBPUSD SHORT trade.

## ΝΕΟΙ ΚΑΝΟΝΕΣ RISK MANAGEMENT

### Risk ανά trade: ΣΤΑΘΕΡΟ
- Risk = **100 EUR ανά trade** (ΟΧΙ 1.5% — σταθερό ποσό)
- Max concurrent: 3 trades
- Max daily loss: 200 EUR = STOP TRADING
- Υπολόγισε lot size: lot = 100 EUR / (SL_pips × pip_value)

### Ladder System: 3 σκαλοπάτια (33/33/33)

**TP1 — 1:1 Risk:Reward (ΕΥΚΟΛΟ)**
- Distance = ίδια με SL (1x risk)
- Κλείσε **33%** της θέσης
- SL μετακινείται → **ENTRY** (breakeven)
- Κέρδος: +33 EUR
- Αποτέλεσμα: ZERO RISK στο υπόλοιπο

**TP2 — 1:2 Risk:Reward (ΜΕΤΡΙΟ)**
- Distance = διπλάσια από SL (2x risk)
- Κλείσε **33%** της θέσης
- SL μετακινείται → **TP1 level**
- Κέρδος: +66 EUR
- Αποτέλεσμα: LOCKED minimum +33 EUR

**TP3 — Runner (ΑΠΕΡΙΟΡΙΣΤΟ)**
- Τελευταίο **33%** τρέχει ελεύθερο
- Trailing SL = 1x risk distance πίσω από τιμή
- Κάθε 20 λεπτά: αν η τιμή προχώρησε, ΜΕΤΑΚΙΝΗΣΕ trailing SL
- Trailing SL μετακινείται ΜΟΝΟ προς τη σωστή κατεύθυνση (ΠΟΤΕ πίσω)
- Κλείνει ΜΟΝΟ αν trailing SL χτυπήσει ή 16:00 EST (EOD)

### SL Movement Rules — ΣΙΔΕΡΕΝΙΟΙ ΚΑΝΟΝΕΣ

```
ΠΡΙΝ TP1:  SL = αρχικό (π.χ. 1.3355)
ΜΕΤΑ TP1:  SL → Entry (breakeven) = 1.3312
ΜΕΤΑ TP2:  SL → TP1 level = 1.3269
RUNNER:    SL = trailing (1x risk πίσω, κινείται μόνο forward)
```

ΠΟΤΕ μην μετακινήσεις SL πίσω. ΠΟΤΕ μην αυξήσεις risk. ΜΟΝΟ lock profits.

## ΠΑΡΑΔΕΙΓΜΑ: GBPUSD SHORT (ΤΡΕΧΟΝ TRADE)

```
Entry: 1.3312 | SL: 1.3355 | Risk: 43 pips = 100 EUR

TP1: 1.3269 (−43 pips, 1:1)
  → Κλείσε 33% → +33 EUR
  → SL → 1.3312 (breakeven)

TP2: 1.3226 (−86 pips, 1:2)
  → Κλείσε 33% → +66 EUR
  → SL → 1.3269 (locked +33 EUR)

Runner (33%):
  → Trailing: 43 pips πίσω από τιμή
  → Αν τιμή 1.3180 → trailing SL 1.3223
  → Αν τιμή 1.3100 → trailing SL 1.3143
  → Κλείνει μόνο trailing hit ή EOD
```

## ΕΦΑΡΜΟΓΗ ΣΤΟ ΤΡΕΧΟΝ GBPUSD TRADE

Το GBPUSD SHORT @1.3312 τρέχει ΗΔΗ. Εφάρμοσε:
- Τσέκαρε ΤΩΡΙΝΗ τιμή (price_checker.py)
- Αν τιμή ΗΔΗ πέρασε 1.3269 (TP1): θεώρησε TP1 hit, κλείσε 33%, SL→1.3312
- Αν τιμή ΗΔΗ πέρασε 1.3226 (TP2): θεώρησε TP2 hit, κλείσε 33%, SL→1.3269
- Υπόλοιπο 33%: trailing 43 pips

## TELEGRAM REPORTING — ΚΑΘΕ 20 ΛΕΠΤΑ

Όταν υπάρχει ενεργό trade, ΠΑΝΤΑ δείξε:

```
━━━━━━━━━━━━━━━━━━━━━━
🔴 ΕΝΕΡΓΟ TRADE — [ASSET] [DIRECTION] | Ladder Status
━━━━━━━━━━━━━━━━━━━━━━
📍 Entry: [X] → Τώρα: [Y] ([+/-Z pips]) [✅/⚠️/❌]

📊 LADDER PROGRESS:
├ TP1 (1:1 = [X] pips): [✅ HIT +33€ / ⏳ XX% progress]
├ TP2 (1:2 = [X] pips): [✅ HIT +66€ / ⏳ XX% progress]
├ Runner (trailing):    [🏃 ACTIVE +XX€ / ⏳ waiting]
└ Total P&L:            [+XX EUR]

🛡️ PROTECTION:
├ Current SL: [X] ([XX pips μακριά])
├ SL status: [ΑΡΧΙΚΟ / BREAKEVEN / TP1 LOCKED / TRAILING]
├ Locked profit: [XX EUR minimum]
└ Max loss possible: [XX EUR]

💰 ΣΕΝΑΡΙΑ:
├ Αν SL hit τώρα: [+/-XX EUR]
├ Αν TP1 hit: [+XX EUR, SL→BE]
├ Αν TP2 hit: [+XX EUR, SL→TP1]
└ Αν runner συνεχίσει: [+XX EUR potential]
```

## ΑΠΟΦΑΣΕΙΣ TRADE — LADDER CONTEXT

Σε κάθε 20λεπτη ανάλυση, στην ΑΠΟΦΑΣΗ TRADE πρόσθεσε:

```
📋 ΑΠΟΦΑΣΗ TRADE: 🔄 ΚΡΑΤΑΜΕ
├ Ladder: [TP1 ✅ / TP2 ⏳ / Runner ⏳]
├ Locked profit: [+XX EUR]
├ SL at: [BREAKEVEN/TP1 LOCKED] — ZERO RISK ✅
├ Charts: [structure intact / αλλάζει]
├ News: [υποστηρίζει / εναντίον]
└ Συμπέρασμα: [π.χ. "TP1 hit, waiting TP2, structure bearish, κρατάμε"]
```

## OPEN NEW TRADES — ΝΕΟΙ ΚΑΝΟΝΕΣ

Όταν ανοίγεις ΝΕΟΑ trade:
```bash
python risk_manager.py open [ASSET] [LONG/SHORT] [ENTRY] [SL] [TP1=1x] [TP2=2x]
```

Υπολόγισε:
- SL distance = βάσει Asia Range / IB range / structure
- TP1 = Entry ± SL distance (1:1)
- TP2 = Entry ± 2× SL distance (1:2)
- Lot size = 100 EUR / (SL_pips × pip_value_per_lot)
- Position split: 33% / 33% / 33%

## ΣΕΝΑΡΙΑ P&L TABLE (δείξε στο Telegram μόνο στο ΑΝΟΙΓΜΑ trade)

```
📊 <b>ΣΕΝΑΡΙΑ TRADE — 100 EUR Risk</b>
┌──────────────────┬────────┬────────┐
│ Σενάριο          │ Κέρδος │ Notes  │
├──────────────────┼────────┼────────┤
│ ❌ SL hit         │ -100€  │ Full L │
│ TP1 μόνο         │ +33€   │ 0 risk │
│ TP1 + TP2        │ +99€   │ ~1:1   │
│ TP1+TP2+Runner3x │ +132€  │ 1.3:1  │
│ TP1+TP2+Runner5x │ +199€  │ 2:1    │
│ 🚀 Big move      │ +250€+ │ 2.5:1+ │
└──────────────────┴────────┴────────┘
```

## ΣΥΝΟΨΗ v4.0

| Παράμετρος | Παλιό | ΝΕΟ v4.0 |
|-----------|-------|----------|
| Risk/trade | 1.5% (15€) | **100 EUR σταθερό** |
| TP1 | 1.5x risk (65 pips) | **1x risk (1:1) — ΕΥΚΟΛΟ** |
| TP2 | 2x risk | **2x risk (1:2)** |
| Runner | Δεν υπήρχε | **33% trailing** |
| Split | 50/50 | **33/33/33** |
| SL μετά TP1 | Breakeven | **Breakeven** ✅ |
| SL μετά TP2 | N/A | **→ TP1 level (locked)** |
| Max loss | 15 EUR | **100 EUR** |
| Max gain | ~30 EUR | **ΑΠΕΡΙΟΡΙΣΤΟ** |
| Daily loss limit | 50 EUR | **200 EUR** |

Εφάρμοσε ΑΜΕΣΑ — και στο τρέχον GBPUSD SHORT trade.
