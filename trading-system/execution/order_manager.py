"""
Order placement and tracking.

Orchestrates the full trade lifecycle:
1. Receive signal from ensemble
2. Run pre-trade risk checks
3. Calculate position size
4. Place order via Alpaca
5. Log everything

This is the single entry point for all order execution.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from config.settings import settings
from data.storage.timescale import TimescaleDB
from execution.alpaca_client import AlpacaClient
from execution.position_sizer import PositionSizer
from execution.risk_manager import RiskManager
from strategies.base import Signal

logger = logging.getLogger(__name__)


class OrderManager:
    """
    Manages the full order lifecycle from signal to execution.

    All trades are logged with full context (signal, risk checks, sizing).
    """

    def __init__(
        self,
        db: TimescaleDB,
        alpaca: AlpacaClient,
        risk_manager: RiskManager,
    ) -> None:
        self.db = db
        self.alpaca = alpaca
        self.risk_manager = risk_manager
        self.position_sizer = PositionSizer()

    def execute_signal(
        self,
        ticker: str,
        signal: Signal,
        ensemble_result: dict,
        current_price: float,
        portfolio_value: float,
        win_rate: float = 0.5,
        avg_win: float = 0.01,
        avg_loss: float = 0.01,
        current_drawdown: float = 0.0,
    ) -> dict:
        """
        Execute a trading signal through the full pipeline.

        Args:
            ticker: Stock symbol.
            signal: Signal from strategy.
            ensemble_result: Result from SignalEnsemble.
            current_price: Current market price.
            portfolio_value: Current portfolio value.
            win_rate: Historical win rate for Kelly sizing.
            avg_win: Average winning trade return.
            avg_loss: Average losing trade return (positive).
            current_drawdown: Current drawdown (negative).

        Returns:
            Execution result dict.
        """
        result: dict[str, Any] = {
            "ticker": ticker,
            "signal": signal.direction,
            "strategy": signal.strategy,
            "hypothesis_id": signal.hypothesis_id,
            "executed": False,
            "reason": "",
        }

        # Step 1: Check ensemble confidence
        if ensemble_result["action"] == "hold":
            result["reason"] = "Ensemble says hold"
            self._log_skipped_signal(ticker, signal, result["reason"])
            return result

        # Step 2: Pre-trade risk checks
        open_positions = self.alpaca.get_positions()
        position_size = self.position_sizer.calculate_size(
            confidence=ensemble_result["confidence"],
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            portfolio_value=portfolio_value,
            current_drawdown=current_drawdown,
        )

        # Apply ensemble position factor
        position_size *= ensemble_result.get("position_size_factor", 1.0)

        # Apply risk scaling
        risk_scale = self.risk_manager.get_position_scale_factor(portfolio_value)
        position_size *= risk_scale

        allowed, reason = self.risk_manager.check_pre_trade(
            ticker=ticker,
            direction=signal.direction,
            position_size=position_size,
            portfolio_value=portfolio_value,
            open_positions=open_positions,
        )

        if not allowed:
            result["reason"] = reason
            self._log_skipped_signal(ticker, signal, reason)
            return result

        # Step 3: Calculate shares
        shares = self.position_sizer.shares_from_dollars(position_size, current_price)
        if shares < 0.01:
            result["reason"] = "Position too small"
            return result

        # Step 4: Place order
        side = "buy" if signal.direction == "long" else "sell"
        limit_price = self._calculate_limit_price(current_price, side)

        order = self.alpaca.place_order(
            ticker=ticker,
            side=side,
            qty=shares,
            limit_price=limit_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
        )

        if order is None:
            result["reason"] = "Order placement failed"
            return result

        # Step 5: Log trade
        trade_record = {
            "time": datetime.now(timezone.utc),
            "ticker": ticker,
            "strategy": signal.strategy,
            "hypothesis_id": signal.hypothesis_id,
            "direction": signal.direction,
            "entry_price": current_price,
            "confidence": ensemble_result["confidence"],
            "position_size": position_size,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "explanation": signal.explanation,
            "status": "open",
        }
        trade_id = self.db.insert_trade(trade_record)

        result["executed"] = True
        result["trade_id"] = trade_id
        result["order_id"] = order["id"]
        result["shares"] = shares
        result["position_size"] = position_size
        result["limit_price"] = limit_price

        logger.info(
            "EXECUTED: %s %s %.2f shares of %s @ $%.2f (SL=$%.2f, TP=$%.2f)",
            signal.direction, ticker, shares, ticker, limit_price,
            signal.stop_loss, signal.take_profit,
        )

        return result

    def _calculate_limit_price(self, current_price: float, side: str) -> float:
        """
        Calculate limit price with small offset for better fills.

        For buys: slightly above current price
        For sells: slightly below current price
        """
        offset = current_price * (settings.execution.limit_offset_pct / 100)
        if side == "buy":
            return round(current_price + offset, 2)
        else:
            return round(current_price - offset, 2)

    def _log_skipped_signal(self, ticker: str, signal: Signal, reason: str) -> None:
        """Log a signal that was generated but not acted upon."""
        import json
        self.db.insert_signal({
            "time": datetime.now(timezone.utc),
            "ticker": ticker,
            "strategy": signal.strategy,
            "hypothesis_id": signal.hypothesis_id,
            "direction": signal.direction,
            "confidence": signal.confidence,
            "acted_upon": False,
            "reason_skipped": reason,
            "features_snapshot": json.dumps(signal.features_snapshot),
            "explanation": signal.explanation,
        })
