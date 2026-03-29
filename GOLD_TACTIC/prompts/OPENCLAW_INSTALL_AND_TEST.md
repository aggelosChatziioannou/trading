# GOLD TACTIC — Cloud Installation & Test
**Δώσε αυτό το αρχείο σε νέο OpenClaw agent για πλήρη εγκατάσταση**

---

## ΑΠΟΣΤΟΛΗ ΣΟΥ

Θα εγκαταστήσεις το σύστημα GOLD TACTIC σε αυτό το περιβάλλον, θα τρέξεις tests επιβεβαίωσης, και θα μου αναφέρεις αν όλα δουλεύουν. ΜΗΝ ενεργοποιήσεις κανένα schedule — απλά install + test + report.

---

## ΒΗΜΑ 1: CLONE REPO

```bash
git clone https://github.com/aggelosChatziioannou/trading.git
cd trading
```

Επιβεβαίωσε ότι υπάρχουν αυτοί οι φάκελοι:
```bash
ls GOLD_TACTIC/scripts/
ls GOLD_TACTIC/data/
ls GOLD_TACTIC/prompts/
```

**Αναμένεις:**
- `scripts/`: chart_generator.py, price_checker.py, risk_manager.py, news_scout.py, telegram_sender.py, opportunity_scanner.py
- `data/`: emergency_activations.json, portfolio.json, scanner_watchlist.json, trade_history.json
- `prompts/`: MASTER_ANALYST_PROMPT.md, cowork_analyst.md, cowork_scanner.md

Αν κάτι λείπει → αναφέρτο αμέσως.

---

## ΒΗΜΑ 2: INSTALL DEPENDENCIES

```bash
pip install -r requirements.txt
```

Αν pip δεν είναι διαθέσιμο:
```bash
pip3 install -r requirements.txt
```

Τα κύρια πακέτα που χρειάζεσαι:
- `yfinance` — live τιμές
- `mplfinance` + `matplotlib` — charts
- `pandas`, `numpy` — data processing
- `feedparser`, `beautifulsoup4` — news
- `requests` — HTTP calls

Επιβεβαίωσε εγκατάσταση:
```bash
python -c "import yfinance, mplfinance, pandas, feedparser; print('All imports OK')"
```

---

## ΒΗΜΑ 3: ΔΗΜΙΟΥΡΓΙΑ ΦΑΚΕΛΩΝ

```bash
mkdir -p GOLD_TACTIC/screenshots
mkdir -p GOLD_TACTIC/data
```

Τα screenshots δεν είναι στο git (μεγάλα PNGs) — πρέπει να δημιουργηθούν locally.

---

## ΒΗΜΑ 4: TESTS — ΤΡΕΞΕ ΟΛΑ ΚΑΙ ΑΝΑΦΕΡΕ ΑΠΟΤΕΛΕΣΜΑ

### Test 1: Price Checker
```bash
python GOLD_TACTIC/scripts/price_checker.py
```
**Αναμένεις:** Τιμές για EURUSD, GBPUSD, BTC, SOL, NAS100 (ή μήνυμα "market closed" αν είναι ΣΚ/νύχτα — αυτό είναι ΟΚ)

### Test 2: Risk Manager
```bash
python GOLD_TACTIC/scripts/risk_manager.py status
```
**Αναμένεις:** Portfolio status με capital και open positions (0 αρχικά)

### Test 3: Chart Generator (1 asset)
```bash
python GOLD_TACTIC/scripts/chart_generator.py BTC
```
**Αναμένεις:** `GOLD_TACTIC/screenshots/BTC_daily.png`, `BTC_4h.png`, `BTC_5m.png` δημιουργήθηκαν

### Test 4: News Scout
```bash
python GOLD_TACTIC/scripts/news_scout.py
```
**Αναμένεις:** `GOLD_TACTIC/data/news_feed.json` γράφτηκε με νέα

### Test 5: Telegram — ΚΡΙΣΙΜΟ TEST
```bash
python GOLD_TACTIC/scripts/telegram_sender.py message "🤖 GOLD TACTIC cloud install OK — testing connectivity"
```
**Αναμένεις:** Μήνυμα να φτάσει στο Telegram channel

Telegram credentials (ήδη μέσα στο script):
- Token: `8621254551:AAF3z5R-5JrAzTKaZQ31E3pmXxtlvQ10wFc`
- Chat ID: `-1003767339297`

### Test 6: Διάβασε το Master Prompt
```bash
cat GOLD_TACTIC/prompts/MASTER_ANALYST_PROMPT.md
```
**Αναμένεις:** Να διαβαστεί χωρίς error. Αυτό είναι το κύριο prompt που θα χρησιμοποιείς σε κάθε κύκλο.

---

## ΒΗΜΑ 5: ΑΝΑΦΟΡΑ ΑΠΟΤΕΛΕΣΜΑΤΩΝ

Μόλις τελειώσεις όλα τα tests, στείλε μου αναφορά με αυτή τη μορφή:

```
GOLD TACTIC INSTALL REPORT
===========================
Περιβάλλον: [OS, Python version]
Clone: ✅/❌
Dependencies: ✅/❌ [αν ❌, ποιο package έπεσε]
Directories: ✅/❌
Test 1 (price_checker): ✅/❌ [τιμές ή error]
Test 2 (risk_manager): ✅/❌
Test 3 (chart_generator): ✅/❌ [png δημιουργήθηκε ή error]
Test 4 (news_scout): ✅/❌
Test 5 (telegram): ✅/❌ [μήνυμα στάλθηκε ή error]
Test 6 (master prompt): ✅/❌

ΣΥΝΟΛΟ: X/6 tests passed
STATUS: [READY / NEEDS FIXES]

[Αν υπάρχουν ❌, περίγραψε το error ακριβώς]
```

---

## ΣΗΜΕΙΩΣΕΙΣ

- **ΜΗΝ** τρέξεις κανένα schedule ακόμα — μόνο install + test
- **ΜΗΝ** αλλάξεις κανένα αρχείο — μόνο εγκατάσταση
- Αν κάποιο test αποτύχει, αναφέρτο με το ακριβές error message
- Μετά την αναφορά, **περίμενε οδηγίες** για το αν θα ενεργοποιήσεις το schedule

Αν όλα είναι ✅, θα σου πω εγώ πότε να ξεκινήσεις.
