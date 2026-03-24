"""Multi-timeframe ICT entry model - TJR strategy with all gates.

Entry flow:
  Gate 1: Killzone active (London 2-5AM or NY 7-10AM EST)
  Gate 2: News filter (no CPI/PPI/FOMC/NFP)
  Gate 3: HTF bias determined (bullish = only long, bearish = only short)
  Gate 4: HTF liquidity sweep (1H/4H level, Asia range, PDH/PDL)
  Gate 5: 5-min confirmation (BOS/CHoCH/IFVG/SMT/79% fib) - min 1
  Gate 6: 5-min continuation (FVG/OB/BB/EQ) - min 1
  Gate 7: Confluence score >= 3 with all categories represented
  Gate 8: Min 1.5 R:R or skip

Stateless approach: each bar is evaluated independently.
ICT structures (FVG, OB, BOS) are detected on the rolling history window.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from config.settings import (
    SWING_LOOKBACK, TP1_RR, TP2_RR, MIN_RR,
    SPREAD, OB_IMPULSE_MIN_MOVE, MAX_TRADES_PER_DAY,
)
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
from ict.confluence import ConfluenceResult
from strategy.session_filter import should_trade
from strategy.signal import TradeSignal


class ICTEntryModel:
    """Entry model — mostly stateless per-bar evaluation.

    Only tracks across bars:
      - trades_today / current_date (daily trade limit)
      - used_sl_levels (no re-entry at exact same SL level after stop-out)
    """

    def __init__(self):
        self.current_date = None
        self.trades_today: int = 0
        self.used_sl_levels: set[float] = set()  # SL levels from stopped-out trades

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
        """Run all gates on this bar and return a signal if all pass."""

        dt = bar_5m.name
        confluence = ConfluenceResult()

        # Reset daily state
        if self.current_date != getattr(dt, 'date', lambda: dt)():
            self.current_date = getattr(dt, 'date', lambda: dt)()
            self.trades_today = 0
            self.used_sl_levels = set()

        # Daily trade limit
        if self.trades_today >= MAX_TRADES_PER_DAY:
            return None

        # ── Gate 1+2: Session + News ─────────────────────────────────
        can_trade, session = should_trade(dt)
        if not can_trade:
            return None

        # ── Gate 3: HTF Bias ─────────────────────────────────────────
        ms_4h = determine_market_structure(gold_4h, lookback=3)
        ms_1h = determine_market_structure(gold_1h, lookback=3)
        bias = ms_4h.bias if ms_4h.bias != "neutral" else ms_1h.bias
        if bias == "neutral":
            return None

        allowed_direction = "long" if bias == "bullish" else "short"
        sweep_dir = "bullish" if allowed_direction == "long" else "bearish"
        confluence.add("htf_bias_aligned")

        # ── Build levels for this bar ────────────────────────────────
        htf_levels = []
        htf_levels.extend(get_session_levels(gold_5m_history))
        htf_levels.extend(get_pdh_pdl(gold_1h))
        swings_1h = find_all_swings(gold_1h, lookback=3)
        swings_4h = find_all_swings(gold_4h, lookback=3)
        htf_levels.extend(get_swing_liquidity(swings_1h, "1H"))
        htf_levels.extend(get_swing_liquidity(swings_4h, "4H"))
        htf_levels.extend(find_equal_levels(swings_1h))
        htf_levels.extend(find_equal_levels(swings_4h))

        # ── Gate 4: Liquidity Sweep on THIS bar ──────────────────────
        swept_level = None
        sweep_type = None

        # Check Asia range sweep
        asia_ranges = get_asia_ranges(gold_5m_history)
        for asia in asia_ranges:
            result = check_asia_sweep(asia, bar_5m)
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

        # Check HTF levels
        if swept_level is None:
            for level in htf_levels:
                if check_liquidity_sweep(level, bar_5m):
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

        # ── Gate 5: Confirmation (BOS/CHoCH/IFVG/SMT/79% fib) ───────
        # Detect 5-min structures on the history window
        bos_5m = detect_bos(gold_5m_history, lookback=SWING_LOOKBACK)
        fvgs_5m = detect_fvgs(gold_5m_history)
        swings_5m = find_all_swings(gold_5m_history, lookback=SWING_LOOKBACK)

        # BOS: look for any BOS in the sweep direction within the last 20 bars
        lookback_time = gold_5m_history.index[max(0, len(gold_5m_history) - 20)]
        recent_bos = [b for b in bos_5m
                      if b.direction == sweep_dir
                      and b.timestamp >= lookback_time]
        if recent_bos:
            confluence.add("bos")
            if any(b.is_choch for b in recent_bos):
                confluence.add("choch")

        # IFVG: any inverted FVG in recent history
        recent_ifvgs = [f for f in fvgs_5m
                        if f.inverted
                        and f.timestamp >= lookback_time]
        if recent_ifvgs:
            confluence.add("ifvg")

        # SMT divergence
        if dxy_5m is not None and not dxy_5m.empty:
            dxy_swings = find_all_swings(dxy_5m, lookback=SWING_LOOKBACK)
            smt_signals = detect_smt(swings_5m, dxy_swings)
            if any(s.direction == sweep_dir for s in smt_signals[-5:]):
                confluence.add("smt")

        # 79% Fib extension
        if len(swings_5m) >= 2:
            fib = find_fib_79_extension(swings_5m[-2], swings_5m[-1])
            if check_fib_79_closure(fib, bar_5m["close"]):
                confluence.add("fib_79")

        if not confluence.has_confirmation:
            return None

        # ── Gate 6: Continuation (FVG/OB/BB/EQ) ─────────────────────
        obs_5m = detect_order_blocks(gold_5m_history, impulse_min=OB_IMPULSE_MIN_MOVE)
        entry_price = None
        entry_type = None
        sl_price = None

        # FVG
        matching_fvgs = [f for f in fvgs_5m
                         if f.direction == sweep_dir and not f.filled
                         and f.timestamp >= lookback_time]
        if matching_fvgs:
            fvg = matching_fvgs[-1]
            if sweep_dir == "bullish":
                entry_price = fvg.top
                sl_price = fvg.bottom - SPREAD
            else:
                entry_price = fvg.bottom
                sl_price = fvg.top + SPREAD
            entry_type = "FVG"
            confluence.add("fvg")

        # OB
        if entry_price is None:
            matching_obs = [ob for ob in obs_5m
                           if ob.direction == sweep_dir and not ob.broken
                           and ob.timestamp >= lookback_time]
            if matching_obs:
                ob = matching_obs[-1]
                if sweep_dir == "bullish":
                    entry_price = ob.zone_high
                    sl_price = ob.zone_low - SPREAD
                else:
                    entry_price = ob.zone_low
                    sl_price = ob.zone_high + SPREAD
                entry_type = "OB"
                confluence.add("ob")

        # Breaker Block
        if entry_price is None:
            breakers = [ob for ob in obs_5m
                        if ob.broken and ob.timestamp >= lookback_time]
            for bb in breakers:
                if sweep_dir == "bullish" and bb.direction == "bearish":
                    entry_price = bb.zone_high
                    sl_price = bb.zone_low - SPREAD
                    entry_type = "BB"
                    confluence.add("bb")
                    break
                elif sweep_dir == "bearish" and bb.direction == "bullish":
                    entry_price = bb.zone_low
                    sl_price = bb.zone_high + SPREAD
                    entry_type = "BB"
                    confluence.add("bb")
                    break

        # Equilibrium
        if entry_price is None and recent_bos:
            latest_bos = recent_bos[-1]
            if latest_bos.swing_broken:
                eq = find_equilibrium(latest_bos.swing_broken, latest_bos)
                entry_price = eq.price
                if sweep_dir == "bullish":
                    sl_price = latest_bos.swing_broken.price - SPREAD
                else:
                    sl_price = latest_bos.swing_broken.price + SPREAD
                entry_type = "EQ"
                confluence.add("eq")

        if entry_price is None:
            return None

        # ── Gate 7: Confluence ≥ 3 with all 3 categories ────────────
        if not confluence.is_valid:
            return None

        # ── Gate 8: Min R:R ──────────────────────────────────────────
        risk = abs(entry_price - sl_price)
        if risk <= 0:
            return None

        # No re-entry at the exact same SL
        sl_rounded = round(sl_price, 1)
        if sl_rounded in self.used_sl_levels:
            return None

        # Calculate TPs
        if sweep_dir == "bullish":
            tp1 = entry_price + risk * TP1_RR
            tp2 = entry_price + risk * TP2_RR
            higher = sorted([l for l in htf_levels if l.price > entry_price],
                           key=lambda l: l.price)
            tp3 = higher[0].price if higher else tp2 + risk
        else:
            tp1 = entry_price - risk * TP1_RR
            tp2 = entry_price - risk * TP2_RR
            lower = sorted([l for l in htf_levels if l.price < entry_price],
                          key=lambda l: l.price, reverse=True)
            tp3 = lower[0].price if lower else tp2 - risk

        planned_rr = abs(tp3 - entry_price) / risk if risk > 0 else 0
        if planned_rr < MIN_RR:
            return None

        self.trades_today += 1

        return TradeSignal(
            timestamp=dt,
            direction=allowed_direction,
            entry_price=entry_price,
            stop_loss=sl_price,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            session=session,
            htf_level_swept=swept_level.price,
            entry_type=entry_type,
            htf_bias=bias,
            confluence_score=confluence.score,
            confluences=list(confluence.confluences),
            planned_rr=round(planned_rr, 2),
        )
