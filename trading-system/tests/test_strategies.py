"""
Test strategy signal generation.

Verifies that strategies:
1. Generate signals when conditions are met
2. Don't generate signals when conditions aren't met
3. Produce valid Signal objects with all required fields
4. Have human-readable explanations
"""

from __future__ import annotations

import pytest

from strategies.base import Signal
from strategies.mean_reversion import MeanReversionStrategy
from strategies.momentum import NewsMomentumStrategy
from strategies.sentiment_divergence import SentimentDivergenceStrategy


def _mrs_config() -> dict:
    return {
        "id": "MRS-001",
        "name": "Mean Reversion Test",
        "theory_basis": "Test theory",
        "confidence_threshold": 0.65,
        "max_positions": 2,
        "time_horizon": "1-5 days",
        "stop_loss": {"method": "atr", "multiplier": 2.0},
        "take_profit": {"method": "atr", "multiplier": 3.0},
    }


class TestMeanReversionStrategy:

    def test_long_signal_when_conditions_met(self) -> None:
        """Should generate long signal when all conditions are met."""
        strategy = MeanReversionStrategy(_mrs_config())
        features = {
            "bb_position": 0.05,      # Near lower band
            "rsi_14": 25.0,           # Oversold
            "sent_24h": -0.5,         # Negative sentiment
            "sent_momentum": -0.3,    # Getting worse
            "volume_ratio": 2.0,      # High volume
            "adx_14": 20.0,           # Not trending
            "atr_14": 2.0,
        }
        signal = strategy.check_entry(features, current_price=100.0)
        assert signal is not None
        assert signal.direction == "long"
        assert signal.confidence >= 0.65
        assert signal.explanation != ""

    def test_no_signal_in_strong_trend(self) -> None:
        """Should NOT generate signal when ADX is high (strong trend)."""
        strategy = MeanReversionStrategy(_mrs_config())
        features = {
            "bb_position": 0.05,
            "rsi_14": 25.0,
            "sent_24h": -0.5,
            "sent_momentum": -0.3,
            "volume_ratio": 2.0,
            "adx_14": 35.0,           # STRONG TREND → no mean reversion
            "atr_14": 2.0,
        }
        signal = strategy.check_entry(features, current_price=100.0)
        assert signal is None

    def test_exit_on_mean_return(self) -> None:
        """Should exit when price returns to BB midline."""
        strategy = MeanReversionStrategy(_mrs_config())
        features = {"bb_position": 0.55, "rsi_14": 52}
        should_exit, reason = strategy.check_exit(
            features, current_price=105, entry_price=100,
            direction="long", holding_days=2,
        )
        assert should_exit
        assert "BB midline" in reason or "RSI" in reason

    def test_exit_on_time_limit(self) -> None:
        """Should exit after max holding period."""
        strategy = MeanReversionStrategy(_mrs_config())
        features = {"bb_position": 0.2, "rsi_14": 35}
        should_exit, reason = strategy.check_exit(
            features, current_price=95, entry_price=100,
            direction="long", holding_days=6,
        )
        assert should_exit
        assert "holding period" in reason.lower()

    def test_stop_loss_calculation(self) -> None:
        """Stop loss should be 2 ATR below entry for long."""
        strategy = MeanReversionStrategy(_mrs_config())
        sl = strategy.calculate_stop_loss(100.0, atr=2.0, direction="long")
        assert sl == 96.0  # 100 - 2*2

    def test_take_profit_calculation(self) -> None:
        """Take profit should be 3 ATR above entry for long."""
        strategy = MeanReversionStrategy(_mrs_config())
        tp = strategy.calculate_take_profit(100.0, atr=2.0, direction="long")
        assert tp == 106.0  # 100 + 3*2


class TestSignalObject:

    def test_signal_has_all_fields(self) -> None:
        """Signal object must have all required fields."""
        signal = Signal(
            direction="long",
            confidence=0.75,
            strategy="Test",
            hypothesis_id="TEST-001",
            stop_loss=95.0,
            take_profit=110.0,
            explanation="Test signal",
            features_snapshot={"rsi_14": 25.0},
        )
        assert signal.direction == "long"
        assert signal.confidence == 0.75
        assert signal.stop_loss == 95.0
        assert signal.take_profit == 110.0
        assert signal.explanation != ""
        assert "rsi_14" in signal.features_snapshot
