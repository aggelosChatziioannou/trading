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
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from config.settings import (
    SWING_LOOKBACK, FVG_EXPIRY_BARS, TP1_RR, TP2_RR, MIN_RR,
    SPREAD, OB_IMPULSE_MIN_MOVE,
)
from ict.structures import (
    find_all_swings, detect_bos, determine_market_structure,
    SwingPoint, BOS, MarketStructure,
)
from ict.fvg import detect_fvgs, update_fvg_status, FVG
from ict.order_blocks import detect_order_blocks, update_ob_status, OB
from ict.liquidity import (
    LiquidityLevel, AsiaRange,
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
    """Stateful entry model tracking ICT structures across bars."""

    def __init__(self):
        self.htf_levels: list[LiquidityLevel] = []
        self.asia_ranges: list[AsiaRange] = []
        self.active_sweep: LiquidityLevel | None = None
        self.sweep_direction: str | None = None
        self.sweep_bar_time: datetime | None = None  # When the sweep actually happened
        self.htf_bias: MarketStructure | None = None

        self.fvgs_5m: list[FVG] = []
        self.obs_5m: list[OB] = []
        self.bos_5m: list[BOS] = []
        self.swings_5m: list[SwingPoint] = []

        self.last_htf_update = None
        self.current_date = None
        self.used_levels: set[float] = set()  # No re-entry at same level

    def update_htf_levels(
        self,
        gold_1h: pd.DataFrame,
        gold_4h: pd.DataFrame,
        gold_5m: pd.DataFrame,
    ):
        """Rebuild HTF liquidity levels."""
        self.htf_levels = []

        # Session levels
        self.htf_levels.extend(get_session_levels(gold_5m))

        # PDH / PDL
        self.htf_levels.extend(get_pdh_pdl(gold_1h))

        # 1H swing levels
        swings_1h = find_all_swings(gold_1h, lookback=3)
        self.htf_levels.extend(get_swing_liquidity(swings_1h, "1H"))

        # 4H swing levels
        swings_4h = find_all_swings(gold_4h, lookback=3)
        self.htf_levels.extend(get_swing_liquidity(swings_4h, "4H"))

        # Equal levels
        self.htf_levels.extend(find_equal_levels(swings_1h))
        self.htf_levels.extend(find_equal_levels(swings_4h))

        # Asia ranges
        self.asia_ranges = get_asia_ranges(gold_5m)

    def update_htf_bias(self, gold_1h: pd.DataFrame, gold_4h: pd.DataFrame):
        """Determine HTF market structure bias."""
        ms_1h = determine_market_structure(gold_1h, lookback=3)
        ms_4h = determine_market_structure(gold_4h, lookback=3)

        # 4H takes priority, fall back to 1H
        if ms_4h.bias != "neutral":
            self.htf_bias = ms_4h
        elif ms_1h.bias != "neutral":
            self.htf_bias = ms_1h
        else:
            self.htf_bias = ms_4h  # neutral

    def update_5m_structures(self, gold_5m: pd.DataFrame):
        """Update 5-min ICT structures."""
        self.swings_5m = find_all_swings(gold_5m, lookback=SWING_LOOKBACK)
        self.bos_5m = detect_bos(gold_5m, lookback=SWING_LOOKBACK)
        self.fvgs_5m = detect_fvgs(gold_5m)
        self.obs_5m = detect_order_blocks(gold_5m, impulse_min=OB_IMPULSE_MIN_MOVE)

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
        """Run all gates and return a signal if all pass."""

        dt = bar_5m.name
        confluence = ConfluenceResult()

        # Reset daily state
        if self.current_date != dt.date():
            self.current_date = dt.date()
            self.used_levels = set()

        # Gate 1+2: Session + News filter
        can_trade, session = should_trade(dt)
        if not can_trade:
            return None

        # Update structures (throttle to every 5 bars for performance)
        if self.last_htf_update is None or bar_idx % 5 == 0:
            self.update_htf_levels(gold_1h, gold_4h, gold_5m_history)
            self.update_htf_bias(gold_1h, gold_4h)
            self.last_htf_update = dt
        self.update_5m_structures(gold_5m_history)

        # Gate 3: HTF bias MANDATORY
        if self.htf_bias is None or self.htf_bias.bias == "neutral":
            return None
        allowed_direction = "long" if self.htf_bias.bias == "bullish" else "short"
        confluence.add("htf_bias_aligned")

        # Gate 4: HTF Liquidity sweep
        swept_level = None
        sweep_type = None

        # Check Asia range sweep
        for asia in self.asia_ranges:
            asia_sweep = check_asia_sweep(asia, bar_5m)
            if asia_sweep is not None:
                price = asia.high if asia_sweep == "high" else asia.low
                if round(price, 2) in self.used_levels:
                    continue
                # Asia high swept = expect bearish, Asia low swept = expect bullish
                expected_dir = "short" if asia_sweep == "high" else "long"
                if expected_dir == allowed_direction:
                    swept_level = LiquidityLevel(
                        price=price, type=f"session_{asia_sweep}",
                        source="Asia", timestamp=dt,
                    )
                    sweep_type = "liquidity_sweep"
                    if asia_sweep == "high":
                        asia.high_swept = True
                    else:
                        asia.low_swept = True
                    break

        # Check other HTF levels
        if swept_level is None:
            for level in self.htf_levels:
                if round(level.price, 2) in self.used_levels:
                    continue
                if check_liquidity_sweep(level, bar_5m):
                    # Determine expected direction from sweep
                    if level.type in ("session_high", "pdh", "swing_high", "equal_highs"):
                        expected_dir = "short"
                    else:
                        expected_dir = "long"
                    if expected_dir == allowed_direction:
                        level.swept = True
                        swept_level = level
                        sweep_type = "pdh_pdl_sweep" if level.type in ("pdh", "pdl") else "liquidity_sweep"
                        break

        if swept_level is None and self.active_sweep is None:
            return None

        if swept_level is not None:
            self.active_sweep = swept_level
            self.sweep_direction = "bearish" if allowed_direction == "short" else "bullish"
            self.sweep_bar_time = dt
            confluence.add(sweep_type)
        elif self.active_sweep is not None:
            # Carry forward the sweep confluence from previous bar
            st = "pdh_pdl_sweep" if self.active_sweep.type in ("pdh", "pdl") else "liquidity_sweep"
            confluence.add(st)

        if self.active_sweep is None:
            return None

        # Expire sweep if too old (30 bars ~ 2.5 hours on 5m)
        sweep_time = self.sweep_bar_time or self.active_sweep.timestamp
        if hasattr(dt, 'tzinfo') and hasattr(sweep_time, 'tzinfo'):
            try:
                age = (dt - sweep_time).total_seconds()
                if age > 9000:  # 2.5 hours
                    self.active_sweep = None
                    self.sweep_direction = None
                    self.sweep_bar_time = None
                    return None
            except TypeError:
                pass

        # Gate 5: 5-min Confirmation (need at least 1)

        # BOS check
        recent_bos = [b for b in self.bos_5m
                      if b.direction == self.sweep_direction
                      and b.timestamp >= sweep_time]
        if recent_bos:
            confluence.add("bos")
            # Also check CHoCH
            choch_bos = [b for b in recent_bos if b.is_choch]
            if choch_bos:
                confluence.add("choch")

        # IFVG check
        recent_ifvgs = [f for f in self.fvgs_5m
                        if f.inverted and f.timestamp >= sweep_time]
        if recent_ifvgs:
            confluence.add("ifvg")

        # SMT divergence check
        if dxy_5m is not None and not dxy_5m.empty:
            dxy_swings = find_all_swings(dxy_5m, lookback=SWING_LOOKBACK)
            smt_signals = detect_smt(self.swings_5m, dxy_swings)
            matching_smt = [s for s in smt_signals
                           if s.direction == self.sweep_direction
                           and abs((s.timestamp - dt).total_seconds()) < 3600]
            if matching_smt:
                confluence.add("smt")

        # 79% Fib extension check
        if len(self.swings_5m) >= 2:
            recent_swings = [s for s in self.swings_5m if s.timestamp >= sweep_time]
            if len(recent_swings) >= 2:
                fib = find_fib_79_extension(recent_swings[-2], recent_swings[-1])
                if check_fib_79_closure(fib, bar_5m["close"]):
                    confluence.add("fib_79")

        if not confluence.has_confirmation:
            return None

        # Gate 6: 5-min Continuation (FVG/OB/BB/EQ)
        entry_price = None
        entry_type = None
        sl_price = None

        # Check FVGs
        matching_fvgs = [f for f in self.fvgs_5m
                         if f.direction == self.sweep_direction
                         and not f.filled
                         and f.timestamp >= sweep_time]
        if matching_fvgs:
            fvg = matching_fvgs[-1]
            if self.sweep_direction == "bullish":
                entry_price = fvg.top
                sl_price = fvg.bottom - SPREAD
            else:
                entry_price = fvg.bottom
                sl_price = fvg.top + SPREAD
            entry_type = "FVG"
            confluence.add("fvg")

        # Check OBs
        if entry_price is None:
            matching_obs = [ob for ob in self.obs_5m
                           if ob.direction == self.sweep_direction
                           and not ob.broken
                           and ob.timestamp >= sweep_time]
            if matching_obs:
                ob = matching_obs[-1]
                if self.sweep_direction == "bullish":
                    entry_price = ob.zone_high
                    sl_price = ob.zone_low - SPREAD
                else:
                    entry_price = ob.zone_low
                    sl_price = ob.zone_high + SPREAD
                entry_type = "OB"
                confluence.add("ob")

        # Check Breaker Blocks
        if entry_price is None:
            breakers = [ob for ob in self.obs_5m
                        if ob.broken and ob.timestamp >= sweep_time]
            if breakers:
                bb = breakers[-1]
                if self.sweep_direction == "bullish" and bb.direction == "bearish":
                    entry_price = bb.zone_high
                    sl_price = bb.zone_low - SPREAD
                    entry_type = "BB"
                    confluence.add("bb")
                elif self.sweep_direction == "bearish" and bb.direction == "bullish":
                    entry_price = bb.zone_low
                    sl_price = bb.zone_high + SPREAD
                    entry_type = "BB"
                    confluence.add("bb")

        # Check Equilibrium
        if entry_price is None and recent_bos:
            latest_bos = recent_bos[-1]
            if latest_bos.swing_broken:
                eq = find_equilibrium(latest_bos.swing_broken, latest_bos)
                entry_price = eq.price
                if self.sweep_direction == "bullish":
                    sl_price = latest_bos.swing_broken.price - SPREAD
                else:
                    sl_price = latest_bos.swing_broken.price + SPREAD
                entry_type = "EQ"
                confluence.add("eq")

        if entry_price is None:
            return None

        # Gate 7: Confluence score check
        if not confluence.is_valid:
            return None

        # Calculate risk and TPs
        risk = abs(entry_price - sl_price)
        if risk <= 0:
            return None

        # Calculate TPs
        if self.sweep_direction == "bullish":
            tp1 = entry_price + risk * TP1_RR
            tp2 = entry_price + risk * TP2_RR
            higher_levels = sorted(
                [l for l in self.htf_levels if l.price > entry_price and not l.swept],
                key=lambda l: l.price,
            )
            tp3 = higher_levels[0].price if higher_levels else tp2 + risk
        else:
            tp1 = entry_price - risk * TP1_RR
            tp2 = entry_price - risk * TP2_RR
            lower_levels = sorted(
                [l for l in self.htf_levels if l.price < entry_price and not l.swept],
                key=lambda l: l.price, reverse=True,
            )
            tp3 = lower_levels[0].price if lower_levels else tp2 - risk

        # Gate 8: Min R:R check
        planned_rr = abs(tp3 - entry_price) / risk if risk > 0 else 0
        if planned_rr < MIN_RR:
            return None

        direction = allowed_direction

        # Mark level as used (no re-entry at same level)
        self.used_levels.add(round(self.active_sweep.price, 2))
        swept_price = self.active_sweep.price
        self.active_sweep = None
        self.sweep_direction = None

        return TradeSignal(
            timestamp=dt,
            direction=direction,
            entry_price=entry_price,
            stop_loss=sl_price,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            session=session,
            htf_level_swept=swept_price,
            entry_type=entry_type,
            htf_bias=self.htf_bias.bias,
            confluence_score=confluence.score,
            confluences=list(confluence.confluences),
            planned_rr=round(planned_rr, 2),
        )
