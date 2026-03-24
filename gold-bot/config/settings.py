"""All trading configuration constants - TJR ICT/Smart Money Strategy.

v2: Theory-driven optimization — ATR-based sizing, proper killzones,
    FVG filtering, displacement confirmation.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SessionWindow:
    name: str
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int


# ── Sessions (EST / US-Eastern) ──────────────────────────────────────
# Change 5: ICT standard killzones from mentorship + CME volume data
ASIA_SESSION = SessionWindow("Asia", 20, 0, 0, 0)         # 8PM-12AM  (range only)
LONDON_KILLZONE = SessionWindow("London", 2, 0, 5, 0)     # 2AM-5AM  (trade)
NY_AM_KILLZONE = SessionWindow("NY_AM", 8, 30, 11, 0)     # 8:30-11AM (trade)
NY_PM_KILLZONE = SessionWindow("NY_PM", 13, 30, 15, 0)    # 1:30-3PM  (trade)

KILLZONES = [LONDON_KILLZONE, NY_AM_KILLZONE, NY_PM_KILLZONE]
ALL_SESSIONS = [ASIA_SESSION, LONDON_KILLZONE, NY_AM_KILLZONE, NY_PM_KILLZONE]

# Silver Bullet windows (highest-probability subsets within killzones)
LONDON_SILVER_BULLET = SessionWindow("London_SB", 3, 0, 4, 0)
NY_AM_SILVER_BULLET = SessionWindow("NY_AM_SB", 10, 0, 11, 0)
NY_PM_SILVER_BULLET = SessionWindow("NY_PM_SB", 14, 0, 15, 0)
SILVER_BULLETS = [LONDON_SILVER_BULLET, NY_AM_SILVER_BULLET, NY_PM_SILVER_BULLET]

# ── Capital & Risk ───────────────────────────────────────────────────
STARTING_CAPITAL = 500.0
INITIAL_RISK_PCT = 0.005       # 0.5% risk per trade
MAX_RISK_PCT = 0.01            # 1% max risk per trade
MAX_POSITIONS = 1              # Max 1 position at a time
# Change 8: ICT max 2 per session, 3 per day
MAX_TRADES_PER_SESSION = 2
MAX_TRADES_PER_DAY = 3
MAX_DAILY_LOSS_PCT = 0.02      # 2% daily loss cap
LEVERAGE = 3
COOLOFF_MINUTES = 30           # After any loss: 30-min cool-off
MAX_CONSECUTIVE_LOSSES = 2     # After 2 losses: stop for the day

# Change 1: ATR-based SL/TP sizing
# Theory: gold 5-min ATR ≈ $2-$5, SL must be ≥ 1.5x ATR
ATR_PERIOD = 14
SL_ATR_MULTIPLIER = 1.5        # SL = 1.5x ATR(14) from entry
MIN_SL_DISTANCE = 3.00         # Minimum $3.00 SL (floor)
# Change 7: 2-tier partial TP (50/50 split for simplicity)
TP1_RR = 2.0                   # Close 50% at 2R
TP1_PCT = 0.50
TP2_RR = 3.0                   # Close 50% at 3R
TP2_PCT = 0.50
MIN_RR = 1.5                   # Minimum planned R:R or skip trade

# Scaling rules
SCALING_TRADE_THRESHOLD = 20
SCALING_ADHERENCE_PCT = 0.80
SCALING_INCREASE = 0.25
DRAWDOWN_REDUCE_R = 4.0
DRAWDOWN_REDUCE_PCT = 0.50
REBUILD_TRADES = 15

# ── Costs (Change 10) ───────────────────────────────────────────────
# Theory: gold spread 1-1.5 pips peak, 3-5 pips off-hours
SPREAD = 0.15                  # $0.15 per side (1.5 pips, peak hours)
SLIPPAGE = 0.10                # $0.10 per trade (1 pip)
TOTAL_COST_PER_TRADE = (SPREAD + SLIPPAGE) * 2  # $0.50 round trip
COMMISSION_PER_LOT = 0.0       # Built into spread for gold
MAX_SLIPPAGE = 0.10

# ── ICT Parameters ───────────────────────────────────────────────────
SWING_LOOKBACK = 5
FVG_EXPIRY_BARS = 50

# Change 2: FVG minimum size filter
FVG_MIN_ATR_RATIO = 0.3        # FVG must be ≥ 0.3x ATR to qualify
FVG_MAX_ATR_RATIO = 3.0        # FVG must be ≤ 3.0x ATR (too large won't fill)

# Change 4: Sweep calibration for gold
SWEEP_MIN_OVERSHOOT_ATR = 0.1  # Minimum overshoot = 0.1x ATR
SWEEP_MAX_OVERSHOOT_ATR = 2.0  # Maximum overshoot = 2.0x ATR (beyond = breakout)

EQUAL_LEVEL_TOLERANCE = 0.50
OB_VOLUME_MULTIPLIER = 1.5
OB_RANGE_ATR_RATIO = 0.5
# Change 9: OB impulse must be ATR-relative
OB_IMPULSE_ATR_RATIO = 1.5     # Impulse after OB must be > 1.5x ATR
OB_IMPULSE_MIN_MOVE = 1.0      # Fallback minimum
FIB_EXTENSION_79 = 0.79

# Change 6: Displacement requirements
DISPLACEMENT_BODY_RATIO = 0.6  # Body must be > 60% of total range
DISPLACEMENT_ATR_RATIO = 1.0   # Body must be > 1.0x ATR

# Confluence scoring (theory-based categories)
MIN_CONFLUENCES = 3
CONFLUENCE_WEIGHTS = {
    "liquidity_sweep": 1,       # Reversal category
    "pdh_pdl_sweep": 1,
    "bos": 1,                   # Confirmation category
    "choch": 1,
    "ifvg": 1,
    "smt": 1,
    "fib_79": 1,
    "displacement": 1,
    "fvg": 1,                   # Continuation category
    "ob": 1,
    "ob_fvg": 1,                # OB+FVG confluence bonus
    "bb": 1,
    "eq": 1,
    "htf_bias_aligned": 1,
    "silver_bullet": 1,         # Silver bullet window bonus
}

# ── Gold Contract ────────────────────────────────────────────────────
LOT_SIZE_OZ = 100
TICK_VALUE = 0.01

# ── Timezone ─────────────────────────────────────────────────────────
TIMEZONE = "US/Eastern"
