"""
Sentiment score aggregator.

Combines FinBERT and Claude LLM scores using weighted average.
Weights: 40% FinBERT + 60% Claude (Claude has better contextual understanding).

This module is the single entry point for sentiment scoring —
it orchestrates both models and produces the final combined score.
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import settings
from sentiment.finbert_scorer import FinBERTScorer
from sentiment.llm_scorer import LLMScorer

logger = logging.getLogger(__name__)


class SentimentAggregator:
    """
    Orchestrate dual-model sentiment scoring pipeline.

    news_text → FinBERT (fast, local) → score_1
    news_text → Claude API (deeper understanding) → score_2
    combined_score = 0.4 * score_1 + 0.6 * score_2
    """

    def __init__(self, use_llm: bool = True) -> None:
        """
        Args:
            use_llm: If False, only use FinBERT (for testing or cost savings).
        """
        self._finbert = FinBERTScorer()
        self._llm = LLMScorer() if use_llm else None
        self._use_llm = use_llm

    def score_article(self, text: str, ticker: str) -> dict:
        """
        Score a single article using both models.

        Args:
            text: Article text (headline + body).
            ticker: Stock symbol for LLM context.

        Returns:
            Dict with:
                sentiment_finbert: float [-1, +1]
                sentiment_llm: float [-1, +1] or None
                sentiment_combined: float [-1, +1]
                confidence: float [0, 1]
                horizon: str
                reasoning: str
        """
        # FinBERT score
        finbert_result = self._finbert.score(text)
        finbert_score = finbert_result["score"]

        # LLM score (if enabled)
        llm_score = None
        llm_result: dict[str, Any] = {}
        if self._use_llm and self._llm is not None:
            llm_result = self._llm.score(text, ticker)
            llm_score = llm_result["score"]

        # Combined score
        if llm_score is not None:
            combined = (
                settings.sentiment.finbert_weight * finbert_score
                + settings.sentiment.llm_weight * llm_score
            )
            # Combined confidence: geometric mean of both models' confidence
            confidence = (finbert_result["confidence"] * llm_result["confidence"]) ** 0.5
        else:
            combined = finbert_score
            confidence = finbert_result["confidence"]

        return {
            "sentiment_finbert": round(finbert_score, 4),
            "sentiment_llm": round(llm_score, 4) if llm_score is not None else None,
            "sentiment_combined": round(combined, 4),
            "confidence": round(confidence, 4),
            "horizon": llm_result.get("horizon", "short"),
            "reasoning": llm_result.get("reasoning", finbert_result["label"]),
        }

    def score_articles(self, articles: list[dict]) -> list[dict]:
        """
        Score a batch of articles and update them in-place with sentiment fields.

        Args:
            articles: List of article dicts (from NewsFeed).
                     Each must have 'raw_text' or 'headline' and 'ticker'.

        Returns:
            Same list with sentiment fields filled in.
        """
        for article in articles:
            text = article.get("raw_text") or article.get("headline", "")
            ticker = article.get("ticker", "")

            if not text:
                logger.warning("Empty text for article: %s", article.get("headline", "unknown"))
                article["sentiment_finbert"] = 0.0
                article["sentiment_llm"] = 0.0
                article["sentiment_combined"] = 0.0
                continue

            result = self.score_article(text, ticker)
            article["sentiment_finbert"] = result["sentiment_finbert"]
            article["sentiment_llm"] = result["sentiment_llm"]
            article["sentiment_combined"] = result["sentiment_combined"]

        return articles
