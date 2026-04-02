# Start Trading

Read the full trading prompt from `GOLD_TACTIC/prompts/adaptive_analyst.md` and begin the adaptive trading loop.

## Startup Sequence

1. Read `GOLD_TACTIC/prompts/adaptive_analyst.md` — this is your complete instruction set
2. Read `GOLD_TACTIC/data/portfolio.json` — current balance and stats
3. Read `GOLD_TACTIC/data/trade_state.json` — check for open trades (file may not exist = no open trades)
4. Read last 5 lines of `GOLD_TACTIC/data/session_log.jsonl` — understand last session context
5. Check current time (EET) — determine weekday/weekend mode
6. If open trades found → IMMEDIATE TIER 3 cycle with ladder management
7. If no open trades → run morning scanner logic if first cycle of day, otherwise TIER 3

## LOOP MECHANISM — CRITICAL

After completing EACH cycle, you MUST:

1. Decide next tier and wait time (based on rules in adaptive_analyst.md)
2. Print the terminal summary with next cycle info
3. Tell the user: "Ρώτα με ό,τι θέλεις. Ο επόμενος κύκλος θα ξεκινήσει αυτόματα σε X λεπτά."
4. Use the Bash tool to sleep for the decided wait time: `sleep [SECONDS]`
5. After sleep completes → AUTOMATICALLY start the next cycle (read state, run tier, send Telegram)
6. REPEAT from step 1 — NEVER stop unless:
   - User types STOP
   - EOD reached (21:40 weekday / 19:40 weekend)
   - Error that cannot be recovered

**THIS IS A CONTINUOUS LOOP.** You do NOT wait for user input to start the next cycle. The sleep command IS the timer. After it completes, you run the next cycle immediately.

**If the user sends a message DURING sleep**, the sleep will be interrupted — answer the question, then resume the loop.

## Example Loop Flow

```
[TIER 3 cycle runs]
→ Print summary
→ sleep 600  (10 minutes)
→ [TIER 2 cycle runs]
→ Print summary
→ sleep 900  (15 minutes)
→ [TIER 1 cycle runs]
→ Nothing changed
→ sleep 1800 (30 minutes)
→ [TIER 1 cycle runs]
→ Price moved! Escalate
→ [TIER 2 cycle runs immediately]
→ TRS 4/5!
→ [TIER 3 cycle runs immediately]
→ ...loop continues
```

## Important

- Follow ALL rules in adaptive_analyst.md exactly
- The user can ask questions between cycles — answer with full context
- The user can type commands: STOP, τρέξε τώρα, πιο αργά, πιο γρήγορα, status
- Send Telegram messages according to tier format
- Write session_log.jsonl entry EVERY cycle
- NEVER stop the loop on your own — keep running until STOP or EOD
