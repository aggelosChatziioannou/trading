#!/usr/bin/env python3
"""Render Mockup A (Selector) and Mockup D (Monitor L2 WATCH) with live data
from data/*.json. Output saved to data/review/preview_mockups.txt.

This is a one-off preview tool — runs locally, no Telegram send. Used after
template updates to verify the rendering before pushing to Cowork."""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

EET = timezone(timedelta(hours=3))
ROOT = Path(__file__).parent.parent
REVIEW = ROOT / "data/review"
REVIEW.mkdir(parents=True, exist_ok=True)


def load(name):
    p = ROOT / f"data/{name}"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


prices = load("live_prices.json").get("prices", {})
scan = {r["asset"]: r for r in load("quick_scan.json").get("assets", [])}
news_summary = load("news_feed.json").get("summary", {})
selected = load("selected_assets.json").get("selected", [])


def fmt_price(sym, val):
    if val is None or val == "?":
        return "—"
    if sym in ("EURUSD", "GBPUSD", "AUDUSD"):
        return f"{val:.4f}"
    if sym in ("USDJPY", "DXY"):
        return f"{val:.2f}"
    if sym in ("BTC", "NAS100"):
        return f"${val:,.0f}"
    if sym == "XAUUSD":
        return f"${val:,.2f}"
    return f"${val:.2f}"


def render_selector_mockup_a():
    """Mockup A — Card-style selector message."""
    now = datetime.now(EET)
    parts = []
    parts.append(f"🎯 <b>Επιλογές ημέρας</b> · Πρωινή {now.strftime('%H:%M')}")
    parts.append("━━━━━━━━━━━━━━━━━━━━━━")
    parts.append("")
    if selected:
        parts.append(
            f"Σήμερα παρακολουθούμε {len(selected)} assets — "
            "δοκιμαστική παρουσίαση Mockup A (ισορροπημένη επιλογή)."
        )
        parts.append("")
        top_sym = selected[0].get("symbol", "?")
        parts.append(f"Πιο κοντά σε trade αυτή τη στιγμή: 🥇 <b>{top_sym}</b>.")
        parts.append("")
        parts.append("━━━━━━━━━━━━━━━━━━━━━━")

        rank_emoji = ["🥇", "🥈", "🥉", "4️⃣"]
        for i, a in enumerate(selected[:4]):
            sym = a.get("symbol", "?")
            score = a.get("score", "?")
            bias = a.get("direction_bias", "—")
            bias_emoji = "📉" if bias == "SHORT" else ("📈" if bias == "LONG" else "🟡")
            price = prices.get(sym, {}).get("price")
            scan_data = scan.get(sym, {})
            rsi_d = scan_data.get("rsi_daily") or 50
            adr_pct = scan_data.get("adr_consumed_pct") or 0
            news = news_summary.get(sym, {})
            news_sent = news.get("overall_sentiment", "neutral")
            top_headline = (news.get("top_headlines") or [{}])[0].get("headline", "")[:80]

            tag = " (πιο κοντά)" if i == 0 else ""
            parts.append(f"{rank_emoji[i]} <b>{sym}</b> · {score}/12 · {bias_emoji} {bias}{tag}")
            parts.append(f"Τιμή τώρα: <code>{fmt_price(sym, price)}</code>")
            if i == 0:
                # full detailed card for #1
                parts.append("🎯 Σημείο εισόδου: <code>(retest zone)</code>")
                parts.append("")
                parts.append("✅ <b>Τι έχουμε ήδη:</b>")
                if "ALIGNED" in (scan_data.get("alignment") or "MIXED") or "PARTIAL" in (
                    scan_data.get("alignment") or "MIXED"
                ):
                    parts.append(
                        f"   ✓ Τάση: {scan_data.get('alignment','MIXED').replace('_',' ').lower()} στα κεριά"
                    )
                if adr_pct < 70:
                    parts.append(f"   ✓ Εύρος ADR: {100 - adr_pct:.0f}% remaining (αρκετός χώρος)")
                if news_sent != "neutral":
                    parts.append(f"   ✓ Νέα: {news_sent} σήμα")
                parts.append("")
                parts.append("⏳ <b>Τι περιμένουμε:</b>")
                parts.append(f"   • Pullback ή confirmation στο επίπεδο εισόδου")
                if 30 <= rsi_d <= 35 or 65 <= rsi_d <= 70:
                    parts.append(f"   • RSI {rsi_d:.0f} — αναμένεται bounce/pullback πρώτα")
                parts.append("")
                if top_headline:
                    parts.append(
                        f"📰 <b>Νέα που στηρίζουν:</b> {top_headline} "
                        f"<i>(top headline)</i>"
                    )
                parts.append(f"🔮 <b>Επόμενο βήμα:</b> ~30-90 λεπτά (στο επόμενο KZ)")
            elif i == 1:
                # compact for #2
                parts.append(f"🎯 Σημείο εισόδου: αναμονή για clear setup")
                parts.append("")
                parts.append(f"⚠️ <b>Λείπουν κριτήρια:</b>")
                if "MIXED" in (scan_data.get("alignment") or "MIXED"):
                    parts.append("   • Καθαρή κατεύθυνση τάσης")
                if adr_pct >= 70:
                    parts.append(f"   • ADR στο {adr_pct:.0f}% — μικρός χώρος")
                parts.append("")
                if top_headline:
                    parts.append(f"📰 <b>Νέα:</b> {news_sent} ({top_headline[:50]}...)")
                parts.append(f"🔮 <b>Επόμενο βήμα:</b> ~2-4 ώρες (αναμονή candle close)")
            else:
                # ultra-compact #3, #4
                if top_headline:
                    parts.append(f"📰 <b>Νέα:</b> {news_sent}")
                parts.append(f"🔮 <b>Επόμενο βήμα:</b> Επόμενο KZ")
            parts.append("")
            parts.append("━━━━━━━━━━━━━━━━━━━━━━")

    parts.append("")
    parts.append("📅 <b>Σημερινά events</b>")
    parts.append("• <code>15:30</code> 🔴 US GDP Q1 (advance)")
    parts.append("• <code>22:00</code> 🟡 Fed minutes")
    parts.append("")
    parts.append("🌡️ Σεντιμέντ αγοράς: <b>26</b> (Φόβος) · 😐 trend_mixed")
    parts.append("💲 DXY <code>98.79</code> (αδυναμία δολαρίου)")
    return "\n".join(parts)


def render_monitor_mockup_d():
    """Mockup D — Monitor L2 WATCH continuity narrative."""
    now = datetime.now(EET)
    if not selected:
        return "(no selected assets to render)"
    focus = selected[0]
    sym = focus.get("symbol", "?")
    bias = focus.get("direction_bias", "—")
    bias_emoji = "📉" if bias == "SHORT" else ("📈" if bias == "LONG" else "🟡")
    price = prices.get(sym, {}).get("price")
    scan_data = scan.get(sym, {})
    rsi_d = scan_data.get("rsi_daily") or 50
    adr_pct = scan_data.get("adr_consumed_pct") or 0
    align = scan_data.get("alignment", "MIXED")

    parts = []
    parts.append(f"👁️ <b>Παρακολούθηση</b> · {now.strftime('%H:%M')}  ·  🌙 εκτός kill zones")
    parts.append(f"🎯 Watched: AM Selector @08:07 — SOL/BTC/GBP/AUD")
    parts.append("")
    parts.append(f"📖 <b>Από το προηγούμενο cycle (12:15)</b>")
    if price:
        parts.append(
            f"{sym} κινήθηκε από <code>$83.16</code> → <code>{fmt_price(sym, price)}</code> "
            f"(+0.13%). Πιο κοντά αλλά ακόμα κάτω από τη ζώνη μας ($83.00-83.20). "
            f"Στις προηγούμενες 2 ώρες δοκίμασε 3 φορές το επίπεδο — δεν έσπασε."
        )
    parts.append("")
    parts.append(
        f"🥇 <b>{sym}</b> · 4/5 · {bias_emoji} {bias} · "
        f"<code>{fmt_price(sym, price)}</code> (+0.13%)"
    )
    crits_met = []
    if "ALIGNED" in align or "PARTIAL" in align:
        crits_met.append(f"τάση {bias}")
    if adr_pct < 70:
        crits_met.append(f"εύρος ADR {100 - adr_pct:.0f}%")
    crits_met.append("νέα supportive")
    crits_met.append("κοντά σε επίπεδο")
    parts.append("   ✓ " + " · ✓ ".join(crits_met[:4]))
    if rsi_d <= 35:
        parts.append(f"   ⏳ ορμή RSI {rsi_d:.0f} — oversold, αναμένεται bounce πρώτα")
    parts.append(f"   💡 Ένα βήμα από trigger. Αν ανέβει στο entry zone με weak candle → entry.")
    parts.append("")
    parts.append("📊 <b>Άλλα 3 assets</b>")
    others = [a.get("symbol", "?") for a in selected[1:4]]
    if others:
        parts.append(f"🟡 {others[0] if len(others) > 0 else ''} 3/5 · "
                     f"⚪ {others[1] if len(others) > 1 else ''} 2/5 · "
                     f"⚪ {others[2] if len(others) > 2 else ''} 2/5 (όλα stable)")
    parts.append("")
    parts.append("📰 Δεν εμφανίστηκε νέο που να επηρεάζει ενεργά. Cached: bearish crypto vibe παραμένει.")
    parts.append("")
    parts.append(
        "🔮 <b>Επόμενα 1-3 cycles:</b> NY KZ ανοίγει σε 2h55'. "
        "Αν φτάσει το entry zone πριν τότε, εξετάζουμε probe entry."
    )
    parts.append("")
    parts.append("⏰ NY KZ σε ~2h55'  ·  🌡️ Φόβος 26 · trend_mixed")
    parts.append("🩺 Δεδομένα: όλα φρέσκα ✓")
    return "\n".join(parts)


# Render both
selector_a = render_selector_mockup_a()
monitor_d = render_monitor_mockup_d()

# Save to review file
out_path = REVIEW / "preview_mockups.txt"
with open(out_path, "w", encoding="utf-8") as f:
    f.write("=" * 70 + "\n")
    f.write("MOCKUP A — Selector (Card-style)\n")
    f.write("=" * 70 + "\n\n")
    f.write(selector_a)
    f.write("\n\n")
    f.write("=" * 70 + "\n")
    f.write("MOCKUP D — Monitor L2 WATCH (Continuity Narrative)\n")
    f.write("=" * 70 + "\n\n")
    f.write(monitor_d)
    f.write("\n\n")
    f.write("=" * 70 + "\n")
    f.write(f"Selector A length: {len(selector_a)} chars\n")
    f.write(f"Monitor D length: {len(monitor_d)} chars\n")

print("=" * 70)
print("MOCKUP A — Selector (Card-style)")
print("=" * 70)
print()
print(selector_a)
print()
print("=" * 70)
print("MOCKUP D — Monitor L2 WATCH (Continuity Narrative)")
print("=" * 70)
print()
print(monitor_d)
print()
print(f"Saved preview to: {out_path.relative_to(ROOT.parent)}")
print(f"Selector A length: {len(selector_a)} chars · Monitor D length: {len(monitor_d)} chars")
