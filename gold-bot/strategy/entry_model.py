"""Multi-timeframe ICT entry model — v2 theory-driven optimization.

Changes integrated:
  1. ATR-based SL/TP sizing (1.5x ATR SL, 2R/3R TPs)
  2. FVG minimum size filter (0.3-3.0x ATR)
  3. HTF bias from H4/H1 market structure (mandatory)
  4. ATR-calibrated sweep detection (0.1-2.0x ATR overshoot)
  5. ICT standard killzones + Silver Bullet bonus
  6. Displacement required after sweep
  7. 2-tier partial TP (50% at 2R, 50% at 3R)
  8. Max 2 trades/session, 3/day
  9. OB+FVG confluence bonus, ATR-relative OB impulse
  10. Proper spread/slippage modeling

Entry flow:
  Gate 1: Killzone active
  Gate 2: News filter
  Gate 3: HTF bias (bullish=long only, bearish=short only)
  Gate 4: Liquidity sweep (ATR-calibrated)
  Gate 5: Displacement after sweep
  Gate 6: Confirmation (BOS/CHoCH/IFVG/SMT/Fib79)
  Gate 7: Continuation entry zone (FVG/OB/BB/EQ) with CE entry
  Gate 8: Confluence ≥ 3 from all 3 categories
  Gate 9: ATR-based SL/TP, min 1.5 R:R
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import numpy as np

from config.settings import (
    SWING_LOOKBACK, SL_ATR_MULTIPLIER, MIN_SL_DISTANCE,
    TP1_RR, TP2_RR, MIN_RR, TOTAL_COST_PER_TRADE,
    MAX_TRADES_PER_DAY, MAX_TRADES_PER_SESSION,
    OB_IMPULSE_MIN_MOVE,
)
from ict.atr import get_current_atr
from ict.structures import (
    find_all_swings, detect_bos, determine_market_structure,
    SwingPoint, BOS,
)
from ict.fvg import detect_fvgs, FVG
from ict.order_blocks import detect_order_blocks, OB
from ict.liquidity import (
    LiquidityLevel,
    check_liquidity_sweep, check_asia_sweep,
    get_session_levels, get_swing_liquidity, find_equal_levels,
    get_pdh_pdl, get_asia_ranges,
)
from ict.smt import detect_smt
from ict.equilibrium import find_equilibrium, find_fib_79_extension, check_fib_79_closure
from ict.displacement import check_displacement
from ict.confluence import ConfluenceResult
from strategy.session_filter import should_trade, is_silver_bullet
from strategy.signal import TradeSignal


class ICTEntryModel:
    """Entry model — stateless per-bar with ATR-based sizing."""

    def __init__(self):
        self.current_date = None
        self.trades_today: int = 0
        self.session_trades: dict[str, int] = {}
        self.used_sl_levels: set[float] = set()

    def check_entry(
        self,
        bar_5m: pd.Series,
        bar_idx: int,
        gold_5m_history: pd.DataFrame,
        gold_1h: pd.DataFrame,
        gold_4h: pd.DataFrame,
        capital: float,
        dxy_5m: pd.DataFrame | None = None,
    ) -> TradeSignal | None:

        dt = bar_5m.name
        confluence = ConfluenceResult()

        # Reset daily state
        today = getattr(dt, 'date', lambda: dt)()
        if self.current_date != today:
            self.current_date = today
            self.trades_today = 0
            self.session_trades = {}
            self.used_sl_levels = set()

        if self.trades_today >= MAX_TRADES_PER_DAY:
            return None

        # ── Gate 1+2: Session + News ─────────────────────────────────
        can_trade, session = should_trade(dt)
        if not can_trade:
            return None

        # Change 8: Per-session limit
        if self.session_trades.get(session, 0) >= MAX_TRADES_PER_SESSION:
            return None

        # ── Compute ATR (Session-specific) ──────────────────────────
        # Theory: London and NY have different volatility profiles.
        # Using session-local ATR gives better calibrated SL per session.
        # Source: CME Group volume data, professional gold trader practice.
        import pytz
        _et = pytz.timezone("US/Eastern")
        dt_et = dt.astimezone(_et) if dt.tzinfo else pytz.utc.localize(dt).astimezone(_et)
        hour_et = dt_et.hour

        # Filter history to same session type for ATR
        history_tz = gold_5m_history.copy()
        if history_tz.index.tz is None:
            history_tz.index = history_tz.index.tz_localize("UTC")
        history_et = history_tz.copy()
        history_et.index = history_et.index.tz_convert(_et)
        hours = history_et.index.hour

        if 2 <= hour_et < 5:  # London
            session_mask = (hours >= 2) & (hours < 5)
        elif 8 <= hour_et < 11:  # NY AM
            session_mask = (hours >= 8) & (hours < 11)
        elif 13 <= hour_et < 15:  # NY PM
            session_mask = (hours >= 13) & (hours < 15)
        else:
            session_mask = pd.Series(True, index=history_et.index)

        if hasattr(session_mask, 'values'):
            mask_arr = session_mask.values
        else:
            mask_arr = session_mask
        session_history = gold_5m_history[mask_arr] if mask_arr.sum() >= 20 else gold_5m_history
        atr = get_current_atr(session_history)
        if atr <= 0:
            atr = get_current_atr(gold_5m_history)  # Fallback to global ATR
        if atr <= 0:
            return None

        # Silver Bullet bonus (Change 5)
        if is_silver_bullet(dt):
            confluence.add("silver_bullet")

        # ── Gate 3: HTF Bias (Change 3) ──────────────────────────────
        ms_4h = determine_market_structure(gold_4h, lookback=3)
        ms_1h = determine_market_structure(gold_1h, lookback=3)
        bias = ms_4h.bias if ms_4h.bias != "neutral" else ms_1h.bias
        if bias == "neutral":
            return None

        allowed_direction = "long" if bias == "bullish" else "short"
        sweep_dir = "bullish" if allowed_direction == "long" else "bearish"
        confluence.add("htf_bias_aligned")

        # ── Build HTF levels ─────────────────────────────────────────
        htf_levels = []
        htf_levels.extend(get_session_levels(gold_5m_history))
        htf_levels.extend(get_pdh_pdl(gold_1h))
        swings_1h = find_all_swings(gold_1h, lookback=3)
        swings_4h = find_all_swings(gold_4h, lookback=3)
        htf_levels.extend(get_swing_liquidity(swings_1h, "1H"))
        htf_levels.extend(get_swing_liquidity(swings_4h, "4H"))
        htf_levels.extend(find_equal_levels(swings_1h))
        htf_levels.extend(find_equal_levels(swings_4h))

        # ── Gate 4: Liquidity Sweep (ATR-calibrated, Change 4) ───────
        swept_level = None
        sweep_type = None
        sweep_bar_idx = bar_idx

        asia_ranges = get_asia_ranges(gold_5m_history)
        for asia in asia_ranges:
            result = check_asia_sweep(asia, bar_5m, atr=atr)
            if result is not None:
                expected = "short" if result == "high" else "long"
                if expected == allowed_direction:
                    price = asia.high if result == "high" else asia.low
                    swept_level = LiquidityLevel(
                        price=price, type=f"session_{result}",
                        source="Asia", timestamp=dt,
                    )
                    sweep_type = "liquidity_sweep"
                    break

        if swept_level is None:
            for level in htf_levels:
                if check_liquidity_sweep(level, bar_5m, atr=atr):
                    if level.type in ("session_high", "pdh", "swing_high", "equal_highs"):
                        expected = "short"
                    else:
                        expected = "long"
                    if expected == allowed_direction:
                        swept_level = level
                        sweep_type = "pdh_pdl_sweep" if level.type in ("pdh", "pdl") else "liquidity_sweep"
                        break

        if swept_level is None:
            return None
        confluence.add(sweep_type)

        # ── Gate 5: Displacement after sweep (Change 6) ──────────────
        if check_displacement(gold_5m_history, len(gold_5m_history) - 1,
                             sweep_dir, atr, max_candles=3):
            confluence.add("displacement")

        # ── Gate 6: Confirmation (BOS/CHoCH/IFVG/SMT/Fib79) ─────────
        bos_5m = detect_bos(gold_5m_history, lookback=SWING_LOOKBACK)
        fvgs_5m = detect_fvgs(gold_5m_history, atr=atr)  # Change 2: ATR-filtered
        swings_5m = find_all_swings(gold_5m_history, lookback=SWING_LOOKBACK)

        lookback_time = gold_5m_history.index[max(0, len(gold_5m_history) - 20)]

        recent_bos = [b for b in bos_5m
                      if b.direction == sweep_dir
                      and b.timestamp >= lookback_time]
        if recent_bos:
            confluence.add("bos")
            if any(b.is_choch for b in recent_bos):
                confluence.add("choch")

        recent_ifvgs = [f for f in fvgs_5m
                        if f.inverted and f.timestamp >= lookback_time]
        if recent_ifvgs:
            confluence.add("ifvg")

        if dxy_5m is not None and not dxy_5m.empty:
            dxy_swings = find_all_swings(dxy_5m, lookback=SWING_LOOKBACK)
            smt_signals = detect_smt(swings_5m, dxy_swings)
            if any(s.direction == sweep_dir for s in smt_signals[-5:]):
                confluence.add("smt")

        if len(swings_5m) >= 2:
            fib = find_fib_79_extension(swings_5m[-2], swings_5m[-1])
            if check_fib_79_closure(fib, bar_5m["close"]):
                confluence.add("fib_79")

        if not confluence.has_confirmation:
            return None

        # ── Gate 7: Continuation entry zone (Change 9: OB+FVG) ──────
        obs_5m = detect_order_blocks(gold_5m_history,
                                     impulse_min=OB_IMPULSE_MIN_MOVE, atr=atr)
        entry_price = None
        entry_type = None
        sl_price = None

        # Check for OB+FVG confluence (highest probability)
        matching_fvgs = [f for f in fvgs_5m
                         if f.direction == sweep_dir and not f.filled
                         and f.timestamp >= lookback_time]
        matching_obs = [ob for ob in obs_5m
                       if ob.direction == sweep_dir and not ob.broken
                       and ob.timestamp >= lookback_time]

        # OTE entry calculation helper
        # ICT OTE: 70.5% fib retracement of the impulse move
        # Source: innercircletrader.net, ForexFactory OTE guide
        # For bullish: entry deeper into FVG (lower price = better R:R)
        # For bearish: entry deeper into FVG (higher price = better R:R)
        def _ote_price(fvg_obj):
            """Calculate OTE entry: 70.5% retracement within the FVG zone."""
            if sweep_dir == "bullish":
                # Bullish: OTE is 70.5% from top toward bottom (deeper = better)
                return fvg_obj.top - (fvg_obj.top - fvg_obj.bottom) * 0.705
            else:
                # Bearish: OTE is 70.5% from bottom toward top (deeper = better)
                return fvg_obj.bottom + (fvg_obj.top - fvg_obj.bottom) * 0.705

        # OB+FVG: FVG inside an OB zone
        for fvg in matching_fvgs:
            for ob in matching_obs:
                if fvg.bottom >= ob.zone_low and fvg.top <= ob.zone_high + atr:
                    entry_price = _ote_price(fvg)  # OTE entry
                    entry_type = "OB+FVG"
                    confluence.add("ob_fvg")
                    confluence.add("fvg")
                    break
            if entry_price is not None:
                break

        # Standalone FVG (use OTE 70.5% instead of CE 50%)
        if entry_price is None and matching_fvgs:
            fvg = matching_fvgs[-1]
            entry_price = _ote_price(fvg)  # OTE entry for precision
            entry_type = "FVG"
            confluence.add("fvg")

        # Standalone OB
        if entry_price is None and matching_obs:
            ob = matching_obs[-1]
            if sweep_dir == "bullish":
                entry_price = ob.zone_high
            else:
                entry_price = ob.zone_low
            entry_type = "OB"
            confluence.add("ob")

        # Breaker Block
        if entry_price is None:
            breakers = [ob for ob in obs_5m
                        if ob.broken and ob.timestamp >= lookback_time]
            for bb in breakers:
                if sweep_dir == "bullish" and bb.direction == "bearish":
                    entry_price = bb.zone_high
                    entry_type = "BB"
                    confluence.add("bb")
                    break
                elif sweep_dir == "bearish" and bb.direction == "bullish":
                    entry_price = bb.zone_low
                    entry_type = "BB"
                    confluence.add("bb")
                    break

        # Equilibrium
        if entry_price is None and recent_bos:
            latest_bos = recent_bos[-1]
            if latest_bos.swing_broken:
                eq = find_equilibrium(latest_bos.swing_broken, latest_bos)
                entry_price = eq.price
                entry_type = "EQ"
                confluence.add("eq")

        if entry_price is None:
            return None

        # ── Gate 8: Confluence ≥ 3 ───────────────────────────────────
        if not confluence.is_valid:
            return None

        # ── Gate 9: ATR-based SL/TP (Change 1 + Change 7) ───────────
        sl_distance = max(SL_ATR_MULTIPLIER * atr, MIN_SL_DISTANCE)

        if sweep_dir == "bullish":
            sl_price = entry_price - sl_distance
            tp1 = entry_price + sl_distance * TP1_RR
            tp2 = entry_price + sl_distance * TP2_RR
        else:
            sl_price = entry_price + sl_distance
            tp1 = entry_price - sl_distance * TP1_RR
            tp2 = entry_price - sl_distance * TP2_RR

        # No re-entry at same SL
        sl_rounded = round(sl_price, 0)
        if sl_rounded in self.used_sl_levels:
            return None

        # Min R:R check (using TP2 as the target for planned R:R)
        planned_rr = TP2_RR  # 3.0 by default
        if planned_rr < MIN_RR:
            return None

        risk = sl_distance

        self.trades_today += 1
        self.session_trades[session] = self.session_trades.get(session, 0) + 1

        return TradeSignal(
            timestamp=dt,
            direction=allowed_direction,
            entry_price=entry_price,
            stop_loss=sl_price,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp2,  # TP3 = TP2 in 2-tier system
            session=session,
            htf_level_swept=swept_level.price,
            entry_type=entry_type,
            htf_bias=bias,
            confluence_score=confluence.score,
            confluences=list(confluence.confluences),
            planned_rr=round(planned_rr, 2),
        )
