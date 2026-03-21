"""
Feature matrix builder.

Orchestrates feature computation from raw data. Combines technical
indicators, sentiment features, and cross-features into a single
feature matrix.

IMPORTANT: This class is called fresh for every CPCV fold.
No state is carried over between calls. Pure function composition.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from data.features.sentiment import SentimentFeatures
from data.features.technical import TechnicalFeatures


class FeatureBuilder:
    """
    Build the complete feature matrix from raw data.

    Takes RAW OHLCV + news data and produces a feature DataFrame.
    Stateless — called fresh for every CPCV fold.
    """

    @staticmethod
    def build(
        ohlcv_df: pd.DataFrame,
        news_df: pd.DataFrame,
        as_of_times: pd.DatetimeIndex | None = None,
    ) -> pd.DataFrame:
        """
        Build complete feature matrix for a time series.

        Args:
            ohlcv_df: Raw OHLCV data (columns: open, high, low, close, volume).
                     Indexed by time, sorted ascending.
            news_df: News data (columns: time, sentiment_combined, source).
            as_of_times: Times at which to compute features.
                        Defaults to ohlcv_df index.

        Returns:
            DataFrame with all features, indexed by time.
            Rows with NaN (from lookback periods) are dropped.
        """
        # Step 1: Technical features from raw OHLCV
        tech_features = TechnicalFeatures.compute_all(ohlcv_df)

        # Step 2: Sentiment features at each time point
        if as_of_times is None:
            as_of_times = ohlcv_df.index

        sent_rows: list[dict] = []
        for t in as_of_times:
            if t.tzinfo is None:
                t_aware = t.replace(tzinfo=timezone.utc)
            else:
                t_aware = t
            sent_feat = SentimentFeatures.compute_all(news_df, t_aware)
            sent_rows.append(sent_feat)

        sent_features = pd.DataFrame(sent_rows, index=as_of_times)

        # Step 3: Merge technical + sentiment
        combined = tech_features.join(sent_features, how="left")

        # Step 4: Cross-features (interactions between price and sentiment)
        combined = FeatureBuilder._add_cross_features(combined)

        # Step 5: Drop rows with NaN from lookback periods
        # Keep track of which columns had NaN to avoid silently losing data
        feature_cols = [c for c in combined.columns if c not in ("open", "high", "low", "close", "volume")]
        combined_features = combined[feature_cols].dropna()

        return combined_features

    @staticmethod
    def build_single(
        ohlcv_df: pd.DataFrame,
        news_df: pd.DataFrame,
        as_of_time: datetime,
    ) -> dict[str, float]:
        """
        Build feature vector for a single point in time.

        Useful for real-time signal generation.

        Args:
            ohlcv_df: Historical OHLCV up to (and including) as_of_time.
            news_df: News data up to as_of_time.
            as_of_time: The point in time for feature computation.

        Returns:
            Dict of feature name -> value.
        """
        feature_df = FeatureBuilder.build(ohlcv_df, news_df, pd.DatetimeIndex([as_of_time]))
        if feature_df.empty:
            return {}
        return feature_df.iloc[-1].to_dict()

    @staticmethod
    def _add_cross_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute cross-features that capture interactions between
        price action and sentiment.

        These features are where the system's edge may come from —
        they represent information that neither price nor sentiment
        alone can capture.
        """
        # Price-Sentiment Divergence:
        # Price going up (positive roc) but sentiment going down (negative momentum), or vice versa.
        # Divergence suggests the narrative is shifting before price catches up.
        if "roc_5" in df.columns and "sent_momentum" in df.columns:
            roc_norm = df["roc_5"] / df["roc_5"].rolling(20).std().replace(0, np.nan)
            sent_norm = df["sent_momentum"] / 0.3  # Normalize: 0.3 is a significant momentum shift
            df["price_sent_divergence"] = roc_norm.fillna(0) - sent_norm.fillna(0)

        # Volume-Sentiment Confirmation:
        # High volume + strong sentiment in same direction = high conviction move.
        # Score is high when volume and sentiment agree, low when they disagree.
        if "volume_ratio" in df.columns and "sent_24h" in df.columns:
            vol_signal = (df["volume_ratio"] - 1.0).clip(lower=0)  # Excess volume
            df["volume_sent_confirmation"] = vol_signal * df["sent_24h"]

        # Volatility-Sentiment Regime:
        # High volatility + negative sentiment = fear regime.
        # This is useful for regime-aware position sizing.
        if "atr_ratio" in df.columns and "sent_24h" in df.columns:
            df["volatility_sent_regime"] = df["atr_ratio"] * (-df["sent_24h"])

        # Momentum-Sentiment Alignment:
        # Price momentum and sentiment trend moving together = continuation likely.
        # Moving apart = potential reversal.
        if "roc_20" in df.columns and "sent_7d" in df.columns:
            df["momentum_sent_alignment"] = np.sign(df["roc_20"]) * np.sign(df["sent_7d"])

        return df

    @staticmethod
    def get_feature_names() -> list[str]:
        """Return list of all feature names produced by the builder."""
        # Technical features
        tech = [
            "rsi_14", "macd_signal", "macd_histogram",
            "bb_position", "bb_width",
            "atr_14", "atr_ratio",
            "obv_slope", "vwap_distance", "volume_ratio",
            "roc_5", "roc_20",
            "adx_14", "stoch_k", "stoch_d",
            "ema_cross", "price_vs_sma50", "price_vs_sma200",
            "high_low_range", "close_position",
            "upper_keltner", "lower_keltner", "keltner_mid",
            "bb_squeeze",
        ]
        # Sentiment features
        sent = [
            "sent_4h", "sent_24h", "sent_7d",
            "sent_momentum", "sent_volume_4h", "sent_volume_24h",
            "sent_dispersion", "sent_extreme", "sent_source_agreement",
        ]
        # Cross features
        cross = [
            "price_sent_divergence", "volume_sent_confirmation",
            "volatility_sent_regime", "momentum_sent_alignment",
        ]
        return tech + sent + cross
