"""Risk manager: daily limits, position tracking, multi-TP management."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from config.settings import (
    MAX_TRADES_PER_DAY, MAX_DAILY_LOSS, TP1_PCT, TP2_PCT, TP3_PCT,
    SPREAD, SLIPPAGE, COMMISSION_PER_LOT, LOT_SIZE_OZ,
)


@dataclass
class Position:
    signal_timestamp: datetime
    direction: str          # "long" or "short"
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    total_oz: float
    session: str
    entry_type: str

    # State
    remaining_oz: float = 0
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    sl_hit: bool = False
    closed: bool = False
    exit_price: float = 0.0
    exit_time: datetime | None = None
    pnl: float = 0.0

    def __post_init__(self):
        self.remaining_oz = self.total_oz


@dataclass
class RiskManager:
    starting_capital: float
    capital: float = 0.0
    trades_today: int = 0
    daily_pnl: float = 0.0
    current_date: date | None = None
    positions: list[Position] = field(default_factory=list)
    closed_trades: list[Position] = field(default_factory=list)

    def __post_init__(self):
        self.capital = self.starting_capital

    def can_trade(self, dt: datetime) -> tuple[bool, str]:
        """Check if we can open a new trade."""
        if self.current_date != dt.date():
            self.current_date = dt.date()
            self.trades_today = 0
            self.daily_pnl = 0.0

        if self.trades_today >= MAX_TRADES_PER_DAY:
            return False, "Max trades per day reached"

        if self.daily_pnl <= -(self.starting_capital * MAX_DAILY_LOSS):
            return False, "Max daily loss reached"

        return True, "OK"

    def open_position(self, pos: Position):
        """Register a new open position."""
        self.positions.append(pos)
        self.trades_today += 1

    def update_positions(self, bar: dict) -> list[dict]:
        """Check SL/TP for all open positions using bar data.

        bar: dict with keys high, low, close, timestamp.
        Returns list of fill events.
        """
        fills = []
        high = bar["high"]
        low = bar["low"]

        for pos in self.positions:
            if pos.closed:
                continue

            # Check Stop Loss
            sl_hit = False
            if pos.direction == "long" and low <= pos.stop_loss:
                sl_hit = True
            elif pos.direction == "short" and high >= pos.stop_loss:
                sl_hit = True

            if sl_hit:
                if pos.direction == "long":
                    pnl = (pos.stop_loss - pos.entry_price - SPREAD - SLIPPAGE) * pos.remaining_oz
                else:
                    pnl = (pos.entry_price - pos.stop_loss - SPREAD - SLIPPAGE) * pos.remaining_oz
                pos.pnl += pnl
                pos.sl_hit = True
                pos.closed = True
                pos.exit_price = pos.stop_loss
                pos.exit_time = bar["timestamp"]
                pos.remaining_oz = 0
                fills.append({"type": "SL", "pnl": pnl, "position": pos})
                continue

            # Check TP1
            if not pos.tp1_hit:
                tp1_hit = ((pos.direction == "long" and high >= pos.tp1) or
                           (pos.direction == "short" and low <= pos.tp1))
                if tp1_hit:
                    close_oz = pos.total_oz * TP1_PCT
                    if pos.direction == "long":
                        pnl = (pos.tp1 - pos.entry_price - SPREAD) * close_oz
                    else:
                        pnl = (pos.entry_price - pos.tp1 - SPREAD) * close_oz
                    pos.pnl += pnl
                    pos.tp1_hit = True
                    pos.remaining_oz -= close_oz
                    # Move SL to breakeven
                    pos.stop_loss = pos.entry_price
                    fills.append({"type": "TP1", "pnl": pnl, "position": pos})

            # Check TP2
            if pos.tp1_hit and not pos.tp2_hit:
                tp2_hit = ((pos.direction == "long" and high >= pos.tp2) or
                           (pos.direction == "short" and low <= pos.tp2))
                if tp2_hit:
                    close_oz = pos.total_oz * TP2_PCT
                    if pos.direction == "long":
                        pnl = (pos.tp2 - pos.entry_price - SPREAD) * close_oz
                    else:
                        pnl = (pos.entry_price - pos.tp2 - SPREAD) * close_oz
                    pos.pnl += pnl
                    pos.tp2_hit = True
                    pos.remaining_oz -= close_oz
                    fills.append({"type": "TP2", "pnl": pnl, "position": pos})

            # Check TP3
            if pos.tp2_hit and not pos.tp3_hit:
                tp3_hit = ((pos.direction == "long" and high >= pos.tp3) or
                           (pos.direction == "short" and low <= pos.tp3))
                if tp3_hit:
                    close_oz = pos.remaining_oz
                    if pos.direction == "long":
                        pnl = (pos.tp3 - pos.entry_price - SPREAD) * close_oz
                    else:
                        pnl = (pos.entry_price - pos.tp3 - SPREAD) * close_oz
                    pos.pnl += pnl
                    pos.tp3_hit = True
                    pos.remaining_oz = 0
                    pos.closed = True
                    pos.exit_price = pos.tp3
                    pos.exit_time = bar["timestamp"]
                    fills.append({"type": "TP3", "pnl": pnl, "position": pos})

            # Close if remaining is negligible
            if pos.remaining_oz <= 0.001 and not pos.closed:
                pos.closed = True
                if pos.exit_time is None:
                    pos.exit_time = bar["timestamp"]
                    pos.exit_price = bar["close"]

        # Move closed positions
        newly_closed = [p for p in self.positions if p.closed]
        for p in newly_closed:
            commission = (p.total_oz / LOT_SIZE_OZ) * COMMISSION_PER_LOT
            p.pnl -= commission
            self.daily_pnl += p.pnl
            self.capital += p.pnl
            self.closed_trades.append(p)
        self.positions = [p for p in self.positions if not p.closed]

        return fills
