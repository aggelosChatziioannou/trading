"""
TimescaleDB connection and query helpers.

Provides connection pooling, table operations, and typed query methods
for all tables in the trading system schema.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Generator

import pandas as pd
import psycopg2
import psycopg2.extras
import psycopg2.pool

from config.settings import settings

logger = logging.getLogger(__name__)


class TimescaleDB:
    """
    Connection manager for TimescaleDB.

    Uses a connection pool to handle concurrent access from data ingestion,
    feature computation, and trading execution threads.
    """

    def __init__(
        self,
        min_connections: int = 2,
        max_connections: int = 10,
    ) -> None:
        self._pool: psycopg2.pool.ThreadedConnectionPool | None = None
        self._min_conn = min_connections
        self._max_conn = max_connections

    def connect(self) -> None:
        """Initialize the connection pool."""
        if self._pool is not None:
            return
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            self._min_conn,
            self._max_conn,
            host=settings.db.host,
            port=settings.db.port,
            dbname=settings.db.name,
            user=settings.db.user,
            password=settings.db.password,
        )
        logger.info(
            "Connected to TimescaleDB at %s:%s/%s",
            settings.db.host,
            settings.db.port,
            settings.db.name,
        )

    def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None
            logger.info("Closed all TimescaleDB connections")

    @contextmanager
    def get_conn(self) -> Generator[Any, None, None]:
        """Get a connection from the pool (context manager)."""
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    @contextmanager
    def get_cursor(self) -> Generator[Any, None, None]:
        """Get a cursor with automatic connection management."""
        with self.get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur

    # =============================================================
    # Candle Operations
    # =============================================================

    def insert_candles(self, candles: list[dict]) -> int:
        """
        Bulk insert OHLCV candles.

        Args:
            candles: List of dicts with keys:
                time, ticker, open, high, low, close, volume, timeframe

        Returns:
            Number of rows inserted.
        """
        if not candles:
            return 0

        sql = """
            INSERT INTO candles (time, ticker, open, high, low, close, volume, timeframe)
            VALUES (%(time)s, %(ticker)s, %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s, %(timeframe)s)
            ON CONFLICT DO NOTHING
        """
        with self.get_conn() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, sql, candles, page_size=1000)
                count = cur.rowcount
        logger.debug("Inserted %d candles", count)
        return count

    def get_candles(
        self,
        ticker: str,
        timeframe: str = "1d",
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candles as a DataFrame.

        Args:
            ticker: Stock symbol.
            timeframe: Candle period ('1min', '5min', '15min', '1h', '1d').
            start: Start time (inclusive).
            end: End time (inclusive).
            limit: Maximum rows to return.

        Returns:
            DataFrame with columns: time, open, high, low, close, volume.
            Indexed by time, sorted ascending.
        """
        conditions = ["ticker = %s", "timeframe = %s"]
        params: list[Any] = [ticker, timeframe]

        if start is not None:
            conditions.append("time >= %s")
            params.append(start)
        if end is not None:
            conditions.append("time <= %s")
            params.append(end)

        where = " AND ".join(conditions)
        sql = f"SELECT time, open, high, low, close, volume FROM candles WHERE {where} ORDER BY time ASC"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"

        with self.get_conn() as conn:
            df = pd.read_sql(sql, conn, params=params, parse_dates=["time"])

        if not df.empty:
            df.set_index("time", inplace=True)
        return df

    def get_latest_candle_time(self, ticker: str, timeframe: str = "1d") -> datetime | None:
        """Get the most recent candle timestamp for gap detection."""
        sql = """
            SELECT MAX(time) as latest
            FROM candles
            WHERE ticker = %s AND timeframe = %s
        """
        with self.get_cursor() as cur:
            cur.execute(sql, (ticker, timeframe))
            row = cur.fetchone()
            return row["latest"] if row and row["latest"] else None

    # =============================================================
    # News Operations
    # =============================================================

    def insert_news(self, articles: list[dict]) -> int:
        """
        Bulk insert news articles.

        Args:
            articles: List of dicts with keys:
                time, ticker, headline, source, url, raw_text,
                sentiment_finbert, sentiment_llm, sentiment_combined
        """
        if not articles:
            return 0

        sql = """
            INSERT INTO news (time, ticker, headline, source, url, raw_text,
                            sentiment_finbert, sentiment_llm, sentiment_combined)
            VALUES (%(time)s, %(ticker)s, %(headline)s, %(source)s, %(url)s, %(raw_text)s,
                    %(sentiment_finbert)s, %(sentiment_llm)s, %(sentiment_combined)s)
        """
        with self.get_conn() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, sql, articles, page_size=500)
                count = cur.rowcount
        logger.debug("Inserted %d news articles", count)
        return count

    def get_news(
        self,
        ticker: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Fetch news articles for a ticker as DataFrame."""
        conditions = ["ticker = %s"]
        params: list[Any] = [ticker]

        if start is not None:
            conditions.append("time >= %s")
            params.append(start)
        if end is not None:
            conditions.append("time <= %s")
            params.append(end)

        where = " AND ".join(conditions)
        sql = f"""
            SELECT time, headline, source, url, sentiment_finbert,
                   sentiment_llm, sentiment_combined, raw_text
            FROM news WHERE {where} ORDER BY time ASC
        """
        if limit is not None:
            sql += f" LIMIT {int(limit)}"

        with self.get_conn() as conn:
            df = pd.read_sql(sql, conn, params=params, parse_dates=["time"])
        return df

    # =============================================================
    # Feature Operations
    # =============================================================

    def insert_features(self, ticker: str, time: datetime, features: dict) -> None:
        """Store a feature snapshot."""
        sql = """
            INSERT INTO features (time, ticker, features)
            VALUES (%s, %s, %s)
        """
        with self.get_cursor() as cur:
            cur.execute(sql, (time, ticker, json.dumps(features)))

    def get_features(
        self,
        ticker: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """Fetch feature snapshots, expanding JSONB into columns."""
        conditions = ["ticker = %s"]
        params: list[Any] = [ticker]

        if start is not None:
            conditions.append("time >= %s")
            params.append(start)
        if end is not None:
            conditions.append("time <= %s")
            params.append(end)

        where = " AND ".join(conditions)
        sql = f"SELECT time, features FROM features WHERE {where} ORDER BY time ASC"

        with self.get_conn() as conn:
            df = pd.read_sql(sql, conn, params=params, parse_dates=["time"])

        if not df.empty:
            features_expanded = pd.json_normalize(df["features"])
            features_expanded.index = df.index
            df = pd.concat([df[["time"]], features_expanded], axis=1)
            df.set_index("time", inplace=True)
        return df

    # =============================================================
    # Trade Operations
    # =============================================================

    def insert_trade(self, trade: dict) -> int:
        """Insert a trade record. Returns the trade ID."""
        sql = """
            INSERT INTO trades (time, ticker, strategy, hypothesis_id, direction,
                              entry_price, confidence, position_size, stop_loss,
                              take_profit, explanation, status)
            VALUES (%(time)s, %(ticker)s, %(strategy)s, %(hypothesis_id)s, %(direction)s,
                    %(entry_price)s, %(confidence)s, %(position_size)s, %(stop_loss)s,
                    %(take_profit)s, %(explanation)s, %(status)s)
            RETURNING id
        """
        with self.get_cursor() as cur:
            cur.execute(sql, trade)
            row = cur.fetchone()
            return row["id"]

    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        exit_time: datetime,
        pnl: float,
        status: str = "closed",
    ) -> None:
        """Update a trade with exit information."""
        sql = """
            UPDATE trades
            SET exit_price = %s, exit_time = %s, pnl = %s, status = %s
            WHERE id = %s
        """
        with self.get_cursor() as cur:
            cur.execute(sql, (exit_price, exit_time, pnl, status, trade_id))

    def get_open_trades(self) -> list[dict]:
        """Get all currently open trades."""
        sql = "SELECT * FROM trades WHERE status = 'open' ORDER BY time DESC"
        with self.get_cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

    def get_trades(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        strategy: str | None = None,
    ) -> pd.DataFrame:
        """Fetch trades as DataFrame with optional filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if start is not None:
            conditions.append("time >= %s")
            params.append(start)
        if end is not None:
            conditions.append("time <= %s")
            params.append(end)
        if strategy is not None:
            conditions.append("strategy = %s")
            params.append(strategy)

        where = " AND ".join(conditions) if conditions else "TRUE"
        sql = f"SELECT * FROM trades WHERE {where} ORDER BY time ASC"

        with self.get_conn() as conn:
            return pd.read_sql(sql, conn, params=params, parse_dates=["time", "exit_time"])

    # =============================================================
    # Hypothesis Operations
    # =============================================================

    def upsert_hypothesis(self, hypothesis: dict) -> None:
        """Insert or update a hypothesis record."""
        sql = """
            INSERT INTO hypotheses (id, name, description, theory_basis, status,
                                   cpcv_sharpe_mean, cpcv_sharpe_std, pbo,
                                   deflated_sharpe, notes)
            VALUES (%(id)s, %(name)s, %(description)s, %(theory_basis)s, %(status)s,
                    %(cpcv_sharpe_mean)s, %(cpcv_sharpe_std)s, %(pbo)s,
                    %(deflated_sharpe)s, %(notes)s)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                cpcv_sharpe_mean = EXCLUDED.cpcv_sharpe_mean,
                cpcv_sharpe_std = EXCLUDED.cpcv_sharpe_std,
                pbo = EXCLUDED.pbo,
                deflated_sharpe = EXCLUDED.deflated_sharpe,
                notes = EXCLUDED.notes
        """
        with self.get_cursor() as cur:
            cur.execute(sql, hypothesis)

    def get_all_hypotheses(self) -> pd.DataFrame:
        """Get all hypotheses for DSR multiple-testing correction."""
        sql = "SELECT * FROM hypotheses ORDER BY created_at ASC"
        with self.get_conn() as conn:
            return pd.read_sql(sql, conn, parse_dates=["created_at"])

    # =============================================================
    # Signal & Risk Event Operations
    # =============================================================

    def insert_signal(self, signal: dict) -> None:
        """Log a generated signal."""
        sql = """
            INSERT INTO signals (time, ticker, strategy, hypothesis_id, direction,
                               confidence, acted_upon, reason_skipped,
                               features_snapshot, explanation)
            VALUES (%(time)s, %(ticker)s, %(strategy)s, %(hypothesis_id)s, %(direction)s,
                    %(confidence)s, %(acted_upon)s, %(reason_skipped)s,
                    %(features_snapshot)s, %(explanation)s)
        """
        with self.get_cursor() as cur:
            cur.execute(sql, signal)

    def insert_risk_event(self, event_type: str, details: dict) -> None:
        """Log a risk management event."""
        sql = "INSERT INTO risk_events (event_type, details) VALUES (%s, %s)"
        with self.get_cursor() as cur:
            cur.execute(sql, (event_type, json.dumps(details)))

    def get_daily_pnl(self, date: datetime) -> float:
        """Get total P&L for a specific date."""
        sql = """
            SELECT COALESCE(SUM(pnl), 0) as total_pnl
            FROM trades
            WHERE exit_time::date = %s AND status IN ('closed', 'stopped')
        """
        with self.get_cursor() as cur:
            cur.execute(sql, (date.date(),))
            row = cur.fetchone()
            return float(row["total_pnl"])

    def get_trade_count_today(self) -> int:
        """Get number of trades placed today."""
        sql = """
            SELECT COUNT(*) as cnt
            FROM trades
            WHERE time::date = CURRENT_DATE
        """
        with self.get_cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            return int(row["cnt"])
