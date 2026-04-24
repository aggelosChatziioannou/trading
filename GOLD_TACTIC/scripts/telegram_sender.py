#!/usr/bin/env python3
"""
GOLD TACTIC — Telegram Sender (v7.1)

Sends formatted messages, edits, pins, reactions, and chart images to Telegram.

Commands:
  message "text" [--reply-to ID] [--effect fire|party] [--silent]
  edit MSG_ID "new text"
  pin MSG_ID
  unpin-all
  react MSG_ID EMOJI
  dashboard [--text "html"]      # edit pinned state; reads from stdin if no --text
  photo PATH "caption"
  charts [ASSET]
  detect-chat                     # prints chat type (private|group|channel|supergroup)

All commands print the resulting message_id (or state) to stdout so prompts can chain calls.
"""

import urllib.request
import urllib.error
import json
import sys
import os
import html
from datetime import datetime
from pathlib import Path

if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    try:
        sys.stdin.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHANNEL')
if not TOKEN or not CHAT_ID:
    raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL must be set in .env")

SCREENSHOTS_DIR = Path(__file__).parent.parent / "screenshots"
DATA_DIR = Path(__file__).parent.parent / "data"
LOG_FILE = DATA_DIR / "telegram_log.json"
STATE_FILE = DATA_DIR / "telegram_state.json"

API_BASE = f'https://api.telegram.org/bot{TOKEN}'

# Private-chat-only animated effects (sendMessage message_effect_id)
EFFECT_FIRE = "5104841245755180586"
EFFECT_PARTY = "5046509860389126442"
EFFECT_THUMBS_UP = "5107584321108051014"
EFFECT_HEART = "5044134455711629726"
EFFECT_THUMBS_DOWN = "5104858069142078462"
EFFECTS = {
    "fire": EFFECT_FIRE,
    "party": EFFECT_PARTY,
    "thumbsup": EFFECT_THUMBS_UP,
    "heart": EFFECT_HEART,
    "thumbsdown": EFFECT_THUMBS_DOWN,
}


# ---------- state & logging helpers ----------

def _save_message_id(message_id):
    """Append sent message_id to telegram_log.json for daily cleanup tracking."""
    from datetime import date
    today = date.today().isoformat()
    if LOG_FILE.exists():
        try:
            log = json.loads(LOG_FILE.read_text(encoding='utf-8'))
        except Exception:
            log = {}
    else:
        log = {}
    if log.get("date") != today:
        log = {"date": today, "message_ids": []}
    log["message_ids"].append(message_id)
    LOG_FILE.write_text(json.dumps(log, indent=2), encoding='utf-8')


def read_state():
    """Read telegram_state.json or return empty default."""
    if not STATE_FILE.exists():
        return {
            "pinned_dashboard_id": None,
            "last_selector_id": None,
            "last_monitor_id": None,
            "open_trade_entry_ids": {},
            "last_update": None,
            "chat_type": None,
        }
    try:
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {"pinned_dashboard_id": None, "open_trade_entry_ids": {}}


def write_state(state):
    state["last_update"] = datetime.now().isoformat(timespec='seconds')
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')


def html_escape(s):
    """Escape dynamic content for safe insertion into HTML-parsed Telegram messages."""
    if s is None:
        return ""
    return html.escape(str(s), quote=False)


def chunk_message(text, max_chars=4000):
    """Split a message on paragraph boundaries so every chunk fits within Telegram's 4096 limit."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    remaining = text
    while len(remaining) > max_chars:
        cut = remaining.rfind("\n\n", 0, max_chars)
        if cut == -1:
            cut = remaining.rfind("\n", 0, max_chars)
        if cut == -1:
            cut = max_chars
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


# ---------- core HTTP primitive ----------

_DRY_RUN = os.environ.get("GOLD_DRY_RUN") == "1"
_DRY_RUN_COUNTER = {"id": 900000}


def _dry_run_dispatch(method, payload):
    """Write the would-be-sent call to a review file and return a fake API result.
    Active when GOLD_DRY_RUN=1. Used to preview Telegram flow end-to-end without sending."""
    review_dir = DATA_DIR / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    ts_file = os.environ.get("GOLD_DRY_RUN_FILE") or f"dry_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    path = review_dir / ts_file
    _DRY_RUN_COUNTER["id"] += 1
    fake_id = _DRY_RUN_COUNTER["id"]
    now = datetime.now().strftime("%H:%M:%S")
    reply = payload.get("reply_parameters", {}).get("message_id") if isinstance(payload, dict) else None
    silent = payload.get("disable_notification") if isinstance(payload, dict) else None
    effect = payload.get("message_effect_id") if isinstance(payload, dict) else None
    header = f"\n### [{now}] {method} → msg_id={fake_id}"
    if reply:
        header += f" (reply to {reply})"
    if silent:
        header += " (silent)"
    if effect:
        header += f" (effect={effect})"
    body = payload.get("text") or payload.get("caption") or json.dumps(payload, ensure_ascii=False, indent=2)
    with path.open("a", encoding="utf-8") as f:
        f.write(header + "\n\n")
        f.write("```\n" + str(body) + "\n```\n")
    return {"ok": True, "result": {"message_id": fake_id}, "dry_run": True, "review_file": str(path)}


def _api_call(method, payload, raise_on_error=True):
    """POST a JSON body to the Bot API and return the parsed result.
    If GOLD_DRY_RUN=1, write the call to a review file and return a fake result."""
    if _DRY_RUN:
        return _dry_run_dispatch(method, payload)
    url = f'{API_BASE}/{method}'
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"ok": False, "description": body, "error_code": e.code}
        if raise_on_error:
            raise RuntimeError(f"Telegram API {method} failed: {parsed}")
        return parsed


# ---------- chat type detection (effects only work in private) ----------

def detect_chat_type():
    """Call getChat and cache the result in state."""
    result = _api_call('getChat', {'chat_id': CHAT_ID}, raise_on_error=False)
    chat_type = result.get("result", {}).get("type") if result.get("ok") else None
    state = read_state()
    state["chat_type"] = chat_type
    write_state(state)
    return chat_type


def _effects_supported():
    state = read_state()
    t = state.get("chat_type")
    if t is None:
        t = detect_chat_type()
    return t == "private"


# ---------- send / edit / pin / react ----------

def send_message(text, parse_mode='HTML', reply_to=None, effect_id=None,
                 disable_notification=False, disable_preview=True):
    """Send a text message. Returns the full API result."""
    payload = {
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': disable_preview,
        'disable_notification': disable_notification,
    }
    if reply_to is not None:
        payload['reply_parameters'] = {
            'message_id': int(reply_to),
            'allow_sending_without_reply': True,
        }
    if effect_id is not None and _effects_supported():
        payload['message_effect_id'] = effect_id
    result = _api_call('sendMessage', payload)
    if result.get("ok"):
        _save_message_id(result["result"]["message_id"])
    return result


def edit_message(message_id, text, parse_mode='HTML', disable_preview=True):
    """Edit an existing message. Returns the API result."""
    payload = {
        'chat_id': CHAT_ID,
        'message_id': int(message_id),
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': disable_preview,
    }
    return _api_call('editMessageText', payload, raise_on_error=False)


def pin_message(message_id, silent=True):
    payload = {
        'chat_id': CHAT_ID,
        'message_id': int(message_id),
        'disable_notification': silent,
    }
    return _api_call('pinChatMessage', payload, raise_on_error=False)


def unpin_all():
    return _api_call('unpinAllChatMessages', {'chat_id': CHAT_ID}, raise_on_error=False)


def react(message_id, emoji, is_big=False):
    """Set a single-emoji reaction on a message."""
    payload = {
        'chat_id': CHAT_ID,
        'message_id': int(message_id),
        'reaction': [{'type': 'emoji', 'emoji': emoji}],
        'is_big': is_big,
    }
    return _api_call('setMessageReaction', payload, raise_on_error=False)


# ---------- dashboard helper (create-or-edit pinned) ----------

def update_dashboard(text):
    """Ensure a pinned dashboard message exists and contains `text`.

    Logic:
      1. Read state → pinned_dashboard_id.
      2. If present, try editMessageText. If that fails (message not found or deleted),
         fall through to send+pin path.
      3. If absent, send new message, pin it, save id to state.
    """
    state = read_state()
    existing_id = state.get("pinned_dashboard_id")

    if existing_id:
        result = edit_message(existing_id, text)
        if result.get("ok"):
            return {"action": "edited", "message_id": existing_id}
        # Fall through on "message to edit not found", "message is not modified", etc.
        desc = (result.get("description") or "").lower()
        if "not modified" in desc:
            return {"action": "unchanged", "message_id": existing_id}

    # Need a fresh dashboard message
    sent = send_message(text, disable_notification=True)
    if not sent.get("ok"):
        return {"action": "failed", "error": sent}
    new_id = sent["result"]["message_id"]
    pin_result = pin_message(new_id, silent=True)
    state["pinned_dashboard_id"] = new_id
    write_state(state)
    return {
        "action": "created",
        "message_id": new_id,
        "pinned": pin_result.get("ok", False),
    }


# ---------- photos / media groups (unchanged from v7.0) ----------

def send_photo(photo_path, caption=""):
    if _DRY_RUN:
        return _dry_run_dispatch("sendPhoto", {"caption": f"[PHOTO: {photo_path}]\n{caption}"})
    url = f'{API_BASE}/sendPhoto'
    boundary = '----GoldTacticBoundary'
    body = b''

    body += f'--{boundary}\r\n'.encode()
    body += b'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
    body += f'{CHAT_ID}\r\n'.encode()

    if caption:
        body += f'--{boundary}\r\n'.encode()
        body += b'Content-Disposition: form-data; name="caption"\r\n\r\n'
        body += f'{caption}\r\n'.encode()

    body += f'--{boundary}\r\n'.encode()
    body += b'Content-Disposition: form-data; name="parse_mode"\r\n\r\n'
    body += b'HTML\r\n'

    filename = os.path.basename(photo_path)
    body += f'--{boundary}\r\n'.encode()
    body += f'Content-Disposition: form-data; name="photo"; filename="{filename}"\r\n'.encode()
    body += b'Content-Type: image/png\r\n\r\n'
    with open(photo_path, 'rb') as f:
        body += f.read()
    body += b'\r\n'
    body += f'--{boundary}--\r\n'.encode()

    req = urllib.request.Request(
        url, data=body,
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
    )
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read().decode())
    if result.get("ok") and "result" in result:
        _save_message_id(result["result"]["message_id"])
    return result


def send_media_group(photos_with_captions):
    url = f'{API_BASE}/sendMediaGroup'
    boundary = '----GoldTacticBoundary'
    media = []
    body = b''

    for i, (path, caption) in enumerate(photos_with_captions):
        attach_name = f'photo{i}'
        item = {"type": "photo", "media": f"attach://{attach_name}"}
        if i == 0 and caption:
            item["caption"] = caption
            item["parse_mode"] = "HTML"
        media.append(item)
        filename = os.path.basename(path)
        body += f'--{boundary}\r\n'.encode()
        body += f'Content-Disposition: form-data; name="{attach_name}"; filename="{filename}"\r\n'.encode()
        body += b'Content-Type: image/png\r\n\r\n'
        with open(path, 'rb') as f:
            body += f.read()
        body += b'\r\n'

    prefix = b''
    prefix += f'--{boundary}\r\n'.encode()
    prefix += b'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
    prefix += f'{CHAT_ID}\r\n'.encode()
    prefix += f'--{boundary}\r\n'.encode()
    prefix += b'Content-Disposition: form-data; name="media"\r\n\r\n'
    prefix += json.dumps(media).encode() + b'\r\n'

    full_body = prefix + body + f'--{boundary}--\r\n'.encode()
    req = urllib.request.Request(
        url, data=full_body,
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
    )
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read().decode())
    if result.get("ok") and isinstance(result.get("result"), list):
        for msg in result["result"]:
            if "message_id" in msg:
                _save_message_id(msg["message_id"])
    return result


def send_asset_charts(asset=None):
    assets = [asset] if asset else ["XAUUSD", "NAS100", "EURUSD"]
    for a in assets:
        charts = []
        for tf in ["daily", "4h", "5m"]:
            path = SCREENSHOTS_DIR / f"{a}_{tf}.png"
            if path.exists():
                charts.append((str(path), ""))
        if not charts:
            print(f"  [WARN] No charts found for {a}", file=sys.stderr)
            continue
        caption = f"📊 <b>{a}</b> — Daily / 4H / 5min"
        charts[0] = (charts[0][0], caption)
        print(f"  Sending {a} charts ({len(charts)} images)...", file=sys.stderr)
        try:
            send_media_group(charts)
            print(f"  {a}: OK", file=sys.stderr)
        except Exception as e:
            print(f"  {a}: ERROR - {e}", file=sys.stderr)
            for path, cap in charts:
                try:
                    send_photo(path, cap)
                except Exception as e2:
                    print(f"    Failed: {e2}", file=sys.stderr)


# ---------- legacy helpers kept for backward compat ----------

def send_tier1_pulse(balance, open_trades, asset_prices, next_time):
    prices_str = " | ".join(f"{asset} {price}" for asset, price in asset_prices.items())
    text = (
        f"⚡ PULSE — {datetime.now().strftime('%H:%M')} EET\n"
        f"💼 {balance}€ | Ανοιχτά: {open_trades}/3\n"
        f"📍 {prices_str}\n"
        f"→ Επόμενο: {next_time}"
    )
    return send_message(text)


def send_tier2_quick(html_text):
    return send_message(html_text)


# ---------- CLI ----------

def _parse_flags(argv):
    """Pull known flags out of argv. Returns (positional, flags)."""
    positional = []
    flags = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--reply-to' and i + 1 < len(argv):
            flags['reply_to'] = argv[i + 1]; i += 2; continue
        if a == '--effect' and i + 1 < len(argv):
            flags['effect'] = argv[i + 1]; i += 2; continue
        if a == '--silent':
            flags['silent'] = True; i += 1; continue
        if a == '--text' and i + 1 < len(argv):
            flags['text'] = argv[i + 1]; i += 2; continue
        positional.append(a); i += 1
    return positional, flags


def main():
    if len(sys.argv) < 2:
        print("Usage: telegram_sender.py [message|edit|pin|unpin-all|react|dashboard|photo|charts|detect-chat] ...")
        return 1

    cmd = sys.argv[1].lower()
    rest, flags = _parse_flags(sys.argv[2:])

    if cmd == "message":
        if not rest:
            print("Usage: telegram_sender.py message \"text\" [--reply-to ID] [--effect fire|party] [--silent]")
            return 1
        text = rest[0]
        effect_id = EFFECTS.get(flags.get('effect', '').lower()) if flags.get('effect') else None
        result = send_message(
            text,
            reply_to=flags.get('reply_to'),
            effect_id=effect_id,
            disable_notification=flags.get('silent', False),
        )
        mid = result.get('result', {}).get('message_id')
        print(mid if mid else result)
        return 0 if mid else 1

    if cmd == "edit":
        if len(rest) < 2:
            print("Usage: telegram_sender.py edit MSG_ID \"new text\"")
            return 1
        result = edit_message(rest[0], rest[1])
        if result.get("ok"):
            print(rest[0])
            return 0
        print(result)
        return 1

    if cmd == "pin":
        if not rest:
            print("Usage: telegram_sender.py pin MSG_ID")
            return 1
        result = pin_message(rest[0], silent=True)
        print("OK" if result.get("ok") else result)
        return 0 if result.get("ok") else 1

    if cmd == "unpin-all":
        pass

    print(f"Unknown command: {cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
