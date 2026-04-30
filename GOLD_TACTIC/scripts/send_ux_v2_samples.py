#!/usr/bin/env python3
"""
Send 6 sample messages demonstrating the new v7.2 UX criticality levels.
Sequential send with rate-limit sleeps. Each example has realistic mock data.
Run once to populate the Telegram channel for review.
"""
import time
import subprocess
import sys
from pathlib import Path

SENDER = str(Path(__file__).parent / "telegram_sender.py")

def send(text, silent=False, effect=None, label=""):
    args = ["python", SENDER, "message", text]
    if silent:
        args.append("--silent")
    if effect:
        args.extend(["--effect", effect])
    print(f"\n--- Sending {label} ---")
    r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        print(f"FAIL: {r.stderr[:200]}")
    else:
        print(f"OK msg_id={r.stdout.strip()[:20]}")
    time.sleep(1.4)  # Telegram rate limit

# ── INTRO BANNER ──────────────────────────────────────────────────────────
intro = """🎨 <b>v7.2 UX REDESIGN — 6 Criticality Levels</b>
━━━━━━━━━━━━━━━━━━━━━━

Παρακάτω θα δεις 6 παραδείγματα με αυξανόμενη κρισιμότητα:

❄️ <b>L1 PULSE</b> · Όλα ήρεμα, silent
👁️ <b>L2 WATCH</b> · Κάτι κουνήθηκε, silent
🎯 <b>L3 SETUP</b> · TRS=4, anticipation
🔥 <b>L4 SIGNAL</b> · TRS=5 trade, fire effect
💓 <b>L5 LIVE</b> · Progress milestone reply
🏁 <b>L6 EXIT</b> · TP2 hit closure

<i>Όλα τα demos χρησιμοποιούν mock data για επίδειξη του design system.</i>"""
send(intro, silent=False, label="INTRO")

# ── L1 PULSE ──────────────────────────────────────────────────────────────
l1 = """❄️ <b>21:55</b> · Όλα ήρεμα

🟢 XAU 4/5 · 🟡 EUR 3/5 · 🟡 BTC 3/5 · ⚪ SOL 2/5

📰 News: ίδια εδώ και 18'  ·  ⏰ Next: ECB σε 2h40'
🩺 💚 Healthy  ·  📡 9/9 sources · 23 άρθρα · 78% T1"""
send(l1, silent=True, label="L1 PULSE")

# ── L2 WATCH ──────────────────────────────────────────────────────────────
l2 = """👁️ <b>WATCH</b> · 22:15  ·  ✅ NY Session · Acceptable

🔼 BTC <b>+0.7%</b> @ <code>$76,420</code> → TRS 3→4 (πέρασε ADR)
   ✅TF ✅RSI ✅ADR ✅News ❌Key

📰 <b>ΝΕΟ</b>
• <a href="https://www.coindesk.com/markets/2026/04/29/btc-etf-inflows">"BTC ETF inflows $420M σε μια μέρα"</a> <i>(CoinDesk T1)</i> → 🟢 BTC HIGH (institutional demand)
• <a href="https://www.reuters.com/markets/us/fed-dovish">"Fed dovish tone σε minutes"</a> <i>(Reuters T1)</i> → 🟡 XAU MED (weaker $)

🟢 XAU 4/5 · 🟡 EUR 3/5 · ⚪ SOL 2/5  <i>(stable)</i>

⏰ ECB σε 2h40'  ·  🌡️ F&amp;G 72 · ⚡ RISK_ON
🩺 💚 Healthy

<blockquote expandable>📡 <b>Πηγές</b> (9/9 ok · 23 άρθρα · 78% T1)
✅ ForexLive · CoinDesk · Reuters · Investing · Reddit · ZeroHedge · MarketWatch · Cointelegraph · Finnhub</blockquote>"""
send(l2, silent=True, label="L2 WATCH")

# ── L3 SETUP ──────────────────────────────────────────────────────────────
l3 = """🎯 <b>SETUP · BTCUSD</b> · 4/5 σχηματίζεται · ✅ NY Kill Zone (Optimal)
━━━━━━━━━━━━━━━━━━━━━━

📈 <b>LONG bias</b> @ <code>$76,420</code>  ·  Strategy: TJR Asia Sweep

<b>Τι έχουμε (4/5)</b>
✅ <b>TF</b> — Daily+4H bullish, τάση καθαρή
✅ <b>RSI</b> — 58 (όχι ακόμα υπεραγορασμένο)
✅ <b>ADR</b> — 44% remaining (αρκετός χώρος)
✅ <b>News</b> — CoinDesk T1: ETF inflows υποστηρίζει
❌ <b>Key</b> — λείπει: τιμή 1.8% πάνω από retest <code>$75,500</code>

<b>⏳ Τι περιμένουμε για 5/5</b>
Pullback στο <code>$75,500</code> για retest του breakout level → trigger LONG entry.
ETA: ~30-90' στο NY KZ (15:30-17:30).

🟡 EURUSD 3/5  ·  ⚪ AUDUSD 2/5  ·  ⚪ NAS100 2/5

⏰ ECB σε 2h40'  ·  🌡️ F&amp;G 72 · ⚡ RISK_ON
🩺 💚 Healthy

<blockquote expandable>📰 <b>Νέα που στηρίζουν</b>
• <a href="https://www.coindesk.com/markets/2026/04/29/btc-etf-inflows">"BTC ETF inflows $420M"</a> <i>(CoinDesk T1)</i> → 🟢 HIGH
• <a href="https://www.reuters.com/markets/us/fed-dovish">"Fed dovish tone"</a> <i>(Reuters T1)</i> → 🟡 MED bullish

📡 <b>Πηγές</b> (9/9 · 23 άρθρα · 78% T1)</blockquote>"""
send(l3, silent=False, label="L3 SETUP")

# ── L4 SIGNAL ─────────────────────────────────────────────────────────────
l4 = """🔥 <b>ΣΗΜΑ · BTCUSD</b> · 5/5 ▰▰▰▰▰ · ✅ NY Kill Zone (Optimal)
━━━━━━━━━━━━━━━━━━━━━━

📈 <b>LONG</b> @ <code>$75,520</code>  ·  Risk 2% (20€)  ·  Lot <b>0.026</b>
🎯 TP1 <code>$76,650</code>  +1130 pts  ·  +20€ planned
🎯🎯 TP2 <code>$77,780</code>  +2260 pts  ·  +40€ planned
🛡️ SL  <code>$74,955</code>  −565 pts  ·  −20€ max
⚖️ R:R 1:2  ·  ⏳ Max hold 4h

<b>📊 Γιατί το πήραμε — Όλα τα κριτήρια ✅</b>

✅ <b>TF · Τάση</b>
<i>Η τάση είναι ξεκάθαρη και στις δύο πιο σημαντικές χρονικές κλίμακες — το γράφημα συμφωνεί με τον εαυτό του.</i>

✅ <b>RSI · Δύναμη</b>
<i>Δείκτης δύναμης 58: ούτε υπεραγορασμένο ούτε εξαντλημένο — υπάρχει χώρος για κίνηση.</i>

✅ <b>ADR · Καύσιμο</b>
<i>Διανύθηκε μόνο 56% του ημερήσιου εύρους — υπάρχει καύσιμο για τον στόχο.</i>

✅ <b>News · Ειδήσεις</b>
<i>CoinDesk (T1): θεσμικά λεφτά αγοράζουν BTC ETF — υποστηρίζει την κίνηση.</i>

✅ <b>Key · Σημείο εισόδου</b>
<i>Είμαστε στο $75,520 ακριβώς πάνω σε επίπεδο που η τιμή ιστορικά αντιδράει.</i>

<b>💬 Με μια φράση</b>
Όλα ευθυγραμμισμένα: τάση, χώρος, ειδήσεις, σημείο εισόδου. Κλασικό χαμηλού-ρίσκου setup.

⏰ ECB σε 2h40'  ·  🌡️ F&amp;G 72 · ⚡ RISK_ON
🩺 💚 Healthy  ·  📡 9/9 · 23 άρθρα · 78% T1

<blockquote expandable>📊 <b>Τεχνική ανάλυση</b>
TJR Asia Sweep: σάρωσε το $73,346 PDL, BOS πάνω, retest στο $75,520. Volume 1.2× avg, EMA20 4H acting as support.

📰 <b>Νέα που στηρίζουν</b>
• <a href="https://www.coindesk.com/markets/2026/04/29/btc-etf-inflows">"BTC ETF inflows $420M"</a> <i>(CoinDesk T1)</i> → 🟢 HIGH bullish (institutional demand)
• <a href="https://www.reuters.com/markets/us/fed-dovish">"Fed dovish tone"</a> <i>(Reuters T1)</i> → 🟢 HIGH bullish (weaker $)

📡 <b>Πηγές αυτού του cycle</b>: 9/9 ok · 23 άρθρα · 78% Tier 1
ForexLive · CoinDesk · Reuters · Investing · Reddit · ZeroHedge · MarketWatch · Cointelegraph · Finnhub</blockquote>"""
send(l4, silent=False, effect="fire", label="L4 SIGNAL (fire effect)")

# ── L5 LIVE — Progress milestone reply ────────────────────────────────────
# In real flow this is a reply to entry message; here we send standalone for demo
l5 = """💓 <b>BTCUSD · 50% προς TP1 📈</b>

Τιμή: <code>$76,085</code>  ·  P/L <b>+10.20€</b> (+51%)
Entry $75,520 → TP1 $76,650 · απόμενουν 565 pts
SL ασφαλές στο $74,955

<i>Demo: σε real flow αυτό θα ήταν reply στο entry message για threading.</i>"""
send(l5, silent=True, label="L5 LIVE (progress 50%)")

# ── L6 EXIT — TP2 hit (win) ───────────────────────────────────────────────
l6 = """🏁 <b>BTCUSD · TP2 HIT 🎯🎯 — Runner πέτυχε</b>
━━━━━━━━━━━━━━━━━━━━━━

Exit: <code>$77,780</code>  ·  P/L <b>+39.80€</b> 🟢

<b>Lifecycle</b>
📥 Open @ $75,520 · 16:42
🎯 TP1 @ $76,650 · 17:08 · SL → BE
🎯🎯 TP2 @ $77,780 · 17:34
⏱️ Διάρκεια: 52'  ·  R:R έπιασε 1:2

<b>📊 Νέο portfolio state</b>
💰 Balance <b>1039.80€</b> (+3.98%)
📅 Today: <b>1W-0L</b> · P/L +39.80€  /  στόχος 30€ ✅
📈 Streak: 1W

<b>💬 Take-aways</b>
• Setup ωριμάζει σε kill zone, fundamentals stable
• ETF inflow tier-1 catalyst δούλεψε όπως αναμενόταν
• Επόμενη ευκαιρία: παρακολούθηση BTC pullback σε $77k support"""
send(l6, silent=False, effect="party", label="L6 EXIT TP2 (party effect)")

# ── BONUS: L6 alt — SL hit (loss) ────────────────────────────────────────
l6_sl = """🏁 <b>EURUSD · SL HIT 💀</b>
━━━━━━━━━━━━━━━━━━━━━━

Exit: <code>1.18028</code>  ·  P/L <b>−9.54€</b> 🔴

<b>Lifecycle</b>
📥 Probe @ 1.1824 · 15:50 (TRS=4)
💀 SL @ 1.18028 · 16:23
⏱️ Διάρκεια: 33'

<b>📊 Νέο portfolio state</b>
💰 Balance <b>1030.26€</b> (+3.03%)
📅 Today: <b>1W-1L</b> · P/L +30.26€  /  στόχος 30€ ✅
📉 Streak: 1L

<b>💬 Take-aways</b>
• Probe (1% risk) δούλεψε όπως σχεδιάστηκε — μικρή απώλεια
• ECB upcoming σε 2h δημιούργησε αδυναμία στο EUR
• Δεν θα προσπαθήσουμε re-entry χωρίς νέο TRS=5 setup"""
send(l6_sl, silent=False, label="L6 EXIT SL (alt example)")

# ── CLOSING SUMMARY ───────────────────────────────────────────────────────
summary = """✅ <b>UX v7.2 Demo Complete</b>

7 παραδείγματα στάλθηκαν παραπάνω. Παρατήρησε:
• <b>Visual ladder</b>: από silent ❄️ μέχρι 🔥 fire effect
• <b>Cohesion</b>: ίδια emoji palette, ίδια δομή footer
• <b>Mobile-first</b>: bold hierarchy, code blocks, expandable details
• <b>Group-friendly</b>: όχι emoji-spam, professional vibe
• <b>Plain Greek</b> εξηγήσεις στο L4 SIGNAL για non-traders
• <b>Click-to-copy</b> prices με <code>$75,520</code> blocks

🎨 Πες μου τι σου αρέσει / τι θες αλλαγή για τελική τελειοποίηση πριν live."""
send(summary, silent=True, label="CLOSING SUMMARY")

print("\n=== ALL 9 SAMPLES SENT ===")
