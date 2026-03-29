#!/usr/bin/env python3
"""
GOLD TACTIC — News Scout Agent
Fetches latest market news for XAUUSD, NAS100, EURUSD.
Writes structured output to news_feed.json for the TJR analyst.

Usage:
  python news_scout.py              # Fetch all
  python news_scout.py XAUUSD       # Fetch for specific asset
"""

import urllib.request
import json
import sys
import time
import os
from datetime import datetime, timedelta
from pathlib import Path

# Fix Windows console encoding for Greek
if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

OUTPUT_DIR = Path(__file__).parent.parent
NEWS_FILE = OUTPUT_DIR / "news_feed.json"
FINNHUB_API_KEY = "d6vako1r01qiiutb412gd6vako1r01qiiutb4130"

# News search keywords per asset
ASSET_KEYWORDS = {
    "XAUUSD": {
        "finnhub_category": "general",
        "keywords": ["gold", "XAU", "XAUUSD", "precious metals", "safe haven"],
        "display": "Χρυσός (XAUUSD)",
    },
    "NAS100": {
        "finnhub_category": "general",
        "keywords": ["nasdaq", "NAS100", "tech stocks", "S&P 500", "stock market"],
        "display": "Nasdaq (NAS100)",
    },
    "EURUSD": {
        "finnhub_category": "forex",
        "keywords": ["EUR/USD", "EURUSD", "euro", "ECB", "dollar"],
        "display": "EUR/USD",
    },
    "MACRO": {
        "finnhub_category": "general",
        "keywords": ["Fed", "interest rate", "inflation", "geopolitical", "oil", "war"],
        "display": "Μακροοικονομία",
    },
}


def fetch_finnhub_news(category="general"):
    """Fetch general market news from Finnhub."""
    try:
        url = (f"https://finnhub.io/api/v1/news?"
               f"category={category}&token={FINNHUB_API_KEY}")
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'GoldTactic/2.0')
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"  [WARN] Finnhub news fetch failed: {e}")
        return []


def fetch_finnhub_forex_news():
    """Fetch forex-specific news from Finnhub."""
    try:
        url = (f"https://finnhub.io/api/v1/news?"
               f"category=forex&token={FINNHUB_API_KEY}")
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'GoldTactic/2.0')
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"  [WARN] Finnhub forex news failed: {e}")
        return []


def filter_news_by_keywords(news_list, keywords, max_age_hours=24, max_items=5):
    """Filter news items by keyword relevance and recency."""
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    filtered = []

    for item in news_list:
        # Check age
        pub_time = item.get("datetime", 0)
        if now - pub_time > max_age_seconds:
            continue

        # Check keyword relevance
        text = (item.get("headline", "") + " " + item.get("summary", "")).lower()
        relevance = sum(1 for kw in keywords if kw.lower() in text)

        if relevance > 0:
            filtered.append({
                "headline": item.get("headline", ""),
                "summary": item.get("summary", "")[:300],
                "source": item.get("source", "Unknown"),
                "url": item.get("url", ""),
                "datetime": datetime.fromtimestamp(pub_time).strftime("%Y-%m-%d %H:%M"),
                "timestamp": pub_time,
                "relevance": relevance,
                "category": item.get("category", ""),
            })

    # Sort by relevance then recency
    filtered.sort(key=lambda x: (-x["relevance"], -x["timestamp"]))
    return filtered[:max_items]


def scout_all(asset_filter=None):
    """Fetch and categorize news for all assets."""
    print(f"GOLD TACTIC — News Scout")
    print(f"Fetching news at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    # Fetch raw news (rate limit: 1 call per second for free tier)
    print("Fetching general news...")
    general_news = fetch_finnhub_news("general")
    print(f"  Got {len(general_news)} general articles")

    time.sleep(1)  # Rate limit

    print("Fetching forex news...")
    forex_news = fetch_finnhub_forex_news()
    print(f"  Got {len(forex_news)} forex articles")

    all_news = general_news + forex_news

    # Filter for each asset
    assets_to_process = {k: v for k, v in ASSET_KEYWORDS.items()
                         if asset_filter is None or k in asset_filter}

    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_articles_fetched": len(all_news),
        "assets": {},
    }

    for asset_name, config in assets_to_process.items():
        print(f"\n--- {config['display']} ---")
        filtered = filter_news_by_keywords(all_news, config["keywords"])
        result["assets"][asset_name] = {
            "display": config["display"],
            "count": len(filtered),
            "news": filtered,
        }
        for i, item in enumerate(filtered):
            print(f"  {i+1}. [{item['source']}] {item['headline'][:80]}")
            print(f"     {item['datetime']} | relevance: {item['relevance']}")

    # Write output
    NEWS_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\nDone! News saved to {NEWS_FILE}")
    print(f"Total relevant articles: {sum(a['count'] for a in result['assets'].values())}")

    return result


if __name__ == "__main__":
    asset_filter = None
    if len(sys.argv) > 1:
        asset_filter = [a.upper() for a in sys.argv[1:]]
    scout_all(asset_filter)
