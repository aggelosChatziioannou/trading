#!/usr/bin/env python3
"""Send L7 OPEN-TRADE FOCUS samples to Telegram (HOLD / WATCH / EXIT scenarios)."""
import subprocess, sys, os, time
from pathlib import Path

if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

SENDER = str(Path(__file__).parent / "telegram_sender.py")

def send(text, silent=True, effect=None, label=""):
    args = ["python", SENDER, "message", text]
    if silent:
        args.append("--silent")
    if effect:
        args.extend(["--effect", effect])
    print(f"\n--- {label} ---")
    r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
    print(f"OK msg_id={r.stdout.strip()[:5]}" if r.returncode == 0 else f"FAIL: {r.stderr[:100]}")
    time.sleep(1.4)


# ─── INTRO ──────────────────────────────────────────────────────────────
intro = """💼 <b>L7 OPEN-TRADE FOCUS — Νέο Message Format</b>
━━━━━━━━━━━━━━━━━━━━━━

Όταν έχουμε <b>open trade</b>, κάθε cycle θα στέλνει 2 ξεχωριστά messages:

🅰️ <b>Message A</b> — Per-trade status (1 ανά open trade):
• Live P/L + απόσταση από TP/SL
• Ανάλυση κεριών (4ωρο + 1ωρο)
• Νέα ειδικά για το asset (ή "ίδια" αν τίποτα νέο)
• Κρίση: συνδυασμός candles + news + structure
• Συμβουλή: 🟢 ΚΡΑΤΑ / 🟡 ΠΕΡΙΜΕΝΕ / 🔴 ΒΓΕΣ

🅱️ <b>Message B</b> — Other assets + News Matrix:
• Compact view των 3 non-trade assets
• 🔔 Πίνακας &quot;Νέα × 4 Watched&quot; — κάθε νέο × 4 pairs με ↑/↔/—/↓ effect

⚡ <b>ΒΓΕΣ verdict</b> = αυτόματο close του trade με reason <code>advisor_exit</code>

3 παραδείγματα παρακάτω 👇"""
send(intro, silent=False, label="INTRO")


# ─── SCENARIO 1: HOLD (everything aligned) ──────────────────────────────
hold_msg_a = """💼 <b>BTCUSD LONG</b> @ <code>$75,520</code> → <code>$76,180</code> (<b>+0.87%</b>)
P/L: <b>+17.20€</b> · Πρόοδος: 60% προς TP1
🎯 TP1 <code>$76,650</code> · 🎯🎯 TP2 <code>$77,780</code> · 🛡️ SL <code>$74,955</code>
⏳ Διάρκεια: 1h25' · Max hold σε 2h35'

📊 <b>Ανάλυση κεριών</b>
4ωρο: bullish continuation, αυξανόμενο volume +18% vs avg
1ωρο: pullback shallow, holding $75,800 support

📰 <b>Νέα από last cycle</b>
• <a href="https://www.coindesk.com/btc-etf-inflows">"BTC ETF inflows continue $420M week"</a> <i>(CoinDesk T1)</i> → 🟢 SUPPORTIVE
  Institutional flow ευνοεί συνέχιση της ανοδικής κίνησης
• Άλλα νέα: ίδια με προηγούμενο cycle — καμία αλλαγή

🎯 <b>Κρίση</b>
Όλα δείχνουν συνέχιση. Volume αυξάνεται, RSI healthy 62 (όχι overbought ακόμα), news Tier-1 supportive (ETF flows). Είμαστε στη σωστή πλευρά της αγοράς και η δομή κρατάει.

💡 <b>Συμβουλή: 🟢 ΚΡΑΤΑ</b>
ETF flows + bullish 4H structure + healthy RSI — όλα signs to keep, runner θα φτάσει TP1 σύντομα."""
send(hold_msg_a, silent=True, label="SCENARIO 1 — Message A · HOLD")

hold_msg_b = """📊 <b>Άλλα assets που παρακολουθώ</b> · 11:25

🟢 <b>XAU</b> 4/5 · 📈 LONG · <code>3,251.40</code> <i>(+0.18%)</i>
   ✅TF ✅RSI ✅ADR ✅News ❌Key
   <i>💡 1.2% πάνω από retest 3,245 — αναμονή pullback (ETA 30-90')</i>

🟡 <b>EUR</b> 3/5 · 📈 LONG · <code>1.18395</code> <i>(+0.05%)</i>
   ✅TF ❌RSI ✅ADR ✅News ❌Key
   <i>💡 RSI 78 — περιμένουμε pullback πριν entry</i>

⚪ <b>NAS</b> 2/5 · ➖ neutral · <code>26,540</code> <i>(flat)</i>
   ❌TF ✅RSI ✅ADR ❌News ❌Key
   <i>💡 Daily mixed — μη ενεργό</i>

🔔 <b>Νέα × 4 Watched</b>

📰 <a href="https://www.coindesk.com/btc-etf-inflows">"BTC ETF inflows continue $420M"</a> <i>(CoinDesk T1)</i>
   XAU: ⚪ —  EUR: 🟡 ↔  BTC: 🟢 ↑  NAS: 🟡 ↔
   <i>Crypto-specific catalyst, ευνοεί BTC άμεσα. Marginal risk-on bias βοηθά EUR/NAS, ουδέτερο για XAU.</i>

📰 <a href="https://www.reuters.com/fed-dovish">"Fed dovish tone σε FOMC minutes"</a> <i>(Reuters T1)</i>
   XAU: 🟢 ↑  EUR: 🟢 ↑  BTC: 🟢 ↑  NAS: 🟢 ↑
   <i>Weaker $ benefit παντού — XAU strongest play, EUR/NAS supported, BTC small boost.</i>

⏰ ECB σε 4h35'  ·  🌡️ F&amp;G 72 · ⚡ RISK_ON
🩺 💚 Healthy · 9/9 sources"""
send(hold_msg_b, silent=True, label="SCENARIO 1 — Message B · companion + matrix")


# ─── SCENARIO 2: WATCH (mixed signals) ──────────────────────────────────
watch_msg_a = """💼 <b>BTCUSD LONG</b> @ <code>$75,520</code> → <code>$75,650</code> (<b>+0.17%</b>)
P/L: <b>+3.40€</b> · Πρόοδος: 12% προς TP1
🎯 TP1 <code>$76,650</code> · 🎯🎯 TP2 <code>$77,780</code> · 🛡️ SL <code>$74,955</code>
⏳ Διάρκεια: 2h05' · Max hold σε 1h55'

📊 <b>Ανάλυση κεριών</b>
4ωρο: σιδερωμένο range $75,400-$75,800, low volume
1ωρο: doji/spinning tops — αναποφασιστικότητα

📰 <b>Νέα από last cycle</b>
Ίδια με προηγούμενο cycle — δεν εμφανίστηκε νέο που να επηρεάζει το BTCUSD.

🎯 <b>Κρίση</b>
Πλάγια κίνηση χωρίς catalyst. Δεν έχουμε αντίθετο signal αλλά ούτε επιπλέον boost για να σπάσει το range. Ο time premium φεύγει — αν δεν κουνηθεί στις επόμενες 1-2 ώρες, πιθανό max-hold close στο break-even.

💡 <b>Συμβουλή: 🟡 ΠΕΡΙΜΕΝΕ</b>
Setup κρατάει, structure unchanged — δίνουμε χρόνο μέχρι το 4h close. Αν δεν ξεκινήσει κίνηση, max-hold protocol θα κλείσει πιθανότατα BE."""
send(watch_msg_a, silent=True, label="SCENARIO 2 — Message A · WATCH")


# ─── SCENARIO 3: EXIT (auto-close triggered) ────────────────────────────
exit_msg_a = """💼 <b>BTCUSD LONG</b> @ <code>$75,520</code> → <code>$75,150</code> (<b>-0.49%</b>)
P/L: <b>-9.80€</b> · Πρόοδος: -33% (κοντά στο SL)
🎯 TP1 <code>$76,650</code> · 🎯🎯 TP2 <code>$77,780</code> · 🛡️ SL <code>$74,955</code>
⏳ Διάρκεια: 1h45' · Max hold σε 2h15'

📊 <b>Ανάλυση κεριών</b>
4ωρο: bearish engulfing candle κλείνει κάτω από entry — clear weakness
1ωρο: lower highs + lower lows pattern, RSI bearish divergence

📰 <b>Νέα από last cycle</b>
• <a href="https://www.reuters.com/sec-crypto-action">"SEC ξανά κατά crypto exchanges — fresh enforcement"</a> <i>(Reuters T1)</i> → 🔴 CONTRA
  Direct headwind για BTC — risk-off flow αναμενόμενο
• <a href="https://www.coindesk.com/btc-whale-sell">"Whale wallet $80M BTC outflow to exchanges"</a> <i>(CoinDesk T1)</i> → 🔴 CONTRA
  Selling pressure indicator — βραχυπρόθεσμα bearish

🎯 <b>Κρίση</b>
Συνδυασμός: 2 HIGH-tier contra-news + 4ωρο bearish engulfing + 1ωρο RSI divergence + price σπάει $75,300 short-term support. Όλοι οι παράγοντες δείχνουν συνεχιζόμενη πτώση — η αρχική υπόθεση spawn-άρει πια αντίθετα.

💡 <b>Συμβουλή: 🔴 ΒΓΕΣ — αυτόματο κλείσιμο</b>
2× HIGH contra news + bearish 4H structure + RSI bearish divergence = clear exit signal. Καλύτερα small loss τώρα παρά SL hit σε λίγη ώρα."""
send(exit_msg_a, silent=False, label="SCENARIO 3 — Message A · EXIT (advisor)")

# Simulated auto-close emit (όπως θα έκανε το trade_manager close)
exit_close_emit = """🚪 <b>BTCUSD</b> · ADVISOR EXIT — early close (contra signals)
Exit: 75150 · P/L <b>-9.80€</b>
Daily P/L: -9.80€ · Balance: 990.20€"""
send(exit_close_emit, silent=False, label="SCENARIO 3 — Auto-close emit (trade_manager)")


# ─── CLOSING ────────────────────────────────────────────────────────────
closing = """✅ <b>L7 OPEN-TRADE FOCUS — Demo Complete</b>

3 σενάρια στάλθηκαν:
1️⃣ ΚΡΑΤΑ — όλα aligned, runner συνεχίζει
2️⃣ ΠΕΡΙΜΕΝΕ — mixed signals, time premium φεύγει
3️⃣ ΒΓΕΣ — 2× contra news + bearish structure → auto-close

<b>🔧 Files updated:</b>
• <code>prompts/market_monitor.md</code> — STEP 5.11 + 5.12 πλήρως ξανασχεδιασμένα
• <code>scripts/trade_manager.py</code> — νέοι exit reasons (advisor_exit, news_counter)

<b>🚀 Bootstrap action:</b>
1. Τρέξε χειροκίνητα <b>Gt selector am</b> → παράγει selected_assets.json
2. Μετά τρέξε <b>Gt monitor peak</b> → πρώτο live cycle
3. Activate όλα τα schedules

<i>Σε επόμενο update: copy-paste του νέου market_monitor.md στα 4 monitor schedules.</i>"""
send(closing, silent=True, label="CLOSING")

print("\n=== ALL L7 SAMPLES SENT ===")
