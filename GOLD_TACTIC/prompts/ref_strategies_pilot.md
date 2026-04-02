# Pilot Strategies Reference — Υπό Δοκιμή

**Status:** PILOT MODE — Μόνο shadow trades, ΟΧΙ πραγματικά trades.
**Έναρξη pilot:** 2026-03-31

---

## 1. London Killzone (EURUSD, GBPUSD)

### Λογική
Το London open (09:00 EET) φέρνει τον μεγαλύτερο όγκο της ημέρας στο forex. Οι institutional traders "καθαρίζουν" τα Asia session highs/lows πρώτα (sweep) και μετά ξεκινάνε τη real move. Πιάνουμε αυτή τη real move.

### Window
**09:00 - 11:00 EET** (πρώτο 2ωρο London). Μετά τις 11:00 = STOP, η κίνηση εξασθενεί.

### Setup (ΟΛΑ πρέπει να ισχύουν)
1. **Daily bias ξεκάθαρο** (BULL ή BEAR, όχι ασαφές)
2. **Asia range σχηματίστηκε** (01:00-09:00 EET) — σημείωσε High + Low
3. **Asia range ≥ 20 pips EURUSD / ≥ 25 pips GBPUSD** (αν πολύ μικρό = δεν υπάρχει liquidity)
4. **Sweep γίνεται 08:45-10:00 EET:** Η τιμή περνάει Asia High (για SHORT setup) ή Asia Low (για LONG setup)
5. **Rejection:** Η τιμή ΚΛΕΙΝΕΙ πίσω μέσα στο Asia range μέσα σε 2 κεριά 5 λεπτών
6. **BOS (σπάσιμο δομής):** 5min κλείσιμο πέρα από structure στην αντίθετη κατεύθυνση
7. **ADR consumed < 70%** (υπάρχει χώρος)

### Entry
- Στο BOS candle close, ή σε retracement στο BOS level
- SL: πίσω από το swept Asia extreme + 5 pip buffer
- TP1: 1:1 R:R
- TP2: 1:2 R:R

### Διαφορά από TJR Asia Sweep
- **Πιο αυστηρό timing:** Μόνο 09:00-11:00 (TJR = οποιαδήποτε ώρα)
- **Rejection confirmation:** Πρέπει η τιμή να γυρίσει μέσα σε 2 κεριά (TJR = δεν ελέγχει)
- **Minimum Asia range:** 20/25 pips (TJR = δεν ελέγχει)
- Αναμένεται υψηλότερο win rate λόγω αυστηρότερων φίλτρων

### Ετοιμότητα (TRS) — 5 κριτήρια
1. Daily bias ξεκάθαρο
2. Asia range ≥ 20/25 pips
3. Sweep επιβεβαιωμένο (08:45-10:00 EET)
4. Rejection μέσα σε 2 κεριά
5. BOS + ADR < 70%

---

## 2. NY AM Session Momentum (NAS100, XAUUSD)

### Λογική
Μετά το IB (αρχικό εύρος 16:30-17:30 EET), αν η τιμή σπάσει IB High ή Low, υπάρχει momentum. Αντί να μπούμε στο breakout (πολλά false breakouts), περιμένουμε **pullback** στο IB level και μπαίνουμε εκεί.

### Window
**17:30 - 19:00 EET** (πρώτο 90 λεπτά μετά το IB)

### Setup (ΟΛΑ πρέπει να ισχύουν)
1. **IB σχηματίστηκε** (16:30-17:30 EET)
2. **IB breakout:** Τιμή σπάει IB High (LONG) ή IB Low (SHORT) μετά τις 17:30
3. **Pullback:** Η τιμή γυρίζει πίσω προς IB level (retest)
4. **Hold:** Η τιμή ΔΕΝ κλείνει πίσω μέσα στο IB range σε 15min
5. **Daily bias aligned** με breakout direction
6. **ΟΧΙ FOMC/NFP/CPI ημέρα**

### Entry
- Στο pullback hold (15min κλείσιμο πάνω/κάτω από IB level)
- SL: μέσα στο IB range (πίσω από IB High/Low + buffer)
- TP1: 1× IB range
- TP2: 2× IB range

### Διαφορά από IBB (ήδη ενεργό)
- **Pullback entry αντί breakout entry** — πιο ασφαλές, λιγότερα false breakouts
- **15min confirmation αντί 5min** — πιο αξιόπιστο
- Ίδιο IB window, ίδια TP logic

### Ετοιμότητα (TRS) — 5 κριτήρια
1. IB σχηματίστηκε ξεκάθαρα
2. Breakout εκτός IB range
3. Pullback στο IB level
4. 15min hold (δεν γύρισε μέσα)
5. Daily bias aligned + ADR room

### XAUUSD ειδικά
- Ίδια λογική, ίδιο IB window (16:30-17:30 EET)
- XAUUSD IBB backtest: 50% WR, R:R 1.52 — οριακό, γι' αυτό test πρώτα
- XAUUSD sanity range: $1500-$3500
- pip_value: ~$1/pip/0.01lot (κοντά σε forex)

---

## 3. Late Session Continuation (NAS100 μόνο)

### Λογική
Σε trend days (η τιμή κινείται σταθερά σε μία κατεύθυνση), η κίνηση συνεχίζεται μετά τις 19:00. Αν ήδη πήραμε TP1 σε IBB, αυτό σημαίνει ότι η μέρα είναι trending — δεύτερη ευκαιρία.

### Window
**19:00 - 21:30 EET**

### Setup (ΟΛΑ πρέπει να ισχύουν)
1. **IBB TP1 ήδη hit** σήμερα (confirmed trend day)
2. **Pullback** σε EMA9 ή previous structure
3. **Ίδια κατεύθυνση** με αρχικό IBB trade
4. **ADR consumed < 85%** (ακόμα χώρος παρόλη η κίνηση)
5. **Κανένα major news expected** στις επόμενες 2 ώρες

### Entry
- Στο pullback bounce (5min BOS ίδια κατεύθυνση)
- SL: πίσω από pullback extreme
- TP1: 1:1 R:R ΜΟΝΟ (μικρότερο target — late session)
- **ΜΕΙΩΜΕΝΟ RISK: 50€ αντί 100€** (late session = πιο αβέβαιο)

### Ετοιμότητα (TRS) — 5 κριτήρια
1. IBB TP1 hit today (confirmed trend)
2. Pullback σε structure/EMA
3. BOS ίδια κατεύθυνση
4. ADR < 85%
5. Χωρίς pending news

---

## 4. Crypto Weekend Momentum (BTC, SOL, ETH)

### Λογική
Τα ΣΚ δεν υπάρχει forex/stocks αλλά τα crypto τρέχουν 24/7. Χωρίς institutional
volume, τα crypto κινούνται πιο αργά αλλά τα key levels εξακολουθούν να δουλεύουν.
Ψάχνουμε sweep + reaction σε ημερήσια levels ή strong momentum continuation.

### Window
**ΣΚ 10:00 - 20:00 EET** (active monitoring hours)

### Setup A: Weekend Level Sweep (ΟΛΑ πρέπει να ισχύουν)
1. **Σαββατοκύριακο** (weekend_mode: true)
2. **Τιμή πλησιάζει ή sweep previous day High/Low** (PDH/PDL)
3. **Rejection:** Κερί 1ωρου (1H) κλείνει πίσω μετά το sweep
4. **RSI 4H: 30-70** (ΟΧΙ extreme — εκτός αν counter-trend, βλ. παρακάτω)
5. **Volume spike:** Αν υπάρχει αυξημένο volume στο sweep = καλύτερο
6. **News context:** Τα νέα στηρίζουν κατεύθυνση (ή τουλάχιστον neutral)

### Setup B: Weekend Counter-trend (ΟΛΑ πρέπει να ισχύουν)
1. **RSI Daily < 25** (BTC ή SOL ή ETH)
2. **Sweep of weekly low** (κάτω από χαμηλό εβδομάδας)
3. **1H BOS up** (σπάσιμο δομής πάνω σε 1ωρο)
4. **ΜΟΝΟ LONG**, TP1 = 1:1 ΜΟΝΟ (γρήγορο κέρδος, μην κρατάς)

### Entry
- **Level Sweep:** στο 1H rejection close
- **Counter-trend:** στο 1H BOS candle close
- SL: πίσω από swept level + buffer
- TP1: 1:1 R:R
- TP2: 1.5:1 R:R (μικρότερο — weekend = λιγότερο momentum)

### Ειδικά για ETH
- ETH ΔΕΝ είναι στα core assets — μόνο pilot
- Ακολουθεί BTC αλλά μερικές φορές κινείται ξεχωριστά
- Sanity range: $500-$10,000
- Αν BTC + ETH δίνουν ίδιο σήμα → πάρε ΜΟΝΟ ένα (BTC προτιμάται, μεγαλύτερη ρευστότητα)

### Weekend ρίσκο
- **ΜΕΙΩΜΕΝΟ RISK: 50€ αντί 100€** (weekend = lower liquidity, bigger spreads)
- Max 1 shadow trade ανοιχτό τη φορά (ΣΚ = πιο αβέβαιρο)

### Ετοιμότητα (TRS) — 5 κριτήρια
1. PDH/PDL ή weekly level πλησιάζει
2. Sweep επιβεβαιωμένο (τιμή πέρασε + γύρισε)
3. Rejection σε 1H (κλείσιμο πίσω)
4. RSI σε κανονικά (30-70) ή extreme counter-trend (<25)
5. News context στηρίζει ή neutral

---

## Σύνοψη — Ημερήσιο "Menu" ευκαιριών

### Weekdays (Δευτ-Παρ)
```
09:00-11:00  London Killzone      EURUSD, GBPUSD     Sweep + Rejection
16:30-17:30  IB Formation         NAS100, XAUUSD     Σημείωσε IB H/L
17:30-19:00  NY AM Momentum       NAS100, XAUUSD     Pullback entry μετά breakout
19:00-21:30  Late Continuation    NAS100              2η ευκαιρία αν trend day
```

### Weekends (Σαβ-Κυρ)
```
10:00-20:00  Crypto Weekend       BTC, SOL, ETH      Level sweep ή counter-trend
```

Στόχος: **2-3 ευκαιρίες weekdays + 1 ευκαιρία weekends**.

---

## Shadow Trade Κανόνες

- **ΔΕΝ** ανοίγεις πραγματικό trade σε pilot στρατηγική
- **Καταγράφεις** στο `data/shadow_trades.json` κάθε ευκαιρία
- **Ελέγχεις** κάθε κύκλο αν χτύπησε TP1/SL
- **Σημειώνεις** παρατηρήσεις στο `data/pilot_notes.md`
- Μετά 10+ shadow trades ανά στρατηγική → αξιολόγηση αν γίνει real
