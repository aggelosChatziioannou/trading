"""
Central configuration for the trading system.

All environment variables, constants, and configuration parameters live here.
Every parameter has a comment explaining WHY that value was chosen.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from dotenv import load_dotenv

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _require_env(key: str) -> str:
    """Get required environment variable or raise."""
    val = os.getenv(key)
    if val is None:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return val


def _env(key: str, default: str = "") -> str:
    """Get optional environment variable with default."""
    return os.getenv(key, default)


# =============================================================
# Database Configuration
# =============================================================
@dataclass(frozen=True)
class DatabaseConfig:
    host: str = _env("DB_HOST", "localhost")
    port: int = int(_env("DB_PORT", "5432"))
    name: str = _env("DB_NAME", "trading")
    user: str = _env("DB_USER", "postgres")
    password: str = _env("DB_PASSWORD", "")

    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


# =============================================================
# API Keys
# =============================================================
@dataclass(frozen=True)
class APIConfig:
    finnhub_key: str = _env("FINNHUB_API_KEY", "")
    reddit_client_id: str = _env("REDDIT_CLIENT_ID", "")
    reddit_client_secret: str = _env("REDDIT_CLIENT_SECRET", "")
    reddit_user_agent: str = _env("REDDIT_USER_AGENT", "trading-system/1.0")
    anthropic_key: str = _env("ANTHROPIC_API_KEY", "")
    alpaca_key: str = _env("ALPACA_API_KEY", "")
    alpaca_secret: str = _env("ALPACA_SECRET_KEY", "")
    alpaca_base_url: str = _env("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    telegram_bot_token: str = _env("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = _env("TELEGRAM_CHAT_ID", "")


# =============================================================
# Trading Universe
# =============================================================
# High-liquidity US stocks with good news coverage + ETFs for regime detection.
# Selected for: sufficient volume, analyst coverage, news flow, and sector diversity.
WATCHLIST: list[str] = [
    # Large-cap stocks (high liquidity, rich news flow)
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "JPM", "V", "JNJ",
    "WMT", "PG", "HD", "BAC", "XOM",
    # Broad market ETFs (regime detection)
    "SPY", "QQQ", "IWM", "TLT",
    # Sector ETFs (sector rotation signals)
    "XLF", "XLK", "XLE", "XLV", "XLI",
]

# VIX is fetched separately (no WebSocket, daily only via yfinance)
REGIME_TICKERS: list[str] = ["SPY", "QQQ", "IWM", "TLT"]
VIX_TICKER: str = "^VIX"


# =============================================================
# Market Hours (US Eastern Time)
# =============================================================
@dataclass(frozen=True)
class MarketHours:
    # Regular trading session
    market_open_hour: int = 9
    market_open_minute: int = 30
    market_close_hour: int = 16
    market_close_minute: int = 0
    timezone: str = "US/Eastern"

    # Institutional activity windows (for VWAP strategy)
    # Morning: first 2 hours after open — high institutional volume
    institutional_morning_start: str = "10:00"
    institutional_morning_end: str = "11:30"
    # Afternoon: last 1.5 hours — portfolio rebalancing, MOC orders
    institutional_afternoon_start: str = "14:30"
    institutional_afternoon_end: str = "15:30"


# =============================================================
# Data Pipeline
# =============================================================
@dataclass(frozen=True)
class DataConfig:
    # Historical backfill period: 2 years provides enough data for
    # CPCV with 6 groups while covering multiple market regimes.
    backfill_years: int = 2

    # Candle timeframes to store
    timeframes: tuple[str, ...] = ("1min", "5min", "15min", "1h", "1d")

    # Bad-data filter: reject candles where close differs from previous
    # close by more than this factor. 2x catches data errors without
    # filtering legitimate moves (even circuit-breaker halts rarely exceed 50%).
    max_price_change_factor: float = 2.0

    # Raw tick retention: keep for aggregation, purge after 7 days
    # to avoid unbounded storage growth.
    tick_retention_days: int = 7

    # WebSocket reconnect parameters
    ws_reconnect_base_delay: float = 1.0   # seconds
    ws_reconnect_max_delay: float = 60.0   # seconds
    ws_reconnect_max_attempts: int = 10

    # Finnhub rate limit: 60 calls/min on free tier
    finnhub_rate_limit_per_min: int = 60

    # yfinance has no formal rate limit but we throttle to avoid blocks
    yfinance_delay_between_calls: float = 0.5  # seconds


# =============================================================
# Sentiment Configuration
# =============================================================
@dataclass(frozen=True)
class SentimentConfig:
    # FinBERT weight: fast but less nuanced
    finbert_weight: float = 0.4
    # Claude LLM weight: slower but deeper understanding of context
    llm_weight: float = 0.6

    # FinBERT model identifier (ProsusAI fine-tuned on financial text)
    finbert_model: str = "ProsusAI/finbert"

    # Claude model for sentiment scoring — Haiku for speed/cost balance
    llm_model: str = "claude-haiku-4-5-20251001"

    # Max tokens for sentiment response (JSON output is small)
    llm_max_tokens: int = 150

    # Reddit subreddits to monitor
    reddit_subreddits: tuple[str, ...] = ("wallstreetbets", "stocks", "investing")

    # RSS feed URLs for financial news
    rss_feeds: tuple[str, ...] = (
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.reuters.com/reuters/companyNews",
    )


# =============================================================
# Feature Engineering
# =============================================================
@dataclass(frozen=True)
class FeatureConfig:
    # RSI lookback: 14 is the standard Wilder period
    rsi_period: int = 14

    # MACD: 12/26/9 is the standard configuration (Appel, 1979)
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # Bollinger Bands: 20-period SMA ± 2 std devs (Bollinger, 2001)
    bb_period: int = 20
    bb_std: float = 2.0

    # ATR: 14-period is standard (Wilder, 1978)
    atr_period: int = 14

    # Volume baseline: 20-day average captures ~1 month of trading
    volume_avg_period: int = 20

    # OBV slope: 5-period captures short-term accumulation/distribution
    obv_slope_period: int = 5

    # ADX: 14-period (Wilder, 1978)
    adx_period: int = 14

    # Stochastic: 14/3/3 is standard
    stoch_k_period: int = 14
    stoch_d_period: int = 3

    # Moving averages: 9/21 for short-term, 50/200 for trend
    ema_fast: int = 9
    ema_slow: int = 21
    sma_medium: int = 50
    sma_long: int = 200

    # Rate of change periods
    roc_short: int = 5
    roc_long: int = 20

    # Keltner Channel: 20-period EMA ± 1.5 ATR (standard)
    keltner_period: int = 20
    keltner_atr_mult: float = 1.5

    # Sentiment time windows
    sentiment_short_hours: int = 4
    sentiment_medium_hours: int = 24
    sentiment_long_days: int = 7


# =============================================================
# Model Configuration (FIXED — not tuned per fold)
# =============================================================
@dataclass(frozen=True)
class ModelConfig:
    """
    LightGBM parameters are intentionally conservative to prevent overfitting.
    These are set based on general ML best practices for tabular financial data.
    Changing them requires a THEORETICAL justification, not an empirical one.
    """
    # Shallow trees to prevent memorizing noise
    max_depth: int = 5
    # Default leaf count — not tuned
    num_leaves: int = 31
    # Moderate number of trees
    n_estimators: int = 200
    # Slow learning rate for better generalization
    learning_rate: float = 0.05
    # Row subsampling: 80% prevents overfitting to specific samples
    subsample: float = 0.8
    # Feature subsampling: 80% prevents overfitting to specific features
    colsample_bytree: float = 0.8
    # Require 50+ samples per leaf — prevents fitting to small groups
    min_child_samples: int = 50
    # L1 regularization: mild sparsity
    reg_alpha: float = 0.1
    # L2 regularization: stronger smoothing
    reg_lambda: float = 1.0
    # Fixed seed for reproducibility
    random_state: int = 42

    # Target variable thresholds (return buckets)
    # These define what constitutes a meaningful move.
    # ±0.5% is roughly 1 standard deviation of daily S&P returns,
    # ±1.5% is roughly 3 standard deviations.
    return_buckets: tuple[float, ...] = (-1.5, -0.5, 0.5, 1.5)
    bucket_labels: tuple[str, ...] = ("strong_sell", "sell", "hold", "buy", "strong_buy")


# =============================================================
# Validation Configuration
# =============================================================
@dataclass(frozen=True)
class ValidationConfig:
    # CPCV: 6 groups, 2 test → C(6,2) = 15 unique paths
    # 6 groups balances granularity vs having enough data per group
    cpcv_n_groups: int = 6
    cpcv_n_test_groups: int = 2

    # Purge window: 5 trading days covers the max signal horizon
    # across all strategies (PEAD has longest at 20 days, but the
    # label is computed at entry, not exit)
    cpcv_purge_window: int = 5

    # Embargo: 2% of test size provides buffer against label leakage
    cpcv_embargo_pct: float = 0.02

    # PBO threshold: < 10% means strategy is likely robust
    pbo_max_acceptable: float = 0.10

    # Deflated Sharpe significance level
    dsr_significance: float = 0.05

    # Minimum CPCV Sharpe to consider a strategy viable
    min_cpcv_sharpe: float = 0.5


# =============================================================
# Risk Management (NON-NEGOTIABLE HARD LIMITS)
# =============================================================
@dataclass(frozen=True)
class RiskConfig:
    initial_capital: float = 10_000.0

    # Per-trade limits
    max_position_pct: float = 5.0       # Max 5% of portfolio per trade
    min_position_pct: float = 0.5       # Min position to avoid dust trades
    max_open_positions: int = 5         # Diversification across ideas
    max_daily_trades: int = 10          # Prevent overtrading (commission drag)

    # Loss circuit breakers
    max_daily_loss_pct: float = -2.0    # Day stop: prevents tilt/revenge trading
    max_weekly_loss_pct: float = -5.0   # Week stop: triggers position size reduction
    max_drawdown_pct: float = -10.0     # Hard stop: observation-only mode
    recovery_threshold_pct: float = -5.0  # Resume when drawdown recovers to -5%

    # Position sizing
    position_method: str = "half_kelly"

    # Leverage
    max_leverage: float = 1.0           # NO LEVERAGE. Cash only.

    # Sector concentration
    max_same_sector: int = 2
    max_correlation: float = 0.7

    # Paper trading duration before going live (days)
    min_paper_trading_days: int = 90


# =============================================================
# Execution Configuration
# =============================================================
@dataclass(frozen=True)
class ExecutionConfig:
    trading_mode: str = _env("TRADING_MODE", "paper")

    # Order type: limit orders for better fills
    default_order_type: str = "limit"

    # Limit order offset: place limit 0.05% from current price
    # to get filled quickly while avoiding market order slippage
    limit_offset_pct: float = 0.05

    # Order timeout: cancel unfilled orders after 5 minutes
    order_timeout_seconds: int = 300


# =============================================================
# Logging & Monitoring
# =============================================================
@dataclass(frozen=True)
class LoggingConfig:
    log_level: str = "DEBUG"
    log_dir: Path = _PROJECT_ROOT / "logs"
    json_log_dir: Path = _PROJECT_ROOT / "logs" / "signals"

    # Streamlit dashboard port
    dashboard_port: int = 8501


# =============================================================
# Aggregate Settings
# =============================================================
@dataclass(frozen=True)
class Settings:
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    api: APIConfig = field(default_factory=APIConfig)
    market_hours: MarketHours = field(default_factory=MarketHours)
    data: DataConfig = field(default_factory=DataConfig)
    sentiment: SentimentConfig = field(default_factory=SentimentConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # Project paths
    project_root: ClassVar[Path] = _PROJECT_ROOT
    config_dir: ClassVar[Path] = _PROJECT_ROOT / "config"
    data_dir: ClassVar[Path] = _PROJECT_ROOT / "data"


# Singleton instance
settings = Settings()
