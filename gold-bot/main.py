"""Gold ICT Trading Bot - Main entry point."""
import argparse
import sys
from pathlib import Path

# Add gold-bot to path
sys.path.insert(0, str(Path(__file__).parent))

from data.downloader import download_gold, download_dxy, load_csv
from data.manager import DataManager
from backtest.engine import run_backtest
from backtest.report import generate_report
from config.settings import STARTING_CAPITAL


def main():
    parser = argparse.ArgumentParser(description="Gold ICT Trading Bot")
    parser.add_argument("--capital", type=float, default=STARTING_CAPITAL,
                        help="Starting capital (default: $500)")
    parser.add_argument("--gold-csv", type=str, default=None,
                        help="Path to Gold 1-min CSV data")
    parser.add_argument("--dxy-csv", type=str, default=None,
                        help="Path to DXY 1-min CSV data")
    parser.add_argument("--period", type=str, default="7d",
                        help="yfinance download period (default: 7d)")
    parser.add_argument("--output", type=str, default="results",
                        help="Output directory for reports")
    args = parser.parse_args()

    print("=" * 60)
    print("  GOLD ICT TRADING BOT - BACKTEST MODE")
    print("=" * 60)

    # Load data
    if args.gold_csv:
        print(f"Loading Gold data from CSV: {args.gold_csv}")
        gold_1m = load_csv(args.gold_csv)
    else:
        print(f"Downloading Gold data (period={args.period})...")
        gold_1m = download_gold(period=args.period, interval="1m")

    if gold_1m.empty:
        print("ERROR: No gold data available. Try --gold-csv with historical data.")
        sys.exit(1)

    dxy_1m = None
    if args.dxy_csv:
        print(f"Loading DXY data from CSV: {args.dxy_csv}")
        dxy_1m = load_csv(args.dxy_csv)
    else:
        try:
            print(f"Downloading DXY data (period={args.period})...")
            dxy_1m = download_dxy(period=args.period, interval="1m")
            if dxy_1m.empty:
                dxy_1m = None
                print("  DXY data empty, continuing without SMT divergence")
        except Exception as e:
            print(f"  DXY download failed ({e}), continuing without SMT divergence")

    print(f"Gold data: {len(gold_1m)} bars ({gold_1m.index[0]} to {gold_1m.index[-1]})")
    if dxy_1m is not None:
        print(f"DXY data: {len(dxy_1m)} bars")

    # Build multi-TF data
    data = DataManager(gold_1m=gold_1m, dxy_1m=dxy_1m)
    print(f"Timeframes: 1m={len(data.gold_1m)}, 5m={len(data.gold_5m)}, "
          f"1H={len(data.gold_1h)}, 4H={len(data.gold_4h)}")

    # Run backtest
    print(f"\nRunning backtest with ${args.capital:,.2f} capital...")
    result = run_backtest(data, capital=args.capital)

    # Generate report
    metrics = generate_report(result, output_dir=args.output)

    return metrics


if __name__ == "__main__":
    main()
