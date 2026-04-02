#!/usr/bin/env python3
"""
GOLD TACTIC — Telegram Sender
Sends formatted messages and chart images to Telegram channel.

Usage:
  python telegram_sender.py message "text here"           # Send text (HTML)
  python telegram_sender.py photo XAUUSD_5m.png "caption" # Send chart image
  python telegram_sender.py charts                        # Send all 9 charts
  python telegram_sender.py charts XAUUSD                 # Send 3 charts for asset
"""

import urllib.request
import json
import sys
import os
from datetime import datetime
from pathlib import Path

TOKEN = '8621254551:AAF3z5R-5JrAzTKaZQ31E3pmXxtlvQ10wFc'
CHAT_ID = '-1003767339297'
SCREENSHOTS_DIR = Path(__file__).parent.parent / "screenshots"
DATA_DIR = Path(__file__).parent.parent / "data"
LOG_FILE = DATA_DIR / "telegram_log.json"


def _save_message_id(message_id):
    """Append a sent message_id to telegram_log.json for daily cleanup."""
    from datetime import date
    today = date.today().isoformat()
    # Re-read on every call — never cache
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


def send_message(text, parse_mode='HTML'):
    """Send text message to Telegram."""
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    payload = json.dumps({
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload,
                                headers={'Content-Type': 'application/json'})
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read().decode())
    if result.get("ok") and "result" in result:
        _save_message_id(result["result"]["message_id"])
    return result


def send_photo(photo_path, caption=""):
    """Send photo to Telegram channel."""
    url = f'https://api.telegram.org/bot{TOKEN}/sendPhoto'

    # Build multipart form data
    boundary = '----GoldTacticBoundary'
    body = b''

    # chat_id field
    body += f'--{boundary}\r\n'.encode()
    body += b'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
    body += f'{CHAT_ID}\r\n'.encode()

    # caption field
    if caption:
        body += f'--{boundary}\r\n'.encode()
        body += b'Content-Disposition: form-data; name="caption"\r\n\r\n'
        body += f'{caption}\r\n'.encode()

    # parse_mode
    body += f'--{boundary}\r\n'.encode()
    body += b'Content-Disposition: form-data; name="parse_mode"\r\n\r\n'
    body += b'HTML\r\n'

    # photo file
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
    """Send multiple photos as an album."""
    url = f'https://api.telegram.org/bot{TOKEN}/sendMediaGroup'

    boundary = '----GoldTacticBoundary'
    media = []
    body = b''

    for i, (path, caption) in enumerate(photos_with_captions):
        attach_name = f'photo{i}'
        media_item = {
            "type": "photo",
            "media": f"attach://{attach_name}",
        }
        if i == 0 and caption:  # Only first photo gets caption in album
            media_item["caption"] = caption
            media_item["parse_mode"] = "HTML"
        media.append(media_item)

        # Add file
        filename = os.path.basename(path)
        body += f'--{boundary}\r\n'.encode()
        body += f'Content-Disposition: form-data; name="{attach_name}"; filename="{filename}"\r\n'.encode()
        body += b'Content-Type: image/png\r\n\r\n'
        with open(path, 'rb') as f:
            body += f.read()
        body += b'\r\n'

    # chat_id
    body_prefix = b''
    body_prefix += f'--{boundary}\r\n'.encode()
    body_prefix += b'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
    body_prefix += f'{CHAT_ID}\r\n'.encode()

    # media JSON
    body_prefix += f'--{boundary}\r\n'.encode()
    body_prefix += b'Content-Disposition: form-data; name="media"\r\n\r\n'
    body_prefix += json.dumps(media).encode() + b'\r\n'

    full_body = body_prefix + body + f'--{boundary}--\r\n'.encode()

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
    """Send chart images for an asset (or all assets) as albums."""
    assets = [asset] if asset else ["XAUUSD", "NAS100", "EURUSD"]

    for a in assets:
        charts = []
        for tf in ["daily", "4h", "5m"]:
            path = SCREENSHOTS_DIR / f"{a}_{tf}.png"
            if path.exists():
                charts.append((str(path), ""))

        if not charts:
            print(f"  [WARN] No charts found for {a}")
            continue

        # First chart gets the caption
        caption = f"📊 <b>{a}</b> — Daily / 4H / 5min"
        charts[0] = (charts[0][0], caption)

        print(f"  Sending {a} charts ({len(charts)} images)...")
        try:
            result = send_media_group(charts)
            print(f"  {a}: OK")
        except Exception as e:
            print(f"  {a}: ERROR - {e}")
            # Fallback: send one by one
            for path, cap in charts:
                try:
                    send_photo(path, cap)
                except Exception as e2:
                    print(f"    Failed: {e2}")


def send_tier1_pulse(balance, open_trades, asset_prices, next_time):
    """TIER 1 pulse message — minimal, only if something moved."""
    prices_str = " | ".join(
        f"{asset} {price}" for asset, price in asset_prices.items()
    )
    text = (
        f"⚡ PULSE — {datetime.now().strftime('%H:%M')} EET\n"
        f"💼 {balance}€ | Ανοιχτά: {open_trades}/3\n"
        f"📍 {prices_str}\n"
        f"→ Επόμενο: {next_time}"
    )
    return send_message(text, parse_mode='HTML')


def send_tier2_quick(html_text):
    """TIER 2 quick check — agent builds the full HTML."""
    return send_message(html_text, parse_mode='HTML')


def main():
    if len(sys.argv) < 2:
        print("Usage: telegram_sender.py [message|photo|charts] ...")
        return

    cmd = sys.argv[1].lower()

    if cmd == "message":
        text = sys.argv[2] if len(sys.argv) > 2 else "Test message"
        result = send_message(text)
        print(f"Sent OK, ID: {result.get('result', {}).get('message_id')}")

    elif cmd == "photo":
        if len(sys.argv) < 3:
            print("Usage: telegram_sender.py photo <path> [caption]")
            return
        path = sys.argv[2]
        caption = sys.argv[3] if len(sys.argv) > 3 else ""
        result = send_photo(path, caption)
        print(f"Photo sent OK, ID: {result.get('result', {}).get('message_id')}")

    elif cmd == "charts":
        asset = sys.argv[2].upper() if len(sys.argv) > 2 else None
        send_asset_charts(asset)

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
