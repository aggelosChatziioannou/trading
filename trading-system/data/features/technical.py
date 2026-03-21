"""
Stateless technical indicator calculator.

CRITICAL: Every method takes raw OHLCV data and returns features.
No internal state. No memory between calls. Pure functions.
This ensures CPCV folds are independent — features are recomputed
from raw data for each fold with zero information leakage.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import settings

_cfg = settings.features


class TechnicalFeatures:
    """
    Compute all technical features from raw OHLCV data.

    All methods are static — no instance state. Each takes a DataFrame
    with columns [open, high, low, close, volume] indexed by time.
    """

    @staticmethod
    def compute_all(ohlcv: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all technical features from raw OHLCV data.

        Args:
            ohlcv: DataFrame with columns: open, high, low, close, volume.
                   Must be sorted by time ascending.

        Returns:
            DataFrame with all technical feature columns.
            NaN rows at the start (lookback period) should be dropped by caller.
        """
        df = ohlcv.copy()
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"].astype(float)

        # --- RSI ---
        df["rsi_14"] = TechnicalFeatures._rsi(close, _cfg.rsi_period)

        # --- MACD ---
        ema_fast = close.ewm(span=_cfg.macd_fast, adjust=False).mean()
        ema_slow = close.ewm(span=_cfg.macd_slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=_cfg.macd_signal, adjust=False).mean()
        df["macd_signal"] = macd_line - signal_line
        df["macd_histogram"] = df["macd_signal"]  # Same as histogram by convention

        # --- Bollinger Bands ---
        sma_bb = close.rolling(_cfg.bb_period).mean()
        std_bb = close.rolling(_cfg.bb_period).std()
        upper_bb = sma_bb + _cfg.bb_std * std_bb
        lower_bb = sma_bb - _cfg.bb_std * std_bb
        bb_range = upper_bb - lower_bb
        df["bb_position"] = np.where(bb_range > 0, (close - lower_bb) / bb_range, 0.5)
        df["bb_width"] = np.where(sma_bb > 0, bb_range / sma_bb, 0.0)

        # --- ATR (Average True Range) ---
        df["atr_14"] = TechnicalFeatures._atr(high, low, close, _cfg.atr_period)
        atr_avg = df["atr_14"].rolling(20).mean()
        df["atr_ratio"] = np.where(atr_avg > 0, df["atr_14"] / atr_avg, 1.0)

        # --- OBV (On-Balance Volume) ---
        obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
        df["obv_slope"] = obv.rolling(_cfg.obv_slope_period).apply(
            lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) > 1 else 0.0,
            raw=False,
        )

        # --- VWAP Distance ---
        # Approximate VWAP using cumulative (price * volume) / cumulative volume
        # For daily data, this is a rolling VWAP proxy
        typical_price = (high + low + close) / 3.0
        cum_tp_vol = (typical_price * volume).rolling(20).sum()
        cum_vol = volume.rolling(20).sum()
        vwap = np.where(cum_vol > 0, cum_tp_vol / cum_vol, close)
        atr_safe = df["atr_14"].replace(0, np.nan)
        df["vwap_distance"] = (close - vwap) / atr_safe

        # --- Volume Ratio ---
        vol_avg = volume.rolling(_cfg.volume_avg_period).mean()
        df["volume_ratio"] = np.where(vol_avg > 0, volume / vol_avg, 1.0)

        # --- Rate of Change ---
        df["roc_5"] = close.pct_change(_cfg.roc_short) * 100
        df["roc_20"] = close.pct_change(_cfg.roc_long) * 100

        # --- ADX (Average Directional Index) ---
        df["adx_14"] = TechnicalFeatures._adx(high, low, close, _cfg.adx_period)

        # --- Stochastic ---
        lowest_low = low.rolling(_cfg.stoch_k_period).min()
        highest_high = high.rolling(_cfg.stoch_k_period).max()
        stoch_range = highest_high - lowest_low
        df["stoch_k"] = np.where(stoch_range > 0, 100 * (close - lowest_low) / stoch_range, 50.0)
        df["stoch_d"] = df["stoch_k"].rolling(_cfg.stoch_d_period).mean()

        # --- EMA Cross ---
        ema_9 = close.ewm(span=_cfg.ema_fast, adjust=False).mean()
        ema_21 = close.ewm(span=_cfg.ema_slow, adjust=False).mean()
        df["ema_cross"] = (ema_9 - ema_21) / atr_safe

        # --- Price vs SMAs ---
        sma_50 = close.rolling(_cfg.sma_medium).mean()
        sma_200 = close.rolling(_cfg.sma_long).mean()
        df["price_vs_sma50"] = (close - sma_50) / atr_safe
        df["price_vs_sma200"] = (close - sma_200) / atr_safe

        # --- Intraday Range ---
        df["high_low_range"] = (high - low) / atr_safe

        # --- Close Position within candle ---
        candle_range = high - low
        df["close_position"] = np.where(candle_range > 0, (close - low) / candle_range, 0.5)

        # --- Keltner Channel ---
        keltner_mid = close.ewm(span=_cfg.keltner_period, adjust=False).mean()
        keltner_atr = TechnicalFeatures._atr(high, low, close, _cfg.keltner_period)
        df["upper_keltner"] = keltner_mid + _cfg.keltner_atr_mult * keltner_atr
        df["lower_keltner"] = keltner_mid - _cfg.keltner_atr_mult * keltner_atr
        df["keltner_mid"] = keltner_mid

        # --- BB Width at 20-day low (squeeze detector) ---
        df["bb_squeeze"] = (
            df["bb_width"] == df["bb_width"].rolling(20).min()
        ).astype(float)

        return df

    @staticmethod
    def _rsi(series: pd.Series, period: int) -> pd.Series:
        """Relative Strength Index (Wilder's smoothed)."""
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """Average True Range."""
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    @staticmethod
    def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """Average Directional Index."""
        plus_dm = high.diff().clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)

        # Zero out the smaller DM
        plus_dm = np.where(plus_dm > minus_dm, plus_dm, 0.0)
        minus_dm = np.where(pd.Series(minus_dm) > pd.Series(plus_dm), minus_dm, 0.0)

        atr = TechnicalFeatures._atr(high, low, close, period)
        atr_safe = pd.Series(atr).replace(0, np.nan)

        plus_di = 100 * pd.Series(plus_dm).ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr_safe
        minus_di = 100 * pd.Series(minus_dm).ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr_safe

        di_sum = plus_di + minus_di
        dx = 100 * (plus_di - minus_di).abs() / di_sum.replace(0, np.nan)
        adx = dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        return adx
