#!/usr/bin/env python3

import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
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
    ("Google News Vietnam Coastal", "https://news.google.com/rss/search?q=Vietnam+coastal+fisheries+climate"),
    ("Google News Thailand Coastal", "https://news.google.com/rss/search?q=Thailand+marine+pollution+coastal"),
    ("Google News Philippines Maritime", "https://news.google.com/rss/search?q=Philippines+maritime+security+fisheries"),
    ("Google News Indonesia Blue Economy", "https://news.google.com/rss/search?q=Indonesia+blue+economy+coastal"),
    ("Google News Malaysia Fisheries", "https://news.google.com/rss/search?q=Malaysia+fisheries+marine"),
    ("Google News Singapore Maritime", "https://news.google.com/rss/search?q=Singapore+maritime+security+ASEAN"),
    ("Google News Cambodia Mekong Coastal", "https://news.google.com/rss/search?q=Cambodia+coastal+fisheries+Mekong"),
    ("Google News Myanmar Coastal", "https://news.google.com/rss/search?q=Myanmar+coastal+marine+ASEAN"),
    ("Google News Brunei Blue Economy", "https://news.google.com/rss/search?q=Brunei+blue+economy+marine"),
    ("Mongabay", "https://news.mongabay.com/feed/"),
    ("UN News Asia Pacific", "https://news.un.org/feed/subscribe/en/news/region/asia-pacific/feed/rss.xml"),
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

MAX_PER_CATEGORY = int(os.getenv("MAX_PER_CATEGORY", "8"))


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


def _clean_snippet(raw: str) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 420:
        return text[:419].rstrip() + "…"
    return text


def _clean_publisher(raw: str) -> str:
    text = re.sub(r"\s+", " ", (raw or "")).strip(" -|•\t\n\r")
    text = re.sub(r"^Google\s+News\s*[:\-]?\s*", "", text, flags=re.IGNORECASE)
    return text.strip() or ""


def _split_title_and_publisher(title: str, fallback_source: str) -> tuple[str, str]:
    raw_title = re.sub(r"\s+", " ", (title or "")).strip()
    if not raw_title:
        return "", _clean_publisher(fallback_source)

    parts = [p.strip() for p in re.split(r"\s+-\s+", raw_title) if p.strip()]
    if len(parts) >= 2:
        candidate_publisher = _clean_publisher(parts[-1])
        if candidate_publisher and len(candidate_publisher) <= 80:
            clean_title = " - ".join(parts[:-1]).strip()
            if clean_title:
                return clean_title, candidate_publisher

    return raw_title, _clean_publisher(fallback_source)


def _derive_subtext(title: str) -> str:
    clean_title = re.sub(r"\s+", " ", (title or "")).strip(" .")
    if not clean_title:
        return ""

    if ":" in clean_title:
        lead, detail = [segment.strip() for segment in clean_title.split(":", 1)]
        if detail:
            return detail[0].upper() + detail[1:]
        return lead

    if ";" in clean_title:
        pieces = [p.strip() for p in clean_title.split(";") if p.strip()]
        if len(pieces) > 1:
            return pieces[1]

    words = clean_title.split()
    if len(words) > 10:
        return " ".join(words[6:18]).strip(" ,.")
    return clean_title


def _best_snippet(summary: str, title: str, publisher: str = "") -> str:
    cleaned_summary = _clean_snippet(summary)
    if not cleaned_summary:
        return _derive_subtext(title)

    words = cleaned_summary.split()
    if len(words) < 5 or len(cleaned_summary) < 36:
        return _derive_subtext(title)

    if publisher and cleaned_summary.lower() == publisher.lower():
        return _derive_subtext(title)

    normalized_summary = re.sub(r"\W+", "", cleaned_summary.lower())
    normalized_title = re.sub(r"\W+", "", title.lower())
    if normalized_summary and normalized_title and normalized_summary == normalized_title:
        return _derive_subtext(title)

    if cleaned_summary.lower().startswith(title.lower()):
        tail = cleaned_summary[len(title):].strip(" .,-–—|")
        if tail and len(tail) >= 36 and (not publisher or tail.lower() != publisher.lower()):
            return tail
        return _derive_subtext(title)

    return cleaned_summary


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
            raw_title = _first_text(item, ["title"])
            title, publisher = _split_title_and_publisher(raw_title, source_name)
            link = _first_text(item, ["link"])
            published = _first_text(item, ["pubDate"])
            summary = _first_text(item, ["description", "content"])
            if title and link:
                articles.append(
                    {
                        "title": title,
                        "url": link,
                        "source": source_name,
                        "publisher": publisher,
                        "published": _parse_datetime(published),
                        "snippet": _best_snippet(summary, title, publisher),
                    }
                )
        return articles

    atom_entries = root.findall("{http://www.w3.org/2005/Atom}entry")
    for entry in atom_entries:
        raw_title = _first_text(entry, ["{http://www.w3.org/2005/Atom}title"])
        title, publisher = _split_title_and_publisher(raw_title, source_name)
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
        summary = _first_text(
            entry,
            [
                "{http://www.w3.org/2005/Atom}summary",
                "{http://www.w3.org/2005/Atom}content",
            ],
        )
        if title and link:
            articles.append(
                {
                    "title": title,
                    "url": link,
                    "source": source_name,
                    "publisher": publisher,
                    "published": _parse_datetime(published),
                    "snippet": _best_snippet(summary, title, publisher),
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
            summary = article.get("snippet", "")
            is_valid, _, _ = is_relevant(headline, summary)
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


def _to_latest_payload(news_payload: dict) -> dict:
    by_category = news_payload.get("by_category") or {}
    sectors = []
    for name, items in by_category.items():
        sectors.append(
            {
                "name": name,
                "items": items if isinstance(items, list) else [],
            }
        )
    return {
        "runAt": news_payload.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "totalItems": int(news_payload.get("total_articles") or 0),
        "sectors": sectors,
    }


def main() -> None:
    payload = build_news_payload()

    news_path = Path("docs/news.json")
    news_path.parent.mkdir(parents=True, exist_ok=True)
    news_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    latest_path = Path("docs/data/latest.json")
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_payload = _to_latest_payload(payload)
    latest_path.write_text(json.dumps(latest_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {news_path} and {latest_path} with {payload['total_articles']} articles")


if __name__ == "__main__":
    main()
