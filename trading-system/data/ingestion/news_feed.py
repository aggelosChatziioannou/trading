"""
Multi-source news collection for sentiment analysis.

Sources:
1. Finnhub News API — company-specific financial news
2. Reddit via PRAW — r/wallstreetbets, r/stocks, r/investing
3. RSS feeds — Reuters, MarketWatch

Each article is scored by both FinBERT (fast, local) and Claude LLM
(deeper contextual understanding), then stored with combined score.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser
import finnhub
import praw

from config.settings import WATCHLIST, settings
from data.storage.timescale import TimescaleDB

logger = logging.getLogger(__name__)

UTC = timezone.utc


class NewsFeed:
    """
    Collect news from multiple sources and prepare for sentiment scoring.

    The sentiment scoring itself is delegated to the sentiment module.
    This class handles fetching, deduplication, and storage.
    """

    def __init__(self, db: TimescaleDB) -> None:
        self.db = db

        # Finnhub client
        self._finnhub: finnhub.Client | None = None
        if settings.api.finnhub_key:
            self._finnhub = finnhub.Client(api_key=settings.api.finnhub_key)

        # Reddit client
        self._reddit: praw.Reddit | None = None
        if settings.api.reddit_client_id and settings.api.reddit_client_secret:
            self._reddit = praw.Reddit(
                client_id=settings.api.reddit_client_id,
                client_secret=settings.api.reddit_client_secret,
                user_agent=settings.api.reddit_user_agent,
            )

    # =============================================================
    # Finnhub News
    # =============================================================

    def fetch_finnhub_news(
        self,
        ticker: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[dict]:
        """
        Fetch company-specific news from Finnhub.

        Args:
            ticker: Stock symbol.
            from_date: Start date (defaults to 7 days ago).
            to_date: End date (defaults to now).

        Returns:
            List of article dicts with keys: time, ticker, headline, source, url, raw_text.
        """
        if self._finnhub is None:
            logger.warning("Finnhub client not configured — skipping news fetch")
            return []

        if from_date is None:
            from_date = datetime.now(UTC) - timedelta(days=7)
        if to_date is None:
            to_date = datetime.now(UTC)

        try:
            news = self._finnhub.company_news(
                ticker,
                _from=from_date.strftime("%Y-%m-%d"),
                to=to_date.strftime("%Y-%m-%d"),
            )
        except Exception as e:
            logger.error("Finnhub news fetch failed for %s: %s", ticker, e)
            return []

        articles: list[dict] = []
        for item in news:
            articles.append({
                "time": datetime.fromtimestamp(item.get("datetime", 0), tz=UTC),
                "ticker": ticker,
                "headline": item.get("headline", ""),
                "source": item.get("source", "finnhub"),
                "url": item.get("url", ""),
                "raw_text": item.get("summary", ""),
                # Sentiment fields filled later by scorer
                "sentiment_finbert": None,
                "sentiment_llm": None,
                "sentiment_combined": None,
            })

        logger.info("Fetched %d articles from Finnhub for %s", len(articles), ticker)
        return articles

    def fetch_all_finnhub_news(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[dict]:
        """Fetch Finnhub news for all watchlist symbols."""
        all_articles: list[dict] = []
        for ticker in WATCHLIST:
            articles = self.fetch_finnhub_news(ticker, from_date, to_date)
            all_articles.extend(articles)
            # Rate limit: Finnhub free tier = 60 calls/min
            time.sleep(60 / settings.data.finnhub_rate_limit_per_min)
        return all_articles

    # =============================================================
    # Reddit (PRAW)
    # =============================================================

    def fetch_reddit_mentions(
        self,
        ticker: str,
        subreddits: tuple[str, ...] | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Fetch Reddit posts/comments mentioning the ticker.

        Args:
            ticker: Stock symbol to search for.
            subreddits: Subreddit names to search. Defaults to config.
            limit: Max posts to fetch per subreddit.

        Returns:
            List of article dicts.
        """
        if self._reddit is None:
            logger.warning("Reddit client not configured — skipping Reddit fetch")
            return []

        if subreddits is None:
            subreddits = settings.sentiment.reddit_subreddits

        articles: list[dict] = []

        for sub_name in subreddits:
            try:
                subreddit = self._reddit.subreddit(sub_name)
                # Search for ticker mentions in recent posts
                # Use $ prefix common in WSB, also search without it
                search_query = f"{ticker} OR ${ticker}"
                for post in subreddit.search(search_query, sort="new", limit=limit, time_filter="week"):
                    # Combine title and selftext for sentiment analysis
                    text = f"{post.title}. {post.selftext}" if post.selftext else post.title
                    articles.append({
                        "time": datetime.fromtimestamp(post.created_utc, tz=UTC),
                        "ticker": ticker,
                        "headline": post.title,
                        "source": f"reddit/{sub_name}",
                        "url": f"https://reddit.com{post.permalink}",
                        "raw_text": text[:5000],  # Cap text length
                        "sentiment_finbert": None,
                        "sentiment_llm": None,
                        "sentiment_combined": None,
                    })
            except Exception as e:
                logger.error("Reddit fetch failed for r/%s ticker %s: %s", sub_name, ticker, e)

        logger.info("Fetched %d Reddit mentions for %s", len(articles), ticker)
        return articles

    # =============================================================
    # RSS Feeds
    # =============================================================

    def fetch_rss_feeds(self, ticker: str | None = None) -> list[dict]:
        """
        Fetch and parse RSS feeds from configured financial news sources.

        Args:
            ticker: If provided, only keep articles mentioning this ticker.
                   If None, return all articles.

        Returns:
            List of article dicts.
        """
        articles: list[dict] = []

        for feed_url in settings.sentiment.rss_feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    # Parse published time
                    pub_time = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub_time = datetime(*entry.published_parsed[:6], tzinfo=UTC)
                    else:
                        pub_time = datetime.now(UTC)

                    headline = entry.get("title", "")
                    summary = entry.get("summary", "")
                    text = f"{headline}. {summary}"

                    # If ticker filter is set, check if article mentions it
                    if ticker and ticker.upper() not in text.upper():
                        continue

                    # Try to identify the ticker from the text
                    matched_ticker = ticker
                    if matched_ticker is None:
                        matched_ticker = self._extract_ticker(text)

                    articles.append({
                        "time": pub_time,
                        "ticker": matched_ticker,
                        "headline": headline,
                        "source": feed_url.split("/")[2] if "/" in feed_url else "rss",
                        "url": entry.get("link", ""),
                        "raw_text": text[:5000],
                        "sentiment_finbert": None,
                        "sentiment_llm": None,
                        "sentiment_combined": None,
                    })
            except Exception as e:
                logger.error("RSS fetch failed for %s: %s", feed_url, e)

        logger.info("Fetched %d RSS articles", len(articles))
        return articles

    def _extract_ticker(self, text: str) -> str | None:
        """
        Try to identify which watchlist ticker an article is about.

        Simple approach: check if any watchlist ticker appears in the text.
        Returns the first match or None.
        """
        text_upper = text.upper()
        for ticker in WATCHLIST:
            # Look for ticker as a whole word (avoid matching substrings)
            if f" {ticker} " in f" {text_upper} ":
                return ticker
        return None

    # =============================================================
    # Batch Operations
    # =============================================================

    def fetch_all_sources(
        self,
        ticker: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[dict]:
        """
        Fetch news from all sources for a single ticker.

        Returns combined, deduplicated list of articles.
        """
        articles: list[dict] = []

        # Finnhub
        articles.extend(self.fetch_finnhub_news(ticker, from_date, to_date))

        # Reddit
        articles.extend(self.fetch_reddit_mentions(ticker))

        # RSS
        articles.extend(self.fetch_rss_feeds(ticker))

        # Deduplicate by headline similarity (exact match only for simplicity)
        seen_headlines: set[str] = set()
        unique: list[dict] = []
        for article in articles:
            headline_key = article["headline"].lower().strip()
            if headline_key not in seen_headlines:
                seen_headlines.add(headline_key)
                unique.append(article)

        logger.info("Total unique articles for %s: %d (from %d raw)", ticker, len(unique), len(articles))
        return unique

    def store_articles(self, articles: list[dict]) -> int:
        """
        Store articles in the database.

        Articles should already have sentiment scores filled in.

        Returns:
            Number of articles stored.
        """
        return self.db.insert_news(articles)
