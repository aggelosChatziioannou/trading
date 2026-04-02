#!/usr/bin/env python3
"""
GOLD TACTIC — Sentiment Fetcher
Fetches Fear & Greed indices for crypto and traditional markets.
Writes to data/sentiment.json.

Usage:
  python sentiment.py           # Fetch all
  python sentiment.py --json    # JSON to stdout
"""

import urllib.request
import json
import sys
import os
from datetime import datetime
from pathlib import Path

if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

OUTPUT_DIR = Path(__file__).parent.parent / "data"
SENTIMENT_FILE = OUTPUT_DIR / "sentiment.json"


def fetch_crypto_fear_greed():
    """Fetch Crypto Fear & Greed Index from Alternative.me."""
    try:
        url = "https://api.alternative.me/fng/?limit=1&format=json"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'GoldTactic/2.0')
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get("data"):
                item = data["data"][0]
                return {
                    "value": int(item["value"]),
                    "label": item["value_classification"],
                    "timestamp": item.get("timestamp", ""),
                    "source": "alternative.me"
                }
    except Exception as e:
        print(f"  [WARN] Crypto Fear & Greed failed: {e}")
    return {"value": None, "label": "unavailable", "source": "alternative.me"}


def fetch_traditional_fear_greed():
    """Fetch CNN Fear & Greed Index."""
    try:
        url = "https://production.dataviz.cnn.com/index/fearandgreed/graphdata"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            score = data.get("fear_and_greed", {}).get("score")
            rating = data.get("fear_and_greed", {}).get("rating")
            if score is not None:
                return {
                    "value": round(float(score)),
                    "label": rating or "unknown",
                    "source": "CNN Fear & Greed"
                }
    except Exception as e:
        print(f"  [WARN] CNN Fear & Greed failed: {e}")
    return {"value": None, "label": "unavailable", "source": "CNN Fear & Greed"}


def fetch_all():
    """Fetch all sentiment data."""
    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "crypto_fear_greed": fetch_crypto_fear_greed(),
        "traditional_fear_greed": fetch_traditional_fear_greed(),
    }

    SENTIMENT_FILE.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8'
    )
    return result


if __name__ == "__main__":
    result = fetch_all()
    if "--json" in sys.argv:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        crypto = result["crypto_fear_greed"]
        trad = result["traditional_fear_greed"]
        print(f"Crypto Fear & Greed: {crypto['value']} ({crypto['label']})")
        print(f"Traditional Fear & Greed: {trad['value']} ({trad['label']})")
        print(f"Saved to {SENTIMENT_FILE}")
