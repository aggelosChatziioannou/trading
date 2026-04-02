#!/usr/bin/env python3
"""
GOLD TACTIC — Telegram Cleanup
Deletes previous day's Telegram messages at start of new trading day.
Reads message IDs from data/telegram_log.json.

Usage:
  python telegram_cleanup.py    # Run cleanup if date < today
"""

import urllib.request
import json
import sys
import os
from datetime import date
from pathlib import Path

if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

TOKEN = '8621254551:AAF3z5R-5JrAzTKaZQ31E3pmXxtlvQ10wFc'
CHAT_ID = '-1003767339297'
DATA_DIR = Path(__file__).parent.parent / "data"
LOG_FILE = DATA_DIR / "telegram_log.json"


def delete_message(message_id):
    """Delete a single Telegram message. Returns True on success or safe failure."""
    url = f'https://api.telegram.org/bot{TOKEN}/deleteMessage'
    payload = json.dumps({
        'chat_id': CHAT_ID,
        'message_id': message_id,
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload,
                                  headers={'Content-Type': 'application/json'})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read().decode())
        return result.get("ok", False)
    except urllib.error.HTTPError as e:
        if e.code == 400:
            # Message already deleted or not found — safe to ignore
            return True
        print(f"  [WARN] deleteMessage {message_id} failed: HTTP {e.code}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  [WARN] deleteMessage {message_id} error: {e}", file=sys.stderr)
        return False


def run_cleanup():
    """Delete previous day's messages if log date < today."""
    today = date.today().isoformat()

    if not LOG_FILE.exists():
        print("Cleanup: no telegram_log.json found — nothing to clean.")
        return

    try:
        log = json.loads(LOG_FILE.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"Cleanup: failed to read log: {e}")
        return

    log_date = log.get("date")
    message_ids = log.get("message_ids", [])

    if not log_date or log_date >= today:
        print(f"Cleanup: log date={log_date}, today={today} — nothing to clean.")
        return

    if not message_ids:
        print(f"Cleanup: log date={log_date} < today but no message IDs — resetting log.")
        LOG_FILE.write_text(json.dumps({"date": today, "message_ids": []}, indent=2),
                            encoding='utf-8')
        return

    print(f"Cleanup: deleting {len(message_ids)} messages from {log_date}...")
    deleted = 0
    for mid in message_ids:
        if delete_message(mid):
            deleted += 1

    print(f"Cleanup: done — {deleted}/{len(message_ids)} deleted.")
    LOG_FILE.write_text(json.dumps({"date": today, "message_ids": []}, indent=2),
                        encoding='utf-8')


if __name__ == "__main__":
    run_cleanup()
