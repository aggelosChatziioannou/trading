#!/usr/bin/env python3
"""
GOLD TACTIC — Live Price Checker (Dual Source)
Gets real-time prices from 2 FREE sources (no API key needed):
  1. yfinance (primary — may have 15min delay)
  2. Yahoo Finance web scrape (backup — near real-time)

Usage:
  python price_checker.py                  # All core assets
  python price_checker.py GBPUSD           # Single asset
  python price_checker.py --json           # Output as JSON
"""

import json
import sys
import os
import urllib.request
import re
import traceback
import logging
from datetime import datetime
from pathlib import Path

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Error log for debugging scheduled runs
ERROR_LOG = OUTPUT_DIR / "price_checker_errors.log"
def log_error(source, error):
    """Log errors to file for debugging scheduled runs."""
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {source}: {error}\n")
    except:
        pass

ASSETS = {
    "EURUSD": {"yf": "EURUSD=X",  "yahoo_id": "EURUSD=X",  "fmt": ".4f", "range": (1.05, 1.25)},
    "GBPUSD": {"yf": "GBPUSD=X",  "yahoo_id": "GBPUSD=X",  "fmt": ".4f", "range": (1.20, 1.40)},
    "NAS100": {"yf": "^NDX",       "yahoo_id": "^NDX",        "fmt": ",.2f", "range": (18000, 30000)},
    "SOL":    {"yf": "SOL-USD",    "yahoo_id": "SOL-USD",    "fmt": ",.2f", "range": (50, 200)},
    "BTC":    {"yf": "BTC-USD",    "yahoo_id": "BTC-USD",    "fmt": ",.0f", "range": (50000, 150000)},
}


def get_price_yfinance(symbol):
    """Get price via yfinance download (may be delayed). Tries multiple periods."""
    try:
        import yfinance as yf
        import pandas as pd
        # Try 1d first (most recent), fallback to 5d if empty
        for period in ["1d", "5d"]:
            try:
                df = yf.download(symbol, period=period, interval="5m", progress=False, timeout=15)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                if not df.empty:
                    return float(df['Close'].iloc[-1]), "yfinance"
            except Exception as e:
                log_error(f"yfinance-{period}", f"{symbol}: {type(e).__name__}: {e}")
                continue
        # Last resort: daily close
        df = yf.download(symbol, period="2d", interval="1d", progress=False, timeout=15)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if not df.empty:
            return float(df['Close'].iloc[-1]), "yfinance-daily"
    except Exception as e:
        log_error("yfinance-import", f"{symbol}: {type(e).__name__}: {e}\n{traceback.format_exc()}")
    return None, "yfinance-failed"


def get_price_yahoo_web(symbol):
    """Get price via Yahoo Finance web (near real-time, no API key)."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1m"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            result = data.get('chart', {}).get('result', [])
            if result:
                meta = result[0].get('meta', {})
                price = meta.get('regularMarketPrice', None)
                if price:
                    return float(price), "yahoo-web"
    except Exception as e:
        log_error("yahoo-web", f"{symbol}: {type(e).__name__}: {e}")
    return None, "yahoo-web-failed"


def get_live_price(asset_name, config):
    """Get price from both sources, compare, return best. Retry once on failure."""
    import time
    symbol = config["yf"]
    lo, hi = config["range"]

    price1, src1 = get_price_yfinance(symbol)
    price2, src2 = get_price_yahoo_web(symbol)

    # Retry failed sources once with a small delay
    if price1 is None:
        time.sleep(2)
        log_error("retry", f"{asset_name}: retrying yfinance after initial failure ({src1})")
        price1, src1 = get_price_yfinance(symbol)
    if price2 is None:
        time.sleep(2)
        log_error("retry", f"{asset_name}: retrying yahoo-web after initial failure ({src2})")
        price2, src2 = get_price_yahoo_web(symbol)

    # Sanity check
    if price1 and not (lo <= price1 <= hi):
        price1 = None
        src1 = "yfinance-sanity-fail"
    if price2 and not (lo <= price2 <= hi):
        price2 = None
        src2 = "yahoo-web-sanity-fail"

    # Determine best price
    if price1 and price2:
        diff = abs(price1 - price2)
        pct_diff = (diff / price2) * 100 if price2 else 0
        agreed = pct_diff < 1.0
        best_price = price2  # Yahoo web is usually more real-time
        return {
            "asset": asset_name,
            "price": best_price,
            "source1": {"price": price1, "source": src1},
            "source2": {"price": price2, "source": src2},
            "agreed": agreed,
            "diff_pct": round(pct_diff, 3),
            "status": "OK" if agreed else "MISMATCH",
        }
    elif price2:
        return {
            "asset": asset_name,
            "price": price2,
            "source1": {"price": None, "source": src1},
            "source2": {"price": price2, "source": src2},
            "agreed": False,
            "diff_pct": 0,
            "status": "SINGLE_SOURCE",
        }
    elif price1:
        return {
            "asset": asset_name,
            "price": price1,
            "source1": {"price": price1, "source": src1},
            "source2": {"price": None, "source": src2},
            "agreed": False,
            "diff_pct": 0,
            "status": "SINGLE_SOURCE",
        }
    else:
        return {
            "asset": asset_name,
            "price": None,
            "source1": {"price": None, "source": src1},
            "source2": {"price": None, "source": src2},
            "agreed": False,
            "diff_pct": 0,
            "status": "FAILED",
        }


def check_all(asset_filter=None, output_json=False):
    """Check prices for all assets."""
    # Log environment info on every run (helps debug scheduled vs manual)
    log_error("ENV", f"python={sys.executable} | cwd={os.getcwd()} | PATH_first={os.environ.get('PATH','?')[:200]}")

    assets_to_check = {k: v for k, v in ASSETS.items()
                       if asset_filter is None or k in asset_filter}

    results = {}
    print(f"GOLD TACTIC — Live Price Checker")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    for name, config in assets_to_check.items():
        result = get_live_price(name, config)
        results[name] = result
        fmt = config["fmt"]

        if result["price"]:
            status_emoji = "✅" if result["status"] == "OK" else "⚠️"
            p1 = f"{result['source1']['price']:{fmt}}" if result['source1']['price'] else "N/A"
            p2 = f"{result['source2']['price']:{fmt}}" if result['source2']['price'] else "N/A"
            print(f"  {status_emoji} {name}: {result['price']:{fmt}}")
            print(f"     yfinance: {p1} | yahoo-web: {p2} | diff: {result['diff_pct']}%")
        else:
            print(f"  ❌ {name}: FAILED")

    # Save
    output = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "prices": results,
    }
    outfile = OUTPUT_DIR / "live_prices.json"
    outfile.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')

    if output_json:
        print(json.dumps(output, indent=2))

    return results


if __name__ == "__main__":
    asset_filter = None
    output_json = "--json" in sys.argv

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        asset_filter = [a.upper() for a in args]

    check_all(asset_filter, output_json)