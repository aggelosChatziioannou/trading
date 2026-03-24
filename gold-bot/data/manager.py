"""Multi-timeframe data manager. Resamples 1-min data to higher timeframes."""
import pandas as pd


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample OHLCV data to a higher timeframe."""
    return df.resample(rule).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()


class DataManager:
    """Holds and manages multi-timeframe OHLCV data for Gold and optionally DXY."""

    def __init__(
        self,
        gold_1m: pd.DataFrame,
        dxy_1m: pd.DataFrame | None = None,
    ):
        self.gold_1m = gold_1m.sort_index()
        self.gold_5m = resample_ohlcv(gold_1m, "5min")
        self.gold_1h = resample_ohlcv(gold_1m, "1h")
        self.gold_4h = resample_ohlcv(gold_1m, "4h")

        self.dxy_1m = dxy_1m.sort_index() if dxy_1m is not None else None
        self.dxy_5m = resample_ohlcv(dxy_1m, "5min") if dxy_1m is not None else None

    def get_gold_slice(self, timeframe: str, end: pd.Timestamp, bars: int) -> pd.DataFrame:
        """Get the last N bars of gold data up to `end` for a given timeframe."""
        data = getattr(self, f"gold_{timeframe}")
        mask = data.index <= end
        return data[mask].tail(bars)

    def get_dxy_slice(self, end: pd.Timestamp, bars: int) -> pd.DataFrame | None:
        """Get the last N bars of DXY 5-min data up to `end`."""
        if self.dxy_5m is None:
            return None
        mask = self.dxy_5m.index <= end
        return self.dxy_5m[mask].tail(bars)
