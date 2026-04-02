# GOLD TACTIC — Adaptive Trading System

🤖 **Dual-Runtime AI Trading Agent** — Τρέχει με **Claude Code** ή **Kimi Code CLI**

```
📈 Paper trading system with adaptive cycles (TIER 1/2/3)
🔄 Auto-detects Claude or Kimi CLI
🌊 Market regime detection (Trending/Ranging/Choppy)
🔗 Dynamic correlation matrix
📱 Telegram integration
```

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Adaptive Cycles** | TIER 1 (heartbeat), TIER 2 (quick check), TIER 3 (full analysis) based on market activity |
| **Market Regime** | ADX-based detection: Trending (>25), Ranging (20-25), Choppy (<20) |
| **Dynamic Correlations** | 20-day rolling correlation for EURUSD↔GBPUSD, BTC↔SOL, NAS100↔BTC |
| **ADR Override** | Entry even with ADR >90% on trend days with reduced risk |
| **Dual Runtime** | Auto-detects and runs on **Claude Code** or **Kimi Code CLI** |
| **Telegram Alerts** | Live P&L, trade entries/exits, heartbeat messages |
| **Risk Management** | Dynamic position sizing, streak adjustment, correlation limits |

---

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/YOUR_USERNAME/gold-tactic.git
cd gold-tactic

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your API keys
```

### 2. Configure API Keys

Edit `.env`:
```ini
# Telegram (required)
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_CHANNEL=your_channel_id

# Finnhub (required for news)
FINNHUB_API_KEY=your_finnhub_key

# Alpaca (for paper trading)
ALPACA_API_KEY=your_alpaca_key
ALPACA_SECRET_KEY=your_alpaca_secret

# Kimi (only if using Kimi CLI)
KIMI_API_KEY=your_moonshot_key
```

### 3. Choose Your Runtime

#### Option A: Claude Code (Recommended for Max subscribers)
```bash
# Make sure claude is on PATH
python GOLD_TACTIC/scripts/analyst_runner.py --cli claude
```

#### Option B: Kimi Code CLI
```bash
# Make sure kimi is installed and KIMI_API_KEY is set
python GOLD_TACTIC/scripts/analyst_runner.py --cli kimi
```

#### Option C: Auto-detect (uses first available)
```bash
python GOLD_TACTIC/scripts/analyst_runner.py
```

### 4. Schedule (Windows Task Scheduler)

Create a task that runs every 5 minutes (08:00–22:00):
```
Action: python C:\path\to\gold-tactic\GOLD_TACTIC\scripts\analyst_runner.py
Trigger: Every 5 minutes, 08:00-22:00 daily
```

---

## 📁 Project Structure

```
gold-tactic/
├── GOLD_TACTIC/
│   ├── prompts/
│   │   ├── adaptive_analyst.md      # Main trading analyst prompt
│   │   ├── scanner_morning_v6.md    # Morning scanner
│   │   └── scanner_afternoon_v6.md  # Afternoon scanner
│   ├── scripts/
│   │   ├── analyst_runner.py        # Dual-runtime entry point ⭐
│   │   ├── quick_scan.py            # Market regime + correlations
│   │   ├── price_checker.py         # Live price fetching
│   │   ├── risk_manager.py          # Portfolio & position sizing
│   │   └── telegram_sender.py       # Telegram integration
│   └── data/                         # Runtime data (gitignored)
├── kimi_skills/
│   └── gold_tactic/SKILL.md         # Kimi Claw skill
├── .env.example                      # Environment template
└── README.md                         # This file
```

---

## 🧠 How It Works

### Adaptive Cycle System

```
TIER 1 (Heartbeat)      ~500 tokens   → Every 30 min when quiet
    ↓ Price moves > threshold
TIER 2 (Quick Check)    ~3,000 tokens → Every 10-15 min
    ↓ TRS ≥ 4 or news
TIER 3 (Full Analysis)  ~15,000 tokens → Scanner + trade execution
```

### Market Regime Rules

| Regime | ADX | Action |
|--------|-----|--------|
| **Trending** | >25 | Relax SL, allow ADR>90% entry with 50% reduced risk |
| **Ranging** | 20-25 | Strict TRS ≥5, smaller targets |
| **Choppy** | <20 | No-trade mode, management only |

### Correlation Rules

| Pair | Correlation | Rule |
|------|-------------|------|
| EURUSD↔GBPUSD | >0.80 | Max 1 trade |
| EURUSD↔GBPUSD | <0.20 | **Exception**: Can take both (diversification) |
| BTC↔SOL | >0.80 | Max 1 trade |

---

## 🛠️ Development

### Testing

```bash
cd GOLD_TACTIC/scripts
python -m pytest test_analyst_runner.py -v
```

### Manual Cycle Trigger

```bash
# Force immediate cycle
python GOLD_TACTIC/scripts/analyst_runner.py --cli claude
```

### Kimi Skill (for Kimi Claw)

Install locally:
```bash
mkdir -p ~/.config/agents/skills/gold_tactic
cp kimi_skills/gold_tactic/SKILL.md ~/.config/agents/skills/gold_tactic/
```

Then in Kimi:
```
/skill gold_tactic
Ξεκίνα το trading session
```

---

## 💰 Costs & Billing

| Runtime | Billing Model | Est. Cost (40 cycles/day) |
|---------|---------------|---------------------------|
| **Claude Code** | Max subscription (flat) | Included |
| **Kimi Code CLI** | Per-token ($0.60/M input, $2.50/M output) | ~$2-8/day |
| **Kimi Claw** | $39/mo + usage | $39/mo base |

---

## ⚠️ Disclaimer

This is a **paper trading** system for educational purposes. 
- No real money is traded by default
- All trading is simulated unless explicitly configured
- Past performance does not guarantee future results

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📜 License

MIT License — see LICENSE file for details.

---

## 🔗 Links

- [Claude Code](https://claude.ai/code)
- [Kimi Code CLI](https://github.com/MoonshotAI/kimi-cli)
- [Kimi Claw](https://www.kimi.com)
- [Finnhub](https://finnhub.io)
