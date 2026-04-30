# GOLD TACTIC v7.2 — E2E Go-Live Runbook

> Pre-go-live checklist + live kill-zone observation protocol. Follow this **before** considering the system "officially live".

**Updated:** 2026-04-29
**Owner:** User (manual observation required — system runs autonomously, you watch)

---

## Phase 0 — Pre-Flight Checks (5 min before market open)

Run **15 minutes before London open (09:45 EET)** or NY open (15:15 EET) on a normal weekday.

### 0.1 — Code state
```bash
cd C:\Users\aggel\Desktop\trading
git status              # ensure no uncommitted critical files
git log --oneline -5    # confirm latest commit is what you expect
```

### 0.2 — Schedules deployed
Open Claude app → Schedules. Confirm all 8 active and contain the **current** prompt content:
- [ ] GT Asset Selector AM (08:00 weekday) — uses `asset_selector.md` v7.2 (with `--full --summarize`, STEP 6.5 includes health/embargo)
- [ ] GT Asset Selector PM (15:00 weekday)
- [ ] GT Asset Selector EVE (21:00 weekday)
- [ ] GT Asset Selector WE (10:00 weekend)
- [ ] GT Market Monitor Peak (every 20' weekday 08:05–22:00)
- [ ] GT Market Monitor OffPeak (every 40' weekday 22:00–00:00)
- [ ] GT Market Monitor Night (every 40' weekday 00:00–07:40)
- [ ] GT Market Monitor WE (every 40' weekend 10:00–22:00)

**If a prompt is outdated** (no STEP 2.7 / 4.85 / 4.95 / 5.A / 5.D), copy-paste the current `.md` content from `GOLD_TACTIC/prompts/` into that schedule.

### 0.3 — Pipeline scripts exist + executable
```bash
python GOLD_TACTIC/scripts/data_health.py --line     # expect: "💚 Data: N/M fresh" (or 🟡/🔴 with reason)
python GOLD_TACTIC/scripts/news_embargo.py --line    # expect: "📅 News: clear" (or upcoming countdown)
python GOLD_TACTIC/scripts/news_scout_v2.py --light --summarize   # expect: 5-23 articles, 9/9 sources ok
python GOLD_TACTIC/scripts/trade_manager.py list     # expect: "No open trades" (post-cleanup)
python GOLD_TACTIC/scripts/trade_manager.py header   # expect: empty string
```

All 5 must succeed without exceptions. If any fail → fix before proceeding.

### 0.4 — Portfolio sane
```bash
python -c "import json; d=json.load(open('GOLD_TACTIC/data/portfolio.json')); print(d['current_balance'], d['risk_per_trade_pct'], d['max_concurrent_trades'], d['max_daily_loss_eur'])"
```
Expected: `1000.0 2.0 2 40.0`. If different → check post-cleanup state.

### 0.5 — Telegram channel reachable
```bash
python GOLD_TACTIC/scripts/telegram_sender.py message "🧪 E2E pre-flight test — $(date +%H:%M)" --silent
```
Expect: Telegram channel receives the message within 2 seconds.

### 0.6 — Backups in place
- [ ] `archive/cleanup_2026-04-29/` exists with backup of orphans
- [ ] `git log` shows the cleanup commit (or run `/ultrareview` first)

---

## Phase 1 — First Selector Run (08:00 EET on a weekday)

### Observation goals
1. Selector fetches all 12 assets
2. News scout (full mode) returns 30+ articles across multiple sources
3. Selected 4 assets are reasonable (correlations explained, mixed asset classes preferred)
4. Telegram message arrives in Greek, properly formatted, with all source links clickable
5. Pinned dashboard updates in place (no duplicate dashboards)
6. `selected_assets.json` written with timestamp

### Pass criteria
- [ ] Selector message arrived within 60s of 08:00 EET
- [ ] Message has a 📡 sources footer showing 8+ ok sources
- [ ] At least 3 of 4 selected assets have **tier-1 source coverage** (Reuters / Bloomberg / ForexLive / CoinDesk)
- [ ] Pinned dashboard `🩺 health` line shows `💚 Selector` + freshly green
- [ ] If HIGH event today → `📅 Next HIGH:` line in dashboard footer

### Fail signals
- ❌ Selector takes >120s — likely Finnhub / Investing.com timeout, but should still complete (graceful degradation)
- ❌ Telegram has bare URLs (not `<a href>`) — prompt didn't apply Common Rule #11
- ❌ Dashboard duplicated (new pinned message every cycle) — `telegram_state.json` lost; investigate

---

## Phase 2 — Monitor Cycles (every 20' during peak, 08:05–22:00)

### Observation goals (across 5 consecutive cycles)
1. Each cycle runs in under 90s
2. Tier A heartbeats are silent, ~450 chars, with sources footer
3. Tier B/C messages have expandable sources blockquote with 6+ sources
4. Stale data detection works: if you manually rename `data/quick_scan.json` → next Monitor should show 🔴 banner
5. News embargo: if there is a HIGH event in 30min → `🛑 EMBARGO PENDING` banner appears
6. Pinned dashboard updates every cycle

### Pass criteria (after 5 cycles)
- [ ] No duplicate dashboards (always 1 pinned)
- [ ] All news links clickable
- [ ] Sources footer present in **every** Tier (A/B/C)
- [ ] Health line in dashboard updates each cycle (Monitor age = 0-20 min)
- [ ] Trade header empty (no open trades yet)

### Stale-data injection test
```bash
# Simulate Monitor failure: hide quick_scan
mv GOLD_TACTIC/data/quick_scan.json GOLD_TACTIC/data/quick_scan.json.hidden
# Wait for next Monitor cycle
# Expect: dashboard shows 🔴 Data N/8 STALE; Tier A line shows 🔴 Data: ...
# Restore:
mv GOLD_TACTIC/data/quick_scan.json.hidden GOLD_TACTIC/data/quick_scan.json
```

---

## Phase 3 — First Tier C Signal (within first kill-zone)

### Setup
The first London Kill Zone (10:00–12:00 EET) or NY Kill Zone (15:30–17:30 EET) is the most likely time for a Tier C signal. Watch all Monitor cycles in this window.

### Observation goals
1. When TRS reaches 4 (probe) or 5 (full) in optimal KZ → Tier C message
2. Auto-open writes to `data/trade_state.json` + `data/portfolio.json`
3. Telegram receives Tier C message + immediate 📥/🧪/🔥 reply with trade details
4. Open-trades header appears in next cycle's Tier A/B/C messages
5. Pinned dashboard's "Open trades" section populates

### Pass criteria (first signal)
- [ ] Tier C message has all 5 criteria visible (not just TRS number)
- [ ] Lot size respects 2% risk (or 1% for probe)
- [ ] SL within asset's `max_sl_pct_4h` cap (e.g., BTC ≤ 1.0%, EURUSD ≤ 0.30%)
- [ ] `trade_manager.py list` shows the new trade
- [ ] Dashboard "Open" section shows the trade with live P/L
- [ ] If TRS=5 → Tier C had 🔥 fire effect (private chat) or silent fallback (group chat)

### Fail signals
- ❌ Tier C signal in `off` session (Asian hours) — gate violation
- ❌ Trade opened with SL > cap → Risk guard not enforced
- ❌ 3rd trade opened despite max_concurrent=2 → portfolio gate not enforced
- ❌ Tier C without auto-open call → STEP 5.7 skipped

---

## Phase 4 — Trade Lifecycle (during open trade hold time)

### Observation goals (next 4 hours after open)
1. Every Monitor cycle runs `trade_manager.py tick`
2. Progress milestones (25/50/75% to TP1) emit silent replies
3. If price hits TP1 → 🎯 + 🔄 BE upgrade message
4. If price retraces to entry post-TP1 → 🛡️ BE exit (P/L=0)
5. If TP2 hit → 🎯🎯 close
6. If 4h elapses without TP/SL hit → ⌛ max-hold close
7. `trade_journal.jsonl` appends final state

### Pass criteria (lifecycle)
- [ ] Each progress milestone fires only ONCE per trade (no spam)
- [ ] TP1 hit moves SL to entry — visible in next dashboard cycle
- [ ] Trade closes for one of: tp2 / be / sl / max_hold
- [ ] Final P/L logged in journal
- [ ] Portfolio balance updates correctly
- [ ] Pinned dashboard "Open" section empties

---

## Phase 5 — Daily Stop Test (synthetic — only if comfortable)

### Setup
**Optional**, only after at least one real trade lifecycle observed. Manually edit `portfolio.json` to set `daily_pnl: -41.0` (just below `max_daily_loss_eur=40`).

### Observation goals
1. Next Monitor cycle detects daily stop hit
2. Tier A/B messages show `🛑 Daily Stop ενεργό`
3. Tier C signal blocked even if TRS=5
4. Pinned dashboard shows the daily stop banner

### Pass criteria
- [ ] No new trades opened
- [ ] Existing open trades continue tick() normally
- [ ] Banner remains until you reset `daily_pnl` to 0

### Cleanup
```bash
python -c "import json; d=json.load(open('GOLD_TACTIC/data/portfolio.json')); d['daily_pnl']=0.0; json.dump(d,open('GOLD_TACTIC/data/portfolio.json','w'),indent=2)"
```

---

## Phase 6 — Session-End Verification (22:00 EET)

After the EVE Selector runs (21:00) and final Monitor cycle:

### Pass criteria
- [ ] `briefing_log.md` rotated correctly (yesterday's entries archived)
- [ ] All open trades either closed or have valid `max_hold_expires` for tomorrow
- [ ] Dashboard reflects end-of-day state
- [ ] No exception logs in `runner_log.txt` for any cycle

---

## ❗ Failure Recovery

### If Monitor stops running
1. Check Claude app schedule — did it pause? Reactivate.
2. Check `data/runner_log.txt` for last error
3. Manually run a cycle: paste Monitor prompt into a fresh Claude session

### If trade_state.json corrupts
1. `cp GOLD_TACTIC/data/trade_state.json GOLD_TACTIC/data/trade_state.json.bad`
2. Inspect for valid JSON
3. If unrecoverable: restore from `archive/cleanup_2026-04-29/trade_state.json.backup` or write `{"open_trades":[],"last_tick":"<now>"}`

### If pinned dashboard duplicates
- `data/telegram_state.json` lost the `pinned_dashboard_id`
- Manually delete the stale pinned messages in Telegram
- Next dashboard call will create a new one

### If embargo blocks legitimate trades for too long
- Check `data/economic_calendar.json` for stale events still showing as "today"
- Manually run `python GOLD_TACTIC/scripts/economic_calendar.py` to refresh
- If event is genuinely active → respect the embargo (don't override unless you have strong reason)

---

## 📊 Go-Live Decision Criteria

**Declare "officially live" when ALL of:**
- [ ] Phases 0-2 passed on a weekday
- [ ] At least 1 Tier C signal observed (Phase 3) with auto-open success
- [ ] At least 1 full trade lifecycle observed (Phase 4) — open → tick → close
- [ ] Stale-data injection test passed
- [ ] No critical bugs identified during 1-week paper run
- [ ] At least 5 successful selector cycles + 100 successful monitor cycles

**Soak time: 5 trading days minimum** before considering moving to live broker (Phase 4 of TIER 1 → TIER 4 plan).

---

## 📝 Test Run Log Template

Copy-paste into `data/e2e_test_log.md` while observing:

```
## E2E Test Run — [DATE]

### Phase 0 (08:00)
- Pre-flight: ✅ all 5 checks pass
- Schedules: ✅ all 8 deployed with current prompts
- Telegram test message: ✅ received in 1.2s

### Phase 1 (08:00 Selector)
- Run time: 47s
- Articles fetched: 56
- Selected: EURUSD (9), AUDUSD (8), BTC (8), NAS100 (7)
- Sources ok: 9/9
- Health line: 💚 / 💚 / 💚
- Issue: [none / details]

### Phase 2 (08:05 → 12:00 Monitor cycles, every 20')
- Total cycles: 12
- Tier A: 9, Tier B: 3, Tier C: 0
- Avg cycle time: 38s
- Stale injection test: ✅ banner appeared in cycle #6
- Issues: [list]

### Phase 3 (kill zone signals)
- 1st Tier C: 11:25 EET, BTC TRS=4 PROBE, lot=0.02
- Auto-open success: ✅
- Header in next cycle: ✅
- Issues: [list]

### Phase 4 (trade lifecycle)
- BTC PROBE: opened 75150, TP1 hit 11:48 → BE upgrade
- TP2 hit 12:14 → +9.80€
- Lifecycle: ✅ clean
- Issues: [list]

### Verdict
- [ ] PASS — declare live
- [ ] PASS WITH NOTES — track issues for TIER 2
- [ ] FAIL — fix before re-attempting
```

---

## 🚀 After Successful E2E

1. Commit + push all current state to GitHub (`git add -A && git commit -m "feat: GOLD TACTIC v7.2 production-ready post-E2E"`)
2. Tag the release: `git tag v7.2.0-production`
3. Move to TIER 2 improvements (regime detector, Twitter integration, performance tracking)
4. Document any issues found into `docs/known_issues_v7.2.md`
