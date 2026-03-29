#!/usr/bin/env python3
"""
GOLD TACTIC — Backtest Scanner (Hybrid Phase 1)
Scans historical data for TJR Asia Sweep setups.
Finds days where sweep + BOS occurred, calculates theoretical P&L.

Usage:
  python backtest_scanner.py                    # XAUUSD 6 months
  python backtest_scanner.py XAUUSD 12mo        # XAUUSD 12 months
  python backtest_scanner.py NAS100 6mo          # NAS100 6 months
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ASSETS = {
    "XAUUSD": {"yf": "GC=F", "pip_size": 0.10, "adr_typical": 40, "pip_value": 10},
    "NAS100": {"yf": "NQ=F", "pip_size": 1.0, "adr_typical": 350, "pip_value": 1},
    "EURUSD": {"yf": "EURUSD=X", "pip_size": 0.0001, "adr_typical": 0.008, "pip_value": 10},
    "USDJPY": {"yf": "JPY=X", "pip_size": 0.01, "adr_typical": 1.0, "pip_value": 7},
    "BTC": {"yf": "BTC-USD", "pip_size": 1.0, "adr_typical": 2000, "pip_value": 1},
    "GBPUSD": {"yf": "GBPUSD=X", "pip_size": 0.0001, "adr_typical": 0.010, "pip_value": 10},
    "AUDUSD": {"yf": "AUDUSD=X", "pip_size": 0.0001, "adr_typical": 0.007, "pip_value": 10},
    "GBPJPY": {"yf": "GBPJPY=X", "pip_size": 0.01, "adr_typical": 1.5, "pip_value": 7},
    "SOL": {"yf": "SOL-USD", "pip_size": 0.01, "adr_typical": 8.0, "pip_value": 1},
}


def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def get_daily_bias(daily_df, date):
    """Get daily bias for a specific date using EMAs."""
    mask = daily_df.index.date <= date
    subset = daily_df[mask]
    if len(subset) < 50:
        return "UNKNOWN"

    ema50 = subset['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
    price = subset['Close'].iloc[-1]
    rsi = compute_rsi(subset['Close'], 14).iloc[-1]

    if price > ema50:
        return "BULL"
    else:
        return "BEAR"


def find_asia_range_for_date(intraday_df, date):
    """
    Find Asia session range for a given date.
    Asia session: 00:00-07:00 UTC (approx).
    """
    if intraday_df.index.tz is not None:
        df = intraday_df.copy()
        df.index = df.index.tz_convert('UTC')
    else:
        df = intraday_df

    asia_mask = (
        (df.index.date == date) &
        (df.index.hour >= 0) &
        (df.index.hour < 7)
    )
    asia = df[asia_mask]

    if len(asia) < 3:
        return None, None

    return float(asia['High'].max()), float(asia['Low'].min())


def check_sweep_and_bos(intraday_df, date, asia_high, asia_low, daily_bias):
    """
    Check if sweep + BOS happened during London/NY session.
    Returns trade details if setup found, None otherwise.
    """
    if intraday_df.index.tz is not None:
        df = intraday_df.copy()
        df.index = df.index.tz_convert('UTC')
    else:
        df = intraday_df

    # London + NY session: 07:00-21:00 UTC
    session_mask = (
        (df.index.date == date) &
        (df.index.hour >= 7) &
        (df.index.hour <= 21)
    )
    session = df[session_mask]

    if len(session) < 10:
        return None

    asia_range = asia_high - asia_low
    if asia_range <= 0:
        return None

    # Check for sweep patterns
    trades = []

    # BEARISH setup: Sweep Asia HIGH + BOS down
    if daily_bias == "BEAR":
        sweep_found = False
        sweep_price = None
        sweep_time = None

        for i in range(len(session)):
            candle = session.iloc[i]

            # Sweep: wick above Asia High but close back below
            if not sweep_found:
                if candle['High'] > asia_high and candle['Close'] < asia_high:
                    sweep_found = True
                    sweep_price = float(candle['High'])
                    sweep_time = session.index[i]

            # BOS: after sweep, look for break below recent swing low
            if sweep_found and i > 0:
                # Simple BOS: close below Asia Low
                if candle['Close'] < asia_low:
                    entry_price = float(candle['Close'])
                    sl = sweep_price + (asia_range * 0.1)  # Above sweep + buffer
                    risk = sl - entry_price
                    tp1 = entry_price - (risk * 1.5)
                    tp2 = entry_price - (risk * 2.5)

                    trades.append({
                        "direction": "SHORT",
                        "sweep_time": str(sweep_time),
                        "entry_time": str(session.index[i]),
                        "entry_price": entry_price,
                        "sl": sl,
                        "tp1": tp1,
                        "tp2": tp2,
                        "risk": risk,
                        "sweep_price": sweep_price,
                    })
                    break

    # BULLISH setup: Sweep Asia LOW + BOS up
    if daily_bias == "BULL":
        sweep_found = False
        sweep_price = None
        sweep_time = None

        for i in range(len(session)):
            candle = session.iloc[i]

            if not sweep_found:
                if candle['Low'] < asia_low and candle['Close'] > asia_low:
                    sweep_found = True
                    sweep_price = float(candle['Low'])
                    sweep_time = session.index[i]

            if sweep_found and i > 0:
                if candle['Close'] > asia_high:
                    entry_price = float(candle['Close'])
                    sl = sweep_price - (asia_range * 0.1)
                    risk = entry_price - sl
                    tp1 = entry_price + (risk * 1.5)
                    tp2 = entry_price + (risk * 2.5)

                    trades.append({
                        "direction": "LONG",
                        "sweep_time": str(sweep_time),
                        "entry_time": str(session.index[i]),
                        "entry_price": entry_price,
                        "sl": sl,
                        "tp1": tp1,
                        "tp2": tp2,
                        "risk": risk,
                        "sweep_price": sweep_price,
                    })
                    break

    # OVERSOLD BOUNCE: Sweep lows even in BEAR (new rule)
    if daily_bias == "BEAR":
        sweep_found = False
        sweep_price = None
        sweep_time = None

        for i in range(len(session)):
            candle = session.iloc[i]

            if not sweep_found:
                if candle['Low'] < asia_low and candle['Close'] > asia_low:
                    sweep_found = True
                    sweep_price = float(candle['Low'])
                    sweep_time = session.index[i]

            if sweep_found and i > 0:
                if candle['Close'] > asia_high:
                    entry_price = float(candle['Close'])
                    sl = sweep_price - (asia_range * 0.1)
                    risk = entry_price - sl
                    tp1 = entry_price + (risk * 1.0)  # Tighter TP for counter-trend
                    tp2 = entry_price + (risk * 1.5)

                    trades.append({
                        "direction": "COUNTER-TREND LONG",
                        "sweep_time": str(sweep_time),
                        "entry_time": str(session.index[i]),
                        "entry_price": entry_price,
                        "sl": sl,
                        "tp1": tp1,
                        "tp2": tp2,
                        "risk": risk,
                        "sweep_price": sweep_price,
                    })
                    break

    return trades[0] if trades else None


def simulate_trade_outcome(intraday_df, trade, date):
    """
    Simulate what happened after entry — did it hit TP1, TP2, or SL?
    """
    if intraday_df.index.tz is not None:
        df = intraday_df.copy()
        df.index = df.index.tz_convert('UTC')
    else:
        df = intraday_df

    entry_time = pd.Timestamp(trade["entry_time"])
    if entry_time.tzinfo:
        entry_time = entry_time.tz_convert('UTC')

    # Get candles after entry
    after_entry = df[df.index > entry_time]
    # Only same day + next day
    end_date = date + timedelta(days=1)
    after_entry = after_entry[after_entry.index.date <= end_date]

    if after_entry.empty:
        return "UNKNOWN", 0

    direction = trade["direction"]
    is_long = "LONG" in direction

    for i in range(len(after_entry)):
        candle = after_entry.iloc[i]

        if is_long:
            # Check SL first (worst case)
            if candle['Low'] <= trade["sl"]:
                pnl = -(trade["risk"])
                return "SL_HIT", pnl
            # Check TP1
            if candle['High'] >= trade["tp1"]:
                pnl = trade["risk"] * 1.5 * 0.5  # 50% at TP1
                # Check if TP2 also hit
                remaining = after_entry.iloc[i:]
                for j in range(len(remaining)):
                    if remaining.iloc[j]['High'] >= trade["tp2"]:
                        pnl += trade["risk"] * 2.5 * 0.5
                        return "TP2_HIT", pnl
                    if remaining.iloc[j]['Low'] <= trade["entry_price"]:  # BE stop
                        return "TP1_HIT+BE", pnl
                return "TP1_HIT", pnl
        else:
            # SHORT
            if candle['High'] >= trade["sl"]:
                pnl = -(trade["risk"])
                return "SL_HIT", pnl
            if candle['Low'] <= trade["tp1"]:
                pnl = trade["risk"] * 1.5 * 0.5
                remaining = after_entry.iloc[i:]
                for j in range(len(remaining)):
                    if remaining.iloc[j]['Low'] <= trade["tp2"]:
                        pnl += trade["risk"] * 2.5 * 0.5
                        return "TP2_HIT", pnl
                    if remaining.iloc[j]['High'] >= trade["entry_price"]:
                        return "TP1_HIT+BE", pnl
                return "TP1_HIT", pnl

    # End of day — close at last price
    last_price = float(after_entry['Close'].iloc[-1])
    if is_long:
        pnl = last_price - trade["entry_price"]
    else:
        pnl = trade["entry_price"] - last_price
    return "EOD_CLOSE", pnl


def run_backtest(asset="XAUUSD", period="6mo"):
    """Run full backtest scan."""
    config = ASSETS.get(asset)
    if not config:
        print(f"Unknown asset: {asset}")
        return

    print(f"{'='*60}")
    print(f"  GOLD TACTIC — Backtest Scanner")
    print(f"  Asset: {asset} | Period: {period}")
    print(f"  Strategy: TJR Asia Sweep + BOS")
    print(f"{'='*60}")

    # Download data
    print("\nDownloading daily data...")
    daily = yf.download(config["yf"], period=period, interval="1d", progress=False)
    if isinstance(daily.columns, pd.MultiIndex):
        daily.columns = daily.columns.get_level_values(0)
    print(f"  Daily bars: {len(daily)}")

    print("Downloading 5min data (max 60 days)...")
    intraday = yf.download(config["yf"], period="60d", interval="5m", progress=False)
    if isinstance(intraday.columns, pd.MultiIndex):
        intraday.columns = intraday.columns.get_level_values(0)
    print(f"  5min bars: {len(intraday)}")

    if intraday.empty:
        print("No intraday data!")
        return

    # Get unique dates from intraday data
    if intraday.index.tz is not None:
        dates = sorted(set(intraday.index.tz_convert('UTC').date))
    else:
        dates = sorted(set(intraday.index.date))

    print(f"  Trading days to scan: {len(dates)}")
    print(f"\n{'─'*60}")
    print(f"  Scanning for TJR setups...")
    print(f"{'─'*60}\n")

    results = []
    setups_found = 0

    for date in dates:
        # Get daily bias
        bias = get_daily_bias(daily, date)
        if bias == "UNKNOWN":
            continue

        # Find Asia range
        asia_h, asia_l = find_asia_range_for_date(intraday, date)
        if asia_h is None:
            continue

        asia_range = asia_h - asia_l
        adr = config["adr_typical"]

        # Skip if Asia range is too extreme (>200% ADR)
        if adr > 0 and asia_range > adr * 2:
            continue

        # Check for sweep + BOS
        trade = check_sweep_and_bos(intraday, date, asia_h, asia_l, bias)
        if trade is None:
            continue

        setups_found += 1

        # Simulate outcome
        outcome, pnl = simulate_trade_outcome(intraday, trade, date)

        trade["date"] = str(date)
        trade["daily_bias"] = bias
        trade["asia_high"] = asia_h
        trade["asia_low"] = asia_l
        trade["asia_range"] = asia_range
        trade["outcome"] = outcome
        trade["pnl_dollars"] = round(pnl, 2)

        emoji = "✅" if pnl > 0 else "❌" if pnl < 0 else "⚪"
        print(f"  {emoji} {date} | {trade['direction']:20s} | "
              f"Entry: {trade['entry_price']:.2f} | "
              f"Asia: {asia_l:.2f}-{asia_h:.2f} | "
              f"{outcome}: ${pnl:+.2f}")

        results.append(trade)

    # Summary
    print(f"\n{'='*60}")
    print(f"  BACKTEST RESULTS")
    print(f"{'='*60}")

    if not results:
        print("  No setups found!")
        return results

    wins = [r for r in results if r["pnl_dollars"] > 0]
    losses = [r for r in results if r["pnl_dollars"] < 0]
    neutral = [r for r in results if r["pnl_dollars"] == 0]

    total_pnl = sum(r["pnl_dollars"] for r in results)
    win_rate = len(wins) / len(results) * 100 if results else 0
    avg_win = np.mean([r["pnl_dollars"] for r in wins]) if wins else 0
    avg_loss = np.mean([r["pnl_dollars"] for r in losses]) if losses else 0

    # With 1000 EUR capital, 1.5% risk
    risk_per_trade = 15.0  # EUR
    total_pnl_eur = sum(
        risk_per_trade * (r["pnl_dollars"] / r["risk"]) if r["risk"] != 0 else 0
        for r in results
    )

    print(f"  Days scanned: {len(dates)}")
    print(f"  Setups found: {setups_found}")
    print(f"  Trades taken: {len(results)}")
    print(f"  Wins: {len(wins)} | Losses: {len(losses)} | Neutral: {len(neutral)}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Avg Win: ${avg_win:+.2f} | Avg Loss: ${avg_loss:+.2f}")
    print(f"  Total P&L (raw): ${total_pnl:+.2f}")
    print(f"")
    print(f"  --- With 1,000 EUR Capital (1.5% risk) ---")
    print(f"  Total P&L: {total_pnl_eur:+.2f} EUR")
    print(f"  Return: {total_pnl_eur/10:+.1f}%")
    print(f"  Final Balance: {1000 + total_pnl_eur:.2f} EUR")

    if losses:
        max_loss = min(r["pnl_dollars"] for r in results)
        print(f"  Worst Trade: ${max_loss:.2f}")
    if wins:
        max_win = max(r["pnl_dollars"] for r in results)
        print(f"  Best Trade: ${max_win:+.2f}")

    # Breakdown by type
    types = {}
    for r in results:
        d = r["direction"]
        if d not in types:
            types[d] = {"count": 0, "wins": 0, "pnl": 0}
        types[d]["count"] += 1
        types[d]["pnl"] += r["pnl_dollars"]
        if r["pnl_dollars"] > 0:
            types[d]["wins"] += 1

    print(f"\n  --- By Direction ---")
    for d, stats in types.items():
        wr = stats["wins"] / stats["count"] * 100 if stats["count"] > 0 else 0
        print(f"  {d}: {stats['count']} trades, {wr:.0f}% WR, ${stats['pnl']:+.2f}")

    # Breakdown by outcome
    outcomes = {}
    for r in results:
        o = r["outcome"]
        if o not in outcomes:
            outcomes[o] = 0
        outcomes[o] += 1

    print(f"\n  --- By Outcome ---")
    for o, count in sorted(outcomes.items()):
        print(f"  {o}: {count}")

    print(f"{'='*60}")

    # Save results
    output = {
        "asset": asset,
        "period": period,
        "scan_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "days_scanned": len(dates),
        "setups_found": setups_found,
        "total_trades": len(results),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "total_pnl_raw": round(total_pnl, 2),
        "total_pnl_eur": round(total_pnl_eur, 2),
        "final_balance_eur": round(1000 + total_pnl_eur, 2),
        "trades": results,
    }

    outfile = OUTPUT_DIR / f"backtest_{asset}.json"
    outfile.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\nResults saved to {outfile}")

    return results


if __name__ == "__main__":
    asset = sys.argv[1] if len(sys.argv) > 1 else "XAUUSD"
    period = sys.argv[2] if len(sys.argv) > 2 else "6mo"
    asset = asset.upper()

    run_backtest(asset, period)
