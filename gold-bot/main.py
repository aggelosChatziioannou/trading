"""Gold ICT Trading Bot - TJR Strategy - Main entry point."""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data.downloader import download_gold_multi_tf, download_dxy_multi_tf, load_csv
from data.manager import DataManager
from backtest.engine import run_backtest
from backtest.report import generate_report
from config.settings import STARTING_CAPITAL


def main():
    parser = argparse.ArgumentParser(description="Gold ICT Trading Bot - TJR Strategy")
    parser.add_argument("--capital", type=float, default=STARTING_CAPITAL)
    parser.add_argument("--months", type=int, default=6, help="Months of data to download")
    parser.add_argument("--gold-csv", type=str, default=None, help="Gold CSV (any TF)")
    parser.add_argument("--dxy-csv", type=str, default=None, help="DXY CSV (any TF)")
    parser.add_argument("--output", type=str, default="results")
    parser.add_argument("--no-dxy", action="store_true", help="Skip DXY download")
    parser.add_argument("--no-walk-forward", action="store_true", help="Skip walk-forward analysis")
    args = parser.parse_args()

    start_time = time.time()

    print("=" * 70)
    print("  GOLD ICT TRADING BOT - TJR STRATEGY")
    print("  Power of 3: Asia Accumulation -> London Manipulation -> NY Distribution")
    print("=" * 70)

    # ── Load Data ─────────────────────────────────────────────────────
    gold_data = {}
    dxy_data = {}

    if args.gold_csv:
        print(f"\nLoading Gold data from CSV: {args.gold_csv}")
        csv_data = load_csv(args.gold_csv)
        # Detect timeframe from data frequency
        if len(csv_data) > 1:
            freq = (csv_data.index[1] - csv_data.index[0]).total_seconds()
            if freq <= 60:
                gold_data["1m"] = csv_data
            elif freq <= 300:
                gold_data["5m"] = csv_data
            elif freq <= 900:
                gold_data["15m"] = csv_data
            else:
                gold_data["1h"] = csv_data
        print(f"  Loaded {len(csv_data)} bars")
    else:
        print(f"\nDownloading Gold data ({args.months} months)...")
        gold_data = download_gold_multi_tf(months=args.months)

    if not gold_data:
        print("ERROR: No gold data available.")
        sys.exit(1)

    if args.dxy_csv:
        print(f"Loading DXY data from CSV: {args.dxy_csv}")
        dxy_csv = load_csv(args.dxy_csv)
        dxy_data["5m"] = dxy_csv
    elif not args.no_dxy:
        print(f"\nDownloading DXY data ({args.months} months)...")
        try:
            dxy_data = download_dxy_multi_tf(months=args.months)
        except Exception as e:
            print(f"  DXY download failed ({e}), continuing without SMT")

    # ── Build DataManager ─────────────────────────────────────────────
    print("\nBuilding multi-timeframe data...")
    data = DataManager(gold_data=gold_data, dxy_data=dxy_data)

    # Print data summary
    for tf in ["1m", "5m", "15m", "1h", "4h", "1d"]:
        df = getattr(data, f"gold_{tf}", None)
        if df is not None and not df.empty:
            print(f"  Gold {tf}: {len(df)} bars ({df.index[0]} to {df.index[-1]})")
    if data.has_dxy:
        for tf in ["5m", "1h"]:
            df = getattr(data, f"dxy_{tf}", None)
            if df is not None and not df.empty:
                print(f"  DXY {tf}: {len(df)} bars")

    print(f"  Primary entry TF: {data.base_tf}")

    # ── Run Backtest ──────────────────────────────────────────────────
    print(f"\nRunning backtest with ${args.capital:,.2f} capital...")
    result = run_backtest(data, capital=args.capital)

    # ── Generate Report ───────────────────────────────────────────────
    report_data = data if not args.no_walk_forward else None
    metrics = generate_report(
        result, data=report_data, capital=args.capital, output_dir=args.output,
    )

    elapsed = time.time() - start_time
    print(f"\nTotal runtime: {elapsed:.1f}s")

    return metrics


if __name__ == "__main__":
    main()
