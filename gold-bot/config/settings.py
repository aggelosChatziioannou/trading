"""All trading configuration constants."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SessionWindow:
    name: str
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int


# Trading sessions (EST/New York timezone)
LONDON_KILLZONE = SessionWindow("London", 3, 0, 4, 0)
NY_KILLZONE = SessionWindow("NY", 9, 50, 10, 30)
ASIAN_SESSION = SessionWindow("Asian", 19, 0, 0, 0)  # 7PM-midnight EST (prev day)
LONDON_SESSION = SessionWindow("London_Full", 2, 0, 5, 0)
NY_SESSION = SessionWindow("NY_Full", 8, 0, 12, 0)

KILLZONES = [LONDON_KILLZONE, NY_KILLZONE]
SESSIONS = [ASIAN_SESSION, LONDON_SESSION, NY_SESSION]

# Risk management
STARTING_CAPITAL = 500.0
RISK_PER_TRADE = 0.01        # 1% of capital
MAX_TRADES_PER_DAY = 2
MAX_DAILY_LOSS = 0.02        # 2% of capital
LEVERAGE = 3

# Costs
SPREAD = 0.30                # $0.30 for XAUUSD
COMMISSION_PER_LOT = 5.0     # $5 round trip per standard lot
SLIPPAGE = 0.10              # $0.10 simulated slippage

# Multi-TP
TP1_RR = 1.0                 # 1:1 R:R
TP1_PCT = 0.50               # Close 50%
TP2_RR = 2.0                 # 2:1 R:R
TP2_PCT = 0.30               # Close 30%
TP3_PCT = 0.20               # Trail remaining 20%

# ICT parameters
SWING_LOOKBACK = 5           # Bars to look back for swing detection
FVG_EXPIRY_BARS = 50         # FVGs expire after N bars
EQUAL_LEVEL_TOLERANCE = 0.50 # $ tolerance for equal highs/lows
OB_IMPULSE_MIN_MOVE = 1.0    # Minimum $ move to qualify as impulse

# Gold lot sizing (1 standard lot = 100 oz)
LOT_SIZE_OZ = 100
TICK_VALUE = 0.01            # Minimum price movement

TIMEZONE = "US/Eastern"
