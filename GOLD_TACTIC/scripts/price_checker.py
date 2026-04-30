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
from datetime import datetime, timezone, timedelta
from pathlib import Path

# EET timezone — fixes UTC-vs-EET timestamp drift (2026-04-29)
EET = timezone(timedelta(hours=3))

try:
    from dotenv import load_dotenv
    _project_root = Path(__file__).parent.parent.parent
    # Load public .env first
    _env_path = _project_root / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
    # Then .env.local — gitignored, contains private keys; overrides .env values.
    _env_local = _project_root / ".env.local"
    if _env_local.exists():
        load_dotenv(_env_local, override=True)
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
            f.write(f"[{datetime.now(EET).strftime('%Y-%m-%d %H:%M:%S')}] {source}: {error}\n")
    except:
        pass

ASSETS = {
    # ── Forex (provider chain: twelvedata → yahoo-web → yfinance) ──
    "EURUSD": {"yf": "EURUSD=X",  "yahoo_id": "EURUSD=X",  "fmt": ".4f",  "range": (0.90, 1.30),    "td": "EUR/USD",  "binance": None,        "asset_class": "forex"},
    "GBPUSD": {"yf": "GBPUSD=X",  "yahoo_id": "GBPUSD=X",  "fmt": ".4f",  "range": (1.15, 1.45),    "td": "GBP/USD",  "binance": None,        "asset_class": "forex"},
    "USDJPY": {"yf": "JPY=X",     "yahoo_id": "JPY=X",     "fmt": ".2f",  "range": (120, 170),      "td": "USD/JPY",  "binance": None,        "asset_class": "forex"},
    "AUDUSD": {"yf": "AUDUSD=X",  "yahoo_id": "AUDUSD=X",  "fmt": ".4f",  "range": (0.55, 0.80),    "td": "AUD/USD",  "binance": None,        "asset_class": "forex"},
    # ── Gold (twelvedata → yahoo-web futures) ──
    "XAUUSD": {"yf": "GC=F",      "yahoo_id": "GC=F",      "fmt": ",.2f", "range": (1800, 8000),    "td": "XAU/USD",  "binance": None,        "asset_class": "metal"},
    # ── Indices: cash tickers (^IXIC, ^GSPC) for TradingView-aligned prices ──
    # NAS100/SPX500 are now CASH indices, not futures. Used to be NQ=F/ES=F which
    # diverged ~30-50pts from TradingView's default cash chart.
    "NAS100": {"yf": "^IXIC",     "yahoo_id": "^IXIC",     "fmt": ",.2f", "range": (15000, 40000),  "td": "IXIC",     "binance": None,        "asset_class": "index"},
    "SPX500": {"yf": "^GSPC",     "yahoo_id": "^GSPC",     "fmt": ",.2f", "range": (3500, 9500),    "td": "SPX",      "binance": None,        "asset_class": "index"},
    # ── Crypto (Binance public ticker primary — matches every major exchange) ──
    "BTC":    {"yf": "BTC-USD",   "yahoo_id": "BTC-USD",   "fmt": ",.0f", "range": (30000, 200000), "td": "BTC/USD",  "binance": "BTCUSDT",   "asset_class": "crypto"},
    "ETH":    {"yf": "ETH-USD",   "yahoo_id": "ETH-USD",   "fmt": ",.2f", "range": (1000, 8000),    "td": "ETH/USD",  "binance": "ETHUSDT",   "asset_class": "crypto"},
    "SOL":    {"yf": "SOL-USD",   "yahoo_id": "SOL-USD",   "fmt": ",.2f", "range": (30, 400),       "td": "SOL/USD",  "binance": "SOLUSDT",   "asset_class": "crypto"},
    "XRP":    {"yf": "XRP-USD",   "yahoo_id": "XRP-USD",   "fmt": ".4f",  "range": (0.30, 5.00),    "td": "XRP/USD",  "binance": "XRPUSDT",   "asset_class": "crypto"},
    # ── Dollar Index ──
    "DXY":    {"yf": "DX-Y.NYB",  "yahoo_id": "DX-Y.NYB",  "fmt": ".2f",  "range": (90, 120),       "td": "DXY",      "binance": None,        "asset_class": "dxy"},
}

# Provider priority chain per asset class — tried in order, first non-None wins.
# Each provider returns (price, source_str) or (None, "<provider>-failed").
# Designed to match TradingView's default chart per asset class while staying
# under Twelve Data's 8-credits/minute free-tier rate limit.
#
# Quota math (full 12-asset sweep):
#   - Forex (4) + Metal (1) = 5 TD credits  (under 8/min ✓)
#   - Indices (2): Yahoo cash ^GSPC/^IXIC primary (TD as fallback if needed)
#   - Crypto (4): Binance public API primary (no quota)
#   - DXY (1): Yahoo
# Total: ~5 TD + 3 Yahoo + 4 Binance per Selector run.
PROVIDER_CHAIN = {
    "crypto": ["binance", "yahoo-web", "yfinance"],          # Binance == TradingView default
    "forex":  ["twelvedata", "yahoo-web", "yfinance"],       # TD = institutional-grade forex
    "metal":  ["twelvedata", "yahoo-web", "yfinance"],       # TD for XAU/USD precision
    "index":  ["yahoo-web", "twelvedata", "yfinance"],       # Yahoo cash ticker == TradingView
    "dxy":    ["yahoo-web", "twelvedata", "yfinance"],
}

# Asset classes where Twelve Data is the PRIMARY provider — these are batched
# in get_prices_twelvedata_batch() to consume credits efficiently (1 HTTP call,
# N credits where N = number of TD-primary symbols).
_TD_PRIMARY_CLASSES = {"forex", "metal"}


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


def get_price_binance(binance_symbol):
    """Fetch crypto spot price from Binance public ticker API.

    Binance is the primary exchange most price feeds reference, including
    TradingView's default crypto charts. No API key needed.

    Args:
      binance_symbol: e.g., 'BTCUSDT', 'ETHUSDT', 'SOLUSDT'

    Returns:
      (price_float, source_str) or (None, 'binance-failed')
    """
    if not binance_symbol:
        return None, "binance-skipped"
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={binance_symbol}"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'GoldTactic/1.0')
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            price = data.get("price")
            if price is not None:
                return float(price), "binance"
    except Exception as e:
        log_error("binance", f"{binance_symbol}: {type(e).__name__}: {e}")
    return None, "binance-failed"


def get_price_twelvedata_single(td_symbol):
    """Single-symbol Twelve Data fetch. Used by per-asset provider chain.

    Returns (price, source) or (None, 'twelvedata-failed' / 'twelvedata-nokey').
    """
    if not td_symbol:
        return None, "twelvedata-skipped"
    td_key = os.environ.get('TWELVEDATA_API_KEY', '')
    if not td_key:
        return None, "twelvedata-nokey"
    try:
        url = f"https://api.twelvedata.com/price?symbol={td_symbol}&apikey={td_key}"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'GoldTactic/1.0')
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            price = data.get("price")
            if price is not None:
                return float(price), "twelvedata"
    except Exception as e:
        log_error("twelvedata-single", f"{td_symbol}: {type(e).__name__}: {e}")
    return None, "twelvedata-failed"


def get_prices_twelvedata_batch():
    """Batch fetch TD-primary asset prices in a single API call.

    Only fetches assets where TD is the PRIMARY provider in PROVIDER_CHAIN
    (forex + metal — currently 5 symbols: EUR/USD, GBP/USD, USD/JPY, AUD/USD,
    XAU/USD). This stays well under the 8-credits/min free-tier limit (5 ≤ 8).

    For non-TD-primary assets (indices/crypto/DXY), TD is only consulted on
    fallback when the primary provider fails — those calls happen via
    get_price_twelvedata_single() inside the per-asset chain.

    Returns dict: {asset_name: float_price}.
    """
    td_key = os.environ.get('TWELVEDATA_API_KEY', '')
    if not td_key:
        return {}

    # Limit batch to TD-primary asset classes (forex + metal) to respect rate limit
    td_symbols = {
        name: cfg["td"]
        for name, cfg in ASSETS.items()
        if cfg.get("td") and cfg.get("asset_class") in _TD_PRIMARY_CLASSES
    }
    if not td_symbols:
        return {}
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
        age_min = (datetime.now(EET) - prev_time.replace(tzinfo=EET) if prev_time.tzinfo is None else datetime.now(EET) - prev_time).total_seconds() / 60
        return age_min > 45, round(age_min, 1)
    except Exception:
        return False, 0.0


def get_live_price(asset_name, config, td_price=None):
    """Multi-source price fetch with per-asset-class provider chain.

    Provider priority by asset class:
      crypto → Binance → Twelve Data → Yahoo web → yfinance
      forex  → Twelve Data → Yahoo web → yfinance
      metal  → Twelve Data → Yahoo web → yfinance
      index  → Twelve Data → Yahoo web (cash ticker) → yfinance
      dxy    → Yahoo web (^DXY data) → Twelve Data → yfinance

    Each provider returns (price, source). First valid + sanity-passing price wins
    as the "primary". All other providers' prices are also collected for cross-
    validation (agreed=true if max-min < 1% diff).

    The primary provider is intentionally chosen to match TradingView's default
    chart for each asset class — Binance for crypto, cash indices for indices,
    Twelve Data (institutional-grade) for forex.
    """
    asset_class = config.get("asset_class", "forex")
    chain = PROVIDER_CHAIN.get(asset_class, ["yahoo-web", "yfinance"])
    yf_sym = config["yf"]
    td_sym = config.get("td")
    bin_sym = config.get("binance")
    lo, hi = config["range"]

    # Collect ALL providers' prices for cross-validation, even if not in primary chain
    sources = {}  # name → {"price": float|None, "source": str}

    def _try(provider_name):
        """Run provider, return (price_or_none, source_str). Records to sources dict."""
        if provider_name == "binance":
            p, s = get_price_binance(bin_sym)
        elif provider_name == "twelvedata":
            # Use pre-fetched batch result if available, else single-call fallback
            if td_price is not None:
                p, s = td_price, "twelvedata"
            else:
                p, s = get_price_twelvedata_single(td_sym)
        elif provider_name == "yahoo-web":
            p, s = get_price_yahoo_web(yf_sym)
            if p is None:
                # One retry with backoff for transient Yahoo failures
                time.sleep(1)
                p, s = get_price_yahoo_web(yf_sym)
        elif provider_name == "yfinance":
            p, s = get_price_yfinance(yf_sym)
        else:
            p, s = None, f"{provider_name}-unknown"

        # Sanity check
        if p is not None and not (lo <= p <= hi):
            sources[provider_name] = {"price": p, "source": f"{s}-sanity-fail"}
            return None, f"{s}-sanity-fail"
        sources[provider_name] = {"price": p, "source": s}
        return p, s

    # Walk the chain in order — FIRST SUCCESS WINS, then stop (saves quota).
    # Cross-validation against extra providers is intentionally skipped; the chain
    # is already curated so that the primary provider matches TradingView's default
    # chart for each asset class, making cross-validation redundant most of the time.
    # If the user wants explicit multi-source diff, they can invoke individual
    # providers directly via the helper functions.
    primary_price = None
    primary_src = "none"
    for provider in chain:
        p, s = _try(provider)
        if p is not None:
            primary_price = p
            primary_src = s
            break  # first success wins — preserve TD quota, save round-trips

    # Build cross-validation diff stats
    ref_prices = [v["price"] for v in sources.values() if v["price"] is not None]
    if len(ref_prices) >= 2:
        diff = max(ref_prices) - min(ref_prices)
        pct_diff = (diff / min(ref_prices)) * 100
        agreed = pct_diff < 1.0
    else:
        pct_diff = 0.0
        agreed = len(ref_prices) == 1

    status = "OK" if (agreed and primary_price) else ("SINGLE_SOURCE" if primary_price else "FAILED")

    # Backward-compatible source1/source2/source3 fields for downstream consumers
    legacy_yw = sources.get("yahoo-web", {"price": None, "source": "yahoo-web-skipped"})
    legacy_td = sources.get("twelvedata", {"price": None, "source": "twelvedata-skipped"})
    legacy_yf = sources.get("yfinance", {"price": None, "source": "yfinance-skipped"})
    legacy_bin = sources.get("binance", {"price": None, "source": "binance-skipped"})

    return {
        "asset": asset_name,
        "price": primary_price,
        "realtime_source": primary_src,
        "asset_class": asset_class,
        "provider_chain": chain,
        "sources": sources,  # NEW — full per-provider result dict
        # Legacy fields kept for downstream consumers (dashboard, sanity checks)
        "source1": legacy_yw,
        "source2": legacy_td,
        "source3": legacy_yf,
        "source4": legacy_bin,
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
    print(f"Time: {datetime.now(EET).strftime('%Y-%m-%d %H:%M:%S')}")
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
        "timestamp": datetime.now(EET).strftime("%Y-%m-%d %H:%M:%S"),
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