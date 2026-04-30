#!/usr/bin/env python3
"""
GOLD TACTIC — TRS History Logger (#8)
Appends current TRS for all selected assets to data/trs_history.jsonl.
Run AFTER each Market Monitor cycle computes TRS (STEP 4).

Usage:
  python trs_history.py XAUUSD=4 EURUSD=3 BTC=3 SOL=2   # Log TRS from CLI args (CANONICAL)
  python trs_history.py                                 # Fallback: read from selected_assets.json (will be 0 if trs field missing)
  python trs_history.py --summary                       # Print weekly stats
  python trs_history.py --summary --alert               # Send weekly stats to Telegram
"""
import sys, json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# EET timezone — fixes UTC-vs-EET timestamp drift (2026-04-29)
EET = timezone(timedelta(hours=3))

if sys.platform == 'win32':
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except: pass

DATA_DIR = Path(__file__).parent.parent / "data"
HISTORY_FILE = DATA_DIR / "trs_history.jsonl"
sys.path.insert(0, str(Path(__file__).parent))

def log_current(cli_trs=None):
    """Log TRS entry. cli_trs: dict like {"XAUUSD": 4, ...} from CLI args.
    If None, falls back to selected_assets.json (which usually lacks trs field)."""
    if cli_trs:
        assets = cli_trs
    else:
        sel_file = DATA_DIR / "selected_assets.json"
        if not sel_file.exists():
            print("[SKIP] No selected_assets.json and no CLI args"); return
        sel = json.loads(sel_file.read_text(encoding="utf-8"))
        assets = {s["symbol"]: s.get("trs", 0) for s in sel.get("selected", [])}
        if all(v == 0 for v in assets.values()):
            print("[WARN] All TRS=0 — selected_assets.json has no 'trs' field. Monitor should pass TRS as CLI args: python trs_history.py XAUUSD=4 EURUSD=3 ...")

    entry = {
        "ts": datetime.now(EET).strftime("%Y-%m-%d %H:%M"),
        "assets": assets,
    }
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[OK] Logged TRS: {entry['assets']}")


def parse_cli_trs(args):
    """Parse 'SYMBOL=N' pairs from args. Returns dict or None if none found."""
    out = {}
    for a in args:
        if "=" in a and not a.startswith("--"):
            sym, val = a.split("=", 1)
            try:
                out[sym.strip().upper()] = int(val.strip())
            except ValueError:
                continue
    return out or None

def weekly_summary(send_alert=False):
    if not HISTORY_FILE.exists():
        print("No history yet."); return
    cutoff = (datetime.now(EET) - timedelta(days=7)).strftime("%Y-%m-%d")
    asset_trs = {}
    with open(HISTORY_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
                if e["ts"][:10] < cutoff: continue
                for sym, trs in e["assets"].items():
                    if sym not in asset_trs: asset_trs[sym] = []
                    asset_trs[sym].append(trs)
            except: pass
    if not asset_trs:
        print("No data in last 7 days."); return

    lines = []
    for sym, scores in sorted(asset_trs.items()):
        avg = round(sum(scores)/len(scores), 1)
        high4 = sum(1 for s in scores if s >= 4)
        pct = round(high4/len(scores)*100)
        bar = "█" * int(pct/10) + "░" * (10-int(pct/10))
        line = f"  {sym:<8} avg {avg}/5  TRS≥4: {pct}%  {bar}"
        lines.append(line)
        print(line)

    if send_alert and lines:
        from telegram_sender import send_message
        send_message(f"📈 <b>TRS History — 7 ημέρες</b>\n\n<pre>" + "\n".join(lines) + "</pre>")
        print("[OK] Sent to Telegram")

def main():
    args = sys.argv[1:]
    if "--summary" in args:
        weekly_summary("--alert" in args)
    else:
        log_current(parse_cli_trs(args))

if __name__ == "__main__":
    main()
