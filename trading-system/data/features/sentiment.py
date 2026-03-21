"""
Aggregate sentiment scores into time-windowed features.

CRITICAL: Sentiment features must only use NEWS AVAILABLE AT THAT TIME.
A feature at time T can only use news published BEFORE time T.
This is verified by test_no_leakage.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from config.settings import settings

_cfg = settings.features


class SentimentFeatures:
    """
    Compute sentiment features from news data.

    All methods are stateless — they take raw news data and a reference time,
    and return features using only data strictly before that time.
    """

    @staticmethod
    def compute_all(news_df: pd.DataFrame, as_of_time: datetime) -> dict[str, float]:
        """
        Compute sentiment features using only news available before as_of_time.

        ANTI-LEAKAGE: Filters news_df to only rows where time < as_of_time.
        This is the primary guard against future data leakage in sentiment.

        Args:
            news_df: DataFrame with columns: time, sentiment_combined, source.
                    'time' must be timezone-aware (UTC).
            as_of_time: Reference point. Only news BEFORE this time is used.

        Returns:
            Dict of sentiment features.
        """
        if news_df.empty:
            return SentimentFeatures._empty_features()

        # CRITICAL: Only use news published BEFORE as_of_time
        if as_of_time.tzinfo is None:
            as_of_time = as_of_time.replace(tzinfo=timezone.utc)

        news_times = news_df["time"]
        if news_times.dt.tz is None:
            news_times = news_times.dt.tz_localize(timezone.utc)

        available = news_df[news_times < as_of_time].copy()

        if available.empty:
            return SentimentFeatures._empty_features()

        sent = available["sentiment_combined"].astype(float)
        times = available["time"]

        # Time windows
        t_4h = as_of_time - timedelta(hours=_cfg.sentiment_short_hours)
        t_24h = as_of_time - timedelta(hours=_cfg.sentiment_medium_hours)
        t_7d = as_of_time - timedelta(days=_cfg.sentiment_long_days)

        mask_4h = times >= t_4h
        mask_24h = times >= t_24h
        mask_7d = times >= t_7d

        sent_4h = sent[mask_4h]
        sent_24h = sent[mask_24h]
        sent_7d = sent[mask_7d]

        # Average sentiment per window
        avg_4h = sent_4h.mean() if len(sent_4h) > 0 else 0.0
        avg_24h = sent_24h.mean() if len(sent_24h) > 0 else 0.0
        avg_7d = sent_7d.mean() if len(sent_7d) > 0 else 0.0

        # Sentiment momentum: short-term vs long-term
        sent_momentum = avg_4h - avg_7d

        # Article volume (proxy for event significance)
        vol_4h = len(sent_4h)
        vol_24h = len(sent_24h)

        # Sentiment dispersion: disagreement among recent articles
        dispersion = sent_24h.std() if len(sent_24h) > 1 else 0.0

        # Extreme sentiment flag
        extreme = 1.0 if (sent_4h.abs() > 0.8).any() else 0.0

        # Source agreement: do different sources agree on sentiment direction?
        source_agreement = SentimentFeatures._source_agreement(available, mask_24h)

        return {
            "sent_4h": round(float(avg_4h), 4),
            "sent_24h": round(float(avg_24h), 4),
            "sent_7d": round(float(avg_7d), 4),
            "sent_momentum": round(float(sent_momentum), 4),
            "sent_volume_4h": float(vol_4h),
            "sent_volume_24h": float(vol_24h),
            "sent_dispersion": round(float(dispersion), 4),
            "sent_extreme": float(extreme),
            "sent_source_agreement": round(float(source_agreement), 4),
        }

    @staticmethod
    def _source_agreement(news_df: pd.DataFrame, time_mask: pd.Series) -> float:
        """
        Calculate agreement across different news sources.

        Returns value in [0, 1] where:
        1.0 = all sources agree on direction
        0.0 = sources completely disagree
        """
        recent = news_df[time_mask]
        if "source" not in recent.columns or len(recent) < 2:
            return 0.5  # Insufficient data, return neutral

        # Group by source and get average sentiment direction
        source_means = recent.groupby("source")["sentiment_combined"].mean()

        if len(source_means) < 2:
            return 0.5

        # Agreement = fraction of sources that agree on the sign
        signs = np.sign(source_means)
        if len(signs) == 0:
            return 0.5

        majority_sign = np.sign(signs.sum())
        if majority_sign == 0:
            return 0.0  # Perfect disagreement

        agreement = (signs == majority_sign).mean()
        return float(agreement)

    @staticmethod
    def _empty_features() -> dict[str, float]:
        """Return zero-valued features when no news is available."""
        return {
            "sent_4h": 0.0,
            "sent_24h": 0.0,
            "sent_7d": 0.0,
            "sent_momentum": 0.0,
            "sent_volume_4h": 0.0,
            "sent_volume_24h": 0.0,
            "sent_dispersion": 0.0,
            "sent_extreme": 0.0,
            "sent_source_agreement": 0.5,
        }
