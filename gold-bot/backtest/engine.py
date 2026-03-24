"""Event-driven backtesting engine."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from config.settings import STARTING_CAPITAL
from data.manager import DataManager
from strategy.entry_model import ICTEntryModel
from risk.position_sizer import calculate_position_size
from risk.manager import RiskManager, Position
from ict.structures import find_all_swings


@dataclass
class BacktestResult:
    trades: list[Position]
    equity_curve: list[dict]  # [{timestamp, equity}]
    starting_capital: float
    ending_capital: float


def run_backtest(
    data: DataManager,
    capital: float = STARTING_CAPITAL,
) -> BacktestResult:
    """Run the ICT strategy backtest on the provided data.

    Iterates through 5-min bars. At each bar:
    1. Update risk manager positions using 1-min sub-bars
    2. Check entry model for new signals
    3. Size position and open trade if signal generated
    """
    model = ICTEntryModel()
    risk_mgr = RiskManager(starting_capital=capital)
    equity_curve = []

    bars_5m = data.gold_5m
    bars_1m = data.gold_1m
    bars_1h = data.gold_1h
    bars_4h = data.gold_4h

    # Pre-compute DXY swings if available
    dxy_swings = None
    if data.dxy_5m is not None:
        dxy_swings = find_all_swings(data.dxy_5m, lookback=5)

    min_history = 50  # Need enough bars for structure detection
    if len(bars_5m) <= min_history:
        return BacktestResult(
            trades=[], equity_curve=[], starting_capital=capital, ending_capital=capital
        )

    for i in range(min_history, len(bars_5m)):
        bar = bars_5m.iloc[i]
        bar_time = bars_5m.index[i]

        # Get 1-min bars within this 5-min bar for precise SL/TP checking
        next_time = bars_5m.index[i + 1] if i + 1 < len(bars_5m) else bar_time + pd.Timedelta(minutes=5)
        sub_bars = bars_1m[(bars_1m.index >= bar_time) & (bars_1m.index < next_time)]

        # Update positions with 1-min precision
        for _, sub_bar in sub_bars.iterrows():
            risk_mgr.update_positions({
                "high": sub_bar["high"],
                "low": sub_bar["low"],
                "close": sub_bar["close"],
                "timestamp": sub_bar.name,
            })

        # Record equity
        open_pnl = sum(
            _unrealized_pnl(pos, bar["close"]) for pos in risk_mgr.positions
        )
        equity_curve.append({
            "timestamp": bar_time,
            "equity": risk_mgr.capital + open_pnl,
        })

        # Check for new entry
        can_trade, reason = risk_mgr.can_trade(bar_time)
        if not can_trade:
            continue

        # Slice history up to current bar (no lookahead)
        history_5m = bars_5m.iloc[max(0, i - 200) : i + 1]
        history_1h = bars_1h[bars_1h.index <= bar_time].tail(100)
        history_4h = bars_4h[bars_4h.index <= bar_time].tail(50)

        signal = model.check_entry(
            bar_5m=bar,
            bar_idx=i,
            gold_5m_history=history_5m,
            gold_1h=history_1h,
            gold_4h=history_4h,
            capital=risk_mgr.capital,
            dxy_swings=dxy_swings,
        )

        if signal is None:
            continue

        # Size position
        sizing = calculate_position_size(
            capital=risk_mgr.capital,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
        )

        if sizing["oz"] <= 0:
            continue

        # Open position
        pos = Position(
            signal_timestamp=signal.timestamp,
            direction=signal.direction,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            tp1=signal.take_profit_1,
            tp2=signal.take_profit_2,
            tp3=signal.take_profit_3,
            total_oz=sizing["oz"],
            session=signal.session,
            entry_type=signal.entry_type,
        )
        risk_mgr.open_position(pos)

    # Close any remaining open positions at last price
    if risk_mgr.positions:
        last_price = bars_5m.iloc[-1]["close"]
        last_time = bars_5m.index[-1]
        for pos in list(risk_mgr.positions):
            if pos.direction == "long":
                pos.pnl += (last_price - pos.entry_price) * pos.remaining_oz
            else:
                pos.pnl += (pos.entry_price - last_price) * pos.remaining_oz
            pos.closed = True
            pos.exit_price = last_price
            pos.exit_time = last_time
            risk_mgr.capital += pos.pnl
            risk_mgr.closed_trades.append(pos)
        risk_mgr.positions = []

    return BacktestResult(
        trades=risk_mgr.closed_trades,
        equity_curve=equity_curve,
        starting_capital=capital,
        ending_capital=risk_mgr.capital,
    )


def _unrealized_pnl(pos: Position, current_price: float) -> float:
    if pos.direction == "long":
        return (current_price - pos.entry_price) * pos.remaining_oz
    else:
        return (pos.entry_price - current_price) * pos.remaining_oz
