#!/usr/bin/env python3
"""
GOLD TACTIC — TRS Calculator (Trade Readiness Score)
Αλγοριθμικός υπολογισμός TRS 0-5 για κάθε asset.
Ο AI Analyst χρησιμοποιεί αυτό ως baseline και μπορεί να κάνει override ±1 με αιτιολόγηση.

5 Κριτήρια:
  1. Daily bias ξεκάθαρο (BULL/BEAR, όχι MIXED)
  2. 4H ευθυγραμμισμένο με Daily
  3. Asia Sweep ή IB Breakout (τιμή πέρασε PDH/PDL)
  4. Νέα στηρίζουν την κατεύθυνση
  5. Break of Structure + ADR < 90% (χώρος κίνησης)

Reads:  data/quick_scan.json, data/news_feed.json, data/correlation_matrix.json, data/portfolio.json
Writes: data/trs_scores.json

Usage:
  python trs_calculator.py              # Terminal output
  python trs_calculator.py --json       # JSON output for Agent
  python trs_calculator.py EURUSD BTC   # Specific assets only
"""

import json
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

DATA_DIR = Path(__file__).parent.parent / "data"
QUICK_SCAN_FILE = DATA_DIR / "quick_scan.json"
NEWS_FEED_FILE = DATA_DIR / "news_feed.json"
CORRELATION_FILE = DATA_DIR / "correlation_matrix.json"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
OUTPUT_FILE = DATA_DIR / "trs_scores.json"

# ── Keyword λίστες για sentiment detection σε headlines ──────────────────────

BULLISH_KEYWORDS = [
    "rally", "surge", "soar", "jump", "gain", "rise", "bullish", "breakout",
    "record high", "all-time high", "ath", "pump", "boost", "recovery",
    "strong", "upbeat", "optimistic", "hawkish", "buy", "long",
    "ανοδικά", "ράλι", "κέρδη", "άνοδος",
]

BEARISH_KEYWORDS = [
    "crash", "plunge", "dump", "drop", "fall", "decline", "bearish",
    "breakdown", "sell-off", "selloff", "fear", "panic", "recession",
    "weak", "dovish", "cut", "loss", "risk-off", "downgrade",
    "πτώση", "κατάρρευση", "ζημιά", "πτωτικά",
]

# Ποια news keywords αντιστοιχούν σε κάθε asset
ASSET_NEWS_TAGS = {
    "EURUSD": ["eurusd", "eur/usd", "euro", "ecb", "eurozone", "eur"],
    "GBPUSD": ["gbpusd", "gbp/usd", "pound", "sterling", "boe", "gbp", "uk economy"],
    "NAS100": ["nasdaq", "nas100", "tech stocks", "us100", "ndx", "sp500", "s&p"],
    "XAUUSD": ["gold", "xauusd", "xau", "precious metal", "safe haven", "bullion"],
    "BTC":    ["bitcoin", "btc", "crypto"],
    "SOL":    ["solana", "sol", "crypto"],
    "ETH":    ["ethereum", "eth", "crypto"],
}


# ══════════════════════════════════════════════════════════════════════════════
# CRITERION 1: Daily Bias Clear
# ══════════════════════════════════════════════════════════════════════════════

def check_daily_bias_clear(asset_data):
    """
    Κριτήριο 1: Η ημερήσια κατεύθυνση είναι ξεκάθαρη (BULL ή BEAR).

    Returns: (met: bool, reason: str)
    """
    bias = asset_data.get("daily_bias", "N/A")
    if bias in ("BULL", "BEAR"):
        return True, f"Daily bias σαφές: {bias}"
    return False, f"Daily bias ασαφές: {bias} (χρειάζεται BULL ή BEAR)"


# ══════════════════════════════════════════════════════════════════════════════
# CRITERION 2: 4H Aligned with Daily
# ══════════════════════════════════════════════════════════════════════════════

def check_4h_aligned(asset_data):
    """
    Κριτήριο 2: Το 4ωρο timeframe δείχνει ίδια κατεύθυνση με το Daily.

    Returns: (met: bool, reason: str)
    """
    daily = asset_data.get("daily_bias", "N/A")
    h4 = asset_data.get("h4_bias", "N/A")

    if daily in ("BULL", "BEAR") and h4 == daily:
        return True, f"4H ({h4}) ευθυγραμμισμένο με Daily ({daily})"

    if daily in ("BULL", "BEAR") and h4 != daily:
        return False, f"4H ({h4}) ΔΕΝ ευθυγραμμίζεται με Daily ({daily})"

    return False, f"Daily ({daily}) ή 4H ({h4}) δεν είναι σαφή"


# ══════════════════════════════════════════════════════════════════════════════
# CRITERION 3: Asia Sweep / IB Breakout
# ══════════════════════════════════════════════════════════════════════════════

def check_asia_sweep_or_ib(asset_data):
    """
    Κριτήριο 3: Η τιμή πέρασε πάνω από PDH ή κάτω από PDL (sweep).

    PDH = Previous Day High, PDL = Previous Day Low
    Αυτό δείχνει ότι η αγορά "σκούπισε" liquidity — σημαντικό σημάδι.

    Returns: (met: bool, reason: str)
    """
    price = asset_data.get("price")
    pdh = asset_data.get("pdh")
    pdl = asset_data.get("pdl")

    if price is None or pdh is None or pdl is None:
        return False, "Λείπουν δεδομένα τιμής ή PDH/PDL"

    if price > pdh:
        return True, f"Sweep UP: τιμή {price:.5g} > PDH {pdh:.5g}"
    elif price < pdl:
        return True, f"Sweep DOWN: τιμή {price:.5g} < PDL {pdl:.5g}"

    # Ελέγχουμε αν είμαστε κοντά (εντός 20% του range)
    day_range = pdh - pdl
    if day_range > 0:
        proximity_high = (pdh - price) / day_range
        proximity_low = (price - pdl) / day_range
        if proximity_high < 0.10:
            return False, f"Πλησιάζει PDH ({proximity_high:.0%} απόσταση) — ακόμα δεν σπάει"
        elif proximity_low < 0.10:
            return False, f"Πλησιάζει PDL ({proximity_low:.0%} απόσταση) — ακόμα δεν σπάει"

    return False, f"Τιμή {price:.5g} εντός PDH/PDL range ({pdl:.5g}–{pdh:.5g})"


# ══════════════════════════════════════════════════════════════════════════════
# CRITERION 4: News Support
# ══════════════════════════════════════════════════════════════════════════════

def _detect_headline_sentiment(headline):
    """
    Απλή keyword-based ανίχνευση sentiment σε headline.

    Returns: "bullish", "bearish", ή "neutral"
    """
    if not headline:
        return "neutral"

    lower = headline.lower()
    bull_score = sum(1 for kw in BULLISH_KEYWORDS if kw in lower)
    bear_score = sum(1 for kw in BEARISH_KEYWORDS if kw in lower)

    if bull_score > bear_score:
        return "bullish"
    elif bear_score > bull_score:
        return "bearish"
    return "neutral"


def _is_news_relevant(article, asset_name):
    """Ελέγχει αν ένα article αφορά συγκεκριμένο asset."""
    tags = ASSET_NEWS_TAGS.get(asset_name, [])
    if not tags:
        return False

    # Τσέκαρε headline + summary
    text = ""
    text += (article.get("headline") or article.get("title") or "").lower()
    text += " " + (article.get("summary") or article.get("description") or "").lower()

    # Τσέκαρε asset_tags αν υπάρχουν (από news_scout_v2.py)
    article_tags = article.get("asset_tags", [])
    if article_tags:
        for tag in article_tags:
            if tag.lower() == asset_name.lower():
                return True

    return any(tag in text for tag in tags)


def check_news_support(asset_name, asset_data, news_data):
    """
    Κριτήριο 4: Τα νέα στηρίζουν (ή δεν αντιβαίνουν) την κατεύθυνση.

    Logic:
    - Βρες relevant articles για το asset
    - Μέτρα bullish/bearish sentiment
    - Αν daily_bias = BULL, χρειάζεται bullish >= bearish
    - Αν daily_bias = BEAR, χρειάζεται bearish >= bullish
    - Αν δεν υπάρχουν νέα → "neutral" (δεν μπλοκάρει)

    Returns: (met: bool, reason: str)
    """
    daily_bias = asset_data.get("daily_bias", "N/A")
    if daily_bias not in ("BULL", "BEAR"):
        return False, "Daily bias ασαφές — δεν μπορώ να αξιολογήσω νέα"

    articles = news_data.get("articles", [])
    if not articles:
        # Χωρίς νέα → neutral, δεν μπλοκάρει
        return True, "Δεν υπάρχουν νέα — neutral (δεν μπλοκάρει)"

    relevant = [a for a in articles if _is_news_relevant(a, asset_name)]

    if not relevant:
        return True, f"Κανένα σχετικό νέο για {asset_name} — neutral"

    bullish_count = 0
    bearish_count = 0

    for article in relevant:
        # Πρώτα τσέκαρε αν υπάρχει ήδη sentiment field (CryptoPanic)
        sentiment = article.get("sentiment", "").lower()
        if not sentiment or sentiment == "neutral":
            sentiment = _detect_headline_sentiment(
                article.get("headline") or article.get("title") or ""
            )

        if sentiment == "bullish":
            bullish_count += 1
        elif sentiment == "bearish":
            bearish_count += 1

    total = len(relevant)

    if daily_bias == "BULL":
        if bullish_count >= bearish_count:
            return True, f"Νέα στηρίζουν BULL ({bullish_count}↑ vs {bearish_count}↓ από {total})"
        return False, f"Νέα αντιβαίνουν BULL ({bullish_count}↑ vs {bearish_count}↓ από {total})"

    else:  # BEAR
        if bearish_count >= bullish_count:
            return True, f"Νέα στηρίζουν BEAR ({bearish_count}↓ vs {bullish_count}↑ από {total})"
        return False, f"Νέα αντιβαίνουν BEAR ({bearish_count}↓ vs {bullish_count}↑ από {total})"


# ══════════════════════════════════════════════════════════════════════════════
# CRITERION 5: Break of Structure + Room (ADR < 90%)
# ══════════════════════════════════════════════════════════════════════════════

def check_bos_and_room(asset_data):
    """
    Κριτήριο 5: Ισχυρή ευθυγράμμιση (BOS proxy) + ADR < 90%.

    "ALIGNED_BULL" ή "ALIGNED_BEAR" σημαίνει ότι Daily + 4H + 1H δείχνουν
    ίδια κατεύθυνση — proxy για Break of Structure.

    Returns: (met: bool, reason: str)
    """
    alignment = asset_data.get("alignment", "MIXED")
    adr_pct = asset_data.get("adr_consumed_pct")

    has_bos = "ALIGNED" in alignment
    has_room = adr_pct is not None and adr_pct < 90

    if has_bos and has_room:
        return True, f"BOS ({alignment}) + ADR {adr_pct:.0f}% (< 90% — υπάρχει χώρος)"

    reasons = []
    if not has_bos:
        reasons.append(f"alignment={alignment} (χρειάζεται ALIGNED)")
    if adr_pct is not None and adr_pct >= 90:
        reasons.append(f"ADR {adr_pct:.0f}% ≥ 90% (εξαντλημένη κίνηση)")
    elif adr_pct is None:
        reasons.append("ADR δεν υπολογίστηκε")

    return False, " + ".join(reasons)


# ══════════════════════════════════════════════════════════════════════════════
# ADR GATE (Hard Cutoff — FIX #7)
# ══════════════════════════════════════════════════════════════════════════════

def check_adr_gate(asset_data):
    """
    Hard ADR cutoff στο 85%.

    Exception: TRENDING regime + volume_ratio > 1.5 + ALIGNED →
    επιτρέπεται με 50% risk reduction.

    Returns: dict {blocked, risk_modifier, reason}
    """
    adr_pct = asset_data.get("adr_consumed_pct")
    regime = asset_data.get("regime", "UNKNOWN")
    volume_ratio = asset_data.get("volume_ratio") or 0
    alignment = asset_data.get("alignment", "MIXED")

    if adr_pct is None:
        return {"blocked": False, "risk_modifier": 1.0, "reason": "ADR δεν υπολογίστηκε"}

    if adr_pct <= 85:
        return {"blocked": False, "risk_modifier": 1.0, "reason": f"ADR {adr_pct:.0f}% OK"}

    # TRENDING exception
    if regime == "TRENDING" and volume_ratio > 1.5 and "ALIGNED" in alignment:
        return {
            "blocked": False,
            "risk_modifier": 0.5,
            "reason": f"ADR {adr_pct:.0f}% > 85% αλλά TRENDING + volume {volume_ratio:.1f}x → 50% risk"
        }

    return {
        "blocked": True,
        "risk_modifier": 0.0,
        "reason": f"ADR {adr_pct:.0f}% > 85% — BLOCKED (regime: {regime}, vol: {volume_ratio:.1f}x)"
    }


# ══════════════════════════════════════════════════════════════════════════════
# CORRELATION FILTER (FIX #6)
# ══════════════════════════════════════════════════════════════════════════════

CORRELATION_PAIRS_MAP = [
    ("EURUSD", "GBPUSD"),
    ("BTC", "SOL"),
    ("NAS100", "BTC"),
]


def check_correlation_blocks(trs_results, correlation_data, open_trades):
    """
    Ελέγχει αν 2 correlated assets πρέπει να μπλοκαριστούν.

    Κανόνας: αν correlation > 0.80 και ένα asset έχει ανοιχτό trade,
    το άλλο μπλοκάρεται (εκτός αν το ανοιχτό trade έχει TP1 hit = zero risk).

    Args:
        trs_results: dict {asset: {trs_score, direction, ...}}
        correlation_data: dict {correlations: {PAIR: float}}
        open_trades: list of trade dicts from portfolio.json

    Returns: dict {asset: {blocked, reason, correlated_with, correlation_value}}
    """
    corr_values = correlation_data.get("correlations", {})

    # Φτιάξε set από assets με ανοιχτά trades
    open_assets = {}
    for trade in open_trades:
        asset = trade.get("asset") or trade.get("symbol")
        if asset:
            open_assets[asset] = trade

    blocks = {}

    for asset_a, asset_b in CORRELATION_PAIRS_MAP:
        pair_key = f"{asset_a}_{asset_b}"
        corr_val = corr_values.get(pair_key)

        if corr_val is None or abs(corr_val) <= 0.80:
            continue

        # Correlation > 0.80 — τσέκαρε αν ένα έχει ανοιχτό trade
        if asset_a in open_assets and asset_b in trs_results:
            trade = open_assets[asset_a]
            tp1_hit = trade.get("tp1_hit", False)
            if not tp1_hit:
                blocks[asset_b] = {
                    "blocked": True,
                    "reason": f"Correlation {corr_val:.3f} > 0.80 με {asset_a} (ανοιχτό trade)",
                    "correlated_with": asset_a,
                    "correlation_value": corr_val,
                }

        if asset_b in open_assets and asset_a in trs_results:
            trade = open_assets[asset_b]
            tp1_hit = trade.get("tp1_hit", False)
            if not tp1_hit:
                blocks[asset_a] = {
                    "blocked": True,
                    "reason": f"Correlation {corr_val:.3f} > 0.80 με {asset_b} (ανοιχτό trade)",
                    "correlated_with": asset_b,
                    "correlation_value": corr_val,
                }

        # Αν κανένα δεν έχει ανοιχτό trade αλλά και τα δύο TRS >= 4
        if asset_a not in open_assets and asset_b not in open_assets:
            trs_a = trs_results.get(asset_a, {}).get("trs_score", 0)
            trs_b = trs_results.get(asset_b, {}).get("trs_score", 0)
            if trs_a >= 4 and trs_b >= 4:
                # Μπλόκαρε αυτό με χαμηλότερο TRS
                if trs_a >= trs_b:
                    blocks[asset_b] = {
                        "blocked": True,
                        "reason": f"Corr {corr_val:.3f} > 0.80, {asset_a} TRS={trs_a} > {asset_b} TRS={trs_b}",
                        "correlated_with": asset_a,
                        "correlation_value": corr_val,
                    }
                else:
                    blocks[asset_a] = {
                        "blocked": True,
                        "reason": f"Corr {corr_val:.3f} > 0.80, {asset_b} TRS={trs_b} > {asset_a} TRS={trs_a}",
                        "correlated_with": asset_b,
                        "correlation_value": corr_val,
                    }

    return blocks


# ══════════════════════════════════════════════════════════════════════════════
# PROXIMITY & TIME ESTIMATION (Card System)
# ══════════════════════════════════════════════════════════════════════════════

# Pip sizes per asset (for trigger distance calculation)
ASSET_PIP_SIZES = {
    "EURUSD": 0.0001, "GBPUSD": 0.0001, "XAUUSD": 0.01,
    "NAS100": 1.0, "BTC": 1.0, "SOL": 0.01, "ETH": 1.0,
}


def compute_proximity_score(trs_score, asset_data, adr_gate, correlation_block):
    """
    Υπολογίζει πόσο κοντά είμαστε σε trade (0-100%).

    Base = (TRS/5) * 100
    Modifiers: ADR, regime, correlation, trigger distance

    Returns: int (0-100)
    """
    if adr_gate.get("blocked"):
        return 0
    if correlation_block:
        return 0

    base = (trs_score / 5) * 100

    # ADR penalty
    adr_pct = asset_data.get("adr_consumed_pct") or 0
    regime = asset_data.get("regime", "UNKNOWN")
    if adr_pct > 85 and regime != "TRENDING":
        base -= 20

    # Choppy penalty
    if regime == "CHOPPY":
        base -= 30

    # Trigger proximity bonus (price near PDH/PDL)
    price = asset_data.get("price")
    pdh = asset_data.get("pdh")
    pdl = asset_data.get("pdl")
    if price and pdh and pdl:
        range_size = pdh - pdl
        if range_size > 0:
            dist_to_trigger = min(abs(price - pdh), abs(price - pdl))
            proximity_ratio = dist_to_trigger / range_size
            if proximity_ratio < 0.15:
                base += 10  # Very close to sweep level

    return max(0, min(100, int(base)))


def estimate_trade_time(trs_score, asset_name, asset_data):
    """
    Εκτιμά πόσο χρόνο μέχρι πιθανό trade.

    Returns: str ή None (αν δεν αξίζει να δείξουμε)
    """
    if trs_score >= 5:
        return "ΤΩΡΑ — trade ready!"

    if trs_score == 4:
        # Υπολόγισε απόσταση σε pips από trigger
        price = asset_data.get("price")
        pdh = asset_data.get("pdh")
        pdl = asset_data.get("pdl")
        pip_size = ASSET_PIP_SIZES.get(asset_name, 0.0001)

        if price and pdh and pdl and pip_size > 0:
            dist = min(abs(price - pdh), abs(price - pdl))
            pips = dist / pip_size
            if pips < 10:
                return "~15-30 λεπτά"
        return "~30-60 λεπτά"

    if trs_score == 3:
        if asset_data.get("regime") == "TRENDING":
            return "~1-2 ώρες"
        return "~2-4 ώρες (αν κινηθεί)"

    if trs_score == 2:
        return "Δεν βλέπω σύντομα"

    return None  # TRS 0-1: don't show


def format_proximity_bar(pct):
    """
    Δημιουργεί visual progress bar για proximity.

    Returns: str "[▓▓▓▓▓░░░░░] 50% — μισός δρόμος"
    """
    filled = max(0, min(10, round(pct / 10)))
    bar = "\u2593" * filled + "\u2591" * (10 - filled)

    if pct >= 80:
        label = "σχεδόν εκεί!"
    elif pct >= 60:
        label = "πλησιάζει"
    elif pct >= 40:
        label = "μισός δρόμος"
    elif pct >= 20:
        label = "νωρίς"
    else:
        label = "μακριά"

    return f"[{bar}] {pct}% \u2014 {label}"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN TRS CALCULATOR
# ══════════════════════════════════════════════════════════════════════════════

def calculate_trs(asset_name, asset_data, news_data):
    """
    Υπολογίζει TRS 0-5 για ένα asset.

    Returns: dict {
        trs_score: int (0-5),
        direction: str (BULL/BEAR/NONE),
        criteria: [{name, met, reason}],
        met_count: int,
        adr_gate: {blocked, risk_modifier, reason}
    }
    """
    criteria = []

    # Κριτήριο 1: Daily bias clear
    met1, reason1 = check_daily_bias_clear(asset_data)
    criteria.append({"name": "Daily Bias Clear", "met": met1, "reason": reason1})

    # Κριτήριο 2: 4H aligned
    met2, reason2 = check_4h_aligned(asset_data)
    criteria.append({"name": "4H Aligned", "met": met2, "reason": reason2})

    # Κριτήριο 3: Asia Sweep / IB Breakout
    met3, reason3 = check_asia_sweep_or_ib(asset_data)
    criteria.append({"name": "Asia Sweep / IB Breakout", "met": met3, "reason": reason3})

    # Κριτήριο 4: News support
    met4, reason4 = check_news_support(asset_name, asset_data, news_data)
    criteria.append({"name": "News Support", "met": met4, "reason": reason4})

    # Κριτήριο 5: BOS + Room
    met5, reason5 = check_bos_and_room(asset_data)
    criteria.append({"name": "BOS + Room (ADR < 90%)", "met": met5, "reason": reason5})

    # Score
    met_count = sum(1 for c in criteria if c["met"])

    # Direction
    daily_bias = asset_data.get("daily_bias", "N/A")
    direction = daily_bias if daily_bias in ("BULL", "BEAR") else "NONE"

    # ADR Gate (hard cutoff)
    adr_gate = check_adr_gate(asset_data)

    # Proximity & Time estimation (Card System)
    proximity = compute_proximity_score(met_count, asset_data, adr_gate, False)
    proximity_bar = format_proximity_bar(proximity)
    time_est = estimate_trade_time(met_count, asset_name, asset_data)

    return {
        "trs_score": met_count,
        "direction": direction,
        "criteria": criteria,
        "met_count": met_count,
        "adr_gate": adr_gate,
        "proximity_score": proximity,
        "proximity_bar": proximity_bar,
        "estimated_time": time_est,
    }


# ══════════════════════════════════════════════════════════════════════════════
# FILE I/O
# ══════════════════════════════════════════════════════════════════════════════

def load_json(filepath, default=None):
    """Ασφαλές φόρτωμα JSON αρχείου."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def main():
    args = sys.argv[1:]
    json_mode = "--json" in args
    args = [a for a in args if a != "--json"]

    # Φόρτωσε δεδομένα
    quick_scan = load_json(QUICK_SCAN_FILE)
    news_feed = load_json(NEWS_FEED_FILE)
    correlation_data = load_json(CORRELATION_FILE)
    portfolio = load_json(PORTFOLIO_FILE)

    if not quick_scan or not quick_scan.get("assets"):
        msg = f"ERROR: {QUICK_SCAN_FILE} δεν βρέθηκε ή είναι κενό. Τρέξε πρώτα quick_scan.py"
        if json_mode:
            print(json.dumps({"error": msg}))
        else:
            print(msg, file=sys.stderr)
        sys.exit(1)

    # Φίλτρο assets αν δόθηκαν ονόματα
    filter_assets = set(a.upper() for a in args) if args else None

    # Υπολόγισε TRS για κάθε asset
    trs_results = {}

    for asset_data in quick_scan["assets"]:
        asset_name = asset_data.get("asset")
        if not asset_name:
            continue

        # Skip DXY (δεν κάνουμε trade στο DXY)
        if asset_name == "DXY":
            continue

        # Φίλτρο αν ζητήθηκαν συγκεκριμένα assets
        if filter_assets and asset_name not in filter_assets:
            continue

        # Skip αν υπάρχει error στο scan
        if asset_data.get("error"):
            trs_results[asset_name] = {
                "trs_score": 0,
                "direction": "NONE",
                "criteria": [],
                "met_count": 0,
                "error": asset_data["error"],
                "adr_gate": {"blocked": True, "risk_modifier": 0.0, "reason": f"Scan error: {asset_data['error']}"},
                "correlation_block": False,
            }
            continue

        result = calculate_trs(asset_name, asset_data, news_feed)
        trs_results[asset_name] = result

    # Correlation blocks
    open_trades = portfolio.get("open_trades", [])
    corr_blocks = check_correlation_blocks(trs_results, correlation_data, open_trades)

    # Ενσωμάτωσε correlation blocks στα results
    for asset_name, result in trs_results.items():
        if asset_name in corr_blocks:
            result["correlation_block"] = True
            result["correlation_info"] = corr_blocks[asset_name]
        else:
            result["correlation_block"] = False

    # Φτιάξε output
    output = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scan_source": quick_scan.get("scan_time", "unknown"),
        "scores": trs_results,
    }

    # Γράψε αρχείο
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"WARNING: Αποτυχία αποθήκευσης {OUTPUT_FILE}: {e}", file=sys.stderr)

    # Output
    if json_mode:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print("GOLD TACTIC — TRS Calculator")
        print(f"Scan: {output['scan_source']}")
        print(f"Time: {output['timestamp']}")
        print("=" * 80)

        for asset_name, result in trs_results.items():
            score = result["trs_score"]
            direction = result["direction"]
            adr_blocked = result.get("adr_gate", {}).get("blocked", False)
            corr_blocked = result.get("correlation_block", False)

            # Emoji βάσει score
            if score >= 5:
                emoji = "🔥"
                label = "TRADE!"
            elif score >= 4:
                emoji = "🟢"
                label = "TRADE"
            elif score == 3:
                emoji = "🟡"
                label = "WAIT"
            else:
                emoji = "⬜"
                label = "SKIP"

            # Blocks override
            if adr_blocked:
                emoji = "🚫"
                label = "ADR BLOCK"
            if corr_blocked:
                emoji = "🔗"
                label = "CORR BLOCK"

            print(f"\n{emoji} {asset_name} — TRS {score}/5 {direction} → {label}")

            for c in result.get("criteria", []):
                mark = "✅" if c["met"] else "❌"
                print(f"   {mark} {c['name']}: {c['reason']}")

            if adr_blocked:
                print(f"   🚫 ADR: {result['adr_gate']['reason']}")
            if corr_blocked:
                print(f"   🔗 CORR: {result['correlation_info']['reason']}")

            # Proximity & Time
            prox = result.get("proximity_score", 0)
            prox_bar = result.get("proximity_bar", "")
            time_est = result.get("estimated_time")
            if prox_bar:
                print(f"   {prox_bar}")
            if time_est:
                print(f"   ⏱️ {time_est}")

        print("\n" + "=" * 80)

        # Summary line
        tradeable = [
            name for name, r in trs_results.items()
            if r["trs_score"] >= 4
            and not r.get("adr_gate", {}).get("blocked", False)
            and not r.get("correlation_block", False)
        ]
        if tradeable:
            print(f"✅ TRADEABLE: {', '.join(tradeable)}")
        else:
            print("⬜ Κανένα asset δεν πληροί TRS ≥ 4 χωρίς blocks")


if __name__ == "__main__":
    main()
