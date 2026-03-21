"""
Claude API-based sentiment scoring.

Uses Claude (Haiku for speed/cost) to deeply analyze financial news.
More nuanced than FinBERT — understands context, sarcasm, and implications.
Returns structured JSON with score, confidence, time horizon, and reasoning.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import anthropic

from config.settings import settings

logger = logging.getLogger(__name__)

# Structured prompt for consistent, parseable output
_SENTIMENT_PROMPT = """You are a financial sentiment analyst. Analyze the following news article about {ticker}.

Rate the sentiment on a scale from -1.0 to +1.0 where:
- -1.0 = extremely bearish (company facing existential threat, fraud, bankruptcy)
- -0.5 = moderately bearish (earnings miss, downgrades, negative guidance)
- 0.0 = neutral (routine announcements, no clear directional impact)
- +0.5 = moderately bullish (earnings beat, upgrades, positive guidance)
- +1.0 = extremely bullish (transformative deal, breakthrough product, major contract win)

Consider:
1. Direct impact on {ticker}'s revenue/earnings
2. Industry/competitive implications
3. Time horizon of the impact (today vs months)
4. Market's likely reaction vs actual fundamental impact

Article: {text}

Respond ONLY with JSON: {{"score": float, "confidence": float, "horizon": "short|medium|long", "reasoning": "one sentence"}}"""


class LLMScorer:
    """
    Score financial text sentiment using the Claude API.

    Includes retry logic with exponential backoff for API errors.
    Rate-limited to respect API quotas.
    """

    def __init__(self) -> None:
        self._client: anthropic.Anthropic | None = None

    def _get_client(self) -> anthropic.Anthropic:
        """Lazy-initialize the Anthropic client."""
        if self._client is None:
            if not settings.api.anthropic_key:
                raise RuntimeError("ANTHROPIC_API_KEY not set")
            self._client = anthropic.Anthropic(api_key=settings.api.anthropic_key)
        return self._client

    def score(self, text: str, ticker: str) -> dict:
        """
        Score a single article using Claude.

        Args:
            text: News article text (headline + body).
            ticker: Stock symbol for context.

        Returns:
            Dict with:
                score: float in [-1, +1]
                confidence: float in [0, 1]
                horizon: 'short', 'medium', or 'long'
                reasoning: str
        """
        prompt = _SENTIMENT_PROMPT.format(ticker=ticker, text=text[:3000])

        # Retry with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                client = self._get_client()
                response = client.messages.create(
                    model=settings.sentiment.llm_model,
                    max_tokens=settings.sentiment.llm_max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )

                # Parse JSON response
                content = response.content[0].text.strip()
                result = json.loads(content)

                # Validate and clamp values
                score = max(-1.0, min(1.0, float(result.get("score", 0.0))))
                confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
                horizon = result.get("horizon", "short")
                if horizon not in ("short", "medium", "long"):
                    horizon = "short"
                reasoning = str(result.get("reasoning", ""))

                return {
                    "score": round(score, 4),
                    "confidence": round(confidence, 4),
                    "horizon": horizon,
                    "reasoning": reasoning,
                }

            except json.JSONDecodeError as e:
                logger.warning("LLM returned non-JSON response (attempt %d): %s", attempt + 1, e)
            except anthropic.RateLimitError:
                wait_time = 2 ** (attempt + 1)
                logger.warning("Rate limited, waiting %ds", wait_time)
                time.sleep(wait_time)
            except anthropic.APIError as e:
                wait_time = 2 ** (attempt + 1)
                logger.error("API error (attempt %d): %s", attempt + 1, e)
                time.sleep(wait_time)
            except Exception as e:
                logger.error("Unexpected error scoring sentiment: %s", e)
                break

        # Return neutral on failure
        logger.warning("All LLM scoring attempts failed for %s, returning neutral", ticker)
        return {
            "score": 0.0,
            "confidence": 0.0,
            "horizon": "short",
            "reasoning": "scoring_failed",
        }
