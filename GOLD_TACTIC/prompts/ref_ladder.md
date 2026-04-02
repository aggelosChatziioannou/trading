# Ladder Risk System v5.0 — Reference

## Dynamic Risk Sizing

**Base risk = 10% του τρέχοντος balance:**

| Balance | Base Risk |
|---------|-----------|
| 500€    | 50€       |
| 1,000€  | 100€      |
| 1,500€  | 150€      |
| 2,000€  | 200€      |

**Streak modifier:**

| Κατάσταση | Modifier | Παράδειγμα (1000€ balance) |
|-----------|----------|---------------------------|
| Κανονικό (0-1 consecutive losses) | 100% | 100€ |
| 2 consecutive losses | 75% | 75€ |
| 3+ consecutive losses | 50% | 50€ |
| Win streak (2+ wins σερί) | 100% (ΟΧΙ πάνω!) | 100€ |

**Επιστροφή μετά streak down:**
- 1 νίκη → ανέβα 1 βαθμίδα (50%→75% ή 75%→100%)
- 2 νίκες → πίσω στο 100%

**Caps:**
- **Max risk: 200€** ανά trade (ποτέ πάνω, ακόμα σε μεγάλο balance)
- **Min risk: 25€** ανά trade (κάτω δεν αξίζει)
- **Daily loss limit: 3× base risk** (π.χ. 300€ σε 1000€ balance)

**Weekend/Late session:** Risk = 50% του κανονικού (pilot strategies, lower conviction)

---

## Confidence-Based Position Sizing

Μετά τον υπολογισμό base risk, ο Agent δίνει **Confidence Score 1-5** βάσει ποιότητας setup:

| Confidence | Πότε | Risk modifier |
|------------|------|---------------|
| 5 — Perfect | Όλα ✅, textbook setup, aligned news | 100% |
| 4 — Strong | 4/5 TRS + context καθαρό | 85% |
| 3 — OK | 3-4/5 TRS, μικρές αμφιβολίες | 70% |
| 2 — Weak | Borderline setup, missing confirmation | 50% |
| 1 — Poor | Αμφίβολο — μάλλον να μην μπεις | Skip |

**Final risk = base_risk × streak_modifier × confidence_modifier**

Παράδειγμα: balance 1000€, 1 consecutive loss, confidence 4:
`100€ × 100% × 85% = 85€ risk`

---

## 33/33/33 Ladder Split

| Step   | R:R | Action          | P&L (100€ risk) | SL μετά          |
|--------|-----|-----------------|-----------------|------------------|
| TP1    | 1:1 | Close 33%       | +33€            | → Entry (BE)     |
| TP2    | 1:2 | Close 33%       | +66€            | → TP1 (+33€ locked) |
| Runner | ∞   | Trail 33%       | +33€+           | Trailing 1× risk |

**P&L Scenarios (100€ example risk):**
- SL hit: −100€
- TP1 only: +33€
- TP1 + TP2: +99€
- Full run 3×: +132€
- Full run 5×: +199€

---

## SL Movement Rules (ΣΙΔΕΡΕΝΙΟΙ)

- **Before TP1:** SL stays at original — never move back
- **After TP1:** SL → Entry immediately (zero risk)
- **After TP2:** SL → TP1 level (profit locked)
- **Runner:** trail = price − 1× risk distance. ΜΟΝΟ forward, never back.

---

## Entry Calculation

```
SL_distance = Asia High − Asia Low (pips or points)
Lot = final_risk / (SL_distance × pip_value)
TP1 = Entry ± 1× SL_distance
TP2 = Entry ± 2× SL_distance
Initial SL = Entry ∓ SL_distance
```

---

## EOD Rule

Last cycle ~21:40 EET 🇬🇷: if open trade AND TP1 not yet hit → close at market.
If TP1 was already hit → runner may stay overnight at discretion.

---

## Portfolio State (διαβάζεις από data\portfolio.json)

Πριν κάθε trade execution διάβασε:
- `balance`: τρέχον balance
- `consecutive_losses`: πόσες συνεχόμενες απώλειες
- `consecutive_wins`: πόσες συνεχόμενες νίκες
- `daily_loss_today`: πόσο έχεις χάσει σήμερα

Αν `daily_loss_today ≥ daily_loss_limit` → NO NEW TRADES για σήμερα.
