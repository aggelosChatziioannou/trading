#!/usr/bin/env python3
"""Send 4 sample messages demonstrating the new Selector cooperation header (G1)."""
import time
import subprocess
import sys, os
from pathlib import Path

if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

SENDER = str(Path(__file__).parent / "telegram_sender.py")

def send(text, silent=False, effect=None, label=""):
    args = ["python", SENDER, "message", text]
    if silent:
        args.append("--silent")
    if effect:
        args.extend(["--effect", effect])
    print(f"\n--- {label} ---")
    r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
    print(f"OK msg_id={r.stdout.strip()[:20]}" if r.returncode == 0 else f"FAIL: {r.stderr[:100]}")
    time.sleep(1.4)

# Intro for coordination demo
intro = """🔄 <b>Schedule Coordination Demo (G1)</b>
━━━━━━━━━━━━━━━━━━━━━━

Παρακάτω 4 δείγματα με τη <b>νέα γραμμή Selector reference</b> πάνω-πάνω.

Ο χρήστης βλέπει σε κάθε Monitor message:
🎯 <i>Watched: <b>AM Selector</b> @08:00 (4h12' ago) — EUR·AUD·BTC·NAS</i>

<b>Staleness colors:</b>
🎯 = Selector φρέσκος (&lt;9h)
🟡 = Selector παλιός (9-12h)
🔴 = Selector πολύ παλιός (&gt;12h ago)"""
send(intro, silent=False, label="INTRO")

# L1 PULSE με selector ref (fresh)
l1 = """❄️ <b>10:25</b> · Όλα ήρεμα
🎯 <i>Watched: <b>AM Selector</b> @08:00 (2h25' ago) — EUR·AUD·BTC·NAS</i>

🟡 EUR 3/5 · 🟡 AUD 3/5 · 🟢 BTC 4/5 · ⚪ NAS 2/5

📰 News: ίδια εδώ και 12'  ·  ⏰ Next: ECB σε 4h35'
🩺 💚 Healthy  ·  📡 9/9 sources · 23 άρθρα"""
send(l1, silent=True, label="L1 PULSE με selector ref (fresh)")

# L2 WATCH με selector ref (fresh)
l2 = """👁️ <b>WATCH</b> · 10:45  ·  ✅ London Kill Zone (Optimal)
🎯 <i>Watched: <b>AM Selector</b> @08:00 (2h45' ago) — EUR·AUD·BTC·NAS</i>

🔼 BTC <b>+0.7%</b> @ <code>$76,420</code> → TRS 3→4 (πέρασε ADR)
   ✅TF ✅RSI ✅ADR ✅News ❌Key

📰 <b>ΝΕΟ</b>
• <a href="https://www.coindesk.com/markets/2026/04/29/btc-etf-inflows">"BTC ETF inflows $420M"</a> <i>(CoinDesk T1)</i> → 🟢 BTC HIGH

🟡 EUR 3/5 · 🟡 AUD 3/5 · ⚪ NAS 2/5  <i>(stable)</i>

⏰ ECB σε 4h15'  ·  🌡️ F&amp;G 72 · ⚡ RISK_ON
🩺 💚 Healthy"""
send(l2, silent=True, label="L2 WATCH με selector ref")

# L4 SIGNAL με selector ref (fresh PM Selector)
l4 = """🔥 <b>ΣΗΜΑ · BTCUSD</b> · 5/5 ▰▰▰▰▰ · ✅ NY Kill Zone (Optimal)
🎯 <i>Watched: <b>PM Selector</b> @15:00 (1h25' ago) — XAU·EUR·BTC·NAS</i>
━━━━━━━━━━━━━━━━━━━━━━

📈 <b>LONG</b> @ <code>$75,520</code>  ·  Risk 2% (20€)  ·  Lot <b>0.026</b>
🎯 TP1 <code>$76,650</code>  ·  🎯🎯 TP2 <code>$77,780</code>
🛡️ SL <code>$74,955</code>  ·  ⚖️ R:R 1:2

<b>📊 Γιατί το πήραμε — Όλα τα κριτήρια ✅</b>

✅ <b>TF · Τάση</b>
<i>Η τάση είναι ξεκάθαρη και στις δύο πιο σημαντικές χρονικές κλίμακες.</i>

✅ <b>News · Ειδήσεις</b>
<i>CoinDesk (T1): θεσμικά λεφτά αγοράζουν BTC ETF.</i>

✅ <b>Key · Σημείο εισόδου</b>
<i>Είμαστε ακριβώς πάνω σε επίπεδο που η τιμή ιστορικά αντιδράει.</i>

<i>(2 ακόμα ✅ criteria — RSI Δύναμη + ADR Καύσιμο — full template στο L4)</i>

⏰ ECB σε 1h25'  ·  🩺 💚 Healthy"""
send(l4, silent=False, effect="fire", label="L4 SIGNAL με selector ref")

# Lock contention demo (rare but covered)
skip = """⏸️ <i>Monitor skip — Selector morning τρέχει (3min). Επόμενο cycle θα διαβάσει τα νέα assets.</i>

<i>Demo: αυτό συμβαίνει αν το 8:00 Selector καθυστερήσει και το 8:05 Monitor θα διάβαζε half-state. Lock-file mechanism το αποτρέπει.</i>"""
send(skip, silent=True, label="LOCK CONTENTION SKIP")

# Stale selector example
stale = """❄️ <b>20:15</b> · Όλα ήρεμα
🟡 <i>Watched: <b>PM Selector</b> @15:00 (5h15' ago) — XAU·EUR·BTC·NAS</i>

🟡 XAU 3/5 · ⚪ EUR 2/5 · ⚪ BTC 2/5 · ⚪ NAS 2/5

📰 News: ίδια εδώ και 22'  ·  ⏰ Next: AM Selector σε 11h45'
🩺 💚 Healthy

<i>Demo: yellow icon σημαίνει Selector >9h ago — επόμενος EVE σε 45'.</i>"""
send(stale, silent=True, label="STALE SELECTOR (yellow)")

# Closing
closing = """✅ <b>Coordination v7.2 Complete</b>

Νέες μηχανές που κατοχυρώνουν συνεργασία 8 schedules:

🔒 <b>Lock-file</b> — Selector γράφει lock στην έναρξη, Monitor το ελέγχει (avoid race)
✅ <b>Done signal</b> — selector_done.json με run summary + sources
📋 <b>cycle_log.jsonl</b> — append-only audit trail per-cycle
🎯 <b>Selector ref line</b> — κάθε Monitor message δείχνει last Selector
🌱 <b>EVE seed</b> — μετά rotation, fresh briefing_log έχει context

<b>Verification:</b> <code>python cycle_coordinator.py status</code>
<b>Docs:</b> GOLD_TACTIC/docs/COORDINATION.md"""
send(closing, silent=True, label="CLOSING")

print("\n=== ALL COORDINATION SAMPLES SENT ===")
