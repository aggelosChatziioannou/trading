"""
Strategy registry — maps hypothesis IDs to strategy instances.

Loads strategy definitions from hypotheses.yaml and instantiates
the corresponding strategy classes. This is the single place
where strategies are registered and looked up.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from strategies.base import BaseStrategy
from strategies.breakout import BreakoutStrategy
from strategies.earnings_drift import EarningsDriftStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.momentum import MomentumStrategy
from strategies.overnight_gap import OvernightGapStrategy
from strategies.sentiment_divergence import SentimentDivergenceStrategy
from strategies.vwap_reversion import VWAPReversionStrategy

logger = logging.getLogger(__name__)

# Maps YAML keys to strategy classes
_STRATEGY_CLASS_MAP: dict[str, type[BaseStrategy]] = {
    "mean_reversion_sentiment": MeanReversionStrategy,
    "news_momentum": MomentumStrategy,
    "sentiment_divergence": SentimentDivergenceStrategy,
    "volatility_breakout": BreakoutStrategy,
    "earnings_drift": EarningsDriftStrategy,
    "vwap_reversion": VWAPReversionStrategy,
    "overnight_gap": OvernightGapStrategy,
}


class StrategyRegistry:
    """
    Load strategies from YAML and provide lookup by hypothesis ID.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self._strategies: dict[str, BaseStrategy] = {}
        self._configs: dict[str, dict] = {}

        if config_path is None:
            config_path = Path(__file__).resolve().parent.parent / "config" / "hypotheses.yaml"

        self._load(config_path)

    def _load(self, path: Path) -> None:
        """Parse YAML and instantiate strategy objects."""
        with open(path) as f:
            data = yaml.safe_load(f)

        strategies_data = data.get("strategies", {})

        for key, config in strategies_data.items():
            cls = _STRATEGY_CLASS_MAP.get(key)
            if cls is None:
                logger.warning("No strategy class for YAML key '%s' — skipping", key)
                continue

            hypothesis_id = config.get("id", key)
            try:
                strategy = cls(config)
                self._strategies[hypothesis_id] = strategy
                self._configs[hypothesis_id] = config
                logger.info("Registered strategy: %s (%s)", config.get("name", key), hypothesis_id)
            except Exception as e:
                logger.error("Failed to instantiate strategy '%s': %s", key, e)

    @property
    def all_strategies(self) -> dict[str, BaseStrategy]:
        """Return all registered strategies keyed by hypothesis ID."""
        return dict(self._strategies)

    def get(self, hypothesis_id: str) -> BaseStrategy | None:
        """Look up a strategy by hypothesis ID."""
        return self._strategies.get(hypothesis_id)

    def get_config(self, hypothesis_id: str) -> dict:
        """Get the raw YAML config for a hypothesis."""
        return self._configs.get(hypothesis_id, {})

    def active_strategies(self) -> dict[str, BaseStrategy]:
        """Return strategies that are enabled (all by default)."""
        return dict(self._strategies)
