#!/usr/bin/env python3
"""
Gold Bot Data Downloader
Downloads 6 months of XAUUSD (Dukascopy) and DXY (Twelve Data) 5-min data.
"""
import argparse
import io
import lzma
import struct
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

# ── Constants ─────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent
XAUUSD_CSV = DATA_DIR / "xauusd_5m.csv"
DXY_CSV = DATA_DIR / "dxy_5m.csv"

DUKASCOPY_URL = "https://datafeed.dukascopy.com/datafeed/XAUUSD/{year}/{month:02d}/{day:02d}/{hour:02d}h_ticks.bi5"
TWELVE_DATA_URL = "https://api.twelvedata.com/time_series"
TWELVE_DATA_KEY = "3c433196d4ab4877afe3c944d4cf889c"
# DXY not available on free tier; EUR/USD is inversely correlated with USD (and gold)
# We invert EUR/USD to create a USD proxy for SMT divergence
DXY_SYMBOL = "EUR/USD"

DEFAULT_START = "2025-09-01"
DEFAULT_END = "2026-03-01"

TICK_SIZE = 20  # 5 fields x 4 bytes
TICK_FORMAT = ">IIIff"
XAUUSD_DIVISOR = 1000.0  # 3 decimal places

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "GoldBot/1.0 (backtesting research)"})


# ══════════════════════════════════════════════════════════════════════
#  DUKASCOPY - XAUUSD tick download
# ══════════════════════════════════════════════════════════════════════

def _download_hour(year: int, month: int, day: int, hour: int, retries: int = 3) -> list[dict]:
    """Download and parse one hour of tick data from Dukascopy.

    Returns list of dicts: [{datetime, mid, volume}, ...]
    Note: Dukascopy months are 0-indexed (Jan=0, Feb=1, ...).
    """
    url = DUKASCOPY_URL.format(year=year, month=month - 1, day=day, hour=hour)
    hour_start = datetime(year, month, day, hour)

    for attempt in range(retries):
        try:
            resp = SESSION.get(url, timeout=15)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.content
            if not data or len(data) < 5:
                return []
            break
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
            else:
                return []

    # Decompress LZMA
    try:
        raw = lzma.decompress(data)
    except lzma.LZMAError:
        return []

    if len(raw) < TICK_SIZE:
        return []

    ticks = []
    for offset in range(0, len(raw) - TICK_SIZE + 1, TICK_SIZE):
        ms_offset, ask_raw, bid_raw, ask_vol, bid_vol = struct.unpack_from(
            TICK_FORMAT, raw, offset
        )
        ask = ask_raw / XAUUSD_DIVISOR
        bid = bid_raw / XAUUSD_DIVISOR
        mid = (ask + bid) / 2.0
        vol = ask_vol + bid_vol
        tick_time = hour_start + timedelta(milliseconds=ms_offset)
        ticks.append({"datetime": tick_time, "mid": mid, "volume": vol})

    return ticks


def _resample_ticks_to_5m(ticks: list[dict]) -> pd.DataFrame:
    """Resample tick data to 5-minute OHLCV candles."""
    if not ticks:
        return pd.DataFrame()

    df = pd.DataFrame(ticks)
    df = df.set_index("datetime").sort_index()

    ohlcv = df["mid"].resample("5min").agg(
        open="first", high="max", low="min", close="last"
    )
    ohlcv["volume"] = df["volume"].resample("5min").sum()
    ohlcv = ohlcv.dropna(subset=["open"])
    return ohlcv


def _load_existing_xauusd() -> set[str]:
    """Load existing dates from XAUUSD CSV to enable resume."""
    if not XAUUSD_CSV.exists():
        return set()
    try:
        df = pd.read_csv(XAUUSD_CSV, parse_dates=["datetime"], usecols=["datetime"])
        return set(df["datetime"].dt.strftime("%Y-%m-%d").unique())
    except Exception:
        return set()


def download_xauusd(start_str: str, end_str: str):
    """Download XAUUSD tick data from Dukascopy and resample to 5-min candles."""
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")

    # Resume: load existing dates
    existing_dates = _load_existing_xauusd()
    if existing_dates:
        print(f"  Resume: {len(existing_dates)} dates already downloaded")

    # Load existing data if resuming
    existing_df = None
    if XAUUSD_CSV.exists() and existing_dates:
        try:
            existing_df = pd.read_csv(XAUUSD_CSV, parse_dates=["datetime"], index_col="datetime")
        except Exception:
            existing_df = None

    # Count total hours to download
    total_days = (end - start).days
    trading_days = []
    d = start
    while d < end:
        if d.weekday() < 5:  # Mon-Fri
            date_str = d.strftime("%Y-%m-%d")
            if date_str not in existing_dates:
                trading_days.append(d)
        d += timedelta(days=1)

    total_hours = len(trading_days) * 24
    print(f"  Days to download: {len(trading_days)} ({total_hours} hours)")
    if total_hours == 0:
        print("  Nothing new to download!")
        return

    # Estimate time
    est_seconds = total_hours * 0.08  # ~0.05s sleep + download time
    est_minutes = est_seconds / 60
    print(f"  Estimated time: {est_minutes:.0f} minutes")

    all_ticks = []
    hours_done = 0
    save_counter = 0
    t_start = time.time()

    for day_idx, day in enumerate(trading_days):
        day_ticks = []
        for hour in range(24):
            ticks = _download_hour(day.year, day.month, day.day, hour)
            day_ticks.extend(ticks)
            hours_done += 1
            time.sleep(0.05)

        all_ticks.extend(day_ticks)
        save_counter += 1

        # Progress every 10 days
        if (day_idx + 1) % 10 == 0 or day_idx == len(trading_days) - 1:
            elapsed = time.time() - t_start
            rate = hours_done / elapsed if elapsed > 0 else 0
            remaining = (total_hours - hours_done) / rate if rate > 0 else 0
            print(f"    [{day_idx+1}/{len(trading_days)}] {day.strftime('%Y-%m-%d')} "
                  f"| {len(all_ticks):,} ticks | "
                  f"ETA: {remaining/60:.1f}min")

        # Save intermediate every 30 days
        if save_counter >= 30:
            _save_xauusd_intermediate(all_ticks, existing_df)
            save_counter = 0

    # Final resample and save
    print("  Resampling ticks to 5-min candles...")
    new_df = _resample_ticks_to_5m(all_ticks)

    if existing_df is not None and not new_df.empty:
        combined = pd.concat([existing_df, new_df])
        combined = combined[~combined.index.duplicated(keep="last")]
        combined = combined.sort_index()
    elif not new_df.empty:
        combined = new_df
    else:
        combined = existing_df if existing_df is not None else pd.DataFrame()

    if isinstance(combined, pd.DataFrame) and not combined.empty:
        combined.index.name = "datetime"
        combined.to_csv(XAUUSD_CSV)
        print(f"  Saved: {XAUUSD_CSV} ({len(combined):,} candles)")
    else:
        print("  WARNING: No data to save!")


def _save_xauusd_intermediate(ticks: list[dict], existing_df):
    """Save intermediate results to avoid data loss."""
    df = _resample_ticks_to_5m(ticks)
    if df.empty:
        return
    if existing_df is not None:
        df = pd.concat([existing_df, df])
        df = df[~df.index.duplicated(keep="last")]
        df = df.sort_index()
    df.index.name = "datetime"
    df.to_csv(XAUUSD_CSV)


# ══════════════════════════════════════════════════════════════════════
#  TWELVE DATA - DXY download
# ══════════════════════════════════════════════════════════════════════

def _load_existing_dxy() -> datetime | None:
    """Load earliest date from existing DXY CSV for resume."""
    if not DXY_CSV.exists():
        return None
    try:
        df = pd.read_csv(DXY_CSV, parse_dates=["datetime"], usecols=["datetime"])
        if df.empty:
            return None
        return df["datetime"].min().to_pydatetime()
    except Exception:
        return None


def download_dxy(start_str: str, end_str: str):
    """Download DXY 5-min data from Twelve Data API."""
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")

    # Resume check
    existing_df = None
    if DXY_CSV.exists():
        try:
            existing_df = pd.read_csv(DXY_CSV, parse_dates=["datetime"], index_col="datetime")
            earliest = existing_df.index.min()
            if earliest <= pd.Timestamp(start):
                print(f"  DXY data already covers from {earliest} - skipping download")
                return
            else:
                end = earliest.to_pydatetime()
                print(f"  Resume: downloading up to {end.strftime('%Y-%m-%d')}")
        except Exception:
            existing_df = None

    all_frames = []
    end_date = end.strftime("%Y-%m-%d %H:%M:%S")
    request_num = 0

    while True:
        request_num += 1
        params = {
            "symbol": DXY_SYMBOL,
            "interval": "5min",
            "apikey": TWELVE_DATA_KEY,
            "outputsize": 5000,
            "format": "JSON",
            "order": "ASC",
            "end_date": end_date,
        }

        print(f"    Request #{request_num}: end_date={end_date[:10]}...")

        for attempt in range(3):
            try:
                resp = SESSION.get(TWELVE_DATA_URL, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as e:
                if attempt < 2:
                    print(f"      Retry {attempt+1}: {e}")
                    time.sleep(5)
                else:
                    print(f"      FAILED after 3 retries: {e}")
                    data = None

        if data is None:
            break

        # Check for API errors
        if data.get("status") == "error":
            print(f"      API error: {data.get('message', 'unknown')}")
            break

        values = data.get("values", [])
        if not values:
            print("      No more data")
            break

        rows = []
        for v in values:
            rows.append({
                "datetime": v["datetime"],
                "open": float(v["open"]),
                "high": float(v["high"]),
                "low": float(v["low"]),
                "close": float(v["close"]),
                "volume": float(v.get("volume", 0)),
            })

        batch_df = pd.DataFrame(rows)
        batch_df["datetime"] = pd.to_datetime(batch_df["datetime"])
        all_frames.append(batch_df)

        earliest = batch_df["datetime"].min()
        print(f"      Got {len(values)} candles, earliest: {earliest}")

        if len(values) < 5000:
            break
        if earliest <= pd.Timestamp(start):
            break

        # Set end_date for next request to just before the earliest we got
        end_date = (earliest - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")

        # Rate limit
        print("      Sleeping 10s (rate limit)...")
        time.sleep(10)

    if not all_frames:
        print("  WARNING: No DXY data downloaded!")
        return

    new_df = pd.concat(all_frames, ignore_index=True)
    new_df = new_df.drop_duplicates(subset=["datetime"])
    new_df = new_df.set_index("datetime").sort_index()

    # Filter to date range
    new_df = new_df[(new_df.index >= pd.Timestamp(start)) & (new_df.index < pd.Timestamp(end_str))]

    # Merge with existing
    if existing_df is not None and not new_df.empty:
        combined = pd.concat([new_df, existing_df])
        combined = combined[~combined.index.duplicated(keep="last")]
        combined = combined.sort_index()
    elif not new_df.empty:
        combined = new_df
    else:
        combined = existing_df if existing_df is not None else pd.DataFrame()

    if isinstance(combined, pd.DataFrame) and not combined.empty:
        combined.index.name = "datetime"
        combined.to_csv(DXY_CSV)
        print(f"  Saved: {DXY_CSV} ({len(combined):,} candles)")
    else:
        print("  WARNING: No data to save!")


# ══════════════════════════════════════════════════════════════════════
#  VALIDATION
# ══════════════════════════════════════════════════════════════════════

def validate_csv(filepath: Path, name: str):
    """Validate a downloaded CSV and print summary."""
    if not filepath.exists():
        print(f"  {name}: FILE NOT FOUND")
        return

    df = pd.read_csv(filepath, parse_dates=["datetime"], index_col="datetime")
    if df.empty:
        print(f"  {name}: EMPTY FILE")
        return

    print(f"\n{'='*60}")
    print(f"  {name}: {len(df):,} candles")
    print(f"  Range: {df.index[0]} to {df.index[-1]}")

    # Check for weekend data
    weekend = df[df.index.dayofweek >= 5]
    if len(weekend) > 0:
        print(f"  WARNING: {len(weekend)} weekend candles found - removing...")
        df = df[df.index.dayofweek < 5]
        df.to_csv(filepath)
        print(f"  Cleaned: {len(df):,} candles")

    # Find gaps > 1 hour (excluding Fri 5PM to Sun)
    time_diffs = df.index.to_series().diff()
    gaps = time_diffs[time_diffs > pd.Timedelta(hours=1)]
    # Filter out weekend gaps (Friday to Monday)
    real_gaps = []
    for ts, gap in gaps.items():
        prev_ts = ts - gap
        # Skip Friday PM to Monday AM
        if prev_ts.dayofweek == 4 and ts.dayofweek == 0:
            continue
        if gap > pd.Timedelta(hours=4):
            real_gaps.append((prev_ts, ts, gap))

    print(f"  Gaps > 4h (excluding weekends): {len(real_gaps)}")
    for g_start, g_end, g_len in real_gaps[:5]:
        print(f"    {g_start} -> {g_end} ({g_len})")

    # Sample data
    print(f"\n  First 3 rows:")
    print(df.head(3).to_string(max_cols=6))
    print(f"\n  Last 3 rows:")
    print(df.tail(3).to_string(max_cols=6))
    print(f"{'='*60}")


# ══════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Gold Bot Data Downloader")
    parser.add_argument("--start", default=DEFAULT_START, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=DEFAULT_END, help="End date (YYYY-MM-DD)")
    parser.add_argument("--gold-only", action="store_true", help="Download only XAUUSD")
    parser.add_argument("--dxy-only", action="store_true", help="Download only DXY")
    args = parser.parse_args()

    download_gold = not args.dxy_only
    download_dxy_flag = not args.gold_only

    print("=" * 60)
    print("  GOLD BOT DATA DOWNLOADER")
    print(f"  Period: {args.start} to {args.end}")
    print("=" * 60)

    t_start = time.time()

    if download_gold:
        print(f"\n[1/2] Downloading XAUUSD from Dukascopy...")
        download_xauusd(args.start, args.end)

    if download_dxy_flag:
        step = "2/2" if download_gold else "1/1"
        print(f"\n[{step}] Downloading DXY from Twelve Data...")
        download_dxy(args.start, args.end)

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"  DOWNLOAD COMPLETE ({elapsed:.0f}s)")
    print(f"{'='*60}")

    # Validate
    if download_gold:
        validate_csv(XAUUSD_CSV, "XAUUSD")
    if download_dxy_flag:
        validate_csv(DXY_CSV, "DXY")

    # Final summary
    print(f"\n=== DOWNLOAD COMPLETE ===")
    if download_gold and XAUUSD_CSV.exists():
        df = pd.read_csv(XAUUSD_CSV)
        print(f"XAUUSD: {len(df):,} candles | {args.start} to {args.end}")
    if download_dxy_flag and DXY_CSV.exists():
        df = pd.read_csv(DXY_CSV)
        print(f"DXY:    {len(df):,} candles | {args.start} to {args.end}")
    print(f"Files saved: {XAUUSD_CSV}, {DXY_CSV}")


if __name__ == "__main__":
    main()
