#!/usr/bin/env python3
"""
GOLD TACTIC — Risk Manager
Paper trading portfolio with position sizing, P&L tracking, and drawdown rules.

Portfolio file: portfolio.json
Trade history: trade_history.json

Usage:
  python risk_manager.py status                    # Show current portfolio
  python risk_manager.py open XAUUSD LONG 4435 4412 4470 4500  # Open trade
  python risk_manager.py check                     # Check open trades vs current prices
  python risk_manager.py close XAUUSD 4460         # Close trade at price
  python risk_manager.py history                   # Show trade history
  python risk_manager.py reset                     # Reset portfolio to initial capital
"""

import json
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
HISTORY_FILE = DATA_DIR / "trade_history.json"

# ============================================================
# CONFIG
# ============================================================

DEFAULT_PORTFOLIO = {
    "initial_capital": 1000.00,      # EUR
    "current_balance": 1000.00,      # Available balance (not in trades)
    "total_equity": 1000.00,         # Balance + unrealized P&L
    "risk_per_trade_pct": 1.5,       # 1.5% risk per trade
    "max_daily_loss_pct": 5.0,       # Max 5% loss per day
    "max_concurrent_trades": 3,      # Max 3 open positions
    "target_monthly_return": 100.0,  # Target: 100% = double in 1 month
    "currency": "EUR",
    "open_trades": [],
    "daily_pnl": 0.0,
    "daily_pnl_date": "",
    "total_pnl": 0.0,
    "total_trades": 0,
    "winning_trades": 0,
    "losing_trades": 0,
    "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
}

# Approximate pip values in EUR (for 1 standard lot)
# These are approximations — in reality depend on lot size and broker
ASSET_CONFIG = {
    # ---- Core 5 Assets ----
    "EURUSD": {
        "pip_value_per_lot": 10.0,
        "min_lot": 0.01,
        "pip_size": 0.0001,
        "contract_size": 100000,
        "margin_per_lot": 330,
    },
    "GBPUSD": {
        "pip_value_per_lot": 10.0,
        "min_lot": 0.01,
        "pip_size": 0.0001,
        "contract_size": 100000,
        "margin_per_lot": 400,
    },
    "NAS100": {
        "pip_value_per_lot": 1.0,
        "min_lot": 0.1,
        "pip_size": 1.0,
        "contract_size": 1,
        "margin_per_lot": 500,
    },
    "SOL": {
        "pip_value_per_lot": 1.0,
        "min_lot": 1.0,
        "pip_size": 0.01,
        "contract_size": 1,
        "margin_per_lot": 50,
    },
    "BTC": {
        "pip_value_per_lot": 1.0,
        "min_lot": 0.001,
        "pip_size": 1.0,
        "contract_size": 1,
        "margin_per_lot": 3000,
    },
    # ---- Scanner extras (stocks etc) ----
    "XAUUSD": {
        "pip_value_per_lot": 10.0,
        "min_lot": 0.01,
        "pip_size": 0.10,
        "contract_size": 100,
        "margin_per_lot": 2000,
    },
}


# ============================================================
# PORTFOLIO MANAGEMENT
# ============================================================

def load_portfolio():
    """Load portfolio from file or create default."""
    if PORTFOLIO_FILE.exists():
        data = json.loads(PORTFOLIO_FILE.read_text(encoding='utf-8'))
        # Reset daily P&L if new day
        today = datetime.now().strftime("%Y-%m-%d")
        if data.get("daily_pnl_date") != today:
            data["daily_pnl"] = 0.0
            data["daily_pnl_date"] = today
        return data
    return DEFAULT_PORTFOLIO.copy()


def save_portfolio(portfolio):
    """Save portfolio to file."""
    portfolio["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    PORTFOLIO_FILE.write_text(
        json.dumps(portfolio, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )


def load_history():
    """Load trade history."""
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding='utf-8'))
    return []


def save_history(history):
    """Save trade history."""
    HISTORY_FILE.write_text(
        json.dumps(history, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )


# ============================================================
# DRAWDOWN TRACKER (FIX #5)
# ============================================================

def check_drawdown(portfolio_path=None):
    """
    Ελέγχει το τρέχον drawdown level.

    Levels:
      SAFE    (< 3%)   → Κανένα restriction
      CAUTION (3-4%)   → Warning στο Telegram
      DANGER  (4-5%)   → Force minimum TIER 2
      BLOCKED (>= 5%)  → Αρνείται νέα trades + alert

    Args:
        portfolio_path: Optional Path to portfolio.json (default: DATA_DIR)

    Returns: dict {level, can_trade, drawdown_pct, daily_loss_pct, message}
    """
    # Φόρτωσε portfolio — δοκίμασε πρώτα το DATA_DIR (σωστό), μετά fallback
    portfolio = None
    paths_to_try = []

    if portfolio_path:
        paths_to_try.append(Path(portfolio_path))

    # Primary: GOLD_TACTIC/data/portfolio.json
    data_dir_portfolio = Path(__file__).parent.parent / "data" / "portfolio.json"
    paths_to_try.append(data_dir_portfolio)

    # Fallback: same directory as script (legacy)
    paths_to_try.append(PORTFOLIO_FILE)

    for p in paths_to_try:
        if p.exists():
            try:
                portfolio = json.loads(p.read_text(encoding='utf-8'))
                break
            except (json.JSONDecodeError, Exception):
                continue

    if portfolio is None:
        return {
            "level": "SAFE",
            "can_trade": True,
            "drawdown_pct": 0.0,
            "daily_loss_pct": 0.0,
            "message": "Portfolio not found — defaults (SAFE)"
        }

    initial = portfolio.get("initial_capital", 1000.0)
    equity = portfolio.get("total_equity", portfolio.get("current_balance", initial))
    daily_pnl = portfolio.get("daily_pnl", 0.0)

    # Reset daily P&L check
    today = datetime.now().strftime("%Y-%m-%d")
    if portfolio.get("daily_pnl_date") != today:
        daily_pnl = 0.0

    # Υπολογισμοί
    if initial <= 0:
        initial = 1000.0  # safety fallback

    drawdown_pct = max(0.0, ((initial - equity) / initial) * 100)
    daily_loss_pct = max(0.0, (abs(min(daily_pnl, 0)) / initial) * 100)

    # Πάρε τη χειρότερη μετρική
    worst_pct = max(drawdown_pct, daily_loss_pct)

    if worst_pct >= 5.0:
        return {
            "level": "BLOCKED",
            "can_trade": False,
            "drawdown_pct": round(drawdown_pct, 2),
            "daily_loss_pct": round(daily_loss_pct, 2),
            "message": f"🚫 BLOCKED — Drawdown {drawdown_pct:.1f}% / Daily loss {daily_loss_pct:.1f}% (limit: 5%)"
        }
    elif worst_pct >= 4.0:
        return {
            "level": "DANGER",
            "can_trade": True,
            "drawdown_pct": round(drawdown_pct, 2),
            "daily_loss_pct": round(daily_loss_pct, 2),
            "message": f"⚠️ DANGER — Drawdown {drawdown_pct:.1f}% / Daily loss {daily_loss_pct:.1f}% (κοντά στο 5%)"
        }
    elif worst_pct >= 3.0:
        return {
            "level": "CAUTION",
            "can_trade": True,
            "drawdown_pct": round(drawdown_pct, 2),
            "daily_loss_pct": round(daily_loss_pct, 2),
            "message": f"🟡 CAUTION — Drawdown {drawdown_pct:.1f}% / Daily loss {daily_loss_pct:.1f}%"
        }
    else:
        return {
            "level": "SAFE",
            "can_trade": True,
            "drawdown_pct": round(drawdown_pct, 2),
            "daily_loss_pct": round(daily_loss_pct, 2),
            "message": f"✅ SAFE — Drawdown {drawdown_pct:.1f}% / Daily loss {daily_loss_pct:.1f}%"
        }


# ============================================================
# POSITION SIZING
# ============================================================

def calculate_position_size(portfolio, asset, entry_price, sl_price):
    """
    Calculate position size based on risk management rules.
    Risk = 1.5% of current balance per trade.
    Returns: lot_size, risk_amount_eur, potential_loss, potential_gain_tp1, potential_gain_tp2
    """
    balance = portfolio["current_balance"]
    risk_pct = portfolio["risk_per_trade_pct"]
    config = ASSET_CONFIG.get(asset)

    if not config:
        return None, f"Unknown asset: {asset}"

    # Amount we're willing to risk (in EUR)
    risk_amount = balance * (risk_pct / 100)

    # Distance from entry to SL in price units
    sl_distance = abs(entry_price - sl_price)

    if sl_distance == 0:
        return None, "SL distance is 0"

    # Calculate lot size
    # risk_amount = lot_size * sl_distance * pip_value_per_lot / pip_size
    pip_value = config["pip_value_per_lot"]
    pip_size = config["pip_size"]

    # Convert sl_distance to pips
    sl_pips = sl_distance / pip_size

    # lot_size = risk_amount / (sl_pips * pip_value)
    lot_size = risk_amount / (sl_pips * pip_value)

    # Round to min lot
    min_lot = config["min_lot"]
    lot_size = max(min_lot, round(lot_size / min_lot) * min_lot)

    # Recalculate actual risk with rounded lot size
    actual_risk = lot_size * sl_pips * pip_value

    return {
        "lot_size": round(lot_size, 2),
        "risk_amount_eur": round(risk_amount, 2),
        "actual_risk_eur": round(actual_risk, 2),
        "sl_pips": round(sl_pips, 1),
        "risk_pct": risk_pct,
    }, None


# ============================================================
# TRADE OPERATIONS
# ============================================================

def open_trade(portfolio, asset, direction, entry, sl, tp1, tp2):
    """Open a new paper trade."""
    # Validate
    if len(portfolio["open_trades"]) >= portfolio["max_concurrent_trades"]:
        return None, f"Μέγιστο αριθμό ανοιχτών trades ({portfolio['max_concurrent_trades']})"

    # Check daily loss limit
    daily_loss_limit = portfolio["initial_capital"] * (portfolio["max_daily_loss_pct"] / 100)
    if portfolio["daily_pnl"] <= -daily_loss_limit:
        return None, f"Ημερήσιο όριο ζημίας ({portfolio['max_daily_loss_pct']}%) - STOP TRADING"

    # Check if already have trade on this asset
    for t in portfolio["open_trades"]:
        if t["asset"] == asset:
            return None, f"Ήδη ανοιχτό trade στο {asset}"

    # Calculate position size
    sizing, error = calculate_position_size(portfolio, asset, entry, sl)
    if error:
        return None, error

    trade = {
        "id": f"{asset}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "asset": asset,
        "direction": direction.upper(),  # LONG or SHORT
        "entry_price": entry,
        "sl_price": sl,
        "tp1_price": tp1,
        "tp2_price": tp2,
        "lot_size": sizing["lot_size"],
        "risk_amount": sizing["actual_risk_eur"],
        "opened_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "OPEN",
        "tp1_hit": False,
        "partial_close_pct": 0,
    }

    # Reserve risk amount from balance
    portfolio["current_balance"] -= sizing["actual_risk_eur"]
    portfolio["open_trades"].append(trade)
    portfolio["total_trades"] += 1
    save_portfolio(portfolio)

    return trade, None


def check_trades(portfolio, current_prices):
    """
    Check open trades against current prices.
    current_prices = {"XAUUSD": 4440, "NAS100": 24100, ...}
    Returns list of events (tp1_hit, tp2_hit, sl_hit).
    """
    events = []

    for trade in portfolio["open_trades"]:
        asset = trade["asset"]
        if asset not in current_prices:
            continue

        price = current_prices[asset]
        direction = trade["direction"]

        # Calculate unrealized P&L
        if direction == "LONG":
            pnl_pips = (price - trade["entry_price"]) / ASSET_CONFIG[asset]["pip_size"]
        else:
            pnl_pips = (trade["entry_price"] - price) / ASSET_CONFIG[asset]["pip_size"]

        pnl_eur = pnl_pips * ASSET_CONFIG[asset]["pip_value_per_lot"] * trade["lot_size"]
        trade["unrealized_pnl"] = round(pnl_eur, 2)
        trade["current_price"] = price

        # Check SL
        if direction == "LONG" and price <= trade["sl_price"]:
            events.append({"type": "SL_HIT", "trade": trade, "price": price})
        elif direction == "SHORT" and price >= trade["sl_price"]:
            events.append({"type": "SL_HIT", "trade": trade, "price": price})

        # Check TP1 (close 50%)
        if not trade["tp1_hit"]:
            if direction == "LONG" and price >= trade["tp1_price"]:
                events.append({"type": "TP1_HIT", "trade": trade, "price": price})
            elif direction == "SHORT" and price <= trade["tp1_price"]:
                events.append({"type": "TP1_HIT", "trade": trade, "price": price})

        # Check TP2 (close remaining)
        if trade["tp1_hit"]:
            if direction == "LONG" and price >= trade["tp2_price"]:
                events.append({"type": "TP2_HIT", "trade": trade, "price": price})
            elif direction == "SHORT" and price <= trade["tp2_price"]:
                events.append({"type": "TP2_HIT", "trade": trade, "price": price})

    save_portfolio(portfolio)
    return events


def close_trade(portfolio, asset, close_price, reason="MANUAL"):
    """Close a trade at given price."""
    history = load_history()

    trade = None
    for t in portfolio["open_trades"]:
        if t["asset"] == asset:
            trade = t
            break

    if not trade:
        return None, f"Δεν υπάρχει ανοιχτό trade στο {asset}"

    direction = trade["direction"]
    config = ASSET_CONFIG[asset]

    # Calculate P&L
    if direction == "LONG":
        pnl_pips = (close_price - trade["entry_price"]) / config["pip_size"]
    else:
        pnl_pips = (trade["entry_price"] - close_price) / config["pip_size"]

    pnl_eur = pnl_pips * config["pip_value_per_lot"] * trade["lot_size"]

    # Update portfolio
    portfolio["current_balance"] += trade["risk_amount"] + pnl_eur  # Return reserved + P&L
    portfolio["daily_pnl"] += pnl_eur
    portfolio["total_pnl"] += pnl_eur
    portfolio["total_equity"] = portfolio["current_balance"]

    if pnl_eur > 0:
        portfolio["winning_trades"] += 1
        portfolio["consecutive_wins"] = portfolio.get("consecutive_wins", 0) + 1
        portfolio["consecutive_losses"] = 0
    else:
        portfolio["losing_trades"] += 1
        portfolio["consecutive_losses"] = portfolio.get("consecutive_losses", 0) + 1
        portfolio["consecutive_wins"] = 0

    # Remove from open trades
    portfolio["open_trades"] = [t for t in portfolio["open_trades"] if t["asset"] != asset]

    # Recalculate equity
    portfolio["total_equity"] = portfolio["current_balance"]
    for t in portfolio["open_trades"]:
        portfolio["total_equity"] += t.get("unrealized_pnl", 0)

    # Save to history
    trade["close_price"] = close_price
    trade["close_reason"] = reason
    trade["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    trade["pnl_pips"] = round(pnl_pips, 1)
    trade["pnl_eur"] = round(pnl_eur, 2)
    trade["status"] = "CLOSED"
    history.append(trade)

    save_portfolio(portfolio)
    save_history(history)

    return trade, None


def process_tp1(portfolio, asset, price):
    """Process TP1 hit — close 50% of position."""
    for trade in portfolio["open_trades"]:
        if trade["asset"] == asset:
            trade["tp1_hit"] = True
            trade["partial_close_pct"] = 50

            # Calculate partial P&L
            config = ASSET_CONFIG[asset]
            direction = trade["direction"]
            if direction == "LONG":
                pnl_pips = (price - trade["entry_price"]) / config["pip_size"]
            else:
                pnl_pips = (trade["entry_price"] - price) / config["pip_size"]

            partial_pnl = pnl_pips * config["pip_value_per_lot"] * trade["lot_size"] * 0.5
            portfolio["current_balance"] += partial_pnl + (trade["risk_amount"] * 0.5)
            trade["lot_size"] = round(trade["lot_size"] / 2, 2)
            trade["risk_amount"] = round(trade["risk_amount"] / 2, 2)

            # Move SL to breakeven after TP1
            trade["sl_price"] = trade["entry_price"]

            portfolio["daily_pnl"] += partial_pnl
            portfolio["total_pnl"] += partial_pnl

            save_portfolio(portfolio)
            return trade, partial_pnl

    return None, 0


def update_sl(portfolio, asset, new_sl):
    """Update stop loss for an open trade."""
    for trade in portfolio["open_trades"]:
        if trade["asset"] == asset:
            old_sl = trade["sl_price"]
            trade["sl_price"] = new_sl
            save_portfolio(portfolio)
            return trade, f"SL updated {old_sl} -> {new_sl}"
    return None, f"No open trade for {asset}"


def process_tp2(portfolio, asset, price):
    """Process TP2 hit — close remaining position."""
    for trade in portfolio["open_trades"]:
        if trade["asset"] == asset:
            trade["tp2_hit"] = True
            trade["partial_close_pct"] = 100

            config = ASSET_CONFIG[asset]
            direction = trade["direction"]
            if direction == "LONG":
                pnl_pips = (price - trade["entry_price"]) / config["pip_size"]
            else:
                pnl_pips = (trade["entry_price"] - price) / config["pip_size"]

            remaining_pnl = pnl_pips * config["pip_value_per_lot"] * trade["lot_size"]
            portfolio["current_balance"] += remaining_pnl + trade["risk_amount"]
            portfolio["daily_pnl"] += remaining_pnl
            portfolio["total_pnl"] += remaining_pnl

            portfolio["open_trades"] = [t for t in portfolio["open_trades"] if t["asset"] != asset]
            save_portfolio(portfolio)
            return trade, remaining_pnl
    return None, 0


# ============================================================
# DISPLAY FUNCTIONS
# ============================================================

def format_status(portfolio):
    """Format portfolio status for display."""
    lines = []
    lines.append("=" * 50)
    lines.append("📊 GOLD TACTIC — Portfolio Status")
    lines.append("=" * 50)
    lines.append(f"💰 Αρχικό κεφάλαιο: {portfolio['initial_capital']:.2f} EUR")
    lines.append(f"💵 Διαθέσιμο: {portfolio['current_balance']:.2f} EUR")
    lines.append(f"📈 Συνολικό equity: {portfolio['total_equity']:.2f} EUR")
    lines.append(f"📊 Συνολικό P&L: {portfolio['total_pnl']:+.2f} EUR "
                 f"({portfolio['total_pnl']/portfolio['initial_capital']*100:+.1f}%)")
    lines.append(f"📅 Ημερήσιο P&L: {portfolio['daily_pnl']:+.2f} EUR")
    lines.append(f"🎯 Στόχος μήνα: {portfolio['initial_capital'] * 2:.2f} EUR (x2)")
    lines.append(f"📊 Trades: {portfolio['total_trades']} "
                 f"(W: {portfolio['winning_trades']} / L: {portfolio['losing_trades']})")

    if portfolio["total_trades"] > 0:
        wr = portfolio["winning_trades"] / portfolio["total_trades"] * 100
        lines.append(f"✅ Win Rate: {wr:.1f}%")

    lines.append(f"⚙️ Risk/trade: {portfolio['risk_per_trade_pct']}% "
                 f"= {portfolio['current_balance'] * portfolio['risk_per_trade_pct'] / 100:.2f} EUR")
    lines.append(f"🕐 Τελευταία ενημέρωση: {portfolio['last_updated']}")

    if portfolio["open_trades"]:
        lines.append("")
        lines.append("📂 ΑΝΟΙΧΤΑ TRADES:")
        lines.append("-" * 40)
        for t in portfolio["open_trades"]:
            emoji = "🟢" if t["direction"] == "LONG" else "🔴"
            pnl = t.get("unrealized_pnl", 0)
            pnl_str = f"{pnl:+.2f} EUR" if pnl else "N/A"
            lines.append(f"  {emoji} {t['asset']} {t['direction']} @ {t['entry_price']}")
            lines.append(f"     Lot: {t['lot_size']} | SL: {t['sl_price']} | "
                         f"TP1: {t['tp1_price']} | TP2: {t['tp2_price']}")
            lines.append(f"     Risk: {t['risk_amount']:.2f} EUR | P&L: {pnl_str}")
            if t["tp1_hit"]:
                lines.append(f"     ✅ TP1 hit — SL moved to breakeven")
    else:
        lines.append("\n📭 Κανένα ανοιχτό trade")

    lines.append("=" * 50)
    return "\n".join(lines)


def format_telegram_trade_open(trade, portfolio):
    """Format Telegram message for new trade."""
    emoji = "🟢" if trade["direction"] == "LONG" else "🔴"
    direction_gr = "ΑΓΟΡΑ" if trade["direction"] == "LONG" else "ΠΩΛΗΣΗ"

    return f"""{emoji} <b>{trade['asset']} — {direction_gr}</b>
━━━━━━━━━━━━━━━━━━━━━━
💰 Entry: {trade['entry_price']}
🛑 SL: {trade['sl_price']}
✅ TP1: {trade['tp1_price']} (κλείσε 50%)
✅ TP2: {trade['tp2_price']} (κλείσε υπόλοιπο)
📏 Lot: {trade['lot_size']}

💼 <b>Risk Management:</b>
├ Ρίσκο: {trade['risk_amount']:.2f} EUR ({portfolio['risk_per_trade_pct']}% του balance)
├ Balance πριν: {portfolio['current_balance'] + trade['risk_amount']:.2f} EUR
├ Δεσμευμένο: {trade['risk_amount']:.2f} EUR
└ Διαθέσιμο τώρα: {portfolio['current_balance']:.2f} EUR

📊 Portfolio: {portfolio['total_equity']:.2f} / {portfolio['initial_capital'] * 2:.2f} EUR (στόχος x2)
🤖 GOLD TACTIC v2.0"""


def format_telegram_trade_close(trade, portfolio):
    """Format Telegram message for closed trade."""
    pnl = trade["pnl_eur"]
    emoji = "✅" if pnl > 0 else "❌"
    result = "ΚΕΡΔΟΣ" if pnl > 0 else "ΖΗΜΙΑ"

    return f"""{emoji} <b>{trade['asset']} — {result}: {pnl:+.2f} EUR</b>
━━━━━━━━━━━━━━━━━━━━━━
├ Entry: {trade['entry_price']} → Close: {trade['close_price']}
├ P&L: {trade['pnl_pips']:+.1f} pips = {pnl:+.2f} EUR
├ Λόγος κλεισίματος: {trade['close_reason']}
└ Διάρκεια: {trade['opened_at']} → {trade['closed_at']}

💼 <b>Portfolio Update:</b>
├ Balance: {portfolio['current_balance']:.2f} EUR
├ Ημερήσιο P&L: {portfolio['daily_pnl']:+.2f} EUR
├ Συνολικό P&L: {portfolio['total_pnl']:+.2f} EUR ({portfolio['total_pnl']/portfolio['initial_capital']*100:+.1f}%)
└ W/L: {portfolio['winning_trades']}/{portfolio['losing_trades']}

📊 Equity: {portfolio['total_equity']:.2f} / {portfolio['initial_capital'] * 2:.2f} EUR (στόχος x2)
🤖 GOLD TACTIC v2.0"""


# ============================================================
# CLI
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: risk_manager.py [status|open|check|close|history|reset]")
        return

    cmd = sys.argv[1].lower()
    portfolio = load_portfolio()

    if cmd == "status":
        print(format_status(portfolio))

    elif cmd == "open":
        if len(sys.argv) < 8:
            print("Usage: risk_manager.py open ASSET DIRECTION ENTRY SL TP1 TP2")
            print("Example: risk_manager.py open XAUUSD LONG 4435 4412 4470 4500")
            return
        asset = sys.argv[2].upper()
        direction = sys.argv[3].upper()
        entry = float(sys.argv[4])
        sl = float(sys.argv[5])
        tp1 = float(sys.argv[6])
        tp2 = float(sys.argv[7])

        trade, error = open_trade(portfolio, asset, direction, entry, sl, tp1, tp2)
        if error:
            print(f"❌ Error: {error}")
        else:
            print(f"✅ Trade opened!")
            print(format_telegram_trade_open(trade, portfolio))

    elif cmd == "close":
        if len(sys.argv) < 4:
            print("Usage: risk_manager.py close ASSET PRICE [REASON]")
            return
        asset = sys.argv[2].upper()
        price = float(sys.argv[3])
        reason = sys.argv[4] if len(sys.argv) > 4 else "MANUAL"

        trade, error = close_trade(portfolio, asset, price, reason)
        if error:
            print(f"❌ Error: {error}")
        else:
            print(format_telegram_trade_close(trade, portfolio))

    elif cmd == "update_sl":
        if len(sys.argv) < 4:
            print("Usage: risk_manager.py update_sl ASSET NEW_SL")
            return
        asset = sys.argv[2].upper()
        new_sl = float(sys.argv[3])
        trade, error = update_sl(portfolio, asset, new_sl)
        if error and "No open trade" in error:
            print(f"❌ {error}")
        else:
            print(f"✅ {trade['asset']} SL moved to {trade['sl_price']}")

    elif cmd == "process_tp":
        if len(sys.argv) < 5:
            print("Usage: risk_manager.py process_tp ASSET tp1|tp2 PRICE")
            return
        asset = sys.argv[2].upper()
        tp_level = sys.argv[3].lower()
        price = float(sys.argv[4])
        if tp_level == "tp1":
            trade, partial = process_tp1(portfolio, asset, price)
            if trade:
                print(f"✅ {asset} TP1 hit @ {price} — closed 50%, partial P&L: {partial:+.2f} EUR")
                print(f"   SL moved to breakeven ({trade['sl_price']})")
            else:
                print(f"❌ No open trade for {asset}")
        elif tp_level == "tp2":
            trade, remaining = process_tp2(portfolio, asset, price)
            if trade:
                print(f"✅ {asset} TP2 hit @ {price} — closed remaining, P&L: {remaining:+.2f} EUR")
            else:
                print(f"❌ No open trade for {asset}")
        else:
            print("❌ tp_level must be tp1 or tp2")

    elif cmd == "drawdown":
        result = check_drawdown()
        if "--json" in sys.argv:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"\n💰 Drawdown Status")
            print(f"   Level: {result['level']}")
            print(f"   Drawdown: {result['drawdown_pct']:.1f}%")
            print(f"   Daily Loss: {result['daily_loss_pct']:.1f}%")
            print(f"   Can Trade: {'✅' if result['can_trade'] else '🚫'}")
            print(f"   {result['message']}")

    elif cmd == "check":
        # Just show status of open trades
        print(format_status(portfolio))

    elif cmd == "history":
        history = load_history()
        if not history:
            print("📭 Κανένα κλεισμένο trade ακόμα")
            return
        print(f"\n📜 Trade History ({len(history)} trades):")
        print("-" * 60)
        for t in history:
            pnl = t.get("pnl_eur", 0)
            emoji = "✅" if pnl > 0 else "❌"
            print(f"  {emoji} {t['asset']} {t['direction']} | "
                  f"Entry: {t['entry_price']} → {t['close_price']} | "
                  f"P&L: {pnl:.2f} EUR | Reason: {t.get('reason','?')}")

    else:
        print(f"❌ Unknown command: {cmd}")
        print("Usage: risk_manager.py [status|open|check|close|update_sl|process_tp|history|reset]")

if __name__ == "__main__":
    main()