"""Position sizing based on risk parameters."""
from config.settings import (
    RISK_PER_TRADE, LEVERAGE, LOT_SIZE_OZ, COMMISSION_PER_LOT, SPREAD,
)


def calculate_position_size(
    capital: float,
    entry_price: float,
    stop_loss: float,
) -> dict:
    """Calculate position size in oz and lots.

    Returns dict with: lots, oz, risk_dollars, margin_required, commission.
    """
    risk_dollars = capital * RISK_PER_TRADE
    risk_per_oz = abs(entry_price - stop_loss) + SPREAD

    if risk_per_oz <= 0:
        return {"lots": 0, "oz": 0, "risk_dollars": 0, "margin_required": 0, "commission": 0}

    oz = risk_dollars / risk_per_oz
    lots = oz / LOT_SIZE_OZ

    # Check margin: margin = (lots * LOT_SIZE_OZ * entry_price) / LEVERAGE
    margin_required = (lots * LOT_SIZE_OZ * entry_price) / LEVERAGE

    # If margin exceeds capital, reduce position
    if margin_required > capital:
        lots = (capital * LEVERAGE) / (LOT_SIZE_OZ * entry_price)
        oz = lots * LOT_SIZE_OZ
        margin_required = capital

    return {
        "lots": round(lots, 4),
        "oz": round(oz, 2),
        "risk_dollars": round(risk_dollars, 2),
        "margin_required": round(margin_required, 2),
        "commission": round(lots * COMMISSION_PER_LOT, 2),
    }
