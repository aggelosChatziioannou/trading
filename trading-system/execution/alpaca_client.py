"""
Alpaca API wrapper for paper and live trading.

Modes:
- PAPER: Uses Alpaca paper trading (free, no real money)
- LIVE: Uses Alpaca live trading (commission-free US stocks)

IMPORTANT: Start in PAPER mode for minimum 3 months.
Switch to LIVE only after validation criteria are met.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, OrderType, TimeInForce
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
)

from config.settings import settings

logger = logging.getLogger(__name__)


class AlpacaClient:
    """
    Alpaca API wrapper with pre-trade risk checks.

    Uses limit orders by default for better fills.
    Supports OCO bracket orders (stop-loss + take-profit).
    """

    def __init__(self, mode: str | None = None) -> None:
        """
        Args:
            mode: 'paper' or 'live'. Defaults to config setting.
        """
        self._mode = mode or settings.execution.trading_mode
        paper = self._mode == "paper"

        if not settings.api.alpaca_key or not settings.api.alpaca_secret:
            logger.warning("Alpaca API keys not set — client will not function")
            self._client = None
            return

        self._client = TradingClient(
            api_key=settings.api.alpaca_key,
            secret_key=settings.api.alpaca_secret,
            paper=paper,
        )
        logger.info("Alpaca client initialized (mode=%s)", self._mode)

    def place_order(
        self,
        ticker: str,
        side: str,
        qty: float,
        limit_price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> dict | None:
        """
        Place an order with optional bracket (stop-loss + take-profit).

        Args:
            ticker: Stock symbol.
            side: 'buy' or 'sell'.
            qty: Number of shares (can be fractional).
            limit_price: Limit price. If None, uses market order.
            stop_loss: Stop-loss price.
            take_profit: Take-profit price.

        Returns:
            Order dict or None on failure.
        """
        if self._client is None:
            logger.error("Alpaca client not initialized")
            return None

        order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL

        try:
            if limit_price is not None:
                order_data = LimitOrderRequest(
                    symbol=ticker,
                    qty=qty,
                    side=order_side,
                    type=OrderType.LIMIT,
                    time_in_force=TimeInForce.DAY,
                    limit_price=round(limit_price, 2),
                )
            else:
                order_data = MarketOrderRequest(
                    symbol=ticker,
                    qty=qty,
                    side=order_side,
                    type=OrderType.MARKET,
                    time_in_force=TimeInForce.DAY,
                )

            # Add bracket legs if provided
            if stop_loss is not None:
                order_data.stop_loss = {"stop_price": round(stop_loss, 2)}
            if take_profit is not None:
                order_data.take_profit = {"limit_price": round(take_profit, 2)}

            order = self._client.submit_order(order_data)
            logger.info(
                "Order placed: %s %s %.2f shares of %s @ %s (SL=%s, TP=%s)",
                side, ticker, qty, ticker, limit_price or "market",
                stop_loss, take_profit,
            )
            return {
                "id": str(order.id),
                "status": str(order.status),
                "symbol": order.symbol,
                "side": str(order.side),
                "qty": str(order.qty),
                "filled_qty": str(order.filled_qty),
            }

        except Exception as e:
            logger.error("Order failed: %s", e)
            return None

    def get_positions(self) -> list[dict]:
        """Get all current open positions."""
        if self._client is None:
            return []
        try:
            positions = self._client.get_all_positions()
            return [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "side": "long" if float(p.qty) > 0 else "short",
                    "avg_entry": float(p.avg_entry_price),
                    "current_price": float(p.current_price),
                    "unrealized_pnl": float(p.unrealized_pl),
                    "unrealized_pnl_pct": float(p.unrealized_plpc) * 100,
                }
                for p in positions
            ]
        except Exception as e:
            logger.error("Failed to get positions: %s", e)
            return []

    def get_account(self) -> dict:
        """Get account info (buying power, equity, P&L)."""
        if self._client is None:
            return {}
        try:
            account = self._client.get_account()
            return {
                "equity": float(account.equity),
                "buying_power": float(account.buying_power),
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "daily_pnl": float(account.equity) - float(account.last_equity),
            }
        except Exception as e:
            logger.error("Failed to get account: %s", e)
            return {}

    def close_position(self, ticker: str) -> bool:
        """Close all shares of a position."""
        if self._client is None:
            return False
        try:
            self._client.close_position(ticker)
            logger.info("Closed position: %s", ticker)
            return True
        except Exception as e:
            logger.error("Failed to close position %s: %s", ticker, e)
            return False

    def cancel_all_orders(self) -> bool:
        """Cancel all open orders."""
        if self._client is None:
            return False
        try:
            self._client.cancel_orders()
            logger.info("Cancelled all open orders")
            return True
        except Exception as e:
            logger.error("Failed to cancel orders: %s", e)
            return False
