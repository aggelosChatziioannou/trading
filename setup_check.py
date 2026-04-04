#!/usr/bin/env python3
"""
GOLD TACTIC — Setup Checker
Ελέγχει αν το σύστημα είναι έτοιμο να τρέξει σε αυτό το PC.
Τρέξε: python setup_check.py

Checks:
  1. Python version
  2. Required packages installed
  3. .env file exists with required keys
  4. Data directory structure
  5. Required data files exist
  6. Claude/Kimi CLI availability
  7. Telegram connectivity
"""

import sys
import os
import json
import shutil
from pathlib import Path

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "GOLD_TACTIC" / "data"
SCRIPTS_DIR = PROJECT_ROOT / "GOLD_TACTIC" / "scripts"
PROMPTS_DIR = PROJECT_ROOT / "GOLD_TACTIC" / "prompts"

passed = 0
failed = 0
warnings = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  {GREEN}✅ {msg}{RESET}")

def fail(msg, fix=""):
    global failed
    failed += 1
    print(f"  {RED}❌ {msg}{RESET}")
    if fix:
        print(f"     {YELLOW}→ Fix: {fix}{RESET}")

def warn(msg, fix=""):
    global warnings
    warnings += 1
    print(f"  {YELLOW}⚠️  {msg}{RESET}")
    if fix:
        print(f"     → {fix}")


print(f"\n{BOLD}🔍 GOLD TACTIC — Setup Check{RESET}\n")

# ── 1. Python Version ─────────────────────────────────────────────────────────
print(f"{BOLD}[1] Python{RESET}")
v = sys.version_info
if v.major >= 3 and v.minor >= 10:
    ok(f"Python {v.major}.{v.minor}.{v.micro}")
else:
    fail(f"Python {v.major}.{v.minor} — need 3.10+", "Install Python 3.10+")

# ── 2. Required Packages ─────────────────────────────────────────────────────
print(f"\n{BOLD}[2] Python Packages{RESET}")
required_packages = {
    "yfinance": "Market data",
    "pandas": "Data analysis",
    "numpy": "Numerical computing",
    "requests": "HTTP requests",
    "dotenv": "Environment variables (python-dotenv)",
    "mplfinance": "Chart generation",
}

missing = []
for pkg, desc in required_packages.items():
    try:
        if pkg == "dotenv":
            __import__("dotenv")
        else:
            __import__(pkg)
        ok(f"{pkg} — {desc}")
    except ImportError:
        fail(f"{pkg} — {desc}", f"pip install {pkg if pkg != 'dotenv' else 'python-dotenv'}")
        missing.append(pkg)

if missing:
    print(f"\n  {YELLOW}Quick fix: pip install -r requirements.txt{RESET}")

# ── 3. .env File ─────────────────────────────────────────────────────────────
print(f"\n{BOLD}[3] Environment (.env){RESET}")
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    ok(".env file exists")
    env_content = env_file.read_text(encoding="utf-8")

    required_keys = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL", "FINNHUB_API_KEY"]
    optional_keys = ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "CRYPTOPANIC_API_KEY", "KIMI_API_KEY"]

    for key in required_keys:
        if key in env_content and "your_" not in env_content.split(key)[1][:30]:
            ok(f"{key} configured")
        else:
            fail(f"{key} missing or placeholder", f"Add {key}=... to .env")

    for key in optional_keys:
        if key in env_content and "your_" not in env_content.split(key)[1][:30] if key in env_content else False:
            ok(f"{key} configured (optional)")
        else:
            warn(f"{key} not set (optional)")
else:
    fail(".env file missing", "cp .env.example .env && edit with your API keys")

# ── 4. Directory Structure ───────────────────────────────────────────────────
print(f"\n{BOLD}[4] Directory Structure{RESET}")
for d in [DATA_DIR, SCRIPTS_DIR, PROMPTS_DIR]:
    if d.exists():
        ok(f"{d.relative_to(PROJECT_ROOT)}/")
    else:
        fail(f"{d.relative_to(PROJECT_ROOT)}/ missing")

screenshots_dir = PROJECT_ROOT / "GOLD_TACTIC" / "screenshots"
if not screenshots_dir.exists():
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    ok(f"Created screenshots/ directory")
else:
    ok(f"screenshots/ exists")

# ── 5. Required Data Files ───────────────────────────────────────────────────
print(f"\n{BOLD}[5] Data Files{RESET}")
required_data = {
    "portfolio.json": "Portfolio state",
    "scanner_watchlist.json": "Scanner decisions",
    "narrative_memory.json": "Cross-session memory",
    "emergency_activations.json": "Emergency assets",
    "shadow_trades.json": "Pilot shadow trades",
}

for filename, desc in required_data.items():
    filepath = DATA_DIR / filename
    if filepath.exists():
        try:
            json.loads(filepath.read_text(encoding="utf-8"))
            ok(f"{filename} — {desc}")
        except json.JSONDecodeError:
            fail(f"{filename} — corrupt JSON", f"Delete and recreate")
    else:
        warn(f"{filename} missing — {desc}", "Will be created on first run")

optional_data = ["trade_journal.md", "pilot_notes.md", "trade_history.json", "news_digest.json"]
for filename in optional_data:
    filepath = DATA_DIR / filename
    if filepath.exists():
        ok(f"{filename} (optional)")
    else:
        warn(f"{filename} missing (optional — created on first run)")

# ── 6. Required Scripts ──────────────────────────────────────────────────────
print(f"\n{BOLD}[6] Scripts{RESET}")
required_scripts = [
    "analyst_runner.py", "quick_scan.py", "price_checker.py",
    "telegram_sender.py", "risk_manager.py", "trs_calculator.py",
    "telegram_state.py", "news_scout_v2.py", "economic_calendar.py",
    "sentiment.py", "chart_generator.py",
]
for script in required_scripts:
    filepath = SCRIPTS_DIR / script
    if filepath.exists():
        ok(script)
    else:
        fail(f"{script} missing!")

# ── 7. Required Prompts ─────────────────────────────────────────────────────
print(f"\n{BOLD}[7] Prompts{RESET}")
required_prompts = [
    "adaptive_analyst.md", "ref_strategies.md", "ref_ladder.md",
    "ref_emergency.md", "scanner_morning_v6.md", "scanner_afternoon_v6.md",
]
for prompt in required_prompts:
    filepath = PROMPTS_DIR / prompt
    if filepath.exists():
        ok(prompt)
    else:
        fail(f"{prompt} missing!")

# ── 8. CLI Availability ──────────────────────────────────────────────────────
print(f"\n{BOLD}[8] AI CLI{RESET}")
claude_path = shutil.which("claude")
kimi_path = shutil.which("kimi")

if claude_path:
    ok(f"Claude CLI found: {claude_path}")
elif kimi_path:
    ok(f"Kimi CLI found: {kimi_path}")
else:
    warn("No AI CLI found (claude/kimi)", "Install Claude Code: https://claude.ai/download")

# ── 9. Telegram Connectivity ─────────────────────────────────────────────────
print(f"\n{BOLD}[9] Telegram{RESET}")
try:
    import urllib.request
    # Try to load token from .env
    tg_token = ""
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                tg_token = line.split("=", 1)[1].strip()

    if tg_token:
        url = f"https://api.telegram.org/bot{tg_token}/getMe"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            if data.get("ok"):
                bot_name = data["result"].get("username", "?")
                ok(f"Telegram bot connected: @{bot_name}")
            else:
                fail("Telegram API returned ok=false")
    else:
        warn("Telegram token not found in .env")
except Exception as e:
    fail(f"Telegram unreachable: {e}")

# ── 10. Hardcoded Path Check ─────────────────────────────────────────────────
print(f"\n{BOLD}[10] Portability{RESET}")
import subprocess
result = subprocess.run(
    ["grep", "-r", "--include=*.md", "--include=*.py", "-l", "Users.aggel.Desktop"],
    capture_output=True, text=True, cwd=str(PROJECT_ROOT), encoding="utf-8"
)
aggel_files = [l for l in result.stdout.strip().split("\n") if l]
if not aggel_files:
    ok("No hardcoded user paths found")
else:
    warn(f"Hardcoded paths in {len(aggel_files)} files", "Run path fixer script")

# ── Summary ──────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"{BOLD}Summary:{RESET} {GREEN}{passed} passed{RESET}, {RED}{failed} failed{RESET}, {YELLOW}{warnings} warnings{RESET}")

if failed == 0:
    print(f"\n{GREEN}{BOLD}🎉 System ready! Run: python GOLD_TACTIC/scripts/analyst_runner.py{RESET}")
elif failed <= 3:
    print(f"\n{YELLOW}{BOLD}⚠️  Fix the {failed} failures above, then re-run this check.{RESET}")
else:
    print(f"\n{RED}{BOLD}🚫 System not ready. Fix {failed} critical issues first.{RESET}")

sys.exit(0 if failed == 0 else 1)
