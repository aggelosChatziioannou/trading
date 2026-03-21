"""
Automated daily P&L and analysis report.

Generates a comprehensive daily report covering:
- P&L summary
- Trade log
- Signal statistics
- Risk status
- Hypothesis performance
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pandas as pd

from data.storage.timescale import TimescaleDB

logger = logging.getLogger(__name__)


class DailyReport:
    """Generate daily trading reports for review."""

    def __init__(self, db: TimescaleDB) -> None:
        self.db = db

    def generate(self, date: datetime | None = None) -> dict:
        """
        Generate a comprehensive daily report.

        Args:
            date: Report date. Defaults to today.

        Returns:
            Report dict with all sections.
        """
        if date is None:
            date = datetime.now(timezone.utc)

        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        # Get trades for the day
        trades_df = self.db.get_trades(start=start, end=end)

        # P&L
        pnl_summary = self._pnl_summary(trades_df)

        # Trade details
        trade_details = self._trade_details(trades_df)

        # Hypothesis performance
        hypotheses = self.db.get_all_hypotheses()

        report = {
            "date": date.strftime("%Y-%m-%d"),
            "pnl": pnl_summary,
            "trades": trade_details,
            "trade_count": len(trades_df),
            "hypotheses_active": int((hypotheses["status"] == "active").sum()) if not hypotheses.empty else 0,
            "hypotheses_total": len(hypotheses),
        }

        logger.info("Daily report for %s: PnL=$%.2f, trades=%d", report["date"], pnl_summary["total_pnl"], len(trades_df))
        return report

    def _pnl_summary(self, trades_df: pd.DataFrame) -> dict:
        """Calculate P&L metrics from trades."""
        if trades_df.empty:
            return {"total_pnl": 0.0, "win_count": 0, "loss_count": 0, "win_rate": 0.0}

        closed = trades_df[trades_df["status"].isin(["closed", "stopped"])]
        if closed.empty:
            return {"total_pnl": 0.0, "win_count": 0, "loss_count": 0, "win_rate": 0.0}

        pnl = closed["pnl"].fillna(0)
        wins = pnl[pnl > 0]
        losses = pnl[pnl < 0]

        return {
            "total_pnl": round(float(pnl.sum()), 2),
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate": round(len(wins) / len(pnl), 4) if len(pnl) > 0 else 0.0,
            "avg_win": round(float(wins.mean()), 2) if len(wins) > 0 else 0.0,
            "avg_loss": round(float(losses.mean()), 2) if len(losses) > 0 else 0.0,
            "best_trade": round(float(pnl.max()), 2),
            "worst_trade": round(float(pnl.min()), 2),
        }

    def _trade_details(self, trades_df: pd.DataFrame) -> list[dict]:
        """Format trade details for report."""
        if trades_df.empty:
            return []

        details: list[dict] = []
        for _, row in trades_df.iterrows():
            details.append({
                "ticker": row["ticker"],
                "strategy": row["strategy"],
                "direction": row["direction"],
                "entry_price": row.get("entry_price"),
                "exit_price": row.get("exit_price"),
                "pnl": row.get("pnl"),
                "status": row["status"],
                "explanation": row.get("explanation", ""),
            })
        return details
