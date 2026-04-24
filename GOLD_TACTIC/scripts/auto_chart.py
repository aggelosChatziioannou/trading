#!/usr/bin/env python3
"""
GOLD TACTIC — Auto Chart Sender
Generates 4H + 5min charts for an asset and sends to Telegram.
Called by Market Monitor when TRS >= 4.

Throttle: max 1 send per asset per 2 hours (data/chart_send_log.json)

Usage:
  python auto_chart.py XAUUSD          # Generate + send (throttled)
  python auto_chart.py XAUUSD --force  # Force send, ignore throttle
"""

import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR   = Path(__file__).parent.parent / "data"
SCRIPTS_DIR = Path(__file__).parent
THROTTLE_FILE = DATA_DIR / "chart_send_log.json"
THROTTLE_HOURS = 2

sys.path.insert(0, str(SCRIPTS_DIR))


def is_throttled(asset):
    if not THROTTLE_FILE.exists():
        return False
    try:
        log = json.loads(THROTTLE_FILE.read_text(encoding="utf-8"))
        last = log.get(asset)
        if not last:
            return False
        return (datetime.now() - datetime.fromisoformat(last)) < timedelta(hours=THROTTLE_HOURS)
    except Exception:
        return False


def update_throttle(asset):
    log = {}
    if THROTTLE_FILE.exists():
        try:
            log = json.loads(THROTTLE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    log[asset] = datetime.now().isoformat()
    THROTTLE_FILE.write_text(json.dumps(log, indent=2), encoding="utf-8")


def main():
    args = sys.argv[1:]
    force = "--force" in args
    args = [a for a in args if not a.startswith("--")]

    if not args:
        print("Usage: auto_chart.py <ASSET> [--force]")
        sys.exit(1)

    asset = args[0].upper()

    if not force and is_throttled(asset):
        print(f"[THROTTLE] {asset}: charts sent <{THROTTLE_HOURS}h ago. Use --force to override.")
        sys.exit(0)

    import chart_generator as cg

    asset_config = cg.ASSETS.get(asset)
    if not asset_config:
        cg.register_asset(asset)
        asset_config = cg.ASSETS.get(asset)
    if not asset_config:
        print(f"[ERROR] Unknown asset: {asset}")
        sys.exit(1)

    # Generate 4H and 5min charts
    generated = []
    for tf_name in ["4h", "5m"]:
        path = cg.generate_chart(asset, asset_config, tf_name, cg.TIMEFRAMES[tf_name])
        if path:
            print(f"  {tf_name}: OK")
            generated.append((str(path), ""))
        else:
            print(f"  {tf_name}: FAILED")

    if not generated:
        print(f"[ERROR] No charts generated for {asset}")
        sys.exit(1)

    # Build caption from live data
    price_str, trs_str, bias_str = "", "", ""
    try:
        prices = json.loads((DATA_DIR / "live_prices.json").read_text(encoding="utf-8"))
        p = prices.get("prices", {}).get(asset, {}).get("price")
        if p:
            fmt = ",.2f" if p > 10 else ".4f"
            price_str = f" {p:{fmt}}"
    except Exception:
        pass
    try:
        sel = json.loads((DATA_DIR / "selected_assets.json").read_text(encoding="utf-8"))
        for s in sel.get("selected", []):
            if s.get("symbol") == asset:
                trs_str = f" | TRS {s.get('trs', '?')}/5"
                bias_str = f" | {s.get('direction_bias', '')}"
                break
    except Exception:
        pass

    caption = (
        f"📊 <b>{asset}</b>{price_str}{bias_str}{trs_str}\n"
        f"4H (trend) + 5min (entry timing)\n"
        f"🕐 {datetime.now().strftime('%H:%M')} EET"
    )
    generated[0] = (generated[0][0], caption)

    # Send
    from telegram_sender import send_media_group, send_photo
    try:
        if len(generated) >= 2:
            send_media_group(generated)
        else:
            send_photo(generated[0][0], caption)
        print(f"[OK] {asset} charts sent to Telegram")
        update_throttle(asset)
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
