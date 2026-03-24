"""SMT (Smart Money Trap) Divergence between Gold and DXY."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ict.structures import SwingPoint


@dataclass
class SMTSignal:
    timestamp: datetime
    direction: str  # "bullish" or "bearish"
    gold_swing: SwingPoint
    dxy_swing: SwingPoint


def detect_smt(
    gold_swings: list[SwingPoint],
    dxy_swings: list[SwingPoint],
    time_tolerance_minutes: int = 30,
) -> list[SMTSignal]:
    """Detect SMT divergence between Gold and DXY.

    Bullish SMT: Gold makes a lower low but DXY doesn't make a higher high.
    Bearish SMT: Gold makes a higher high but DXY doesn't make a lower low.

    Gold and DXY are inversely correlated, so:
    - Gold LL + DXY no HH = bullish divergence (Gold reversal up)
    - Gold HH + DXY no LL = bearish divergence (Gold reversal down)
    """
    signals = []
    gold_lows = [s for s in gold_swings if s.type == "low"]
    gold_highs = [s for s in gold_swings if s.type == "high"]
    dxy_highs = [s for s in dxy_swings if s.type == "high"]
    dxy_lows = [s for s in dxy_swings if s.type == "low"]

    tol = timedelta(minutes=time_tolerance_minutes)

    # Bullish SMT: Gold LL, DXY fails to make HH
    for i in range(1, len(gold_lows)):
        if gold_lows[i].price >= gold_lows[i - 1].price:
            continue  # Not a lower low
        gl = gold_lows[i]
        prev_gl = gold_lows[i - 1]

        dxy_near_prev = [d for d in dxy_highs
                         if abs((d.timestamp - prev_gl.timestamp).total_seconds()) < tol.total_seconds()]
        dxy_near_curr = [d for d in dxy_highs
                         if abs((d.timestamp - gl.timestamp).total_seconds()) < tol.total_seconds()]

        if dxy_near_prev and dxy_near_curr:
            prev_dxy_high = max(d.price for d in dxy_near_prev)
            curr_dxy_high = max(d.price for d in dxy_near_curr)
            if curr_dxy_high <= prev_dxy_high:  # DXY failed to make higher high
                signals.append(SMTSignal(
                    timestamp=gl.timestamp,
                    direction="bullish",
                    gold_swing=gl,
                    dxy_swing=dxy_near_curr[0],
                ))

    # Bearish SMT: Gold HH, DXY fails to make LL
    for i in range(1, len(gold_highs)):
        if gold_highs[i].price <= gold_highs[i - 1].price:
            continue  # Not a higher high
        gh = gold_highs[i]
        prev_gh = gold_highs[i - 1]

        dxy_near_prev = [d for d in dxy_lows
                         if abs((d.timestamp - prev_gh.timestamp).total_seconds()) < tol.total_seconds()]
        dxy_near_curr = [d for d in dxy_lows
                         if abs((d.timestamp - gh.timestamp).total_seconds()) < tol.total_seconds()]

        if dxy_near_prev and dxy_near_curr:
            prev_dxy_low = min(d.price for d in dxy_near_prev)
            curr_dxy_low = min(d.price for d in dxy_near_curr)
            if curr_dxy_low >= prev_dxy_low:  # DXY failed to make lower low
                signals.append(SMTSignal(
                    timestamp=gh.timestamp,
                    direction="bearish",
                    gold_swing=gh,
                    dxy_swing=dxy_near_curr[0],
                ))

    return signals
