"""
Hypothesis tracking and logging.

Tracks EVERY hypothesis tested — including failures.
This is essential for the Deflated Sharpe Ratio calculation,
which needs to know the total number of trials to correct for
multiple testing bias.

If we test 20 ideas and 1 "works," that 1 is probably noise
unless DSR says otherwise.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from data.storage.timescale import TimescaleDB

logger = logging.getLogger(__name__)


class HypothesisLog:
    """
    Track all hypotheses tested, including failures.

    Every test updates the count used by Deflated Sharpe Ratio.
    """

    def __init__(self, db: TimescaleDB) -> None:
        self.db = db

    def register(
        self,
        hypothesis_id: str,
        name: str,
        description: str,
        theory_basis: str,
    ) -> None:
        """
        Register a new hypothesis BEFORE testing it.

        Must be called before any backtesting to ensure
        the trial count is accurate for DSR.
        """
        self.db.upsert_hypothesis({
            "id": hypothesis_id,
            "name": name,
            "description": description,
            "theory_basis": theory_basis,
            "status": "active",
            "cpcv_sharpe_mean": None,
            "cpcv_sharpe_std": None,
            "pbo": None,
            "deflated_sharpe": None,
            "notes": None,
        })
        logger.info("Registered hypothesis: %s (%s)", hypothesis_id, name)

    def record_results(
        self,
        hypothesis_id: str,
        cpcv_sharpe_mean: float,
        cpcv_sharpe_std: float,
        pbo: float,
        deflated_sharpe: float,
        passed: bool,
        notes: str = "",
    ) -> None:
        """
        Record test results for a hypothesis.

        Sets status to 'active' if passed, 'failed' otherwise.
        """
        status = "active" if passed else "failed"

        self.db.upsert_hypothesis({
            "id": hypothesis_id,
            "name": "",  # Won't overwrite existing on UPDATE
            "description": "",
            "theory_basis": "",
            "status": status,
            "cpcv_sharpe_mean": cpcv_sharpe_mean,
            "cpcv_sharpe_std": cpcv_sharpe_std,
            "pbo": pbo,
            "deflated_sharpe": deflated_sharpe,
            "notes": notes,
        })

        logger.info(
            "Hypothesis %s: %s (Sharpe=%.4f±%.4f, PBO=%.2f%%, DSR=%.4f)",
            hypothesis_id, status.upper(),
            cpcv_sharpe_mean, cpcv_sharpe_std, pbo * 100, deflated_sharpe,
        )

    def retire(self, hypothesis_id: str, reason: str) -> None:
        """Mark a hypothesis as retired (no longer traded)."""
        self.db.upsert_hypothesis({
            "id": hypothesis_id,
            "name": "", "description": "", "theory_basis": "",
            "status": "retired",
            "cpcv_sharpe_mean": None, "cpcv_sharpe_std": None,
            "pbo": None, "deflated_sharpe": None,
            "notes": f"Retired: {reason}",
        })
        logger.info("Retired hypothesis %s: %s", hypothesis_id, reason)

    def get_total_trials(self) -> int:
        """
        Get the total number of hypotheses ever tested.

        This is the N in the Deflated Sharpe Ratio formula.
        Includes active, failed, and retired hypotheses.
        """
        df = self.db.get_all_hypotheses()
        return len(df)

    def get_active_hypotheses(self) -> list[dict]:
        """Get all currently active (passing) hypotheses."""
        df = self.db.get_all_hypotheses()
        active = df[df["status"] == "active"]
        return active.to_dict("records")

    def get_summary(self) -> dict:
        """Get summary statistics of hypothesis testing history."""
        df = self.db.get_all_hypotheses()
        if df.empty:
            return {"total": 0, "active": 0, "failed": 0, "retired": 0}

        return {
            "total": len(df),
            "active": int((df["status"] == "active").sum()),
            "failed": int((df["status"] == "failed").sum()),
            "retired": int((df["status"] == "retired").sum()),
        }
