#!/usr/bin/env python3
"""GOLD TACTIC - Trading Session Check"""
import json, os, sys
from pathlib import Path
from datetime import datetime

OUTPUT_FILE = Path(__file__).parent.parent / "data" / "session_now.json"

def current_session(now=None):
    now = now or datetime.now()
    h = now.hour + now.minute / 60.0
    wd = now.weekday()
    if wd >= 5:
        return {"name":"Σαββατοκύριακο","tier":"crypto_only","emoji":"🏖️","weekend":True,"optimal":False,"message":"Crypto μόνο — forex/indices κλειστά"}
    lkz = 10.0 <= h < 12.0
    nkz = 15.5 <= h < 17.5
    lon = 10.0 <= h < 18.0
    ny  = 15.5 <= h < 23.0
    if lkz and nkz:
        return {"name":"London/NY Overlap","tier":"optimal","emoji":"🔥","weekend":False,"optimal":True,"message":"Peak liquidity — optimal για Tier C signals"}
    if lkz:
        return {"name":"London Kill Zone","tier":"optimal","emoji":"🎯","weekend":False,"optimal":True,"message":"Optimal window — Tier C signals ενεργά"}
    if nkz:
        return {"name":"NY Kill Zone","tier":"optimal","emoji":"🎯","weekend":False,"optimal":True,"message":"Optimal window — Tier C signals ενεργά"}
    if lon or ny:
        return {"name":"London Session" if lon else "NY Session","tier":"acceptable","emoji":"✅","weekend":False,"optimal":False,"message":"Acceptable — signals OK αλλά όχι peak"}
    return {"name":"Asian / Off-hours","tier":"off","emoji":"🌙","weekend":False,"optimal":False,"message":"Εκτός kill zones — μόνο παρακολούθηση, όχι Tier C"}

def session_tag(s=None):
    s = s or current_session()
    return f"{s['emoji']} <b>{s['name']}</b> · {s['message']}"

def main():
    s = current_session()
    if "--line" in sys.argv:
        print(session_tag(s))
        return
    try:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[WARN] {e}", file=sys.stderr)
    print(json.dumps(s, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
