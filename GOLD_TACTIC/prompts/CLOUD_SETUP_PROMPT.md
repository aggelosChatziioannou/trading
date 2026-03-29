# GOLD TACTIC — Cloud Setup & Runtime Prompt
**Για νέο OpenClaw/cloud schedule — εκτέλεσε αυτό ΜΟΝΟ ΜΙΑ ΦΟΡΑ για setup**

---

## ΒΗΜΑ 1: CLONE & SETUP (εκτέλεσε μία φορά)

```bash
# 1. Clone το repo
git clone https://github.com/aggelosChatziioannou/trading.git
cd trading

# 2. Install dependencies
pip install -r requirements.txt

# 3. Επιβεβαίωσε δομή
ls GOLD_TACTIC/scripts/
ls GOLD_TACTIC/data/
ls GOLD_TACTIC/prompts/
```

**Αναμενόμενο αποτέλεσμα setup:**
```
scripts/: chart_generator.py, price_checker.py, risk_manager.py,
          news_scout.py, telegram_sender.py, opportunity_scanner.py
data/:    emergency_activations.json, portfolio.json, scanner_watchlist.json,
          trade_history.json, opportunities.json
prompts/: MASTER_ANALYST_PROMPT.md, cowork_analyst.md, cowork_scanner.md
```

**Δημιούργησε φάκελο για screenshots** (δεν είναι στο git):
```bash
mkdir -p trading/GOLD_TACTIC/screenshots
```

---

## ΒΗΜΑ 2: ΕΠΙΒΕΒΑΙΩΣΗ SCRIPTS

```bash
cd trading

# Test price checker (πρέπει να βγάλει τιμές)
python GOLD_TACTIC/scripts/price_checker.py

# Test telegram (πρέπει να σταλεί test μήνυμα)
python GOLD_TACTIC/scripts/telegram_sender.py message "🤖 GOLD TACTIC cloud setup OK"

# Test portfolio status
python GOLD_TACTIC/scripts/risk_manager.py status
```

---

## ΒΗΜΑ 3: GIT PULL (κάθε κύκλο — ΚΡΙΣΙΜΟ)

Ο Analyst στο cloud πρέπει να κάνει `git pull` στην ΑΡΧΗ κάθε κύκλου για να πάρει τα ενημερωμένα data files από το local PC (scanner_watchlist.json κλπ).

```bash
cd trading && git pull origin main
```

**ΓΙΑΤΙ:** Το local PC τρέχει τον Scanner και γράφει στο `scanner_watchlist.json`. Ο cloud Analyst πρέπει να διαβάζει το τελευταίο watchlist. Χωρίς `git pull`, θα δουλεύει με παλιά δεδομένα.

**ΣΕΙΡΑ κάθε κύκλου:**
```
git pull → διάβασε scanner_watchlist.json → εκτέλεσε κύκλο → git add/commit/push (data updates)
```

---

## ΒΗΜΑ 4: PATHS ΓΙΑ CLOUD

Στο cloud, το project root είναι εκεί που έκανες clone. Τα paths στα scripts είναι **relative** (χρησιμοποιούν `Path(__file__).parent`), οπότε δουλεύουν αυτόματα.

Αν το clone είναι στο `/home/user/trading`:
```
Scripts:      /home/user/trading/GOLD_TACTIC/scripts/
Data:         /home/user/trading/GOLD_TACTIC/data/
Screenshots:  /home/user/trading/GOLD_TACTIC/screenshots/
```

Τρέξε πάντα τα scripts από το root:
```bash
cd /home/user/trading
python GOLD_TACTIC/scripts/price_checker.py   # ✅ σωστό
```

---

## ΒΗΜΑ 5: SYNC DATA ΠΙΣΩ ΣΤΟ GITHUB

Μετά από κάθε κύκλο, αν άλλαξαν data files (trade, emergency activation, κλπ):

```bash
cd trading
git add GOLD_TACTIC/data/emergency_activations.json
git add GOLD_TACTIC/data/portfolio.json
git add GOLD_TACTIC/data/trade_history.json
git add GOLD_TACTIC/data/trade_journal.md
git commit -m "data: analyst cycle [timestamp] — [σύντομη περιγραφή]"
git push origin main
```

Αυτό επιτρέπει στο local PC να βλέπει trades που άνοιξε ο cloud Analyst.

---

## RUNTIME PROMPT (αντέγραψε στο schedule)

Μόλις το setup είναι έτοιμο, το runtime prompt κάθε κύκλου είναι:

```
Εκτέλεσε τον κύκλο GOLD TACTIC Analyst v5.1.

ΒΗΜΑΤΑ ΕΚΚΙΝΗΣΗΣ:
1. cd /path/to/trading && git pull origin main
2. Διάβασε: GOLD_TACTIC/prompts/MASTER_ANALYST_PROMPT.md (πλήρεις οδηγίες)
3. Εκτέλεσε τον κύκλο ακριβώς όπως περιγράφεται στο "ΣΕΙΡΑ ΚΥΚΛΟΥ v5.1"
4. Μετά το Telegram, αν άλλαξαν data: git add/commit/push

Project: /path/to/trading
Ώρα: [current EET time]
```

**Αντικατάστησε το `/path/to/trading`** με το πραγματικό path μετά το clone.

---

## TROUBLESHOOTING

| Πρόβλημα | Λύση |
|---------|------|
| `ModuleNotFoundError: yfinance` | `pip install yfinance mplfinance matplotlib` |
| `ModuleNotFoundError: mplfinance` | `pip install mplfinance` |
| `git pull` conflicts | `git stash && git pull && git stash pop` |
| scanner_watchlist.json παλιό | Τρέξε `git pull` — το local PC το ενημερώνει |
| screenshots dir missing | `mkdir -p GOLD_TACTIC/screenshots` |
| Telegram 401 error | Token λάθος — check `telegram_sender.py` line 19 |
| Τιμές εκτός sanity range | Κανονικό αν market closed — flag και συνέχισε |

---

## REPO

```
https://github.com/aggelosChatziioannou/trading
Branch: main
```

Το repo είναι **public** — no auth needed για clone/pull.
Push (για data sync) χρειάζεται GitHub token αν ο cloud agent δεν έχει SSH key.
