# Scanner v2.0 — Dynamic Universe + Smart Selection

**Date:** 2026-04-05
**Author:** Aggelos + Claude
**Status:** APPROVED

## Problem

Scanner v1 examines the SAME 7 assets every day with subjective AI scoring (1-10). On days when all 7 are choppy, it finds NOTHING. The opportunity scanner (15 extra assets) exists but is barely used. Selection is AI-subjective, not algorithmic.

## Solution: 2-Phase Dynamic Scanner

### Phase 1: Wide Scan (20 assets, lightweight, 08:00 + 15:30 EET)

**Universe: 7 core + up to 13 extended**

Core (always scanned):
| Asset | Strategies Available |
|-------|---------------------|
| EURUSD | TJR Asia Sweep, Session H/L Fade |
| GBPUSD | TJR Asia Sweep, Session H/L Fade |
| NAS100 | IBB Breakout |
| XAUUSD | Gold NY Killzone |
| BTC | Crypto Trend, Mean Reversion |
| SOL | Crypto Trend, Mean Reversion |
| ETH | Mean Reversion (weekend only) |

Extended (scanned for opportunity):
| Assets | Type | Strategy if Selected |
|--------|------|---------------------|
| AAPL, TSLA, NVDA, META, AMZN | US Tech Stocks | ORB/Momentum (future) |
| MSFT, GOOGL, AMD | US Tech Stocks | ORB/Momentum (future) |
| COIN, MSTR | Crypto-adjacent | Momentum |
| PLTR, SQ, INTC | Growth/Value | Momentum |

**Wide Scan metrics (per asset, fast computation):**
```
1. ADX (daily) → regime classification: TRENDING(>25) / RANGING(15-25) / CHOPPY(<15)
2. RSI (daily) → zone: OVERSOLD(<30) / NEUTRAL(30-70) / OVERBOUGHT(>70)
3. ADR consumed % → room remaining
4. Volume ratio → today vs 20-day average
5. PDH/PDL proximity → how close to sweep level
```

**Opportunity Score formula (algorithmic, NOT AI-subjective):**

```
opportunity_score = (regime_fit × 0.30) + (setup_proximity × 0.30) +
                    (volume_signal × 0.20) + (adr_room × 0.20)

Each component scores 0-100:

regime_fit:
  Strategy matches regime = 100
  (e.g., ADX>25 + TJR available = 100)
  (e.g., ADX<20 + Session Fade available = 100)
  Strategy mismatches regime = 0
  (e.g., ADX>25 but only range strategy = 0)
  CHOPPY (ADX<15) = 0 always (no strategy works)

setup_proximity:
  Price within 5% of PDH/PDL = 100 (very close to sweep)
  Price within 15% = 70
  Price within 30% = 40
  Price far from levels = 10

volume_signal:
  Volume > 2.0x 20-day avg = 100 (institutional interest)
  Volume > 1.5x = 80
  Volume > 1.2x = 60
  Volume normal (0.8-1.2) = 40
  Volume low (<0.8) = 10

adr_room:
  ADR consumed < 20% = 100 (full day ahead)
  ADR consumed < 40% = 80
  ADR consumed < 60% = 60
  ADR consumed < 85% = 30
  ADR consumed > 85% = 0 (BLOCKED)
```

**Wide Scan output: Ranked list sorted by opportunity_score descending**

### Phase 2: Deep Scan (top 3 only)

From the ranked list, select top 3 with score >= 50:

**Selection rules:**
1. Take #1 highest score → Slot 1
2. Take #2 → but check correlation with #1
   - If correlation > 0.80 with #1 → skip, take #3 instead
3. Take next uncorrelated → Slot 3
4. If < 3 assets score >= 50 → fewer slots (don't force bad picks)

**Correlation pairs that block each other:**
- EURUSD ↔ GBPUSD (>0.80 = pick one)
- BTC ↔ SOL (>0.80 = pick one)
- BTC ↔ ETH (>0.80 = pick one)
- NAS100 ↔ AAPL/TSLA (>0.70 = pick one, highly correlated)

**Deep Scan per selected asset:**
- Full TRS scoring (strategy-specific 5 criteria)
- News impact assessment
- Proximity meter + time estimation
- Bollinger Band position (for mean reversion assets)
- Session window check (is asset in its optimal trading hours?)

**Output: scanner_watchlist.json v2.0**
```json
{
  "scan_timestamp": "2026-04-05T08:00:00+03:00",
  "scan_type": "morning",
  "phase1_results": {
    "total_scanned": 20,
    "scored": [
      {"asset": "EURUSD", "opportunity_score": 82, "regime": "TRENDING", "strategy": "TJR"},
      {"asset": "BTC", "opportunity_score": 71, "regime": "RANGING", "strategy": "Mean Reversion"},
      {"asset": "NAS100", "opportunity_score": 65, "regime": "TRENDING", "strategy": "IBB"},
      ...
    ]
  },
  "active_slots": [
    {"slot": 1, "asset": "EURUSD", "score": 82, "strategy": "TJR", "trs": 3},
    {"slot": 2, "asset": "BTC", "score": 71, "strategy": "Mean Reversion", "trs": 2},
    {"slot": 3, "asset": "NAS100", "score": 65, "strategy": "IBB", "trs": null, "note": "Afternoon activation"}
  ],
  "standby": ["GBPUSD", "SOL"],
  "skip": ["XAUUSD", "ETH", "AAPL", "TSLA", ...],
  "skip_reasons": {
    "XAUUSD": "CHOPPY (ADX 12) — no strategy",
    "ETH": "Weekday — weekend only",
    "AAPL": "No strategy implemented yet"
  }
}
```

### Phase 3: Continuous Monitoring (3 slots)

Selected assets get price downloads every 10-30 minutes:

| Cycle | What runs | Per asset |
|-------|-----------|-----------|
| Every 30' (quiet) | quick_scan.py | Price, RSI, ADR update |
| Every 10' (active) | quick_scan + trs_calculator | Full TRS reassessment |
| On trigger | Full TIER 3a | Trade execution + Telegram |

**Slot swap rules (mid-day):**
- If active asset ADR > 85% → swap with top STANDBY
- If active asset TRS drops to 0-1 for 3 consecutive cycles → swap
- If breaking news makes STANDBY score jump > active score → swap
- Afternoon scanner (15:30) can fully reshuffle based on new scores

**Trade trigger:** TRS >= 4 (scanner asset) or TRS >= 5 (emergency/new asset)

### Afternoon Scanner (15:30 EET)

Re-runs Phase 1 Wide Scan with fresh data:
- New ADR consumed values (8 hours of trading)
- New volume data
- Updated news sentiment
- NAS100 now in NY hours → properly scored

**Changes only:** If afternoon ranking differs from morning:
- New #1 that wasn't in morning → promote to active
- Morning active that dropped to score < 40 → demote
- Telegram: ONLY report changes ("🔄 NAS100 replaces GBPUSD")

---

## Implementation

### New script: `opportunity_score.py`

```python
def wide_scan(assets_config) -> list[dict]:
    """Phase 1: Score all assets, return sorted list."""

def compute_opportunity_score(asset_data, available_strategies) -> int:
    """Algorithmic score 0-100."""

def select_slots(ranked_assets, correlation_data, max_slots=3) -> list[dict]:
    """Phase 2: Pick top uncorrelated assets."""

def should_swap(current_slots, new_rankings) -> list[dict]:
    """Afternoon: Determine if slots should change."""
```

### Modified files:
| File | Change |
|------|--------|
| `scripts/opportunity_score.py` | NEW — replaces opportunity_scanner.py |
| `prompts/adaptive_analyst.md` | Update scanner steps to use 2-phase flow |
| `prompts/scanner_morning_v6.md` | Simplify — AI reads opportunity_score output |
| `prompts/scanner_afternoon_v6.md` | Changes-only mode |
| `scripts/trs_calculator.py` | Add strategy-specific TRS |

### Data files:
| File | Change |
|------|--------|
| `data/scanner_watchlist.json` | v2.0 format with phase1_results + active_slots |
| `data/opportunities.json` | Retired — merged into scanner_watchlist |

---

## Key Principles

1. **Regime first, strategy second.** ADX determines which strategies are eligible.
2. **Algorithmic scoring, not AI gut.** Opportunity Score = formula, reproducible.
3. **Dynamic universe.** Bad day for forex? Scanner picks crypto/gold instead.
4. **3 slots max.** Focus beats breadth. Quality over quantity.
5. **Afternoon reshuffles.** Morning picks aren't sacred — data changes.
6. **Correlation guard.** Never 2 highly-correlated assets in active slots.
