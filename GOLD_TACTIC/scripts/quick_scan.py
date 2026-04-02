#!/usr/bin/env python3
"""
GOLD TACTIC — Quick Scan
Multi-timeframe dashboard: Daily/4H/1H bias, RSI, ADR, Market Regime, Correlations.
Reduces Agent token usage by pre-computing alignment.

Usage:
  python quick_scan.py              # All core assets
  python quick_scan.py EURUSD BTC   # Specific assets
  python quick_scan.py --json       # JSON output for Agent
  python quick_scan.py --changes    # Compare vs last scan, output changes JSON
"""

import json
import sys
import os
import traceback
from datetime import datetime, timedelta
from pathlib import Path

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

OUTPUT_DIR = Path(__file__).parent.parent / "data"
ERROR_LOG = OUTPUT_DIR / "price_checker_errors.log"

def log_error(source, error):
    """Log errors to file for debugging scheduled runs."""
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {source}: {error}\n")
    except:
        pass

try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
except ImportError as e:
    log_error("quick_scan-IMPORT", f"CRITICAL: {type(e).__name__}: {e}\npython={sys.executable}\nPATH={os.environ.get('PATH','?')[:300]}")
    print(f"ERROR: Cannot import required packages: {e}", file=sys.stderr)
    print(f"Python: {sys.executable}", file=sys.stderr)
    sys.exit(1)

ASSETS = {
    "EURUSD": {"yf": "EURUSD=X", "adr_typical": 0.0080, "pip_size": 0.0001},
    "GBPUSD": {"yf": "GBPUSD=X", "adr_typical": 0.0100, "pip_size": 0.0001},
    "NAS100": {"yf": "^NDX",     "adr_typical": 400,     "pip_size": 1.0},
    "SOL":    {"yf": "SOL-USD",  "adr_typical": 6.0,     "pip_size": 0.01},
    "BTC":    {"yf": "BTC-USD",  "adr_typical": 2000,    "pip_size": 1.0},
    "XAUUSD": {"yf": "GC=F",    "adr_typical": 30,      "pip_size": 0.01},
    "DXY":    {"yf": "DX-Y.NYB","adr_typical": 0.6,     "pip_size": 0.01},
    "ETH":    {"yf": "ETH-USD",  "adr_typical": 80,      "pip_size": 0.01},
}


CORRELATION_PAIRS = [
    ("EURUSD", "GBPUSD"),
    ("BTC", "SOL"),
    ("NAS100", "BTC"),
]


def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_atr(df, period=14):
    """Compute Average True Range."""
    high = df['High']
    low = df['Low']
    close = df['Close']
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period, min_periods=period).mean()
    return atr


def compute_adx(df, period=14):
    """Compute ADX, +DI, -DI. Returns dict."""
    high = df['High']
    low = df['Low']
    close = df['Close']

    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    plus_dm[plus_dm <= minus_dm] = 0
    minus_dm[minus_dm <= plus_dm] = 0

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(span=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.ewm(span=period, adjust=False).mean()

    return {
        "adx": adx,
        "plus_di": plus_di,
        "minus_di": minus_di,
    }


def detect_regime(daily_df):
    """Return market regime dict based on ADX and ATR."""
    if daily_df is None or len(daily_df) < 22:
        return {"regime": "UNKNOWN", "adx": None, "atr": None, "atr_percentile": None}

    adx_data = compute_adx(daily_df)
    adx_val = float(adx_data["adx"].iloc[-1]) if not pd.isna(adx_data["adx"].iloc[-1]) else 0
    plus_di = float(adx_data["plus_di"].iloc[-1]) if not pd.isna(adx_data["plus_di"].iloc[-1]) else 0
    minus_di = float(adx_data["minus_di"].iloc[-1]) if not pd.isna(adx_data["minus_di"].iloc[-1]) else 0

    atr = compute_atr(daily_df)
    atr_val = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0
    atr_series = atr.dropna().tail(20)
    atr_percentile = 50
    if len(atr_series) > 0 and atr_val > 0:
        atr_percentile = int((atr_series < atr_val).mean() * 100)

    if adx_val > 25:
        regime = "TRENDING"
    elif adx_val < 20 and atr_percentile < 40:
        regime = "CHOPPY"
    else:
        regime = "RANGING"

    return {
        "regime": regime,
        "adx": round(adx_val, 1),
        "plus_di": round(plus_di, 1),
        "minus_di": round(minus_di, 1),
        "atr": round(atr_val, 4),
        "atr_percentile": atr_percentile,
    }


def compute_volume_ratio(daily_df):
    """Return today's volume vs 20-day average ratio."""
    if daily_df is None or len(daily_df) < 21 or 'Volume' not in daily_df.columns:
        return None
    today_vol = float(daily_df['Volume'].iloc[-1])
    avg_vol = float(daily_df['Volume'].iloc[-21:-1].mean())
    if avg_vol == 0:
        return None
    return round(today_vol / avg_vol, 2)


def get_bias(df):
    if df is None or len(df) < 21:
        return "N/A"
    close = df['Close'].iloc[-1]
    ema9 = df['Close'].ewm(span=9).mean().iloc[-1]
    ema21 = df['Close'].ewm(span=21).mean().iloc[-1]
    if close > ema9 > ema21:
        return "BULL"
    elif close < ema9 < ema21:
        return "BEAR"
    else:
        return "MIXED"


def scan_asset(name, config):
    symbol = config["yf"]
    result = {"asset": name, "error": None}

    try:
        # Daily data (3 months for SMA50)
        daily = yf.download(symbol, period="3mo", interval="1d", progress=False)
        if isinstance(daily.columns, pd.MultiIndex):
            daily.columns = daily.columns.get_level_values(0)

        # 4H data (1 month)
        h4 = yf.download(symbol, period="1mo", interval="1h", progress=False)
        if isinstance(h4.columns, pd.MultiIndex):
            h4.columns = h4.columns.get_level_values(0)

        # 1H data (5 days)
        h1 = yf.download(symbol, period="5d", interval="1h", progress=False)
        if isinstance(h1.columns, pd.MultiIndex):
            h1.columns = h1.columns.get_level_values(0)

        if daily.empty:
            result["error"] = "No data"
            return result

        # Current price
        result["price"] = float(daily['Close'].iloc[-1])

        # Bias per timeframe
        result["daily_bias"] = get_bias(daily)
        result["h4_bias"] = get_bias(h4)
        result["h1_bias"] = get_bias(h1)

        # RSI
        daily_rsi = compute_rsi(daily['Close'])
        result["rsi_daily"] = round(float(daily_rsi.iloc[-1]), 1) if not pd.isna(daily_rsi.iloc[-1]) else None

        h4_rsi = compute_rsi(h4['Close'])
        result["rsi_4h"] = round(float(h4_rsi.iloc[-1]), 1) if len(h4_rsi) > 0 and not pd.isna(h4_rsi.iloc[-1]) else None

        # ADR consumed today
        if len(daily) >= 15:
            recent_ranges = (daily['High'] - daily['Low']).tail(14)
            adr = float(recent_ranges.mean())
            today_range = float(daily['High'].iloc[-1] - daily['Low'].iloc[-1])
            result["adr"] = round(adr, 4 if config["pip_size"] < 0.01 else 2)
            result["adr_consumed_pct"] = round((today_range / adr) * 100, 1) if adr > 0 else 0
        else:
            result["adr_consumed_pct"] = None

        # SMA50
        if len(daily) >= 50:
            sma50 = float(daily['Close'].rolling(50).mean().iloc[-1])
            result["sma50"] = round(sma50, 4 if config["pip_size"] < 0.01 else 2)
            result["above_sma50"] = result["price"] > sma50
        else:
            result["sma50"] = None
            result["above_sma50"] = None

        # Alignment score
        biases = [result["daily_bias"], result["h4_bias"], result["h1_bias"]]
        bull_count = biases.count("BULL")
        bear_count = biases.count("BEAR")
        if bull_count == 3:
            result["alignment"] = "ALIGNED_BULL"
        elif bear_count == 3:
            result["alignment"] = "ALIGNED_BEAR"
        elif bull_count >= 2:
            result["alignment"] = "PARTIAL_BULL"
        elif bear_count >= 2:
            result["alignment"] = "PARTIAL_BEAR"
        else:
            result["alignment"] = "MIXED"

        # Previous day high/low
        if len(daily) >= 2:
            result["pdh"] = float(daily['High'].iloc[-2])
            result["pdl"] = float(daily['Low'].iloc[-2])

        # Regime + Volume
        regime = detect_regime(daily)
        result["regime"] = regime["regime"]
        result["adx"] = regime["adx"]
        result["volume_ratio"] = compute_volume_ratio(daily)

    except Exception as e:
        result["error"] = str(e)
        log_error(f"quick_scan-{name}", f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

    return result


def alignment_emoji(a):
    if "ALIGNED" in a:
        return "✅"
    elif "PARTIAL" in a:
        return "🟡"
    else:
        return "❌"


def compute_correlations():
    """Compute 20-day rolling correlations for key pairs."""
    closes = {}
    for name, config in ASSETS.items():
        try:
            df = yf.download(config["yf"], period="1mo", interval="1d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if not df.empty and len(df) >= 5:
                closes[name] = df['Close'].dropna()
        except Exception as e:
            log_error(f"corr-{name}", str(e))

    correlations = {}
    for a, b in CORRELATION_PAIRS:
        if a in closes and b in closes:
            # Align dates
            s1 = closes[a]
            s2 = closes[b]
            aligned = pd.concat([s1, s2], axis=1).dropna()
            if len(aligned) >= 5:
                corr = float(aligned.iloc[-20:].corr().iloc[0, 1])
                if pd.isna(corr):
                    corr = None
            else:
                corr = None
        else:
            corr = None
        correlations[f"{a}_{b}"] = round(corr, 3) if corr is not None else None

    return correlations


def compute_changes(prev_scan, new_scan):
    """Compare two scans and return a changes dict with deltas and escalation flag."""
    THRESHOLDS = {
        "EURUSD": 15,
        "GBPUSD": 15,
        "XAUUSD": 15,
        "NAS100": 100,
        "BTC":    500,
        "SOL":    1.50,
    }

    prev_prices = {}
    for a in prev_scan.get("assets", []):
        if a.get("price") is not None:
            prev_prices[a["asset"]] = a["price"]

    moves = {}
    escalate = False

    for a in new_scan.get("assets", []):
        name = a.get("asset")
        now_price = a.get("price")
        if name is None or now_price is None:
            continue
        if name not in prev_prices:
            continue

        prev_price = prev_prices[name]
        raw_delta = now_price - prev_price

        if name in ("EURUSD", "GBPUSD"):
            pip_size = ASSETS[name]["pip_size"]
            delta_pips = round(raw_delta / pip_size, 1)
            moves[name] = {
                "prev": round(prev_price, 5),
                "now": round(now_price, 5),
                "pips": delta_pips
            }
            threshold = THRESHOLDS.get(name)
            if threshold and abs(delta_pips) >= threshold:
                escalate = True
        else:
            delta = round(raw_delta, 2)
            moves[name] = {
                "prev": round(prev_price, 2),
                "now": round(now_price, 2),
                "delta": delta
            }
            threshold = THRESHOLDS.get(name)
            if threshold and abs(delta) >= threshold:
                escalate = True

    changed = any(
        abs(m.get("pips", 0)) > 0 or abs(m.get("delta", 0)) > 0
        for m in moves.values()
    )

    return {
        "changed": changed,
        "moves": moves,
        "escalate": escalate
    }


def main():
    args = sys.argv[1:]
    json_mode = "--json" in args
    changes_mode = "--changes" in args
    args = [a for a in args if a not in ("--json", "--changes")]

    assets_to_scan = args if args else ["EURUSD", "GBPUSD", "NAS100", "SOL", "BTC", "DXY"]

    output_file = OUTPUT_DIR / "quick_scan.json"
    corr_file = OUTPUT_DIR / "correlation_matrix.json"
    regime_file = OUTPUT_DIR / "market_regime.json"

    # Load previous scan for --changes mode
    prev_scan = None
    if changes_mode:
        try:
            with open(output_file, 'r') as f:
                prev_scan = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            prev_scan = None

    results = []
    for name in assets_to_scan:
        if name in ASSETS:
            r = scan_asset(name, ASSETS[name])
            results.append(r)

    # Compute correlations
    correlations = compute_correlations()
    with open(corr_file, 'w') as f:
        json.dump({
            "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "correlations": correlations,
        }, f, indent=2)

    # Aggregate regime summary
    regimes = {r["asset"]: r.get("regime", "UNKNOWN") for r in results if not r.get("error")}
    adx_values = {r["asset"]: r.get("adx") for r in results if not r.get("error") and r.get("adx") is not None}
    with open(regime_file, 'w') as f:
        json.dump({
            "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "regimes": regimes,
            "adx": adx_values,
        }, f, indent=2)

    new_scan = {
        "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "assets": results,
        "correlations": correlations,
    }

    # Always save the fresh scan
    with open(output_file, 'w') as f:
        json.dump(new_scan, f, indent=2)

    if changes_mode:
        if prev_scan is None:
            changes_output = {
                "changed": False,
                "moves": {},
                "escalate": False,
                "note": "No previous scan found; this run establishes the baseline."
            }
        else:
            changes_output = compute_changes(prev_scan, new_scan)
        print(json.dumps(changes_output, indent=2))
    elif json_mode:
        print(json.dumps(new_scan, indent=2))
    else:
        print("GOLD TACTIC — Quick Scan Dashboard")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 90)
        print(f"{'Asset':<8} {'Price':>12} {'Daily':>6} {'4H':>6} {'1H':>6} {'RSI(D)':>7} {'RSI(4H)':>8} {'ADR%':>6} {'Regime':>10} {'Align':>15}")
        print("-" * 90)
        for r in results:
            if r.get("error"):
                print(f"{r['asset']:<8} ERROR: {r['error']}")
                continue
            price_str = f"{r.get('price', 0):,.2f}" if r.get('price') else "N/A"
            rsi_d = f"{r['rsi_daily']:.0f}" if r.get('rsi_daily') else "N/A"
            rsi_4h = f"{r['rsi_4h']:.0f}" if r.get('rsi_4h') else "N/A"
            adr = f"{r['adr_consumed_pct']:.0f}%" if r.get('adr_consumed_pct') is not None else "N/A"
            emoji = alignment_emoji(r.get('alignment', 'MIXED'))
            regime = r.get('regime', '?')[:10]
            print(f"{r['asset']:<8} {price_str:>12} {r.get('daily_bias','?'):>6} {r.get('h4_bias','?'):>6} {r.get('h1_bias','?'):>6} {rsi_d:>7} {rsi_4h:>8} {adr:>6} {regime:>10} {emoji} {r.get('alignment','?')}")

        print(f"\nCorrelations: {correlations}")

        # DXY summary
        dxy = next((r for r in results if r['asset'] == 'DXY'), None)
        if dxy and not dxy.get('error'):
            print(f"\n💵 DXY (Dollar Index): {dxy.get('price', 0):.2f} | Bias: {dxy.get('daily_bias', '?')} | RSI: {dxy.get('rsi_daily', '?')}")
            if dxy.get('daily_bias') == 'BULL':
                print("   → USD δυνατό: EURUSD/GBPUSD SHORT bias ενισχυμένο")
            elif dxy.get('daily_bias') == 'BEAR':
                print("   → USD αδύναμο: EURUSD/GBPUSD LONG bias ενισχυμένο")


if __name__ == "__main__":
    main()
