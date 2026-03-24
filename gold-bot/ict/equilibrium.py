"""Equilibrium (50% fib retracement) and 79% Fibonacci extension."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from config.settings import FIB_EXTENSION_79
from ict.structures import SwingPoint, BOS


@dataclass
class Equilibrium:
    price: float
    direction: str       # direction of the impulse
    swing_start: SwingPoint
    bos_point: BOS
    timestamp: datetime


@dataclass
class FibLevel:
    price: float
    level: float         # 0.5, 0.79, etc.
    direction: str
    timestamp: datetime


def find_equilibrium(swing: SwingPoint, bos: BOS) -> Equilibrium:
    """Calculate the 50% retracement (equilibrium) of an impulse move."""
    eq_price = (swing.price + bos.price) / 2
    return Equilibrium(
        price=eq_price, direction=bos.direction,
        swing_start=swing, bos_point=bos, timestamp=bos.timestamp,
    )


def find_fib_79_extension(swing_start: SwingPoint, swing_end: SwingPoint) -> FibLevel:
    """Calculate the 79% Fibonacci extension of a move.

    TJR uses the 79% extension on 5-min as a confirmation signal.
    If a candle CLOSES beyond the 79% extension, it confirms the move.
    """
    move = swing_end.price - swing_start.price
    fib_price = swing_start.price + move * FIB_EXTENSION_79

    direction = "bullish" if move > 0 else "bearish"
    return FibLevel(
        price=fib_price, level=FIB_EXTENSION_79,
        direction=direction, timestamp=swing_end.timestamp,
    )


def check_fib_79_closure(fib: FibLevel, close_price: float) -> bool:
    """Check if a candle has closed beyond the 79% extension level.

    Bullish: close > fib level
    Bearish: close < fib level
    """
    if fib.direction == "bullish":
        return close_price > fib.price
    else:
        return close_price < fib.price
