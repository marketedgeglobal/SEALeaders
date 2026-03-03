#!/usr/bin/env python3
"""Fetch Southeast Asia coastal news and write docs/data/latest.json."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import feedparser

from fetch_news_seasia import is_relevant

FEEDS = [
    {
        "name": "Google News SEA",
        "url": "https://news.google.com/rss/search?q=Southeast+Asia+marine",
    },
    {
        "name": "Google News ASEAN",
        "url": "https://news.google.com/rss/search?q=ASEAN+maritime",
    },
    {
        "name": "Google News Climate SEA",
        "url": "https://news.google.com/rss/search?q=Climate+Change+Southeast+Asia+coastal",
    },
    {
        "name": "Google News Fisheries SEA",
        "url": "https://news.google.com/rss/search?q=Sustainable+Fisheries+Southeast+Asia",
    },
    {
        "name": "Google News Blue Economy SEA",
        "url": "https://news.google.com/rss/search?q=Blue+Economy+Southeast+Asia",
    },
    {
        "name": "Google News Marine Pollution SEA",
        "url": "https://news.google.com/rss/search?q=Marine+Pollution+Southeast+Asia",
    },
    {
        "name": "SEAFDEC",
        "url": "https://www.seafdec.org/feed/",
    },
    {
        "name": "East Asia Forum",
        "url": "https://www.eastasiaforum.org/feed/",
    },
]

SECTORS = [
    "Sustainable Fisheries",
    "Climate Change",
    "Maritime Security",
    "Sustainable Blue Economy",
    "Marine Pollution",
]

SECTOR_KEYWORDS = {
    "Sustainable Fisheries": ["fisheries", "fishery", "fishing", "aquaculture", "fish stocks"],
    "Climate Change": ["climate", "sea level", "coastal erosion", "resilience", "extreme weather"],
    "Maritime Security": ["maritime", "security", "sovereignty", "navy", "patrol", "piracy", "south china sea"],
    "Sustainable Blue Economy": ["blue economy", "shipping", "ports", "coastal livelihoods", "ocean economy"],
    "Marine Pollution": ["marine pollution", "pollution", "plastic", "microplastic", "oil spill", "waste"],
}

MAX_ITEMS_PER_SECTOR = 8
OUTPUT_PATH = "docs/data/latest.json"


def _to_date_string(value: str) -> str:
    if not value:
        return ""
    try:
        dt = parsedate_to_datetime(value)
        return dt.date().isoformat()
    except Exception:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.date().isoformat()
        except Exception:
            return value[:10]


def _publisher_from_url(url: str) -> str:
    if not url:
        return "unknown"
    host = urlparse(url).netloc.lower()
    return host.replace("www.", "") or "unknown"


def _make_id(url: str, title: str) -> str:
    raw = f"{url}|{title}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:12]


def _categorize(title: str, summary: str = "") -> str | None:
    text = f"{title} {summary}".lower()
    for sector, keywords in SECTOR_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return sector
    return None


def _extract_items(feed_name: str, feed_url: str) -> list[dict]:
    parsed = feedparser.parse(feed_url)
    results: list[dict] = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        summary = (entry.get("summary") or "").strip()
        published = (entry.get("published") or entry.get("updated") or "").strip()

        if not title or not link:
            continue
        is_valid, _, _ = is_relevant(title, summary)
        if not is_valid:
            continue

        sector = _categorize(title, summary)
        if not sector:
            continue

        results.append(
            {
                "id": _make_id(link, title),
                "title": title,
                "url": link,
                "publisher": _publisher_from_url(link),
                "publishedAt": _to_date_string(published),
                "sourcePublishedAt": _to_date_string(published),
                "source": feed_name,
                "sector": sector,
                "snippet": summary[:280],
            }
        )
    return results


def build_latest_json() -> dict:
    all_items: list[dict] = []
    seen_urls: set[str] = set()

    for feed in FEEDS:
        print(f"Fetching {feed['name']} …")
        try:
            items = _extract_items(feed["name"], feed["url"])
        except Exception as exc:  # noqa: BLE001
            print(f"  [WARN] Failed: {type(exc).__name__}: {exc}")
            items = []

        for item in items:
            url = item["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            all_items.append(item)

    all_items.sort(key=lambda i: (i.get("publishedAt") or ""), reverse=True)

    sectors_payload = []
    total = 0
    for sector in SECTORS:
        sector_items = [item for item in all_items if item["sector"] == sector][:MAX_ITEMS_PER_SECTOR]
        total += len(sector_items)
        sectors_payload.append(
            {
                "name": sector,
                "items": sector_items,
            }
        )

    if total == 0:
        fallback = [
            {
                "name": "Sustainable Fisheries",
                "items": [
                    {
                        "id": "placeholder-fish",
                        "title": "ASEAN fisheries cooperation updates for coastal communities",
                        "url": "#",
                        "publisher": "placeholder",
                        "publishedAt": datetime.now(timezone.utc).date().isoformat(),
                        "sourcePublishedAt": datetime.now(timezone.utc).date().isoformat(),
                        "source": "Placeholder",
                        "sector": "Sustainable Fisheries",
                        "snippet": "Placeholder story shown because no live items passed filters.",
                    }
                ],
            },
            {
                "name": "Climate Change",
                "items": [
                    {
                        "id": "placeholder-climate",
                        "title": "Southeast Asia climate resilience planning for coastal zones",
                        "url": "#",
                        "publisher": "placeholder",
                        "publishedAt": datetime.now(timezone.utc).date().isoformat(),
                        "sourcePublishedAt": datetime.now(timezone.utc).date().isoformat(),
                        "source": "Placeholder",
                        "sector": "Climate Change",
                        "snippet": "Placeholder story shown because no live items passed filters.",
                    }
                ],
            },
            {
                "name": "Maritime Security",
                "items": [
                    {
                        "id": "placeholder-security",
                        "title": "Maritime Security coordination in Southeast Asia waters",
                        "url": "#",
                        "publisher": "placeholder",
                        "publishedAt": datetime.now(timezone.utc).date().isoformat(),
                        "sourcePublishedAt": datetime.now(timezone.utc).date().isoformat(),
                        "source": "Placeholder",
                        "sector": "Maritime Security",
                        "snippet": "Placeholder story shown because no live items passed filters.",
                    }
                ],
            },
            {
                "name": "Sustainable Blue Economy",
                "items": [
                    {
                        "id": "placeholder-blue",
                        "title": "Southeast Asia blue economy initiatives for grassroots groups",
                        "url": "#",
                        "publisher": "placeholder",
                        "publishedAt": datetime.now(timezone.utc).date().isoformat(),
                        "sourcePublishedAt": datetime.now(timezone.utc).date().isoformat(),
                        "source": "Placeholder",
                        "sector": "Sustainable Blue Economy",
                        "snippet": "Placeholder story shown because no live items passed filters.",
                    }
                ],
            },
            {
                "name": "Marine Pollution",
                "items": [
                    {
                        "id": "placeholder-pollution",
                        "title": "Marine Pollution response initiatives across ASEAN",
                        "url": "#",
                        "publisher": "placeholder",
                        "publishedAt": datetime.now(timezone.utc).date().isoformat(),
                        "sourcePublishedAt": datetime.now(timezone.utc).date().isoformat(),
                        "source": "Placeholder",
                        "sector": "Marine Pollution",
                        "snippet": "Placeholder story shown because no live items passed filters.",
                    }
                ],
            },
        ]

        return {
            "runAt": datetime.now(timezone.utc).isoformat(),
            "totalItems": 5,
            "sectors": fallback,
        }

    return {
        "runAt": datetime.now(timezone.utc).isoformat(),
        "totalItems": total,
        "sectors": sectors_payload,
    }


def main() -> None:
    payload = build_latest_json()
    output_path = Path(OUTPUT_PATH)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"Wrote {output_path} with {payload['totalItems']} items")


if __name__ == "__main__":
    main()
