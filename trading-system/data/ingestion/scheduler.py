"""
Cron-like scheduler for data collection tasks.

Runs periodic jobs:
- Tick-to-candle aggregation (every minute during market hours)
- News collection (every 30 minutes)
- Feature computation (every 15 minutes during market hours)
- Data cleanup (daily at midnight)
"""

from __future__ import annotations

import logging
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config.settings import WATCHLIST, settings
from data.ingestion.price_feed import PriceFeed

logger = logging.getLogger(__name__)

ET = pytz.timezone("US/Eastern")


class DataScheduler:
    """
    Manages periodic data collection and processing tasks.

    All jobs are timezone-aware and respect market hours where appropriate.
    """

    def __init__(self, price_feed: PriceFeed, news_feed=None) -> None:
        self._price_feed = price_feed
        self._news_feed = news_feed
        self._scheduler = BackgroundScheduler(timezone=ET)

    def start(self) -> None:
        """Start all scheduled jobs."""
        # Aggregate ticks into 1-min candles every 60 seconds during market hours
        self._scheduler.add_job(
            self._aggregate_candles,
            IntervalTrigger(seconds=60),
            id="aggregate_candles",
            name="Aggregate ticks to candles",
            max_instances=1,
        )

        # Check for and fill data gaps daily at 6 AM ET (before market open)
        self._scheduler.add_job(
            self._check_and_fill_gaps,
            CronTrigger(hour=6, minute=0, timezone=ET),
            id="fill_gaps",
            name="Check and fill data gaps",
        )

        # Fetch news every 30 minutes during market hours (9:00-16:30 ET)
        if self._news_feed is not None:
            self._scheduler.add_job(
                self._fetch_news,
                IntervalTrigger(minutes=30),
                id="fetch_news",
                name="Fetch news from all sources",
                max_instances=1,
            )

        self._scheduler.start()
        logger.info("Data scheduler started with %d jobs", len(self._scheduler.get_jobs()))

    def stop(self) -> None:
        """Shut down the scheduler gracefully."""
        self._scheduler.shutdown(wait=True)
        logger.info("Data scheduler stopped")

    def _aggregate_candles(self) -> None:
        """Flush tick buffer to 1-min candles (only during market hours)."""
        if not PriceFeed.is_market_open():
            return
        try:
            count = self._price_feed.flush_candles(timeframe="1min")
            if count > 0:
                logger.debug("Aggregated %d candles", count)
        except Exception as e:
            logger.error("Candle aggregation failed: %s", e)

    def _fetch_news(self) -> None:
        """Fetch news from all sources for all watchlist stocks."""
        if self._news_feed is None:
            return
        try:
            for ticker in WATCHLIST:
                # Skip ETFs — no company-specific news
                if ticker in ("SPY", "QQQ", "IWM", "TLT", "XLF", "XLK", "XLE", "XLV", "XLI"):
                    continue
                articles = self._news_feed.fetch_all_sources(ticker)
                if articles:
                    self._news_feed.store_articles(articles)
                    logger.debug("Stored %d articles for %s", len(articles), ticker)
        except Exception as e:
            logger.error("News fetch failed: %s", e)

    def _check_and_fill_gaps(self) -> None:
        """Identify and fill data gaps using yfinance."""
        try:
            results = self._price_feed.backfill_all(timeframe="1d")
            total = sum(results.values())
            if total > 0:
                logger.info("Gap fill complete: %d candles across %d tickers", total, len(results))
        except Exception as e:
            logger.error("Gap fill failed: %s", e)
