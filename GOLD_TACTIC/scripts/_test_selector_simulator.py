#!/usr/bin/env python3
"""Simulator for the GOLD TACTIC v7.3 selector logic with all 7 B-improvements.

B1 — Asset class diversification (max 2 per class)
B2 — Direction-aware news scoring
B3 — Looser alignment (WEAK_BULL/BEAR awareness — applied at quick_scan level)
B4 — RSI criterion (0-2 pts)
B5 — Brain state input (regime_state.json)
B6 — All-12-asset visibility
B7 — Score breakdown per criterion

Inputs:  GOLD_TACTIC/data/{live_prices,quick_scan,news_feed,regime_state}.json
Output:  GOLD_TACTIC/data/review/test_selector_<date>_output.json
"""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
EET = timezone(timedelta(hours=3))
ROOT = Path(__file__).parent.parent

prices = json.load(open(ROOT / 'data/live_prices.json', encoding='utf-8'))
scan = json.load(open(ROOT / 'data/quick_scan.json', encoding='utf-8'))
news = json.load(open(ROOT / 'data/news_feed.json', encoding='utf-8'))

# B5 — read brain state if available (graceful fallback)
regime_state = {}
if (ROOT / 'data/regime_state.json').exists():
    try:
        regime_state = json.load(open(ROOT / 'data/regime_state.json', encoding='utf-8'))
    except Exception:
        regime_state = {}

now = datetime.now(EET)
hour = now.hour + now.minute / 60
dow = now.weekday()
in_london_kz = 10 <= hour < 12
in_ny_kz = 15.5 <= hour < 17.5
session_weekend = dow >= 5
print(f"Time: {now.strftime('%Y-%m-%d %H:%M EET')} (DoW={dow})")
print(f"London KZ={in_london_kz}, NY KZ={in_ny_kz}, weekend={session_weekend}")
regime_label = regime_state.get('regime', {}).get('label', 'unknown')
regime_conviction = regime_state.get('regime', {}).get('conviction', 'low')
vix_tier = regime_state.get('vix', {}).get('tier', 'normal')
print(f"Brain: regime={regime_label} conv={regime_conviction} vix={vix_tier}")

news_summary = news.get('summary', {})
ASSETS_LIST = ['EURUSD','GBPUSD','USDJPY','AUDUSD','XAUUSD','NAS100','SPX500','BTC','ETH','SOL','XRP','DXY']
ASSET_CLASS = {
    'EURUSD':'forex','GBPUSD':'forex','USDJPY':'forex','AUDUSD':'forex',
    'XAUUSD':'metal','NAS100':'index','SPX500':'index',
    'BTC':'crypto','ETH':'crypto','SOL':'crypto','XRP':'crypto','DXY':'dxy',
}
# B1 — liquidity priority for tiebreakers (higher = preferred when scores tie)
LIQUIDITY_RANK = {
    'BTC': 4, 'ETH': 3, 'SOL': 2, 'XRP': 1,
    'EURUSD': 4, 'GBPUSD': 3, 'USDJPY': 2, 'AUDUSD': 1,
    'NAS100': 2, 'SPX500': 2,
    'XAUUSD': 1, 'DXY': 1,
}
scan_by_sym = {r['asset']: r for r in scan.get('assets', scan.get('results', []))}

def score_asset(sym):
    s = scan_by_sym.get(sym, {})
    p = prices.get('prices', {}).get(sym, {})
    cls = ASSET_CLASS[sym]
    align = s.get('alignment', 'MIXED')
    rsi_d = s.get('rsi_daily') or 50
    rsi_4h = s.get('rsi_4h') or 50

    # 1. Alignment 0-3
    align_pts = {'ALIGNED_BULL': 3, 'ALIGNED_BEAR': 3,
                 'PARTIAL_BULL': 2, 'PARTIAL_BEAR': 2, 'MIXED': 1}.get(align, 0)

    # Determine direction_bias from alignment (B2 prerequisite)
    if 'BULL' in align:
        bias = 'LONG'
    elif 'BEAR' in align:
        bias = 'SHORT'
    else:
        bias = 'NEUTRAL'

    # 2. News (direction-aware) 0-2
    nsum = news_summary.get(sym, {})
    overall = nsum.get('overall_sentiment', 'neutral')
    if bias == 'NEUTRAL' or overall == 'neutral':
        news_pts = 1
    elif (overall == 'bullish' and bias == 'LONG') or \
         (overall == 'bearish' and bias == 'SHORT'):
        news_pts = 2  # aligned/supportive
    else:
        news_pts = 0  # contra

    # 3. ADR remaining 0-2
    adr_pct = s.get('adr_consumed_pct', 0) or 0
    if adr_pct < 50:
        adr_pts = 2
    elif adr_pct < 70:
        adr_pts = 1
    else:
        adr_pts = 0

    # 4. RSI condition 0-2 (B4)
    rsi_pts = 0
    if rsi_d <= 25 or rsi_d >= 75:
        rsi_pts = 2  # strong extreme — reversal candidate
    elif (25 < rsi_d <= 30 or 70 <= rsi_d < 75):
        # mild extreme — only +2 if alignment matches reversal direction
        if rsi_d <= 30 and bias == 'SHORT':
            rsi_pts = 0  # falling knife
        elif rsi_d >= 70 and bias == 'LONG':
            rsi_pts = 0  # late entry
        else:
            rsi_pts = 2
    elif 35 <= rsi_d <= 65 and bias != 'NEUTRAL':
        rsi_pts = 1  # healthy continuation
    else:
        rsi_pts = 0

    # 5. Strategy applicable 0-2
    strat_pts = 2 if 'ALIGNED' in align else (1 if 'PARTIAL' in align else 0)

    # 6. Market hours 0-1
    if cls == 'crypto':
        market_pts = 1
    elif cls == 'index':
        market_pts = 1 if 16 <= hour <= 23 else 0
    elif cls in ('forex', 'metal', 'dxy'):
        market_pts = 0 if session_weekend else 1
    else:
        market_pts = 0

    score = align_pts + news_pts + adr_pts + rsi_pts + strat_pts + market_pts

    # Status
    if adr_pct > 120:
        status = 'blocked'
        reason = f'ADR consumed {adr_pct}% — extreme volatility'
    elif adr_pct >= 95:
        status = 'monitoring_only'
        reason = f'ADR consumed {adr_pct}% — borderline'
    elif cls == 'index' and not (16 <= hour <= 23):
        status = 'monitoring_only'
        reason = 'Index outside cash hours (16:00-23:00 EET)'
    elif cls in ('forex', 'metal') and session_weekend:
        status = 'blocked'
        reason = 'Forex closed on weekend'
    else:
        status = 'tradeable'
        reason = f'OK — {align}, ADR {adr_pct}%, news {overall} (bias {bias})'

    return {
        'symbol': sym, 'asset_class': cls, 'price': p.get('price', '?'),
        'realtime_source': p.get('realtime_source', '?'),
        'score': score, 'direction_bias': bias,
        'breakdown': {
            'align': f'{align_pts}/3',
            'news': f'{news_pts}/2',
            'adr': f'{adr_pts}/2',
            'rsi': f'{rsi_pts}/2',
            'strat': f'{strat_pts}/2',
            'mkt': f'{market_pts}/1',
        },
        'status': status, 'block_reason': reason if status != 'tradeable' else None,
        'rsi_d': rsi_d, 'rsi_4h': rsi_4h, 'regime': s.get('regime', '?'),
        'adr_pct': adr_pct, 'alignment': align,
        'news_sentiment': overall, 'liquidity': LIQUIDITY_RANK.get(sym, 0),
    }


# Score all assets
all_scored = [score_asset(s) for s in ASSETS_LIST]

# B2 enhancement: if alignment=MIXED but news has strong directional sentiment,
# use news to derive bias (gives the asset a chance at a non-zero direction).
for r in all_scored:
    if r['direction_bias'] == 'NEUTRAL':
        if r['news_sentiment'] == 'bullish':
            r['direction_bias'] = 'LONG'
            r['bias_source'] = 'news'
        elif r['news_sentiment'] == 'bearish':
            r['direction_bias'] = 'SHORT'
            r['bias_source'] = 'news'
        else:
            r['bias_source'] = 'neutral'
    else:
        r['bias_source'] = 'alignment'

# Sort priority: tradeable beats monitoring beats blocked at same score
# (tradeable assets fill top-4 first; user still sees blocked/monitoring as
# excluded entries with their own score breakdown).
STATUS_PRIORITY = {'tradeable': 0, 'monitoring_only': 1, 'blocked': 2}
all_scored.sort(key=lambda x: (
    STATUS_PRIORITY[x['status']],   # tradeable first
    -x['score'],                    # then by score DESC
    -x['liquidity'],                # then by liquidity DESC
    x['symbol'],                    # alphabetical (deterministic last-resort)
))


# B1 — Class diversification (max 2 per class)
def diversified_top4(sorted_assets, max_per_class=2):
    picked = []
    skip_log = []  # (asset, reason)
    class_count = {}
    for a in sorted_assets:
        cls = a['asset_class']
        if class_count.get(cls, 0) >= max_per_class:
            skip_log.append((a, 'diversity_skip'))
            continue
        picked.append(a)
        class_count[cls] = class_count.get(cls, 0) + 1
        if len(picked) == 4:
            break
    # Backfill if fewer than 4 (shouldn't happen with 12 assets but be safe)
    if len(picked) < 4:
        for a in sorted_assets:
            if a not in picked and a not in [s[0] for s in skip_log]:
                picked.append(a)
                if len(picked) == 4:
                    break
    return picked, skip_log

top4, diversity_skips = diversified_top4(all_scored)
top4_syms = {a['symbol'] for a in top4}
diversity_skip_syms = {s[0]['symbol'] for s in diversity_skips}
excluded = [a for a in all_scored if a['symbol'] not in top4_syms]

# Annotate exclude reason
for a in excluded:
    if a['symbol'] in diversity_skip_syms:
        a['exclude_reason'] = 'diversity_skip'
    else:
        a['exclude_reason'] = 'score_too_low'

# Compute diversity note
class_count_in_top4 = {}
for a in top4:
    class_count_in_top4[a['asset_class']] = class_count_in_top4.get(a['asset_class'], 0) + 1
diversity_note = ' + '.join(f"{v} {k}" for k, v in sorted(class_count_in_top4.items(), key=lambda x: -x[1]))

print()
print("=" * 120)
print("ALL 12 ASSETS SCORED (with B1+B2+B3+B4+B5+B7 improvements)")
print("=" * 120)
header = f"{'Rank':<7}{'Symbol':<8}{'Score':<8}{'Bias':<8}{'Status':<18}{'Class':<8}{'Price':<14}Breakdown"
print(header)
print("-" * 120)
for i, r in enumerate(all_scored):
    if r['symbol'] in top4_syms:
        pos = "TOP-4"
    elif r['symbol'] in diversity_skip_syms:
        pos = "div-skip"
    else:
        pos = "  excl"
    p_str = str(r['price'])[:12] if r['price'] != '?' else '?'
    bd = (f"al={r['breakdown']['align']:<5}"
          f"nw={r['breakdown']['news']:<5}"
          f"adr={r['breakdown']['adr']:<5}"
          f"rsi={r['breakdown']['rsi']:<5}"
          f"st={r['breakdown']['strat']:<5}"
          f"mkt={r['breakdown']['mkt']:<5}")
    print(f"{pos:<7}{r['symbol']:<8}{r['score']:<8}{r['direction_bias']:<8}{r['status']:<18}{r['asset_class']:<8}{p_str:<14}{bd}")

print()
print("=" * 120)
print(f"TOP-4 SELECTED (after B1 diversification: {diversity_note})")
print("=" * 120)
for i, r in enumerate(top4, 1):
    icon = {'tradeable': '[OK]   ', 'monitoring_only': '[WATCH]',
            'blocked': '[BLOCK]'}[r['status']]
    print(f"{icon} #{i} {r['symbol']:<8} score={r['score']:>2} bias={r['direction_bias']:<8} "
          f"status={r['status']:<18} class={r['asset_class']}")
    print(f"        Price: {r['price']} via {r['realtime_source']}  |  "
          f"RSI(D): {r['rsi_d']:.0f} | Regime: {r['regime']} | ADR: {r['adr_pct']}% | News: {r['news_sentiment']}")
    if r['block_reason']:
        print(f"        Reason: {r['block_reason']}")
    print()

# Status distribution
status_dist = {'all12': {}, 'top4': {}}
for a in all_scored:
    status_dist['all12'][a['status']] = status_dist['all12'].get(a['status'], 0) + 1
for a in top4:
    status_dist['top4'][a['status']] = status_dist['top4'].get(a['status'], 0) + 1

print("=" * 120)
print(f"All 12 status distribution: {status_dist['all12']}")
print(f"Top-4 status distribution : {status_dist['top4']}")
print(f"Diversification result    : {diversity_note}")
print()

# Save selected_assets.json with new schema (v2)
selected_doc = {
    "timestamp": now.isoformat(timespec='seconds'),
    "selector_run": "TEST_SIMULATION_v2_2026-04-30",
    "schema_version": "v2",
    "selected": [
        {
            "symbol": r['symbol'], "score": r['score'], "status": r['status'],
            "block_reason": r['block_reason'],
            "direction_bias": r['direction_bias'],
            "reason": r['block_reason'] if r['block_reason'] else f"tradeable {r['alignment']}",
            "reasons": [
                f"Alignment: {r['alignment']} (RSI D={r['rsi_d']:.0f})",
                f"News: {r['news_sentiment']} → {r['breakdown']['news']} (bias-aware)",
                f"ADR: {r['adr_pct']}% consumed → {r['breakdown']['adr']}",
            ],
            "recent_lessons": [],
            "narrative_seed": f"{r['symbol']} {r['alignment']} με {r['news_sentiment']} news. Watching ADR {r['adr_pct']}% consumed at {r['regime']} regime.",
            "strategy": "—", "key_level": None, "what_to_watch": "—",
            "asset_class": r['asset_class'], "score_breakdown": r['breakdown'],
        }
        for r in top4
    ],
    "excluded_below_top4": [
        {"symbol": r['symbol'], "score": r['score'],
         "status": r['status'], "reason": r['exclude_reason']}
        for r in excluded
    ],
    "market_context": (
        f"Test simulation at {now.strftime('%H:%M EET')}, "
        f"session={'London KZ' if in_london_kz else 'NY KZ' if in_ny_kz else 'off-hours'}. "
        f"diversification_applied: {diversity_note}. "
        f"Brain state: regime={regime_label} conv={regime_conviction} vix={vix_tier}."
    ),
}
out_path = ROOT / 'data/review/test_selector_2026-04-30_output.json'
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(selected_doc, f, ensure_ascii=False, indent=2)
print(f"Output saved to: {out_path.relative_to(ROOT.parent)}")
