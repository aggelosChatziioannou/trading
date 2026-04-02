#!/usr/bin/env python3
"""Send analyst message for 16:03 EET cycle"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from telegram_sender import send_message

msg1 = """📊 <b>GOLD TACTIC ANALYST</b> — 16:03 EET 🇬🇷
💼 1008.7€ | 📊 2W-0L (100%) | 🎯 Ρίσκο/trade: 15.1€
⚠️ Max σήμερα: -50.4€ | Χρησιμοποιημένο: 0€ (0%)
🔥 Streak: 2 νίκες | Σήμερα: +0€
⚠️ Μία μόνο πηγή τιμών
━━━━━━━━━━━━━━━━━━━━━━

🔄 <b>ΤΙ ΑΛΛΑΞΕ</b> (vs 15:52):
• EURUSD: -5 pips (1.1511→1.1506), TRS 1→1
• GBPUSD: -9 pips (1.3246→1.3237), H4 RSI 73→76.6 (πιο overbought)
• NAS100: αμετάβλητο στο cash (22.953), NQ futures 23.418 (+465 pts pre-market 🔥)
• DXY: 100.25→100.19, συνεχίζει κάτω
• XAUUSD: ~4.580→4.604 (+24 pts), ανεβαίνει
• Νέα: Καμία νέα είδηση
→ Εκτίμηση: Αγορά σε αναμονή — NAS100 IBB ανοίγει σε 27 λεπτά. Pre-market bid +465 pts ισχυρό σήμα.

🟡 <b>ΠΑΡΑΚΟΛΟΥΘΗΣΗ</b>
━━━━━━━━━━━━━━━━━━━━━━

⏰ <b>NAS100</b> — 22.953 (NQ futures: 23.418) — <b>IBB ΑΝΟΙΓΕΙ 16:30</b>
📊 Alignment: Daily BEAR | 4H OVERSOLD | 1H BEAR → ALIGNED_BEAR

✅ RSI 4H 17.9 — extreme oversold (σπάνιο, σήμα πιθανής ανάκαμψης)
✅ Pre-market NQ +465 pts από χθεσινό κλείσιμο — ισχυρό bid
✅ Ceasefire news (Trump/Iran) → risk-on, ευνοεί stocks
❌ IBB δεν έχει σχηματιστεί — αναμένουμε 16:30-17:30
❌ Entry μόνο μετά 17:30 αν IB σπάσει

⚡ ΑΠΟΦΑΣΗ: ΑΝΑΜΟΝΗ — IBB window σε 27 λεπτά
🎯 PROXIMITY: [░░░░░░░░░░] 0% — window δεν έχει ανοίξει
📏 ΑΠΟΣΤΑΣΗ:
├ Trigger: IB High +10pts (μετά 17:30)
├ Τι λείπει: Σχηματισμός IB + breakout confirmation
└ Εκτίμηση: ΚΟΝΤΑ — σε ~2 κύκλους
⏭️ 16:30 → σημείωσε IB High/Low | 17:30 → τσέκαρε breakout"""

msg2 = """📉 <b>EURUSD</b> — 1.1506 — Ετοιμότητα 1/5 ⬜
📊 Alignment: Daily BEAR | 4H BULL (RSI 73.1) | 1H BULL → PARTIAL ⚠️

✅ Ημέρα πτωτική — Daily BEAR (RSI 42.2, κάτω SMA50)
❌ 4H ανεβαίνει post-CPI (RSI 73.1) — πρέπει να εξαντληθεί
❌ Δεν υπήρξε bearish BOS &lt;1.1480
❌ DXY πέφτει (100.19) — ευνοεί EURUSD UP, εναντίον SHORT

⚡ ΑΠΟΦΑΣΗ: ΑΝΑΜΟΝΗ — H4 BULL εμποδίζει, ADR 82.9%
🎯 PROXIMITY: [▓░░░░░░░░░] 20%
📏 Trigger: BOS κλείσιμο &lt;1.1480 | Απόσταση: 26 pips
└ Εκτίμηση: ΜΑΚΡΙΑ — πιθανόν αύριο
⏭️ Αν 4H κλείσει &lt;1.1480 → TRS πηγαίνει 3-4/5

━━━━━━━━━━━━━━━━━━━━━━

📉 <b>GBPUSD</b> — 1.3237 — Ετοιμότητα 1/5 ⬜
📊 Alignment: Daily BEAR | 4H BULL (RSI 76.6 overbought) → PARTIAL ⚠️

✅ Ημέρα πτωτική — Daily BEAR (RSI 40.0)
❌ H4 BULL RSI 76.6 — overbought αλλά ακόμα BULL direction
❌ ADR 85.9% σχεδόν εξαντλημένο
❌ DXY πέφτει — ευνοεί GBP, εναντίον SHORT
🚫 Correlation block με EURUSD (ίδιο group)

⚡ ΑΠΟΦΑΣΗ: ΑΝΑΜΟΝΗ — H4 BULL + ADR + correlation block
🎯 PROXIMITY: [▓░░░░░░░░░] 20%
└ Εκτίμηση: ΜΑΚΡΙΑ — ADR τελειωμένο

⏳ <b>STANDBY XAUUSD</b> — 4.604 (Iran premium ↑+24)
→ NY Momentum window: ⏰ 17:30 EET. Ανεβαίνει ήδη. Αναμονή.

📰 Καμία νέα είδηση από τον προηγούμενο κύκλο.
Κλίμα: Risk-on (ceasefire hope, DXY πέφτει, NQ pre-market ισχυρό)

━━━━━━━━━━━━━━━━━━━━━━

🔬 <b>PILOT SHADOW</b>
• Κανένα ανοιχτό shadow
• NAS100 IBB: ⏰ 16:30 — NQ +465 pts, RSI 4H 17.9 → shadow LONG candidate μετά 17:30
• XAUUSD NY Momentum: ⏰ 17:30 — τιμή ήδη ανεβαίνει (4.604)
• Γιατί δεν άνοιξε shadow: Windows δεν έχουν ανοίξει

💲 DXY: 100.19 (BULL daily, BEAR 4H ↓)
   └ EURUSD ⬆️ | GBPUSD ⬆️ | XAUUSD ⬆️

💼 Portfolio: 1008.7€ | Ανοιχτά: 0/3 | Σήμερα: +0€
📊 Σύνολο: 2 trades, 2 νίκες (100%) | +21.6€ από αρχή
🔥 Streak: 2 συνεχόμενες νίκες
📅 Μήνας: [██░░░░░░░░] 21.6/100€ (21.6%)"""

try:
    r1 = send_message(msg1)
    print(f"Msg1 sent: {r1.get('result',{}).get('message_id')}")
    r2 = send_message(msg2)
    print(f"Msg2 sent: {r2.get('result',{}).get('message_id')}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
