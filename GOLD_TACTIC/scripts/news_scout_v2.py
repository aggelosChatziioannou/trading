#!/usr/bin/env python3
"""
GOLD TACTIC — News Scout v2
Enhanced news fetching: Finnhub + CryptoPanic + Google News RSS.
Every item includes article URL for Telegram links.
Writes to data/news_feed.json.

Usage:
  python news_scout_v2.py              # Fetch all
  python news_scout_v2.py --light      # TIER 2: CryptoPanic + Google RSS only
  python news_scout_v2.py --full       # TIER 3: All sources
  python news_scout_v2.py XAUUSD       # Specific asset
"""

import urllib.request
import json
import sys
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

OUTPUT_DIR = Path(__file__).parent.parent / "data"
NEWS_FILE = OUTPUT_DIR / "news_feed.json"

from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY', '')
CRYPTOPANIC_API_KEY = os.environ.get('CRYPTOPANIC_API_KEY', '')
# FINNHUB is optional — only required for full scan, not --light mode.
# Functions that need it will check and skip/warn if missing.

GOOGLE_NEWS_QUERIES = {
    "EURUSD": "EURUSD+OR+%22EUR+USD%22+forex",
    "GBPUSD": "GBPUSD+OR+%22GBP+USD%22+forex",
    "XAUUSD": "gold+price+OR+XAUUSD+OR+%22gold+rally%22",
    "NAS100": "nasdaq+OR+%22tech+stocks%22+OR+%22S%26P+500%22",
    "BTC": "bitcoin+OR+BTC+crypto",
    "SOL": "solana+OR+SOL+crypto",
    "MACRO": "federal+reserve+OR+ECB+OR+inflation+OR+interest+rate",
}

ASSET_KEYWORDS = {
    "XAUUSD": ["gold", "XAU", "XAUUSD", "precious metals", "safe haven"],
    "NAS100": ["nasdaq", "NAS100", "tech stocks", "S&P 500", "stock market"],
    "EURUSD": ["EUR/USD", "EURUSD", "euro", "ECB", "dollar"],
    "GBPUSD": ["GBP/USD", "GBPUSD", "pound", "sterling", "BoE"],
    "BTC": ["bitcoin", "BTC", "crypto"],
    "SOL": ["solana", "SOL"],
    "MACRO": ["Fed", "interest rate", "inflation", "geopolitical", "oil", "war"],
}


def fetch_json(url, timeout=10):
    """Fetch JSON from URL."""
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'GoldTactic/2.0')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  [WARN] Fetch failed {url[:60]}: {e}")
        return None


def fetch_rss(url, timeout=10):
    """Fetch and parse RSS XML."""
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  [WARN] RSS fetch failed {url[:60]}: {e}")
        return None


# --- Source 1: Finnhub ---

def fetch_finnhub(category="general", max_items=10):
    """Fetch from Finnhub API."""
    items = []
    data = fetch_json(
        f"https://finnhub.io/api/v1/news?category={category}&token={FINNHUB_API_KEY}"
    )
    if not data:
        return items

    now = time.time()
    for article in data[:30]:
        pub_time = article.get("datetime", 0)
        if now - pub_time > 86400:  # Skip > 24h old
            continue
        items.append({
            "headline": article.get("headline", ""),
            "summary": article.get("summary", "")[:200],
            "source": article.get("source", "Unknown"),
            "url": article.get("url", ""),
            "datetime": datetime.fromtimestamp(pub_time).strftime("%Y-%m-%d %H:%M"),
            "timestamp": pub_time,
        })

    return items[:max_items]


# --- Source 2: CryptoPanic ---

def fetch_cryptopanic(currencies="BTC,SOL", max_items=5):
    """Fetch from CryptoPanic API (free tier)."""
    if not CRYPTOPANIC_API_KEY:
        # Fallback: use public page scraping via Google News
        return []

    data = fetch_json(
        f"https://cryptopanic.com/api/v1/posts/"
        f"?auth_token={CRYPTOPANIC_API_KEY}&currencies={currencies}&kind=news"
    )
    if not data or "results" not in data:
        return []

    items = []
    for post in data["results"][:max_items]:
        votes = post.get("votes", {})
        sentiment = "neutral"
        pos = votes.get("positive", 0) + votes.get("liked", 0)
        neg = votes.get("negative", 0) + votes.get("disliked", 0)
        if pos > neg * 2:
            sentiment = "bullish"
        elif neg > pos * 2:
            sentiment = "bearish"

        items.append({
            "headline": post.get("title", ""),
            "summary": "",
            "source": post.get("source", {}).get("title", "CryptoPanic"),
            "url": post.get("url", ""),
            "datetime": post.get("published_at", "")[:16].replace("T", " "),
            "timestamp": 0,
            "sentiment": sentiment,
            "currencies": [c["code"] for c in post.get("currencies", [])],
        })

    return items


# --- Source 3: Google News RSS ---

def fetch_google_news_rss(query_key, max_items=3):
    """Fetch Google News RSS for a specific query."""
    query = GOOGLE_NEWS_QUERIES.get(query_key, query_key)
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    xml_text = fetch_rss(url)
    if not xml_text:
        return []

    items = []
    try:
        root = ET.fromstring(xml_text)
        for item in root.findall('.//item')[:max_items]:
            title = item.findtext('title', '').strip()
            link = item.findtext('link', '').strip()
            pub_date = item.findtext('pubDate', '').strip()
            source = item.findtext('source', '').strip()

            items.append({
                "headline": title,
                "summary": "",
                "source": source if source else "Google News",
                "url": link,
                "datetime": pub_date[:16] if pub_date else "",
                "timestamp": 0,
            })
    except Exception as e:
        print(f"  [WARN] Google News RSS parse error: {e}")

    return items


# --- Main orchestration ---

def scout_light(asset_filter=None):
    """TIER 2: Light news — CryptoPanic + Google News RSS only."""
    print("News Scout v2 — LIGHT mode (TIER 2)")

    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "light",
        "assets": {},
    }

    # CryptoPanic for crypto
    print("Fetching CryptoPanic...")
    crypto_news = fetch_cryptopanic("BTC,SOL")
    if crypto_news:
        result["assets"]["CRYPTO"] = {"news": crypto_news, "count": len(crypto_news)}

    # Google News RSS for key assets
    assets_to_check = asset_filter or ["EURUSD", "XAUUSD", "BTC", "MACRO"]
    for asset in assets_to_check:
        if asset in GOOGLE_NEWS_QUERIES:
            print(f"Fetching Google News: {asset}...")
            gn = fetch_google_news_rss(asset, max_items=2)
            if gn:
                existing = result["assets"].get(asset, {"news": [], "count": 0})
                existing["news"].extend(gn)
                existing["count"] = len(existing["news"])
                result["assets"][asset] = existing

    result["total_articles"] = sum(a["count"] for a in result["assets"].values())
    NEWS_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Done! {result['total_articles']} articles. Saved to {NEWS_FILE}")
    return result


def scout_full(asset_filter=None):
    """TIER 3: Full news — Finnhub + CryptoPanic + Google News RSS."""
    print("News Scout v2 — FULL mode (TIER 3)")

    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "full",
        "assets": {},
    }

    # Finnhub
    print("Fetching Finnhub general...")
    general = fetch_finnhub("general")
    print(f"  Got {len(general)} articles")
    time.sleep(1)

    print("Fetching Finnhub forex...")
    forex = fetch_finnhub("forex")
    print(f"  Got {len(forex)} articles")

    all_finnhub = general + forex

    # Filter Finnhub by asset keywords
    for asset, keywords in ASSET_KEYWORDS.items():
        if asset_filter and asset not in asset_filter:
            continue
        matched = []
        for item in all_finnhub:
            text = (item["headline"] + " " + item["summary"]).lower()
            if any(kw.lower() in text for kw in keywords):
                matched.append(item)
        if matched:
            result["assets"][asset] = {"news": matched[:3], "count": len(matched[:3])}

    # CryptoPanic
    print("Fetching CryptoPanic...")
    crypto_news = fetch_cryptopanic("BTC,SOL")
    if crypto_news:
        for item in crypto_news:
            for curr in item.get("currencies", ["BTC"]):
                existing = result["assets"].get(curr, {"news": [], "count": 0})
                existing["news"].append(item)
                existing["count"] = len(existing["news"])
                result["assets"][curr] = existing

    # Google News RSS
    assets_to_check = asset_filter or list(GOOGLE_NEWS_QUERIES.keys())
    for asset in assets_to_check:
        if asset in GOOGLE_NEWS_QUERIES:
            print(f"Fetching Google News: {asset}...")
            gn = fetch_google_news_rss(asset, max_items=2)
            if gn:
                existing = result["assets"].get(asset, {"news": [], "count": 0})
                existing["news"].extend(gn)
                existing["count"] = len(existing["news"])
                result["assets"][asset] = existing
            time.sleep(0.5)

    result["total_articles"] = sum(a["count"] for a in result["assets"].values())
    NEWS_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Done! {result['total_articles']} articles. Saved to {NEWS_FILE}")
    return result


# ── News Summarization (FIX #11) ─────────────────────────────────────────────

BULLISH_WORDS = [
    "rally", "surge", "soar", "jump", "gain", "rise", "bullish", "breakout",
    "record high", "all-time high", "pump", "boost", "recovery", "strong",
    "upbeat", "optimistic", "hawkish", "buy",
]
BEARISH_WORDS = [
    "crash", "plunge", "dump", "drop", "fall", "decline", "bearish",
    "breakdown", "sell-off", "selloff", "fear", "panic", "recession",
    "weak", "dovish", "cut", "loss", "risk-off", "downgrade",
]


def _detect_headline_sentiment(headline):
    """Simple keyword sentiment detection."""
    if not headline:
        return "neutral"
    lower = headline.lower()
    bull = sum(1 for kw in BULLISH_WORDS if kw in lower)
    bear = sum(1 for kw in BEARISH_WORDS if kw in lower)
    if bull > bear:
        return "bullish"
    elif bear > bull:
        return "bearish"
    return "neutral"


def summarize_news(result):
    """
    Δημιουργεί compact summary: top 3 headlines ανά asset + sentiment.
    Μειώνει tokens που χρειάζεται ο Analyst να διαβάσει.
    """
    summary = {}

    for asset_key, asset_data in result.get("assets", {}).items():
        articles = asset_data.get("news", [])
        if not articles:
            continue

        top_3 = articles[:3]
        summaries = []
        sentiment_counts = {"bullish": 0, "bearish": 0, "neutral": 0}

        for article in top_3:
            headline = article.get("headline") or article.get("title") or "?"
            # Use existing sentiment if available (CryptoPanic), else detect
            sent = article.get("sentiment", "").lower()
            if sent not in ("bullish", "bearish"):
                sent = _detect_headline_sentiment(headline)

            sentiment_counts[sent] = sentiment_counts.get(sent, 0) + 1
            summaries.append({
                "headline": headline[:120],
                "sentiment": sent,
            })

        # Overall sentiment for this asset
        if sentiment_counts["bullish"] > sentiment_counts["bearish"]:
            overall = "bullish"
        elif sentiment_counts["bearish"] > sentiment_counts["bullish"]:
            overall = "bearish"
        else:
            overall = "neutral"

        summary[asset_key] = {
            "overall_sentiment": overall,
            "article_count": len(articles),
            "top_headlines": summaries,
        }

    return summary


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    asset_filter = [a.upper() for a in args] if args else None
    do_summarize = "--summarize" in sys.argv

    if "--light" in sys.argv:
        result = scout_light(asset_filter)
    else:
        result = scout_full(asset_filter)

    if do_summarize and result:
        summary = summarize_news(result)
        result["summary"] = summary
        NEWS_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"\nSummary ({len(summary)} assets):")
        for asset, info in summary.items():
            emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(info["overall_sentiment"], "?")
            print(f"  {emoji} {asset}: {info['overall_sentiment']} ({info['article_count']} articles)")
            for h in info["top_headlines"]:
                print(f"      [{h['sentiment']}] {h['headline'][:80]}")
