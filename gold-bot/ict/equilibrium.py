"""Equilibrium (50% retracement) of impulse moves."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ict.structures import SwingPoint, BOS


@dataclass
class Equilibrium:
    price: float
    direction: str  # "bullish" or "bearish" (direction of the impulse)
    swing_start: SwingPoint
    bos_point: BOS
    timestamp: datetime


def find_equilibrium(swing: SwingPoint, bos: BOS) -> Equilibrium:
    """Calculate the 50% retracement (equilibrium) of an impulse move.

    The impulse runs from the swing point to the BOS point.
    """
    eq_price = (swing.price + bos.price) / 2
    return Equilibrium(
        price=eq_price,
        direction=bos.direction,
        swing_start=swing,
        bos_point=bos,
        timestamp=bos.timestamp,
    )
