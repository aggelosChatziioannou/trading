"""
Real-time and historical price data ingestion.

Architecture:
- Finnhub WebSocket for live streaming during market hours
- yfinance for historical backfill and gap-filling
- Auto-aggregation of ticks into 1min/5min/15min/1h/1d candles

Data validation rejects obvious errors (e.g., close > 2x previous close).
WebSocket auto-reconnects with exponential backoff.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import finnhub
import pandas as pd
import pytz
import websocket
import yfinance as yf

from config.settings import WATCHLIST, settings
from data.storage.timescale import TimescaleDB

logger = logging.getLogger(__name__)

ET = pytz.timezone("US/Eastern")
UTC = pytz.UTC


class PriceFeed:
    """
    Real-time and historical price data ingestion.

    Finnhub WebSocket streams live trades during market hours.
    yfinance provides historical backfill and fills gaps on startup.
    Ticks are aggregated into OHLCV candles at multiple timeframes.
    """

    def __init__(self, db: TimescaleDB, finnhub_api_key: str | None = None) -> None:
        self.db = db
        self._api_key = finnhub_api_key or settings.api.finnhub_key
        self._client = finnhub.Client(api_key=self._api_key) if self._api_key else None
        self._ws: websocket.WebSocketApp | None = None
        self._ws_thread: threading.Thread | None = None
        self._running = False

        # Tick buffer for candle aggregation: {ticker: [tick_dicts]}
        self._tick_buffer: dict[str, list[dict]] = defaultdict(list)
        self._buffer_lock = threading.Lock()

        # Reconnect state
        self._reconnect_attempt = 0

    # =============================================================
    # Historical Backfill (yfinance)
    # =============================================================

    def backfill_historical(
        self,
        ticker: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        timeframe: str = "1d",
    ) -> int:
        """
        Download historical data via yfinance and store in DB.

        Args:
            ticker: Stock symbol (e.g., 'AAPL').
            start_date: Start of backfill period. Defaults to 2 years ago.
            end_date: End of backfill period. Defaults to today.
            timeframe: Candle period ('1d', '1h', '5min', etc.).

        Returns:
            Number of candles inserted.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=365 * settings.data.backfill_years)
        if end_date is None:
            end_date = datetime.now(UTC)

        # Map our timeframe names to yfinance interval strings
        yf_interval_map = {
            "1min": "1m",
            "5min": "5m",
            "15min": "15m",
            "1h": "1h",
            "1d": "1d",
        }
        yf_interval = yf_interval_map.get(timeframe, "1d")

        # yfinance limits intraday data to 60 days for 1m, 730 days for 1h
        logger.info("Backfilling %s %s from %s to %s", ticker, timeframe, start_date, end_date)

        try:
            yf_ticker = yf.Ticker(ticker)
            df = yf_ticker.history(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval=yf_interval,
                auto_adjust=True,
            )
        except Exception as e:
            logger.error("yfinance download failed for %s: %s", ticker, e)
            return 0

        if df.empty:
            logger.warning("No data returned for %s %s", ticker, timeframe)
            return 0

        candles = self._dataframe_to_candles(df, ticker, timeframe)
        candles = self._validate_candles(candles)

        if candles:
            count = self.db.insert_candles(candles)
            logger.info("Inserted %d/%d candles for %s %s", count, len(candles), ticker, timeframe)
            return count
        return 0

    def backfill_all(self, timeframe: str = "1d") -> dict[str, int]:
        """
        Backfill historical data for all watchlist symbols.

        Checks for existing data and only fills gaps.

        Returns:
            Dict mapping ticker to number of candles inserted.
        """
        results: dict[str, int] = {}
        for ticker in WATCHLIST:
            # Check for existing data to avoid re-downloading
            latest = self.db.get_latest_candle_time(ticker, timeframe)
            if latest is not None:
                start = latest + timedelta(days=1)
                logger.info("Resuming backfill for %s from %s", ticker, start)
            else:
                start = None  # Full backfill

            count = self.backfill_historical(ticker, start_date=start, timeframe=timeframe)
            results[ticker] = count

            # Throttle to respect yfinance rate limits
            time.sleep(settings.data.yfinance_delay_between_calls)

        return results

    # =============================================================
    # Real-time WebSocket (Finnhub)
    # =============================================================

    def start_realtime(self) -> None:
        """
        Start WebSocket streaming for all WATCHLIST symbols.

        Runs in a background thread. Auto-reconnects on disconnect.
        """
        if not self._api_key:
            logger.warning("No Finnhub API key — skipping real-time feed")
            return

        self._running = True
        self._ws_thread = threading.Thread(target=self._run_websocket, daemon=True)
        self._ws_thread.start()
        logger.info("Started real-time price feed")

    def stop_realtime(self) -> None:
        """Stop the WebSocket stream."""
        self._running = False
        if self._ws is not None:
            self._ws.close()
        if self._ws_thread is not None:
            self._ws_thread.join(timeout=5)
        logger.info("Stopped real-time price feed")

    def _run_websocket(self) -> None:
        """WebSocket event loop with auto-reconnect."""
        while self._running:
            try:
                ws_url = f"wss://ws.finnhub.io?token={self._api_key}"
                self._ws = websocket.WebSocketApp(
                    ws_url,
                    on_open=self._on_ws_open,
                    on_message=self._on_ws_message,
                    on_error=self._on_ws_error,
                    on_close=self._on_ws_close,
                )
                self._ws.run_forever()
            except Exception as e:
                logger.error("WebSocket error: %s", e)

            if not self._running:
                break

            # Exponential backoff reconnect
            delay = min(
                settings.data.ws_reconnect_base_delay * (2 ** self._reconnect_attempt),
                settings.data.ws_reconnect_max_delay,
            )
            self._reconnect_attempt += 1

            if self._reconnect_attempt > settings.data.ws_reconnect_max_attempts:
                logger.error("Max WebSocket reconnect attempts reached")
                break

            logger.info("Reconnecting WebSocket in %.1fs (attempt %d)", delay, self._reconnect_attempt)
            time.sleep(delay)

    def _on_ws_open(self, ws: Any) -> None:
        """Subscribe to all watchlist symbols on connection."""
        self._reconnect_attempt = 0
        for ticker in WATCHLIST:
            ws.send(json.dumps({"type": "subscribe", "symbol": ticker}))
        logger.info("WebSocket connected, subscribed to %d symbols", len(WATCHLIST))

    def _on_ws_message(self, ws: Any, message: str) -> None:
        """Process incoming tick data."""
        data = json.loads(message)
        if data.get("type") != "trade":
            return

        for trade in data.get("data", []):
            tick = {
                "ticker": trade["s"],
                "price": trade["p"],
                "volume": trade["v"],
                "time": datetime.fromtimestamp(trade["t"] / 1000, tz=UTC),
            }
            with self._buffer_lock:
                self._tick_buffer[tick["ticker"]].append(tick)

    def _on_ws_error(self, ws: Any, error: Exception) -> None:
        logger.error("WebSocket error: %s", error)

    def _on_ws_close(self, ws: Any, close_status_code: int | None, close_msg: str | None) -> None:
        logger.info("WebSocket closed: %s %s", close_status_code, close_msg)

    # =============================================================
    # Tick-to-Candle Aggregation
    # =============================================================

    def flush_candles(self, timeframe: str = "1min") -> int:
        """
        Aggregate buffered ticks into candles and store in DB.

        Called periodically by the scheduler (e.g., every minute).

        Args:
            timeframe: Target candle period.

        Returns:
            Number of candles stored.
        """
        with self._buffer_lock:
            buffer_copy = dict(self._tick_buffer)
            self._tick_buffer.clear()

        if not buffer_copy:
            return 0

        all_candles: list[dict] = []
        for ticker, ticks in buffer_copy.items():
            if not ticks:
                continue
            candle = self._aggregate_ticks(ticks, ticker, timeframe)
            if candle is not None:
                all_candles.append(candle)

        if all_candles:
            all_candles = self._validate_candles(all_candles)
            return self.db.insert_candles(all_candles)
        return 0

    def _aggregate_ticks(self, ticks: list[dict], ticker: str, timeframe: str) -> dict | None:
        """Aggregate a list of ticks into a single OHLCV candle."""
        if not ticks:
            return None

        prices = [t["price"] for t in ticks]
        volumes = [t["volume"] for t in ticks]
        times = [t["time"] for t in ticks]

        # Truncate time to the candle boundary
        candle_time = self._truncate_time(min(times), timeframe)

        return {
            "time": candle_time,
            "ticker": ticker,
            "open": prices[0],
            "high": max(prices),
            "low": min(prices),
            "close": prices[-1],
            "volume": sum(volumes),
            "timeframe": timeframe,
        }

    @staticmethod
    def _truncate_time(dt: datetime, timeframe: str) -> datetime:
        """Truncate datetime to the start of the candle period."""
        if timeframe == "1min":
            return dt.replace(second=0, microsecond=0)
        elif timeframe == "5min":
            return dt.replace(minute=(dt.minute // 5) * 5, second=0, microsecond=0)
        elif timeframe == "15min":
            return dt.replace(minute=(dt.minute // 15) * 15, second=0, microsecond=0)
        elif timeframe == "1h":
            return dt.replace(minute=0, second=0, microsecond=0)
        elif timeframe == "1d":
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return dt

    # =============================================================
    # Data Validation
    # =============================================================

    def _validate_candles(self, candles: list[dict]) -> list[dict]:
        """
        Filter out obviously bad candle data.

        Rejects candles where:
        - Any OHLCV value is None or negative
        - Close differs from previous close by > max_price_change_factor
        - Volume is zero (no actual trades)
        """
        valid: list[dict] = []
        prev_close: dict[str, float] = {}

        for candle in candles:
            ticker = candle["ticker"]

            # Basic sanity checks
            if any(
                candle.get(f) is None or candle.get(f, 0) < 0
                for f in ("open", "high", "low", "close")
            ):
                logger.warning("Rejected candle with invalid price: %s", candle)
                continue

            if candle.get("volume", 0) <= 0:
                logger.debug("Skipping zero-volume candle: %s %s", ticker, candle["time"])
                continue

            # Price continuity check
            if ticker in prev_close:
                ratio = candle["close"] / prev_close[ticker] if prev_close[ticker] > 0 else 1.0
                if ratio > settings.data.max_price_change_factor or ratio < (1.0 / settings.data.max_price_change_factor):
                    logger.warning(
                        "Rejected candle with extreme price change: %s %.2f -> %.2f (%.1fx)",
                        ticker, prev_close[ticker], candle["close"], ratio,
                    )
                    continue

            prev_close[ticker] = candle["close"]
            valid.append(candle)

        return valid

    @staticmethod
    def _dataframe_to_candles(df: pd.DataFrame, ticker: str, timeframe: str) -> list[dict]:
        """Convert a yfinance DataFrame to list of candle dicts."""
        candles: list[dict] = []
        for idx, row in df.iterrows():
            ts = idx
            if not isinstance(ts, datetime):
                ts = pd.Timestamp(ts)
            if ts.tzinfo is None:
                ts = ts.tz_localize(UTC)
            else:
                ts = ts.tz_convert(UTC)

            candles.append({
                "time": ts,
                "ticker": ticker,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]),
                "timeframe": timeframe,
            })
        return candles

    # =============================================================
    # Market Hours Check
    # =============================================================

    @staticmethod
    def is_market_open() -> bool:
        """Check if US stock market is currently open (regular hours only)."""
        now_et = datetime.now(ET)
        # Weekends
        if now_et.weekday() >= 5:
            return False
        # Regular hours: 9:30-16:00 ET
        market_open = now_et.replace(
            hour=settings.market_hours.market_open_hour,
            minute=settings.market_hours.market_open_minute,
            second=0,
        )
        market_close = now_et.replace(
            hour=settings.market_hours.market_close_hour,
            minute=settings.market_hours.market_close_minute,
            second=0,
        )
        return market_open <= now_et <= market_close
