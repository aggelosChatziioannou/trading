# Gold ICT Trading Bot Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete Gold (XAUUSD) ICT/Smart Money Concepts trading bot with backtesting engine producing full performance reports.

**Architecture:** Rules-based multi-timeframe system in `gold-bot/`. ICT concepts (FVG, OB, BOS, liquidity, SMT) implemented as independent pure-function modules. Event-driven backtester processes 5-min bars, uses 1-min data for SL/TP precision. Sequential gate entry model enforces all ICT conditions.

**Tech Stack:** Python 3.10+, pandas, numpy, yfinance, matplotlib, openpyxl, pytz, pytest

---

## Chunk 1: Foundation — Config, Data, and Project Setup

### Task 1: Project Scaffold & Dependencies

**Files:**
- Create: `gold-bot/requirements.txt`
- Create: `gold-bot/config/__init__.py`
- Create: `gold-bot/config/settings.py`
- Create: `gold-bot/config/news_calendar.py`
- Create: `gold-bot/ict/__init__.py`
- Create: `gold-bot/strategy/__init__.py`
- Create: `gold-bot/risk/__init__.py`
- Create: `gold-bot/backtest/__init__.py`
- Create: `gold-bot/data/__init__.py`
- Create: `gold-bot/tests/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
pandas>=2.0.0
numpy>=1.24.0
yfinance>=0.2.30
matplotlib>=3.7.0
openpyxl>=3.1.0
pytz>=2023.3
pytest>=7.4.0
```

- [ ] **Step 2: Create config/settings.py with all constants**

```python
"""All trading configuration constants."""
from dataclasses import dataclass, field
from typing import Dict, Tuple


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
```

- [ ] **Step 3: Create config/news_calendar.py**

```python
"""High-impact news dates to avoid trading."""
from datetime import date

# 2025 H2 + 2026 H1 high-impact USD news dates
# CPI, PPI, FOMC, NFP
NEWS_BLACKOUT_DATES: set[date] = {
    # 2025
    date(2025, 7, 11),   # CPI
    date(2025, 7, 15),   # PPI
    date(2025, 7, 30),   # FOMC
    date(2025, 8, 1),    # NFP
    date(2025, 8, 12),   # CPI
    date(2025, 8, 14),   # PPI
    date(2025, 9, 5),    # NFP
    date(2025, 9, 10),   # CPI
    date(2025, 9, 11),   # PPI
    date(2025, 9, 17),   # FOMC
    date(2025, 10, 3),   # NFP
    date(2025, 10, 14),  # CPI
    date(2025, 10, 15),  # PPI
    date(2025, 10, 29),  # FOMC
    date(2025, 11, 7),   # NFP
    date(2025, 11, 12),  # CPI
    date(2025, 11, 13),  # PPI
    date(2025, 12, 5),   # NFP
    date(2025, 12, 10),  # CPI
    date(2025, 12, 11),  # PPI
    date(2025, 12, 17),  # FOMC
    # 2026
    date(2026, 1, 9),    # NFP
    date(2026, 1, 14),   # CPI
    date(2026, 1, 15),   # PPI
    date(2026, 1, 28),   # FOMC
    date(2026, 2, 6),    # NFP
    date(2026, 2, 11),   # CPI
    date(2026, 2, 12),   # PPI
    date(2026, 3, 6),    # NFP
    date(2026, 3, 11),   # CPI
    date(2026, 3, 12),   # PPI
    date(2026, 3, 18),   # FOMC
}


def is_news_blackout(d: date) -> bool:
    """Return True if the given date is a high-impact news day."""
    return d in NEWS_BLACKOUT_DATES
```

- [ ] **Step 4: Create all `__init__.py` files (empty)**

- [ ] **Step 5: Commit**
```bash
git add gold-bot/
git commit -m "feat(gold-bot): project scaffold with config, settings, news calendar"
```

---

### Task 2: Data Downloader & Manager

**Files:**
- Create: `gold-bot/data/downloader.py`
- Create: `gold-bot/data/manager.py`
- Create: `gold-bot/tests/test_data.py`

- [ ] **Step 1: Write test for downloader**

```python
"""Tests for data download and management."""
import pandas as pd
import pytest
from data.downloader import download_gold, download_dxy
from data.manager import DataManager


def test_download_gold_returns_ohlcv():
    df = download_gold(period="5d", interval="1h")
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) >= {"open", "high", "low", "close", "volume"}
    assert isinstance(df.index, pd.DatetimeIndex)
    assert len(df) > 0


def test_download_dxy_returns_ohlcv():
    df = download_dxy(period="5d", interval="1h")
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) >= {"open", "high", "low", "close"}
    assert len(df) > 0


def test_data_manager_resample():
    """Verify 1-min data can be resampled to 5m, 1H, 4H."""
    # Create fake 1-min data
    idx = pd.date_range("2025-01-02 08:00", periods=240, freq="1min")
    df = pd.DataFrame({
        "open": range(240),
        "high": [x + 1 for x in range(240)],
        "low": [x - 1 for x in range(240)],
        "close": [x + 0.5 for x in range(240)],
        "volume": [100] * 240,
    }, index=idx)

    mgr = DataManager(gold_1m=df)
    assert len(mgr.gold_5m) == 48     # 240/5
    assert len(mgr.gold_1h) == 4      # 240/60
```

- [ ] **Step 2: Run test, verify it fails**
```bash
cd gold-bot && python -m pytest tests/test_data.py -v
```

- [ ] **Step 3: Implement downloader.py**

```python
"""Download XAUUSD and DXY data from yfinance."""
import pandas as pd
import yfinance as yf


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase columns, drop Adj Close if present."""
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    df = df.drop(columns=["adj_close"], errors="ignore")
    return df


def download_gold(period: str = "7d", interval: str = "1m") -> pd.DataFrame:
    """Download Gold futures (GC=F) data."""
    df = yf.download("GC=F", period=period, interval=interval, progress=False)
    df = _normalize_columns(df)
    return df


def download_dxy(period: str = "7d", interval: str = "1m") -> pd.DataFrame:
    """Download Dollar Index (DX-Y.NYB) data."""
    df = yf.download("DX-Y.NYB", period=period, interval=interval, progress=False)
    df = _normalize_columns(df)
    return df


def load_csv(filepath: str) -> pd.DataFrame:
    """Load OHLCV data from CSV.

    Expected columns: datetime (or date), open, high, low, close, volume (optional).
    Handles MT5, TradingView, and generic CSV exports.
    """
    df = pd.read_csv(filepath, parse_dates=True, index_col=0)
    df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]
    # Ensure required columns
    for col in ["open", "high", "low", "close"]:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    if "volume" not in df.columns:
        df["volume"] = 0
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    return df
```

- [ ] **Step 4: Implement manager.py**

```python
"""Multi-timeframe data manager. Resamples 1-min data to higher timeframes."""
import pandas as pd


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample OHLCV data to a higher timeframe."""
    return df.resample(rule).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()


class DataManager:
    """Holds and manages multi-timeframe OHLCV data for Gold and optionally DXY."""

    def __init__(
        self,
        gold_1m: pd.DataFrame,
        dxy_1m: pd.DataFrame | None = None,
    ):
        self.gold_1m = gold_1m.sort_index()
        self.gold_5m = resample_ohlcv(gold_1m, "5min")
        self.gold_1h = resample_ohlcv(gold_1m, "1h")
        self.gold_4h = resample_ohlcv(gold_1m, "4h")

        self.dxy_1m = dxy_1m.sort_index() if dxy_1m is not None else None
        self.dxy_5m = resample_ohlcv(dxy_1m, "5min") if dxy_1m is not None else None

    def get_gold_slice(self, timeframe: str, end: pd.Timestamp, bars: int) -> pd.DataFrame:
        """Get the last N bars of gold data up to `end` for a given timeframe."""
        data = getattr(self, f"gold_{timeframe}")
        mask = data.index <= end
        return data[mask].tail(bars)

    def get_dxy_slice(self, end: pd.Timestamp, bars: int) -> pd.DataFrame | None:
        """Get the last N bars of DXY 5-min data up to `end`."""
        if self.dxy_5m is None:
            return None
        mask = self.dxy_5m.index <= end
        return self.dxy_5m[mask].tail(bars)
```

- [ ] **Step 5: Run tests, verify pass**
```bash
cd gold-bot && python -m pytest tests/test_data.py -v
```

- [ ] **Step 6: Commit**
```bash
git add gold-bot/data/ gold-bot/tests/test_data.py
git commit -m "feat(gold-bot): data downloader and multi-TF data manager"
```

---

## Chunk 2: ICT Concepts — Core Modules

### Task 3: Market Structure — Swings & BOS

**Files:**
- Create: `gold-bot/ict/structures.py`
- Create: `gold-bot/tests/test_structures.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for market structure detection."""
import pandas as pd
import numpy as np
import pytest
from ict.structures import find_swing_highs, find_swing_lows, detect_bos


def _make_candles(highs, lows, closes=None):
    """Helper to build a DataFrame from high/low arrays."""
    n = len(highs)
    if closes is None:
        closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    return pd.DataFrame({
        "open": closes,
        "high": highs,
        "low": lows,
        "close": closes,
    }, index=pd.date_range("2025-01-01", periods=n, freq="5min"))


def test_swing_high_detection():
    # Peak at index 5: higher than 5 bars on each side
    highs = [10, 11, 12, 13, 14, 20, 14, 13, 12, 11, 10]
    lows =  [9,  10, 11, 12, 13, 19, 13, 12, 11, 10, 9]
    df = _make_candles(highs, lows)
    swings = find_swing_highs(df, lookback=5)
    assert len(swings) == 1
    assert swings[0].price == 20


def test_swing_low_detection():
    # Trough at index 5
    highs = [20, 19, 18, 17, 16, 11, 16, 17, 18, 19, 20]
    lows =  [19, 18, 17, 16, 15, 10, 15, 16, 17, 18, 19]
    df = _make_candles(highs, lows)
    swings = find_swing_lows(df, lookback=5)
    assert len(swings) == 1
    assert swings[0].price == 10


def test_bullish_bos():
    # Price makes HH: swing high at 100, then new swing high at 105
    highs = [90, 92, 95, 98, 100, 95, 92, 90, 95, 100, 105, 100, 95]
    lows  = [88, 90, 93, 96, 98,  93, 90, 88, 93, 98,  103, 98,  93]
    df = _make_candles(highs, lows)
    bos_list = detect_bos(df, lookback=3)
    bullish = [b for b in bos_list if b.direction == "bullish"]
    assert len(bullish) >= 1


def test_bearish_bos():
    # Price makes LL: swing low at 100, then new swing low at 95
    highs = [110, 108, 105, 102, 100, 105, 108, 110, 105, 100, 95, 100, 105]
    lows  = [108, 106, 103, 100, 98,  103, 106, 108, 103, 98,  93, 98,  103]
    df = _make_candles(highs, lows)
    bos_list = detect_bos(df, lookback=3)
    bearish = [b for b in bos_list if b.direction == "bearish"]
    assert len(bearish) >= 1
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement structures.py**

```python
"""Market structure: swing highs/lows, break of structure (BOS)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass
class SwingPoint:
    timestamp: datetime
    price: float
    type: str  # "high" or "low"
    index: int  # bar index in the dataframe


@dataclass
class BOS:
    timestamp: datetime
    price: float
    direction: str  # "bullish" or "bearish"
    swing_broken: SwingPoint


def find_swing_highs(df: pd.DataFrame, lookback: int = 5) -> list[SwingPoint]:
    """Find swing highs: bar where high is highest within lookback bars on each side."""
    swings = []
    highs = df["high"].values
    for i in range(lookback, len(df) - lookback):
        window = highs[i - lookback : i + lookback + 1]
        if highs[i] == max(window) and list(window).count(highs[i]) == 1:
            swings.append(SwingPoint(
                timestamp=df.index[i],
                price=float(highs[i]),
                type="high",
                index=i,
            ))
    return swings


def find_swing_lows(df: pd.DataFrame, lookback: int = 5) -> list[SwingPoint]:
    """Find swing lows: bar where low is lowest within lookback bars on each side."""
    swings = []
    lows = df["low"].values
    for i in range(lookback, len(df) - lookback):
        window = lows[i - lookback : i + lookback + 1]
        if lows[i] == min(window) and list(window).count(lows[i]) == 1:
            swings.append(SwingPoint(
                timestamp=df.index[i],
                price=float(lows[i]),
                type="low",
                index=i,
            ))
    return swings


def find_all_swings(df: pd.DataFrame, lookback: int = 5) -> list[SwingPoint]:
    """Find all swing points sorted by time."""
    swings = find_swing_highs(df, lookback) + find_swing_lows(df, lookback)
    swings.sort(key=lambda s: s.timestamp)
    return swings


def detect_bos(df: pd.DataFrame, lookback: int = 5) -> list[BOS]:
    """Detect Break of Structure events.

    Bullish BOS: price breaks above a previous swing high.
    Bearish BOS: price breaks below a previous swing low.
    """
    swing_highs = find_swing_highs(df, lookback)
    swing_lows = find_swing_lows(df, lookback)
    bos_list = []

    # Check for bullish BOS (breaking swing highs)
    for i in range(1, len(swing_highs)):
        prev = swing_highs[i - 1]
        curr = swing_highs[i]
        if curr.price > prev.price:
            bos_list.append(BOS(
                timestamp=curr.timestamp,
                price=curr.price,
                direction="bullish",
                swing_broken=prev,
            ))

    # Check for bearish BOS (breaking swing lows)
    for i in range(1, len(swing_lows)):
        prev = swing_lows[i - 1]
        curr = swing_lows[i]
        if curr.price < prev.price:
            bos_list.append(BOS(
                timestamp=curr.timestamp,
                price=curr.price,
                direction="bearish",
                swing_broken=prev,
            ))

    bos_list.sort(key=lambda b: b.timestamp)
    return bos_list
```

- [ ] **Step 4: Run tests, verify pass**
```bash
cd gold-bot && python -m pytest tests/test_structures.py -v
```

- [ ] **Step 5: Commit**
```bash
git add gold-bot/ict/structures.py gold-bot/tests/test_structures.py
git commit -m "feat(gold-bot): market structure — swing detection and BOS"
```

---

### Task 4: Fair Value Gaps

**Files:**
- Create: `gold-bot/ict/fvg.py`
- Create: `gold-bot/tests/test_fvg.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for Fair Value Gap detection."""
import pandas as pd
from ict.fvg import detect_fvgs, FVG


def _make_candles(data):
    """data: list of (open, high, low, close) tuples."""
    df = pd.DataFrame(data, columns=["open", "high", "low", "close"])
    df.index = pd.date_range("2025-01-01", periods=len(data), freq="5min")
    df["volume"] = 100
    return df


def test_bullish_fvg():
    # Candle 0 high=100, Candle 1 big move up, Candle 2 low=102 → gap [100, 102]
    candles = [
        (98, 100, 97, 99),   # candle 0
        (100, 105, 99, 104), # candle 1 (impulse)
        (104, 107, 102, 106),# candle 2: low(102) > candle0 high(100) = bullish FVG
    ]
    df = _make_candles(candles)
    fvgs = detect_fvgs(df)
    assert len(fvgs) == 1
    assert fvgs[0].direction == "bullish"
    assert fvgs[0].top == 102  # candle 2 low
    assert fvgs[0].bottom == 100  # candle 0 high


def test_bearish_fvg():
    # Candle 0 low=100, Candle 1 big move down, Candle 2 high=98 → gap [98, 100]
    candles = [
        (102, 103, 100, 101), # candle 0
        (100, 101, 95, 96),   # candle 1 (impulse down)
        (96, 98, 94, 95),     # candle 2: high(98) < candle0 low(100) = bearish FVG
    ]
    df = _make_candles(candles)
    fvgs = detect_fvgs(df)
    assert len(fvgs) == 1
    assert fvgs[0].direction == "bearish"
    assert fvgs[0].top == 100   # candle 0 low
    assert fvgs[0].bottom == 98 # candle 2 high


def test_no_fvg_when_no_gap():
    candles = [
        (100, 102, 99, 101),
        (101, 103, 100, 102),
        (102, 104, 101, 103),  # No gap: candle2.low(101) < candle0.high(102)
    ]
    df = _make_candles(candles)
    fvgs = detect_fvgs(df)
    assert len(fvgs) == 0
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement fvg.py**

```python
"""Fair Value Gap (FVG) detection and tracking."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass
class FVG:
    timestamp: datetime    # Time of the middle candle (impulse)
    direction: str         # "bullish" or "bearish"
    top: float             # Upper bound of the gap
    bottom: float          # Lower bound of the gap
    index: int             # Bar index of the middle candle
    filled: bool = False   # Whether price has returned to fill the gap
    inverted: bool = False # Whether this FVG has been inverted (IFVG)


def detect_fvgs(df: pd.DataFrame) -> list[FVG]:
    """Detect all Fair Value Gaps in the data.

    Bullish FVG: candle[i-2].high < candle[i].low
    Bearish FVG: candle[i-2].low > candle[i].high
    """
    fvgs = []
    highs = df["high"].values
    lows = df["low"].values

    for i in range(2, len(df)):
        # Bullish FVG
        if lows[i] > highs[i - 2]:
            fvgs.append(FVG(
                timestamp=df.index[i - 1],
                direction="bullish",
                top=float(lows[i]),
                bottom=float(highs[i - 2]),
                index=i - 1,
            ))
        # Bearish FVG
        elif highs[i] < lows[i - 2]:
            fvgs.append(FVG(
                timestamp=df.index[i - 1],
                direction="bearish",
                top=float(lows[i - 2]),
                bottom=float(highs[i]),
                index=i - 1,
            ))
    return fvgs


def update_fvg_status(
    fvgs: list[FVG],
    current_bar: pd.Series,
    current_index: int,
    expiry_bars: int = 50,
) -> list[FVG]:
    """Update FVG fill/inversion status and remove expired ones.

    Returns the list of still-active FVGs.
    """
    active = []
    for fvg in fvgs:
        age = current_index - fvg.index
        if age > expiry_bars:
            continue  # Expired

        high = current_bar["high"]
        low = current_bar["low"]

        if not fvg.filled:
            # Check if price has entered the FVG zone
            if fvg.direction == "bullish" and low <= fvg.top:
                fvg.filled = True
            elif fvg.direction == "bearish" and high >= fvg.bottom:
                fvg.filled = True

        if fvg.filled and not fvg.inverted:
            # Check for inversion: price passes through and the FVG now acts as S/R
            if fvg.direction == "bullish" and low < fvg.bottom:
                fvg.inverted = True
            elif fvg.direction == "bearish" and high > fvg.top:
                fvg.inverted = True

        active.append(fvg)
    return active
```

- [ ] **Step 4: Run tests, verify pass**
- [ ] **Step 5: Commit**
```bash
git add gold-bot/ict/fvg.py gold-bot/tests/test_fvg.py
git commit -m "feat(gold-bot): Fair Value Gap detection with fill/inversion tracking"
```

---

### Task 5: Order Blocks & Breaker Blocks

**Files:**
- Create: `gold-bot/ict/order_blocks.py`
- Create: `gold-bot/tests/test_order_blocks.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for Order Block detection."""
import pandas as pd
from ict.order_blocks import detect_order_blocks, OB


def _make_candles(data):
    df = pd.DataFrame(data, columns=["open", "high", "low", "close"])
    df.index = pd.date_range("2025-01-01", periods=len(data), freq="5min")
    df["volume"] = 100
    return df


def test_bullish_ob():
    """Last bearish candle before a bullish impulse move."""
    candles = [
        (100, 101, 99, 100),   # neutral
        (100, 101, 99, 100),   # neutral
        (101, 102, 99, 99.5),  # BEARISH candle (close < open) ← this is the OB
        (100, 106, 99, 105),   # bullish impulse starts
        (105, 110, 104, 109),  # continuation up
        (109, 115, 108, 114),  # strong move up
    ]
    df = _make_candles(candles)
    obs = detect_order_blocks(df, lookback=2, impulse_min=3.0)
    bullish = [ob for ob in obs if ob.direction == "bullish"]
    assert len(bullish) >= 1
    assert bullish[0].zone_low <= 99.5  # OB body low
    assert bullish[0].zone_high >= 101  # OB body high


def test_bearish_ob():
    """Last bullish candle before a bearish impulse move."""
    candles = [
        (100, 101, 99, 100),
        (100, 101, 99, 100),
        (99, 101, 98.5, 100.5),  # BULLISH candle ← this is the OB
        (100, 101, 94, 95),      # bearish impulse
        (95, 96, 90, 91),        # continuation down
        (91, 92, 86, 87),        # strong move down
    ]
    df = _make_candles(candles)
    obs = detect_order_blocks(df, lookback=2, impulse_min=3.0)
    bearish = [ob for ob in obs if ob.direction == "bearish"]
    assert len(bearish) >= 1
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement order_blocks.py**

```python
"""Order Block (OB) and Breaker Block detection."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass
class OB:
    timestamp: datetime
    direction: str       # "bullish" or "bearish"
    zone_high: float     # Upper bound of OB (candle body high)
    zone_low: float      # Lower bound of OB (candle body low)
    index: int
    broken: bool = False # Becomes a Breaker Block if broken


def _is_bearish_candle(row: pd.Series) -> bool:
    return row["close"] < row["open"]


def _is_bullish_candle(row: pd.Series) -> bool:
    return row["close"] > row["open"]


def detect_order_blocks(
    df: pd.DataFrame,
    lookback: int = 5,
    impulse_min: float = 1.0,
) -> list[OB]:
    """Detect Order Blocks.

    Bullish OB: last bearish candle before a bullish impulse (strong up move).
    Bearish OB: last bullish candle before a bearish impulse (strong down move).

    impulse_min: minimum price move (in $) to qualify as an impulse.
    """
    obs = []
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values

    for i in range(1, len(df) - 2):
        # Check for bullish impulse starting at i+1
        impulse_move = highs[i + 1] - lows[i]
        if impulse_move >= impulse_min and closes[i + 1] > opens[i + 1]:
            # Look back for last bearish candle at or before i
            for j in range(i, max(i - lookback - 1, -1), -1):
                if closes[j] < opens[j]:  # bearish candle
                    body_high = max(opens[j], closes[j])
                    body_low = min(opens[j], closes[j])
                    obs.append(OB(
                        timestamp=df.index[j],
                        direction="bullish",
                        zone_high=float(body_high),
                        zone_low=float(body_low),
                        index=j,
                    ))
                    break

        # Check for bearish impulse starting at i+1
        impulse_move = highs[i] - lows[i + 1]
        if impulse_move >= impulse_min and closes[i + 1] < opens[i + 1]:
            # Look back for last bullish candle at or before i
            for j in range(i, max(i - lookback - 1, -1), -1):
                if closes[j] > opens[j]:  # bullish candle
                    body_high = max(opens[j], closes[j])
                    body_low = min(opens[j], closes[j])
                    obs.append(OB(
                        timestamp=df.index[j],
                        direction="bearish",
                        zone_high=float(body_high),
                        zone_low=float(body_low),
                        index=j,
                    ))
                    break
    return obs


def update_ob_status(obs: list[OB], current_bar: pd.Series) -> list[OB]:
    """Check if OBs have been broken (becoming Breaker Blocks)."""
    for ob in obs:
        if ob.broken:
            continue
        if ob.direction == "bullish" and current_bar["low"] < ob.zone_low:
            ob.broken = True  # Now a bearish Breaker Block
        elif ob.direction == "bearish" and current_bar["high"] > ob.zone_high:
            ob.broken = True  # Now a bullish Breaker Block
    return obs
```

- [ ] **Step 4: Run tests, verify pass**
- [ ] **Step 5: Commit**
```bash
git add gold-bot/ict/order_blocks.py gold-bot/tests/test_order_blocks.py
git commit -m "feat(gold-bot): Order Block and Breaker Block detection"
```

---

### Task 6: Liquidity, SMT Divergence, Equilibrium

**Files:**
- Create: `gold-bot/ict/liquidity.py`
- Create: `gold-bot/ict/smt.py`
- Create: `gold-bot/ict/equilibrium.py`

- [ ] **Step 1: Implement liquidity.py**

```python
"""Liquidity level detection: session highs/lows, equal levels, sweeps."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

import pandas as pd
import pytz

from config.settings import SESSIONS, TIMEZONE, EQUAL_LEVEL_TOLERANCE
from ict.structures import SwingPoint

ET = pytz.timezone(TIMEZONE)


@dataclass
class LiquidityLevel:
    price: float
    type: str          # "session_high", "session_low", "equal_highs", "equal_lows", "swing_high", "swing_low"
    source: str        # e.g. "London", "NY", "1H", "4H"
    timestamp: datetime
    swept: bool = False


def get_session_levels(df: pd.DataFrame) -> list[LiquidityLevel]:
    """Extract session highs/lows for Asian, London, NY sessions."""
    levels = []
    if df.index.tz is None:
        df = df.copy()
        df.index = df.index.tz_localize("UTC")

    df_et = df.copy()
    df_et.index = df_et.index.tz_convert(ET)

    for session in SESSIONS:
        for date in df_et.index.normalize().unique():
            start = date.replace(hour=session.start_hour, minute=session.start_minute)
            if session.end_hour < session.start_hour:
                end = (date + pd.Timedelta(days=1)).replace(
                    hour=session.end_hour, minute=session.end_minute
                )
            else:
                end = date.replace(hour=session.end_hour, minute=session.end_minute)

            mask = (df_et.index >= start) & (df_et.index < end)
            session_data = df_et[mask]
            if len(session_data) < 2:
                continue

            levels.append(LiquidityLevel(
                price=float(session_data["high"].max()),
                type="session_high",
                source=session.name,
                timestamp=session_data["high"].idxmax(),
            ))
            levels.append(LiquidityLevel(
                price=float(session_data["low"].min()),
                type="session_low",
                source=session.name,
                timestamp=session_data["low"].idxmin(),
            ))
    return levels


def get_swing_liquidity(swings: list[SwingPoint], source: str) -> list[LiquidityLevel]:
    """Convert swing points to liquidity levels."""
    levels = []
    for s in swings:
        levels.append(LiquidityLevel(
            price=s.price,
            type=f"swing_{s.type}",
            source=source,
            timestamp=s.timestamp,
        ))
    return levels


def find_equal_levels(
    swings: list[SwingPoint],
    tolerance: float = EQUAL_LEVEL_TOLERANCE,
) -> list[LiquidityLevel]:
    """Find equal highs/lows where 2+ swings cluster near the same price."""
    levels = []
    highs = [s for s in swings if s.type == "high"]
    lows = [s for s in swings if s.type == "low"]

    for group, ltype in [(highs, "equal_highs"), (lows, "equal_lows")]:
        used = set()
        for i, a in enumerate(group):
            if i in used:
                continue
            cluster = [a]
            for j, b in enumerate(group):
                if j != i and j not in used and abs(a.price - b.price) <= tolerance:
                    cluster.append(b)
                    used.add(j)
            if len(cluster) >= 2:
                used.add(i)
                avg_price = sum(s.price for s in cluster) / len(cluster)
                levels.append(LiquidityLevel(
                    price=avg_price,
                    type=ltype,
                    source="equal_levels",
                    timestamp=cluster[-1].timestamp,
                ))
    return levels


def check_liquidity_sweep(
    level: LiquidityLevel,
    bar: pd.Series,
) -> bool:
    """Check if a bar sweeps a liquidity level (wick beyond, close back inside)."""
    if level.swept:
        return False

    if "high" in level.type or level.type == "equal_highs":
        # Price wicks above but closes below
        if bar["high"] > level.price and bar["close"] < level.price:
            return True
    elif "low" in level.type or level.type == "equal_lows":
        # Price wicks below but closes above
        if bar["low"] < level.price and bar["close"] > level.price:
            return True
    return False
```

- [ ] **Step 2: Implement smt.py**

```python
"""SMT (Smart Money Trap) Divergence between Gold and DXY."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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

    from datetime import timedelta
    tol = timedelta(minutes=time_tolerance_minutes)

    # Bullish SMT: Gold LL, DXY fails to make HH
    for i in range(1, len(gold_lows)):
        if gold_lows[i].price >= gold_lows[i - 1].price:
            continue  # Not a lower low
        # Find corresponding DXY highs near these timestamps
        gl = gold_lows[i]
        prev_gl = gold_lows[i - 1]

        dxy_near_prev = [d for d in dxy_highs if abs((d.timestamp - prev_gl.timestamp).total_seconds()) < tol.total_seconds()]
        dxy_near_curr = [d for d in dxy_highs if abs((d.timestamp - gl.timestamp).total_seconds()) < tol.total_seconds()]

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

        dxy_near_prev = [d for d in dxy_lows if abs((d.timestamp - prev_gh.timestamp).total_seconds()) < tol.total_seconds()]
        dxy_near_curr = [d for d in dxy_lows if abs((d.timestamp - gh.timestamp).total_seconds()) < tol.total_seconds()]

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
```

- [ ] **Step 3: Implement equilibrium.py**

```python
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
```

- [ ] **Step 4: Commit**
```bash
git add gold-bot/ict/liquidity.py gold-bot/ict/smt.py gold-bot/ict/equilibrium.py
git commit -m "feat(gold-bot): liquidity levels, SMT divergence, equilibrium"
```

---

## Chunk 3: Strategy & Risk Management

### Task 7: Session Filter & Signal

**Files:**
- Create: `gold-bot/strategy/signal.py`
- Create: `gold-bot/strategy/session_filter.py`

- [ ] **Step 1: Implement signal.py**

```python
"""Trading signal dataclass."""
from __future__ import annotations

from dataclasses import dataclass, field
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
    confidence: float = 1.0  # 1.0 for all gates passed, lower if optional gates missed
    risk_dollars: float = 0.0
```

- [ ] **Step 2: Implement session_filter.py**

```python
"""Session and news filters."""
from __future__ import annotations

from datetime import datetime, date

import pytz

from config.settings import KILLZONES, TIMEZONE, SessionWindow
from config.news_calendar import is_news_blackout

ET = pytz.timezone(TIMEZONE)


def is_in_killzone(dt: datetime) -> str | None:
    """Return killzone name if dt is within a trading killzone, else None."""
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    dt_et = dt.astimezone(ET)

    for kz in KILLZONES:
        start = dt_et.replace(hour=kz.start_hour, minute=kz.start_minute, second=0, microsecond=0)
        end = dt_et.replace(hour=kz.end_hour, minute=kz.end_minute, second=0, microsecond=0)
        if start <= dt_et < end:
            return kz.name
    return None


def should_trade(dt: datetime) -> tuple[bool, str]:
    """Check if we should trade at this time.

    Returns (can_trade, reason).
    """
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    dt_et = dt.astimezone(ET)

    if is_news_blackout(dt_et.date()):
        return False, "News blackout day"

    kz = is_in_killzone(dt)
    if kz is None:
        return False, "Outside killzone"

    return True, kz
```

- [ ] **Step 3: Commit**
```bash
git add gold-bot/strategy/
git commit -m "feat(gold-bot): session filter, news filter, signal dataclass"
```

---

### Task 8: Entry Model

**Files:**
- Create: `gold-bot/strategy/entry_model.py`

- [ ] **Step 1: Implement entry_model.py**

```python
"""Multi-timeframe ICT entry model with sequential gates."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from config.settings import (
    SWING_LOOKBACK, FVG_EXPIRY_BARS, TP1_RR, TP2_RR,
    SPREAD, OB_IMPULSE_MIN_MOVE,
)
from ict.structures import find_all_swings, detect_bos, SwingPoint, BOS
from ict.fvg import detect_fvgs, update_fvg_status, FVG
from ict.order_blocks import detect_order_blocks, update_ob_status, OB
from ict.liquidity import (
    LiquidityLevel, check_liquidity_sweep,
    get_session_levels, get_swing_liquidity, find_equal_levels,
)
from ict.smt import detect_smt, SMTSignal
from ict.equilibrium import find_equilibrium, Equilibrium
from strategy.session_filter import should_trade
from strategy.signal import TradeSignal


class ICTEntryModel:
    """Stateful entry model that tracks ICT structures across bars."""

    def __init__(self):
        # HTF state
        self.htf_levels: list[LiquidityLevel] = []
        self.active_sweep: LiquidityLevel | None = None
        self.sweep_direction: str | None = None  # "bullish" or "bearish"

        # 5-min state
        self.fvgs_5m: list[FVG] = []
        self.obs_5m: list[OB] = []
        self.bos_5m: list[BOS] = []
        self.swings_5m: list[SwingPoint] = []

        # Tracking
        self.last_htf_update: datetime | None = None
        self.trades_today: int = 0
        self.current_date = None

    def update_htf_levels(
        self,
        gold_1h: pd.DataFrame,
        gold_4h: pd.DataFrame,
        gold_5m: pd.DataFrame,
    ):
        """Rebuild HTF liquidity levels from 1H/4H data + session levels."""
        self.htf_levels = []

        # Session levels from 5-min data
        self.htf_levels.extend(get_session_levels(gold_5m))

        # 1H swing levels
        swings_1h = find_all_swings(gold_1h, lookback=3)
        self.htf_levels.extend(get_swing_liquidity(swings_1h, "1H"))

        # 4H swing levels
        swings_4h = find_all_swings(gold_4h, lookback=3)
        self.htf_levels.extend(get_swing_liquidity(swings_4h, "4H"))

        # Equal levels
        self.htf_levels.extend(find_equal_levels(swings_1h))
        self.htf_levels.extend(find_equal_levels(swings_4h))

    def update_5m_structures(self, gold_5m: pd.DataFrame):
        """Update 5-min ICT structures."""
        self.swings_5m = find_all_swings(gold_5m, lookback=SWING_LOOKBACK)
        self.bos_5m = detect_bos(gold_5m, lookback=SWING_LOOKBACK)
        self.fvgs_5m = detect_fvgs(gold_5m)
        self.obs_5m = detect_order_blocks(gold_5m, impulse_min=OB_IMPULSE_MIN_MOVE)

    def check_entry(
        self,
        bar_5m: pd.Series,
        bar_idx: int,
        gold_5m_history: pd.DataFrame,
        gold_1h: pd.DataFrame,
        gold_4h: pd.DataFrame,
        capital: float,
        dxy_swings: list[SwingPoint] | None = None,
    ) -> TradeSignal | None:
        """Run all gates and return a signal if all pass."""

        dt = bar_5m.name

        # Reset daily counter
        if self.current_date != dt.date():
            self.current_date = dt.date()
            self.trades_today = 0

        # Gate 1: Session filter
        can_trade, session = should_trade(dt)
        if not can_trade:
            return None

        # Gate 2: Max trades check
        if self.trades_today >= 2:
            return None

        # Update structures periodically
        self.update_htf_levels(gold_1h, gold_4h, gold_5m_history)
        self.update_5m_structures(gold_5m_history)

        # Gate 3: HTF Liquidity sweep
        swept_level = None
        for level in self.htf_levels:
            if check_liquidity_sweep(level, bar_5m):
                level.swept = True
                swept_level = level
                break

        if swept_level is None and self.active_sweep is None:
            return None

        if swept_level is not None:
            self.active_sweep = swept_level
            # Determine expected direction after sweep
            if "high" in swept_level.type or swept_level.type == "equal_highs":
                self.sweep_direction = "bearish"  # Swept highs → expect sell
            else:
                self.sweep_direction = "bullish"  # Swept lows → expect buy

        # Gate 4: 5-min BOS in expected direction
        recent_bos = [b for b in self.bos_5m if b.direction == self.sweep_direction
                      and b.timestamp >= self.active_sweep.timestamp]
        if not recent_bos:
            return None

        latest_bos = recent_bos[-1]

        # Gate 5: Entry zone (FVG → OB → Breaker → EQ)
        entry_price = None
        entry_type = None
        sl_price = None

        # Check FVGs
        matching_fvgs = [f for f in self.fvgs_5m
                         if f.direction == self.sweep_direction
                         and not f.filled
                         and f.timestamp >= self.active_sweep.timestamp]
        if matching_fvgs:
            fvg = matching_fvgs[-1]
            if self.sweep_direction == "bullish":
                entry_price = fvg.top  # Enter at top of bullish FVG
                sl_price = fvg.bottom - SPREAD
            else:
                entry_price = fvg.bottom  # Enter at bottom of bearish FVG
                sl_price = fvg.top + SPREAD
            entry_type = "FVG"

        # Check OBs if no FVG
        if entry_price is None:
            matching_obs = [ob for ob in self.obs_5m
                           if ob.direction == self.sweep_direction
                           and not ob.broken
                           and ob.timestamp >= self.active_sweep.timestamp]
            if matching_obs:
                ob = matching_obs[-1]
                if self.sweep_direction == "bullish":
                    entry_price = ob.zone_high
                    sl_price = ob.zone_low - SPREAD
                else:
                    entry_price = ob.zone_low
                    sl_price = ob.zone_high + SPREAD
                entry_type = "OB"

        # Check Breaker Blocks
        if entry_price is None:
            breakers = [ob for ob in self.obs_5m
                        if ob.broken
                        and ob.timestamp >= self.active_sweep.timestamp]
            if breakers:
                bb = breakers[-1]
                if self.sweep_direction == "bullish" and bb.direction == "bearish":
                    entry_price = bb.zone_high
                    sl_price = bb.zone_low - SPREAD
                    entry_type = "BB"
                elif self.sweep_direction == "bearish" and bb.direction == "bullish":
                    entry_price = bb.zone_low
                    sl_price = bb.zone_high + SPREAD
                    entry_type = "BB"

        # Check Equilibrium
        if entry_price is None and latest_bos.swing_broken:
            eq = find_equilibrium(latest_bos.swing_broken, latest_bos)
            entry_price = eq.price
            if self.sweep_direction == "bullish":
                sl_price = latest_bos.swing_broken.price - SPREAD
            else:
                sl_price = latest_bos.swing_broken.price + SPREAD
            entry_type = "EQ"

        if entry_price is None:
            return None

        # Calculate TPs
        risk = abs(entry_price - sl_price)
        if self.sweep_direction == "bullish":
            tp1 = entry_price + risk * TP1_RR
            tp2 = entry_price + risk * TP2_RR
            # TP3: next HTF high level
            higher_levels = sorted(
                [l for l in self.htf_levels if l.price > entry_price and not l.swept],
                key=lambda l: l.price,
            )
            tp3 = higher_levels[0].price if higher_levels else tp2 + risk
        else:
            tp1 = entry_price - risk * TP1_RR
            tp2 = entry_price - risk * TP2_RR
            lower_levels = sorted(
                [l for l in self.htf_levels if l.price < entry_price and not l.swept],
                key=lambda l: l.price,
                reverse=True,
            )
            tp3 = lower_levels[0].price if lower_levels else tp2 - risk

        direction = "long" if self.sweep_direction == "bullish" else "short"

        # SMT divergence check (optional confidence boost)
        confidence = 1.0
        if dxy_swings:
            smt_signals = detect_smt(self.swings_5m, dxy_swings)
            matching_smt = [s for s in smt_signals
                           if s.direction == self.sweep_direction
                           and abs((s.timestamp - dt).total_seconds()) < 1800]
            if matching_smt:
                confidence = 1.2  # Bonus confidence

        self.trades_today += 1
        self.active_sweep = None
        self.sweep_direction = None

        return TradeSignal(
            timestamp=dt,
            direction=direction,
            entry_price=entry_price,
            stop_loss=sl_price,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            session=session,
            htf_level_swept=self.active_sweep.price if self.active_sweep else 0,
            entry_type=entry_type,
            confidence=confidence,
        )
```

- [ ] **Step 2: Commit**
```bash
git add gold-bot/strategy/entry_model.py
git commit -m "feat(gold-bot): multi-TF ICT entry model with sequential gates"
```

---

### Task 9: Risk Management & Position Sizing

**Files:**
- Create: `gold-bot/risk/position_sizer.py`
- Create: `gold-bot/risk/manager.py`

- [ ] **Step 1: Implement position_sizer.py**

```python
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

    Returns dict with: lots, oz, risk_dollars, margin_required.
    """
    risk_dollars = capital * RISK_PER_TRADE
    risk_per_oz = abs(entry_price - stop_loss) + SPREAD

    if risk_per_oz <= 0:
        return {"lots": 0, "oz": 0, "risk_dollars": 0, "margin_required": 0}

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
```

- [ ] **Step 2: Implement manager.py**

```python
"""Risk manager: daily limits, position tracking, multi-TP management."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from config.settings import (
    MAX_TRADES_PER_DAY, MAX_DAILY_LOSS, TP1_PCT, TP2_PCT, TP3_PCT,
    SPREAD, SLIPPAGE,
)


@dataclass
class Position:
    signal_timestamp: datetime
    direction: str          # "long" or "short"
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    total_oz: float
    session: str
    entry_type: str

    # State
    remaining_oz: float = 0
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    sl_hit: bool = False
    closed: bool = False
    exit_price: float = 0.0
    exit_time: datetime | None = None
    pnl: float = 0.0

    def __post_init__(self):
        self.remaining_oz = self.total_oz


@dataclass
class RiskManager:
    starting_capital: float
    capital: float = 0.0
    trades_today: int = 0
    daily_pnl: float = 0.0
    current_date: date | None = None
    positions: list[Position] = field(default_factory=list)
    closed_trades: list[Position] = field(default_factory=list)

    def __post_init__(self):
        self.capital = self.starting_capital

    def can_trade(self, dt: datetime) -> tuple[bool, str]:
        """Check if we can open a new trade."""
        if self.current_date != dt.date():
            self.current_date = dt.date()
            self.trades_today = 0
            self.daily_pnl = 0.0

        if self.trades_today >= MAX_TRADES_PER_DAY:
            return False, "Max trades per day reached"

        if self.daily_pnl <= -(self.starting_capital * MAX_DAILY_LOSS):
            return False, "Max daily loss reached"

        return True, "OK"

    def open_position(self, pos: Position):
        """Register a new open position."""
        self.positions.append(pos)
        self.trades_today += 1

    def update_positions(self, bar: dict) -> list[dict]:
        """Check SL/TP for all open positions using bar data.

        bar: dict with keys high, low, close, timestamp.
        Returns list of fill events.
        """
        fills = []
        high = bar["high"]
        low = bar["low"]

        for pos in self.positions:
            if pos.closed:
                continue

            # Check Stop Loss
            if pos.direction == "long" and low <= pos.stop_loss:
                pnl = (pos.stop_loss - pos.entry_price - SPREAD - SLIPPAGE) * pos.remaining_oz
                pos.pnl += pnl
                pos.sl_hit = True
                pos.closed = True
                pos.exit_price = pos.stop_loss
                pos.exit_time = bar["timestamp"]
                pos.remaining_oz = 0
                fills.append({"type": "SL", "pnl": pnl, "position": pos})
            elif pos.direction == "short" and high >= pos.stop_loss:
                pnl = (pos.entry_price - pos.stop_loss - SPREAD - SLIPPAGE) * pos.remaining_oz
                pos.pnl += pnl
                pos.sl_hit = True
                pos.closed = True
                pos.exit_price = pos.stop_loss
                pos.exit_time = bar["timestamp"]
                pos.remaining_oz = 0
                fills.append({"type": "SL", "pnl": pnl, "position": pos})

            if pos.closed:
                continue

            # Check TP1
            if not pos.tp1_hit:
                tp1_hit = (pos.direction == "long" and high >= pos.tp1) or \
                          (pos.direction == "short" and low <= pos.tp1)
                if tp1_hit:
                    close_oz = pos.total_oz * TP1_PCT
                    if pos.direction == "long":
                        pnl = (pos.tp1 - pos.entry_price - SPREAD) * close_oz
                    else:
                        pnl = (pos.entry_price - pos.tp1 - SPREAD) * close_oz
                    pos.pnl += pnl
                    pos.tp1_hit = True
                    pos.remaining_oz -= close_oz
                    # Move SL to breakeven
                    pos.stop_loss = pos.entry_price
                    fills.append({"type": "TP1", "pnl": pnl, "position": pos})

            # Check TP2
            if pos.tp1_hit and not pos.tp2_hit:
                tp2_hit = (pos.direction == "long" and high >= pos.tp2) or \
                          (pos.direction == "short" and low <= pos.tp2)
                if tp2_hit:
                    close_oz = pos.total_oz * TP2_PCT
                    if pos.direction == "long":
                        pnl = (pos.tp2 - pos.entry_price - SPREAD) * close_oz
                    else:
                        pnl = (pos.entry_price - pos.tp2 - SPREAD) * close_oz
                    pos.pnl += pnl
                    pos.tp2_hit = True
                    pos.remaining_oz -= close_oz
                    fills.append({"type": "TP2", "pnl": pnl, "position": pos})

            # Check TP3
            if pos.tp2_hit and not pos.tp3_hit:
                tp3_hit = (pos.direction == "long" and high >= pos.tp3) or \
                          (pos.direction == "short" and low <= pos.tp3)
                if tp3_hit:
                    close_oz = pos.remaining_oz
                    if pos.direction == "long":
                        pnl = (pos.tp3 - pos.entry_price - SPREAD) * close_oz
                    else:
                        pnl = (pos.entry_price - pos.tp3 - SPREAD) * close_oz
                    pos.pnl += pnl
                    pos.tp3_hit = True
                    pos.remaining_oz = 0
                    pos.closed = True
                    pos.exit_price = pos.tp3
                    pos.exit_time = bar["timestamp"]
                    fills.append({"type": "TP3", "pnl": pnl, "position": pos})

            # Close if remaining is negligible
            if pos.remaining_oz <= 0.001:
                pos.closed = True
                if pos.exit_time is None:
                    pos.exit_time = bar["timestamp"]
                    pos.exit_price = bar["close"]

        # Move closed positions
        newly_closed = [p for p in self.positions if p.closed]
        for p in newly_closed:
            commission = (p.total_oz / 100) * 5.0  # $5 per lot
            p.pnl -= commission
            self.daily_pnl += p.pnl
            self.capital += p.pnl
            self.closed_trades.append(p)
        self.positions = [p for p in self.positions if not p.closed]

        return fills
```

- [ ] **Step 3: Commit**
```bash
git add gold-bot/risk/
git commit -m "feat(gold-bot): position sizing and risk manager with multi-TP"
```

---

## Chunk 4: Backtest Engine & Reports

### Task 10: Backtest Engine

**Files:**
- Create: `gold-bot/backtest/engine.py`

- [ ] **Step 1: Implement engine.py**

```python
"""Event-driven backtesting engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from config.settings import STARTING_CAPITAL
from data.manager import DataManager
from strategy.entry_model import ICTEntryModel
from risk.position_sizer import calculate_position_size
from risk.manager import RiskManager, Position
from ict.structures import find_all_swings


@dataclass
class BacktestResult:
    trades: list[Position]
    equity_curve: list[dict]  # [{timestamp, equity}]
    starting_capital: float
    ending_capital: float


def run_backtest(
    data: DataManager,
    capital: float = STARTING_CAPITAL,
) -> BacktestResult:
    """Run the ICT strategy backtest on the provided data.

    Iterates through 5-min bars. At each bar:
    1. Update risk manager positions using 1-min sub-bars
    2. Check entry model for new signals
    3. Size position and open trade if signal generated
    """
    model = ICTEntryModel()
    risk_mgr = RiskManager(starting_capital=capital)
    equity_curve = []

    bars_5m = data.gold_5m
    bars_1m = data.gold_1m
    bars_1h = data.gold_1h
    bars_4h = data.gold_4h

    # Pre-compute DXY swings if available
    dxy_swings = None
    if data.dxy_5m is not None:
        dxy_swings = find_all_swings(data.dxy_5m, lookback=5)

    for i in range(50, len(bars_5m)):  # Start at 50 to have enough history
        bar = bars_5m.iloc[i]
        bar_time = bars_5m.index[i]

        # Get 1-min bars within this 5-min bar for precise SL/TP checking
        next_time = bars_5m.index[i + 1] if i + 1 < len(bars_5m) else bar_time + pd.Timedelta(minutes=5)
        sub_bars = bars_1m[(bars_1m.index >= bar_time) & (bars_1m.index < next_time)]

        # Update positions with 1-min precision
        for _, sub_bar in sub_bars.iterrows():
            risk_mgr.update_positions({
                "high": sub_bar["high"],
                "low": sub_bar["low"],
                "close": sub_bar["close"],
                "timestamp": sub_bar.name,
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

        # Slice history up to current bar (no lookahead)
        history_5m = bars_5m.iloc[max(0, i - 200) : i + 1]
        history_1h = bars_1h[bars_1h.index <= bar_time].tail(100)
        history_4h = bars_4h[bars_4h.index <= bar_time].tail(50)

        signal = model.check_entry(
            bar_5m=bar,
            bar_idx=i,
            gold_5m_history=history_5m,
            gold_1h=history_1h,
            gold_4h=history_4h,
            capital=risk_mgr.capital,
            dxy_swings=dxy_swings,
        )

        if signal is None:
            continue

        # Size position
        sizing = calculate_position_size(
            capital=risk_mgr.capital,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
        )

        if sizing["oz"] <= 0:
            continue

        # Open position
        pos = Position(
            signal_timestamp=signal.timestamp,
            direction=signal.direction,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            tp1=signal.take_profit_1,
            tp2=signal.take_profit_2,
            tp3=signal.take_profit_3,
            total_oz=sizing["oz"],
            session=signal.session,
            entry_type=signal.entry_type,
        )
        risk_mgr.open_position(pos)

    # Close any remaining open positions at last price
    if risk_mgr.positions:
        last_price = bars_5m.iloc[-1]["close"]
        last_time = bars_5m.index[-1]
        for pos in risk_mgr.positions:
            if pos.direction == "long":
                pos.pnl += (last_price - pos.entry_price) * pos.remaining_oz
            else:
                pos.pnl += (pos.entry_price - last_price) * pos.remaining_oz
            pos.closed = True
            pos.exit_price = last_price
            pos.exit_time = last_time
            risk_mgr.closed_trades.append(pos)
            risk_mgr.capital += pos.pnl

    return BacktestResult(
        trades=risk_mgr.closed_trades,
        equity_curve=equity_curve,
        starting_capital=capital,
        ending_capital=risk_mgr.capital,
    )


def _unrealized_pnl(pos: Position, current_price: float) -> float:
    if pos.direction == "long":
        return (current_price - pos.entry_price) * pos.remaining_oz
    else:
        return (pos.entry_price - current_price) * pos.remaining_oz
```

- [ ] **Step 2: Commit**
```bash
git add gold-bot/backtest/engine.py
git commit -m "feat(gold-bot): event-driven backtest engine with 1-min precision"
```

---

### Task 11: Metrics & Report Generation

**Files:**
- Create: `gold-bot/backtest/metrics.py`
- Create: `gold-bot/backtest/report.py`

- [ ] **Step 1: Implement metrics.py**

```python
"""Backtest performance metrics."""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtest.engine import BacktestResult
from risk.manager import Position


def compute_metrics(result: BacktestResult) -> dict:
    """Compute all performance metrics from backtest results."""
    trades = result.trades
    if not trades:
        return {"error": "No trades generated"}

    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    # Basic stats
    total_trades = len(trades)
    win_rate = len(wins) / total_trades if total_trades > 0 else 0

    # Profit Factor
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # R:R achieved
    rr_ratios = []
    for t in trades:
        risk = abs(t.entry_price - t.stop_loss) * t.total_oz
        if risk > 0 and t.pnl != 0:
            rr_ratios.append(t.pnl / risk)
    avg_rr = np.mean(rr_ratios) if rr_ratios else 0

    # Equity curve for Sharpe & Drawdown
    eq = pd.DataFrame(result.equity_curve)
    if len(eq) > 1:
        eq["returns"] = eq["equity"].pct_change().dropna()
        sharpe = (eq["returns"].mean() / eq["returns"].std() * np.sqrt(252 * 78)) if eq["returns"].std() > 0 else 0

        # Max drawdown
        peak = eq["equity"].expanding().max()
        drawdown = (eq["equity"] - peak) / peak
        max_drawdown = drawdown.min()
    else:
        sharpe = 0
        max_drawdown = 0

    # Session breakdown
    london_trades = [t for t in trades if t.session == "London"]
    ny_trades = [t for t in trades if t.session == "NY"]

    london_pnl = sum(t.pnl for t in london_trades)
    ny_pnl = sum(t.pnl for t in ny_trades)
    london_wr = len([t for t in london_trades if t.pnl > 0]) / len(london_trades) if london_trades else 0
    ny_wr = len([t for t in ny_trades if t.pnl > 0]) / len(ny_trades) if ny_trades else 0

    # TP hit rates
    tp1_hits = sum(1 for t in trades if t.tp1_hit)
    tp2_hits = sum(1 for t in trades if t.tp2_hit)
    tp3_hits = sum(1 for t in trades if t.tp3_hit)

    # Monthly P&L
    monthly_pnl = {}
    for t in trades:
        month_key = t.signal_timestamp.strftime("%Y-%m")
        monthly_pnl[month_key] = monthly_pnl.get(month_key, 0) + t.pnl

    # Trades per week
    if trades:
        first = min(t.signal_timestamp for t in trades)
        last = max(t.signal_timestamp for t in trades)
        weeks = max((last - first).days / 7, 1)
        trades_per_week = total_trades / weeks
    else:
        trades_per_week = 0

    # Entry type breakdown
    entry_types = {}
    for t in trades:
        et = t.entry_type
        if et not in entry_types:
            entry_types[et] = {"count": 0, "pnl": 0, "wins": 0}
        entry_types[et]["count"] += 1
        entry_types[et]["pnl"] += t.pnl
        if t.pnl > 0:
            entry_types[et]["wins"] += 1

    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate * 100, 1),
        "profit_factor": round(profit_factor, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_drawdown * 100, 1),
        "avg_rr": round(avg_rr, 2),
        "total_pnl": round(sum(pnls), 2),
        "starting_capital": result.starting_capital,
        "ending_capital": round(result.ending_capital, 2),
        "return_pct": round((result.ending_capital / result.starting_capital - 1) * 100, 1),
        "london_pnl": round(london_pnl, 2),
        "london_trades": len(london_trades),
        "london_win_rate": round(london_wr * 100, 1),
        "ny_pnl": round(ny_pnl, 2),
        "ny_trades": len(ny_trades),
        "ny_win_rate": round(ny_wr * 100, 1),
        "tp1_hit_rate": round(tp1_hits / total_trades * 100, 1) if total_trades else 0,
        "tp2_hit_rate": round(tp2_hits / total_trades * 100, 1) if total_trades else 0,
        "tp3_hit_rate": round(tp3_hits / total_trades * 100, 1) if total_trades else 0,
        "trades_per_week": round(trades_per_week, 1),
        "monthly_pnl": monthly_pnl,
        "entry_types": entry_types,
        "avg_win": round(np.mean(wins), 2) if wins else 0,
        "avg_loss": round(np.mean(losses), 2) if losses else 0,
        "best_trade": round(max(pnls), 2) if pnls else 0,
        "worst_trade": round(min(pnls), 2) if pnls else 0,
    }
```

- [ ] **Step 2: Implement report.py**

```python
"""Generate backtest reports: equity curve, trade log, metrics summary."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np

from backtest.engine import BacktestResult
from backtest.metrics import compute_metrics


def generate_report(result: BacktestResult, output_dir: str = "results") -> dict:
    """Generate full backtest report: charts, Excel trade log, metrics summary."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    metrics = compute_metrics(result)

    if "error" in metrics:
        print(f"No trades to report: {metrics['error']}")
        return metrics

    # 1. Print metrics summary
    _print_summary(metrics)

    # 2. Equity curve chart
    _plot_equity_curve(result, out / "equity_curve.png")

    # 3. Monthly P&L chart
    _plot_monthly_pnl(metrics["monthly_pnl"], out / "monthly_pnl.png")

    # 4. Trade log to Excel
    _export_trade_log(result.trades, out / "trade_log.xlsx")

    print(f"\nReport saved to {out.resolve()}")
    return metrics


def _print_summary(m: dict):
    print("\n" + "=" * 60)
    print("        GOLD ICT BOT — BACKTEST RESULTS")
    print("=" * 60)
    print(f"  Starting Capital:   ${m['starting_capital']:,.2f}")
    print(f"  Ending Capital:     ${m['ending_capital']:,.2f}")
    print(f"  Total Return:       {m['return_pct']}%")
    print(f"  Total P&L:          ${m['total_pnl']:,.2f}")
    print("-" * 60)
    print(f"  Total Trades:       {m['total_trades']}")
    print(f"  Win Rate:           {m['win_rate']}%")
    print(f"  Profit Factor:      {m['profit_factor']}")
    print(f"  Sharpe Ratio:       {m['sharpe_ratio']}")
    print(f"  Max Drawdown:       {m['max_drawdown_pct']}%")
    print(f"  Avg R:R:            {m['avg_rr']}")
    print(f"  Trades/Week:        {m['trades_per_week']}")
    print("-" * 60)
    print(f"  Avg Win:            ${m['avg_win']:,.2f}")
    print(f"  Avg Loss:           ${m['avg_loss']:,.2f}")
    print(f"  Best Trade:         ${m['best_trade']:,.2f}")
    print(f"  Worst Trade:        ${m['worst_trade']:,.2f}")
    print("-" * 60)
    print("  SESSION BREAKDOWN:")
    print(f"    London:  {m['london_trades']} trades, ${m['london_pnl']:,.2f} P&L, {m['london_win_rate']}% WR")
    print(f"    NY:      {m['ny_trades']} trades, ${m['ny_pnl']:,.2f} P&L, {m['ny_win_rate']}% WR")
    print("-" * 60)
    print("  TP HIT RATES:")
    print(f"    TP1 (1:1 R:R):   {m['tp1_hit_rate']}%")
    print(f"    TP2 (2:1 R:R):   {m['tp2_hit_rate']}%")
    print(f"    TP3 (Key Level): {m['tp3_hit_rate']}%")
    print("-" * 60)
    print("  ENTRY TYPE BREAKDOWN:")
    for et, stats in m.get("entry_types", {}).items():
        wr = round(stats["wins"] / stats["count"] * 100, 1) if stats["count"] > 0 else 0
        print(f"    {et}: {stats['count']} trades, ${stats['pnl']:,.2f} P&L, {wr}% WR")
    print("-" * 60)
    print("  MONTHLY P&L:")
    for month, pnl in sorted(m.get("monthly_pnl", {}).items()):
        bar = "+" * int(abs(pnl) / 5) if pnl > 0 else "-" * int(abs(pnl) / 5)
        print(f"    {month}: ${pnl:>8,.2f}  {bar}")
    print("=" * 60)


def _plot_equity_curve(result: BacktestResult, filepath: Path):
    eq = pd.DataFrame(result.equity_curve)
    eq["timestamp"] = pd.to_datetime(eq["timestamp"])

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={"height_ratios": [3, 1]})

    ax1.plot(eq["timestamp"], eq["equity"], color="#2196F3", linewidth=1.5)
    ax1.axhline(y=result.starting_capital, color="gray", linestyle="--", alpha=0.5)
    ax1.fill_between(eq["timestamp"], result.starting_capital, eq["equity"],
                     where=eq["equity"] >= result.starting_capital, alpha=0.2, color="green")
    ax1.fill_between(eq["timestamp"], result.starting_capital, eq["equity"],
                     where=eq["equity"] < result.starting_capital, alpha=0.2, color="red")
    ax1.set_title("Gold ICT Bot — Equity Curve", fontsize=14, fontweight="bold")
    ax1.set_ylabel("Equity ($)")
    ax1.grid(True, alpha=0.3)

    # Drawdown subplot
    peak = eq["equity"].expanding().max()
    dd = (eq["equity"] - peak) / peak * 100
    ax2.fill_between(eq["timestamp"], dd, 0, color="red", alpha=0.3)
    ax2.set_ylabel("Drawdown (%)")
    ax2.set_xlabel("Date")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Equity curve saved: {filepath}")


def _plot_monthly_pnl(monthly_pnl: dict, filepath: Path):
    if not monthly_pnl:
        return

    months = sorted(monthly_pnl.keys())
    pnls = [monthly_pnl[m] for m in months]
    colors = ["green" if p > 0 else "red" for p in pnls]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(months, pnls, color=colors, alpha=0.7, edgecolor="black", linewidth=0.5)
    ax.axhline(y=0, color="black", linewidth=0.5)
    ax.set_title("Monthly P&L", fontsize=14, fontweight="bold")
    ax.set_ylabel("P&L ($)")
    ax.grid(True, alpha=0.3, axis="y")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Monthly P&L chart saved: {filepath}")


def _export_trade_log(trades: list, filepath: Path):
    rows = []
    for t in trades:
        risk = abs(t.entry_price - t.stop_loss)
        rr = t.pnl / (risk * t.total_oz) if risk > 0 and t.total_oz > 0 else 0
        rows.append({
            "Entry Time": t.signal_timestamp,
            "Exit Time": t.exit_time,
            "Direction": t.direction,
            "Session": t.session,
            "Entry Type": t.entry_type,
            "Entry Price": round(t.entry_price, 2),
            "Stop Loss": round(t.stop_loss, 2),
            "TP1": round(t.tp1, 2),
            "TP2": round(t.tp2, 2),
            "TP3": round(t.tp3, 2),
            "Exit Price": round(t.exit_price, 2),
            "Size (oz)": round(t.total_oz, 2),
            "P&L ($)": round(t.pnl, 2),
            "R:R Achieved": round(rr, 2),
            "TP1 Hit": t.tp1_hit,
            "TP2 Hit": t.tp2_hit,
            "TP3 Hit": t.tp3_hit,
            "SL Hit": t.sl_hit,
        })

    df = pd.DataFrame(rows)
    df.to_excel(filepath, index=False, sheet_name="Trade Log")
    print(f"  Trade log saved: {filepath}")
```

- [ ] **Step 3: Commit**
```bash
git add gold-bot/backtest/metrics.py gold-bot/backtest/report.py
git commit -m "feat(gold-bot): metrics calculator and report generator"
```

---

### Task 12: Main Entry Point & Integration Test

**Files:**
- Create: `gold-bot/main.py`
- Create: `gold-bot/tests/test_backtest.py`

- [ ] **Step 1: Implement main.py**

```python
"""Gold ICT Trading Bot — Main entry point."""
import argparse
import sys
from pathlib import Path

# Add gold-bot to path
sys.path.insert(0, str(Path(__file__).parent))

from data.downloader import download_gold, download_dxy, load_csv
from data.manager import DataManager
from backtest.engine import run_backtest
from backtest.report import generate_report
from config.settings import STARTING_CAPITAL


def main():
    parser = argparse.ArgumentParser(description="Gold ICT Trading Bot")
    parser.add_argument("--capital", type=float, default=STARTING_CAPITAL,
                        help="Starting capital (default: $500)")
    parser.add_argument("--gold-csv", type=str, default=None,
                        help="Path to Gold 1-min CSV data")
    parser.add_argument("--dxy-csv", type=str, default=None,
                        help="Path to DXY 1-min CSV data")
    parser.add_argument("--period", type=str, default="7d",
                        help="yfinance download period (default: 7d)")
    parser.add_argument("--output", type=str, default="results",
                        help="Output directory for reports")
    args = parser.parse_args()

    print("=" * 60)
    print("  GOLD ICT TRADING BOT — BACKTEST MODE")
    print("=" * 60)

    # Load data
    if args.gold_csv:
        print(f"Loading Gold data from CSV: {args.gold_csv}")
        gold_1m = load_csv(args.gold_csv)
    else:
        print(f"Downloading Gold data (period={args.period})...")
        gold_1m = download_gold(period=args.period, interval="1m")

    dxy_1m = None
    if args.dxy_csv:
        print(f"Loading DXY data from CSV: {args.dxy_csv}")
        dxy_1m = load_csv(args.dxy_csv)
    else:
        try:
            print(f"Downloading DXY data (period={args.period})...")
            dxy_1m = download_dxy(period=args.period, interval="1m")
            if dxy_1m.empty:
                dxy_1m = None
                print("  DXY data empty, continuing without SMT divergence")
        except Exception as e:
            print(f"  DXY download failed ({e}), continuing without SMT divergence")

    print(f"Gold data: {len(gold_1m)} bars ({gold_1m.index[0]} to {gold_1m.index[-1]})")
    if dxy_1m is not None:
        print(f"DXY data: {len(dxy_1m)} bars")

    # Build multi-TF data
    data = DataManager(gold_1m=gold_1m, dxy_1m=dxy_1m)
    print(f"Timeframes: 1m={len(data.gold_1m)}, 5m={len(data.gold_5m)}, "
          f"1H={len(data.gold_1h)}, 4H={len(data.gold_4h)}")

    # Run backtest
    print(f"\nRunning backtest with ${args.capital:,.2f} capital...")
    result = run_backtest(data, capital=args.capital)

    # Generate report
    metrics = generate_report(result, output_dir=args.output)

    return metrics


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create integration test**

```python
"""Integration test for the backtest engine."""
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.manager import DataManager
from backtest.engine import run_backtest


def test_backtest_runs_without_error():
    """Smoke test: backtest completes on synthetic data."""
    np.random.seed(42)
    n = 5000  # ~3.5 days of 1-min data

    # Generate random walk price data around $2000
    returns = np.random.normal(0, 0.0002, n)
    prices = 2000 * np.cumprod(1 + returns)

    idx = pd.date_range("2025-09-15 00:00", periods=n, freq="1min", tz="UTC")
    gold_1m = pd.DataFrame({
        "open": prices,
        "high": prices * (1 + np.random.uniform(0, 0.001, n)),
        "low": prices * (1 - np.random.uniform(0, 0.001, n)),
        "close": prices * (1 + np.random.normal(0, 0.0001, n)),
        "volume": np.random.randint(100, 10000, n),
    }, index=idx)

    data = DataManager(gold_1m=gold_1m)
    result = run_backtest(data, capital=500)

    assert result.starting_capital == 500
    assert result.ending_capital > 0
    assert len(result.equity_curve) > 0
```

- [ ] **Step 3: Run integration test**
```bash
cd gold-bot && python -m pytest tests/test_backtest.py -v
```

- [ ] **Step 4: Commit**
```bash
git add gold-bot/main.py gold-bot/tests/test_backtest.py
git commit -m "feat(gold-bot): main CLI entry point and integration test"
```

---

## Execution Order Summary

| Task | Component | Dependencies |
|------|-----------|-------------|
| 1 | Project scaffold & config | None |
| 2 | Data downloader & manager | Task 1 |
| 3 | Market structure (swings, BOS) | Task 1 |
| 4 | Fair Value Gaps | Task 1 |
| 5 | Order Blocks | Task 1 |
| 6 | Liquidity, SMT, Equilibrium | Tasks 1, 3 |
| 7 | Session filter & signal | Task 1 |
| 8 | Entry model | Tasks 3-7 |
| 9 | Risk management | Task 1 |
| 10 | Backtest engine | Tasks 2, 8, 9 |
| 11 | Metrics & reports | Task 10 |
| 12 | Main CLI & integration test | All |

**Parallelizable:** Tasks 3, 4, 5 can run in parallel. Tasks 2 and 7 can run in parallel.
