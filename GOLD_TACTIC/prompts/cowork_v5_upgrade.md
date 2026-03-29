# COWORK v5.0 — Scanner + Analyst Συνεργασία

Δώσε αυτό ΚΑΙ στα 2 schedules (Scanner + Analyst):

---

ΑΝΑΒΑΘΜΙΣΗ v5.0 — SCANNER ΟΔΗΓΕΙ ΤΟΝ ANALYST

## ΑΛΛΑΓΗ 1: SCANNER ΑΠΟΦΑΣΙΖΕΙ ΤΑ ASSETS ΤΗΣ ΗΜΕΡΑΣ

Ο Scanner ΔΕΝ στέλνει απλά WATCH/SKIP. Αποφασίζει ΠΟΙΑ assets θα αναλύει ο Analyst σήμερα.

### Scanner γράφει στο scanner_watchlist.json:

```json
{
  "scan_timestamp": "2026-03-28 08:00",
  "active_today": ["EURUSD", "BTC"],
  "skip_today": {
    "GBPUSD": "ADR ήδη 75% από Asia crash, δεν θα βρει setup",
    "NAS100": "IBB window 16:30 EET — θα αξιολογηθεί στο afternoon scan",
    "SOL": "Ακολουθεί BTC χωρίς ανεξάρτητο catalyst"
  },
  "active_reasons": {
    "EURUSD": "Bias aligned BEAR, Asia range σφιχτό 22 pips, ADR 15%, Fed hawkish = USD strong. Εκτίμηση Score: 3/5, πιθανό setup 10:00-14:00 EET",
    "BTC": "RSI 30 πλησιάζει oversold, $65K critical support, Iran talks = catalyst. Counter-trend bounce πιθανό αν RSI<25"
  },
  "analyst_instructions": {
    "EURUSD": "Ψάξε sweep Asia High 1.1549 + BOS down. SHORT setup.",
    "BTC": "Παρακολούθησε RSI — αν πέσει κάτω 25, counter-trend LONG setup ενεργοποιείται"
  },
  "nas100_afternoon": true,
  "weekend_mode": false
}
```

### Κριτήρια: Πότε ένα asset γίνεται ACTIVE

Ο Scanner βάζει asset στα active_today ΜΟΝΟ αν:
1. ✅ Daily + 4H bias aligned (ή RSI <30 για counter-trend)
2. ✅ ADR < 70% consumed (υπάρχει χώρος)
3. ✅ Asia range formed (ή IB window σύντομα για NAS100)
4. ✅ Κάποιο news catalyst υποστηρίζει direction

Αν ΚΑΝΕΝΑ asset δεν πληρεί = active_today μπορεί να είναι ΚΕΝΟ. Τότε ο Analyst στέλνει:
"📭 Scanner: Κανένα asset δεν αξίζει σήμερα. Αναμονή afternoon scan."

### NAS100 ειδική μεταχείριση

NAS100 χρησιμοποιεί IBB (window 16:30-17:30 EET). Ο Scanner πρωί ΔΕΝ μπορεί να ξέρει αν θα υπάρξει setup.
- Morning scan: NAS100 πάντα "skip — IBB window αργότερα"
- Afternoon scan (15:30 EET): Αξιολογεί NAS100 και αν αξίζει → active
- Αν afternoon scan βάλει NAS100 active, ο Analyst ξεκινά ανάλυση από 16:30

### ΣΚ λειτουργία

Σαββατοκύριακο:
- Scanner: τρέχει ΜΟΝΟ πρωί, σκανάρει ΜΟΝΟ BTC + SOL (crypto 24/7)
- Analyst: κάθε 20 λεπτά ΜΟΝΟ για crypto assets
- EURUSD, GBPUSD, NAS100: ΚΛΕΙΣΤΑ — δεν αναλύονται ΣΚ
- Στο watchlist: "weekend_mode": true

## ΑΛΛΑΓΗ 2: ANALYST ΥΠΑΚΟΥΕΙ ΤΟΝ SCANNER

Ο Analyst διαβάζει scanner_watchlist.json ΠΡΩΤΑ.

### Αν active_today = ["EURUSD", "BTC"]:
- Αναλύει ΜΟΝΟ EURUSD + BTC (full TRS, charts, news, levels)
- GBPUSD, NAS100, SOL: 1 γραμμή "⏭️ Skipped by Scanner: [λόγος]"
- ΔΕΝ φτιάχνει charts για skip assets
- ΔΕΝ υπολογίζει TRS για skip assets

### Αν active_today = []:
- Στέλνει: "📭 Κανένα asset active σήμερα. Παρακολουθώ μόνο news."
- ΜΟΝΟ news monitoring — αν βγει breaking news, αξιολογεί ξανά

### Αν nas100_afternoon = true και ώρα > 16:30 EET:
- Προσθέτει NAS100 στα active
- Ξεκινά IBB ανάλυση

### Charts: ΜΟΝΟ active assets
```bash
python scripts/chart_generator.py [ACTIVE_ASSETS ONLY]
```
Αν active = EURUSD + BTC:
```bash
python scripts/chart_generator.py EURUSD BTC
```
ΟΧΙ: python scripts/chart_generator.py EURUSD GBPUSD NAS100 SOL BTC

## ΑΛΛΑΓΗ 3: TELEGRAM FORMAT

### Scanner Telegram (2x/ημέρα):
```
🔍 <b>SCANNER — [Πρωινή/Απογευματινή] Ενημέρωση</b>
🕐 08:00 EET 🇬🇷 | [Ημέρα]
━━━━━━━━━━━━━━━━━━━━━━

📊 <b>ΑΓΟΡΑ ΣΗΜΕΡΑ:</b>
[3 γραμμές macro — πόλεμος, oil, Fed, sentiment]

━━━━━━━━━━━━━━━━━━━━━━
✅ <b>ΣΗΜΕΡΑ ΠΑΡΑΚΟΛΟΥΘΟΥΜΕ:</b>
━━━━━━━━━━━━━━━━━━━━━━

📈 <b>EURUSD</b> — Score εκτίμηση: 3/5
├ Γιατί: [2-3 γραμμές — bias, ADR, news catalyst]
├ Τι ψάχνουμε: [sweep level + direction]
├ 📰 News: [σχετικό νέο + IMPACT]
└ ⏰ Πιθανό setup: [ώρα EET]

📈 <b>BTC</b> — Score εκτίμηση: 3/5
├ Γιατί: [2-3 γραμμές]
├ Τι ψάχνουμε: [τι trigger]
└ ⏰ Πιθανό setup: [ώρα EET]

━━━━━━━━━━━━━━━━━━━━━━
❌ <b>ΣΗΜΕΡΑ SKIP:</b>
━━━━━━━━━━━━━━━━━━━━━━
GBPUSD: [1 γραμμή λόγος]
NAS100: IBB window 16:30 EET — afternoon scan θα αξιολογήσει
SOL: Follows BTC χωρίς catalyst

🤖 GOLD TACTIC v5.0 | Scanner
```

### Analyst Telegram (κάθε 20'):
```
📊 <b>ANALYST — #[N]</b>
🕐 [ΩΡΑ EET] 🇬🇷 | Scanner: [ώρα τελευταίου scan]
💼 Portfolio: [X] EUR | Open: [X]/3

[ΕΝΕΡΓΟ TRADE αν υπάρχει — ladder + ΑΠΟΦΑΣΗ]

[ΜΟΝΟ ACTIVE ASSETS — full TRS ανάλυση]

⏭️ Skipped: GBPUSD (ADR 75%), NAS100 (IBB 16:30), SOL (follows BTC)

📰 <b>LIVE NEWS:</b>
[ΜΟΝΟ νέα που βγήκαν τελευταία 20 λεπτά]
[+ IMPACT + ΜΑΘΗΜΑ]
[+ ΣΥΜΒΟΥΛΗ αν επηρεάζει ενεργό trade]

📋 ΑΠΟΦΑΣΗ: [ΑΝΑΜΟΝΗ / ΜΠΑΙΝΟΥΜΕ / ΚΡΑΤΑΜΕ]
⏰ Επόμενη: 20 λεπτά
```

## ΑΛΛΑΓΗ 4: SCHEDULE ΩΡΕΣ

| Schedule | Πριν | Τώρα |
|----------|------|------|
| Scanner πρωί | Δευτ-Παρ 08:00 | **Δευτ-Κυρ 08:00** (ΣΚ μόνο crypto) |
| Scanner απόγευμα | Δευτ-Παρ 15:30 | Δευτ-Παρ 15:30 (ίδιο) |
| Analyst | Δευτ-Παρ 08:00-22:00 | **Δευτ-Παρ 08:00-22:00 + ΣΚ 10:00-20:00** |

ΣΚ Analyst: αναλύει ΜΟΝΟ crypto (BTC/SOL αν είναι active).

## ΣΥΝΟΨΗ v5.0

| Τι | Πριν | Τώρα |
|-----|------|------|
| Analyst assets | Πάντα 5 | **ΜΟΝΟ τα active (1-3)** |
| Scanner ρόλος | Βρίσκει extras | **Αποφασίζει τα active** |
| Charts/analysis | 5 assets × 3 TF = 15 charts | **2-3 assets × 3 = 6-9 charts** |
| Telegram μήκος | Πολύ μεγάλο | **50% μικρότερο** |
| ΣΚ | Κλειστό | **Crypto active** |
| Skip assets | Πλήρης ανάλυση | **1 γραμμή** |
| News | Duplicate scanner+analyst | **Scanner: overview, Analyst: live only** |

Εφάρμοσε ΑΠΟ ΤΟ ΕΠΟΜΕΝΟ SCAN.
