"""Multi-timeframe data manager.

Accepts data at any base resolution and resamples up.
For 6-month backtests, the base might be 5m or 1h depending on data availability.
"""
import pandas as pd


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample OHLCV data to a higher timeframe."""
    if df.empty:
        return df
    return df.resample(rule).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()


class DataManager:
    """Holds multi-timeframe OHLCV data for Gold and optionally DXY.

    Supports flexible initialization from any combination of timeframes.
    The strategy uses 5m as primary entry timeframe, with 1h/4h for HTF bias.
    """

    def __init__(
        self,
        gold_data: dict[str, pd.DataFrame] | None = None,
        dxy_data: dict[str, pd.DataFrame] | None = None,
        gold_1m: pd.DataFrame | None = None,
        dxy_1m: pd.DataFrame | None = None,
    ):
        # Support both old interface (gold_1m) and new (gold_data dict)
        if gold_data is not None:
            self._init_from_dict(gold_data, dxy_data or {})
        elif gold_1m is not None:
            self._init_from_1m(gold_1m, dxy_1m)
        else:
            raise ValueError("Provide either gold_data dict or gold_1m DataFrame")

    def _init_from_1m(self, gold_1m: pd.DataFrame, dxy_1m: pd.DataFrame | None):
        """Initialize from 1-min base data (original interface)."""
        self.gold_1m = gold_1m.sort_index()
        self.gold_5m = resample_ohlcv(gold_1m, "5min")
        self.gold_15m = resample_ohlcv(gold_1m, "15min")
        self.gold_1h = resample_ohlcv(gold_1m, "1h")
        self.gold_4h = resample_ohlcv(gold_1m, "4h")
        self.gold_1d = resample_ohlcv(gold_1m, "1D")
        self.base_tf = "1m"

        self.dxy_1m = dxy_1m.sort_index() if dxy_1m is not None else None
        self.dxy_5m = resample_ohlcv(dxy_1m, "5min") if dxy_1m is not None else None
        self.dxy_1h = resample_ohlcv(dxy_1m, "1h") if dxy_1m is not None else None

    def _init_from_dict(self, gold: dict[str, pd.DataFrame], dxy: dict[str, pd.DataFrame]):
        """Initialize from dictionary of {timeframe: DataFrame}.

        Uses the finest available resolution as base and resamples up.
        """
        # Determine finest available gold data
        for tf in ["1m", "5m", "15m", "1h"]:
            if tf in gold and not gold[tf].empty:
                self.base_tf = tf
                break
        else:
            raise ValueError("No valid gold data provided")

        # Store what we have directly
        self.gold_1m = gold.get("1m", pd.DataFrame()).sort_index() if "1m" in gold else pd.DataFrame()
        self.gold_5m = gold.get("5m", pd.DataFrame()).sort_index() if "5m" in gold else pd.DataFrame()
        self.gold_15m = pd.DataFrame()
        self.gold_1h = gold.get("1h", pd.DataFrame()).sort_index() if "1h" in gold else pd.DataFrame()
        self.gold_4h = pd.DataFrame()
        self.gold_1d = pd.DataFrame()

        # Resample up from finest available
        base = gold[self.base_tf].sort_index()
        if self.base_tf == "1m":
            if self.gold_5m.empty:
                self.gold_5m = resample_ohlcv(base, "5min")
            if self.gold_1h.empty:
                self.gold_1h = resample_ohlcv(base, "1h")
        if self.base_tf in ("1m", "5m"):
            if self.gold_15m.empty and not base.empty:
                src = gold.get("5m", base) if self.base_tf == "5m" else base
                self.gold_15m = resample_ohlcv(src, "15min") if self.base_tf == "1m" else resample_ohlcv(src, "15min")
            if self.gold_1h.empty:
                self.gold_1h = resample_ohlcv(base, "1h")

        # Always need 4h and 1d - resample from 1h if available
        src_1h = self.gold_1h if not self.gold_1h.empty else resample_ohlcv(base, "1h")
        if self.gold_4h.empty and not src_1h.empty:
            self.gold_4h = resample_ohlcv(src_1h, "4h")
        if self.gold_1d.empty and not src_1h.empty:
            self.gold_1d = resample_ohlcv(src_1h, "1D")

        # For the 6-month backtest with only 1h data available:
        # If we don't have 5m but have 1h, the entry_model will adapt
        # by using 1h as the entry timeframe
        if self.gold_5m.empty and not self.gold_1h.empty:
            # Use 1h as proxy for entries when 5m not available
            self.gold_5m = self.gold_1h

        # DXY data
        self.dxy_1m = dxy.get("1m", pd.DataFrame()) if "1m" in dxy else pd.DataFrame()
        self.dxy_5m = dxy.get("5m", pd.DataFrame()) if "5m" in dxy else pd.DataFrame()
        self.dxy_1h = dxy.get("1h", pd.DataFrame()) if "1h" in dxy else pd.DataFrame()

        # Resample DXY if needed
        if self.dxy_5m.empty and not self.dxy_1m.empty:
            self.dxy_5m = resample_ohlcv(self.dxy_1m, "5min")
        if self.dxy_1h.empty and not self.dxy_5m.empty:
            self.dxy_1h = resample_ohlcv(self.dxy_5m, "1h")
        # If only 1h DXY available, use it for 5m SMT too (coarser but still useful)
        if self.dxy_5m.empty and not self.dxy_1h.empty:
            self.dxy_5m = self.dxy_1h

    @property
    def primary_tf(self) -> pd.DataFrame:
        """The primary entry timeframe data (5m preferred, 1h fallback)."""
        if not self.gold_5m.empty:
            return self.gold_5m
        return self.gold_1h

    @property
    def has_dxy(self) -> bool:
        return not self.dxy_5m.empty if isinstance(self.dxy_5m, pd.DataFrame) else self.dxy_5m is not None

    def get_gold_slice(self, timeframe: str, end, bars: int) -> pd.DataFrame:
        data = getattr(self, f"gold_{timeframe}", pd.DataFrame())
        if isinstance(data, pd.DataFrame) and not data.empty:
            mask = data.index <= end
            return data[mask].tail(bars)
        return pd.DataFrame()

    def get_dxy_slice(self, timeframe: str, end, bars: int) -> pd.DataFrame:
        data = getattr(self, f"dxy_{timeframe}", pd.DataFrame())
        if isinstance(data, pd.DataFrame) and not data.empty:
            mask = data.index <= end
            return data[mask].tail(bars)
        return pd.DataFrame()
