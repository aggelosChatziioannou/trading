# COWORK v5.1 — Emergency News Activation

Δώσε αυτό ΜΟΝΟ στον Analyst schedule:

---

ΑΝΑΒΑΘΜΙΣΗ v5.1 — EMERGENCY NEWS ACTIVATION SYSTEM

Εφάρμοσε ΑΠΟ ΤΟ ΕΠΟΜΕΝΟ SCAN. Δεν αλλάζει τίποτα στον Scanner.

## ΝΕΟ ΑΡΧΕΙΟ: emergency_activations.json

Υπάρχει ήδη στο `GOLD_TACTIC/data/emergency_activations.json`:
```json
{
  "last_seen_scan_timestamp": "",
  "activations": []
}
```

## ΑΛΛΑΓΗ 1: ΝΕΟΣ ΚΥΚΛΟΣ START (βήματα 1-4 πριν από οτιδήποτε)

**1.** Διάβασε `scanner_watchlist.json` → active_today, scan_timestamp, nas100_afternoon

**2.** Διάβασε `emergency_activations.json` → activations, last_seen_scan_timestamp

**3.** Αν scan_timestamp ≠ last_seen_scan_timestamp → **CLEANUP:**
  - Asset ΣΤΟ Scanner's active_today → ΑΦΑΙΡΕΣΕ από emergency (Scanner το πήρε)
  - Asset ΟΧΙ στο active_today ΚΑΙ open_trade=false → ΑΦΑΙΡΕΣΕ
  - Asset ΟΧΙ στο active_today ΚΑΙ open_trade=true → ΚΡΑΤΑ (trade ανοιχτό)
  - NAS100 ΚΑΙ nas100_afternoon=true ΚΑΙ ώρα < 16:30 EET → ΚΡΑΤΑ (afternoon eval pending)
  - **Μετά cleanup:** γράψε `last_seen_scan_timestamp` = τρέχον scan_timestamp στο emergency_activations.json

**4.** `final_active` = scanner active_today + remaining emergency activations
→ Αναλύσε ΜΟΝΟ final_active assets αυτόν τον κύκλο

## ΑΛΛΑΓΗ 2: BREAKING NEWS SCAN (στο NEWS STEP, κάθε κύκλο)

Αν `activations.length < 2` (cap: max 2 ταυτόχρονα):

Για κάθε news item στο news_feed.json, κρίνε με **3 ερωτήματα**:

**Ε1 — IMPACT ≥ 7/10:** Είναι extraordinary;
- ✅ ΝΑΙ: Fed emergency action, war escalation, exchange circuit breaker, major earnings surprise, central bank intervention
- ❌ ΟΧΙ: routine data releases, analyst upgrades, general commentary

**Ε2 — ASSET MAPPING:** Υπάρχει συγκεκριμένο asset + clear direction (LONG/SHORT);
- Πρέπει να αναφέρεις συγκεκριμένο ticker (ΟΧΙ "markets generally")
- Πρέπει να γράψεις 2 προτάσεις: direction + catalyst. Αν δεν μπορείς → ΟΧΙ activation.

**Ε3 — WORTHWHILE NOW:** Tradeable αυτή την ώρα;
- Forex 24/5, crypto 24/7, equities/NAS100 μόνο κατά session
- Weekend: forex/equity αυτόματα αποτυγχάνουν — μόνο crypto μπορεί να περάσει
- Εκτιμώμενο ADR room ≥ 30%

**Αν ΚΑΙ ΤΑ 3 = ΝΑΙ:**
1. Γράψε activation στο emergency_activations.json:
```json
{
  "asset": "XAUUSD",
  "activated_at": "2026-03-30 11:20 EET",
  "reason": "[2 προτάσεις: direction + catalyst]",
  "headline": "[triggering headline]",
  "source": "[source]",
  "open_trade": false
}
```
2. Πρόσθεσε asset στο final_active ΓΙΑ ΑΥΤΟΝ ΤΟΝ ΚΥΚΛΟ
3. Στείλε 🚨 BREAKING ACTIVATION block πριν κανονική ανάλυση

**Αν cap φτάστηκε (2/2):**
Γράψε στο Telegram: `⚠️ Emergency cap reached (2/2) — [headline] noted but not activated`

### Eligible assets για emergency activation:
- Skipped core 5: EURUSD, GBPUSD, NAS100, SOL, BTC
- Extended: XAUUSD, ETH, NVDA, AAPL, TSLA, MSFT, GOOGL, AMD, INTC, COIN, PLTR, AMZN, META
- Οποιοδήποτε asset αναφέρεται ρητά στο news με clear price impact

**Charts για emergency assets:** αν δεν υπάρχουν ήδη:
```bash
python scripts/chart_generator.py [ASSET]
```

## ΑΛΛΑΓΗ 3: TRS GATE ΓΙΑ EMERGENCY ASSETS

| TRS Score | Regular Asset | Emergency Asset |
|-----------|--------------|-----------------|
| 5/5 🔥 | TRADE | **TRADE** |
| 4/5 🟢 | TRADE | **MONITOR ONLY — ΟΧΙ entry** |
| 3/5 🟡 | Wait | Wait |
| 0-2/5 ⬜ | Skip | Skip |

Emergency activation = override Scanner απόφασης → χρειάζεται 5/5 για trade.

## ΑΛΛΑΓΗ 4: open_trade LIFECYCLE

- Όταν **ανοίγεις** trade σε emergency asset → άμεσα γράψε `"open_trade": true` στο emergency_activations.json
- Όταν **κλείνει** trade (TP/SL/EOD) → άμεσα γράψε `"open_trade": false`
- Και τα δύο γράφονται ΠΡΙΝ σταλεί το Telegram του κύκλου

## ΑΛΛΑΓΗ 5: TELEGRAM FORMAT

### 🚨 BREAKING ACTIVATION (στέλνεται ΠΡΙΝ κανονική ανάλυση):
```
🚨 BREAKING ACTIVATION — [ASSET]

📰 "[headline]" ([source], [ώρα EET])
🧠 Reasoning: [2 προτάσεις: direction + catalyst]
📈 Direction: [LONG/SHORT] — [one-line summary]
⚠️ Override: Scanner είχε [ASSET] ως skip — αυτό το news αλλάζει εικόνα

→ Κάνω full TRS analysis τώρα...
━━━━━━━━━━━━━━━━━━━━━━
[full TRS analysis follows]
```

### Footer κάθε Analyst μηνύματος (ανανεωμένο):
```
✅ Active: [asset] (scanner) | [asset] 🚨 (breaking news)
⏭️ Skipped: [asset] ([λόγος]) | ...
```

### Cleanup notification (μετά από Scanner run που αφαιρεί emergency):
```
🧹 Emergency cleared: [ASSET] — Scanner δεν επιβεβαίωσε, no open trade
```

## EDGE CASES

| Σενάριο | Ενέργεια |
|---------|----------|
| Ίδιο asset activated ξανά | Deduplicate — ανανέωσε activated_at + headline |
| Emergency trade open → Scanner runs | open_trade=true → ΚΡΑΤΑ |
| Scanner επιβεβαιώνει emergency asset | ΑΦΑΙΡΕΣΕ από emergency, το Scanner το αναλαμβάνει |
| NAS100 + nas100_afternoon=true + ώρα < 16:30 | ΚΡΑΤΑ, σημείωσε "monitoring only until IBB window" |
| Cap 2/2 | Σημείωσε αλλά ΟΧΙ activation |
| Weekend + forex/equity news | Ε3 αποτυγχάνει φυσικά — ΟΧΙ activation |

## ΑΝΑΝΕΩΜΕΝΗ ΣΕΙΡΑ ΚΥΚΛΟΥ (v5.1)

1. Διάβασε scanner_watchlist.json + emergency_activations.json
2. Cleanup emergency (αν νέος Scanner run)
3. Build final_active
4. SANITY CHECK τιμών
5. price_checker.py → live_prices.json
6. LADDER MANAGEMENT (open trades)
7. NAS100 afternoon check
8. ΑΝΑΛΥΣΗ final_active assets (TRS)
9. NEWS CHECK → **Breaking News Scan** (βλ. ΑΛΛΑΓΗ 2)
10. TRADE EXECUTION (4-5/5 κανονικά, **5/5 μόνο για emergency**)
11. Update open_trade αν χρειάζεται
12. CHARTS (TRS 4+/5 + chart_generator.py για νέα emergency assets)
13. TELEGRAM
14. JOURNAL update

Εφάρμοσε ΑΠΟ ΤΟ ΕΠΟΜΕΝΟ SCAN.
