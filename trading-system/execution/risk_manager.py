"""
Risk management with hard, non-negotiable limits.

Enforces:
- Max daily loss (circuit breaker)
- Max weekly loss (position size reduction)
- Max drawdown (observation-only mode)
- Position limits (per trade, total, sector)
- No leverage

These rules CANNOT be overridden by strategy signals.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from config.settings import settings
from data.storage.timescale import TimescaleDB

logger = logging.getLogger(__name__)

_risk = settings.risk


class RiskManager:
    """
    Enforces hard risk limits before any trade execution.

    Every order must pass through check_pre_trade() before being placed.
    """

    def __init__(self, db: TimescaleDB) -> None:
        self.db = db
        self._peak_equity: float = _risk.initial_capital
        self._observation_mode: bool = False

    def check_pre_trade(
        self,
        ticker: str,
        direction: str,
        position_size: float,
        portfolio_value: float,
        open_positions: list[dict],
    ) -> tuple[bool, str]:
        """
        Run all pre-trade risk checks.

        Args:
            ticker: Stock to trade.
            direction: 'long' or 'short'.
            position_size: Proposed position size in dollars.
            portfolio_value: Current portfolio value.
            open_positions: List of current open positions.

        Returns:
            Tuple of (allowed, reason).
            If allowed is False, reason explains why.
        """
        # Check 1: Observation mode (max drawdown breached)
        if self._observation_mode:
            current_dd = self._current_drawdown(portfolio_value)
            if current_dd < _risk.recovery_threshold_pct / 100:
                return False, f"OBSERVATION MODE: drawdown {current_dd:.1%}, recovery threshold {_risk.recovery_threshold_pct}%"
            else:
                self._observation_mode = False
                logger.info("Exiting observation mode: drawdown recovered to %.1f%%", current_dd * 100)

        # Check 2: Max drawdown
        current_dd = self._current_drawdown(portfolio_value)
        if current_dd < _risk.max_drawdown_pct / 100:
            self._observation_mode = True
            self.db.insert_risk_event("max_drawdown", {
                "drawdown": current_dd,
                "threshold": _risk.max_drawdown_pct,
                "portfolio_value": portfolio_value,
            })
            return False, f"MAX DRAWDOWN BREACHED: {current_dd:.1%} (limit: {_risk.max_drawdown_pct}%)"

        # Check 3: Daily loss limit
        daily_pnl = self.db.get_daily_pnl(datetime.now(timezone.utc))
        daily_pnl_pct = daily_pnl / portfolio_value if portfolio_value > 0 else 0
        if daily_pnl_pct < _risk.max_daily_loss_pct / 100:
            self.db.insert_risk_event("daily_loss_stop", {
                "daily_pnl": daily_pnl,
                "daily_pnl_pct": daily_pnl_pct,
                "threshold": _risk.max_daily_loss_pct,
            })
            return False, f"DAILY LOSS LIMIT: {daily_pnl_pct:.1%} (limit: {_risk.max_daily_loss_pct}%)"

        # Check 4: Max daily trades
        trade_count = self.db.get_trade_count_today()
        if trade_count >= _risk.max_daily_trades:
            return False, f"MAX DAILY TRADES: {trade_count} (limit: {_risk.max_daily_trades})"

        # Check 5: Max open positions
        if len(open_positions) >= _risk.max_open_positions:
            return False, f"MAX OPEN POSITIONS: {len(open_positions)} (limit: {_risk.max_open_positions})"

        # Check 6: Position size limits
        max_size = portfolio_value * (_risk.max_position_pct / 100)
        if position_size > max_size:
            return False, f"POSITION TOO LARGE: ${position_size:.2f} (max: ${max_size:.2f})"

        # Check 7: No leverage
        total_exposure = sum(abs(p.get("qty", 0) * p.get("current_price", 0)) for p in open_positions)
        if total_exposure + position_size > portfolio_value * _risk.max_leverage:
            return False, f"LEVERAGE BREACH: total exposure would exceed {_risk.max_leverage}x"

        # Check 8: Sector concentration
        same_sector = self._count_same_sector(ticker, open_positions)
        if same_sector >= _risk.max_same_sector:
            return False, f"SECTOR CONCENTRATION: {same_sector} positions in same sector (limit: {_risk.max_same_sector})"

        # All checks passed
        return True, "OK"

    def update_peak_equity(self, current_equity: float) -> None:
        """Update high-water mark for drawdown calculation."""
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity

    def _current_drawdown(self, portfolio_value: float) -> float:
        """Calculate current drawdown from peak."""
        if self._peak_equity <= 0:
            return 0.0
        return (portfolio_value - self._peak_equity) / self._peak_equity

    def get_position_scale_factor(self, portfolio_value: float) -> float:
        """
        Get position size scaling factor based on current risk state.

        Returns:
            1.0 = normal sizing
            0.5 = reduced sizing (weekly loss threshold)
            0.0 = no trading (observation mode)
        """
        if self._observation_mode:
            return 0.0

        # Check weekly loss
        # Approximate: sum last 5 days of P&L
        weekly_pnl = 0.0
        for i in range(5):
            day = datetime.now(timezone.utc) - timedelta(days=i)
            weekly_pnl += self.db.get_daily_pnl(day)

        weekly_pnl_pct = weekly_pnl / portfolio_value if portfolio_value > 0 else 0
        if weekly_pnl_pct < _risk.max_weekly_loss_pct / 100:
            logger.info("Weekly loss scaling: %.1f%% (threshold: %.1f%%)", weekly_pnl_pct * 100, _risk.max_weekly_loss_pct)
            return 0.5

        return 1.0

    @staticmethod
    def _count_same_sector(ticker: str, open_positions: list[dict]) -> int:
        """
        Count positions in the same sector as the ticker.

        Uses a simple mapping — in production, use a proper sector database.
        """
        # Sector mapping for watchlist
        sectors: dict[str, str] = {
            "AAPL": "tech", "MSFT": "tech", "GOOGL": "tech", "AMZN": "tech",
            "NVDA": "tech", "META": "tech", "TSLA": "auto",
            "JPM": "finance", "V": "finance", "BAC": "finance",
            "JNJ": "healthcare", "WMT": "retail", "PG": "consumer",
            "HD": "retail", "XOM": "energy",
        }

        my_sector = sectors.get(ticker, "other")
        count = 0
        for pos in open_positions:
            pos_sector = sectors.get(pos.get("symbol", ""), "other")
            if pos_sector == my_sector:
                count += 1

        return count
