#!/usr/bin/env python3
"""
GOLD TACTIC — Opportunity Scanner
Scans 15 stocks/crypto for momentum setups, scores them, sends Telegram shortlist.
Runs 2x/day: 08:00 EET (pre-Europe) and 15:30 EET (NY open).

Usage:
  python opportunity_scanner.py              # Full scan
  python opportunity_scanner.py --top 5      # Show top 5 only
  python opportunity_scanner.py --telegram   # Scan + send Telegram
"""

import yfinance as yf
import numpy as np
import pandas as pd
import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ============================================================
# CONFIG
# ============================================================

OUTPUT_DIR = Path(__file__).parent.parent
OPPORTUNITIES_FILE = OUTPUT_DIR / "opportunities.json"

# Telegram
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN',
    '8621254551:AAF3z5R-5JrAzTKaZQ31E3pmXxtlvQ10wFc')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '-1003767339297')

# Assets to scan
SCAN_ASSETS = {
    # Mega Cap Stocks
    "AAPL":  {"yf": "AAPL",     "name": "Apple",        "type": "stock",  "price_fmt": ",.2f"},
    "TSLA":  {"yf": "TSLA",     "name": "Tesla",        "type": "stock",  "price_fmt": ",.2f"},
    "NVDA":  {"yf": "NVDA",     "name": "Nvidia",       "type": "stock",  "price_fmt": ",.2f"},
    "META":  {"yf": "META",     "name": "Meta",         "type": "stock",  "price_fmt": ",.2f"},
    "AMZN":  {"yf": "AMZN",     "name": "Amazon",       "type": "stock",  "price_fmt": ",.2f"},
    "MSFT":  {"yf": "MSFT",     "name": "Microsoft",    "type": "stock",  "price_fmt": ",.2f"},
    "GOOGL": {"yf": "GOOGL",    "name": "Google",       "type": "stock",  "price_fmt": ",.2f"},
    # Volatile Tech
    "AMD":   {"yf": "AMD",      "name": "AMD",          "type": "stock",  "price_fmt": ",.2f"},
    "INTC":  {"yf": "INTC",     "name": "Intel",        "type": "stock",  "price_fmt": ",.2f"},
    "COIN":  {"yf": "COIN",     "name": "Coinbase",     "type": "stock",  "price_fmt": ",.2f"},
    "PLTR":  {"yf": "PLTR",     "name": "Palantir",     "type": "stock",  "price_fmt": ",.2f"},
    "SQ":    {"yf": "SQ",       "name": "Block/Square", "type": "stock",  "price_fmt": ",.2f"},  # May be delisted
    "MSTR":  {"yf": "MSTR",    "name": "MicroStrategy","type": "stock",  "price_fmt": ",.2f"},
    # Crypto
    "BTC":   {"yf": "BTC-USD",  "name": "Bitcoin",      "type": "crypto", "price_fmt": ",.0f"},
    "ETH":   {"yf": "ETH-USD",  "name": "Ethereum",     "type": "crypto", "price_fmt": ",.2f"},
    "SOL":   {"yf": "SOL-USD",  "name": "Solana",       "type": "crypto", "price_fmt": ",.2f"},
}

# Scoring weights
WEIGHTS = {
    "volume_spike": 25,
    "trend_clarity": 25,
    "rsi_setup": 20,
    "gap_breakout": 15,
    "adr_room": 15,
}


# ============================================================
# SCORING FUNCTIONS
# ============================================================

def compute_rsi(series, period=14):
    """Compute RSI."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def score_volume_spike(df):
    """Score 0-100: today's volume vs 20-day average."""
    if len(df) < 21 or 'Volume' not in df.columns:
        return 0

    avg_vol_20 = df['Volume'].iloc[-21:-1].mean()
    if avg_vol_20 == 0:
        return 0

    today_vol = df['Volume'].iloc[-1]
    ratio = today_vol / avg_vol_20

    if ratio >= 3.0:
        return 100
    elif ratio >= 2.0:
        return 80
    elif ratio >= 1.5:
        return 60
    elif ratio >= 1.2:
        return 40
    elif ratio >= 1.0:
        return 20
    return 0


def score_trend_clarity(df):
    """Score 0-100: EMA9/EMA21 alignment and separation."""
    if len(df) < 21:
        return 0

    ema9 = df['Close'].ewm(span=9, adjust=False).mean()
    ema21 = df['Close'].ewm(span=21, adjust=False).mean()

    price = df['Close'].iloc[-1]
    e9 = ema9.iloc[-1]
    e21 = ema21.iloc[-1]

    # Both EMAs same direction = clear trend
    if e9 > e21 and price > e9:  # Strong bull
        separation = abs(e9 - e21) / price * 100
        return min(100, int(50 + separation * 20))
    elif e9 < e21 and price < e9:  # Strong bear
        separation = abs(e9 - e21) / price * 100
        return min(100, int(50 + separation * 20))
    elif e9 > e21:  # Weak bull
        return 30
    elif e9 < e21:  # Weak bear
        return 30
    return 10  # Flat


def score_rsi_setup(df):
    """Score 0-100: RSI in reversal zone (near 30 or 70)."""
    if len(df) < 15:
        return 0

    rsi = compute_rsi(df['Close'], 14)
    current_rsi = rsi.iloc[-1]
    prev_rsi = rsi.iloc[-2] if len(rsi) > 1 else current_rsi

    if np.isnan(current_rsi):
        return 0

    # Bouncing off oversold (long setup)
    if 25 <= current_rsi <= 40 and current_rsi > prev_rsi:
        return 90
    # Rejecting overbought (short setup)
    elif 60 <= current_rsi <= 75 and current_rsi < prev_rsi:
        return 80
    # Deep oversold bounce
    elif current_rsi < 25 and current_rsi > prev_rsi:
        return 70
    # Approaching zones
    elif 40 <= current_rsi <= 60:
        return 20  # Neutral
    return 30


def score_gap_breakout(df):
    """Score 0-100: gap from previous close or breakout from range."""
    if len(df) < 21:
        return 0

    price = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2]
    high_20 = df['High'].iloc[-21:-1].max()
    low_20 = df['Low'].iloc[-21:-1].min()

    # Gap calculation
    gap_pct = abs(price - prev_close) / prev_close * 100

    # Breakout detection
    is_breakout_high = price > high_20
    is_breakout_low = price < low_20

    score = 0
    if gap_pct >= 3.0:
        score += 60
    elif gap_pct >= 1.5:
        score += 40
    elif gap_pct >= 0.5:
        score += 20

    if is_breakout_high or is_breakout_low:
        score += 40

    return min(100, score)


def score_adr_room(df):
    """Score 0-100: how much of ADR is left today."""
    if len(df) < 21:
        return 0

    # Calculate 20-day ADR
    daily_ranges = (df['High'] - df['Low']).iloc[-21:-1]
    adr = daily_ranges.mean()

    if adr == 0:
        return 0

    # Today's range consumed
    today_high = df['High'].iloc[-1]
    today_low = df['Low'].iloc[-1]
    today_range = today_high - today_low
    consumed = today_range / adr

    # More room left = higher score
    if consumed < 0.3:
        return 100  # Lots of room
    elif consumed < 0.5:
        return 80
    elif consumed < 0.7:
        return 60
    elif consumed < 0.9:
        return 40
    elif consumed < 1.0:
        return 20
    return 0  # ADR exhausted


# ============================================================
# SCANNER
# ============================================================

def scan_asset(symbol, config):
    """Scan a single asset and return score + details."""
    try:
        df = yf.download(
            config["yf"], period="3mo", interval="1d",
            progress=False, auto_adjust=True,
        )

        if df.empty or len(df) < 21:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Calculate scores
        scores = {
            "volume_spike": score_volume_spike(df),
            "trend_clarity": score_trend_clarity(df),
            "rsi_setup": score_rsi_setup(df),
            "gap_breakout": score_gap_breakout(df),
            "adr_room": score_adr_room(df),
        }

        # Weighted total
        total = sum(scores[k] * WEIGHTS[k] / 100 for k in scores)

        # Extra info
        price = float(df['Close'].iloc[-1])
        rsi = compute_rsi(df['Close'], 14).iloc[-1]
        ema9 = float(df['Close'].ewm(span=9, adjust=False).mean().iloc[-1])
        ema21 = float(df['Close'].ewm(span=21, adjust=False).mean().iloc[-1])
        vol_ratio = float(df['Volume'].iloc[-1] / df['Volume'].iloc[-21:-1].mean()) if df['Volume'].iloc[-21:-1].mean() > 0 else 0
        change_pct = float((price - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100)

        trend = "BULL" if ema9 > ema21 else "BEAR" if ema9 < ema21 else "FLAT"

        return {
            "symbol": symbol,
            "name": config["name"],
            "type": config["type"],
            "price": price,
            "price_fmt": config["price_fmt"],
            "change_pct": round(change_pct, 2),
            "rsi": round(float(rsi), 1) if not np.isnan(rsi) else 0,
            "trend": trend,
            "volume_ratio": round(vol_ratio, 2),
            "scores": scores,
            "total_score": round(total, 1),
        }

    except Exception as e:
        print(f"  [ERROR] {symbol}: {e}")
        return None


def scan_all(top_n=None):
    """Scan all assets and return sorted results."""
    print(f"GOLD TACTIC - Opportunity Scanner")
    print(f"Scanning {len(SCAN_ASSETS)} assets at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    results = []
    for symbol, config in SCAN_ASSETS.items():
        print(f"  Scanning {symbol}...", end=" ")
        result = scan_asset(symbol, config)
        if result:
            print(f"Score: {result['total_score']}/100 | "
                  f"${result['price']:{result['price_fmt']}} | "
                  f"{result['trend']} | RSI: {result['rsi']}")
            results.append(result)
        else:
            print("FAILED")

    # Sort by score
    results.sort(key=lambda x: -x["total_score"])

    if top_n:
        results = results[:top_n]

    # Save to file
    output = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scan_type": "morning" if datetime.now().hour < 12 else "afternoon",
        "total_scanned": len(SCAN_ASSETS),
        "results": results,
        "hot": [r for r in results if r["total_score"] >= 75],
        "warm": [r for r in results if 50 <= r["total_score"] < 75],
    }

    OPPORTUNITIES_FILE.write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8'
    )

    print(f"\nResults saved to {OPPORTUNITIES_FILE}")
    return output


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(text):
    """Send HTML message to Telegram."""
    import urllib.request
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    payload = json.dumps({
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload,
                                headers={'Content-Type': 'application/json'})
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode())


def format_telegram(output):
    """Format scan results for Telegram."""
    scan_type = "Πρωινό" if output["scan_type"] == "morning" else "Απογευματινό"
    now = datetime.now().strftime("%H:%M EET")

    lines = [
        f"🔍 <b>OPPORTUNITY SCAN — {scan_type}</b>",
        f"🕐 {now} | {output['total_scanned']} assets",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    # HOT assets (score >= 75)
    if output["hot"]:
        for r in output["hot"]:
            emoji = "📈" if r["trend"] == "BULL" else "📉"
            type_emoji = "💹" if r["type"] == "stock" else "🪙"
            lines.append(
                f"🟢 <b>{r['symbol']}</b> | Score: {r['total_score']}/100 | "
                f"${r['price']:{r['price_fmt']}}"
            )
            lines.append(
                f"   {type_emoji} {r['name']} | {emoji} {r['trend']} | "
                f"RSI: {r['rsi']} | Vol: x{r['volume_ratio']}"
            )

            # Top reason
            top_score = max(r["scores"], key=r["scores"].get)
            score_labels = {
                "volume_spike": "Volume spike",
                "trend_clarity": "Καθαρό trend",
                "rsi_setup": "RSI setup",
                "gap_breakout": "Gap/Breakout",
                "adr_room": "ADR room",
            }
            lines.append(
                f"   💡 Κύριος λόγος: {score_labels.get(top_score, top_score)} "
                f"({r['scores'][top_score]}/100)"
            )
            lines.append("")
    else:
        lines.append("⚪ Κανένα HOT σήμα (score πάνω από 75)")
        lines.append("")

    # WARM assets (50-74)
    if output["warm"]:
        lines.append("🟡 <b>WARM (παρακολούθηση):</b>")
        for r in output["warm"]:
            lines.append(
                f"   {r['symbol']}: {r['total_score']}/100 | "
                f"${r['price']:{r['price_fmt']}} | {r['trend']} | "
                f"Δ{r['change_pct']:+.1f}%"
            )
        lines.append("")

    # Cold count
    cold_count = output["total_scanned"] - len(output["hot"]) - len(output["warm"])
    if cold_count > 0:
        lines.append(f"🔴 {cold_count} assets χωρίς σήμα (score κάτω από 50)")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    if output["hot"]:
        hot_names = ", ".join(r["symbol"] for r in output["hot"])
        lines.append(f"📌 <b>Πρόταση:</b> Πρόσθεσε {hot_names} στον 20λεπτο κύκλο")
    else:
        lines.append("📌 <b>Πρόταση:</b> Κράτα μόνο Gold/NAS/EUR σήμερα")

    lines.append("🤖 GOLD TACTIC v2.0 | Opportunity Scanner")

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    send_tg = "--telegram" in sys.argv
    top_n = None

    for i, arg in enumerate(sys.argv):
        if arg == "--top" and i + 1 < len(sys.argv):
            top_n = int(sys.argv[i + 1])

    output = scan_all(top_n)

    # Print summary
    print(f"\n{'='*50}")
    print(f"HOT ({len(output['hot'])}): {', '.join(r['symbol'] for r in output['hot']) or 'None'}")
    print(f"WARM ({len(output['warm'])}): {', '.join(r['symbol'] for r in output['warm']) or 'None'}")
    print(f"{'='*50}")

    if send_tg:
        msg = format_telegram(output)
        result = send_telegram(msg)
        print(f"\nTelegram sent, ID: {result.get('result', {}).get('message_id')}")
