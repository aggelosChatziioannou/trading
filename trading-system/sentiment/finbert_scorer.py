"""
FinBERT-based sentiment scoring.

Uses ProsusAI/finbert — a BERT model fine-tuned on financial text.
Fast local inference, good for bulk scoring. Less nuanced than LLM
but consistent and reproducible.

Output: score in [-1, +1] where:
  -1 = strongly negative
   0 = neutral
  +1 = strongly positive
"""

from __future__ import annotations

import logging
from typing import Any

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from config.settings import settings

logger = logging.getLogger(__name__)


class FinBERTScorer:
    """
    Score financial text sentiment using FinBERT.

    Lazy-loads the model on first call to avoid slow imports.
    Thread-safe for concurrent scoring.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._tokenizer: Any = None
        self._device: str = "cuda" if torch.cuda.is_available() else "cpu"

    def _load_model(self) -> None:
        """Load FinBERT model and tokenizer."""
        if self._model is not None:
            return

        model_name = settings.sentiment.finbert_model
        logger.info("Loading FinBERT model: %s (device: %s)", model_name, self._device)

        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self._model.to(self._device)
        self._model.eval()

        logger.info("FinBERT model loaded")

    def score(self, text: str) -> dict:
        """
        Score a single text for financial sentiment.

        Args:
            text: Financial news text (headline + body).

        Returns:
            Dict with:
                score: float in [-1, +1]
                confidence: float in [0, 1]
                label: 'positive', 'negative', or 'neutral'
        """
        self._load_model()

        # Truncate to model's max length (512 tokens for BERT)
        inputs = self._tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        )
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)
            probs = torch.softmax(outputs.logits, dim=1)[0]

        # FinBERT outputs: [positive, negative, neutral]
        positive = probs[0].item()
        negative = probs[1].item()
        neutral = probs[2].item()

        # Convert to [-1, +1] scale
        # Score = positive_prob - negative_prob
        score = positive - negative

        # Confidence = 1 - neutral_prob (how sure the model is that it's not neutral)
        confidence = 1.0 - neutral

        # Label
        label_idx = probs.argmax().item()
        labels = ["positive", "negative", "neutral"]
        label = labels[label_idx]

        return {
            "score": round(score, 4),
            "confidence": round(confidence, 4),
            "label": label,
        }

    def score_batch(self, texts: list[str]) -> list[dict]:
        """
        Score multiple texts efficiently.

        Args:
            texts: List of financial news texts.

        Returns:
            List of score dicts.
        """
        self._load_model()

        if not texts:
            return []

        inputs = self._tokenizer(
            texts,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        )
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)
            probs = torch.softmax(outputs.logits, dim=1)

        results: list[dict] = []
        labels = ["positive", "negative", "neutral"]

        for i in range(len(texts)):
            p = probs[i]
            positive = p[0].item()
            negative = p[1].item()
            neutral = p[2].item()

            results.append({
                "score": round(positive - negative, 4),
                "confidence": round(1.0 - neutral, 4),
                "label": labels[p.argmax().item()],
            })

        return results
