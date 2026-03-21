"""
Telegram/email alerts for key trading events.

Sends notifications for:
- Trade executions
- Risk events (daily loss stop, drawdown mode)
- Daily P&L summary
- System errors
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Send alerts via Telegram for key trading events.

    Falls back to logging if Telegram is not configured.
    """

    def __init__(self) -> None:
        self._bot: Any = None
        self._chat_id = settings.api.telegram_chat_id

        if settings.api.telegram_bot_token and settings.api.telegram_chat_id:
            try:
                import telegram
                self._bot = telegram.Bot(token=settings.api.telegram_bot_token)
                logger.info("Telegram alerts configured")
            except ImportError:
                logger.warning("python-telegram-bot not installed — alerts will be logged only")
        else:
            logger.info("Telegram not configured — alerts will be logged only")

    async def send_alert(self, message: str, urgent: bool = False) -> None:
        """
        Send an alert message.

        Args:
            message: Alert text (supports Markdown).
            urgent: If True, add urgency prefix.
        """
        if urgent:
            message = f"🚨 URGENT: {message}"

        logger.info("ALERT: %s", message)

        if self._bot is not None:
            try:
                await self._bot.send_message(
                    chat_id=self._chat_id,
                    text=message,
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error("Failed to send Telegram alert: %s", e)

    async def trade_alert(self, trade: dict) -> None:
        """Send trade execution alert."""
        msg = (
            f"*Trade Executed*\n"
            f"  {trade.get('direction', '?').upper()} {trade.get('ticker', '?')}\n"
            f"  Entry: ${trade.get('entry_price', 0):.2f}\n"
            f"  Size: ${trade.get('position_size', 0):.2f}\n"
            f"  SL: ${trade.get('stop_loss', 0):.2f} | TP: ${trade.get('take_profit', 0):.2f}\n"
            f"  Strategy: {trade.get('strategy', '?')}\n"
            f"  Confidence: {trade.get('confidence', 0):.0%}"
        )
        await self.send_alert(msg)

    async def risk_alert(self, event_type: str, details: dict) -> None:
        """Send risk event alert (always urgent)."""
        msg = f"*Risk Event: {event_type}*\n{details}"
        await self.send_alert(msg, urgent=True)

    async def daily_summary(self, summary: dict) -> None:
        """Send daily P&L summary."""
        msg = (
            f"*Daily Summary*\n"
            f"  P&L: ${summary.get('daily_pnl', 0):.2f} ({summary.get('daily_pnl_pct', 0):.2f}%)\n"
            f"  Trades: {summary.get('trades_today', 0)}\n"
            f"  Win Rate: {summary.get('win_rate', 0):.0%}\n"
            f"  Portfolio: ${summary.get('portfolio_value', 0):,.2f}\n"
            f"  Drawdown: {summary.get('drawdown', 0):.2f}%"
        )
        await self.send_alert(msg)
