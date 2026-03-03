#!/usr/bin/env python3
"""Fetch Southeast Asia coastal news and write docs/data/latest.json."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import feedparser

from fetch_news_seasia import is_relevant

FEEDS = [
    {
        "name": "Channel News Asia - Asia",
        "url": "https://www.channelnewsasia.com/rssfeeds/8395986",
    },
    {
        "name": "The Straits Times - Asia",
        "url": "https://www.straitstimes.com/news/asia/rss.xml",
    },
    {
        "name": "BenarNews - English",
        "url": "https://www.benarnews.org/english/rss.xml",
    },
    {
        "name": "Mongabay",
        "url": "https://news.mongabay.com/feed/",
    },
    {
        "name": "East Asia Forum",
        "url": "https://www.eastasiaforum.org/feed/",
    },
    {
        "name": "SEAFDEC",
        "url": "https://www.seafdec.org/feed/",
    },
    {
        "name": "Maritime Executive",
        "url": "https://www.maritime-executive.com/rss",
    },
    {
        "name": "gCaptain",
        "url": "https://gcaptain.com/feed/",
    },
    {
        "name": "UN News Asia Pacific",
        "url": "https://news.un.org/feed/subscribe/en/news/region/asia-pacific/feed/rss.xml",
    },
    {
        "name": "UNEP - Oceans",
        "url": "https://www.unep.org/taxonomy/term/1/feed",
    },
    {
        "name": "FAO - Fisheries",
        "url": "https://www.fao.org/fishery/news/rss/en",
    },
    {
        "name": "ADB - News",
        "url": "https://www.adb.org/news/rss.xml",
    },
    {
        "name": "ReliefWeb - Asia Pacific",
        "url": "https://reliefweb.int/updates?advanced-search=%28PC385%29_%28T4596%29&search=%22Southeast%20Asia%22&format=rss",
    },
    {
        "name": "The Diplomat",
        "url": "https://thediplomat.com/feed/",
    },
    {
        "name": "Oceanographic Magazine",
        "url": "https://oceanographicmagazine.com/feed/",
    },
    {
        "name": "SeaNews",
        "url": "https://seanews.co.uk/feed/",
    },
    {
        "name": "VietnamPlus",
        "url": "https://en.vietnamplus.vn/rss/home.rss",
    },
    {
        "name": "ANTARA English",
        "url": "https://en.antaranews.com/rss/latest.xml",
    },
    {
        "name": "Bernama",
        "url": "https://www.bernama.com/en/rss.php",
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
    "Climate Change": [
        "climate",
        "sea level",
        "coastal erosion",
        "resilience",
        "extreme weather",
        "warming",
        "mitigation",
        "adaptation",
        "emission",
        "net zero",
        "flood",
        "drought",
        "typhoon",
        "cyclone",
        "storm surge",
    ],
    "Maritime Security": ["maritime", "security", "sovereignty", "navy", "patrol", "piracy", "south china sea"],
    "Sustainable Blue Economy": ["blue economy", "shipping", "ports", "coastal livelihoods", "ocean economy"],
    "Marine Pollution": [
        "marine pollution",
        "pollution",
        "plastic",
        "microplastic",
        "oil spill",
        "waste",
        "landfill",
        "sewage",
        "contamination",
        "toxic",
        "garbage",
        "wastewater",
    ],
}

MAX_ITEMS_PER_SECTOR = int(os.getenv("MAX_ITEMS_PER_SECTOR", "8"))
MAX_ITEMS_PER_PUBLISHER = int(os.getenv("MAX_ITEMS_PER_PUBLISHER", "3"))
OUTPUT_PATH = "docs/data/latest.json"
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
}

RESOLVED_URL_CACHE: dict[str, str] = {}
EXCERPT_CACHE: dict[str, str] = {}

REGIONAL_CONTEXT_FEEDS = {
    "Channel News Asia - Asia",
    "The Straits Times - Asia",
    "BenarNews - English",
    "Mongabay",
    "East Asia Forum",
    "SEAFDEC",
    "Maritime Executive",
    "gCaptain",
    "UN News Asia Pacific",
    "UNEP - Oceans",
    "FAO - Fisheries",
    "ADB - News",
    "ReliefWeb - Asia Pacific",
    "The Diplomat",
    "Oceanographic Magazine",
    "SeaNews",
    "VietnamPlus",
    "ANTARA English",
    "Bernama",
}

SEA_CONTEXT_MARKERS = (
    "southeast asia",
    "asean",
    "vietnam",
    "thailand",
    "philippines",
    "indonesia",
    "malaysia",
    "myanmar",
    "cambodia",
    "singapore",
    "brunei",
    "timor leste",
)

MARINE_CONTEXT_MARKERS = (
    "marine",
    "maritime",
    "ocean",
    "coastal",
    "climate",
    "adaptation",
    "mitigation",
    "sea level",
    "fisher",
    "fishery",
    "fishing",
    "aquaculture",
    "shipping",
    "port",
    "pollution",
    "plastic",
    "mangrove",
    "seagrass",
    "coral",
    "eez",
)


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


def _clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or " ")
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _publisher_from_url(url: str) -> str:
    if not url:
        return "unknown"
    host = urlparse(url).netloc.lower()
    return host.replace("www.", "") or "unknown"


def _is_google_host(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host.endswith("google.com") or host.endswith("news.google.com") or host.endswith("googleusercontent.com")


def _extract_links_from_summary(summary: str) -> list[str]:
    if not summary:
        return []

    raw = unescape(summary)
    links = re.findall(r"href=[\"'](https?://[^\"']+)[\"']", raw, flags=re.IGNORECASE)
    cleaned: list[str] = []
    for link in links:
        candidate = unescape(link).strip()
        if candidate and candidate not in cleaned:
            cleaned.append(candidate)
    return cleaned


def _resolve_google_news_url(url: str) -> str:
    if not url:
        return ""
    if url in RESOLVED_URL_CACHE:
        return RESOLVED_URL_CACHE[url]

    if not _is_google_host(url):
        RESOLVED_URL_CACHE[url] = url
        return url

    resolved = url
    try:
        request = Request(url, headers=HTTP_HEADERS)
        with urlopen(request, timeout=12) as response:
            resolved = response.geturl() or url
    except Exception:
        resolved = url

    RESOLVED_URL_CACHE[url] = resolved
    return resolved


def _resolve_verified_url(feed_url: str, summary: str) -> str:
    candidates = _extract_links_from_summary(summary)
    candidates.append(feed_url)

    for candidate in candidates:
        resolved = _resolve_google_news_url(candidate)
        if resolved and not _is_google_host(resolved):
            return resolved

    resolved_feed = _resolve_google_news_url(feed_url)
    return resolved_feed or feed_url


def _make_id(url: str, title: str) -> str:
    raw = f"{url}|{title}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:12]


def _categorize(title: str, summary: str = "") -> str | None:
    text = f"{title} {summary}".lower()
    best_sector = None
    best_score = 0

    for sector, keywords in SECTOR_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text)
        if score > best_score:
            best_sector = sector
            best_score = score

    return best_sector if best_score > 0 else None


def _clean_publisher(raw: str) -> str:
    text = re.sub(r"\s+", " ", (raw or "")).strip(" -|•\t\n\r")
    text = re.sub(r"^Google\s+News\s*[:\-]?\s*", "", text, flags=re.IGNORECASE)
    return text.strip() or ""


def _split_title_and_publisher(title: str, fallback_source: str) -> tuple[str, str]:
    raw_title = re.sub(r"\s+", " ", (title or "")).strip()
    if not raw_title:
        return "", _clean_publisher(fallback_source)

    if "google news" not in (fallback_source or "").lower():
        return raw_title, _clean_publisher(fallback_source)

    parts = [p.strip() for p in re.split(r"\s+-\s+", raw_title) if p.strip()]
    if len(parts) >= 2:
        candidate_publisher = _clean_publisher(parts[-1])
        if candidate_publisher and len(candidate_publisher) <= 80:
            clean_title = " - ".join(parts[:-1]).strip()
            if clean_title:
                return clean_title, candidate_publisher

    return raw_title, _clean_publisher(fallback_source)


def _normalize_for_compare(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _headline_fallback_summary(title: str) -> str:
    clean = re.sub(r"\s+", " ", (title or "")).strip(" .")
    if not clean:
        return ""

    clean = re.sub(r"^(opinion|analysis|explainer)\s*\|\s*", "", clean, flags=re.IGNORECASE)
    if ":" in clean:
        parts = [part.strip() for part in clean.split(":", 1)]
        if len(parts) == 2 and len(parts[1]) >= 20:
            clean = parts[1]

    if len(clean) < 24:
        return ""

    sentence = f"The report indicates that {clean}."
    sentence = sentence.replace("..", ".")
    return sentence[:280].rstrip()


def _best_snippet(summary: str, title: str, publisher: str = "", allow_fallback: bool = True) -> str:
    fallback = _headline_fallback_summary(title) if allow_fallback else ""
    cleaned = _clean_text(summary)
    if not cleaned:
        return fallback

    if len(cleaned) < 36 or len(cleaned.split()) < 5:
        return fallback

    if publisher and cleaned.lower() == publisher.lower():
        return fallback

    normalized_summary = _normalize_for_compare(cleaned)
    normalized_title = _normalize_for_compare(title)
    if normalized_summary and normalized_title and normalized_summary == normalized_title:
        return fallback

    if normalized_title and (normalized_summary in normalized_title or normalized_title in normalized_summary):
        return fallback

    if cleaned.lower().startswith(title.lower()):
        tail = cleaned[len(title):].strip(" .,-–—|")
        if tail and len(tail) >= 56 and (not publisher or tail.lower() != publisher.lower()):
            return tail
        return fallback

    return cleaned


def _extract_feed_summary_excerpt(summary_html: str) -> str:
    if not summary_html:
        return ""

    paragraphs = re.findall(r"<p[^>]*>([\s\S]*?)</p>", summary_html, flags=re.IGNORECASE)
    for paragraph in paragraphs[:4]:
        text = _clean_text(paragraph)
        if len(text) >= 56 and len(text.split()) >= 10:
            return text

    return _clean_text(summary_html)


def _extract_meta_description(html: str) -> str:
    patterns = [
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']',
        r'<meta[^>]+name=["\']twitter:description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:description["\']',
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            return _clean_text(match.group(1))
    return ""


def _extract_first_paragraph(html: str) -> str:
    cleaned_html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    cleaned_html = re.sub(r"<style[\s\S]*?</style>", " ", cleaned_html, flags=re.IGNORECASE)
    paragraphs = re.findall(r"<p[^>]*>([\s\S]*?)</p>", cleaned_html, flags=re.IGNORECASE)
    for paragraph in paragraphs[:12]:
        text = _clean_text(paragraph)
        if len(text) >= 90 and len(text.split()) >= 14:
            return text
    return ""


def _extract_article_excerpt(url: str, title: str, publisher: str) -> str:
    if not url or _is_google_host(url):
        return ""
    if url in EXCERPT_CACHE:
        return EXCERPT_CACHE[url]

    excerpt = ""
    try:
        request = Request(url, headers=HTTP_HEADERS)
        with urlopen(request, timeout=12) as response:
            payload = response.read(600_000)
            html = payload.decode("utf-8", errors="ignore")

        meta_description = _extract_meta_description(html)
        if meta_description:
            excerpt = meta_description
        else:
            excerpt = _extract_first_paragraph(html)
    except Exception:
        excerpt = ""

    excerpt = _best_snippet(excerpt, title, publisher, allow_fallback=False)
    EXCERPT_CACHE[url] = excerpt
    return excerpt


def _extract_items(feed_name: str, feed_url: str) -> list[dict]:
    parsed = feedparser.parse(feed_url)
    results: list[dict] = []
    for entry in parsed.entries:
        raw_title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        summary = (entry.get("summary") or entry.get("description") or "").strip()
        published = (entry.get("published") or entry.get("updated") or "").strip()
        title, publisher = _split_title_and_publisher(raw_title, feed_name)
        verified_url = _resolve_verified_url(link, summary)
        excerpt = _extract_article_excerpt(verified_url, title, publisher)
        feed_excerpt = _extract_feed_summary_excerpt(summary)
        snippet = excerpt or _best_snippet(feed_excerpt or summary, title, publisher)
        clean_publisher = publisher or _publisher_from_url(verified_url)

        if not title or not link:
            continue

        context_text = f"{title} {summary} {verified_url}".lower()
        has_marine_marker = any(marker in context_text for marker in MARINE_CONTEXT_MARKERS)
        if not has_marine_marker:
            continue

        sector = _categorize(title, summary)
        if not sector:
            continue

        is_valid, _, _ = is_relevant(title, summary)
        if not is_valid:
            has_sea_marker = any(marker in context_text for marker in SEA_CONTEXT_MARKERS)
            is_direct_context_match = feed_name in REGIONAL_CONTEXT_FEEDS and has_marine_marker
            if not (is_direct_context_match or has_sea_marker):
                continue

        results.append(
            {
                "id": _make_id(link, title),
                "title": title,
                "url": verified_url or link,
                "originalUrl": link,
                "verifiedUrl": verified_url or link,
                "publisher": clean_publisher,
                "publishedAt": _to_date_string(published),
                "sourcePublishedAt": _to_date_string(published),
                "source": feed_name,
                "sector": sector,
                "snippet": snippet[:320],
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
    publisher_usage: dict[str, int] = {}

    for sector in SECTORS:
        candidates = [item for item in all_items if item["sector"] == sector]
        selected: list[dict] = []

        for item in candidates:
            publisher = str(item.get("publisher") or "unknown").lower()
            if publisher_usage.get(publisher, 0) >= MAX_ITEMS_PER_PUBLISHER:
                continue

            selected.append(item)
            publisher_usage[publisher] = publisher_usage.get(publisher, 0) + 1
            if len(selected) >= MAX_ITEMS_PER_SECTOR:
                break

        if len(selected) < MAX_ITEMS_PER_SECTOR:
            for item in candidates:
                if item in selected:
                    continue
                selected.append(item)
                if len(selected) >= MAX_ITEMS_PER_SECTOR:
                    break

        total += len(selected)
        sectors_payload.append(
            {
                "name": sector,
                "items": selected,
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
