"""Download XAUUSD and DXY data from yfinance."""
import pandas as pd
import yfinance as yf


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase columns, handle MultiIndex from newer yfinance, drop Adj Close."""
    # yfinance >= 0.2.31 returns MultiIndex columns for single ticker
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    df = df.drop(columns=["adj_close"], errors="ignore")
    return df


def download_gold(period: str = "7d", interval: str = "1m") -> pd.DataFrame:
    """Download Gold futures (GC=F) data."""
    df = yf.download("GC=F", period=period, interval=interval, progress=False)
    df = _normalize_columns(df)
    return df


def download_dxy(period: str = "7d", interval: str = "1m") -> pd.DataFrame:
    """Download Dollar Index (DX-Y.NYB) data."""
    df = yf.download("DX-Y.NYB", period=period, interval=interval, progress=False)
    df = _normalize_columns(df)
    return df


def load_csv(filepath: str) -> pd.DataFrame:
    """Load OHLCV data from CSV.

    Expected columns: datetime (or date), open, high, low, close, volume (optional).
    Handles MT5, TradingView, and generic CSV exports.
    """
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
