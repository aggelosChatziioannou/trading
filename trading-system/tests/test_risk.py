"""
Test risk management rules.

Verifies that hard limits are enforced correctly:
- Daily loss limits
- Position size limits
- Open position limits
- No leverage
- Sector concentration
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from execution.position_sizer import PositionSizer
from execution.risk_manager import RiskManager


class TestPositionSizer:

    def test_half_kelly_basic(self) -> None:
        """Half Kelly should produce reasonable position sizes."""
        size = PositionSizer.calculate_size(
            confidence=0.8,
            win_rate=0.55,
            avg_win=0.02,
            avg_loss=0.015,
            portfolio_value=10_000,
        )
        # Should be between min (0.5%) and max (5%) of portfolio
        assert 50 <= size <= 500

    def test_negative_kelly_returns_zero(self) -> None:
        """Negative Kelly (losing strategy) should return 0."""
        size = PositionSizer.calculate_size(
            confidence=0.8,
            win_rate=0.30,      # 30% win rate
            avg_win=0.01,       # Small wins
            avg_loss=0.03,      # Big losses
            portfolio_value=10_000,
        )
        assert size == 0.0

    def test_zero_confidence_returns_zero(self) -> None:
        """Zero confidence should return 0."""
        size = PositionSizer.calculate_size(
            confidence=0.0,
            win_rate=0.6,
            avg_win=0.02,
            avg_loss=0.01,
            portfolio_value=10_000,
        )
        assert size == 0.0

    def test_drawdown_scaling(self) -> None:
        """Position should be reduced in drawdown."""
        normal = PositionSizer.calculate_size(
            confidence=0.8, win_rate=0.55, avg_win=0.02, avg_loss=0.015,
            portfolio_value=10_000, current_drawdown=0.0,
        )
        drawdown = PositionSizer.calculate_size(
            confidence=0.8, win_rate=0.55, avg_win=0.02, avg_loss=0.015,
            portfolio_value=10_000, current_drawdown=-0.06,  # 6% drawdown
        )
        assert drawdown < normal

    def test_shares_calculation(self) -> None:
        """Dollar amount should convert to correct share count."""
        shares = PositionSizer.shares_from_dollars(1000.0, 150.0)
        assert abs(shares - 6.6667) < 0.01


class TestRiskManager:

    def _make_mock_db(self) -> MagicMock:
        db = MagicMock()
        db.get_daily_pnl.return_value = 0.0
        db.get_trade_count_today.return_value = 0
        db.insert_risk_event.return_value = None
        return db

    def test_allows_normal_trade(self) -> None:
        """Normal trade should pass all checks."""
        db = self._make_mock_db()
        rm = RiskManager(db)

        allowed, reason = rm.check_pre_trade(
            ticker="AAPL",
            direction="long",
            position_size=400,
            portfolio_value=10_000,
            open_positions=[],
        )
        assert allowed
        assert reason == "OK"

    def test_blocks_oversized_position(self) -> None:
        """Position exceeding 5% should be blocked."""
        db = self._make_mock_db()
        rm = RiskManager(db)

        allowed, reason = rm.check_pre_trade(
            ticker="AAPL",
            direction="long",
            position_size=600,      # 6% of 10k
            portfolio_value=10_000,
            open_positions=[],
        )
        assert not allowed
        assert "POSITION TOO LARGE" in reason

    def test_blocks_too_many_positions(self) -> None:
        """Should block when max positions reached."""
        db = self._make_mock_db()
        rm = RiskManager(db)

        positions = [
            {"symbol": f"SYM{i}", "qty": 10, "current_price": 100}
            for i in range(5)
        ]
        allowed, reason = rm.check_pre_trade(
            ticker="AAPL",
            direction="long",
            position_size=400,
            portfolio_value=10_000,
            open_positions=positions,
        )
        assert not allowed
        assert "MAX OPEN POSITIONS" in reason

    def test_blocks_on_daily_loss(self) -> None:
        """Should block trading when daily loss limit exceeded."""
        db = self._make_mock_db()
        db.get_daily_pnl.return_value = -250.0  # -2.5% of 10k
        rm = RiskManager(db)

        allowed, reason = rm.check_pre_trade(
            ticker="AAPL",
            direction="long",
            position_size=400,
            portfolio_value=10_000,
            open_positions=[],
        )
        assert not allowed
        assert "DAILY LOSS" in reason

    def test_blocks_excessive_leverage(self) -> None:
        """Should block when total exposure exceeds 1x."""
        db = self._make_mock_db()
        rm = RiskManager(db)

        positions = [
            {"symbol": "MSFT", "qty": 50, "current_price": 180},  # $9,000 exposure
        ]
        allowed, reason = rm.check_pre_trade(
            ticker="AAPL",
            direction="long",
            position_size=2000,     # Would push total to $11,000 > $10,000 portfolio
            portfolio_value=10_000,
            open_positions=positions,
        )
        assert not allowed
        assert "LEVERAGE" in reason

    def test_max_drawdown_triggers_observation(self) -> None:
        """Should enter observation mode on max drawdown."""
        db = self._make_mock_db()
        rm = RiskManager(db)
        rm._peak_equity = 10_000

        allowed, reason = rm.check_pre_trade(
            ticker="AAPL",
            direction="long",
            position_size=400,
            portfolio_value=8_900,  # 11% drawdown
            open_positions=[],
        )
        assert not allowed
        assert "DRAWDOWN" in reason
        assert rm._observation_mode
