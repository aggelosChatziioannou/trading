# Backtest Agent Prompt - Daily/Intraday Trading Strategy

## Objective

Build a complete backtest system for a **daily/intraday trading strategy** that opens and closes all positions within the same trading day. The system trades US stocks on 15-minute bars with 3 sub-strategies: Opening Range Breakout (ORB), VWAP Mean Reversion, and Gap Fade. A critical component is a **news filter** that determines whether it's safe to trade on any given day.

## Context

You are working in `/home/user/trading/trading-system/`. This is an existing trading system with strategies, risk management, and execution infrastructure already built. We are now **pivoting to daily/intraday trading** and need a backtest to validate the approach before going live.

**IMPORTANT**: We are building a system where:
- **Claude Code** (scheduled every 30 min) analyzes news and writes a signal file (YES/NO trade)
- **Python bot** reads that signal file and executes intraday trades
- For backtesting, we simulate the news filter using historical news data

### Existing codebase overview:
- `strategies/vwap_reversion.py` - VWAP strategy (adapt for backtest)
- `strategies/overnight_gap.py` - Gap fade strategy (adapt for backtest)
- `config/settings.py` - Configuration (watchlist, risk params, etc.)
- `config/risk_params.yaml` - Risk limits ($10K capital, max 5% per trade, -2% daily stop)
- `config/hypotheses.yaml` - Strategy definitions
- `analysis/intraday_strategy_research.md` - Detailed research on ORB, VWAP, Gap strategies
- `validation/` - CPCV, PBO, Deflated Sharpe validation framework

### Watchlist (from settings.py):
AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, JPM, V, JNJ, WMT, PG, HD, BAC, XOM, SPY, QQQ

## Tasks

### Task 1: Download Historical Intraday Data

Create `scripts/download_backtest_data.py`:

```python
# Download 15-min and 5-min bars for the watchlist
# Source: yfinance (free, goes back ~60 days for intraday)
#         For longer history: use daily bars from yfinance (2 years)
# Save to: data/backtest/intraday/{ticker}_15min.csv
#          data/backtest/daily/{ticker}_daily.csv

# Each CSV should have: datetime, open, high, low, close, volume
# Handle timezone: all timestamps in US/Eastern
# Add pre-market gap calculation (previous close vs today open)
```

For intraday data (15min bars), yfinance provides max ~60 days. That's fine for initial validation. For longer backtests, use daily bars to simulate gap fades and ORB (approximate with daily OHLC).

### Task 2: Download Historical News Data

Create `scripts/download_news_data.py`:

```python
# Option A: Use Finnhub API (if FINNHUB_API_KEY is set in .env)
#   - finnhub.company_news(ticker, from_date, to_date)
#   - Free tier: 1 year of news history
#   - Save to: data/backtest/news/{ticker}_news.csv
#   - Columns: date, headline, source, sentiment (if available)

# Option B: Generate synthetic news filter from price data
#   - If no API key available, use a proxy:
#   - "Unsafe" days = days with gap > 3% or VIX spike > 20%
#   - "Safe" days = everything else
#   - This is a rough approximation but allows backtest to proceed

# The output should be a daily file: data/backtest/news/daily_safety.csv
# Columns: date, trade_safe (bool), risk_level (low/medium/high), reason
```

### Task 3: Build the Backtest Engine

Create `scripts/backtest_daily.py` — the main backtest script:

```python
"""
Daily/Intraday Trading Backtest Engine

Simulates our 3-strategy daily trading approach:
1. Opening Range Breakout (ORB) - 15min range breakout
2. VWAP Mean Reversion - price deviation from VWAP
3. Gap Fade - fade overnight gaps not caused by news

Key features:
- News filter: skip trading on "unsafe" days
- Risk management: max 5% per trade, -2% daily stop, no leverage
- Position sizing: Half-Kelly or fixed fractional
- All positions closed before 15:45 ET
- Realistic slippage: 0.05% per trade
- Commission: $0 (Alpaca is commission-free)
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from pathlib import Path

# === Configuration ===
INITIAL_CAPITAL = 10_000
MAX_POSITION_PCT = 0.05      # 5% of portfolio per trade
MAX_DAILY_LOSS_PCT = -0.02   # -2% daily circuit breaker
SLIPPAGE_PCT = 0.0005        # 0.05% slippage per trade
MAX_OPEN_POSITIONS = 3       # Max simultaneous intraday positions
FORCE_CLOSE_TIME = "15:45"   # Close all positions before this time

# === ORB Strategy Parameters ===
ORB_RANGE_MINUTES = 15       # First 15 minutes define the range
ORB_MIN_RANGE_ATR = 0.3      # Minimum range size (fraction of ATR)
ORB_MAX_RANGE_ATR = 2.0      # Maximum range size (too wide = skip)
ORB_RVOL_MIN = 1.5           # Minimum relative volume for breakout
ORB_STOP_INSIDE_RANGE = True # Stop loss inside the range
ORB_TARGET_MULTIPLIER = 1.0  # Target = range height * multiplier

# === VWAP Strategy Parameters ===
VWAP_DEVIATION_ATR = 1.5     # Min deviation from VWAP in ATR units
VWAP_ADX_MAX = 30            # Max ADX (only trade in non-trending markets)
VWAP_VOLUME_MIN = 1.2        # Min volume ratio

# === Gap Fade Parameters ===
GAP_MIN_PCT = 1.5            # Minimum gap size to trade
GAP_MAX_NEWS_ARTICLES = 3    # Max news articles (more = skip, it's news-driven)
GAP_TARGET_FILL = 0.5        # Target 50% gap fill
GAP_MAX_TIME = "11:00"       # Exit if not filled by 11 AM

# === Core Engine ===

@dataclass
class Trade:
    """Record of a single trade."""
    date: str
    ticker: str
    strategy: str           # "ORB", "VWAP", "GAP"
    direction: str          # "long" or "short"
    entry_time: str
    entry_price: float
    exit_time: str
    exit_price: float
    shares: int
    pnl: float
    pnl_pct: float
    exit_reason: str        # "target", "stop", "time", "circuit_breaker"

class DailyBacktester:
    """Main backtest engine for daily/intraday strategies."""

    def __init__(self, capital=INITIAL_CAPITAL):
        self.initial_capital = capital
        self.capital = capital
        self.trades: list[Trade] = []
        self.daily_pnl: dict[str, float] = {}  # date -> daily P&L

    def run(self, tickers: list[str], start_date: str, end_date: str):
        """Run backtest across all tickers and dates."""
        # Load data
        # For each trading day:
        #   1. Check news filter (trade_safe?)
        #   2. If safe, scan for setups across all tickers
        #   3. Execute trades with risk management
        #   4. Close all positions before 15:45
        #   5. Record results
        pass

    def _check_orb_setup(self, day_bars: pd.DataFrame, daily_data: pd.DataFrame) -> dict | None:
        """
        Check for Opening Range Breakout.

        Opening Range = High/Low of first 15 minutes (9:30-9:45)
        Entry = Close above range high (long) or below range low (short)
        Filter = VWAP alignment + RVOL > 1.5
        Stop = Inside the range
        Target = Range height
        """
        pass

    def _check_vwap_setup(self, bars: pd.DataFrame) -> dict | None:
        """
        Check for VWAP mean reversion.

        Entry = Price > 1.5 ATR away from VWAP
        Filter = ADX < 30 (non-trending) + Volume ratio > 1.2
        Target = Return to VWAP
        Stop = 2 ATR from entry
        """
        pass

    def _check_gap_setup(self, today_open: float, prev_close: float,
                          news_count: int, bars: pd.DataFrame) -> dict | None:
        """
        Check for gap fade opportunity.

        Entry = Gap > 1.5% at open
        Filter = Low news count (< 3 articles) → not news-driven
        Target = 50% gap fill
        Stop = Gap expands by 50%
        Exit = By 11:00 AM regardless
        """
        pass

    def _calculate_vwap(self, bars: pd.DataFrame) -> pd.Series:
        """Calculate cumulative VWAP."""
        typical_price = (bars['high'] + bars['low'] + bars['close']) / 3
        return (typical_price * bars['volume']).cumsum() / bars['volume'].cumsum()

    def _position_size(self, price: float, stop_price: float) -> int:
        """Calculate position size based on risk."""
        risk_per_share = abs(price - stop_price)
        if risk_per_share <= 0:
            return 0
        max_position_value = self.capital * MAX_POSITION_PCT
        max_shares_by_capital = int(max_position_value / price)
        risk_amount = self.capital * 0.01  # Risk 1% per trade
        max_shares_by_risk = int(risk_amount / risk_per_share)
        return min(max_shares_by_capital, max_shares_by_risk)

    def report(self) -> dict:
        """Generate backtest report."""
        # Total return, win rate, profit factor, max drawdown,
        # Sharpe ratio, avg trade duration, trades per day
        # Compare: with news filter vs without
        pass


if __name__ == "__main__":
    bt = DailyBacktester()
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
               "META", "TSLA", "JPM", "SPY", "QQQ"]
    bt.run(tickers, start_date="2026-01-15", end_date="2026-03-20")
    results = bt.report()
```

### Task 4: Run the Backtest & Generate Report

After building the engine:

1. **Download all data** (run download scripts first)
2. **Run backtest** with news filter ON
3. **Run backtest** with news filter OFF
4. **Compare results** side by side
5. **Generate report** saved to `data/backtest/results/backtest_report.md`

The report should include:
```
=== DAILY TRADING BACKTEST RESULTS ===

Period: 2026-01-15 to 2026-03-20
Initial Capital: $10,000

--- WITH News Filter ---
Total Return: X%
Win Rate: X%
Profit Factor: X
Max Drawdown: X%
Sharpe Ratio: X
Total Trades: X
Trades/Day: X
Days Traded: X / Y total days
Days Skipped (news): X

--- WITHOUT News Filter ---
(same metrics)

--- Per Strategy ---
ORB:  Win Rate X%, Avg P&L $X, Trades X
VWAP: Win Rate X%, Avg P&L $X, Trades X
GAP:  Win Rate X%, Avg P&L $X, Trades X

--- Best/Worst Days ---
Best day: +$X (date, what happened)
Worst day: -$X (date, what happened)

--- Conclusions ---
(Auto-generated based on results)
```

### Task 5: Build Signal File System

Create `signals/` directory and the following:

**`scripts/generate_signal.py`** - Script that Claude Code scheduled task will run:
```python
"""
This script is designed to be run by a Claude Code scheduled task.
It reads the latest news analysis and writes a signal file.

For now, create the structure. The actual Claude analysis
will be added when we set up the scheduled task.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

SIGNAL_FILE = Path(__file__).parent.parent / "signals" / "news_signal.json"

def write_signal(trade_safe: bool, risk_level: str, reason: str,
                 avoid_tickers: list = None, prefer_tickers: list = None):
    signal = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trade_safe": trade_safe,
        "risk_level": risk_level,
        "reason": reason,
        "avoid_tickers": avoid_tickers or [],
        "prefer_tickers": prefer_tickers or [],
        "valid_until": (datetime.now(timezone.utc).replace(
            minute=datetime.now().minute + 35
        )).isoformat()
    }
    SIGNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    SIGNAL_FILE.write_text(json.dumps(signal, indent=2))
    return signal
```

**`scripts/read_signal.py`** - Utility for the Python bot to read signals:
```python
"""Read and validate the news signal file."""
import json
from datetime import datetime, timezone
from pathlib import Path

SIGNAL_FILE = Path(__file__).parent.parent / "signals" / "news_signal.json"
MAX_SIGNAL_AGE_MINUTES = 35

def read_signal() -> dict | None:
    if not SIGNAL_FILE.exists():
        return None
    signal = json.loads(SIGNAL_FILE.read_text())
    # Check freshness
    ts = datetime.fromisoformat(signal["timestamp"])
    age = (datetime.now(timezone.utc) - ts).total_seconds() / 60
    signal["age_minutes"] = age
    signal["is_fresh"] = age <= MAX_SIGNAL_AGE_MINUTES
    return signal
```

### Task 6: Create Claude Code Scheduled Task Prompt

Create `scheduled_prompts/news_analysis.md`:
```markdown
# Claude Code Scheduled Task: News Analysis for Trading

You are a financial news analyst for an automated daily trading system.

## Your Job
Every 30 minutes during US market hours (9:00-16:00 ET):
1. Search the web for breaking financial news
2. Assess market safety for intraday trading
3. Write your assessment to the signal file

## What makes a day UNSAFE to trade:
- FOMC meeting / Fed announcement today
- Major earnings from FAANG/mega-cap (before/after market)
- Geopolitical crisis (war escalation, sanctions)
- Market-wide circuit breaker triggered
- Major economic data release (NFP, CPI, GDP) in next 2 hours
- Black swan event

## What makes a day SAFE to trade:
- No major scheduled events
- Normal market volatility
- Regular earnings season (small/mid-cap only)
- Sector-specific news (affects 1-2 tickers, not market-wide)

## Output
Run the following command to write your signal:
```
cd /home/user/trading && python scripts/generate_signal.py
```

Or write directly to: `/home/user/trading/signals/news_signal.json`
with this format:
```json
{
  "timestamp": "<current UTC time>",
  "trade_safe": true/false,
  "risk_level": "low/medium/high",
  "reason": "Brief explanation",
  "avoid_tickers": ["TICKER1"],
  "prefer_tickers": ["TICKER2"],
  "valid_until": "<35 minutes from now>"
}
```

## Rules
- When in doubt, set trade_safe = false (capital preservation)
- If you can't access news, set trade_safe = false
- Always check: Fed calendar, earnings calendar, economic calendar
- Note specific tickers to avoid if they have earnings/news
```

## Execution Order

1. First: `python scripts/download_backtest_data.py` (get the data)
2. Second: `python scripts/download_news_data.py` (get news or generate proxy)
3. Third: `python scripts/backtest_daily.py` (run the backtest)
4. Fourth: Review results, tune parameters if needed
5. Fifth: Set up signal file system and scheduled task
6. Sixth: Paper trading with Alpaca

## Important Notes

- **NO leverage** - cash only, max 1x
- **All positions close before 15:45 ET** - no overnight risk
- **$10,000 initial capital** - keep position sizes appropriate
- **Slippage model**: 0.05% per trade (realistic for liquid large-caps)
- **Commission**: $0 (Alpaca)
- **The news filter is the KEY differentiator** - it's what makes this strategy unique. The Claude AI judgment replaces simple keyword matching.
- **Start with paper trading** before any real money
- We use **15-minute bars** as the primary timeframe for ORB and VWAP
- The **Opening Range** is defined as the first 15 minutes (9:30-9:45 ET)
