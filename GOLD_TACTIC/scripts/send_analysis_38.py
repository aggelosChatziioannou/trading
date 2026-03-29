#!/usr/bin/env python3
"""Send Analysis #38 messages to Telegram"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telegram_sender import send_message, send_photo
from pathlib import Path

SCREENSHOTS_DIR = Path(__file__).parent.parent / "screenshots"

MSG1 = """📊 <b>TRADING ANALYST v3.2 — Ανάλυση #38</b>
📋 Scanner: 2026-03-27 11:30 UTC
🕐 15:09 EDT = 21:09 EET 🇬🇷 | NY Afternoon | ⚠️ Close rule σε 51 λεπτά (22:00 EET)
💼 Portfolio: 987.10 EUR | Open: 1/3 | P&amp;L: +10.50 EUR (unrealized)
━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━
🔴 <b>ΕΝΕΡΓΟ TRADE — GBPUSD SHORT</b>
━━━━━━━━━━━━━━━━━━━━━━
📍 Live: 1.3277 (single-source ⚠️) | Chart: 1.3277
📍 Entry: 1.3312 → Τώρα: 1.3277 (−35 pips) ✅
📊 Πρόοδος: [█████░░░░░] 54% προς TP1
📏 SL: 1.3355 | TP1: 1.3247 | TP2: 1.3226
💰 P&amp;L: +10.50 EUR ⏰ Opened: 12:12 EET 🇬🇷

🧭 ΑΞΙΟΛΟΓΗΣΗ: ✅ ΙΣΧΥΡΑ ΣΕ ΠΟΡΕΙΑ
├ Charts: Daily BEAR (RSI 42.3, κάτω EMA50 1.3431) | 4H BEAR | 5m bearish continuation — ADR 74%
├ News: Rubio "Iran war 4+ weeks" (20:46 EET) → USD safe-haven ✅ | Fed Cook hawkish ✅
├ ADR: 74% &lt; 90% ✅ | RSI(D) 42.3 ✅ | Structure intact
└ Πρόβλεψη: TP1 (1.3247) — 29 pips ακόμα, εφικτό σε ~30 λεπτά αν momentum διατηρηθεί

💡 ΣΥΜΒΟΥΛΗ: ΚΡΑΤΑΜΕ — ισχυρό momentum, news ΥΠΕΡ μας.
⚠️ <b>22:00 EET CLOSE RULE</b> σε 51 λεπτά — αν TP1 δεν χτυπηθεί, κλείνουμε manual. Επόμενη ανάλυση 21:29 EET.
━━━━━━━━━━━━━━━━━━━━━━

⚡ <b>LIVE NEWS ALERT</b>: "Rubio: Iran war will continue for another 4 weeks" ⏰ 20:46 EET 🇬🇷 (14:46 EDT)
→ IMPACT: 🔴 GBPUSD/EURUSD (USD ενισχύεται — SHORT tailwind) | 🔴 NAS100 (risk-off) | 🔴 SOL/BTC
→ ΣΥΜΒΟΥΛΗ: GBPUSD SHORT — επιβεβαιώνει την κατεύθυνσή μας ✅
→ ΜΑΘΗΜΑ: Geopolitical continuity = σταθερός risk-off bias. USD safe-haven demand παραμένει.
━━━━━━━━━━━━━━━━━━━━━━

🟡 <b>EURUSD | 1.1522 | ΑΝΑΜΟΝΗ | Score: 3/5</b>
📍 Live: 1.1522 (single-source ⚠️) | Chart: 1.1522
┌ 1.✅ Daily: BEAR (κάτω EMA50 1.1662, RSI ~42)
├ 2.✅ 4H: BEAR (agrees)
├ 3.❌ Sweep: Asia H=1.1549 — τιμή 1.1522, δεν swept
├ 4.❌ BOS: εκκρεμεί μετά sweep
├ 5.✅ ADR OK | RSI 42 ✅ | NY session ✅
├ Από #37: 1.1531 → 1.1522 (−9 pips — συνεχίζει κάτω)
└ 🎯 Trigger: Bounce 1.1549-1.1565 + bearish rejection → 5/5

🎯 <b>EURUSD FOCUS:</b> Bearish bias intact, αλλά χωρίς Asia Sweep ακόμα. Rubio statement = USD tailwind. G7 EU/Rubio meeting (Iran/Russia) μπορεί να δημιουργήσει spike → opportunity. Η EUR αδυναμεί λόγω ενεργειακής κρίσης &amp; ECB cut expectations.
<b>ΑΠΟΦΑΣΗ: ΑΝΑΜΟΝΗ</b> — 3/5, no trigger. Παρακολουθούμε Asia H zone.
━━━━━━━━━━━━━━━━━━━━━━

⬜ <b>NAS100 | 23,473 | SKIP | Score: 2/5</b>
📍 Live: 23,473 (single-source ⚠️)
┌ 1.✅ IB formed 16:30-17:30 EET 🇬🇷
├ 2.✅ IB size OK (300 pts)
├ 3.✅ Breakout: τιμή κάτω IB Low (23,750)
├ 4.❌ Retracement: δεν retest 23,750-23,850 ζώνη
├ 5.❌ ADR &gt;90% ⛔ HARD STOP
├ Από #37: 23,545 → 23,473 (−71 pts — συνεχίζει πτώση)
└ ⏰ IBB window κλείνει 22:00 EET 🇬🇷 | ADR απαγορεύει

<b>ΑΠΟΦΑΣΗ: ΑΠΟΦΥΓΗ</b> — ADR &gt;90% ⛔. Παρά ισχυρό setup, ο κανόνας προστατεύει κεφάλαιο.
━━━━━━━━━━━━━━━━━━━━━━

🟡 <b>SOL | $82.98 | ΑΝΑΜΟΝΗ | Score: 3/5</b>
📍 Live: $82.98 (single-source ⚠️)
┌ 1.✅ Daily: BEAR (κάτω EMA50 $92, RSI ~36)
├ 2.✅ 4H: BEAR (declining)
├ 3.❌ Sweep: Asia H=$86.91 — τιμή $82.98, δεν swept
├ 4.❌ BOS: εκκρεμεί
├ 5.✅ ADR ~58% ✅ | RSI 36 ✅
├ Από #37: $82.76 → $82.98 (+$0.22 — micro bounce)
└ 🎯 Trigger: Bounce $86-87 + rejection → SHORT | RSI&lt;25 → counter-trend LONG

<b>ΑΠΟΦΑΣΗ: ΑΝΑΜΟΝΗ</b> — 3/5, setup intact. Iran war risk-off πιέζει crypto. Χωρίς sweep, χωρίς θέση.
━━━━━━━━━━━━━━━━━━━━━━

⬜ <b>BTC | $65,991 | SKIP | Score: 2/5</b>
📍 Live: $65,991 (single-source ⚠️)
┌ 1.✅ Daily: BEAR (κάτω EMA50 ~$71,745)
├ 2.✅ 4H: BEAR
├ 3.❌ Asia Sweep: εκκρεμεί
├ 4.❌ BOS: εκκρεμεί
├ 5.❌ ADR εκτιμ. &gt;90% ⛔
├ Από #37: $65,812 → $65,991 (+$179 — micro bounce σε risk-off context)
└ 🎯 Trigger: RSI&lt;25 counter-trend | ADR &lt;90% + sweep

<b>ΑΠΟΦΑΣΗ: ΑΠΟΦΥΓΗ</b> — 2/5, ADR υψηλό, Iran war risk-off. Καμία νέα θέση.
━━━━━━━━━━━━━━━━━━━━━━
📊 Scores: EURUSD:3 GBPUSD:5🔴 NAS100:2 SOL:3 BTC:2
⏰ Επόμενη: ~21:29 EET 🇬🇷 | ⚠️ ΤΕΛΕΥΤΑΙΑ ΠΡΙΝ 22:00 EET CLOSE"""

MSG2 = """📰 <b>ΕΙΔΗΣΕΙΣ — Ανάλυση #38</b>
━━━━━━━━━━━━━━━━━━━━━━

⚡ <b>LIVE — Γεωπολιτικά (ΚΡΙΣΙΜΟ):</b> Υπουργός Εξωτερικών Rubio: "Ο πόλεμος με το Ιράν θα συνεχιστεί για άλλες 4 εβδομάδες"
📎 <a href="https://investinglive.com">Source: Forexlive</a> ⏰ 20:46 EET 🇬🇷 (14:46 EDT)
→ IMPACT: 🔴 GBPUSD (USD ισχυρός — SHORT tailwind ✅), 🔴 EURUSD (USD bullish), 🔴 NAS100 (risk-off), 🔴 SOL/BTC (risk-off)
→ ΜΑΘΗΜΑ: Όταν κυβερνητικός αξιωματούχος επιβεβαιώνει διάρκεια πολέμου → USD safe-haven παραμένει ενισχυμένο, GBP/EUR αδυνατίζει.

🔸 <b>Μακρο — Fed:</b> "Balance of risks shifted toward inflation due to Iran war" (Cook)
📎 <a href="https://news.google.com/rss/articles/CBMiuwFBVV95cUxPUGYxOVVzNGEwb1g2LWJsT01QNlJFVDNMUGhMV08yTjRFTEZWeVBJR3R5UUFwVjduQTRubGprUWh4ZGdhSmdranpjUnpqRS01US1OUDZkWG52bmx3ODgzVXVWUU9vWVlPMWNvRURiRUpFaGl0VkxqdThqWEhtbU4yUGV6NW1qczE2SlNLYUl0S3h1RVVYZWVFdTJYVUdMdUNBUFF0QWFxbUpUUXFraWgtOGtQWk1QRXV3cVRF">Reuters: Fed Cook hawkish</a> ⏰ 02:05 EET 🇬🇷 (20:05 EDT)
→ IMPACT: 🟢 USD (rate cuts delayed), 🔴 EURUSD (EUR weak vs USD), 🔴 GBPUSD (GBP weak)
→ ΜΑΘΗΜΑ: Fed hawkish (delayed cuts) = USD strength. ΕΚΤ/BOE cut ενώ Fed holds = EUR/GBP σε μειονεκτική θέση.

🔸 <b>Nasdaq:</b> "Nasdaq confirms correction, Wall Street slumps on Middle East uncertainty"
📎 <a href="https://news.google.com/rss/articles/CBMitAFBVV95cUxNamV4N1ZHTU9NQW0xQ0tFZjkwUWM5LUtGbDY0NGdnS3JhYTZ0eU1JU3YyYUxOOE1pYXJDSlZUNEdjcTlTbGgwWkJkNmh4c0ZnWjFXbVpDTkhMSUpUUnRBNWo3czY1R0hvNWJFTnJkZGI2ejNIdV9WZkhkbHdhZ3VMMlFxV0FyUVRuYnc3VEN4S3dLUFBpZ3A2ZEdyUFl3OVE5RTIyMHA2U3E3U05tOUotcEp5R2U">Reuters: Nasdaq correction</a> ⏰ 03:24 EET 🇬🇷 (21:24 EDT)
→ IMPACT: 🔴 NAS100 (confirmed bear), 🔴 SOL/BTC (tech/risk sell-off), ⚠️ Oversold bounce risk
→ ΜΑΘΗΜΑ: Correction = downtrend confirmed. ΟΧΙ FOMO longs. Περίμενε retracement για entries.

🔸 <b>Πετρέλαιο:</b> Oil +3% αλλά πρώτη εβδομαδιαία πτώση από αρχή πολέμου
📎 <a href="https://news.google.com/rss/articles/CBMirwFBVV95cUxPT3JQcW42VTUxV2dTekoyZUMzVzRlZExaSWVFNjFJc2NGNmFyNmVISWZZdTlBeWFfb05RRzN1WGVlQ3RJUnhfbnBPR3VKclJXR3FPLWk0c0VkQjhrNjdmVGVqQTE2bjI1N0J0aUVVX3hCRHdUWlhITDlNc1pTd3dZZzJKbVktOVdMcS1sTW01cjNTSXNRSmhWck9ZRk9WWGlVVGM5MkRyQmVhSGNNaXp3">Reuters: Oil weekly decline</a> ⏰ 05:12 EET 🇬🇷 (23:12 EDT)
→ IMPACT: ⚠️ USD (μικρή αποδυνάμωση safe-haven αν πετρέλαιο πέσει), 🟡 NAS100 (όχι θετικό ακόμα), ⚠️ GBPUSD (ελαφρά αντίθετο — watch)
→ ΜΑΘΗΜΑ: Πτώση πετρελαίου = η αγορά αρχίζει να "τιμολογεί" ceasefire. ΑΝ συνεχιστεί → ΚΛΕΙΣΕ GBP SHORT γρήγορα.

━━━━━━━━━━━━━━━━━━━━━━
📊 News Scores: EURUSD:🔴 GBPUSD:🔴(✅SHORT) NAS100:🔴 SOL:🔴 BTC:🔴
⏰ Επόμενη: ~21:29 EET 🇬🇷 | ⚠️ 22:00 EET — ΚΛΕΙΣΙΜΟ ΟΛΩΝ ΤΩΝ ΘΕΣΕΩΝ"""

print("Sending Message 1 (Market Analysis)...")
r1 = send_message(MSG1)
print(f"  Result: {r1.get('ok')} | msg_id: {r1.get('result', {}).get('message_id')}")

print("Sending Message 2 (News)...")
r2 = send_message(MSG2)
print(f"  Result: {r2.get('ok')} | msg_id: {r2.get('result', {}).get('message_id')}")

print("Sending GBPUSD charts...")
charts = ['GBPUSD_daily.png', 'GBPUSD_4h.png', 'GBPUSD_5m.png']
for chart in charts:
    p = SCREENSHOTS_DIR / chart
    if p.exists():
        r = send_photo(str(p), f"📊 {chart.replace('_', ' ').replace('.png', '')} — Ανάλυση #38")
        print(f"  {chart}: {r.get('ok')}")
    else:
        print(f"  {chart}: NOT FOUND")

print("Done!")
