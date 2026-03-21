-- Trading System Database Schema
-- TimescaleDB hypertables for time-series data

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- =============================================================
-- OHLCV Candle Data
-- =============================================================
CREATE TABLE IF NOT EXISTS candles (
    time        TIMESTAMPTZ NOT NULL,
    ticker      TEXT NOT NULL,
    open        DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION,
    volume      BIGINT,
    timeframe   TEXT NOT NULL  -- '1min', '5min', '15min', '1h', '1d'
);
SELECT create_hypertable('candles', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_candles_ticker ON candles (ticker, time DESC);
CREATE INDEX IF NOT EXISTS idx_candles_timeframe ON candles (timeframe, ticker, time DESC);

-- =============================================================
-- News Articles + Sentiment Scores
-- =============================================================
CREATE TABLE IF NOT EXISTS news (
    id          SERIAL,
    time        TIMESTAMPTZ NOT NULL,
    ticker      TEXT,
    headline    TEXT NOT NULL,
    source      TEXT,
    url         TEXT,
    sentiment_finbert   DOUBLE PRECISION,  -- [-1, +1]
    sentiment_llm       DOUBLE PRECISION,  -- [-1, +1]
    sentiment_combined  DOUBLE PRECISION,  -- weighted average
    raw_text    TEXT
);
SELECT create_hypertable('news', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_news_ticker ON news (ticker, time DESC);
CREATE INDEX IF NOT EXISTS idx_news_source ON news (source, time DESC);

-- =============================================================
-- Computed Feature Snapshots
-- =============================================================
CREATE TABLE IF NOT EXISTS features (
    time        TIMESTAMPTZ NOT NULL,
    ticker      TEXT NOT NULL,
    features    JSONB NOT NULL
);
SELECT create_hypertable('features', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_features_ticker ON features (ticker, time DESC);

-- =============================================================
-- Trade Log (every signal and execution)
-- =============================================================
CREATE TABLE IF NOT EXISTS trades (
    id              SERIAL PRIMARY KEY,
    time            TIMESTAMPTZ NOT NULL,
    ticker          TEXT NOT NULL,
    strategy        TEXT NOT NULL,
    hypothesis_id   TEXT NOT NULL,
    direction       TEXT NOT NULL,       -- 'long' or 'short'
    entry_price     DOUBLE PRECISION,
    exit_price      DOUBLE PRECISION,
    exit_time       TIMESTAMPTZ,
    pnl             DOUBLE PRECISION,
    confidence      DOUBLE PRECISION,
    position_size   DOUBLE PRECISION,
    stop_loss       DOUBLE PRECISION,
    take_profit     DOUBLE PRECISION,
    explanation     TEXT NOT NULL,        -- human-readable WHY
    status          TEXT DEFAULT 'open'   -- 'open', 'closed', 'stopped'
);

-- =============================================================
-- Hypothesis Registry (EVERY hypothesis ever tested)
-- =============================================================
CREATE TABLE IF NOT EXISTS hypotheses (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    description         TEXT NOT NULL,
    theory_basis        TEXT NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    status              TEXT DEFAULT 'active',  -- 'active', 'retired', 'failed'
    cpcv_sharpe_mean    DOUBLE PRECISION,
    cpcv_sharpe_std     DOUBLE PRECISION,
    pbo                 DOUBLE PRECISION,
    deflated_sharpe     DOUBLE PRECISION,
    notes               TEXT
);

-- =============================================================
-- Signal Log (all signals, including ones not acted upon)
-- =============================================================
CREATE TABLE IF NOT EXISTS signals (
    id              SERIAL,
    time            TIMESTAMPTZ NOT NULL,
    ticker          TEXT NOT NULL,
    strategy        TEXT NOT NULL,
    hypothesis_id   TEXT NOT NULL,
    direction       TEXT NOT NULL,
    confidence      DOUBLE PRECISION,
    acted_upon      BOOLEAN DEFAULT FALSE,
    reason_skipped  TEXT,
    features_snapshot JSONB,
    explanation     TEXT NOT NULL
);
SELECT create_hypertable('signals', 'time', if_not_exists => TRUE);

-- =============================================================
-- Risk Events Log
-- =============================================================
CREATE TABLE IF NOT EXISTS risk_events (
    id          SERIAL,
    time        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type  TEXT NOT NULL,  -- 'daily_loss_stop', 'drawdown_mode', 'position_limit', etc.
    details     JSONB NOT NULL
);
SELECT create_hypertable('risk_events', 'time', if_not_exists => TRUE);
