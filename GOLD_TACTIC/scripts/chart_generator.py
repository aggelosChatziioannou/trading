#!/usr/bin/env python3
"""
GOLD TACTIC - Multi-Asset Chart Generator v2.0
Generates professional trading charts with:
  P0: Asia Range H/L, Session separators, PDH/PDL, Today-only 5min zoom
  P1: RSI subplot, Forex volume fix, 4H UTC alignment
  P2: Current price line, ADR % consumed, Finnhub price validation

Usage:
  python chart_generator.py              # All 3 assets
  python chart_generator.py XAUUSD       # Single asset
  python chart_generator.py --validate   # Generate + Finnhub cross-check
"""

import yfinance as yf
import mplfinance as mpf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os
import sys
import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

OUTPUT_DIR = Path(__file__).parent.parent / "screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY')
if not FINNHUB_API_KEY:
    raise ValueError("FINNHUB_API_KEY must be set in .env")

ASSETS = {
    # ---- Core 5 Assets (backtested) ----
    "EURUSD": {
        "yf_symbol": "EURUSD=X",
        "display_name": "EURUSD",
        "is_forex": True,
        "adr_typical": 0.0080,
        "price_fmt": ".4f",
        "strategy": "TJR",       # +23.8% backtest
    },
    "GBPUSD": {
        "yf_symbol": "GBPUSD=X",
        "display_name": "GBPUSD",
        "is_forex": True,
        "adr_typical": 0.010,
        "price_fmt": ".4f",
        "strategy": "TJR",       # +21.5% backtest
    },
    "NAS100": {
        "yf_symbol": "NQ=F",
        "display_name": "NAS100 (Nasdaq)",
        "is_forex": False,
        "adr_typical": 350.0,
        "price_fmt": ",.2f",
        "strategy": "IBB",       # +13.7% backtest, 60.5% WR
    },
    "SOL": {
        "yf_symbol": "SOL-USD",
        "display_name": "SOL (Solana)",
        "is_forex": False,
        "adr_typical": 8.0,
        "price_fmt": ",.2f",
        "strategy": "TJR",       # +8.4% backtest, 71% CT WR
    },
    "BTC": {
        "yf_symbol": "BTC-USD",
        "display_name": "BTC (Bitcoin)",
        "is_forex": False,
        "adr_typical": 2000,
        "price_fmt": ",.0f",
        "strategy": "TJR",       # +6.4% backtest, 58.3% WR
    },
    # ---- Extended Assets ----
    "XAUUSD": {
        "yf_symbol": "GC=F",
        "display_name": "XAUUSD (Gold)",
        "is_forex": False,
        "adr_typical": 30.0,
        "price_fmt": ",.2f",
        "strategy": "TJR",
    },
    "ETH": {
        "yf_symbol": "ETH-USD",
        "display_name": "ETH (Ethereum)",
        "is_forex": False,
        "adr_typical": 80.0,
        "price_fmt": ",.2f",
        "strategy": "TJR",
    },
    "XRP": {
        "yf_symbol": "XRP-USD",
        "display_name": "XRP (Ripple)",
        "is_forex": False,
        "adr_typical": 0.08,
        "price_fmt": ".4f",
        "strategy": "TJR",
    },
    "USDJPY": {
        "yf_symbol": "JPY=X",
        "display_name": "USDJPY",
        "is_forex": True,
        "adr_typical": 0.80,
        "price_fmt": ".3f",
        "strategy": "TJR",
    },
    "AUDUSD": {
        "yf_symbol": "AUDUSD=X",
        "display_name": "AUDUSD",
        "is_forex": True,
        "adr_typical": 0.0055,
        "price_fmt": ".4f",
        "strategy": "TJR",
    },
    "SPX500": {
        "yf_symbol": "ES=F",
        "display_name": "SPX500 (S&P 500)",
        "is_forex": False,
        "adr_typical": 50.0,
        "price_fmt": ",.2f",
        "strategy": "IBB",
    },
    "DXY": {
        "yf_symbol": "DX-Y.NYB",
        "display_name": "DXY (Dollar Index)",
        "is_forex": False,
        "adr_typical": 0.6,
        "price_fmt": ".3f",
        "strategy": "TJR",
    },
}

TIMEFRAMES = {
    "daily": {
        "interval": "1d",
        "period": "6mo",
        "ema_fast": 50,
        "ema_slow": 200,
        "max_bars": 120,
        "title_suffix": "Daily",
    },
    "4h": {
        "interval": "1h",
        "period": "60d",
        "resample": "4h",
        "resample_offset": "0h",  # Align to 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC
        "ema_fast": 21,
        "ema_slow": 50,
        "max_bars": 100,
        "title_suffix": "4H",
    },
    "5m": {
        "interval": "5m",
        "period": "5d",
        "ema_fast": 9,
        "ema_slow": 21,
        "max_bars": 200,
        "title_suffix": "5min",
        "today_only": True,  # P0: zoom to today
    },
}

# Session times in UTC (convert from EST: +5 hours)
# Asia: 7PM-2AM EST = 00:00-07:00 UTC
# London KZ: 2AM-5AM EST = 07:00-10:00 UTC
# NY open: 9:30AM EST = 14:30 UTC
# NY KZ: 7AM-10AM EST = 12:00-15:00 UTC
SESSIONS_UTC = {
    "asia_start": 0,    # 00:00 UTC = 7PM EST
    "asia_end": 7,      # 07:00 UTC = 2AM EST
    "london_open": 7,   # 07:00 UTC = 2AM EST (London KZ start)
    "ny_open": 14,      # 14:00 UTC ~= 9AM EST
}

# Chart style - TradingView dark theme
mc = mpf.make_marketcolors(
    up='#26a69a', down='#ef5350',
    edge='inherit', wick='inherit',
    volume={'up': '#26a69a80', 'down': '#ef535080'},
)
CHART_STYLE = mpf.make_mpf_style(
    marketcolors=mc,
    base_mpf_style='nightclouds',
    gridstyle='-',
    gridcolor='#2a2e39',
    facecolor='#131722',
    figcolor='#131722',
    rc={
        'axes.labelcolor': '#9598a1',
        'xtick.color': '#9598a1',
        'ytick.color': '#9598a1',
        'font.size': 10,
    }
)

# Colors for overlays
COLOR_ASIA_RANGE = '#FFD700'      # Gold for Asia H/L
COLOR_ASIA_FILL = '#FFD70015'     # Transparent gold fill
COLOR_PDH = '#00BFFF'             # Light blue for PDH
COLOR_PDL = '#FF6347'             # Tomato for PDL
COLOR_CURRENT = '#FFFFFF'         # White for current price
COLOR_SESSION_ASIA = '#FFD70050'  # Asia close line
COLOR_SESSION_LDN = '#4169E150'   # London open line
COLOR_SESSION_NY = '#FF634750'    # NY open line


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def resample_ohlcv(df, freq, offset="0h"):
    """Resample OHLCV data to a lower frequency with UTC alignment."""
    return df.resample(freq, offset=offset).agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()


def compute_rsi(series, period=14):
    """Compute RSI indicator."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def find_asia_range(df):
    """
    Find today's Asia session High/Low from 5min data.
    Asia session: 00:00-07:00 UTC (= 7PM-2AM EST)
    Returns (asia_high, asia_low) or (None, None)
    """
    if df.index.tz is None:
        # Assume UTC if no timezone
        df_utc = df.copy()
    else:
        df_utc = df.copy()
        df_utc.index = df_utc.index.tz_convert('UTC')

    today = df_utc.index[-1].date()

    # Filter Asia session candles for today
    asia_mask = (
        (df_utc.index.date == today) &
        (df_utc.index.hour >= SESSIONS_UTC["asia_start"]) &
        (df_utc.index.hour < SESSIONS_UTC["asia_end"])
    )
    asia_candles = df_utc[asia_mask]

    if asia_candles.empty:
        # Try yesterday if today's Asia hasn't started yet
        yesterday = today - timedelta(days=1)
        asia_mask = (
            (df_utc.index.date == yesterday) &
            (df_utc.index.hour >= SESSIONS_UTC["asia_start"]) &
            (df_utc.index.hour < SESSIONS_UTC["asia_end"])
        )
        asia_candles = df_utc[asia_mask]

    if asia_candles.empty:
        return None, None

    return float(asia_candles['High'].max()), float(asia_candles['Low'].min())


def find_pdh_pdl(df):
    """
    Find Previous Day High/Low from daily or intraday data.
    Returns (pdh, pdl) or (None, None)
    """
    if df.index.tz is None:
        df_work = df.copy()
    else:
        df_work = df.copy()
        df_work.index = df_work.index.tz_convert('UTC')

    # Group by date
    daily_groups = df_work.groupby(df_work.index.date)
    dates = sorted(daily_groups.groups.keys())

    if len(dates) < 2:
        return None, None

    # Previous day = second to last date
    prev_date = dates[-2]
    prev_day = daily_groups.get_group(prev_date)

    return float(prev_day['High'].max()), float(prev_day['Low'].min())


def compute_adr_consumed(df, adr_typical):
    """
    Compute how much of the Average Daily Range has been consumed today.
    Returns (today_range, adr_typical, pct_consumed)
    """
    if df.index.tz is None:
        df_work = df.copy()
    else:
        df_work = df.copy()
        df_work.index = df_work.index.tz_convert('UTC')

    today = df_work.index[-1].date()
    today_data = df_work[df_work.index.date == today]

    if today_data.empty:
        return 0, adr_typical, 0

    today_high = float(today_data['High'].max())
    today_low = float(today_data['Low'].min())
    today_range = today_high - today_low

    pct = (today_range / adr_typical * 100) if adr_typical > 0 else 0
    return today_range, adr_typical, pct


def get_session_vlines(df):
    """
    Get datetime positions for session separator vertical lines.
    Returns dict with session name -> list of datetime positions.
    """
    if df.index.tz is None:
        df_utc = df.copy()
    else:
        df_utc = df.copy()
        df_utc.index = df_utc.index.tz_convert('UTC')

    sessions = {"asia_close": [], "london_open": [], "ny_open": []}
    dates = sorted(set(df_utc.index.date))

    for d in dates:
        for hour, key in [
            (SESSIONS_UTC["asia_end"], "asia_close"),
            (SESSIONS_UTC["london_open"], "london_open"),
            (SESSIONS_UTC["ny_open"], "ny_open"),
        ]:
            ts = pd.Timestamp(year=d.year, month=d.month, day=d.day,
                              hour=hour, minute=0)
            # Find nearest candle in the dataframe
            if df_utc.index.tz:
                ts = ts.tz_localize('UTC')
            # Only include if within data range
            if df_utc.index[0] <= ts <= df_utc.index[-1]:
                # Map back to original timezone
                if df.index.tz:
                    ts = ts.tz_convert(df.index.tz)
                sessions[key].append(ts)

    return sessions


def fetch_finnhub_price(symbol, is_forex=False):
    """Fetch current price from Finnhub API for cross-validation."""
    try:
        if is_forex:
            # Forex endpoint: /forex/rates
            url = (f"https://finnhub.io/api/v1/forex/rates?"
                   f"base=EUR&token={FINNHUB_API_KEY}")
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                # Extract rate from response
                rates = data.get("quote", {})
                if "USD" in rates:
                    rate = 1.0 / rates["USD"]  # EUR/USD = 1/USD_per_EUR
                    return {"current": rate, "high": 0, "low": 0,
                            "open": 0, "prev_close": 0}
                return None
        else:
            url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                return {
                    "current": data.get("c", 0),
                    "high": data.get("h", 0),
                    "low": data.get("l", 0),
                    "open": data.get("o", 0),
                    "prev_close": data.get("pc", 0),
                }
    except Exception as e:
        print(f"  [WARN] Finnhub fetch failed for {symbol}: {e}")
        return None


# ============================================================
# CHART GENERATION
# ============================================================

def generate_chart(asset_name, asset_config, tf_name, tf_config):
    """Generate a single chart PNG with all overlays. Returns filepath or None."""
    yf_symbol = asset_config["yf_symbol"]
    display = asset_config["display_name"]
    is_forex = asset_config.get("is_forex", False)
    adr_typical = asset_config.get("adr_typical", 0)
    pfmt = asset_config.get("price_fmt", ",.2f")  # Price format string
    filename = f"{asset_name}_{tf_name}.png"
    filepath = OUTPUT_DIR / filename

    try:
        # Download data
        df = yf.download(
            yf_symbol,
            period=tf_config["period"],
            interval=tf_config["interval"],
            progress=False,
        )

        if df.empty:
            print(f"  [WARN] No data for {asset_name} {tf_name}")
            return None

        # Flatten multi-level columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # P1: 4H resample with UTC alignment
        if "resample" in tf_config:
            offset = tf_config.get("resample_offset", "0h")
            df = resample_ohlcv(df, tf_config["resample"], offset)

        # P0: Zoom 5min to today only
        if tf_config.get("today_only") and tf_name == "5m":
            if df.index.tz is not None:
                df_check = df.copy()
                df_check.index = df_check.index.tz_convert('UTC')
            else:
                df_check = df

            today = df_check.index[-1].date()
            yesterday = today - timedelta(days=1)

            # Keep yesterday's Asia session + today for context
            keep_mask = df_check.index.date >= yesterday
            df = df[keep_mask]

            # Still cap at max_bars
            max_bars = tf_config.get("max_bars", 200)
            if len(df) > max_bars:
                df = df.tail(max_bars)
        else:
            max_bars = tf_config.get("max_bars", 120)
            if len(df) > max_bars:
                df = df.tail(max_bars)

        if len(df) < 5:
            print(f"  [WARN] Too few bars for {asset_name} {tf_name}: {len(df)}")
            return None

        # ---- Compute indicators ----

        # EMA overlays
        ema_fast = tf_config["ema_fast"]
        ema_slow = tf_config["ema_slow"]
        added_plots = []

        if len(df) >= ema_fast:
            df[f'EMA{ema_fast}'] = df['Close'].ewm(span=ema_fast, adjust=False).mean()
            added_plots.append(mpf.make_addplot(
                df[f'EMA{ema_fast}'], color='#2196F3', width=1.5))
        if len(df) >= ema_slow:
            df[f'EMA{ema_slow}'] = df['Close'].ewm(span=ema_slow, adjust=False).mean()
            added_plots.append(mpf.make_addplot(
                df[f'EMA{ema_slow}'], color='#FF9800', width=1.5))

        # P1: Volume handling - hide for forex pairs
        show_volume = not is_forex

        # P1: RSI
        rsi = compute_rsi(df['Close'], period=14)
        df['RSI'] = rsi

        # RSI panel number depends on whether volume is shown
        # panel 0 = price, panel 1 = volume (if shown), next panel = RSI
        rsi_panel = 2 if show_volume else 1

        # P0: Asia Range (5min only)
        asia_high, asia_low = None, None
        if tf_name == "5m":
            asia_high, asia_low = find_asia_range(df)

        # P0: PDH/PDL (5min and 4h)
        pdh, pdl = None, None
        if tf_name in ("5m", "4h"):
            pdh, pdl = find_pdh_pdl(df)

        # P2: ADR consumed (5min only - today's range)
        adr_info = None
        if tf_name == "5m" and adr_typical > 0:
            adr_info = compute_adr_consumed(df, adr_typical)

        # ---- Build horizontal lines ----
        hlines_dict = {"hlines": [], "colors": [], "linestyle": [], "linewidths": []}

        # P0: Asia Range
        if asia_high is not None:
            hlines_dict["hlines"].append(asia_high)
            hlines_dict["colors"].append(COLOR_ASIA_RANGE)
            hlines_dict["linestyle"].append("--")
            hlines_dict["linewidths"].append(1.2)

            hlines_dict["hlines"].append(asia_low)
            hlines_dict["colors"].append(COLOR_ASIA_RANGE)
            hlines_dict["linestyle"].append("--")
            hlines_dict["linewidths"].append(1.2)

        # P0: PDH/PDL
        if pdh is not None:
            hlines_dict["hlines"].append(pdh)
            hlines_dict["colors"].append(COLOR_PDH)
            hlines_dict["linestyle"].append("-.")
            hlines_dict["linewidths"].append(1.0)

            hlines_dict["hlines"].append(pdl)
            hlines_dict["colors"].append(COLOR_PDL)
            hlines_dict["linestyle"].append("-.")
            hlines_dict["linewidths"].append(1.0)

        # P2: Current price line
        current_price = float(df['Close'].iloc[-1])
        hlines_dict["hlines"].append(current_price)
        hlines_dict["colors"].append(COLOR_CURRENT)
        hlines_dict["linestyle"].append("-")
        hlines_dict["linewidths"].append(0.6)

        # ---- Build vertical lines (session separators) ----
        vlines_dict = None
        if tf_name == "5m":
            sessions = get_session_vlines(df)
            all_vlines = []
            all_vcolors = []
            for ts in sessions.get("asia_close", []):
                all_vlines.append(ts)
                all_vcolors.append(COLOR_SESSION_ASIA)
            for ts in sessions.get("london_open", []):
                all_vlines.append(ts)
                all_vcolors.append(COLOR_SESSION_LDN)
            for ts in sessions.get("ny_open", []):
                all_vlines.append(ts)
                all_vcolors.append(COLOR_SESSION_NY)

            if all_vlines:
                vlines_dict = {
                    "vlines": all_vlines,
                    "colors": all_vcolors,
                    "linewidths": [0.8] * len(all_vlines),
                    "linestyle": ["--"] * len(all_vlines),
                }

        # ---- P1: RSI subplot ----
        # Add RSI as a panel below price
        rsi_plot = mpf.make_addplot(
            df['RSI'], panel=rsi_panel, color='#E040FB', width=1.0,
            ylabel='RSI(14)', ylim=(0, 100),
            secondary_y=False,
        )
        added_plots.append(rsi_plot)

        # RSI 30/70 reference lines
        rsi_30 = pd.Series(30.0, index=df.index)
        rsi_70 = pd.Series(70.0, index=df.index)
        added_plots.append(mpf.make_addplot(
            rsi_30, panel=rsi_panel, color='#FF634540', width=0.5, linestyle='--',
            secondary_y=False, ylim=(0, 100)))
        added_plots.append(mpf.make_addplot(
            rsi_70, panel=rsi_panel, color='#26a69a40', width=0.5, linestyle='--',
            secondary_y=False, ylim=(0, 100)))

        # ---- Chart title ----
        last_close = current_price
        last_time = df.index[-1]
        if hasattr(last_time, 'strftime'):
            time_str = last_time.strftime('%Y-%m-%d %H:%M')
        else:
            time_str = str(last_time)

        title = f"\n{display} -- {tf_config['title_suffix']}  |  {last_close:{pfmt}}  |  {time_str}"

        # ---- Build plot kwargs ----
        plot_kwargs = {
            "type": "candle",
            "style": CHART_STYLE,
            "title": title,
            "figsize": (16, 10),
            "tight_layout": True,
            "returnfig": True,
            "warn_too_much_data": 500,
            "panel_ratios": (4, 1, 2) if show_volume else (4, 2),
        }

        if show_volume:
            plot_kwargs["volume"] = True
        else:
            plot_kwargs["volume"] = False

        if added_plots:
            plot_kwargs["addplot"] = added_plots

        if hlines_dict["hlines"]:
            plot_kwargs["hlines"] = hlines_dict

        if vlines_dict:
            plot_kwargs["vlines"] = vlines_dict

        # ---- Generate chart ----
        fig, axes = mpf.plot(df, **plot_kwargs)

        # ---- Post-render: Fix RSI Y-axis ----
        # Force RSI panel to show 0-100 scale
        rsi_ax_idx = (rsi_panel * 2) if show_volume else (rsi_panel * 2)
        for ax in axes:
            if hasattr(ax, 'get_ylabel') and 'RSI' in str(ax.get_ylabel()):
                ax.set_ylim(0, 100)
                ax.set_yticks([20, 30, 50, 70, 80])
                break
        else:
            # Fallback: last axis is usually RSI
            try:
                axes[-2].set_ylim(0, 100)
                axes[-2].set_yticks([20, 30, 50, 70, 80])
            except (IndexError, Exception):
                pass

        # ---- Post-render annotations ----

        # EMA legend
        legend_parts = []
        if len(df) >= ema_fast:
            legend_parts.append(f"EMA{ema_fast}: {df[f'EMA{ema_fast}'].iloc[-1]:{pfmt}}")
        if len(df) >= ema_slow:
            legend_parts.append(f"EMA{ema_slow}: {df[f'EMA{ema_slow}'].iloc[-1]:{pfmt}}")
        if legend_parts:
            fig.text(0.13, 0.95, "  |  ".join(legend_parts),
                     color='#9598a1', fontsize=9)

        # P0: Asia Range label
        if asia_high is not None:
            fig.text(0.13, 0.93,
                     f"Asia Range: H={asia_high:{pfmt}}  L={asia_low:{pfmt}}  "
                     f"(Range: {asia_high - asia_low:{pfmt}})",
                     color=COLOR_ASIA_RANGE, fontsize=9, fontweight='bold')

        # P0: PDH/PDL label
        if pdh is not None:
            fig.text(0.13, 0.91,
                     f"PDH: {pdh:{pfmt}}  |  PDL: {pdl:{pfmt}}",
                     color='#9598a1', fontsize=9)

        # P2: ADR consumed
        if adr_info:
            today_range, adr, pct = adr_info
            adr_color = '#FF4444' if pct > 90 else '#FFD700' if pct > 70 else '#26a69a'
            fig.text(0.60, 0.95,
                     f"ADR: {today_range:{pfmt}} / {adr:{pfmt}} ({pct:.0f}% consumed)",
                     color=adr_color, fontsize=9, fontweight='bold')

        # P1: RSI value
        current_rsi = df['RSI'].iloc[-1]
        if not np.isnan(current_rsi):
            rsi_color = '#FF4444' if current_rsi > 70 else '#26a69a' if current_rsi < 30 else '#9598a1'
            fig.text(0.60, 0.93,
                     f"RSI(14): {current_rsi:.1f}",
                     color=rsi_color, fontsize=9)

        # Session legend (5min only)
        if tf_name == "5m":
            fig.text(0.60, 0.91,
                     "Sessions: -- gold=Asia close  -- blue=London  -- red=NY",
                     color='#555555', fontsize=8)

        # P2: Current price label
        fig.text(0.85, 0.95,
                 f"NOW: {current_price:{pfmt}}",
                 color=COLOR_CURRENT, fontsize=10, fontweight='bold')

        # Timestamp
        fig.text(0.01, 0.01,
                 f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")} | v2.0',
                 color='#555555', fontsize=8)

        # Save
        fig.savefig(str(filepath), dpi=130, bbox_inches='tight',
                    facecolor='#131722', edgecolor='none')
        plt.close(fig)

        return filepath

    except Exception as e:
        print(f"  [ERROR] {asset_name} {tf_name}: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================
# P2: FINNHUB PRICE VALIDATION
# ============================================================

def validate_prices(results):
    """Cross-check yfinance prices with Finnhub API."""
    print("\n--- Price Validation (Finnhub) ---")
    validations = {}

    for asset_name, asset_config in ASSETS.items():
        finnhub_sym = asset_config.get("finnhub_symbol")
        if not finnhub_sym:
            continue

        is_forex = asset_config.get("is_forex", False)
        finnhub_data = fetch_finnhub_price(finnhub_sym, is_forex=is_forex)
        if not finnhub_data:
            continue

        # Get yfinance price from the most recent chart
        yf_price = None
        for tf in ["5m", "4h", "daily"]:
            fpath = results.get(asset_name, {}).get(tf)
            if fpath:
                try:
                    df = yf.download(
                        asset_config["yf_symbol"],
                        period="1d", interval="5m", progress=False
                    )
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    if not df.empty:
                        yf_price = float(df['Close'].iloc[-1])
                        break
                except:
                    pass

        if yf_price and finnhub_data["current"]:
            diff = abs(yf_price - finnhub_data["current"])
            pct_diff = (diff / finnhub_data["current"]) * 100

            status = "OK" if pct_diff < 1.0 else "WARN" if pct_diff < 3.0 else "ERROR"
            print(f"  {asset_name}: yf={yf_price:,.2f} vs finnhub={finnhub_data['current']:,.2f} "
                  f"(diff={diff:,.2f}, {pct_diff:.2f}%) [{status}]")

            validations[asset_name] = {
                "yfinance": yf_price,
                "finnhub": finnhub_data["current"],
                "diff": diff,
                "pct_diff": pct_diff,
                "status": status,
            }

    return validations


# ============================================================
# DYNAMIC ASSET REGISTRATION (for opportunity scanner picks)
# ============================================================

# Stock/crypto assets that can be added dynamically
DYNAMIC_ASSETS = {
    "AAPL":  {"yf_symbol": "AAPL",    "display_name": "AAPL (Apple)",     "is_forex": False, "adr_typical": 3.0,   "price_fmt": ",.2f"},
    "TSLA":  {"yf_symbol": "TSLA",    "display_name": "TSLA (Tesla)",     "is_forex": False, "adr_typical": 10.0,  "price_fmt": ",.2f"},
    "NVDA":  {"yf_symbol": "NVDA",    "display_name": "NVDA (Nvidia)",    "is_forex": False, "adr_typical": 5.0,   "price_fmt": ",.2f"},
    "META":  {"yf_symbol": "META",    "display_name": "META (Meta)",      "is_forex": False, "adr_typical": 10.0,  "price_fmt": ",.2f"},
    "AMZN":  {"yf_symbol": "AMZN",    "display_name": "AMZN (Amazon)",    "is_forex": False, "adr_typical": 5.0,   "price_fmt": ",.2f"},
    "MSFT":  {"yf_symbol": "MSFT",    "display_name": "MSFT (Microsoft)", "is_forex": False, "adr_typical": 5.0,   "price_fmt": ",.2f"},
    "GOOGL": {"yf_symbol": "GOOGL",   "display_name": "GOOGL (Google)",   "is_forex": False, "adr_typical": 4.0,   "price_fmt": ",.2f"},
    "AMD":   {"yf_symbol": "AMD",     "display_name": "AMD",              "is_forex": False, "adr_typical": 5.0,   "price_fmt": ",.2f"},
    "INTC":  {"yf_symbol": "INTC",    "display_name": "INTC (Intel)",     "is_forex": False, "adr_typical": 1.0,   "price_fmt": ",.2f"},
    "COIN":  {"yf_symbol": "COIN",    "display_name": "COIN (Coinbase)",  "is_forex": False, "adr_typical": 10.0,  "price_fmt": ",.2f"},
    "PLTR":  {"yf_symbol": "PLTR",    "display_name": "PLTR (Palantir)",  "is_forex": False, "adr_typical": 2.0,   "price_fmt": ",.2f"},
    "SQ":    {"yf_symbol": "SQ",      "display_name": "SQ (Block)",       "is_forex": False, "adr_typical": 4.0,   "price_fmt": ",.2f"},
    "BTC":   {"yf_symbol": "BTC-USD", "display_name": "BTC (Bitcoin)",    "is_forex": False, "adr_typical": 2000,  "price_fmt": ",.0f"},
    "ETH":   {"yf_symbol": "ETH-USD", "display_name": "ETH (Ethereum)",   "is_forex": False, "adr_typical": 100,   "price_fmt": ",.2f"},
    "SOL":   {"yf_symbol": "SOL-USD", "display_name": "SOL (Solana)",     "is_forex": False, "adr_typical": 8.0,   "price_fmt": ",.2f"},
}


def register_asset(symbol):
    """Register a dynamic asset for chart generation."""
    if symbol in ASSETS:
        return  # Already registered
    if symbol in DYNAMIC_ASSETS:
        ASSETS[symbol] = DYNAMIC_ASSETS[symbol]
    else:
        print(f"  [WARN] Unknown asset: {symbol}")


# ============================================================
# MAIN
# ============================================================

def generate_all(asset_filter=None, validate=False):
    # Auto-register any filtered assets from DYNAMIC_ASSETS
    if asset_filter:
        for sym in asset_filter:
            register_asset(sym)
    """Generate charts for all (or filtered) assets."""
    results = {}
    total = 0
    errors = 0

    assets_to_process = {k: v for k, v in ASSETS.items()
                         if asset_filter is None or k in asset_filter}

    print(f"GOLD TACTIC Chart Generator v2.0")
    print(f"Generating charts for: {', '.join(assets_to_process.keys())}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Features: Asia Range, Sessions, PDH/PDL, RSI, ADR, Current Price")
    print()

    for asset_name, asset_config in assets_to_process.items():
        results[asset_name] = {}
        print(f"--- {asset_config['display_name']} ---")

        for tf_name, tf_config in TIMEFRAMES.items():
            path = generate_chart(asset_name, asset_config, tf_name, tf_config)
            if path:
                size_kb = os.path.getsize(path) / 1024
                print(f"  {tf_name}: OK ({size_kb:.0f} KB)")
                results[asset_name][tf_name] = str(path)
                total += 1
            else:
                print(f"  {tf_name}: FAILED")
                errors += 1

    # Write metadata
    meta = {
        "version": "2.0",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "assets": list(assets_to_process.keys()),
        "charts_generated": total,
        "errors": errors,
        "features": ["asia_range", "session_separators", "pdh_pdl",
                      "rsi", "adr_consumed", "current_price", "forex_volume_fix",
                      "4h_utc_alignment", "today_zoom_5m"],
        "files": results,
    }
    meta_path = OUTPUT_DIR / "charts_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2))

    ts_path = OUTPUT_DIR / "last_update.txt"
    ts_path.write_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    print(f"\nDone! {total} charts generated, {errors} errors.")

if __name__ == "__main__":
    import sys
    asset_filter = sys.argv[1:] if len(sys.argv) > 1 else None
    generate_all(asset_filter=asset_filter)