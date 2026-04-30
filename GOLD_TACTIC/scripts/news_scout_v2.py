#!/usr/bin/env python3
"""
GOLD TACTIC — News Scout v3 (Phase 1 + Reddit upgrade)

Sources:
  - Finnhub API (general + forex categories)
  - CryptoPanic API (BTC/ETH/SOL/XRP — needs CRYPTOPANIC_API_KEY)
  - Google News RSS (all 12 master assets + MACRO)
  - ForexLive RSS (institutional-grade forex breaking)
  - Investing.com RSS (economic + forex news)
  - ZeroHedge RSS (contrarian macro)
  - CoinDesk + Cointelegraph RSS (crypto)
  - MarketWatch RSS (indices)
  - Reddit RSS (r/Forex, r/CryptoCurrency, r/Bitcoin, r/wallstreetbets)

Source quality tiers (used for AI weighting + ✅/❌ News verdict):
  TIER 1 (×1.5): Reuters, Bloomberg, ForexLive, CoinDesk, WSJ, FT, CNBC
  TIER 2 (×1.0): Yahoo, Investing.com, FOREX.com, MarketWatch, Cointelegraph, Reddit-Top
  TIER 3 (×0.5): blogs, unknown

Light vs Full mode:
  --light  → Google News (selected 4 + MACRO) + Reddit + ForexLive + CoinDesk + CryptoPanic
  --full   → Light + Finnhub general/forex + Investing.com + ZeroHedge + Cointelegraph + MarketWatch
            + Google News for ALL 12 master assets

Usage:
  python news_scout_v2.py                     # FULL mode (default)
  python news_scout_v2.py --light             # LIGHT mode (Monitor)
  python news_scout_v2.py --full              # FULL mode (Selector)
  python news_scout_v2.py --light --summarize # LIGHT + summary block
  python news_scout_v2.py XAUUSD BTC          # Specific assets only

Input:  data/selected_assets.json (light mode auto-detects 4 selected)
Output: data/news_feed.json
"""

import urllib.request
import json
import sys
import os
import time
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

# EET timezone — fixes UTC-vs-EET timestamp drift (2026-04-29)
EET = timezone(timedelta(hours=3))

# Drop articles older than this when bucketing (keeps news_feed.json focused on
# actionable signals; stale RSS items occasionally appear with weeks-old pub dates)
MAX_ARTICLE_AGE_HOURS = 48

# Windows console UTF-8 fix
if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ── Paths ─────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).parent.parent / "data"
NEWS_FILE = OUTPUT_DIR / "news_feed.json"
SELECTED_FILE = OUTPUT_DIR / "selected_assets.json"

from dotenv import load_dotenv
_project_root = Path(__file__).parent.parent.parent
env_path = _project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
# .env.local is gitignored — overrides .env for private keys
env_local = _project_root / ".env.local"
if env_local.exists():
    load_dotenv(env_local, override=True)

FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY', '')
CRYPTOPANIC_API_KEY = os.environ.get('CRYPTOPANIC_API_KEY', '')

# Common HTTP user agent — Reddit + Finnhub friendly
HTTP_UA = 'GoldTactic/3.0 (paper trading research; +https://github.com/aggelosChatziioannou/trading)'

# ── Asset coverage (all 12 master assets + MACRO) ─────────────────────────
GOOGLE_NEWS_QUERIES = {
    "EURUSD": "EURUSD+OR+%22EUR+USD%22+forex",
    "GBPUSD": "GBPUSD+OR+%22GBP+USD%22+forex",
    "USDJPY": "USDJPY+OR+%22USD+JPY%22+OR+yen+OR+BOJ",
    "AUDUSD": "AUDUSD+OR+%22AUD+USD%22+OR+%22Australian+dollar%22+OR+RBA",
    "XAUUSD": "gold+price+OR+XAUUSD+OR+%22gold+rally%22+OR+%22gold+futures%22",
    "NAS100": "nasdaq+OR+%22tech+stocks%22+OR+QQQ+OR+%22NASDAQ+100%22",
    "SPX500": "%22S%26P+500%22+OR+SPX+OR+SPY+OR+%22stock+market%22",
    "BTC": "bitcoin+OR+BTC+crypto",
    "ETH": "ethereum+OR+ETH+crypto+OR+%22ether+price%22",
    "SOL": "solana+OR+SOL+crypto",
    "XRP": "ripple+OR+XRP+crypto+OR+%22Ripple+SEC%22",
    "DXY": "%22dollar+index%22+OR+DXY+OR+%22US+dollar+strength%22",
    "MACRO": "federal+reserve+OR+ECB+OR+inflation+OR+interest+rate+OR+%22Fed+meeting%22",
}

ASSET_KEYWORDS = {
    "XAUUSD": ["gold", "xau", "xauusd", "precious metals", "safe haven", "bullion"],
    "NAS100": ["nasdaq", "nas100", "tech stocks", "qqq", "ndx", "nasdaq 100", "nasdaq-100"],
    "SPX500": ["s&p 500", "s&p500", "spx", "spy", "stock market", "sp500"],
    "EURUSD": ["eur/usd", "eurusd", "euro", "ecb", "lagarde", "eurozone"],
    "GBPUSD": ["gbp/usd", "gbpusd", "pound", "sterling", "boe", "bailey", "bank of england"],
    "USDJPY": ["usd/jpy", "usdjpy", "yen", "boj", "ueda", "japan rate", "bank of japan"],
    "AUDUSD": ["aud/usd", "audusd", "aussie", "rba", "australia rate", "reserve bank of australia"],
    "BTC": ["bitcoin", "btc", "satoshi"],
    "ETH": ["ethereum", "eth", "ether", "vitalik"],
    "SOL": ["solana", "sol "],  # space avoids false hits in "solar" etc
    "XRP": ["ripple", "xrp"],
    "DXY": ["dollar index", "dxy", "usd strength", "greenback"],
    "MACRO": ["fed", "fomc", "interest rate", "inflation", "cpi", "pce", "geopolitical",
              "war", "powell", "yellen", "treasury yield", "jobs report", "nfp", "payrolls"],
}

# ── Source quality tiers ──────────────────────────────────────────────────
SOURCE_TIER_1 = {
    "reuters", "bloomberg", "forexlive", "coindesk", "wsj", "wall street journal",
    "financial times", "ft.com", "ft", "cnbc", "associated press", "ap", "the block",
}
SOURCE_TIER_2 = {
    "yahoo finance", "investing.com", "investing", "forex.com", "marketwatch",
    "barrons", "cointelegraph", "decrypt", "reddit", "fxstreet", "dailyfx",
    "kitco", "zerohedge",
}
TIER_WEIGHT = {1: 1.5, 2: 1.0, 3: 0.5}

def tier_for_source(source_name: str) -> int:
    s = (source_name or "").lower().strip()
    for t1 in SOURCE_TIER_1:
        if t1 in s:
            return 1
    for t2 in SOURCE_TIER_2:
        if t2 in s:
            return 2
    return 3

# ── Generic RSS feeds (non-Reddit, non-Google) ────────────────────────────
RSS_FEEDS = {
    "forexlive": {
        "url": "https://www.forexlive.com/feed/news",
        "source_name": "ForexLive",
        "applies_to": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "XAUUSD", "DXY", "MACRO"],
        "tier": "light",  # included in --light
    },
    "investing_econ": {
        "url": "https://www.investing.com/rss/news_25.rss",
        "source_name": "Investing.com",
        "applies_to": ["MACRO", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "DXY", "SPX500", "NAS100"],
        "tier": "full",
    },
    "investing_forex": {
        "url": "https://www.investing.com/rss/news_1.rss",
        "source_name": "Investing.com",
        "applies_to": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "DXY"],
        "tier": "full",
    },
    "zerohedge": {
        "url": "https://feeds.feedburner.com/zerohedge/feed",
        "source_name": "ZeroHedge",
        "applies_to": ["MACRO", "DXY", "SPX500", "XAUUSD"],
        "tier": "full",
    },
    "coindesk": {
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "source_name": "CoinDesk",
        "applies_to": ["BTC", "ETH", "SOL", "XRP"],
        "tier": "light",
    },
    "cointelegraph": {
        "url": "https://cointelegraph.com/rss",
        "source_name": "Cointelegraph",
        "applies_to": ["BTC", "ETH", "SOL", "XRP"],
        "tier": "full",
    },
    "marketwatch_top": {
        "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "source_name": "MarketWatch",
        "applies_to": ["SPX500", "NAS100", "MACRO"],
        "tier": "full",
    },
}

# ── Reddit feeds (Atom RSS — free, public) ────────────────────────────────
REDDIT_FEEDS = {
    "r/Forex": {
        "url": "https://www.reddit.com/r/Forex/top/.rss?t=hour&limit=15",
        "applies_to": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "XAUUSD", "DXY"],
        "tier": "light",
    },
    "r/CryptoCurrency": {
        "url": "https://www.reddit.com/r/CryptoCurrency/top/.rss?t=hour&limit=15",
        "applies_to": ["BTC", "ETH", "SOL", "XRP"],
        "tier": "light",
    },
    "r/Bitcoin": {
        "url": "https://www.reddit.com/r/Bitcoin/top/.rss?t=hour&limit=10",
        "applies_to": ["BTC"],
        "tier": "full",
    },
    "r/wallstreetbets": {
        "url": "https://www.reddit.com/r/wallstreetbets/top/.rss?t=hour&limit=10",
        "applies_to": ["NAS100", "SPX500", "MACRO"],
        "tier": "full",
    },
}

ATOM_NS = {'a': 'http://www.w3.org/2005/Atom'}


# ── Time normalization (unified across all sources) ───────────────────────
def _normalize_publish_time(raw):
    """
    Convert any RSS/JSON publication time to a unified set of fields.

    Accepts:
      - int/float epoch seconds
      - str ISO-8601 ('2026-04-30T12:34:00Z' / '+00:00')
      - str RFC-2822 / RSS pubDate ('Wed, 30 Apr 2026 12:34:00 GMT')
      - str truncated ('2026-04-30 12:34', '2026-04-30T12:34')
      - empty/None

    Returns dict with:
      epoch            int — UTC seconds since epoch (0 if unparsable)
      published_label  str — '30/04 14:30 EET' (local EET, no year)
      age_minutes      int — minutes since publication (999999 if unparsable)
      age_human        str — Greek short label: 'τώρα', '5λ πριν', '2ω πριν', '1μ πριν'
    """
    dt_utc = None

    # Numeric epoch
    if isinstance(raw, (int, float)) and raw > 0:
        try:
            dt_utc = datetime.fromtimestamp(raw, tz=timezone.utc)
        except Exception:
            dt_utc = None

    # String parsing — try several formats
    if dt_utc is None and isinstance(raw, str) and raw.strip():
        s = raw.strip()
        # Try RFC-2822 / RSS pubDate first
        try:
            dt = parsedate_to_datetime(s)
            if dt is not None:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dt_utc = dt.astimezone(timezone.utc)
        except Exception:
            pass
        # Try ISO-8601
        if dt_utc is None:
            iso_candidate = s.replace("Z", "+00:00").replace("T", " ")
            try:
                dt = datetime.fromisoformat(iso_candidate[:25])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dt_utc = dt.astimezone(timezone.utc)
            except Exception:
                pass
        # Truncated forms (last resort)
        if dt_utc is None:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
                try:
                    dt = datetime.strptime(s[:len(fmt) + 4], fmt)
                    dt_utc = dt.replace(tzinfo=timezone.utc)
                    break
                except Exception:
                    continue

    if dt_utc is None:
        return {"epoch": 0, "published_label": "", "age_minutes": 999999, "age_human": "?"}

    epoch = int(dt_utc.timestamp())
    eet_label = dt_utc.astimezone(EET).strftime("%d/%m %H:%M EET")
    age_min = max(0, int((datetime.now(timezone.utc) - dt_utc).total_seconds() / 60))

    if age_min < 2:
        age_human = "τώρα"
    elif age_min < 60:
        age_human = f"{age_min}λ πριν"
    elif age_min < 24 * 60:
        age_human = f"{age_min // 60}ω πριν"
    elif age_min < 7 * 24 * 60:
        age_human = f"{age_min // (24 * 60)}μ πριν"
    else:
        age_human = f"{age_min // (7 * 24 * 60)}ε πριν"

    return {
        "epoch": epoch,
        "published_label": eet_label,
        "age_minutes": age_min,
        "age_human": age_human,
    }


# ── HTTP helpers ──────────────────────────────────────────────────────────
def fetch_json(url, timeout=15):
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', HTTP_UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  [WARN] Fetch JSON failed {url[:60]}: {e}")
        return None


def fetch_rss_xml(url, timeout=12):
    try:
        req = urllib.request.Request(url)
        # Some RSS providers (Reddit, Mediastack) reject unknown UAs — Mozilla works broadly
        req.add_header('User-Agent', HTTP_UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  [WARN] Fetch RSS failed {url[:60]}: {e}")
        return None


# ── Source polling log (transparency for Telegram footer) ─────────────────
SOURCES_POLLED = []  # reset at start of each scout()

def _log_source(name: str, tier: int, ok: bool, items: int = 0, error: str = ""):
    SOURCES_POLLED.append({
        "name": name,
        "tier": tier,
        "ok": ok,
        "items_returned": items,
        "error": error[:80] if error else "",
    })


# ── Source 1: Finnhub ─────────────────────────────────────────────────────
def fetch_finnhub(category="general", max_items=20):
    if not FINNHUB_API_KEY:
        _log_source(f"Finnhub-{category}", 1, False, 0, "no API key")
        return []
    items = []
    try:
        data = fetch_json(
            f"https://finnhub.io/api/v1/news?category={category}&token={FINNHUB_API_KEY}"
        )
    except Exception as e:
        _log_source(f"Finnhub-{category}", 1, False, 0, str(e))
        return []
    if not data:
        _log_source(f"Finnhub-{category}", 1, False, 0, "empty/timeout")
        return items
    now = time.time()
    for article in data[:50]:
        pub_time = article.get("datetime", 0)
        if now - pub_time > 86400:  # > 24h old
            continue
        time_info = _normalize_publish_time(pub_time)
        items.append({
            "headline": article.get("headline", ""),
            "summary": article.get("summary", "")[:200],
            "source": article.get("source", "Finnhub"),
            "url": article.get("url", ""),
            "datetime": time_info["published_label"],
            "timestamp": pub_time,
            **time_info,
        })
    _log_source(f"Finnhub-{category}", 1, True, len(items))
    return items[:max_items]


# ── Source 2: CryptoPanic ─────────────────────────────────────────────────
def fetch_cryptopanic(currencies="BTC,ETH,SOL,XRP", max_items=10):
    if not CRYPTOPANIC_API_KEY:
        _log_source("CryptoPanic", 2, False, 0, "no API key")
        return []
    data = fetch_json(
        f"https://cryptopanic.com/api/v1/posts/"
        f"?auth_token={CRYPTOPANIC_API_KEY}&currencies={currencies}&kind=news"
    )
    if not data or "results" not in data:
        _log_source("CryptoPanic", 2, False, 0, "empty response")
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
        time_info = _normalize_publish_time(post.get("published_at", ""))
        items.append({
            "headline": post.get("title", ""),
            "summary": "",
            "source": post.get("source", {}).get("title", "CryptoPanic"),
            "url": post.get("url", ""),
            "datetime": time_info["published_label"],
            "timestamp": time_info["epoch"],
            "sentiment": sentiment,
            "currencies": [c["code"] for c in post.get("currencies", [])],
            **time_info,
        })
    _log_source("CryptoPanic", 2, True, len(items))
    return items


# ── Source 3: Google News RSS ─────────────────────────────────────────────
def fetch_google_news_rss(query_key, max_items=3):
    query = GOOGLE_NEWS_QUERIES.get(query_key, query_key)
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    xml_text = fetch_rss_xml(url)
    src_name = f"GoogleNews-{query_key}"
    if not xml_text:
        _log_source(src_name, 2, False, 0, "fetch failed")
        return []
    items = []
    try:
        root = ET.fromstring(xml_text)
        for item in root.findall('.//item')[:max_items]:
            title = (item.findtext('title') or '').strip()
            link = (item.findtext('link') or '').strip()
            pub_date = (item.findtext('pubDate') or '').strip()
            source = (item.findtext('source') or '').strip()
            time_info = _normalize_publish_time(pub_date)
            items.append({
                "headline": title,
                "summary": "",
                "source": source if source else "Google News",
                "url": link,
                "datetime": time_info["published_label"],
                "timestamp": time_info["epoch"],
                **time_info,
            })
        _log_source(src_name, 2, True, len(items))
    except Exception as e:
        print(f"  [WARN] Google News RSS parse error ({query_key}): {e}")
        _log_source(src_name, 2, False, 0, str(e))
    return items


# ── Source 4: Generic RSS feeds (ForexLive, Investing, ZeroHedge, etc) ────
def fetch_generic_rss(feed_key, max_items=10):
    cfg = RSS_FEEDS.get(feed_key)
    if not cfg:
        return []
    src_tier = tier_for_source(cfg["source_name"])
    xml_text = fetch_rss_xml(cfg["url"])
    if not xml_text:
        _log_source(cfg["source_name"], src_tier, False, 0, "fetch failed")
        return []
    items = []
    try:
        root = ET.fromstring(xml_text)
        # Standard RSS 2.0
        for item in root.findall('.//item')[:max_items]:
            title = (item.findtext('title') or '').strip()
            link = (item.findtext('link') or '').strip()
            desc = (item.findtext('description') or '').strip()
            # Strip HTML tags from description
            desc = re.sub(r'<[^>]+>', '', desc)[:200]
            pub_date = (item.findtext('pubDate') or '').strip()
            time_info = _normalize_publish_time(pub_date)
            items.append({
                "headline": title,
                "summary": desc,
                "source": cfg["source_name"],
                "url": link,
                "datetime": time_info["published_label"],
                "timestamp": time_info["epoch"],
                **time_info,
            })
        _log_source(cfg["source_name"], src_tier, True, len(items))
    except Exception as e:
        print(f"  [WARN] Generic RSS parse error ({feed_key}): {e}")
        _log_source(cfg["source_name"], src_tier, False, 0, str(e))
    return items


# ── Source 5: Reddit Atom feeds ───────────────────────────────────────────
def fetch_reddit_atom(feed_key, max_items=10):
    cfg = REDDIT_FEEDS.get(feed_key)
    if not cfg:
        return []
    src_name = f"Reddit-{feed_key}"
    xml_text = fetch_rss_xml(cfg["url"])
    if not xml_text:
        _log_source(src_name, 2, False, 0, "fetch failed")
        return []
    items = []
    try:
        root = ET.fromstring(xml_text)
        for entry in root.findall('a:entry', ATOM_NS)[:max_items]:
            title = (entry.findtext('a:title', default='', namespaces=ATOM_NS) or '').strip()
            link_el = entry.find('a:link', ATOM_NS)
            href = link_el.get('href', '') if link_el is not None else ''
            updated = (entry.findtext('a:updated', default='', namespaces=ATOM_NS) or '').strip()
            published = (entry.findtext('a:published', default='', namespaces=ATOM_NS) or '').strip()
            # Reddit Atom feeds expose both <published> (when posted) and <updated> (last edit).
            # Prefer <published> because that's what users see as the timestamp on the post.
            chosen = published or updated
            author_el = entry.find('a:author/a:name', ATOM_NS)
            author = author_el.text if author_el is not None else ''
            time_info = _normalize_publish_time(chosen)
            items.append({
                "headline": title,
                "summary": f"posted by {author}" if author else "",
                "source": src_name,
                "url": href,
                "datetime": time_info["published_label"],
                "timestamp": time_info["epoch"],
                **time_info,
            })
        _log_source(src_name, 2, True, len(items))
    except Exception as e:
        print(f"  [WARN] Reddit RSS parse error ({feed_key}): {e}")
        _log_source(src_name, 2, False, 0, str(e))
    return items


# ── Asset matching + tier scoring ─────────────────────────────────────────
def matches_asset(article, asset_key) -> bool:
    """Return True if article text matches asset keywords."""
    keywords = ASSET_KEYWORDS.get(asset_key, [])
    if not keywords:
        return False
    text = (article.get("headline", "") + " " + article.get("summary", "")).lower()
    return any(kw in text for kw in keywords)


def annotate_article(article: dict) -> dict:
    """Add tier + relevance score in-place."""
    src = article.get("source", "")
    article["tier"] = tier_for_source(src)
    article["weight"] = TIER_WEIGHT[article["tier"]]
    return article


def dedupe_articles(articles: list) -> list:
    """Remove near-duplicates by first-50-chars normalized."""
    seen = set()
    out = []
    for a in articles:
        h = (a.get("headline") or "").lower().strip()
        # Strip non-alphanumeric for fuzzy match
        key = re.sub(r'[^a-z0-9]', '', h)[:50]
        if key and key not in seen:
            seen.add(key)
            out.append(a)
    return out


# ── Selected assets helper ────────────────────────────────────────────────
def get_selected_assets() -> list:
    if not SELECTED_FILE.exists():
        return []
    try:
        data = json.loads(SELECTED_FILE.read_text(encoding='utf-8'))
        return [item.get("symbol") for item in data.get("selected", []) if item.get("symbol")]
    except Exception:
        return []


# ── Main orchestration ────────────────────────────────────────────────────
def _bucket(result: dict, asset: str, articles: list, max_per_asset=5):
    """Add articles to result['assets'][asset] with annotation, dedupe, freshness filter.

    Sorting policy: tier weight DESC (Tier 1 first), then epoch DESC (newest first
    within same tier). This guarantees a Reuters article from 2h ago beats a
    Reddit post from 30m ago, but if you have two Reuters articles from today the
    fresher one is shown first.
    """
    if not articles:
        return
    existing = result["assets"].get(asset, {"news": [], "count": 0, "filtered_stale": 0})
    stale_dropped = existing.get("filtered_stale", 0)
    cutoff_min = MAX_ARTICLE_AGE_HOURS * 60
    for a in articles:
        annotate_article(a)
        # Freshness filter — drop anything older than cutoff (RSS feeds occasionally
        # surface weeks-old archive items).
        if a.get("age_minutes", 0) > cutoff_min:
            stale_dropped += 1
            continue
        existing["news"].append(a)
    # Dedupe BEFORE sort so we don't waste sort cycles on duplicates
    existing["news"] = dedupe_articles(existing["news"])
    # Primary key: tier weight desc · Secondary: epoch desc (newest within tier)
    existing["news"].sort(
        key=lambda x: (-x.get("weight", 0.5), -x.get("epoch", 0))
    )
    existing["news"] = existing["news"][:max_per_asset]
    existing["count"] = len(existing["news"])
    existing["filtered_stale"] = stale_dropped
    result["assets"][asset] = existing


def scout(mode: str = "full", asset_filter=None) -> dict:
    """
    Unified scout. mode = 'light' or 'full'.
    """
    global SOURCES_POLLED
    SOURCES_POLLED = []  # reset at start
    print(f"News Scout v3 — {mode.upper()} mode")
    is_light = (mode == "light")

    # Determine asset scope
    if asset_filter:
        target_assets = list(asset_filter)
    elif is_light:
        # Light: 4 selected + MACRO (fallback to default 4 if no selection)
        selected = get_selected_assets()
        if selected:
            target_assets = selected + ["MACRO"]
            print(f"  Light mode: using selected assets {selected} + MACRO")
        else:
            target_assets = ["EURUSD", "XAUUSD", "BTC", "MACRO"]
            print(f"  Light mode: no selected_assets.json — fallback to {target_assets}")
    else:
        # Full: all 12 assets + MACRO
        target_assets = list(GOOGLE_NEWS_QUERIES.keys())
        print(f"  Full mode: scanning all {len(target_assets)} assets")

    result = {
        "timestamp": datetime.now(EET).strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "target_assets": target_assets,
        "assets": {},
    }

    # ── 1. Google News RSS (per-asset query) ──────────────────────────────
    for asset in target_assets:
        if asset in GOOGLE_NEWS_QUERIES:
            print(f"  Google News: {asset}...")
            articles = fetch_google_news_rss(asset, max_items=3)
            _bucket(result, asset, articles)
            time.sleep(0.3)  # be polite

    # ── 2. ForexLive RSS (always — light + full) ──────────────────────────
    print("  ForexLive RSS...")
    forexlive = fetch_generic_rss("forexlive", max_items=15)
    for asset in target_assets:
        matched = [a for a in forexlive if matches_asset(a, asset)]
        _bucket(result, asset, matched)

    # ── 3. CoinDesk RSS (light + full — for crypto) ───────────────────────
    crypto_target = [a for a in target_assets if a in ("BTC", "ETH", "SOL", "XRP")]
    if crypto_target:
        print("  CoinDesk RSS...")
        coindesk = fetch_generic_rss("coindesk", max_items=15)
        for asset in crypto_target:
            matched = [a for a in coindesk if matches_asset(a, asset)]
            _bucket(result, asset, matched)

    # ── 4. Reddit (light + full) ──────────────────────────────────────────
    for sub_key, sub_cfg in REDDIT_FEEDS.items():
        if is_light and sub_cfg.get("tier") == "full":
            continue
        relevant = set(sub_cfg["applies_to"]) & set(target_assets)
        if not relevant:
            continue
        print(f"  Reddit: {sub_key}...")
        posts = fetch_reddit_atom(sub_key, max_items=10)
        for asset in relevant:
            matched = [a for a in posts if matches_asset(a, asset)]
            _bucket(result, asset, matched)
        time.sleep(0.3)

    # ── 5. CryptoPanic (light + full if key exists) ───────────────────────
    if crypto_target and CRYPTOPANIC_API_KEY:
        print("  CryptoPanic...")
        cp_news = fetch_cryptopanic(",".join(crypto_target), max_items=10)
        for item in cp_news:
            for curr in item.get("currencies", []):
                if curr in target_assets:
                    _bucket(result, curr, [item])

    # ── 6. FULL-only sources ──────────────────────────────────────────────
    if not is_light:
        # Finnhub
        print("  Finnhub general...")
        finnhub_general = fetch_finnhub("general")
        time.sleep(1)
        print("  Finnhub forex...")
        finnhub_forex = fetch_finnhub("forex")
        all_finnhub = finnhub_general + finnhub_forex
        for asset in target_assets:
            matched = [a for a in all_finnhub if matches_asset(a, asset)]
            _bucket(result, asset, matched)

        # Investing.com — economic + forex
        print("  Investing.com economic...")
        inv_econ = fetch_generic_rss("investing_econ", max_items=15)
        for asset in target_assets:
            matched = [a for a in inv_econ if matches_asset(a, asset)]
            _bucket(result, asset, matched)

        print("  Investing.com forex...")
        inv_forex = fetch_generic_rss("investing_forex", max_items=15)
        for asset in target_assets:
            matched = [a for a in inv_forex if matches_asset(a, asset)]
            _bucket(result, asset, matched)

        # ZeroHedge
        print("  ZeroHedge...")
        zh = fetch_generic_rss("zerohedge", max_items=10)
        for asset in target_assets:
            if asset in RSS_FEEDS["zerohedge"]["applies_to"]:
                matched = [a for a in zh if matches_asset(a, asset)]
                _bucket(result, asset, matched)

        # Cointelegraph
        if crypto_target:
            print("  Cointelegraph...")
            ct = fetch_generic_rss("cointelegraph", max_items=15)
            for asset in crypto_target:
                matched = [a for a in ct if matches_asset(a, asset)]
                _bucket(result, asset, matched)

        # MarketWatch
        if any(a in target_assets for a in ("SPX500", "NAS100", "MACRO")):
            print("  MarketWatch...")
            mw = fetch_generic_rss("marketwatch_top", max_items=15)
            for asset in ("SPX500", "NAS100", "MACRO"):
                if asset in target_assets:
                    matched = [a for a in mw if matches_asset(a, asset)]
                    _bucket(result, asset, matched)

    # ── Final stats ───────────────────────────────────────────────────────
    result["total_articles"] = sum(a["count"] for a in result["assets"].values())
    result["filtered_stale_total"] = sum(
        a.get("filtered_stale", 0) for a in result["assets"].values()
    )
    result["max_article_age_hours"] = MAX_ARTICLE_AGE_HOURS
    # Tier coverage stats
    tier_counts = {1: 0, 2: 0, 3: 0}
    for asset_data in result["assets"].values():
        for art in asset_data.get("news", []):
            tier_counts[art.get("tier", 3)] = tier_counts.get(art.get("tier", 3), 0) + 1
    result["tier_distribution"] = {
        "tier_1_premium": tier_counts[1],
        "tier_2_standard": tier_counts[2],
        "tier_3_other": tier_counts[3],
    }
    # Freshness snapshot — useful for prompt status footers
    all_ages = [
        art.get("age_minutes", 999999)
        for asset_data in result["assets"].values()
        for art in asset_data.get("news", [])
        if art.get("age_minutes", 999999) < 999999
    ]
    if all_ages:
        result["freshness"] = {
            "newest_minutes": min(all_ages),
            "oldest_minutes": max(all_ages),
            "median_minutes": sorted(all_ages)[len(all_ages) // 2],
            "fresh_under_1h": sum(1 for m in all_ages if m < 60),
            "fresh_under_6h": sum(1 for m in all_ages if m < 360),
        }
    else:
        result["freshness"] = {
            "newest_minutes": None, "oldest_minutes": None,
            "median_minutes": None, "fresh_under_1h": 0, "fresh_under_6h": 0,
        }

    # Sources polled — full transparency for Telegram footer
    result["sources_polled"] = list(SOURCES_POLLED)
    ok_count = sum(1 for s in SOURCES_POLLED if s["ok"])
    fail_count = len(SOURCES_POLLED) - ok_count
    result["sources_summary"] = {
        "total": len(SOURCES_POLLED),
        "ok": ok_count,
        "failed": fail_count,
        "ok_names": [s["name"] for s in SOURCES_POLLED if s["ok"]],
        "failed_names": [s["name"] for s in SOURCES_POLLED if not s["ok"]],
    }

    NEWS_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\nDone! {result['total_articles']} articles across {len(result['assets'])} assets.")
    print(f"Tier distribution: T1={tier_counts[1]} T2={tier_counts[2]} T3={tier_counts[3]}")
    print(f"Sources: {ok_count}/{len(SOURCES_POLLED)} ok ({fail_count} failed)")
    print(f"Saved to {NEWS_FILE}")
    return result


# Backward-compat wrappers (Monitor calls --light)
def scout_light(asset_filter=None):
    return scout("light", asset_filter)

def scout_full(asset_filter=None):
    return scout("full", asset_filter)


# ── News Summarization ────────────────────────────────────────────────────
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
    """Tier-weighted sentiment summary per asset."""
    summary = {}
    for asset_key, asset_data in result.get("assets", {}).items():
        articles = asset_data.get("news", [])
        if not articles:
            continue
        top_3 = articles[:3]
        summaries = []
        weighted_score = 0.0  # +1 bullish * weight, -1 bearish * weight
        sentiment_counts = {"bullish": 0, "bearish": 0, "neutral": 0}
        for article in top_3:
            headline = article.get("headline") or "?"
            sent = (article.get("sentiment") or "").lower()
            if sent not in ("bullish", "bearish"):
                sent = _detect_headline_sentiment(headline)
            weight = article.get("weight", 1.0)
            sentiment_counts[sent] = sentiment_counts.get(sent, 0) + 1
            if sent == "bullish":
                weighted_score += weight
            elif sent == "bearish":
                weighted_score -= weight
            summaries.append({
                "headline": headline[:120],
                "sentiment": sent,
                "tier": article.get("tier", 3),
                "source": article.get("source", "?"),
            })
        if weighted_score > 0.5:
            overall = "bullish"
        elif weighted_score < -0.5:
            overall = "bearish"
        else:
            overall = "neutral"
        summary[asset_key] = {
            "overall_sentiment": overall,
            "weighted_score": round(weighted_score, 2),
            "article_count": len(articles),
            "top_headlines": summaries,
        }
    return summary


# ── CLI entry ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    asset_filter = [a.upper() for a in args] if args else None
    do_summarize = "--summarize" in sys.argv
    mode = "light" if "--light" in sys.argv else "full"

    result = scout(mode, asset_filter)

    if do_summarize and result:
        summary = summarize_news(result)
        result["summary"] = summary
        NEWS_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"\nSummary ({len(summary)} assets):")
        for asset, info in summary.items():
            emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(info["overall_sentiment"], "?")
            print(f"  {emoji} {asset}: {info['overall_sentiment']} score={info['weighted_score']} ({info['article_count']} articles)")
            for h in info["top_headlines"]:
                print(f"      [T{h['tier']} {h['sentiment']}] {h['source']}: {h['headline'][:70]}")
