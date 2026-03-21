"""
Main entry point for the trading system.

Orchestrates:
1. Data feeds (price + news)
2. Feature computation
3. Strategy signal generation
4. Ensemble + execution
5. Position monitoring
6. Graceful shutdown

Usage:
    python main.py                  # Run full trading loop
    python main.py --backfill       # Backfill historical data only
    python main.py --dry-run        # Run without placing orders
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytz

from config.settings import WATCHLIST, settings
from data.features.builder import FeatureBuilder
from data.ingestion.news_feed import NewsFeed
from data.ingestion.price_feed import PriceFeed
from data.ingestion.scheduler import DataScheduler
from data.storage.timescale import TimescaleDB
from execution.alpaca_client import AlpacaClient
from execution.order_manager import OrderManager
from execution.risk_manager import RiskManager
from monitoring.alerts import AlertManager
from strategies.base import Signal
from strategies.regime_filter import MarketRegime, RegimeFilter
from strategies.registry import StrategyRegistry

logger = logging.getLogger("trading")
ET = pytz.timezone("US/Eastern")
UTC = timezone.utc


class TradingEngine:
    """
    Main trading engine orchestrating all system components.
    """

    def __init__(self, dry_run: bool = False) -> None:
        self._dry_run = dry_run
        self._running = False

        # Core components
        self.db = TimescaleDB()
        self.price_feed = PriceFeed(self.db)
        self.news_feed = NewsFeed(self.db)
        self.scheduler = DataScheduler(self.price_feed, news_feed=self.news_feed)
        self.alpaca = AlpacaClient()
        self.risk_manager = RiskManager(self.db)
        self.order_manager = OrderManager(self.db, self.alpaca, self.risk_manager)
        self.alert_manager = AlertManager()
        self.registry = StrategyRegistry()

        # Current market state
        self._current_regime: MarketRegime = MarketRegime.SIDEWAYS

    def start(self) -> None:
        """Initialize all components and start the trading loop."""
        logger.info("=" * 60)
        logger.info("TRADING SYSTEM STARTING")
        logger.info("Mode: %s | Dry run: %s", settings.execution.trading_mode, self._dry_run)
        logger.info("Strategies: %d loaded", len(self.registry.all_strategies))
        logger.info("Watchlist: %s", ", ".join(WATCHLIST))
        logger.info("=" * 60)

        # Connect to database
        try:
            self.db.connect()
        except Exception as e:
            logger.error("Database connection failed: %s", e)
            logger.info("Running without database — signals will be logged to console only")

        # Start real-time price feed
        self.price_feed.start_realtime()

        # Start data scheduler (candle aggregation, gap filling)
        self.scheduler.start()

        self._running = True

        # Register shutdown handlers
        signal.signal(signal.SIGINT, self._shutdown_handler)
        signal.signal(signal.SIGTERM, self._shutdown_handler)

        logger.info("Trading engine started successfully")

        # Run the main loop
        try:
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.stop()

    def stop(self) -> None:
        """Gracefully shut down all components."""
        self._running = False
        logger.info("Shutting down trading engine...")

        self.price_feed.stop_realtime()
        self.scheduler.stop()
        self.db.close()

        logger.info("Trading engine stopped")

    def _shutdown_handler(self, signum: int, frame) -> None:
        """Handle OS shutdown signals."""
        logger.info("Received signal %d — initiating shutdown", signum)
        self._running = False

    # =============================================================
    # Main Loop
    # =============================================================

    def _main_loop(self) -> None:
        """
        Core trading loop.

        Runs every 5 minutes during market hours:
        1. Update market regime
        2. Compute features for all watchlist symbols
        3. Run all active strategies
        4. Execute signals through ensemble + risk checks
        5. Monitor open positions for exits
        """
        loop_interval = 300  # 5 minutes

        while self._running:
            loop_start = time.time()

            if not PriceFeed.is_market_open():
                # Outside market hours — check every 60 seconds
                logger.debug("Market closed — sleeping 60s")
                self._sleep_interruptible(60)
                continue

            try:
                self._run_cycle()
            except Exception as e:
                logger.error("Trading cycle error: %s", e, exc_info=True)
                asyncio.get_event_loop().run_until_complete(
                    self.alert_manager.send_alert(f"Trading cycle error: {e}", urgent=True)
                )

            # Sleep until next cycle
            elapsed = time.time() - loop_start
            sleep_time = max(0, loop_interval - elapsed)
            if sleep_time > 0:
                self._sleep_interruptible(sleep_time)

    def _run_cycle(self) -> None:
        """Execute a single trading cycle."""
        now = datetime.now(UTC)
        logger.info("--- Trading cycle at %s ---", now.strftime("%Y-%m-%d %H:%M:%S UTC"))

        # Step 1: Update market regime
        self._update_regime()

        # Step 2: Get account info
        account = self.alpaca.get_account()
        portfolio_value = account.get("portfolio_value", settings.risk.initial_capital)
        self.risk_manager.update_peak_equity(portfolio_value)

        # Step 3: Check open positions for exits
        self._check_exits(portfolio_value)

        # Step 4: Scan for new entry signals
        self._scan_entries(portfolio_value)

        logger.info("--- Cycle complete ---")

    def _update_regime(self) -> None:
        """Detect current market regime from SPY data."""
        try:
            spy_data = self.db.get_candles("SPY", timeframe="1d", limit=250)
            if len(spy_data) >= 60:
                self._current_regime = RegimeFilter.detect(spy_data)
            else:
                logger.warning("Insufficient SPY data for regime detection — defaulting to SIDEWAYS")
                self._current_regime = MarketRegime.SIDEWAYS
        except Exception as e:
            logger.error("Regime detection failed: %s", e)

    def _scan_entries(self, portfolio_value: float) -> None:
        """Scan all watchlist symbols for entry signals."""
        strategies = self.registry.active_strategies()

        for ticker in WATCHLIST:
            # Skip ETFs for individual trading
            if ticker in ("SPY", "QQQ", "IWM", "TLT", "XLF", "XLK", "XLE", "XLV", "XLI"):
                continue

            try:
                features = self._get_current_features(ticker)
                if not features:
                    continue

                current_price = features.get("close", 0)
                if current_price <= 0:
                    continue

                # Run each strategy
                for hyp_id, strategy in strategies.items():
                    # Check regime filter
                    if not RegimeFilter.is_strategy_allowed(hyp_id, self._current_regime):
                        continue

                    # Check for entry signal
                    signal = strategy.check_entry(features, current_price)
                    if signal is None:
                        continue

                    logger.info(
                        "SIGNAL: %s %s from %s (confidence=%.2f)",
                        signal.direction, ticker, signal.strategy, signal.confidence,
                    )

                    if self._dry_run:
                        logger.info("[DRY RUN] Would execute: %s %s", signal.direction, ticker)
                        continue

                    # Execute through order manager
                    # Use a simple ensemble result for now (pass-through)
                    ensemble_result = {
                        "action": "buy" if signal.direction == "long" else "sell",
                        "confidence": signal.confidence,
                        "position_size_factor": 1.0,
                    }

                    result = self.order_manager.execute_signal(
                        ticker=ticker,
                        signal=signal,
                        ensemble_result=ensemble_result,
                        current_price=current_price,
                        portfolio_value=portfolio_value,
                    )

                    if result.get("executed"):
                        logger.info("TRADE EXECUTED: %s", result)
                        asyncio.get_event_loop().run_until_complete(
                            self.alert_manager.trade_alert({
                                "ticker": ticker,
                                "direction": signal.direction,
                                "entry_price": current_price,
                                "position_size": result.get("position_size", 0),
                                "stop_loss": signal.stop_loss,
                                "take_profit": signal.take_profit,
                                "strategy": signal.strategy,
                                "confidence": signal.confidence,
                            })
                        )

            except Exception as e:
                logger.error("Error scanning %s: %s", ticker, e)

    def _check_exits(self, portfolio_value: float) -> None:
        """Check open positions for exit conditions."""
        positions = self.alpaca.get_positions()
        open_trades = self.db.get_open_trades()

        for trade in open_trades:
            ticker = trade.get("ticker", "")
            hyp_id = trade.get("hypothesis_id", "")
            entry_price = trade.get("entry_price", 0)
            direction = trade.get("direction", "long")
            entry_time = trade.get("time")

            strategy = self.registry.get(hyp_id)
            if strategy is None:
                continue

            # Get current features
            features = self._get_current_features(ticker)
            if not features:
                continue

            current_price = features.get("close", 0)
            if current_price <= 0:
                continue

            # Calculate holding days
            holding_days = 0
            if entry_time:
                if hasattr(entry_time, 'tzinfo') and entry_time.tzinfo is None:
                    entry_time = entry_time.replace(tzinfo=UTC)
                holding_days = (datetime.now(UTC) - entry_time).days

            should_exit, reason = strategy.check_exit(
                features=features,
                current_price=current_price,
                entry_price=entry_price,
                direction=direction,
                holding_days=holding_days,
            )

            if should_exit:
                logger.info("EXIT SIGNAL: %s %s — %s", ticker, hyp_id, reason)

                if self._dry_run:
                    logger.info("[DRY RUN] Would close: %s", ticker)
                    continue

                # Close position
                success = self.alpaca.close_position(ticker)
                if success:
                    pnl = (current_price - entry_price) if direction == "long" else (entry_price - current_price)
                    trade_id = trade.get("id")
                    if trade_id:
                        self.db.close_trade(
                            trade_id=trade_id,
                            exit_price=current_price,
                            exit_time=datetime.now(UTC),
                            pnl=pnl,
                            status="closed",
                        )
                    logger.info("CLOSED: %s P&L=$%.2f (%s)", ticker, pnl, reason)

    def _get_current_features(self, ticker: str) -> dict[str, float]:
        """Get the most recent feature vector for a ticker."""
        try:
            # Get recent OHLCV data (250 bars for SMA200 + buffer)
            ohlcv = self.db.get_candles(ticker, timeframe="1d", limit=300)
            if ohlcv.empty or len(ohlcv) < 50:
                return {}

            # Get recent news
            start = datetime.now(UTC) - timedelta(days=30)
            news = self.db.get_news(ticker, start=start)

            # Build features
            features = FeatureBuilder.build_single(ohlcv, news, datetime.now(UTC))

            # Add current price from OHLCV
            if "close" not in features and not ohlcv.empty:
                features["close"] = float(ohlcv["close"].iloc[-1])

            return features

        except Exception as e:
            logger.error("Feature computation failed for %s: %s", ticker, e)
            return {}

    def _sleep_interruptible(self, seconds: float) -> None:
        """Sleep that can be interrupted by shutdown signal."""
        end = time.time() + seconds
        while self._running and time.time() < end:
            time.sleep(min(1.0, end - time.time()))

    # =============================================================
    # Data Backfill
    # =============================================================

    def backfill(self) -> None:
        """Backfill historical price and news data for all symbols."""
        logger.info("Starting historical data backfill...")

        self.db.connect()

        # Backfill daily OHLCV
        logger.info("Backfilling daily OHLCV data...")
        results = self.price_feed.backfill_all(timeframe="1d")
        total = sum(results.values())
        logger.info("Backfilled %d daily candles across %d tickers", total, len(results))

        # Backfill news
        logger.info("Backfilling news data...")
        for ticker in WATCHLIST:
            if ticker in ("SPY", "QQQ", "IWM", "TLT", "XLF", "XLK", "XLE", "XLV", "XLI"):
                continue
            try:
                articles = self.news_feed.fetch_all_sources(ticker)
                if articles:
                    self.news_feed.store_articles(articles)
                    logger.info("Stored %d articles for %s", len(articles), ticker)
            except Exception as e:
                logger.error("News backfill failed for %s: %s", ticker, e)

        logger.info("Backfill complete")
        self.db.close()


def setup_logging() -> None:
    """Configure logging to console and file."""
    log_dir = settings.logging.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, settings.logging.log_level),
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "trading.log"),
        ],
    )
    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("websocket").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def main() -> None:
    parser = argparse.ArgumentParser(description="Trading System")
    parser.add_argument("--backfill", action="store_true", help="Backfill historical data only")
    parser.add_argument("--dry-run", action="store_true", help="Run without placing real orders")
    args = parser.parse_args()

    setup_logging()

    engine = TradingEngine(dry_run=args.dry_run)

    if args.backfill:
        engine.backfill()
    else:
        engine.start()


if __name__ == "__main__":
    main()
