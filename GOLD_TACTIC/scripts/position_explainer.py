#!/usr/bin/env python3
"""
GOLD TACTIC — Position Explainer (plain-Greek financial transparency)

Renders a "Ξεκάθαρα νούμερα" block for L4 SIGNAL messages so non-traders
in the group understand exactly what they're risking and earning.

Computes:
  - Net profit at TP1 and TP2 (EUR)
  - Max loss at SL (EUR)
  - Position size (lot) + asset units
  - Notional exposure (EUR)
  - Required margin (EUR)
  - Effective leverage (1:N)
  - Plain-Greek explanations of jargon (R:R, Lot, Leverage)

Usage:
  python position_explainer.py BTC LONG 75520 74955 76650 77780 0.026 1000
  # asset direction entry sl tp1 tp2 lot balance

  python position_explainer.py --json BTC LONG 75520 74955 76650 77780 0.026 1000
  # JSON output instead of HTML block

  python position_explainer.py --html ...   (default — HTML block for Telegram)
"""

import json
import sys
import os
from pathlib import Path

if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent))
from risk_manager import ASSET_CONFIG

# CySEC retail leverage caps + corresponding margin %
# IC Markets demo (account 52817474) is CySEC-regulated, so these apply.
CYSEC_RETAIL = {
    "EURUSD": {"label": "1:30 (forex major)", "max_leverage": 30, "margin_pct": 0.0333},
    "GBPUSD": {"label": "1:30 (forex major)", "max_leverage": 30, "margin_pct": 0.0333},
    "USDJPY": {"label": "1:30 (forex major)", "max_leverage": 30, "margin_pct": 0.0333},
    "AUDUSD": {"label": "1:30 (forex major)", "max_leverage": 30, "margin_pct": 0.0333},
    "XAUUSD": {"label": "1:20 (gold/CFD)",     "max_leverage": 20, "margin_pct": 0.05},
    "NAS100": {"label": "1:20 (index/CFD)",    "max_leverage": 20, "margin_pct": 0.05},
    "SPX500": {"label": "1:20 (index/CFD)",    "max_leverage": 20, "margin_pct": 0.05},
    "BTC":    {"label": "1:5 (crypto retail)", "max_leverage": 5,  "margin_pct": 0.20},
    "ETH":    {"label": "1:5 (crypto retail)", "max_leverage": 5,  "margin_pct": 0.20},
    "SOL":    {"label": "1:5 (crypto retail)", "max_leverage": 5,  "margin_pct": 0.20},
    "XRP":    {"label": "1:5 (crypto retail)", "max_leverage": 5,  "margin_pct": 0.20},
}


def _fmt_eur(amount):
    return f"{amount:+.2f}€" if amount != 0 else "0.00€"


def _fmt_price(price, asset):
    """Format price with appropriate decimals for the asset class."""
    if asset in ("EURUSD", "GBPUSD", "AUDUSD"):
        return f"{price:.5f}"
    if asset == "USDJPY":
        return f"{price:.3f}"
    if asset in ("XAUUSD",):
        return f"{price:.2f}"
    if price >= 1000:
        return f"{price:,.2f}"
    return f"{price:.4f}"


def _fmt_pct(p):
    sign = "+" if p > 0 else ""
    return f"{sign}{p:.2f}%"


def compute_summary(asset, direction, entry, sl, tp1, tp2, lot, balance):
    """Return all financial figures + explanations."""
    cfg = ASSET_CONFIG.get(asset)
    if not cfg:
        return {"ok": False, "error": f"Unknown asset: {asset}"}

    direction = direction.upper()
    sign = 1 if direction == "LONG" else -1

    pip_size = cfg["pip_size"]
    pip_value_per_lot = cfg["pip_value_per_lot"]
    contract_size = cfg["contract_size"]
    margin_per_lot = cfg["margin_per_lot"]

    # Distances in pips
    sl_distance_pips = abs(entry - sl) / pip_size
    tp1_distance_pips = abs(tp1 - entry) / pip_size
    tp2_distance_pips = abs(tp2 - entry) / pip_size

    # Net P/L in EUR (assumes pip_value_per_lot already in EUR)
    loss_at_sl = -lot * sl_distance_pips * pip_value_per_lot
    gain_at_tp1 = lot * tp1_distance_pips * pip_value_per_lot
    gain_at_tp2 = lot * tp2_distance_pips * pip_value_per_lot

    # Notional exposure (EUR-equivalent, approximate — uses entry price as USD≈EUR)
    asset_units = lot * contract_size
    notional_eur = asset_units * entry  # for crypto/forex this is the USD notional ≈ EUR

    # CySEC retail margin (proper EU-regulated calculation)
    cysec = CYSEC_RETAIL.get(asset, {"label": "—", "max_leverage": 1, "margin_pct": 1.0})
    margin_eur_cysec = notional_eur * cysec["margin_pct"]

    # Effective leverage = notional / margin
    leverage = round(notional_eur / margin_eur_cysec, 1) if margin_eur_cysec > 0 else 0
    margin_eur = margin_eur_cysec  # use CySEC-correct value

    # Risk:Reward ratio (using the bigger of TP1/TP2 — typically 1:2)
    rr_tp1 = abs(gain_at_tp1 / loss_at_sl) if loss_at_sl != 0 else 0
    rr_tp2 = abs(gain_at_tp2 / loss_at_sl) if loss_at_sl != 0 else 0

    # Distances in %
    sl_pct = abs(entry - sl) / entry * 100
    tp1_pct = abs(tp1 - entry) / entry * 100
    tp2_pct = abs(tp2 - entry) / entry * 100

    # Risk as % of balance
    risk_pct_of_balance = abs(loss_at_sl) / balance * 100

    return {
        "ok": True,
        "asset": asset,
        "direction": direction,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "lot": lot,
        "balance": balance,
        # Distances
        "sl_distance_pips": round(sl_distance_pips, 1),
        "tp1_distance_pips": round(tp1_distance_pips, 1),
        "tp2_distance_pips": round(tp2_distance_pips, 1),
        "sl_pct": round(sl_pct, 3),
        "tp1_pct": round(tp1_pct, 3),
        "tp2_pct": round(tp2_pct, 3),
        # Money
        "loss_at_sl_eur": round(loss_at_sl, 2),
        "gain_at_tp1_eur": round(gain_at_tp1, 2),
        "gain_at_tp2_eur": round(gain_at_tp2, 2),
        "risk_pct_of_balance": round(risk_pct_of_balance, 2),
        # Position
        "asset_units": round(asset_units, 6),
        "notional_eur": round(notional_eur, 2),
        "margin_eur": round(margin_eur, 2),
        "leverage_used": leverage,
        "leverage_cysec_max": cysec["label"],
        "leverage_cysec_int": cysec["max_leverage"],
        "margin_pct": cysec["margin_pct"] * 100,
        # Ratios
        "rr_tp1": round(rr_tp1, 2),
        "rr_tp2": round(rr_tp2, 2),
    }


def render_html_block(s):
    """Render a Telegram-ready HTML block from the summary."""
    if not s.get("ok"):
        return f"⚠️ <i>Position explainer: {s.get('error','?')}</i>"

    asset = s["asset"]
    units_label = f"{s['asset_units']} {asset.replace('USD','') if asset.endswith('USD') else asset}"
    if asset in ("BTC", "ETH", "SOL", "XRP"):
        units_label = f"{s['asset_units']} {asset}"
    elif asset.endswith("USD") and asset != "XAUUSD":
        units_label = f"{s['asset_units']:,.0f} {asset[:3]}"
    elif asset == "XAUUSD":
        units_label = f"{s['asset_units']:.0f} ουγγιές χρυσού"
    elif asset in ("NAS100", "SPX500"):
        units_label = f"{s['asset_units']:.1f} contracts"

    lines = [
        f"💰 <b>Ξεκάθαρα νούμερα</b>",
        f"",
        f"🎯 <b>Αν φτάσει TP1</b> ({_fmt_price(s['tp1'], asset)}): <b>{_fmt_eur(s['gain_at_tp1_eur'])}</b> καθαρά (+{s['tp1_distance_pips']:.0f} pts)",
        f"🎯🎯 <b>Αν φτάσει TP2</b> ({_fmt_price(s['tp2'], asset)}): <b>{_fmt_eur(s['gain_at_tp2_eur'])}</b> καθαρά (+{s['tp2_distance_pips']:.0f} pts)",
        f"🛡️ <b>Αν χτυπήσει SL</b> ({_fmt_price(s['sl'], asset)}): <b>{_fmt_eur(s['loss_at_sl_eur'])}</b> μέγιστη απώλεια (−{s['sl_distance_pips']:.0f} pts)",
        f"",
        f"⚙️ <b>Στοιχεία θέσης</b>",
        f"• Είσοδος: <code>{_fmt_price(s['entry'], asset)}</code> · Direction: {s['direction']}",
        f"• Μέγεθος: <b>{s['lot']} lot</b> = {units_label}",
        f"• Αξία θέσης: <b>~{s['notional_eur']:,.0f}€</b> (notional exposure)",
        f"• Απαιτούμενο margin: <b>~{s['margin_eur']:,.0f}€</b> από τα {s['balance']:.0f}€ ({s['margin_pct']:.0f}% του notional, μένουν {s['balance']-s['margin_eur']:,.0f}€ ελεύθερα)",
        f"• Leverage: <b>{s['leverage_cysec_max']}</b> · CySEC retail standard για IC Markets demo",
        f"• Ρίσκο: <b>{s['risk_pct_of_balance']:.1f}%</b> του κεφαλαίου",
        f"",
        f"📚 <b>Τι σημαίνουν τα νούμερα</b>",
        f"• <b>Lot {s['lot']}</b> = πόσα κομμάτια του asset αγοράζουμε. Εδώ {units_label}.",
        f"• <b>R:R 1:{s['rr_tp2']:.0f}</b> (Risk:Reward) = ρισκάρουμε {abs(s['loss_at_sl_eur']):.0f}€ για να κερδίσουμε {s['gain_at_tp2_eur']:.0f}€ στο TP2. Αν χτυπάμε 1 στις 3 φορές βγαίνουμε κερδοφόροι.",
        f"• <b>Leverage {s['leverage_cysec_max']}</b> = με {s['margin_eur']:.0f}€ margin \"πιάνουμε\" {s['notional_eur']:,.0f}€ exposure στην αγορά. Ο broker μας δανείζει το υπόλοιπο. Αυτό είναι το standard CySEC retail όριο για το asset class.",
        f"",
        f"<i>💡 Με 1.000€ κεφάλαιο, η μέγιστη απώλεια αυτού του trade είναι {abs(s['loss_at_sl_eur']):.2f}€ — ποτέ δεν χάνεις πάνω από αυτό.</i>",
    ]
    return "\n".join(lines)


def render_compact_block(s):
    """Shorter version for in-trade reminders / dashboard. ~280 chars."""
    if not s.get("ok"):
        return ""
    return (
        f"💰 TP1 <b>{_fmt_eur(s['gain_at_tp1_eur'])}</b> · "
        f"TP2 <b>{_fmt_eur(s['gain_at_tp2_eur'])}</b> · "
        f"SL <b>{_fmt_eur(s['loss_at_sl_eur'])}</b>\n"
        f"⚙️ {s['lot']} lot · margin ~{s['margin_eur']:.0f}€ · leverage 1:{s['leverage_used']:.0f}"
    )


# ─── CLI ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    output_mode = "html"
    if "--json" in args:
        output_mode = "json"
        args.remove("--json")
    elif "--compact" in args:
        output_mode = "compact"
        args.remove("--compact")
    elif "--html" in args:
        args.remove("--html")

    if len(args) < 8:
        print("Usage: position_explainer.py [--json|--html|--compact] ASSET DIR ENTRY SL TP1 TP2 LOT BALANCE")
        print("Example: position_explainer.py BTC LONG 75520 74955 76650 77780 0.026 1000")
        sys.exit(1)

    asset = args[0].upper()
    direction = args[1].upper()
    entry = float(args[2])
    sl = float(args[3])
    tp1 = float(args[4])
    tp2 = float(args[5])
    lot = float(args[6])
    balance = float(args[7])

    summary = compute_summary(asset, direction, entry, sl, tp1, tp2, lot, balance)

    if output_mode == "json":
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif output_mode == "compact":
        print(render_compact_block(summary))
    else:
        print(render_html_block(summary))
