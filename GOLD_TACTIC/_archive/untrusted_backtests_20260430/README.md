# Untrusted Backtest Archive — 2026-04-30

## Γιατί αρχειοθετήθηκε αυτός ο φάκελος

Στις 2026-04-30 ο χρήστης δήλωσε ρητά:

> "Το backtesting που έχουμε καταγεγραμμένο δεν ξέρω από τι προέκυψε διότι το σύστημα δεν έχει τεσταριστεί καλά ακόμα. Είμαστε στο 0. Αν υπάρχει κάποιο αρχείο με backtesting πρέπει να σβηστεί. We start fresh."

Όλα τα empirical νούμερα από προηγούμενα backtest runs (BTC 58%, NAS100 IBB 60.5%, AUDUSD 0%, κ.λπ.) **θεωρούνται αναξιόπιστα**. Το σύστημα v7.4 βασίζεται μόνο σε **live trade data** που θα συγκεντρωθούν μέσω του self-improvement loop.

## Κατάσταση του φακέλου

Κατά την αρχειοθέτηση δεν βρέθηκαν συγκεκριμένα `backtest_*.json` ή `scanner_results_*.json` files στο `data/` — έχουν είτε διαγραφεί ήδη είτε δεν δημιουργήθηκαν ποτέ.

**Files που ΔΕΝ μετακινήθηκαν εδώ** (γιατί δεν είναι backtest output):
- `data/strategy_scorecard.md` — περιέχει live trade tracking (1 real trade +€11.70), παραμένει ενεργό
- `data/trade_history.json` — live trade history
- `data/trade_journal.jsonl` — live trade journal
- `data/portfolio.json` — live portfolio state

## Πολιτική για το μέλλον

- `weekly_audit.py` και `daily_observer.py` (νέα Phase 3) **απαγορεύεται** να διαβάσουν οτιδήποτε από αυτόν τον φάκελο
- Η `git revert` ή restore από backup που θα επανέφερνε untrusted backtest data πρέπει να αποτραπεί
- Όλες οι μετρήσεις win rate / expectancy αναφέρονται **μόνο** σε live trade reflections από 2026-04-30 και μετά

## Reset δεδομένων που έγιναν στις 2026-04-30

- `data/edge_weights.json` → fresh, όλα 0
- `data/learned_patterns.json` → fresh, empty arrays
- `data/agent_calibration.json` → fresh, empty overrides
- `data/daily_observations/` → νέος φάκελος, .gitkeep μόνο

Από αυτό το σημείο και μετά, κάθε αξιολόγηση γίνεται live.
