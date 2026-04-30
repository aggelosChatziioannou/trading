# GOLD TACTIC v7.2 — Self-Improvement Loop (v1)

**Last updated:** 2026-04-29
**Scope:** Layers 2 + 3 (per-trade reflection + weekly audit + calibration proposer)
**Inspired by:** [CryptoTrade Reflection Analyst](https://github.com/Xtra-Computing/CryptoTrade), [TradingAgents](https://github.com/TauricResearch/TradingAgents), [FinMem](https://github.com/pipiku915/FinMem-LLM-StockTrading)

---

## TL;DR — How the system gets better

```
Every closed trade  →  Layer 2 reflection  →  trade_reflections.jsonl
                                                      ▼
Every Sunday 22:00  →  Layer 3 weekly audit  →  weekly_audit_*.json + Telegram digest
                                                      ▼
Hypothesis detectors  →  calibration_proposals.json (max 2/week)  →  Telegram notif
                                                      ▼
                          USER comes to PC  →  asks Claude to apply
                                                      ▼
Claude reads queue → presents → applies after OK → calibration_log.jsonl + git commit
```

**Critical:** Nothing auto-mutates prompts or configs. All changes are **collaborative** (user + Claude).

---

## Layer 2 — Per-Trade Reflection

### When it runs
Triggered automatically by `prompts/market_monitor.md` STEP 5.9 after `trade_manager.py tick` closes any trade.

### Command
```bash
python GOLD_TACTIC/scripts/reflection_logger.py post-trade <trade_id>
```

### What it produces
One line in `data/trade_reflections.jsonl`:

```json
{
  "trade_id": "EURUSD_probe_20260417T155007",
  "reflected_at": "2026-04-17T20:15:00+03:00",
  "outcome": "loss",
  "r_multiple": -1.0,
  "hold_minutes": 264,
  "tp1_hit_then_be": false,
  "trs_at_entry": 4,
  "criteria_at_entry": {"TF": true, "RSI": true, "ADR": true, "News": false, "Key": true},
  "missing_criteria": ["News"],
  "exit_reason": "max_hold",
  "session_at_entry": "london_kz",
  "asset_class": "forex_major",
  "tag": "probe",
  "attribution_tags": ["entered_with_missing_news_criterion", "high_event_within_2h_of_entry", "max_hold_4h_timeout"],
  "narrative": "Probe LONG EURUSD σε London KZ. χωρίς News. 4h timeout χωρίς TP/SL (-9.54€). HIGH event εντός 2h — pre-event compression πιθανό αίτιο.",
  "lesson_one_liner": "Probes με HIGH event εντός 2h → υψηλός κίνδυνος timeout",
  "calibration_seeds": ["news_embargo_widen", "probe_during_pre_event_block"]
}
```

### Side effect — Telegram L6 EXIT lesson line
Μετά το post-trade reflection, ο Monitor στέλνει 1-line silent reply στο entry message:
```
🧠 Lesson: Probes με HIGH event εντός 2h → υψηλός κίνδυνος timeout
```

### Other CLI modes
- `reflection_logger.py recent --symbol EURUSD --limit 3` — used by `asset_selector.md` STEP 4.5 to inject feedback into next selection
- `reflection_logger.py replay 2026-04-01` — backfill reflections retroactively
- `reflection_logger.py latest-lesson` — print last lesson_one_liner (for L6 EXIT)
- `reflection_logger.py stats` — print outcome counters + calibration seeds

---

## Layer 3 — Weekly Audit + Calibration Proposer

### When it runs
**GT Weekly Audit** Claude schedule, Sunday 22:00 EET. Reads `prompts/weekly_audit.md`.

### What it produces

**Files written:**
- `data/weekly_audit_YYYY_WW.json` (machine readable)
- `data/weekly_audit_YYYY_WW.md` (human readable narrative)
- `data/strategy_scorecard.md` (appended new week section)
- `data/calibration_proposals.json` (queue, max 2 new proposals)
- `data/cycle_log.jsonl` (audit-trail entry)

**Telegram messages:**
1. **Sunday 22:30 — Weekly digest** (~1500 chars). Content:
   - Headline metrics (trades / WR / R / P/L)
   - Per-strategy roll-up με ✅/⏳/🛑 verdicts
   - Anomaly clusters (top 3 recurring failure tags)
   - Top lesson (most common calibration seed)
   - Expandable full per-asset/per-session table
   - Footer: number of new proposals available

2. **Sunday 22:31 — Per-proposal silent notification** (one per generated proposal):
   - Title + category
   - Evidence (n, confidence)
   - Expected impact
   - Affected file (config OR prompt)
   - "🤝 Όταν έρθεις στο PC, ζήτα μου να την εφαρμόσουμε μαζί"

### Hypothesis Detectors (v1 — 3 deterministic)

| # | Detector | min_n | Trigger |
|---|---|---|---|
| 1 | `news_embargo_widen` | 4 | ≥3 losses in last 2 weeks tagged `entered_with_missing_news_criterion` OR `high_event_within_2h_of_entry` AND exit_reason in (max_hold, sl) |
| 2 | `sl_cap_calibrate` | 10 per asset | If ≥40% of trades on that asset hit SL |
| 3 | `session_pruning` | 4 per session | 100% loss rate in any session over ≥4 trades |

**Cap**: Top 2 by `ranking_score` (= count × confidence multiplier). Excess deferred to next week.

---

## Approval Workflow (Collaborative)

### When user is at PC

User starts a Claude session and says something like:
- "διάβασε τις προτάσεις calibration"
- "δες το queue και ας ξεκινήσουμε"
- "εφάρμοσε την πρώτη πρόταση"

### Claude responds

1. **Read queue:**
   ```
   Read: data/calibration_proposals.json
   ```

2. **Present each pending proposal** με:
   - Full title + category
   - Evidence summary (supporting trade IDs, n, confidence)
   - Expected impact
   - Diff target (which file/line)
   - Suggested git commit message

3. **Wait for explicit user OK** for each.

4. **On approval:**
   - **Config-scope** (e.g., `risk_manager.py::ASSET_CONFIG`, `news_embargo.py::PENDING_BEFORE_MIN`):
     - Direct file edit via Edit tool
     - Append to `data/calibration_log.jsonl`:
       ```json
       {"ts": "...", "proposal_id": "P_2026_W17_01", "action": "approved", "applied_by": "user+claude", "diff_applied": "...", "git_commit": "<sha>"}
       ```
     - Move proposal from `queue` → `history` in `calibration_proposals.json`
     - `git add` + `git commit` με message: `chore(calibration): apply P_2026_W17_01 — {title}`

   - **Prompt-scope** (e.g., new STEP in `market_monitor.md`):
     - Edit the `.md` file in repo
     - **Reminder to user:** "Πρέπει να κάνεις copy-paste το νέο STEP στο Claude app schedule «GT Market Monitor Peak» (και τα άλλα 3 monitor schedules)."
     - Mark proposal `pending_user_paste` in queue
     - User confirms when done → move to `history`

5. **On rejection:**
   - Append `calibration_log.jsonl` entry με reason
   - Move from queue → history with `status: "rejected"`

### Post-apply monitoring

Each applied proposal carries `evaluation_window: "2 weeks after apply"` tag. Layer 3 audit στο 2-week mark explicitly compares pre/post metrics. If post-apply regression > pre-apply variance → Telegram alert "🚨 calibration P_X may need rollback".

---

## Schemas Reference

### `data/trade_reflections.jsonl`
Append-only. One line per closed trade. See Layer 2 above.

### `data/weekly_audit_YYYY_WW.json`
```json
{
  "week_id": "2026_W17",
  "period": {"start": "2026-04-21", "end": "2026-04-27"},
  "headline": {"trades": 7, "wins": 4, "losses": 2, "be": 1, "wr_pct": 57.1, "total_pnl_eur": 23.4, "avg_r": 0.42},
  "per_strategy": [{"strategy": "TJR Asia Sweep", "trades": 3, "wins": 2, "losses": 1, "wr_pct": 66.7, "verdict": "INSUFFICIENT_DATA", ...}],
  "per_asset": [...],
  "per_session": [...],
  "anomaly_clusters": [{"tag": "...", "count": 2, "outcome_skew": "..."}],
  "calibration_seed_summary": {"news_embargo_widen": 3, "probe_during_pre_event_block": 2},
  "proposals_generated": ["P_2026_W17_01", "P_2026_W17_02"]
}
```

### `data/calibration_proposals.json`
```json
{
  "queue": [
    {
      "id": "P_2026_W17_01",
      "created": "...",
      "category": "news_embargo",
      "title": "...",
      "evidence": {"supporting_trade_ids": [...], "n": 4, "confidence": "low"},
      "current_value": {...},
      "proposed_value": {...},
      "scope": "config|prompt",
      "diff_target": "scripts/news_embargo.py::PENDING_BEFORE_MIN",
      "expected_impact": "...",
      "evaluation_window": "2 weeks after apply",
      "status": "pending_approval"
    }
  ],
  "history": [...]
}
```

### `data/calibration_log.jsonl`
Append-only audit trail of every applied/rejected proposal.

---

## Telegram Surface

### Pinned Dashboard — Learning Stats panel
Empty-state: `🧠 Learning: αναμονή πρώτου weekly audit (Κυρ 22:00)`
With data:
```
🧠 Learning Stats · 2026_W17 (21 Apr-27 Apr)
   Trades: 7 · WR 57% · R +0.42 · P/L +23.40€
   📊 Best: TJR Asia (3W/3T) · Worst: LK Pilot (1W/3T)
   🔬 Pending: 2 · Last applied: 4d ago
```

### Weekly Digest (Sunday 22:30)
~1500 chars. See `weekly_audit.py::_render_telegram_digest`.

### Per-Proposal Notification (Sunday 22:31, silent)
~400 chars. See `weekly_audit.py::_render_telegram_proposal`.

### L6 EXIT Lesson Line
Optional, follows L6 EXIT message as silent reply:
```
🧠 Lesson: {lesson_one_liner}
```

---

## Troubleshooting

### Reflection logger fails silently
Check `data/reflection_errors.jsonl` for the latest error. Common causes:
- `trade_id` not found in `trade_journal.jsonl` (timing race — tick wrote journal after Monitor stopped looking)
- Calendar parse error — usually safe to ignore (fallback returns no high_event flag)

### Weekly audit doesn't fire Sunday 22:00
1. Check Claude app schedule "GT Weekly Audit" is active
2. Check `cycle_log.jsonl` for `weekly-audit-start` lock contention
3. Manual run: `python GOLD_TACTIC/scripts/weekly_audit.py --week current --telegram`

### Proposals queue gets stale
- Cap is hard-coded at 2/week, so queue grows slowly
- Add proactive Telegram reminder to dashboard panel (already shows pending count)
- v2: stale proposal alert after 14 days — implement when queue >5

### Calibration applied but performance regressed
- Check `calibration_log.jsonl` for the apply entry → get `git_commit`
- `git revert <sha>` to roll back the change
- Add reverted proposal to history with `outcome: "reverted"` for Layer 4 to learn

---

## Verification (after first week of live data)

- [ ] At least 1 closed trade has reflection in `trade_reflections.jsonl`
- [ ] L6 EXIT message in Telegram has `🧠 Lesson:` line
- [ ] Sunday 22:30 weekly digest arrived
- [ ] `weekly_audit_*.json` has non-zero headline metrics
- [ ] If ≥4 trades + 2 fits a detector → at least 1 proposal queued
- [ ] Pinned dashboard Learning Stats panel populated

---

## Future Enhancements (deferred to v2)

- **Layer 1**: per-cycle qualitative reflection in `pilot_notes.md` (auto via STEP 5.E in market_monitor)
- **Layer 4 auto-apply**: low-impact cosmetic proposals auto-apply με 2-week monitoring rollback
- **Layer 5 inline buttons**: Telegram inline keyboard for one-tap approve/reject
- **Layer 6 quarterly research**: `/research-phase` command using WebSearch to ingest external trading insights
- **Same-ticker decision injection in Monitor STEP 4** (currently only Selector STEP 4.5)
- **Performance attribution** (alpha vs spread cost) — borrow from AgenticTrading repo pattern
- **Bayesian confidence updates** with priors from research_notes for proposal ranking
