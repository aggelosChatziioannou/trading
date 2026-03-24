"""Multi-timeframe ICT entry model with sequential gates."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from config.settings import (
    SWING_LOOKBACK, FVG_EXPIRY_BARS, TP1_RR, TP2_RR,
    SPREAD, OB_IMPULSE_MIN_MOVE,
)
from ict.structures import find_all_swings, detect_bos, SwingPoint, BOS
from ict.fvg import detect_fvgs, FVG
from ict.order_blocks import detect_order_blocks, OB
from ict.liquidity import (
    LiquidityLevel, check_liquidity_sweep,
    get_session_levels, get_swing_liquidity, find_equal_levels,
)
from ict.smt import detect_smt
from ict.equilibrium import find_equilibrium
from strategy.session_filter import should_trade
from strategy.signal import TradeSignal


class ICTEntryModel:
    """Stateful entry model that tracks ICT structures across bars."""

    def __init__(self):
        self.htf_levels: list[LiquidityLevel] = []
        self.active_sweep: LiquidityLevel | None = None
        self.sweep_direction: str | None = None

        self.fvgs_5m: list[FVG] = []
        self.obs_5m: list[OB] = []
        self.bos_5m: list[BOS] = []
        self.swings_5m: list[SwingPoint] = []

        self.last_htf_update: datetime | None = None
        self.trades_today: int = 0
        self.current_date = None

    def update_htf_levels(
        self,
        gold_1h: pd.DataFrame,
        gold_4h: pd.DataFrame,
        gold_5m: pd.DataFrame,
    ):
        """Rebuild HTF liquidity levels from 1H/4H data + session levels."""
        self.htf_levels = []

        # Session levels from 5-min data
        self.htf_levels.extend(get_session_levels(gold_5m))

        # 1H swing levels
        swings_1h = find_all_swings(gold_1h, lookback=3)
        self.htf_levels.extend(get_swing_liquidity(swings_1h, "1H"))

        # 4H swing levels
        swings_4h = find_all_swings(gold_4h, lookback=3)
        self.htf_levels.extend(get_swing_liquidity(swings_4h, "4H"))

        # Equal levels
        self.htf_levels.extend(find_equal_levels(swings_1h))
        self.htf_levels.extend(find_equal_levels(swings_4h))

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
        dxy_swings: list[SwingPoint] | None = None,
    ) -> TradeSignal | None:
        """Run all gates and return a signal if all pass."""

        dt = bar_5m.name

        # Reset daily counter
        if self.current_date != dt.date():
            self.current_date = dt.date()
            self.trades_today = 0

        # Gate 1: Session filter
        can_trade, session = should_trade(dt)
        if not can_trade:
            return None

        # Gate 2: Max trades check
        if self.trades_today >= 2:
            return None

        # Update structures periodically
        self.update_htf_levels(gold_1h, gold_4h, gold_5m_history)
        self.update_5m_structures(gold_5m_history)

        # Gate 3: HTF Liquidity sweep
        swept_level = None
        for level in self.htf_levels:
            if check_liquidity_sweep(level, bar_5m):
                level.swept = True
                swept_level = level
                break

        if swept_level is None and self.active_sweep is None:
            return None

        if swept_level is not None:
            self.active_sweep = swept_level
            if "high" in swept_level.type or swept_level.type == "equal_highs":
                self.sweep_direction = "bearish"
            else:
                self.sweep_direction = "bullish"

        # Gate 4: 5-min BOS in expected direction
        recent_bos = [b for b in self.bos_5m if b.direction == self.sweep_direction
                      and b.timestamp >= self.active_sweep.timestamp]
        if not recent_bos:
            return None

        latest_bos = recent_bos[-1]

        # Gate 5: Entry zone (FVG -> OB -> Breaker -> EQ)
        entry_price = None
        entry_type = None
        sl_price = None

        # Check FVGs
        matching_fvgs = [f for f in self.fvgs_5m
                         if f.direction == self.sweep_direction
                         and not f.filled
                         and f.timestamp >= self.active_sweep.timestamp]
        if matching_fvgs:
            fvg = matching_fvgs[-1]
            if self.sweep_direction == "bullish":
                entry_price = fvg.top
                sl_price = fvg.bottom - SPREAD
            else:
                entry_price = fvg.bottom
                sl_price = fvg.top + SPREAD
            entry_type = "FVG"

        # Check OBs if no FVG
        if entry_price is None:
            matching_obs = [ob for ob in self.obs_5m
                           if ob.direction == self.sweep_direction
                           and not ob.broken
                           and ob.timestamp >= self.active_sweep.timestamp]
            if matching_obs:
                ob = matching_obs[-1]
                if self.sweep_direction == "bullish":
                    entry_price = ob.zone_high
                    sl_price = ob.zone_low - SPREAD
                else:
                    entry_price = ob.zone_low
                    sl_price = ob.zone_high + SPREAD
                entry_type = "OB"

        # Check Breaker Blocks
        if entry_price is None:
            breakers = [ob for ob in self.obs_5m
                        if ob.broken
                        and ob.timestamp >= self.active_sweep.timestamp]
            if breakers:
                bb = breakers[-1]
                if self.sweep_direction == "bullish" and bb.direction == "bearish":
                    entry_price = bb.zone_high
                    sl_price = bb.zone_low - SPREAD
                    entry_type = "BB"
                elif self.sweep_direction == "bearish" and bb.direction == "bullish":
                    entry_price = bb.zone_low
                    sl_price = bb.zone_high + SPREAD
                    entry_type = "BB"

        # Check Equilibrium
        if entry_price is None and latest_bos.swing_broken:
            eq = find_equilibrium(latest_bos.swing_broken, latest_bos)
            entry_price = eq.price
            if self.sweep_direction == "bullish":
                sl_price = latest_bos.swing_broken.price - SPREAD
            else:
                sl_price = latest_bos.swing_broken.price + SPREAD
            entry_type = "EQ"

        if entry_price is None:
            return None

        # Calculate TPs
        risk = abs(entry_price - sl_price)
        if risk <= 0:
            return None

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
                key=lambda l: l.price,
                reverse=True,
            )
            tp3 = lower_levels[0].price if lower_levels else tp2 - risk

        direction = "long" if self.sweep_direction == "bullish" else "short"

        # SMT divergence check (optional confidence boost)
        confidence = 1.0
        if dxy_swings:
            smt_signals = detect_smt(self.swings_5m, dxy_swings)
            matching_smt = [s for s in smt_signals
                           if s.direction == self.sweep_direction
                           and abs((s.timestamp - dt).total_seconds()) < 1800]
            if matching_smt:
                confidence = 1.2

        swept_price = self.active_sweep.price if self.active_sweep else 0.0
        self.trades_today += 1
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
            confidence=confidence,
        )
