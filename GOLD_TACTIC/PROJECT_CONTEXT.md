# GOLD TACTIC v7.1 — Project Context

Τελευταία ενημέρωση: 2026-04-17

**Διάβασε αυτό αν ξεκινάς νέο session.** Ενεργή αρχιτεκτονική v7.1 (Telegram UX upgrade).

---

## Τι είναι

Paper trading σύστημα για daily trading (1–2 trades/ημέρα, όχι investing). Τρέχει μέσω **Claude app scheduled tasks** (χρήστης: Pro subscription). Γλώσσα Telegram: Ελληνικά. Broker: IC Markets demo (CySEC, MT5 Raw Spread, EUR, account 52817474).

## Αρχιτεκτονική v7 (2 prompts, 8 schedules)

```
Asset Selector (4x/week) ──► data/selected_assets.json ──┐
                                                          ├─► Market Monitor (20'/40')
                              data/briefing_log.md  ◄────┘    ─► Telegram (Greek)
```

**Μόνο 2 prompts είναι ενεργά:**
- `prompts/asset_selector.md` — σαρώνει 12 assets, διαλέγει top 4
- `prompts/market_monitor.md` — παρακολουθεί τα 4 selected, στέλνει TRS + actions

**12 master assets:** EURUSD, GBPUSD, USDJPY, AUDUSD, XAUUSD, NAS100, SPX500, BTC, ETH, SOL, XRP, DXY (ref).

## 8 Claude App Schedules

| Name | When | Prompt |
|------|------|--------|
| GT Asset Selector AM | Mon–Fri 08:00 | asset_selector.md |
| GT Asset Selector PM | Mon–Fri 15:00 | asset_selector.md |
| GT Asset Selector EVE | Mon–Fri 21:00 | asset_selector.md (+ briefing rotation) |
| GT Asset Selector WE | Sat/Sun 10:00 | asset_selector.md |
| GT Market Monitor Peak | Mon–Fri 08:05–22:00 every 20' | market_monitor.md |
| GT Market Monitor OffPeak | Mon–Fri 22:00–00:00 every 40' | market_monitor.md |
| GT Market Monitor Night | Mon–Fri 00:00–07:40 every 40' | market_monitor.md |
| GT Market Monitor WE | Sat/Sun 10:00–22:00 every 40' | market_monitor.md |

Monitor 08:05 offset αποφεύγει race με Selector 08:00.

## Κρίσιμοι κανόνες

1. **ΟΛΕΣ οι αλλαγές prompt** γίνονται στα `.md` στο `prompts/`. Ο χρήστης τα κάνει copy-paste στα Claude app schedules. Μην κάνεις αλλαγές "στον αέρα".
2. **Canonical data paths** (όχι scripts/): `data/portfolio.json`, `data/selected_assets.json`, `data/briefing_log.md`.
3. **Model:** Sonnet 4.6 για όλα (Pro subscription).
4. **Γλώσσα Telegram:** Ελληνικά πάντα.

## Key files (ενεργά)

| File | Ρόλος |
|------|-------|
| `prompts/asset_selector.md` | Selector prompt |
| `prompts/market_monitor.md` | Monitor prompt |
| `data/master_assets.json` | 12 assets + strategies |
| `data/selected_assets.json` | Τρέχοντα top 4 (auto από Selector) |
| `data/briefing_log.md` | Ημερήσιο Telegram log για coherence |
| `data/portfolio.json` | Balance + open trades (paper) |
| `data/trs_history.jsonl` | TRS scoring history |
| `SCHEDULE_SETUP.md` | Οδηγίες install των 8 schedules |
| `README.md` | Onboarding/overview |

## Archive

Όλα τα legacy v5/v6 prompts/scripts/docs είναι στο `archive/`. Μην τα χρησιμοποιείς. Το Windows Task Scheduler path (`archive/windows_schtasks/`) δεν χρησιμοποιείται — ο χρήστης δουλεύει με Claude app schedules.

---

## Telegram UX v7.1 (2026-04-17)

Ανασχεδιασμός της παρουσίασης όλων των Telegram μηνυμάτων: **pinned Dashboard + chronological stream**, rich HTML, message effects (🔥/🎉), bot reactions (👍🔥💯), smart adaptive monitor tiers.

### Pinned Dashboard contract
- **Owner:** `scripts/dashboard_builder.py` (producer) + `scripts/telegram_sender.py dashboard` (transport).
- **Refreshed από:** Asset Selector STEP 6.5 + Market Monitor STEP 6.7 (πάντα στο τέλος κάθε cycle).
- **Περιεχόμενο:** balance, daily P/L με progress bar, 4 watched assets με TRS + 5 criteria (✅/❌), open trades, next event countdown, sentiment footer.
- **Lifecycle:** Αν δεν υπάρχει pinned → create + pin. Αν υπάρχει → editMessageText (κανένα nέο message).

### Market Monitor tier rules
| Tier | Πότε | Length | Notification | Effect |
|------|------|--------|--------------|--------|
| **A — Heartbeat** | Nothing changed + Δp < 0.3% + καμία HIGH/MED news | ~280 chars | silent | — |
| **B — Delta** | TRS κατηγορία άλλαξε Ή Δp ≥ 0.3% Ή ΝΕΑ HIGH/MED | ~700 chars | normal | — |
| **C — Full signal** | Οποιοδήποτε asset πέρασε TRS ≥ 4 | ~1200 chars | normal | `fire` (μόνο TRS=5) |

### TRS transparency rule
Κανένα TRS δεν εμφανίζεται χωρίς τα 5 canonical criteria ✅/❌ δίπλα: **TF** (timeframe), **RSI**, **ADR**, **News**, **Key** (level). Εφαρμόζεται σε Tier A (inline), Tier B (per-line), Tier C (full descriptions), Dashboard (always).

### News Reasoning Protocol
Σε κάθε cycle ο Monitor αξιολογεί **κάθε νέο σε ΚΑΘΕΝΑ από τα 4 selected** με 🟢HIGH / 🟡MED / ⚪LOW / ⚫NONE. Κάθε HIGH/MED ΠΡΕΠΕΙ να έχει 1-φράση αιτιολόγηση σε παρένθεση. Tier B δείχνει ολόκληρο το news-impact matrix· Tier C εστιάζει στο asset του signal μέσα σε expandable blockquote.

### Effects & reactions
- 🔥 fire effect: Tier C όταν TRS = 5 (private chat only — auto-fallback silent σε groups).
- 🎉 party effect: TP hit reply.
- Bot reactions: `🔥` σε entry_id όταν TP hit, `👎` σε SL hit.

### State
- `data/telegram_state.json` — pinned_dashboard_id, last_selector_id, last_monitor_id, open_trade_entry_ids, cached chat_type.
- `data/trs_current.json` — τρέχον snapshot TRS + 5 criteria per asset (γραμμένο από Monitor, διαβασμένο από dashboard_builder).

### Rate limits
1.2s sleep μεταξύ sequential sends του ίδιου prompt (Telegram: 1 msg/sec same chat).
