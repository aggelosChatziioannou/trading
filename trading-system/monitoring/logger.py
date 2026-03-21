"""
Structured trading logger.

Logs EVERYTHING — every signal, trade, decision, and risk event.
This is not just for debugging; it's for anti-overfit accountability.
We need to prove that we didn't cherry-pick results.

Logs to:
1. PostgreSQL (trades/signals tables) — structured data
2. JSON files — full signal details for analysis
3. Console — real-time monitoring
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import settings

_log_dir = settings.logging.log_dir
_json_dir = settings.logging.json_log_dir


def setup_logging() -> None:
    """
    Configure structured logging for the entire trading system.

    Sets up:
    - Console handler (INFO level)
    - File handler with rotation (DEBUG level)
    - JSON signal logger (separate file)
    """
    _log_dir.mkdir(parents=True, exist_ok=True)
    _json_dir.mkdir(parents=True, exist_ok=True)

    # Root logger
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(console)

    # Rotating file handler (10MB, keep 5 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        _log_dir / "trading.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s",
    ))
    root.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("websocket").setLevel(logging.WARNING)


class TradingLogger:
    """
    Domain-specific logger for trading events.

    Every method logs to both the standard Python logger
    and writes a JSON file for detailed analysis.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger("trading")

    def log_signal(self, signal_dict: dict) -> None:
        """Log a generated signal (whether acted on or not)."""
        self._logger.info(
            "SIGNAL: %s %s %s (conf=%.2f, strategy=%s)",
            signal_dict.get("direction", "?"),
            signal_dict.get("ticker", "?"),
            "ACTED" if signal_dict.get("acted_upon") else "SKIPPED",
            signal_dict.get("confidence", 0),
            signal_dict.get("strategy", "?"),
        )
        self._write_json("signal", signal_dict)

    def log_trade(self, trade_dict: dict) -> None:
        """Log a trade execution."""
        self._logger.info(
            "TRADE: %s %s %s @ $%.2f (size=$%.2f, SL=$%.2f, TP=$%.2f)",
            trade_dict.get("direction", "?"),
            trade_dict.get("ticker", "?"),
            trade_dict.get("status", "?"),
            trade_dict.get("entry_price", 0),
            trade_dict.get("position_size", 0),
            trade_dict.get("stop_loss", 0),
            trade_dict.get("take_profit", 0),
        )
        self._write_json("trade", trade_dict)

    def log_trade_close(self, trade_dict: dict) -> None:
        """Log a trade closure with P&L."""
        self._logger.info(
            "CLOSE: %s %s PnL=$%.2f (%.2f%%), held %s",
            trade_dict.get("ticker", "?"),
            trade_dict.get("status", "?"),
            trade_dict.get("pnl", 0),
            trade_dict.get("pnl_pct", 0),
            trade_dict.get("holding_period", "?"),
        )
        self._write_json("close", trade_dict)

    def log_hypothesis_test(
        self,
        hypothesis_id: str,
        cpcv_results: dict,
        pbo: float,
        deflated_sharpe: float,
    ) -> None:
        """Log results of testing a hypothesis (including failures)."""
        passed = pbo < 0.10 and deflated_sharpe > 0
        self._logger.info(
            "HYPOTHESIS %s: %s (Sharpe=%.4f±%.4f, PBO=%.2f%%, DSR=%.4f)",
            hypothesis_id,
            "PASS" if passed else "FAIL",
            cpcv_results.get("sharpe_mean", 0),
            cpcv_results.get("sharpe_std", 0),
            pbo * 100,
            deflated_sharpe,
        )
        self._write_json("hypothesis", {
            "id": hypothesis_id,
            "passed": passed,
            "cpcv": cpcv_results,
            "pbo": pbo,
            "deflated_sharpe": deflated_sharpe,
        })

    def log_risk_event(self, event_type: str, details: dict) -> None:
        """Log risk management triggers."""
        self._logger.warning("RISK EVENT: %s — %s", event_type, details)
        self._write_json("risk", {"event_type": event_type, **details})

    def _write_json(self, event_type: str, data: dict) -> None:
        """Write event as JSON file for detailed analysis."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{event_type}_{timestamp}.json"
        filepath = _json_dir / filename

        try:
            # Make data JSON-serializable
            clean_data = self._make_serializable(data)
            clean_data["_event_type"] = event_type
            clean_data["_timestamp"] = datetime.now(timezone.utc).isoformat()

            with open(filepath, "w") as f:
                json.dump(clean_data, f, indent=2, default=str)
        except Exception as e:
            self._logger.error("Failed to write JSON log: %s", e)

    @staticmethod
    def _make_serializable(obj: Any) -> Any:
        """Convert non-serializable objects to strings."""
        if isinstance(obj, dict):
            return {k: TradingLogger._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [TradingLogger._make_serializable(v) for v in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, float) and (obj != obj):  # NaN check
            return None
        return obj
