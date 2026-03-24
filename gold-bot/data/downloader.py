"""Download XAUUSD and DXY data from yfinance with multi-interval strategy.

yfinance limits:
  1m  -> max 7 days
  5m  -> max 60 days
  15m -> max 60 days
  1h  -> max 730 days
  1d  -> unlimited

Strategy: download the finest available resolution for each period,
then stitch together into a unified dataset.
"""
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    df = df.drop(columns=["adj_close"], errors="ignore")
    return df


def _download_yf(ticker: str, period: str = None, interval: str = "1h",
                  start: str = None, end: str = None) -> pd.DataFrame:
    """Download from yfinance with error handling."""
    try:
        kwargs = {"progress": False, "interval": interval}
        if start and end:
            kwargs["start"] = start
            kwargs["end"] = end
        else:
            kwargs["period"] = period or "7d"
        df = yf.download(ticker, **kwargs)
        if df.empty:
            return pd.DataFrame()
        df = _normalize_columns(df)
        return df
    except Exception as e:
        print(f"  Warning: yfinance download failed for {ticker} ({interval}): {e}")
        return pd.DataFrame()


def download_gold_multi_tf(months: int = 6) -> dict[str, pd.DataFrame]:
    """Download Gold futures data at multiple timeframes.

    Returns dict with keys: '1h', '5m' (if available), '1m' (if available).
    The 1h data covers the full period; 5m/1m cover their max available windows.
    """
    end = datetime.now()
    start_full = end - timedelta(days=months * 31)

    result = {}

    # 1H data - full period (up to 730 days)
    print(f"  Downloading GC=F 1h data ({months} months)...")
    df_1h = _download_yf("GC=F", start=start_full.strftime("%Y-%m-%d"),
                          end=end.strftime("%Y-%m-%d"), interval="1h")
    if not df_1h.empty:
        result["1h"] = df_1h
        print(f"    1h: {len(df_1h)} bars ({df_1h.index[0]} to {df_1h.index[-1]})")

    # 5M data - max 60 days
    print("  Downloading GC=F 5m data (last 60 days)...")
    df_5m = _download_yf("GC=F", period="60d", interval="5m")
    if not df_5m.empty:
        result["5m"] = df_5m
        print(f"    5m: {len(df_5m)} bars ({df_5m.index[0]} to {df_5m.index[-1]})")

    # 1M data - max 7 days
    print("  Downloading GC=F 1m data (last 7 days)...")
    df_1m = _download_yf("GC=F", period="7d", interval="1m")
    if not df_1m.empty:
        result["1m"] = df_1m
        print(f"    1m: {len(df_1m)} bars ({df_1m.index[0]} to {df_1m.index[-1]})")

    return result


def download_dxy_multi_tf(months: int = 6) -> dict[str, pd.DataFrame]:
    """Download DXY data at multiple timeframes for SMT divergence."""
    end = datetime.now()
    start_full = end - timedelta(days=months * 31)
    result = {}

    print(f"  Downloading DX-Y.NYB 1h data ({months} months)...")
    df_1h = _download_yf("DX-Y.NYB", start=start_full.strftime("%Y-%m-%d"),
                          end=end.strftime("%Y-%m-%d"), interval="1h")
    if not df_1h.empty:
        result["1h"] = df_1h
        print(f"    1h: {len(df_1h)} bars")

    print("  Downloading DX-Y.NYB 5m data (last 60 days)...")
    df_5m = _download_yf("DX-Y.NYB", period="60d", interval="5m")
    if not df_5m.empty:
        result["5m"] = df_5m
        print(f"    5m: {len(df_5m)} bars")

    return result


def load_csv(filepath: str) -> pd.DataFrame:
    """Load OHLCV data from CSV (MT5, TradingView, or generic format)."""
    df = pd.read_csv(filepath, parse_dates=True, index_col=0)
    df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]
    for col in ["open", "high", "low", "close"]:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    if "volume" not in df.columns:
        df["volume"] = 0
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    return df
