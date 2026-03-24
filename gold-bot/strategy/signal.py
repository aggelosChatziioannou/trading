"""Trading signal dataclass."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TradeSignal:
    timestamp: datetime
    direction: str           # "long" or "short"
    entry_price: float
    stop_loss: float
    take_profit_1: float     # TP1 at 1:1 R:R
    take_profit_2: float     # TP2 at 2:1 R:R
    take_profit_3: float     # TP3 at next key level
    session: str             # "London" or "NY"
    htf_level_swept: float   # The liquidity level that was swept
    entry_type: str          # "FVG", "OB", "BB", "EQ"
    confidence: float = 1.0
    risk_dollars: float = 0.0
