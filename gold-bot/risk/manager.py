"""Risk manager with TJR strict rules.

Rules:
- Max 1 position at a time
- Max 2 trades per day
- Daily loss cap: 2% -> stop trading
- After any loss: 30 min cool-off
- After 2 consecutive losses: stop for the session
- No re-entry at same level after stop-out
- No revenge trades
- Scaling rules: after 20 trades with 80%+ adherence, increase 25%
- After 4R drawdown: reduce 50%, 15-trade rebuild block
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import random

from config.settings import (
    MAX_POSITIONS, MAX_TRADES_PER_DAY, MAX_DAILY_LOSS_PCT,
    INITIAL_RISK_PCT, MAX_RISK_PCT,
    TP1_PCT, TP2_PCT, TP3_PCT, TP1_RR,
    SPREAD, MAX_SLIPPAGE, COMMISSION_PER_LOT, LOT_SIZE_OZ,
    COOLOFF_MINUTES, MAX_CONSECUTIVE_LOSSES,
    SCALING_TRADE_THRESHOLD, SCALING_ADHERENCE_PCT,
    SCALING_INCREASE, DRAWDOWN_REDUCE_R, DRAWDOWN_REDUCE_PCT, REBUILD_TRADES,
)


@dataclass
class Position:
    signal_timestamp: datetime
    direction: str          # "long" or "short"
    entry_price: float
    stop_loss: float
    original_sl: float      # Never-widened SL
    tp1: float
    tp2: float
    tp3: float
    total_oz: float
    session: str
    entry_type: str
    htf_bias: str
    confluence_score: int = 0
    confluences: list[str] = field(default_factory=list)
    planned_rr: float = 0.0

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
        self.original_sl = self.stop_loss


@dataclass
class RiskManager:
    starting_capital: float
    capital: float = 0.0
    trades_today: int = 0
    daily_pnl: float = 0.0
    current_date: date | None = None
    positions: list[Position] = field(default_factory=list)
    closed_trades: list[Position] = field(default_factory=list)

    # TJR strict rules
    consecutive_losses: int = 0
    last_loss_time: datetime | None = None
    current_risk_pct: float = INITIAL_RISK_PCT
    total_trade_count: int = 0
    winning_trades_count: int = 0
    peak_capital: float = 0.0
    in_rebuild: bool = False
    rebuild_count: int = 0
    session_stopped: bool = False
    current_session: str = ""

    def __post_init__(self):
        self.capital = self.starting_capital
        self.peak_capital = self.starting_capital

    def can_trade(self, dt: datetime) -> tuple[bool, str]:
        """Check if we can open a new trade."""
        # Reset daily state
        if self.current_date != dt.date():
            self.current_date = dt.date()
            self.trades_today = 0
            self.daily_pnl = 0.0
            self.session_stopped = False
            self.consecutive_losses = 0  # Reset consecutive losses each day
            self.current_session = ""

        # Max trades per day
        if self.trades_today >= MAX_TRADES_PER_DAY:
            return False, "Max trades per day"

        # Max positions at a time
        if len(self.positions) >= MAX_POSITIONS:
            return False, "Max positions open"

        # Daily loss cap
        if self.daily_pnl <= -(self.starting_capital * MAX_DAILY_LOSS_PCT):
            return False, "Daily loss cap hit"

        # Session stopped (after 2 consecutive losses in same session)
        if self.session_stopped:
            return False, "Session stopped after consecutive losses"

        # Cool-off after loss
        if self.last_loss_time is not None:
            cooloff_end = self.last_loss_time + timedelta(minutes=COOLOFF_MINUTES)
            if dt < cooloff_end:
                return False, "Cool-off period"

        # Consecutive losses check
        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            self.session_stopped = True
            return False, "Max consecutive losses"

        return True, "OK"

    def open_position(self, pos: Position):
        """Register a new open position."""
        self.positions.append(pos)
        self.trades_today += 1
        self.total_trade_count += 1

    def update_positions(self, bar: dict) -> list[dict]:
        """Check SL/TP for all open positions using bar data.

        Applies realistic execution with random slippage.
        """
        fills = []
        high = bar["high"]
        low = bar["low"]
        slippage = random.uniform(0, MAX_SLIPPAGE)

        for pos in self.positions:
            if pos.closed:
                continue

            # Check Stop Loss FIRST (worst case execution)
            sl_hit = False
            if pos.direction == "long" and low <= pos.stop_loss:
                sl_hit = True
            elif pos.direction == "short" and high >= pos.stop_loss:
                sl_hit = True

            if sl_hit:
                fill_price = pos.stop_loss
                if pos.direction == "long":
                    fill_price -= slippage  # Worse for longs
                    pnl = (fill_price - pos.entry_price - SPREAD) * pos.remaining_oz
                else:
                    fill_price += slippage  # Worse for shorts
                    pnl = (pos.entry_price - fill_price - SPREAD) * pos.remaining_oz
                pos.pnl += pnl
                pos.sl_hit = True
                pos.closed = True
                pos.exit_price = fill_price
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

        # Process closed positions
        newly_closed = [p for p in self.positions if p.closed]
        for p in newly_closed:
            commission = (p.total_oz / LOT_SIZE_OZ) * COMMISSION_PER_LOT
            p.pnl -= commission
            self.daily_pnl += p.pnl
            self.capital += p.pnl

            # Update peak and drawdown tracking
            if self.capital > self.peak_capital:
                self.peak_capital = self.capital

            # Consecutive loss tracking
            if p.pnl < 0:
                self.consecutive_losses += 1
                self.last_loss_time = p.exit_time
                self._check_drawdown_scaling()
            else:
                self.consecutive_losses = 0
                self.winning_trades_count += 1
                self._check_positive_scaling()

            self.closed_trades.append(p)

        self.positions = [p for p in self.positions if not p.closed]
        return fills

    def _check_drawdown_scaling(self):
        """After 4R drawdown: reduce risk 50%, enter rebuild block."""
        if self.peak_capital <= 0:
            return
        drawdown_pct = (self.peak_capital - self.capital) / self.peak_capital
        avg_risk = self.starting_capital * self.current_risk_pct
        if avg_risk > 0:
            drawdown_in_r = (self.peak_capital - self.capital) / avg_risk
            if drawdown_in_r >= DRAWDOWN_REDUCE_R and not self.in_rebuild:
                self.current_risk_pct *= DRAWDOWN_REDUCE_PCT
                self.current_risk_pct = max(self.current_risk_pct, 0.001)
                self.in_rebuild = True
                self.rebuild_count = 0

    def _check_positive_scaling(self):
        """After 20 trades with 80%+ win rate: increase risk 25%."""
        if self.in_rebuild:
            self.rebuild_count += 1
            if self.rebuild_count >= REBUILD_TRADES:
                self.in_rebuild = False
            return

        if self.total_trade_count >= SCALING_TRADE_THRESHOLD:
            win_rate = self.winning_trades_count / self.total_trade_count
            if win_rate >= SCALING_ADHERENCE_PCT:
                new_risk = self.current_risk_pct * (1 + SCALING_INCREASE)
                self.current_risk_pct = min(new_risk, MAX_RISK_PCT)
