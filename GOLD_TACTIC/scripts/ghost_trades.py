#!/usr/bin/env python3
"""
GOLD TACTIC — Ghost Trades (#4)
Auto-opens/closes simulated trades when TRS=5. Tracks P&L without manual input.
Compares "system" performance vs actual trades in portfolio.json.

Usage:
  python ghost_trades.py --check   # Check open ghosts vs current prices, close if TP/SL hit
  python ghost_trades.py --report  # Print ghost trade P&L summary
  python ghost_trades.py --report --alert  # Send to Telegram
"""
import sys, json
from datetime import datetime
from pathlib import Path

if sys.platform == 'win32':
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except: pass

DATA_DIR  = Path(__file__).parent.parent / "data"
GHOST_FILE = DATA_DIR / "ghost_trades.json"
sys.path.insert(0, str(Path(__file__).parent))

def load_ghosts():
    if not GHOST_FILE.exists():
        return {"open": [], "closed": []}
    try:
        return json.loads(GHOST_FILE.read_text(encoding="utf-8"))
    except:
        return {"open": [], "closed": []}

def save_ghosts(data):
    GHOST_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def open_ghost(symbol, direction, entry, sl, tp, trs, strategy):
    """Open a new ghost trade when TRS=5."""
    data = load_ghosts()
    # Don't open if already have open ghost for this symbol
    if any(g["symbol"] == symbol for g in data["open"]):
        print(f"[SKIP] Ghost already open for {symbol}")
        return
    ghost = {
        "id": f"G{len(data['closed'])+len(data['open'])+1:03d}",
        "symbol": symbol, "direction": direction,
        "entry": entry, "sl": sl, "tp": tp,
        "trs_at_open": trs, "strategy": strategy,
        "opened_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status": "OPEN"
    }
    data["open"].append(ghost)
    save_ghosts(data)
    print(f"[GHOST OPEN] {ghost['id']} {symbol} {direction} @ {entry}  TP:{tp}  SL:{sl}")

def check_and_close():
    """Check open ghost trades against current prices."""
    data = load_ghosts()
    if not data["open"]:
        print("[INFO] No open ghost trades."); return

    prices_file = DATA_DIR / "live_prices.json"
    if not prices_file.exists():
        print("[SKIP] No price data"); return
    prices = json.loads(prices_file.read_text(encoding="utf-8")).get("prices", {})

    closed_now = []
    for g in data["open"][:]:
        sym = g["symbol"]
        price_data = prices.get(sym, {})
        current = price_data.get("price")
        if current is None: continue

        hit_tp = (g["direction"] == "BUY"  and current >= g["tp"]) or \
                 (g["direction"] == "SELL" and current <= g["tp"])
        hit_sl = (g["direction"] == "BUY"  and current <= g["sl"]) or \
                 (g["direction"] == "SELL" and current >= g["sl"])

        if hit_tp or hit_sl:
            exit_price = g["tp"] if hit_tp else g["sl"]
            raw_pnl = exit_price - g["entry"] if g["direction"] == "BUY" else g["entry"] - exit_price
            g.update({
                "exit": exit_price, "result": "WIN" if hit_tp else "LOSS",
                "pnl_pts": round(raw_pnl, 5),
                "closed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "status": "CLOSED"
            })
            data["open"].remove(g)
            data["closed"].append(g)
            closed_now.append(g)
            print(f"[GHOST CLOSE] {g['id']} {sym} → {g['result']}  pnl:{g['pnl_pts']}")

    if closed_now:
        save_ghosts(data)

def report(send_alert=False):
    data = load_ghosts()
    closed = data["closed"]
    if not closed:
        print("No ghost trades yet."); return

    wins   = [g for g in closed if g.get("result") == "WIN"]
    losses = [g for g in closed if g.get("result") == "LOSS"]
    wr     = round(len(wins)/len(closed)*100) if closed else 0
    open_c = len(data["open"])

    lines = [
        f"Ghost Trades: {len(closed)} closed | {open_c} open",
        f"Win Rate: {wr}%  ({len(wins)}W / {len(losses)}L)",
    ]
    for g in closed[-5:]:  # Last 5
        lines.append(f"  {g['id']} {g['symbol']} {g['direction']} → {g.get('result','?')} ({g.get('pnl_pts','?')})")

    for l in lines: print(l)
    if send_alert:
        from telegram_sender import send_message
        send_message(f"👻 <b>Ghost Trades</b>\n\n" + "\n".join(lines))
        print("[OK] Sent")

def main():
    args = sys.argv[1:]
    if "--check" in args:
        check_and_close()
    elif "--report" in args:
        report("--alert" in args)
    else:
        print("Usage: ghost_trades.py [--check | --report [--alert]]")

if __name__ == "__main__":
    main()
