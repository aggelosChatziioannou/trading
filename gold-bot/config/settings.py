"""All trading configuration constants - TJR ICT/Smart Money Strategy."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SessionWindow:
    name: str
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int


# ── Sessions (EST / US-Eastern) ──────────────────────────────────────
ASIA_SESSION = SessionWindow("Asia", 20, 0, 0, 0)       # 8PM-12AM  (range only)
LONDON_KILLZONE = SessionWindow("London", 2, 0, 5, 0)   # 2AM-5AM  (trade)
NY_KILLZONE = SessionWindow("NY", 7, 0, 10, 0)          # 7AM-10AM (trade)

KILLZONES = [LONDON_KILLZONE, NY_KILLZONE]
ALL_SESSIONS = [ASIA_SESSION, LONDON_KILLZONE, NY_KILLZONE]

# ── Capital & Risk ───────────────────────────────────────────────────
STARTING_CAPITAL = 500.0
INITIAL_RISK_PCT = 0.005       # 0.5% risk per trade (start conservative)
MAX_RISK_PCT = 0.01            # 1% max risk per trade
MAX_POSITIONS = 1              # Max 1 position at a time
MAX_TRADES_PER_DAY = 2
MAX_DAILY_LOSS_PCT = 0.02      # 2% daily loss cap
MIN_RR = 1.5                   # Minimum R:R or skip trade
LEVERAGE = 3
COOLOFF_MINUTES = 30           # After any loss: 30-min cool-off
MAX_CONSECUTIVE_LOSSES = 2     # After 2 losses: stop for session

# Scaling rules
SCALING_TRADE_THRESHOLD = 20   # After 20 trades with good stats
SCALING_ADHERENCE_PCT = 0.80   # 80%+ adherence required
SCALING_INCREASE = 0.25        # Increase risk 25%
DRAWDOWN_REDUCE_R = 4.0        # After 4R drawdown: reduce 50%
DRAWDOWN_REDUCE_PCT = 0.50
REBUILD_TRADES = 15            # 15-trade rebuild block after reduction

# ── Multi-TP ─────────────────────────────────────────────────────────
TP1_RR = 1.5                   # Close 50% at 1-1.5R
TP1_PCT = 0.50
TP2_RR = 2.0                   # Close 30% at 2R
TP2_PCT = 0.30
TP3_PCT = 0.20                 # Trail remaining 20%

# ── Costs ────────────────────────────────────────────────────────────
SPREAD = 0.30                  # $0.30 for XAUUSD
COMMISSION_PER_LOT = 5.0       # $5 round trip per standard lot
MAX_SLIPPAGE = 0.10            # Max $0.10 random slippage

# ── ICT Parameters ───────────────────────────────────────────────────
SWING_LOOKBACK = 5             # Bars for swing detection
FVG_EXPIRY_BARS = 50           # FVGs expire after N bars
EQUAL_LEVEL_TOLERANCE = 0.50   # $ tolerance for equal highs/lows
OB_VOLUME_MULTIPLIER = 1.5     # OB volume must be > 1.5x 20-SMA
OB_RANGE_ATR_RATIO = 0.5       # OB range must be < 0.5x ATR(20)
OB_IMPULSE_MIN_MOVE = 1.0      # Minimum $ move for OB impulse
FIB_EXTENSION_79 = 0.79        # 79% Fibonacci extension

# Confluence scoring
MIN_CONFLUENCES = 3            # Minimum confluences to take trade
CONFLUENCE_WEIGHTS = {
    "liquidity_sweep": 2,      # Required
    "bos": 1,
    "choch": 1,
    "ifvg": 1,
    "smt": 1,
    "fib_79": 1,
    "fvg": 1,
    "ob": 1,
    "bb": 1,
    "eq": 1,
    "htf_bias_aligned": 1,
    "pdh_pdl_sweep": 2,
}

# ── Gold Contract ────────────────────────────────────────────────────
LOT_SIZE_OZ = 100              # 1 standard lot = 100 oz
TICK_VALUE = 0.01

# ── Timezone ─────────────────────────────────────────────────────────
TIMEZONE = "US/Eastern"
