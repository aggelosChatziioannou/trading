#!/usr/bin/env python3
"""
GOLD TACTIC — Liquidity Map (#10)
Identifies key liquidity levels: equal highs/lows, round numbers, PDH/PDL,
prev week H/L, Asia range. Writes data/liquidity_map.json.

Usage:
  python liquidity_map.py              # Generate for selected assets
  python liquidity_map.py XAUUSD BTC  # Specific assets
"""
import sys, json
from datetime import datetime, timedelta
from pathlib import Path

if sys.platform == 'win32':
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except: pass

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT   = DATA_DIR / "liquidity_map.json"
sys.path.insert(0, str(Path(__file__).parent))

TOLERANCE = 0.001  # 0.1% tolerance for "equal" highs/lows

def find_equal_levels(df, col, n=20, tolerance=TOLERANCE):
    """Find clusters of nearly equal highs or lows (liquidity pools)."""
    vals = df[col].tail(n).dropna().tolist()
    clusters = []
    used = set()
    for i, v in enumerate(vals):
        if i in used: continue
        group = [v]
        for j, v2 in enumerate(vals):
            if j != i and j not in used and abs(v2-v)/v < tolerance:
                group.append(v2); used.add(j)
        if len(group) >= 2:
            clusters.append(round(sum(group)/len(group), 5))
            used.add(i)
    return sorted(set(clusters))

def round_numbers(price, n=5):
    """Find N nearest round numbers above and below price."""
    if price > 1000:   step = 100
    elif price > 100:  step = 10
    elif price > 10:   step = 1
    elif price > 1:    step = 0.1
    else:              step = 0.01
    base = round(price / step) * step
    return sorted({round(base + step*i, 5) for i in range(-n, n+1)})

def get_prev_week_hl(df):
    """Return previous week's High and Low."""
    try:
        import pandas as pd
        df_utc = df.copy()
        if df_utc.index.tz: df_utc.index = df_utc.index.tz_localize(None)
        weekly = df_utc.resample("W").agg({"High":"max","Low":"min"})
        if len(weekly) >= 2:
            return float(weekly["High"].iloc[-2]), float(weekly["Low"].iloc[-2])
    except: pass
    return None, None

def build_map(symbol, yf_symbol):
    try:
        import yfinance as yf, pandas as pd
        df = yf.download(yf_symbol, period="1mo", interval="1h", progress=False)
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        if df.empty: return {"error": "no data"}

        price = float(df["Close"].iloc[-1])
        daily = yf.download(yf_symbol, period="3mo", interval="1d", progress=False)
        if isinstance(daily.columns, pd.MultiIndex): daily.columns = daily.columns.get_level_values(0)

        pdh = float(daily["High"].iloc[-2]) if len(daily)>=2 else None
        pdl = float(daily["Low"].iloc[-2])  if len(daily)>=2 else None
        pwh, pwl = get_prev_week_hl(daily)

        eq_highs = find_equal_levels(df, "High")
        eq_lows  = find_equal_levels(df, "Low")
        rounds   = [r for r in round_numbers(price) if abs(r-price)/price < 0.03]  # within 3%

        # Load Asia range if available
        asia_h, asia_l = None, None
        try:
            ar = json.loads((DATA_DIR/"asia_range.json").read_text(encoding="utf-8"))
            a  = ar.get("assets",{}).get(symbol,{})
            asia_h = a.get("asia_high"); asia_l = a.get("asia_low")
        except: pass

        return {
            "symbol": symbol, "price": round(price,5),
            "pdh": round(pdh,5) if pdh else None,
            "pdl": round(pdl,5) if pdl else None,
            "prev_week_high": round(pwh,5) if pwh else None,
            "prev_week_low":  round(pwl,5) if pwl else None,
            "equal_highs": [round(x,5) for x in eq_highs],
            "equal_lows":  [round(x,5) for x in eq_lows],
            "round_numbers": rounds,
            "asia_high": asia_h, "asia_low": asia_l,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        return {"error": str(e)}

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    YF_MAP = {
        "EURUSD":"EURUSD=X","GBPUSD":"GBPUSD=X","USDJPY":"JPY=X","AUDUSD":"AUDUSD=X",
        "XAUUSD":"GC=F","NAS100":"NQ=F","SPX500":"ES=F","BTC":"BTC-USD",
        "ETH":"ETH-USD","SOL":"SOL-USD","XRP":"XRP-USD","DXY":"DX-Y.NYB",
    }
    if args:
        symbols = [a.upper() for a in args]
    else:
        try:
            sel = json.loads((DATA_DIR/"selected_assets.json").read_text(encoding="utf-8"))
            symbols = [s["symbol"] for s in sel.get("selected",[])]
        except:
            symbols = ["XAUUSD","BTC"]

    results = {}
    for sym in symbols:
        yf = YF_MAP.get(sym)
        if not yf: print(f"[SKIP] Unknown: {sym}"); continue
        print(f"  Building liquidity map: {sym}...")
        m = build_map(sym, yf)
        results[sym] = m
        if not m.get("error"):
            print(f"    PDH:{m.get('pdh')} PDL:{m.get('pdl')}  EqH:{m.get('equal_highs')}  EqL:{m.get('equal_lows')}")

    OUTPUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved → {OUTPUT}")

if __name__ == "__main__":
    main()
