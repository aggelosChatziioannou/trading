#!/usr/bin/env python3
"""
GOLD TACTIC — Tests for TRS Calculator
Τρέξε: python test_trs_calculator.py
"""

import json
import sys
from pathlib import Path

# Ensure we can import from same directory
sys.path.insert(0, str(Path(__file__).parent))

from trs_calculator import (
    check_daily_bias_clear,
    check_4h_aligned,
    check_asia_sweep_or_ib,
    check_news_support,
    check_bos_and_room,
    check_adr_gate,
    check_correlation_blocks,
    calculate_trs,
    _detect_headline_sentiment,
)


def test_criterion_1_daily_bias():
    """Test: Daily bias clear."""
    # BULL → met
    met, reason = check_daily_bias_clear({"daily_bias": "BULL"})
    assert met is True, f"BULL should be met: {reason}"

    # BEAR → met
    met, reason = check_daily_bias_clear({"daily_bias": "BEAR"})
    assert met is True, f"BEAR should be met: {reason}"

    # MIXED → not met
    met, reason = check_daily_bias_clear({"daily_bias": "MIXED"})
    assert met is False, f"MIXED should NOT be met: {reason}"

    # N/A → not met
    met, reason = check_daily_bias_clear({"daily_bias": "N/A"})
    assert met is False, f"N/A should NOT be met: {reason}"

    # Missing → not met
    met, reason = check_daily_bias_clear({})
    assert met is False, f"Missing should NOT be met: {reason}"

    print("  ✅ Criterion 1: Daily Bias Clear — PASS")


def test_criterion_2_4h_aligned():
    """Test: 4H aligned with Daily."""
    # Both BULL → met
    met, _ = check_4h_aligned({"daily_bias": "BULL", "h4_bias": "BULL"})
    assert met is True

    # Both BEAR → met
    met, _ = check_4h_aligned({"daily_bias": "BEAR", "h4_bias": "BEAR"})
    assert met is True

    # BULL vs BEAR → not met
    met, _ = check_4h_aligned({"daily_bias": "BULL", "h4_bias": "BEAR"})
    assert met is False

    # BULL vs MIXED → not met
    met, _ = check_4h_aligned({"daily_bias": "BULL", "h4_bias": "MIXED"})
    assert met is False

    # MIXED daily → not met
    met, _ = check_4h_aligned({"daily_bias": "MIXED", "h4_bias": "MIXED"})
    assert met is False

    print("  ✅ Criterion 2: 4H Aligned — PASS")


def test_criterion_3_asia_sweep():
    """Test: Asia Sweep / IB Breakout (price vs PDH/PDL)."""
    # Price above PDH → sweep up
    met, _ = check_asia_sweep_or_ib({"price": 1.0900, "pdh": 1.0850, "pdl": 1.0780})
    assert met is True

    # Price below PDL → sweep down
    met, _ = check_asia_sweep_or_ib({"price": 1.0770, "pdh": 1.0850, "pdl": 1.0780})
    assert met is True

    # Price inside range → not met
    met, _ = check_asia_sweep_or_ib({"price": 1.0820, "pdh": 1.0850, "pdl": 1.0780})
    assert met is False

    # Missing data ��� not met
    met, _ = check_asia_sweep_or_ib({"price": 1.0820})
    assert met is False

    print("  ✅ Criterion 3: Asia Sweep / IB Breakout — PASS")


def test_criterion_4_news_support():
    """Test: News support direction."""
    # Bullish news + BULL bias → met
    news = {"articles": [
        {"headline": "Euro rally continues as ECB stays hawkish", "asset_tags": ["EURUSD"]},
        {"headline": "Strong euro gains momentum", "asset_tags": ["EURUSD"]},
    ]}
    met, _ = check_news_support("EURUSD", {"daily_bias": "BULL"}, news)
    assert met is True

    # Bearish news + BULL bias → not met
    news = {"articles": [
        {"headline": "Euro crashes on recession fears", "asset_tags": ["EURUSD"]},
        {"headline": "ECB signals dovish turn, euro plunges", "asset_tags": ["EURUSD"]},
    ]}
    met, _ = check_news_support("EURUSD", {"daily_bias": "BULL"}, news)
    assert met is False

    # No news → met (neutral, δεν μπλοκάρει)
    met, _ = check_news_support("EURUSD", {"daily_bias": "BULL"}, {"articles": []})
    assert met is True

    # CryptoPanic with sentiment field
    news = {"articles": [
        {"headline": "BTC moves", "sentiment": "bullish", "asset_tags": ["BTC"]},
    ]}
    met, _ = check_news_support("BTC", {"daily_bias": "BULL"}, news)
    assert met is True

    print("  ✅ Criterion 4: News Support — PASS")


def test_criterion_5_bos_and_room():
    """Test: Break of Structure + ADR < 90%."""
    # ALIGNED + ADR < 90 → met
    met, _ = check_bos_and_room({"alignment": "ALIGNED_BULL", "adr_consumed_pct": 65.0})
    assert met is True

    # ALIGNED + ADR >= 90 → not met
    met, _ = check_bos_and_room({"alignment": "ALIGNED_BEAR", "adr_consumed_pct": 92.0})
    assert met is False

    # PARTIAL + ADR < 90 → not met (no BOS)
    met, _ = check_bos_and_room({"alignment": "PARTIAL_BULL", "adr_consumed_pct": 50.0})
    assert met is False

    # MIXED → not met
    met, _ = check_bos_and_room({"alignment": "MIXED", "adr_consumed_pct": 30.0})
    assert met is False

    print("  ✅ Criterion 5: BOS + Room — PASS")


def test_adr_gate():
    """Test: ADR Hard Cutoff (85%)."""
    # ADR 60% → OK
    result = check_adr_gate({"adr_consumed_pct": 60.0, "regime": "RANGING", "volume_ratio": 1.0, "alignment": "MIXED"})
    assert result["blocked"] is False

    # ADR 90% RANGING → BLOCKED
    result = check_adr_gate({"adr_consumed_pct": 90.0, "regime": "RANGING", "volume_ratio": 1.0, "alignment": "MIXED"})
    assert result["blocked"] is True

    # ADR 90% TRENDING + high volume + ALIGNED → OK with 50% risk
    result = check_adr_gate({"adr_consumed_pct": 90.0, "regime": "TRENDING", "volume_ratio": 2.0, "alignment": "ALIGNED_BULL"})
    assert result["blocked"] is False
    assert result["risk_modifier"] == 0.5

    # ADR 90% TRENDING but low volume → BLOCKED
    result = check_adr_gate({"adr_consumed_pct": 90.0, "regime": "TRENDING", "volume_ratio": 1.0, "alignment": "ALIGNED_BULL"})
    assert result["blocked"] is True

    print("  ✅ ADR Gate — PASS")


def test_correlation_blocks():
    """Test: Correlation filter."""
    corr_data = {"correlations": {"EURUSD_GBPUSD": 0.88, "BTC_SOL": 0.72}}

    # EURUSD open trade, GBPUSD should be blocked
    trs = {"EURUSD": {"trs_score": 4}, "GBPUSD": {"trs_score": 4}}
    open_trades = [{"asset": "EURUSD", "tp1_hit": False}]
    blocks = check_correlation_blocks(trs, corr_data, open_trades)
    assert "GBPUSD" in blocks and blocks["GBPUSD"]["blocked"] is True

    # EURUSD open trade with TP1 hit → GBPUSD NOT blocked
    open_trades = [{"asset": "EURUSD", "tp1_hit": True}]
    blocks = check_correlation_blocks(trs, corr_data, open_trades)
    assert "GBPUSD" not in blocks or blocks.get("GBPUSD", {}).get("blocked") is not True

    # BTC-SOL correlation 0.72 (< 0.80) → no blocks
    trs = {"BTC": {"trs_score": 5}, "SOL": {"trs_score": 5}}
    open_trades = [{"asset": "BTC", "tp1_hit": False}]
    blocks = check_correlation_blocks(trs, corr_data, open_trades)
    assert "SOL" not in blocks

    # Both TRS >= 4, no open trades, high correlation → block lower TRS
    trs = {"EURUSD": {"trs_score": 5}, "GBPUSD": {"trs_score": 4}}
    blocks = check_correlation_blocks(trs, corr_data, [])
    assert "GBPUSD" in blocks and blocks["GBPUSD"]["blocked"] is True
    assert "EURUSD" not in blocks  # Higher TRS stays

    print("  ✅ Correlation Blocks — PASS")


def test_headline_sentiment():
    """Test: Headline sentiment detection."""
    assert _detect_headline_sentiment("Bitcoin rally continues with record surge") == "bullish"
    assert _detect_headline_sentiment("Markets crash as recession fears grow") == "bearish"
    assert _detect_headline_sentiment("Fed meets today to discuss rates") == "neutral"
    assert _detect_headline_sentiment("") == "neutral"
    assert _detect_headline_sentiment(None) == "neutral"

    print("  ✅ Headline Sentiment — PASS")


def test_calculate_trs_full():
    """Test: Full TRS calculation with perfect setup."""
    asset_data = {
        "asset": "EURUSD",
        "price": 1.0900,
        "daily_bias": "BULL",
        "h4_bias": "BULL",
        "h1_bias": "BULL",
        "alignment": "ALIGNED_BULL",
        "adr_consumed_pct": 45.0,
        "pdh": 1.0880,
        "pdl": 1.0800,
        "regime": "TRENDING",
        "adx": 30.0,
        "volume_ratio": 1.5,
    }
    news = {"articles": [
        {"headline": "Euro rallies on strong data", "asset_tags": ["EURUSD"]},
    ]}

    result = calculate_trs("EURUSD", asset_data, news)

    assert result["trs_score"] == 5, f"Expected TRS 5, got {result['trs_score']}"
    assert result["direction"] == "BULL"
    assert result["adr_gate"]["blocked"] is False
    assert len(result["criteria"]) == 5
    assert all(c["met"] for c in result["criteria"])

    print("  ✅ Full TRS Calculation (5/5) — PASS")


def test_calculate_trs_mixed():
    """Test: TRS with mixed signals (should be 2/5)."""
    asset_data = {
        "asset": "GBPUSD",
        "price": 1.3200,
        "daily_bias": "BEAR",
        "h4_bias": "BULL",       # NOT aligned
        "h1_bias": "MIXED",
        "alignment": "MIXED",    # NOT aligned
        "adr_consumed_pct": 92.0, # Too high
        "pdh": 1.3250,
        "pdl": 1.3150,
        "regime": "CHOPPY",
        "adx": 15.0,
        "volume_ratio": 0.8,
    }
    news = {"articles": []}

    result = calculate_trs("GBPUSD", asset_data, news)

    # Criterion 1: Daily BEAR clear → ✅ (+1)
    # Criterion 2: 4H BULL ≠ Daily BEAR → ❌
    # Criterion 3: price 1.3200 inside range → ❌
    # Criterion 4: No news → ✅ neutral (+1)
    # Criterion 5: MIXED alignment + ADR 92% → ❌
    assert result["trs_score"] == 2, f"Expected TRS 2, got {result['trs_score']}"
    assert result["direction"] == "BEAR"

    print("  ✅ Mixed TRS Calculation (2/5) — PASS")


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n🧪 GOLD TACTIC — TRS Calculator Tests\n")

    tests = [
        test_criterion_1_daily_bias,
        test_criterion_2_4h_aligned,
        test_criterion_3_asia_sweep,
        test_criterion_4_news_support,
        test_criterion_5_bos_and_room,
        test_adr_gate,
        test_correlation_blocks,
        test_headline_sentiment,
        test_calculate_trs_full,
        test_calculate_trs_mixed,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ❌ {test.__name__}: UNEXPECTED {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"Results: {passed} passed, {failed} failed / {len(tests)} total")

    if failed > 0:
        sys.exit(1)
    else:
        print("🎉 ALL TESTS PASSED!")
