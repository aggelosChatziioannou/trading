#!/usr/bin/env python3
"""
GOLD TACTIC — Initial Balance Breakout (IBB) Backtester
Strategy: Wait for first hour range (Initial Balance), trade breakout with retracement.
Based on: TradeThisSwing IBB strategy (411% in 1 year on Gold Futures).

Rules:
1. Mark first 1 hour of NY session as "Initial Balance" (IB)
2. IB = High/Low of first hour (14:30-15:30 UTC for Gold)
3. Wait for breakout above IB High or below IB Low
4. Entry on retracement back to IB edge
5. SL: opposite side of IB
6. TP: 1.5x IB range from entry

Usage:
  python backtest_ibb.py                    # XAUUSD 60 days
  python backtest_ibb.py XAUUSD            # Same
  python backtest_ibb.py NAS100            # NAS100
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
    "XAUUSD": {
        "yf": "GC=F",
        "ib_start_utc": 14,  # 14:30 UTC = 9:30 AM EST (NY open)
        "ib_end_utc": 15,    # 15:30 UTC = 10:30 AM EST
        "session_end_utc": 21,  # 21:00 UTC = 4:00 PM EST
        "adr_typical": 40,
    },
    "NAS100": {
        "yf": "NQ=F",
        "ib_start_utc": 14,
        "ib_end_utc": 15,
        "session_end_utc": 21,
        "adr_typical": 350,
    },
}


def find_initial_balance(df, date, config):
    """Find Initial Balance (first hour range) for a date."""
    if df.index.tz is not None:
        df_utc = df.copy()
        df_utc.index = df_utc.index.tz_convert('UTC')
    else:
        df_utc = df

    ib_start = config["ib_start_utc"]
    ib_end = config["ib_end_utc"]

    ib_mask = (
        (df_utc.index.date == date) &
        (df_utc.index.hour >= ib_start) &
        (df_utc.index.hour < ib_end)
    )
    ib_candles = df_utc[ib_mask]

    if len(ib_candles) < 3:
        return None, None, None

    ib_high = float(ib_candles['High'].max())
    ib_low = float(ib_candles['Low'].min())
    ib_range = ib_high - ib_low

    return ib_high, ib_low, ib_range


def find_ibb_trade(df, date, ib_high, ib_low, ib_range, config):
    """
    Find IBB trade after IB is established.
    Look for: breakout beyond IB → retracement back to IB edge → entry.
    """
    if df.index.tz is not None:
        df_utc = df.copy()
        df_utc.index = df_utc.index.tz_convert('UTC')
    else:
        df_utc = df

    ib_end = config["ib_end_utc"]
    session_end = config["session_end_utc"]

    # After IB, during NY session
    post_ib_mask = (
        (df_utc.index.date == date) &
        (df_utc.index.hour >= ib_end) &
        (df_utc.index.hour < session_end)
    )
    post_ib = df_utc[post_ib_mask]

    if len(post_ib) < 5:
        return None

    # Skip if IB range too small (< 20% of ADR)
    if ib_range < config["adr_typical"] * 0.15:
        return None

    # Skip if IB range too large (> 80% of ADR = no room left)
    if ib_range > config["adr_typical"] * 0.8:
        return None

    breakout_up = False
    breakout_down = False
    breakout_price = None
    breakout_time = None

    for i in range(len(post_ib)):
        candle = post_ib.iloc[i]

        # Detect breakout above IB High
        if not breakout_up and not breakout_down:
            if candle['Close'] > ib_high:
                breakout_up = True
                breakout_price = float(candle['Close'])
                breakout_time = post_ib.index[i]
            elif candle['Close'] < ib_low:
                breakout_down = True
                breakout_price = float(candle['Close'])
                breakout_time = post_ib.index[i]

        # After breakout UP, wait for retracement to IB High (entry zone)
        if breakout_up and i > 0:
            # Retracement: price comes back to IB High area
            if candle['Low'] <= ib_high + (ib_range * 0.1):  # Within 10% of IB High
                entry = ib_high + (ib_range * 0.05)  # Slight buffer above IB High
                sl = ib_low - (ib_range * 0.1)  # Below IB Low + buffer
                risk = entry - sl
                tp = entry + (ib_range * 1.5)  # 1.5x IB range

                return {
                    "direction": "LONG",
                    "breakout_time": str(breakout_time),
                    "entry_time": str(post_ib.index[i]),
                    "entry_price": round(entry, 2),
                    "sl": round(sl, 2),
                    "tp": round(tp, 2),
                    "risk": round(risk, 2),
                    "ib_high": ib_high,
                    "ib_low": ib_low,
                    "ib_range": round(ib_range, 2),
                }

        # After breakout DOWN, wait for retracement to IB Low
        if breakout_down and i > 0:
            if candle['High'] >= ib_low - (ib_range * 0.1):
                entry = ib_low - (ib_range * 0.05)
                sl = ib_high + (ib_range * 0.1)
                risk = sl - entry
                tp = entry - (ib_range * 1.5)

                return {
                    "direction": "SHORT",
                    "breakout_time": str(breakout_time),
                    "entry_time": str(post_ib.index[i]),
                    "entry_price": round(entry, 2),
                    "sl": round(sl, 2),
                    "tp": round(tp, 2),
                    "risk": round(risk, 2),
                    "ib_high": ib_high,
                    "ib_low": ib_low,
                    "ib_range": round(ib_range, 2),
                }

    return None


def simulate_ibb_outcome(df, trade, date, config):
    """Simulate trade outcome — TP or SL or EOD close."""
    if df.index.tz is not None:
        df_utc = df.copy()
        df_utc.index = df_utc.index.tz_convert('UTC')
    else:
        df_utc = df

    entry_time = pd.Timestamp(trade["entry_time"])
    if entry_time.tzinfo:
        entry_time = entry_time.tz_convert('UTC')

    session_end = config["session_end_utc"]
    after_entry = df_utc[
        (df_utc.index > entry_time) &
        (df_utc.index.date == date) &
        (df_utc.index.hour < session_end)
    ]

    if after_entry.empty:
        return "NO_DATA", 0

    is_long = trade["direction"] == "LONG"

    for i in range(len(after_entry)):
        candle = after_entry.iloc[i]

        if is_long:
            if candle['Low'] <= trade["sl"]:
                return "SL_HIT", -(trade["risk"])
            if candle['High'] >= trade["tp"]:
                return "TP_HIT", trade["risk"] * 1.5
        else:
            if candle['High'] >= trade["sl"]:
                return "SL_HIT", -(trade["risk"])
            if candle['Low'] <= trade["tp"]:
                return "TP_HIT", trade["risk"] * 1.5

    # EOD close
    last = float(after_entry['Close'].iloc[-1])
    if is_long:
        pnl = last - trade["entry_price"]
    else:
        pnl = trade["entry_price"] - last

    return "EOD_CLOSE", pnl


def run_ibb_backtest(asset="XAUUSD"):
    config = ASSETS.get(asset)
    if not config:
        print(f"Unknown asset: {asset}")
        return

    print(f"{'='*60}")
    print(f"  GOLD TACTIC — IBB Backtest")
    print(f"  Asset: {asset}")
    print(f"  Strategy: Initial Balance Breakout (1st hour NY)")
    print(f"{'='*60}")

    print("\nDownloading 5min data (60 days max)...")
    df = yf.download(config["yf"], period="60d", interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    print(f"  5min bars: {len(df)}")

    if df.empty:
        print("No data!")
        return

    if df.index.tz is not None:
        dates = sorted(set(df.index.tz_convert('UTC').date))
    else:
        dates = sorted(set(df.index.date))

    print(f"  Trading days: {len(dates)}")
    print(f"\n{'─'*60}")

    results = []

    for date in dates:
        ib_high, ib_low, ib_range = find_initial_balance(df, date, config)
        if ib_high is None:
            continue

        trade = find_ibb_trade(df, date, ib_high, ib_low, ib_range, config)
        if trade is None:
            continue

        outcome, pnl = simulate_ibb_outcome(df, trade, date, config)

        trade["date"] = str(date)
        trade["outcome"] = outcome
        trade["pnl_dollars"] = round(pnl, 2)

        emoji = "✅" if pnl > 0 else "❌" if pnl < 0 else "⚪"
        print(f"  {emoji} {date} | {trade['direction']:6s} | "
              f"IB: {ib_low:.0f}-{ib_high:.0f} (${ib_range:.0f}) | "
              f"Entry: {trade['entry_price']:.0f} | "
              f"{outcome}: ${pnl:+.2f}")

        results.append(trade)

    # Summary
    print(f"\n{'='*60}")
    print(f"  IBB BACKTEST RESULTS — {asset}")
    print(f"{'='*60}")

    if not results:
        print("  No setups found!")
        return

    wins = [r for r in results if r["pnl_dollars"] > 0]
    losses = [r for r in results if r["pnl_dollars"] < 0]

    total_pnl = sum(r["pnl_dollars"] for r in results)
    win_rate = len(wins) / len(results) * 100

    avg_win = np.mean([r["pnl_dollars"] for r in wins]) if wins else 0
    avg_loss = np.mean([abs(r["pnl_dollars"]) for r in losses]) if losses else 0
    rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0

    risk_per_trade = 15.0
    total_pnl_eur = sum(
        risk_per_trade * (r["pnl_dollars"] / r["risk"]) if r["risk"] != 0 else 0
        for r in results
    )

    print(f"  Days scanned: {len(dates)}")
    print(f"  Trades taken: {len(results)} ({len(results)/len(dates)*100:.0f}% of days)")
    print(f"  Wins: {len(wins)} | Losses: {len(losses)}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Avg Win: ${avg_win:+.2f} | Avg Loss: ${avg_loss:.2f}")
    print(f"  Risk:Reward: 1:{rr_ratio:.2f}")
    print(f"  Total P&L (raw): ${total_pnl:+.2f}")
    print(f"")
    print(f"  --- With 1,000 EUR Capital (1.5% risk) ---")
    print(f"  Total P&L: {total_pnl_eur:+.2f} EUR")
    print(f"  Return: {total_pnl_eur/10:+.1f}%")
    print(f"  Final Balance: {1000 + total_pnl_eur:.2f} EUR")

    # By direction
    for d in set(r["direction"] for r in results):
        subset = [r for r in results if r["direction"] == d]
        d_wins = len([r for r in subset if r["pnl_dollars"] > 0])
        d_pnl = sum(r["pnl_dollars"] for r in subset)
        d_wr = d_wins / len(subset) * 100
        print(f"  {d}: {len(subset)} trades, {d_wr:.0f}% WR, ${d_pnl:+.2f}")

    # By outcome
    print(f"\n  --- By Outcome ---")
    for o in set(r["outcome"] for r in results):
        count = len([r for r in results if r["outcome"] == o])
        print(f"  {o}: {count}")

    # Save
    output = {
        "asset": asset,
        "strategy": "Initial Balance Breakout",
        "scan_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "days_scanned": len(dates),
        "total_trades": len(results),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "rr_ratio": round(rr_ratio, 2),
        "total_pnl_raw": round(total_pnl, 2),
        "total_pnl_eur": round(total_pnl_eur, 2),
        "final_balance": round(1000 + total_pnl_eur, 2),
        "trades": results,
    }

    outfile = OUTPUT_DIR / f"backtest_IBB_{asset}.json"
    outfile.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\nSaved to {outfile}")

    return results


if __name__ == "__main__":
    asset = sys.argv[1].upper() if len(sys.argv) > 1 else "XAUUSD"
    run_ibb_backtest(asset)
