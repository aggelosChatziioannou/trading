#!/usr/bin/env python3
"""
GOLD TACTIC — Asia Session Range Tracker
Calculates Asia session High/Low (00:00-09:00 EET) for selected assets.
At 09:00 EET reports: range size, sweep status, TJR setup readiness.
Writes: data/asia_range.json

Usage:
  python asia_range.py              # Check and report
  python asia_range.py --alert      # Also send Telegram if setup forming
"""

import sys
import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_FILE = DATA_DIR / "asia_range.json"

sys.path.insert(0, str(Path(__file__).parent))

# Asia session: 00:00–09:00 EET (= 21:00–06:00 UTC prev day)
ASIA_START_EET = 0
ASIA_END_EET   = 9


def get_5m_bars(yf_symbol):
    """Fetch 5-minute bars for last 2 days via Yahoo Finance."""
    try:
        import yfinance as yf
        import pandas as pd
        df = yf.download(yf_symbol, period="2d", interval="5m", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.empty:
            return None
        # Convert index to UTC+3 (EET)
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        df.index = df.index.tz_convert('Etc/GMT-3')
        return df
    except Exception as e:
        print(f"  [ERROR] {yf_symbol}: {e}")
        return None


def compute_asia_range(df, today):
    """Extract Asia session candles and compute High/Low."""
    mask = (
        (df.index.date == today) &
        (df.index.hour >= ASIA_START_EET) &
        (df.index.hour < ASIA_END_EET)
    )
    asia = df[mask]
    if asia.empty:
        return None, None, 0
    h = float(asia['High'].max())
    l = float(asia['Low'].min())
    return h, l, len(asia)


def check_sweep(current_price, asia_high, asia_low):
    """Check if price has swept Asia High or Low."""
    if current_price is None or asia_high is None:
        return None
    if current_price > asia_high:
        return "HIGH_SWEPT"
    if current_price < asia_low:
        return "LOW_SWEPT"
    return "INSIDE"


def main():
    send_alert = "--alert" in sys.argv

    try:
        import yfinance as yf
        import pandas as pd
    except ImportError:
        print("[ERROR] yfinance not installed")
        sys.exit(1)

    # EET now
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    eet_now = utc_now + timedelta(hours=3)
    today   = eet_now.date()

    # Load selected assets
    sel_file = DATA_DIR / "selected_assets.json"
    selected = []
    if sel_file.exists():
        try:
            sel = json.loads(sel_file.read_text(encoding="utf-8"))
            selected = sel.get("selected", [])
        except Exception:
            pass

    if not selected:
        print("[INFO] No selected assets found.")
        sys.exit(0)

    # Asset → yfinance symbol mapping
    YF_MAP = {
        "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "JPY=X",
        "AUDUSD": "AUDUSD=X", "XAUUSD": "GC=F", "NAS100": "NQ=F",
        "SPX500": "ES=F", "BTC": "BTC-USD", "ETH": "ETH-USD",
        "SOL": "SOL-USD", "XRP": "XRP-USD", "DXY": "DX-Y.NYB",
    }

    results = {}
    print(f"Asia Range Report — {eet_now.strftime('%Y-%m-%d %H:%M')} EET")
    print(f"Asia Session: {ASIA_START_EET:02d}:00–{ASIA_END_EET:02d}:00 EET")
    print()

    for asset in selected:
        sym = asset.get("symbol", "")
        yf_sym = YF_MAP.get(sym)
        if not yf_sym:
            continue

        df = get_5m_bars(yf_sym)
        if df is None:
            results[sym] = {"error": "no data"}
            continue

        asia_h, asia_l, bars = compute_asia_range(df, today)
        current = float(df['Close'].iloc[-1]) if not df.empty else None

        sweep = check_sweep(current, asia_h, asia_l)
        asia_range = round(asia_h - asia_l, 5) if asia_h and asia_l else None

        # TJR setup: not yet swept = setup still valid
        setup_valid = sweep == "INSIDE" and bars >= 10

        result = {
            "symbol":      sym,
            "asia_high":   round(asia_h, 5) if asia_h else None,
            "asia_low":    round(asia_l, 5) if asia_l else None,
            "asia_range":  asia_range,
            "bars":        bars,
            "current":     round(current, 5) if current else None,
            "sweep":       sweep,
            "setup_valid": setup_valid,
            "timestamp":   eet_now.strftime("%Y-%m-%d %H:%M"),
        }
        results[sym] = result

        sweep_icon = {"HIGH_SWEPT": "⬆️ HIGH swept", "LOW_SWEPT": "⬇️ LOW swept", "INSIDE": "⏳ Inside range"}.get(sweep, "?")
        setup_icon = "✅ Setup valid" if setup_valid else "❌ Setup gone"
        print(f"  {sym}: H={asia_h}  L={asia_l}  Range={asia_range}  [{sweep_icon}]  [{setup_icon}]")

    # Save
    OUTPUT_FILE.write_text(json.dumps({
        "date":    today.isoformat(),
        "time":    eet_now.strftime("%H:%M"),
        "assets":  results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved to {OUTPUT_FILE}")

    # Telegram alert if --alert and setups exist
    if send_alert:
        valid_setups = [r for r in results.values() if r.get("setup_valid")]
        if valid_setups:
            lines = []
            for r in valid_setups:
                lines.append(
                    f"• <b>{r['symbol']}</b>: H={r['asia_high']} L={r['asia_low']} "
                    f"(Range {r['asia_range']}) — TJR setup active"
                )
            msg = (
                f"🌏 <b>Asia Range — {eet_now.strftime('%H:%M')} EET</b>\n\n"
                + "\n".join(lines)
                + "\n\n<i>Αναμονή sweep για TJR entry</i>"
            )
            from telegram_sender import send_message
            send_message(msg)
            print(f"[OK] Alert sent for {len(valid_setups)} setup(s)")
        else:
            print("[INFO] No valid TJR setups — no alert sent")


if __name__ == "__main__":
    main()
