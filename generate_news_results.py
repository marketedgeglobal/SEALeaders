#!/usr/bin/env python3

import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from fetch_news_seasia import is_relevant

FEEDS = [
    ("Google News SEA", "https://news.google.com/rss/search?q=Southeast+Asia+marine"),
    ("Google News ASEAN", "https://news.google.com/rss/search?q=ASEAN+maritime"),
    ("Google News Climate SEA", "https://news.google.com/rss/search?q=Climate+Change+Southeast+Asia+coastal"),
    ("Google News Fisheries SEA", "https://news.google.com/rss/search?q=Sustainable+Fisheries+Southeast+Asia"),
    ("Google News Blue Economy SEA", "https://news.google.com/rss/search?q=Blue+Economy+Southeast+Asia"),
    ("Google News Marine Pollution SEA", "https://news.google.com/rss/search?q=Marine+Pollution+Southeast+Asia"),
    ("SEAFDEC", "https://www.seafdec.org/feed/"),
    ("East Asia Forum", "https://www.eastasiaforum.org/feed/"),
]

CATEGORY_KEYWORDS = {
    "Sustainable Fisheries": [
        "fisheries",
        "fishery",
        "fishing",
        "aquaculture",
        "fish stocks",
    ],
    "Climate Change": [
        "climate",
        "sea level",
        "coastal erosion",
        "resilience",
        "extreme weather",
    ],
    "Maritime Security": [
        "maritime",
        "security",
        "sovereignty",
        "navy",
        "patrol",
        "piracy",
        "south china sea",
    ],
    "Sustainable Blue Economy": [
        "blue economy",
        "shipping",
        "ports",
        "coastal livelihoods",
        "ocean economy",
    ],
    "Marine Pollution": [
        "marine pollution",
        "pollution",
        "plastic",
        "microplastic",
        "oil spill",
        "waste",
    ],
}

MAX_PER_CATEGORY = 8


def _parse_datetime(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return raw.strip()


def _get_text(node: ET.Element, path: str) -> str:
    found = node.find(path)
    if found is None or found.text is None:
        return ""
    return found.text.strip()


def _first_text(node: ET.Element, paths: list[str]) -> str:
    for path in paths:
        text = _get_text(node, path)
        if text:
            return text
    return ""


def _fetch_xml(url: str) -> bytes | None:
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return response.read()
    except Exception:
        return None


def _parse_feed(xml_bytes: bytes, source_name: str) -> list[dict]:
    articles: list[dict] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return articles

    channel_items = root.findall("./channel/item")
    if channel_items:
        for item in channel_items:
            title = _first_text(item, ["title"])
            link = _first_text(item, ["link"])
            published = _first_text(item, ["pubDate"])
            if title and link:
                articles.append(
                    {
                        "title": title,
                        "url": link,
                        "source": source_name,
                        "published": _parse_datetime(published),
                    }
                )
        return articles

    atom_entries = root.findall("{http://www.w3.org/2005/Atom}entry")
    for entry in atom_entries:
        title = _first_text(entry, ["{http://www.w3.org/2005/Atom}title"])
        link = ""
        for link_node in entry.findall("{http://www.w3.org/2005/Atom}link"):
            href = link_node.attrib.get("href", "").strip()
            if href:
                link = href
                break
        published = _first_text(
            entry,
            [
                "{http://www.w3.org/2005/Atom}updated",
                "{http://www.w3.org/2005/Atom}published",
            ],
        )
        if title and link:
            articles.append(
                {
                    "title": title,
                    "url": link,
                    "source": source_name,
                    "published": _parse_datetime(published),
                }
            )

    return articles


def _categorize(title: str) -> str | None:
    lowered = title.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return None


def build_news_payload() -> dict:
    all_articles: list[dict] = []
    seen_urls: set[str] = set()

    for source_name, url in FEEDS:
        xml_bytes = _fetch_xml(url)
        if not xml_bytes:
            continue

        for article in _parse_feed(xml_bytes, source_name):
            headline = article.get("title", "")
            is_valid, _, _ = is_relevant(headline)
            if not is_valid:
                continue

            category = _categorize(headline)
            if not category:
                continue

            article_url = article.get("url", "")
            if not article_url or article_url in seen_urls:
                continue

            seen_urls.add(article_url)
            article["category"] = category
            all_articles.append(article)

    all_articles.sort(key=lambda item: item.get("published", ""), reverse=True)

    by_category: dict[str, list[dict]] = {name: [] for name in CATEGORY_KEYWORDS}
    for article in all_articles:
        category = article["category"]
        if len(by_category[category]) < MAX_PER_CATEGORY:
            by_category[category].append(article)

    total = sum(len(items) for items in by_category.values())

    if total == 0:
        fallback = {
            "Sustainable Fisheries": [
                {
                    "title": "ASEAN fisheries cooperation updates for coastal communities",
                    "url": "#",
                    "source": "Placeholder",
                    "published": "",
                    "category": "Sustainable Fisheries",
                }
            ],
            "Climate Change": [
                {
                    "title": "Southeast Asia climate resilience planning for coastal zones",
                    "url": "#",
                    "source": "Placeholder",
                    "published": "",
                    "category": "Climate Change",
                }
            ],
            "Maritime Security": [
                {
                    "title": "Maritime Security coordination in Southeast Asia waters",
                    "url": "#",
                    "source": "Placeholder",
                    "published": "",
                    "category": "Maritime Security",
                }
            ],
            "Sustainable Blue Economy": [
                {
                    "title": "Southeast Asia blue economy initiatives for grassroots groups",
                    "url": "#",
                    "source": "Placeholder",
                    "published": "",
                    "category": "Sustainable Blue Economy",
                }
            ],
            "Marine Pollution": [
                {
                    "title": "Marine Pollution response initiatives across ASEAN",
                    "url": "#",
                    "source": "Placeholder",
                    "published": "",
                    "category": "Marine Pollution",
                }
            ],
        }
        by_category = fallback
        total = 5

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_articles": total,
        "by_category": by_category,
    }


def main() -> None:
    payload = build_news_payload()
    output_path = Path("docs/news.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output_path} with {payload['total_articles']} articles")


if __name__ == "__main__":
    main()
