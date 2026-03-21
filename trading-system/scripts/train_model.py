"""
Model training pipeline.

End-to-end flow:
1. Load historical OHLCV + news data from database
2. Build feature matrix
3. Run CPCV (Combinatorial Purged Cross-Validation)
4. Train LightGBM on each fold
5. Compute PBO (Probability of Backtest Overfitting)
6. Compute Deflated Sharpe Ratio
7. Register hypothesis in database

Usage:
    python scripts/train_model.py
    python scripts/train_model.py --hypothesis MRS-001
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import WATCHLIST, settings
from data.features.builder import FeatureBuilder
from data.storage.timescale import TimescaleDB
from models.lightgbm_model import TradingLGBM
from validation.cpcv import CPCV
from validation.deflated_sharpe import DeflatedSharpe
from validation.pbo import PBO

logger = logging.getLogger(__name__)
UTC = timezone.utc


def build_training_data(db: TimescaleDB) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build training dataset from all watchlist symbols.

    Returns:
        Tuple of (features_df, target_df).
    """
    all_features: list[pd.DataFrame] = []

    for ticker in WATCHLIST:
        # Skip ETFs
        if ticker in ("SPY", "QQQ", "IWM", "TLT", "XLF", "XLK", "XLE", "XLV", "XLI"):
            continue

        logger.info("Building features for %s...", ticker)

        # Get OHLCV data
        ohlcv = db.get_candles(ticker, timeframe="1d")
        if ohlcv.empty or len(ohlcv) < 250:
            logger.warning("Insufficient data for %s (%d rows) — skipping", ticker, len(ohlcv))
            continue

        # Get news data
        start = ohlcv.index[0] if hasattr(ohlcv.index[0], 'date') else None
        news = db.get_news(ticker, start=start)

        # Build features
        try:
            features = FeatureBuilder.build(ohlcv, news)
            if features.empty:
                continue

            # Add target: forward 5-day return
            close_aligned = ohlcv["close"].reindex(features.index)
            forward_return = close_aligned.pct_change(5).shift(-5) * 100
            features["target_return"] = forward_return
            features["ticker"] = ticker

            all_features.append(features)
        except Exception as e:
            logger.error("Feature build failed for %s: %s", ticker, e)

    if not all_features:
        logger.error("No training data built — ensure database has OHLCV data")
        return pd.DataFrame(), pd.DataFrame()

    combined = pd.concat(all_features)
    combined = combined.dropna(subset=["target_return"])

    # Separate features and target
    target = combined["target_return"]
    ticker_col = combined["ticker"]
    features = combined.drop(columns=["target_return", "ticker"])

    logger.info("Training data: %d samples, %d features", len(features), len(features.columns))
    return features, target


def bucket_returns(returns: pd.Series) -> pd.Series:
    """Convert continuous returns to classification buckets."""
    buckets = settings.model.return_buckets
    labels = list(range(len(buckets) + 1))
    return pd.cut(returns, bins=[-np.inf] + list(buckets) + [np.inf], labels=labels).astype(int)


def run_cpcv_validation(
    features: pd.DataFrame,
    target: pd.Series,
) -> dict:
    """
    Run CPCV validation and compute all metrics.

    Returns:
        Dict with sharpe_mean, sharpe_std, pbo, deflated_sharpe, passed.
    """
    target_buckets = bucket_returns(target)

    cpcv = CPCV(
        n_groups=settings.validation.cpcv_n_groups,
        n_test_groups=settings.validation.cpcv_n_test_groups,
        purge_window=settings.validation.cpcv_purge_window,
        embargo_pct=settings.validation.cpcv_embargo_pct,
    )

    fold_sharpes: list[float] = []
    fold_returns: list[pd.Series] = []

    for fold_idx, (train_idx, test_idx) in enumerate(cpcv.split(features)):
        logger.info("CPCV fold %d/%d...", fold_idx + 1, cpcv.n_splits)

        X_train = features.iloc[train_idx]
        y_train = target_buckets.iloc[train_idx]
        X_test = features.iloc[test_idx]
        y_test_returns = target.iloc[test_idx]

        # Train model from scratch per fold
        model = TradingLGBM()
        model.train(X_train, y_train)

        # Get predictions on test set
        signals = model.get_signal(X_test)

        # Compute strategy returns
        strategy_returns = []
        for i, (action, confidence, _) in enumerate(signals):
            actual_return = y_test_returns.iloc[i] / 100  # Convert back to decimal
            if action == "buy":
                strategy_returns.append(actual_return * confidence)
            elif action == "sell":
                strategy_returns.append(-actual_return * confidence)
            else:
                strategy_returns.append(0.0)

        returns_series = pd.Series(strategy_returns, index=X_test.index)
        fold_returns.append(returns_series)

        # Annualized Sharpe (daily returns, 252 trading days)
        if len(returns_series) > 1 and returns_series.std() > 0:
            sharpe = (returns_series.mean() / returns_series.std()) * np.sqrt(252)
        else:
            sharpe = 0.0
        fold_sharpes.append(sharpe)

        logger.info("Fold %d Sharpe: %.3f", fold_idx + 1, sharpe)

    # Aggregate results
    sharpe_mean = np.mean(fold_sharpes)
    sharpe_std = np.std(fold_sharpes)

    # PBO
    pbo_value = PBO.compute(fold_sharpes)

    # Deflated Sharpe
    n_hypotheses = max(1, len(fold_sharpes))
    dsr = DeflatedSharpe.compute(
        observed_sharpe=sharpe_mean,
        n_trials=n_hypotheses,
        sample_length=len(features),
        skewness=float(target.skew()),
        kurtosis=float(target.kurtosis()),
    )

    # Pass/fail criteria
    passed = (
        sharpe_mean >= settings.validation.min_cpcv_sharpe
        and pbo_value <= settings.validation.pbo_max_acceptable
        and dsr > 0
    )

    results = {
        "sharpe_mean": round(sharpe_mean, 4),
        "sharpe_std": round(sharpe_std, 4),
        "pbo": round(pbo_value, 4),
        "deflated_sharpe": round(dsr, 4),
        "n_folds": len(fold_sharpes),
        "passed": passed,
    }

    logger.info("=" * 50)
    logger.info("VALIDATION RESULTS")
    logger.info("  CPCV Sharpe: %.4f +/- %.4f", sharpe_mean, sharpe_std)
    logger.info("  PBO: %.4f (max acceptable: %.2f)", pbo_value, settings.validation.pbo_max_acceptable)
    logger.info("  Deflated Sharpe: %.4f", dsr)
    logger.info("  PASSED: %s", passed)
    logger.info("=" * 50)

    return results


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
    )

    parser = argparse.ArgumentParser(description="Model Training Pipeline")
    parser.add_argument("--hypothesis", type=str, help="Specific hypothesis ID to validate")
    args = parser.parse_args()

    db = TimescaleDB()
    db.connect()

    try:
        # Build training data
        features, target = build_training_data(db)
        if features.empty:
            logger.error("No training data available. Run backfill first: python main.py --backfill")
            return

        # Run CPCV validation
        results = run_cpcv_validation(features, target)

        # Register hypothesis in database
        hypothesis_id = args.hypothesis or "SYSTEM-001"
        db.upsert_hypothesis({
            "id": hypothesis_id,
            "name": "Full System Validation",
            "description": "End-to-end validation of all strategies",
            "theory_basis": "Combined strategy ensemble",
            "status": "active" if results["passed"] else "failed",
            "cpcv_sharpe_mean": results["sharpe_mean"],
            "cpcv_sharpe_std": results["sharpe_std"],
            "pbo": results["pbo"],
            "deflated_sharpe": results["deflated_sharpe"],
            "notes": f"Validation run at {datetime.now(UTC).isoformat()}",
        })

        if results["passed"]:
            logger.info("STRATEGY PASSED VALIDATION — ready for paper trading")
        else:
            logger.warning("STRATEGY FAILED VALIDATION — review parameters")

    finally:
        db.close()


if __name__ == "__main__":
    main()
