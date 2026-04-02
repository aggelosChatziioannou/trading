# GOLD TACTIC — Trading Analyst Skill for Kimi

Αυτό το skill είναι για χρήση με **Kimi Code CLI** ή **Kimi Claw** για το GOLD TACTIC paper trading σύστημα.

## Τι είναι το GOLD TACTIC

Paper trading σύστημα που τρέχει adaptive cycles (TIER 1/2/3) για ανάλυση αγοράς και trading. Στέλνει αναλύσεις μέσω Telegram κάθε 20-30 λεπτά.

## Προαπαιτούμενα

1. Εγκατεστημένο το Kimi Code CLI (`pip install kimi-cli`)
2. Κλωνοποιημένο το repository: `git clone <repo-url>`
3. `.env` file με τα απαραίτητα API keys
4. Python 3.11+ με dependencies: `pip install -r requirements.txt`

## Ρύθμιση

```bash
# 1. Κλωνοποίησε το repo
git clone https://github.com/YOUR_USERNAME/gold-tactic.git
cd gold-tactic

# 2. Δημιούργησε .env από το παράδειγμα
copy .env.example .env
# Επεξεργάσου το .env και πρόσθεσε τα API keys σου

# 3. Εγκατάσταση Python dependencies
pip install -r requirements.txt

# 4. Εγκατάσταση Kimi skill (για local χρήση)
mkdir -p ~/.config/agents/skills/gold_tactic
cp kimi_skills/gold_tactic/SKILL.md ~/.config/agents/skills/gold_tactic/
```

## Χρήση

### Μέσω Kimi Code CLI (τοπικά)

```bash
# Με το skill φορτωμένο
/skill gold_tactic

# Ή απευθείας με το runner
python GOLD_TACTIC/scripts/analyst_runner.py --cli kimi
```

### Μέσω Kimi Claw (cloud)

Το Kimi Claw διαβάζει αυτόματα το `SKILL.md` αν το repo είναι συνδεδεμένο. Τρέξε:

```
/skill gold_tactic
Ξεκίνα το trading session
```

## Δομή Project

```
gold-tactic/
├── GOLD_TACTIC/
│   ├── prompts/
│   │   └── adaptive_analyst.md    # Main prompt
│   ├── scripts/
│   │   ├── analyst_runner.py      # Dual runtime (Claude/Kimi)
│   │   ├── quick_scan.py          # Market regime + correlations
│   │   ├── telegram_sender.py     # Telegram integration
│   │   └── risk_manager.py        # Portfolio management
│   └── data/                       # Runtime data (gitignored)
├── kimi_skills/
│   └── gold_tactic/SKILL.md       # This file
└── .env.example                    # Template for secrets
```

## Environment Variables

Δες `.env.example` για όλες τις απαραίτητες μεταβλητές:
- `TELEGRAM_BOT_TOKEN` — από @BotFather
- `TELEGRAM_CHANNEL` — ID του channel
- `FINNHUB_API_KEY` — από finnhub.io
- `KIMI_API_KEY` — από Moonshot (για Kimi CLI)
- `ALPACA_API_KEY` — για paper trading

## Διαφορές από Claude Code

| Χαρακτηριστικό | Claude Code | Kimi Code CLI |
|----------------|-------------|---------------|
| Tool: Read | `Read` | `ReadFile` |
| Tool: Write | `Write` | `WriteFile` |
| Tool: Bash | `Bash` | `Shell` |
| Tool: Grep | `Grep` | `Grep` |
| Billing | Max subscription | Per-token (API key) |

## Υποστήριξη

Για issues και feature requests: [GitHub Issues](https://github.com/YOUR_USERNAME/gold-tactic/issues)
