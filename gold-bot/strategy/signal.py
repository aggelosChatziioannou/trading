"""Trading signal dataclass - comprehensive for TJR strategy."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TradeSignal:
    timestamp: datetime
    direction: str           # "long" or "short"
    entry_price: float
    stop_loss: float
    take_profit_1: float     # TP1 at 1-1.5R
    take_profit_2: float     # TP2 at 2R
    take_profit_3: float     # TP3 at next key level
    session: str             # "London" or "NY"
    htf_level_swept: float   # The liquidity level that was swept
    entry_type: str          # "FVG", "OB", "BB", "EQ"
    htf_bias: str            # "bullish" or "bearish"
    confluence_score: int = 0
    confluences: list[str] = field(default_factory=list)
    risk_dollars: float = 0.0
    planned_rr: float = 0.0
