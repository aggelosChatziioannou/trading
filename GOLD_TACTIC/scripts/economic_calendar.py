#!/usr/bin/env python3
"""
GOLD TACTIC — Economic Calendar
Fetches events from ForexFactory XML + Central Bank RSS feeds.
Writes to data/economic_calendar.json.

Usage:
  python economic_calendar.py           # Fetch all
  python economic_calendar.py --json    # JSON to stdout
"""

import urllib.request
import json
import sys
import os
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
CALENDAR_FILE = OUTPUT_DIR / "economic_calendar.json"

CENTRAL_BANK_FEEDS = {
    "Fed": "https://www.federalreserve.gov/feeds/press_all.xml",
    "ECB": "https://www.ecb.europa.eu/rss/press.xml",
    "BoE": "https://www.bankofengland.co.uk/rss/news",
}

IMPACT_KEYWORDS = {
    "high": ["NFP", "Non-Farm", "CPI", "Interest Rate", "FOMC", "GDP", "PMI",
             "Retail Sales", "Unemployment", "ECB Press", "Fed Chair"],
    "medium": ["PPI", "Trade Balance", "Consumer Confidence", "Housing",
               "Industrial Production", "Durable Goods"],
}


def fetch_xml(url, timeout=15):
    """Fetch and parse XML from URL."""
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'GoldTactic/2.0')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  [WARN] Failed to fetch {url}: {e}")
        return None


def parse_forexfactory():
    """Parse ForexFactory weekly calendar XML."""
    events = []
    xml_text = fetch_xml("https://www.forexfactory.com/ffcal_week_this.xml")
    if not xml_text:
        return events

    try:
        root = ET.fromstring(xml_text)
        for event_el in root.findall('.//event'):
            title = event_el.findtext('title', '').strip()
            country = event_el.findtext('country', '').strip()
            date = event_el.findtext('date', '').strip()
            time_str = event_el.findtext('time', '').strip()
            impact = event_el.findtext('impact', '').strip()
            forecast = event_el.findtext('forecast', '').strip()
            previous = event_el.findtext('previous', '').strip()

            # Map impact
            impact_level = "LOW"
            if impact.lower() in ["high", "red"]:
                impact_level = "HIGH"
            elif impact.lower() in ["medium", "orange"]:
                impact_level = "MEDIUM"

            # Map currency to our assets
            affected = []
            if country in ["USD", "US"]:
                affected = ["EURUSD", "GBPUSD", "NAS100", "XAUUSD"]
            elif country in ["EUR", "EU"]:
                affected = ["EURUSD"]
            elif country in ["GBP", "GB"]:
                affected = ["GBPUSD"]

            events.append({
                "title": title,
                "country": country,
                "date": date,
                "time": time_str,
                "impact": impact_level,
                "forecast": forecast,
                "previous": previous,
                "affected_assets": affected,
                "source": "ForexFactory"
            })
    except Exception as e:
        print(f"  [WARN] ForexFactory parse error: {e}")

    return events


def parse_central_bank_rss(name, url):
    """Parse central bank RSS feed for recent announcements."""
    items = []
    xml_text = fetch_xml(url)
    if not xml_text:
        return items

    try:
        root = ET.fromstring(xml_text)
        # Standard RSS 2.0 format
        for item in root.findall('.//item')[:5]:  # Last 5 items only
            title = item.findtext('title', '').strip()
            link = item.findtext('link', '').strip()
            pub_date = item.findtext('pubDate', '').strip()
            description = item.findtext('description', '').strip()[:200]

            # Determine impact
            impact = "LOW"
            title_lower = title.lower()
            for kw in IMPACT_KEYWORDS["high"]:
                if kw.lower() in title_lower:
                    impact = "HIGH"
                    break
            if impact == "LOW":
                for kw in IMPACT_KEYWORDS["medium"]:
                    if kw.lower() in title_lower:
                        impact = "MEDIUM"
                        break

            items.append({
                "title": title,
                "url": link,
                "date": pub_date,
                "summary": description,
                "impact": impact,
                "source": name,
            })
    except Exception as e:
        print(f"  [WARN] {name} RSS parse error: {e}")

    return items


def fetch_all():
    """Fetch economic calendar + central bank news."""
    print("GOLD TACTIC — Economic Calendar")
    print(f"Fetching at {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # ForexFactory
    print("Fetching ForexFactory calendar...")
    ff_events = parse_forexfactory()
    print(f"  Got {len(ff_events)} events")

    # Central banks
    cb_items = {}
    for name, url in CENTRAL_BANK_FEEDS.items():
        print(f"Fetching {name} RSS...")
        items = parse_central_bank_rss(name, url)
        cb_items[name] = items
        print(f"  Got {len(items)} items")

    # Aggregate HIGH events from BOTH forexfactory + central_banks (FIX 2026-04-29)
    # Previously only ff_events were considered, so FOMC/ECB statements from RSS were missed.
    today_str = datetime.now().strftime("%Y-%m-%d")

    def _is_today_high(ev):
        if str(ev.get("impact", "")).upper() != "HIGH":
            return False
        date_field = ev.get("date") or ev.get("datetime") or ""
        if not date_field:
            return False
        # Try multiple formats: "Wed, 29 Apr 2026 18:00:00 GMT" / "2026-04-29 18:00:00" / ISO
        from email.utils import parsedate_to_datetime
        try:
            dt = parsedate_to_datetime(date_field)
            if dt:
                return dt.strftime("%Y-%m-%d") == today_str
        except Exception:
            pass
        try:
            if 'T' in date_field:
                s = date_field.replace('Z', '+00:00')
                from datetime import datetime as _dt
                return _dt.fromisoformat(s).strftime("%Y-%m-%d") == today_str
            if ' ' in date_field:
                from datetime import datetime as _dt
                return _dt.strptime(date_field[:10], "%Y-%m-%d").strftime("%Y-%m-%d") == today_str
        except Exception:
            pass
        return False

    high_today = [e for e in ff_events if _is_today_high(e)]
    for bank_name, items in cb_items.items():
        for ev in items:
            if _is_today_high(ev):
                # Tag the source so consumers know origin
                ev_copy = dict(ev)
                ev_copy["_source_bank"] = bank_name
                high_today.append(ev_copy)

    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "forexfactory_events": ff_events,
        "central_banks": cb_items,
        "high_impact_today": high_today,
        "high_impact_count": len(high_today),
    }

    CALENDAR_FILE.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8'
    )
    print(f"\nSaved to {CALENDAR_FILE}")
    return result


if __name__ == "__main__":
    result = fetch_all()
    if "--json" in sys.argv:
        print(json.dumps(result, indent=2, ensure_ascii=False))
