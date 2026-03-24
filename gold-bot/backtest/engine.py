"""Event-driven backtesting engine - processes bars chronologically."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from config.settings import STARTING_CAPITAL
from data.manager import DataManager
from strategy.entry_model import ICTEntryModel
from risk.position_sizer import calculate_position_size
from risk.manager import RiskManager, Position


@dataclass
class BacktestResult:
    trades: list[Position]
    equity_curve: list[dict]  # [{timestamp, equity}]
    starting_capital: float
    ending_capital: float
    data_start: str = ""
    data_end: str = ""
    base_tf: str = ""
    no_trade_days: int = 0


def run_backtest(
    data: DataManager,
    capital: float = STARTING_CAPITAL,
) -> BacktestResult:
    """Run the TJR ICT strategy backtest.

    Uses 5-min bars as the primary loop. At each bar:
    1. Update risk manager positions using sub-bars (1-min if available)
    2. Check entry model for new signals
    3. Size and open trade if signal passes all gates
    """
    model = ICTEntryModel()
    risk_mgr = RiskManager(starting_capital=capital)
    equity_curve = []

    bars_5m = data.primary_tf
    bars_1h = data.gold_1h
    bars_4h = data.gold_4h

    # Use 1-min bars for precise SL/TP if available
    has_1m = not data.gold_1m.empty if isinstance(data.gold_1m, pd.DataFrame) else False

    # DXY for SMT
    dxy_5m = data.dxy_5m if data.has_dxy else None

    min_history = 50
    if len(bars_5m) <= min_history:
        return BacktestResult(
            trades=[], equity_curve=[], starting_capital=capital,
            ending_capital=capital, base_tf=data.base_tf,
        )

    trading_days = set()
    no_trade_days = set()
    last_day = None

    for i in range(min_history, len(bars_5m)):
        bar = bars_5m.iloc[i]
        bar_time = bars_5m.index[i]
        today = bar_time.date() if hasattr(bar_time, 'date') else bar_time

        # Track trading days
        if today != last_day:
            if last_day is not None and last_day not in trading_days:
                no_trade_days.add(last_day)
            last_day = today

        # Get sub-bars for precise position management
        if has_1m:
            next_time = bars_5m.index[i + 1] if i + 1 < len(bars_5m) else bar_time + pd.Timedelta(minutes=5)
            sub_bars = data.gold_1m[(data.gold_1m.index >= bar_time) & (data.gold_1m.index < next_time)]
            for _, sub_bar in sub_bars.iterrows():
                risk_mgr.update_positions({
                    "high": sub_bar["high"], "low": sub_bar["low"],
                    "close": sub_bar["close"], "timestamp": sub_bar.name,
                })
        else:
            # Use 5-min bar directly
            risk_mgr.update_positions({
                "high": bar["high"], "low": bar["low"],
                "close": bar["close"], "timestamp": bar_time,
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

        # Slice history (no lookahead)
        history_5m = bars_5m.iloc[max(0, i - 200): i + 1]
        history_1h = bars_1h[bars_1h.index <= bar_time].tail(100)
        history_4h = bars_4h[bars_4h.index <= bar_time].tail(50)

        # DXY slice for SMT
        dxy_slice = None
        if dxy_5m is not None and not dxy_5m.empty:
            dxy_slice = dxy_5m[dxy_5m.index <= bar_time].tail(200)

        signal = model.check_entry(
            bar_5m=bar, bar_idx=i,
            gold_5m_history=history_5m,
            gold_1h=history_1h, gold_4h=history_4h,
            capital=risk_mgr.capital,
            dxy_5m=dxy_slice,
        )

        if signal is None:
            continue

        # Size position
        sizing = calculate_position_size(
            capital=risk_mgr.capital,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            risk_pct=risk_mgr.current_risk_pct,
        )

        if sizing["oz"] <= 0:
            continue

        # Open position
        pos = Position(
            signal_timestamp=signal.timestamp,
            direction=signal.direction,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            original_sl=signal.stop_loss,
            tp1=signal.take_profit_1,
            tp2=signal.take_profit_2,
            tp3=signal.take_profit_3,
            total_oz=sizing["oz"],
            session=signal.session,
            entry_type=signal.entry_type,
            htf_bias=signal.htf_bias,
            confluence_score=signal.confluence_score,
            confluences=list(signal.confluences),
            planned_rr=signal.planned_rr,
        )
        risk_mgr.open_position(pos)
        trading_days.add(today)

    # Close remaining open positions at last price
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

    # Count no-trade days
    if last_day is not None and last_day not in trading_days:
        no_trade_days.add(last_day)

    data_start = str(bars_5m.index[0]) if len(bars_5m) > 0 else ""
    data_end = str(bars_5m.index[-1]) if len(bars_5m) > 0 else ""

    return BacktestResult(
        trades=risk_mgr.closed_trades,
        equity_curve=equity_curve,
        starting_capital=capital,
        ending_capital=risk_mgr.capital,
        data_start=data_start,
        data_end=data_end,
        base_tf=data.base_tf,
        no_trade_days=len(no_trade_days),
    )


def _unrealized_pnl(pos: Position, current_price: float) -> float:
    if pos.direction == "long":
        return (current_price - pos.entry_price) * pos.remaining_oz
    else:
        return (pos.entry_price - current_price) * pos.remaining_oz
