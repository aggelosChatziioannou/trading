# GOLD TACTIC — Cowork Schedule Setup Prompt

Δώσε αυτό το prompt σε ένα Cowork chat για να φτιάξει τα schedules.

---

## PROMPT:

Χρειάζομαι να φτιάξεις scheduled tasks για το trading σύστημα GOLD TACTIC. Θα σου δώσω ακριβώς τι schedule χρειάζεται κάθε ένα.

**ΣΗΜΑΝΤΙΚΟ:** Κάθε schedule τρέχει ένα prompt αρχείο. Θα σου δώσω τα paths. Το prompt για κάθε task βρίσκεται στο αρχείο — κάνε copy-paste ολόκληρο το περιεχόμενο του αρχείου ως prompt του schedule.

### Timezone: EET (Europe/Athens, UTC+3 καλοκαίρι)

---

## WEEKDAY SCHEDULES (Δευτέρα - Παρασκευή)

### 1. Scanner Morning
- **Όνομα:** Gold tactic scanner morning
- **Πότε:** Κάθε μέρα Δευτ-Παρ, **1 φορά στις 08:00 EET**
- **Prompt:** Αντέγραψε ολόκληρο το `C:\Users\aggel\Desktop\trading\GOLD_TACTIC\prompts\scanner_morning_v6.md`

### 2. Analyst PRIME (London Killzone)
- **Όνομα:** Gold tactic analyst PRIME
- **Πότε:** Κάθε μέρα Δευτ-Παρ, **κάθε 15 λεπτά, 08:15 - 11:00 EET**
- **Prompt:** Αντέγραψε ολόκληρο το `C:\Users\aggel\Desktop\trading\GOLD_TACTIC\prompts\analyst_core_v6.md`

### 3. Analyst MIDDAY (Monitoring)
- **Όνομα:** Gold tactic analyst MIDDAY
- **Πότε:** Κάθε μέρα Δευτ-Παρ, **κάθε 45 λεπτά, 11:00 - 15:30 EET**
- **Prompt:** Ίδιο prompt: `analyst_core_v6.md`

### 4. Scanner Afternoon
- **Όνομα:** Gold tactic scanner afternoon
- **Πότε:** Κάθε μέρα Δευτ-Παρ, **1 φορά στις 15:30 EET**
- **Prompt:** Αντέγραψε ολόκληρο το `C:\Users\aggel\Desktop\trading\GOLD_TACTIC\prompts\scanner_afternoon_v6.md`

### 5. Analyst PRIME 2 (NY Open + IB)
- **Όνομα:** Gold tactic analyst NY
- **Πότε:** Κάθε μέρα Δευτ-Παρ, **κάθε 15 λεπτά, 15:45 - 19:00 EET**
- **Prompt:** Ίδιο prompt: `analyst_core_v6.md`

### 6. Analyst EVENING (Late Session)
- **Όνομα:** Gold tactic analyst evening
- **Πότε:** Κάθε μέρα Δευτ-Παρ, **κάθε 30 λεπτά, 19:00 - 21:45 EET**
- **Prompt:** Ίδιο prompt: `analyst_core_v6.md`

### ΟΧΙ schedule 22:00 - 08:00 (dead zone — καμία δραστηριότητα)

---

## WEEKEND SCHEDULES (Σάββατο - Κυριακή)

### 7. Scanner Weekend
- **Όνομα:** Gold tactic scanner weekend
- **Πότε:** Κάθε μέρα Σαβ-Κυρ, **1 φορά στις 10:00 EET**
- **Prompt:** Ίδιο prompt: `scanner_morning_v6.md` (αναγνωρίζει weekend mode αυτόματα)

### 8. Analyst WEEKEND (Crypto)
- **Όνομα:** Gold tactic analyst weekend
- **Πότε:** Κάθε μέρα Σαβ-Κυρ, **κάθε 60 λεπτά, 10:15 - 20:00 EET**
- **Prompt:** Ίδιο prompt: `analyst_core_v6.md` (αναγνωρίζει weekend mode αυτόματα)

### ΟΧΙ schedule 20:00 - 10:00 ΣΚ (χαμηλό volume, δεν αξίζει)

---

## ΣΒΗΣΕ ΤΑ ΠΑΛΙΑ SCHEDULES

Σβήσε αυτά (αν υπάρχουν):
- Gold tactic trading analyst (παλιό, κάθε 20')
- Gold tactic scanner morning (παλιό)
- Gold tactic scanner afternoon (παλιό)

---

## ΣΥΝΟΨΗ

| # | Όνομα | Interval | Ώρες EET | Ημέρες |
|---|-------|----------|----------|--------|
| 1 | Scanner Morning | 1x 08:00 | — | Δευτ-Παρ |
| 2 | Analyst PRIME | κάθε 15' | 08:15-11:00 | Δευτ-Παρ |
| 3 | Analyst MIDDAY | κάθε 45' | 11:00-15:30 | Δευτ-Παρ |
| 4 | Scanner Afternoon | 1x 15:30 | — | Δευτ-Παρ |
| 5 | Analyst NY | κάθε 15' | 15:45-19:00 | Δευτ-Παρ |
| 6 | Analyst Evening | κάθε 30' | 19:00-21:45 | Δευτ-Παρ |
| 7 | Scanner Weekend | 1x 10:00 | — | Σαβ-Κυρ |
| 8 | Analyst Weekend | κάθε 60' | 10:15-20:00 | Σαβ-Κυρ |

**Σύνολο: 8 scheduled tasks**

Κάθε Analyst schedule χρησιμοποιεί **το ίδιο prompt** (analyst_core_v6.md) — η συχνότητα αλλάζει, όχι το prompt. Οι Scanners έχουν ξεχωριστά prompts (morning vs afternoon).

Αν η πλατφόρμα ΔΕΝ υποστηρίζει "μόνο Δευτ-Παρ" ή "μόνο ΣΚ":
- Βάλε τα weekday schedules κάθε μέρα — το prompt αναγνωρίζει weekend mode και κάνει skip
- Βάλε τα weekend schedules κάθε μέρα — σε weekdays θα τρέξει αλλά δεν θα κάνει ζημιά (double coverage)

---

## TESTING

Μετά τη δημιουργία:
1. Ενεργοποίησε ΜΟΝΟ τον Scanner Morning
2. Περίμενε να τρέξει → τσέκαρε Telegram αν ήρθε μήνυμα
3. Αν OK → ενεργοποίησε Analyst PRIME
4. Περίμενε 1-2 κύκλους → τσέκαρε Telegram format
5. Αν OK → ενεργοποίησε ΟΛΑ τα υπόλοιπα
