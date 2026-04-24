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
import time
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except Exception:
    pass

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
    "EURUSD": {"yf": "EURUSD=X",  "yahoo_id": "EURUSD=X",  "fmt": ".4f",  "range": (0.90, 1.30),    "td": "EUR/USD"},
    "GBPUSD": {"yf": "GBPUSD=X",  "yahoo_id": "GBPUSD=X",  "fmt": ".4f",  "range": (1.15, 1.45),    "td": "GBP/USD"},
    "USDJPY": {"yf": "JPY=X",     "yahoo_id": "JPY=X",     "fmt": ".2f",  "range": (120, 170),      "td": "USD/JPY"},
    "AUDUSD": {"yf": "AUDUSD=X",  "yahoo_id": "AUDUSD=X",  "fmt": ".4f",  "range": (0.55, 0.80),    "td": "AUD/USD"},
    "XAUUSD": {"yf": "GC=F",      "yahoo_id": "GC=F",      "fmt": ",.2f", "range": (1800, 6000),    "td": "XAU/USD"},
    "NAS100": {"yf": "NQ=F",      "yahoo_id": "NQ=F",      "fmt": ",.2f", "range": (15000, 30000),  "td": None},
    "SPX500": {"yf": "ES=F",      "yahoo_id": "ES=F",      "fmt": ",.2f", "range": (4000, 7000),    "td": None},
    "BTC":    {"yf": "BTC-USD",   "yahoo_id": "BTC-USD",   "fmt": ",.0f", "range": (30000, 200000), "td": "BTC/USD"},
    "ETH":    {"yf": "ETH-USD",   "yahoo_id": "ETH-USD",   "fmt": ",.2f", "range": (1000, 8000),    "td": "ETH/USD"},
    "SOL":    {"yf": "SOL-USD",   "yahoo_id": "SOL-USD",   "fmt": ",.2f", "range": (30, 400),       "td": "SOL/USD"},
    "XRP":    {"yf": "XRP-USD",   "yahoo_id": "XRP-USD",   "fmt": ".4f",  "range": (0.30, 5.00),    "td": "XRP/USD"},
    "DXY":    {"yf": "DX-Y.NYB",  "yahoo_id": "DX-Y.NYB",  "fmt": ".2f",  "range": (90, 120),       "td": None},
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


def get_prices_twelvedata_batch():
    """Batch fetch real-time prices for all supported assets from Twelve Data API.
    Requires TWELVEDATA_API_KEY in .env. Free tier: 800 calls/day, 8/min.
    Returns dict: {asset_name: float_price} for assets with td mapping.
    """
    td_key = os.environ.get('TWELVEDATA_API_KEY', '')
    if not td_key:
        return {}

    td_symbols = {name: cfg["td"] for name, cfg in ASSETS.items() if cfg.get("td")}
    symbols_str = ",".join(td_symbols.values())
    url = f"https://api.twelvedata.com/price?symbol={symbols_str}&apikey={td_key}"

    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode())

        results = {}
        for asset_name, td_sym in td_symbols.items():
            entry = data.get(td_sym, {})
            if isinstance(entry, dict) and "price" in entry:
                try:
                    results[asset_name] = float(entry["price"])
                except (ValueError, TypeError):
                    pass

        if results:
            print(f"[twelvedata] OK — {len(results)}/{len(td_symbols)} assets fetched", file=sys.stderr)
        return results

    except Exception as e:
        log_error("twelvedata-batch", f"{type(e).__name__}: {e}")
        return {}


def check_data_staleness():
    """Check if previous price data is older than 45 minutes.
    Returns (is_stale: bool, age_minutes: float).
    """
    outfile = OUTPUT_DIR / "live_prices.json"
    if not outfile.exists():
        return False, 0.0
    try:
        with open(outfile, 'r', encoding='utf-8') as f:
            prev = json.load(f)
        prev_time = datetime.strptime(prev["timestamp"], "%Y-%m-%d %H:%M:%S")
        age_min = (datetime.now() - prev_time).total_seconds() / 60
        return age_min > 45, round(age_min, 1)
    except Exception:
        return False, 0.0


def get_live_price(asset_name, config, td_price=None):
    """Get price using priority: Twelve Data (real-time) > yahoo-web > yfinance.
    td_price: pre-fetched price from get_prices_twelvedata_batch() or None.
    Uses exponential backoff on retries (1s, 2s, 4s).
    """
    symbol = config["yf"]
    lo, hi = config["range"]

    # --- Source 1: Yahoo Finance web (near real-time, no key) ---
    price_yw, src_yw = get_price_yahoo_web(symbol)
    if price_yw is None:
        for backoff in [1, 2, 4]:
            time.sleep(backoff)
            price_yw, src_yw = get_price_yahoo_web(symbol)
            if price_yw is not None:
                break

    # --- Source 2: Twelve Data (real-time, API key required) ---
    price_td = td_price
    src_td = "twelvedata" if td_price is not None else "twelvedata-n/a"

    # --- Sanity checks ---
    if price_yw and not (lo <= price_yw <= hi):
        price_yw = None
        src_yw = "yahoo-web-sanity-fail"
    if price_td and not (lo <= price_td <= hi):
        price_td = None
        src_td = "twelvedata-sanity-fail"

    # --- Best real-time price: prefer TD if available, else yahoo-web ---
    best_rt = price_td if price_td else price_yw
    best_rt_src = src_td if price_td else (src_yw if price_yw else "none")

    # --- Source 3: yfinance (delayed fallback, only if real-time sources failed) ---
    price_yf, src_yf = None, "yfinance-skipped"
    if best_rt is None:
        price_yf, src_yf = get_price_yfinance(symbol)
        if price_yf is None:
            for backoff in [1, 2, 4]:
                time.sleep(backoff)
                price_yf, src_yf = get_price_yfinance(symbol)
                if price_yf is not None:
                    break
        if price_yf and not (lo <= price_yf <= hi):
            price_yf = None
            src_yf = "yfinance-sanity-fail"

    final_price = best_rt if best_rt else price_yf

    # --- Build reference comparison (for diff_pct / agreed) ---
    ref_prices = [p for p in [price_yw, price_td, price_yf] if p]
    if len(ref_prices) >= 2:
        diff = max(ref_prices) - min(ref_prices)
        pct_diff = (diff / min(ref_prices)) * 100
        agreed = pct_diff < 1.0
    else:
        pct_diff = 0.0
        agreed = len(ref_prices) == 1

    status = "OK" if (agreed and final_price) else ("SINGLE_SOURCE" if final_price else "FAILED")

    return {
        "asset": asset_name,
        "price": final_price,
        "realtime_source": best_rt_src,
        "source1": {"price": price_yw,  "source": src_yw},
        "source2": {"price": price_td,  "source": src_td},
        "source3": {"price": price_yf,  "source": src_yf},
        "agreed": agreed,
        "diff_pct": round(pct_diff, 3),
        "status": status,
    }


def check_all(asset_filter=None, output_json=False):
    """Check prices for all assets."""
    # Log environment info on every run (helps debug scheduled vs manual)
    log_error("ENV", f"python={sys.executable} | cwd={os.getcwd()} | PATH_first={os.environ.get('PATH','?')[:200]}")

    # --- #4: Staleness check — alert if previous data > 45 min old ---
    is_stale, age_min = check_data_staleness()
    if is_stale:
        stale_msg = (
            f"⚠️ <b>GOLD TACTIC — Δεδομένα Ληξιπρόθεσμα</b>\n"
            f"Τελευταία ενημέρωση τιμών: <b>{age_min:.0f} λεπτά</b> πριν\n"
            f"(Κανονικό διάστημα: &lt;45 λεπτά)"
        )
        print(f"⚠️  STALENESS WARNING: Last price update was {age_min:.0f}min ago!")
        log_error("STALENESS", f"Data is {age_min}min old (threshold: 45min)")
        try:
            import sys as _sys
            _sys.path.insert(0, str(Path(__file__).parent))
            from telegram_sender import send_message
            send_message(stale_msg)
        except Exception as e:
            log_error("staleness-telegram", str(e))

    assets_to_check = {k: v for k, v in ASSETS.items()
                       if asset_filter is None or k in asset_filter}

    # --- #1: Fetch Twelve Data batch (one API call for all assets) ---
    td_prices = get_prices_twelvedata_batch()
    if td_prices and not output_json:
        print(f"  [Twelve Data] Real-time prices: {', '.join(td_prices.keys())}")

    results = {}
    print(f"GOLD TACTIC — Live Price Checker")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    for name, config in assets_to_check.items():
        result = get_live_price(name, config, td_price=td_prices.get(name))
        results[name] = result
        fmt = config["fmt"]

        if result["price"]:
            status_emoji = "✅" if result["status"] == "OK" else "⚠️"
            p_yw  = f"{result['source1']['price']:{fmt}}" if result['source1']['price'] else "N/A"
            p_td  = f"{result['source2']['price']:{fmt}}" if result['source2']['price'] else "—"
            src   = result.get("realtime_source", "?")
            print(f"  {status_emoji} {name}: {result['price']:{fmt}}  [{src}]")
            print(f"     yahoo-web: {p_yw} | twelve-data: {p_td} | diff: {result['diff_pct']}%")
        else:
            print(f"  ❌ {name}: FAILED")

    # Save
    output = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "twelvedata_active": bool(td_prices),
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

    # --assets XAUUSD,BTC,SOL format (comma-separated)
    for a in sys.argv[1:]:
        if a.startswith("--assets="):
            asset_filter = [x.strip().upper() for x in a.split("=", 1)[1].split(",")]
        elif a.startswith("--assets") and sys.argv.index(a) + 1 < len(sys.argv):
            next_arg = sys.argv[sys.argv.index(a) + 1]
            if not next_arg.startswith("--"):
                asset_filter = [x.strip().upper() for x in next_arg.split(",")]

    # Positional args (legacy support)
    if asset_filter is None:
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        if args:
            asset_filter = [a.upper() for a in args]

    check_all(asset_filter, output_json)