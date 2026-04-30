# GOLD TACTIC v7.2 — Project Context

Τελευταία ενημέρωση: 2026-04-29

**Διάβασε αυτό αν ξεκινάς νέο session.** Ενεργή αρχιτεκτονική v7.2 (full trade lifecycle + news transparency v3).

---

## Τι είναι

Paper trading σύστημα για **daily trading** (1–2 trades/ημέρα, όχι swing/investing). Τρέχει μέσω **Claude app scheduled tasks** (χρήστης: Pro subscription, Sonnet 4.6 only). Γλώσσα Telegram: Ελληνικά. Broker reference: IC Markets demo (CySEC, MT5 Raw Spread, EUR, account 52817474).

Κεφάλαιο 1000€, στόχος **30€ base / 50€ stretch / -40€ daily stop**.

## Αρχιτεκτονική v7.2 (2 prompts, 8 schedules)

```
Asset Selector (4x/week) ──► data/selected_assets.json ──┐
                                                          ├─► Market Monitor (20'/40')
                              data/briefing_log.md  ◄────┘    ─► Telegram (Greek)
                                                              ─► trade_manager (open/tick/close/launch)
```

**Μόνο 2 prompts είναι ενεργά:**
- `prompts/asset_selector.md` — σαρώνει 12 assets, διαλέγει top 4 (`--full --summarize`)
- `prompts/market_monitor.md` — παρακολουθεί τα 4 selected, στέλνει TRS + actions, διαχειρίζεται open trades (`--light`)

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
2. **Canonical data paths** (όχι scripts/): `data/portfolio.json`, `data/selected_assets.json`, `data/briefing_log.md`, `data/trade_state.json`, `data/trade_journal.jsonl`.
3. **Model:** Sonnet 4.6 για όλα (Pro subscription).
4. **Γλώσσα Telegram:** Ελληνικά πάντα.
5. **Working dir:** `C:\Users\aggel\Desktop\trading` (hardcoded σε prompts).

## Key files (ενεργά)

| File | Ρόλος |
|------|-------|
| `prompts/asset_selector.md` | Selector prompt (296 LOC) |
| `prompts/market_monitor.md` | Monitor prompt (970+ LOC) |
| `data/master_assets.json` | 12 assets + strategies |
| `data/selected_assets.json` | Τρέχοντα top 4 (auto από Selector) |
| `data/briefing_log.md` | Ημερήσιο Telegram log για coherence |
| `data/portfolio.json` | Balance + closed trade stats (paper) — fresh από 2026-04-29 |
| `data/trade_state.json` | Open trades (atomic writes) |
| `data/trade_journal.jsonl` | Append-only closed-trade log (audit trail) |
| `data/correlation_map.json` | 4 clusters, max 2/cluster blocking |
| `data/telegram_state.json` | pinned_dashboard_id + msg state |
| `data/trs_current.json` | Current TRS snapshot per asset |
| `data/news_feed.json` | News v3 output με tier/sources/url |
| `SCHEDULE_SETUP.md` | Οδηγίες install των 8 schedules |
| `README.md` | Onboarding/overview |

## Core Scripts (12,134 LOC συνολικά)

| Script | Ρόλος |
|--------|-------|
| `trade_manager.py` (937 LOC) | open/tick/close/launch/header/suggest CLI + library |
| `risk_manager.py` (902 LOC) | ASSET_CONFIG (4h SL caps), suggest_tp_sl, validate_sl_distance |
| `news_scout_v2.py` (480 LOC, **v3**) | 10 πηγές: Finnhub + CryptoPanic + Google News + ForexLive + Investing + ZeroHedge + CoinDesk + Cointelegraph + MarketWatch + Reddit (×4) |
| `quick_scan.py` (610 LOC) | RSI/EMA/ADR/regime από TV MCP ή yfinance |
| `dashboard_builder.py` (366 LOC) | Pinned dashboard producer |
| `telegram_sender.py` (514 LOC) | Telegram API transport |
| `trs_calculator.py` (748 LOC) | Algorithmic TRS baseline (AI override ±1) |
| `session_check.py` (125 LOC) | Kill zone awareness |
| `economic_calendar.py` (186 LOC) | HIGH impact events |
| `news_impact.py` (298 LOC) | Pre/post snapshot tracker |

## Archive

Όλα τα legacy v5/v6 prompts/scripts/docs είναι στο `archive/`. Μην τα χρησιμοποιείς.

`archive/cleanup_2026-04-29/` περιέχει pre-go-live cleanup backups (orphan EURUSD probe + scripts/portfolio.json).

---

## v7.2 Trade Lifecycle Features (2026-04-17)

### Probe / Full / Confirm Sizing
| Tag | Trigger | Risk |
|-----|---------|------|
| `full` | TRS=5 fresh setup | 2% (20€) |
| `probe` | TRS=4 σε optimal kill-zone | 1% (10€) |
| `confirm` | TRS=5 με υπάρχον active probe | 1% (+half-position) |

Combined probe+confirm = 2%. Tag-specific 📥/🧪/🔥 Telegram headers.

### TP1 → BE → TP2 Runner
- TP1 hit → SL → entry (break-even), `tp1_hit=true`, `be_moved=true`. ΔΕΝ κλείνει.
- TP2 hit → close runner (🎯🎯).
- Επιστροφή στο entry post-TP1 → 🛡️ BE exit (P/L=0, neutral counter).

### 🚀 Launch Protocol (Rocket Extension)
Manual `launch <trade_id> --reason <news|momentum|tp2_runner|manual>` ή opt-in `--auto-launch` στο open. Επεκτείνει TP/SL/timeout. Διατηρεί original fields για audit.

### TP/SL 4h Caps (Hard-block)
`validate_sl_distance(asset, entry, sl)` block-άρει swing-scale stops. Caps ANA asset: BTC 1.0%, XAUUSD 0.50%, EURUSD 0.30% κλπ. STEP 5.6 στον Monitor.

### Correlation Cluster Blocking
`correlation_map.json` 4 clusters, max 2/cluster. Blocks 3rd in same cluster.

### 4 Gates (STEP 4.8 Monitor)
Daily stop (-40€) / max concurrent (2) / kill zone / max hold (4h).

---

## Telegram UX v7.2 (refined από 2026-04-17 + sources transparency 2026-04-29)

### Pinned Dashboard contract
- **Owner:** `scripts/dashboard_builder.py` (producer) + `scripts/telegram_sender.py dashboard` (transport).
- **Refreshed:** Selector STEP 6.5 + Monitor STEP 6.7 (πάντα στο τέλος κάθε cycle).
- **Περιεχόμενο:** balance, daily P/L με progress bar, 4 watched assets με TRS + 5 criteria, open trades με live P/L+countdown, next event countdown, session badge, daily-stop banner, sentiment footer.
- **Lifecycle:** create+pin OR editMessageText (κανένα νέο message).

### Market Monitor tier rules
| Tier | Πότε | Length | Notification | Effect |
|------|------|--------|--------------|--------|
| **A — Heartbeat** | Nothing changed + Δp < 0.3% + καμία HIGH/MED news | ~450 chars | silent | — |
| **B — Delta** | TRS κατηγορία άλλαξε Ή Δp ≥ 0.3% Ή ΝΕΑ HIGH/MED | ~700 chars | normal | — |
| **C — Full signal** | Asset πέρασε TRS ≥ 4 (acceptable KZ) ή ≥ 5 (off) | ~1200 chars | normal | `fire` (μόνο TRS=5) |

### TRS transparency rule
Κανένα TRS δεν εμφανίζεται χωρίς τα 5 canonical criteria ✅/❌ δίπλα: **TF · RSI · ADR · News · Key**. Εφαρμόζεται σε ΟΛΑ τα tiers + Dashboard.

### News Reasoning Protocol (STEP 5.A)
Σε κάθε cycle ο Monitor αξιολογεί **κάθε νέο σε ΚΑΘΕΝΑ από τα 4 selected** με 🟢HIGH / 🟡MED / ⚪LOW / ⚫NONE. **Source tier awareness:** ένα Reuters T1 contra-news = ❌ News criterion (×1.5 weight); χρειάζονται 2+ tier-2 για ίδιο effect. Reddit posts = social sentiment, όχι fundamental.

### Sources Transparency Footer (STEP 5.D — NEW 2026-04-29)
ΥΠΟΧΡΕΩΤΙΚΟ σε ΟΛΑ τα tiers (A/B/C). Δείχνει `sources_polled` + `sources_summary` + tier distribution. Failed sources πάντα ορατά (όχι μόνο τα ok). Όλα τα άρθρα clickable HTML links.

### Open-Trades Header (STEP 4.95)
`trade_manager.py header` HTML block prepended σε ΚΑΘΕ Tier A/B/C message αν υπάρχουν open trades. Χρήστης πάντα βλέπει live positions.

### Effects & reactions
- 🔥 fire effect: Tier C TRS=5 (private chat only — auto-fallback silent σε groups).
- 🎉 party effect: TP hit reply.
- Bot reactions: 🔥 σε entry_id όταν TP hit, 👎 σε SL hit.

### State files
- `data/telegram_state.json` — pinned_dashboard_id, last_selector_id, last_monitor_id, open_trade_entry_ids, cached chat_type.
- `data/trs_current.json` — current TRS snapshot per asset (Monitor → Dashboard).

### Rate limits
1.2s sleep μεταξύ sequential sends στο ίδιο chat (Telegram: 1 msg/sec).

---

## Τι Έχει Γίνει vs Pending

### ✅ DONE σε v7.2
- Phase A — Core lifecycle (`trade_manager.py`, market_monitor STEP 5.7/5.8/4.95, dashboard open-trades section)
- Phase B2 — Correlation cluster blocking
- Probe/Full/Confirm tag system + risk-aware sizing + risk guard
- TP1 → BE → TP2 Runner + BE exit
- Launch Protocol (manual + auto-launch)
- TP/SL 4h caps + validate_sl_distance hard block
- Daily stop / max concurrent / kill zone / max hold gates
- Telegram UX (Dashboard + Tier A/B/C + reactions/effects + open-trades header)
- News v3 (10 sources + tier system + sources transparency footer)
- Pre-go-live cleanup (stale EURUSD probe + orphan scripts/portfolio.json)

### ⏳ DEFERRED (TIER 1 next steps)
- B1 — News Embargo (T-30/T-0/T+5 για HIGH events)
- B3 — Regime Detector (Trend/Range/Volatile/News badge)
- E2E live test in kill zone

### 🔮 Future (TIER 4)
- OANDA API integration (real-time + auto-execution)
- Live broker bridge (paper → IC Markets MT5)
