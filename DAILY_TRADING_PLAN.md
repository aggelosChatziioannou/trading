# Daily Trading System - Implementation Plan

## Αλλαγή Στρατηγικής: Από Multi-Day σε Daily/Intraday Trading

### Γιατί αλλάζουμε
- Περνάμε σε **daily trading** (μέσα στη μέρα, κλείνουμε θέσεις πριν κλείσει η αγορά)
- Χρησιμοποιούμε **Claude subscription** (όχι API) μέσω scheduled Claude Code sessions
- Ο Claude κάνει news analysis, ο Python κάνει technical + execution

---

## ΦΑΣΗ 1: Backtest Infrastructure (ΤΩΡΑ)

### 1.1 Κατέβασε Historical Intraday Data
```
Πηγή: yfinance (δωρεάν, 15min bars, max ~2 μήνες πίσω)
       Alpaca (δωρεάν με account, 5min bars, πολλά χρόνια πίσω)
Tickers: AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, JPM, TSLA, SPY
Timeframes: 5min, 15min
Αποθήκευση: CSV στο data/backtest/
```

### 1.2 News Data για Backtest
```
Πηγή 1: FNSPID dataset (πρέπει να κατεβεί - 5.5GB news headlines)
Πηγή 2: Finnhub historical news (δωρεάν API, limited history)
Αποθήκευση: CSV στο data/backtest/news/
Χρήση: Για κάθε μέρα → "trade_safe" ή "no_trade"
```

### 1.3 Build Backtest Engine
```python
# scripts/backtest_daily.py

Για κάθε trading day:
  1. Φόρτωσε τα news εκείνης της μέρας
  2. News Filter: trade_safe = True/False (keyword-based για backtest)
  3. Αν trade_safe:
     a. Υπολόγισε Opening Range (πρώτα 15 λεπτά)
     b. Υπολόγισε VWAP
     c. Ψάξε για ORB breakout signals
     d. Ψάξε για VWAP reversion signals
     e. Ψάξε για Gap Fade signals
     f. Εκτέλεσε trades με risk management
  4. Κατέγραψε P&L, win rate, drawdown
```

### 1.4 Daily Trading Strategies για Backtest

**Strategy A: Opening Range Breakout (ORB)**
- Range: Πρώτα 15 λεπτά (9:30-9:45)
- Entry: Breakout πάνω από high ή κάτω από low
- Filters: VWAP alignment, RVOL > 1.5x
- Stop: Μέσα στο range (ATR-based)
- Target: 1x range height
- Exit: Πριν τις 15:30 σε κάθε περίπτωση

**Strategy B: VWAP Mean Reversion**
- Ήδη υπάρχει στο repo (strategies/vwap_reversion.py)
- Προσαρμογή για backtest engine

**Strategy C: Gap Fade**
- Ήδη υπάρχει στο repo (strategies/overnight_gap.py)
- News filter: ΔΕΝ κάνεις fade gap αν υπάρχουν material news

### 1.5 Metrics για Αξιολόγηση
```
- Total Return
- Win Rate
- Profit Factor
- Max Drawdown
- Sharpe Ratio (annualized)
- Average Trade Duration
- Trades per Day
- Σύγκριση: ΜΕ news filter vs ΧΩΡΙΣ news filter
```

---

## ΦΑΣΗ 2: Signal File System (Claude ↔ Python)

### 2.1 Claude Code Scheduled Task
```
Κάθε 30 λεπτά κατά τη διάρκεια market hours:
  1. Αναζήτηση news (web search)
  2. Ανάλυση impact (AI judgment)
  3. Γράφει αρχείο: signals/news_signal.json
```

### 2.2 Signal File Format
```json
{
  "timestamp": "2026-03-21T15:30:00Z",
  "trade_safe": true,
  "risk_level": "low",
  "market_sentiment": "neutral_bullish",
  "key_events": [],
  "avoid_tickers": [],
  "prefer_tickers": ["NVDA", "AAPL"],
  "reason": "Καθαρή μέρα, κανένα major event. Fed silent period.",
  "valid_until": "2026-03-21T16:05:00Z"
}
```

### 2.3 Python Bot (Daily Trader)
```python
# scripts/daily_trader.py

while market_is_open():
    # 1. Διάβασε Claude signal
    signal = read_signal("signals/news_signal.json")

    # 2. Validate freshness
    if signal.age > 35_minutes:
        log("Signal stale, waiting for refresh")
        continue

    # 3. Check if safe to trade
    if not signal.trade_safe:
        log(f"No trade: {signal.reason}")
        continue

    # 4. Scan for setups
    for ticker in watchlist:
        if ticker in signal.avoid_tickers:
            continue
        setup = scan_intraday_setup(ticker)  # ORB, VWAP, Gap
        if setup and setup.confidence >= threshold:
            execute_trade(setup)

    # 5. Manage open positions
    manage_positions()

    sleep(60)
```

---

## ΦΑΣΗ 3: Paper Trading (1-2 μήνες)

- Τρέχουμε σε Alpaca paper mode
- Claude scheduled κάθε 30 λεπτά
- Μαζεύουμε real-world data
- Αξιολογούμε: πόσες μέρες κάνει trade, win rate, drawdown

---

## ΦΑΣΗ 4: Live (αν τα νούμερα βγαίνουν)

- $10,000 initial capital
- Max 5% per trade
- Daily loss limit: -2%
- No leverage

---

## Prompt για Backtest Agent

Παρακάτω είναι το prompt που θα δοθεί στον agent:
