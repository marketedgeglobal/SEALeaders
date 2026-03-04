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
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

import feedparser

from fetch_news_seasia import is_relevant

FEEDS = [
    {
        "name": "AP News ASEAN Hub",
        "url": "https://apnews.com/hub/association-of-southeast-asian-nations",
        "mode": "web",
    },
    {
        "name": "Channel News Asia - Asia",
        "url": "https://www.channelnewsasia.com/rssfeeds/8395986",
    },
    {
        "name": "The Straits Times - Asia",
        "url": "https://www.straitstimes.com/news/asia/rss.xml",
    },
    {
        "name": "The Straits Times - Global",
        "url": "https://www.straitstimes.com/global",
        "mode": "web",
    },
    {
        "name": "Bangkok Post",
        "url": "https://www.bangkokpost.com/rss/data/topstories.xml",
    },
    {
        "name": "Nation Thailand",
        "url": "https://www.nationthailand.com/",
        "mode": "web",
    },
    {
        "name": "BenarNews - English",
        "url": "https://www.benarnews.org/english/rss.xml",
    },
    {
        "name": "The Jakarta Post",
        "url": "https://www.thejakartapost.com/",
        "mode": "web",
    },
    {
        "name": "Rappler",
        "url": "https://www.rappler.com/rss/",
    },
    {
        "name": "Inquirer",
        "url": "https://newsinfo.inquirer.net/feed",
    },
    {
        "name": "Philstar",
        "url": "https://www.philstar.com/rss/headlines",
    },
    {
        "name": "Malay Mail",
        "url": "https://www.malaymail.com/feed/rss",
    },
    {
        "name": "The Star Malaysia",
        "url": "https://www.thestar.com.my/rss/news/nation/",
    },
    {
        "name": "Free Malaysia Today",
        "url": "https://www.freemalaysiatoday.com/category/nation/feed/",
    },
    {
        "name": "Mongabay",
        "url": "https://news.mongabay.com/feed/",
    },
    {
        "name": "Mongabay - Asia",
        "url": "https://news.mongabay.com/list/asia/",
        "mode": "web",
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
        "name": "IUCN - Asia",
        "url": "https://iucn.org/our-work/region/asia",
        "mode": "web",
    },
    {
        "name": "WWF Asia Pacific - Newsroom",
        "url": "https://asiapacific.panda.org/latest/newsroom/",
        "mode": "web",
    },
    {
        "name": "Mangrove Alliance - Newsroom",
        "url": "https://www.mangrovealliance.org/blog-feed.xml",
    },
    {
        "name": "Eco-Business - News",
        "url": "https://www.eco-business.com/feeds/news/",
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
        "name": "ANTARA Indonesia",
        "url": "https://www.antaranews.com/rss/terkini.xml",
    },
    {
        "name": "Tatoli",
        "url": "https://en.tatoli.tl/feed/",
    },
    {
        "name": "Myanmar Now",
        "url": "https://myanmar-now.org/en/feed/",
    },
    {
        "name": "VietnamPlus",
        "url": "https://en.vietnamplus.vn/rss/home.rss",
    },
    {
        "name": "VNExpress International",
        "url": "https://e.vnexpress.net/rss/news.rss",
    },
    {
        "name": "Vietnam News - Environment",
        "url": "https://vietnamnews.vn/rss/environment.rss",
    },
    {
        "name": "ISEAS Commentaries",
        "url": "https://www.iseas.edu.sg/category/commentaries/feed/",
    },
    {
        "name": "AMTI - CSIS",
        "url": "https://amti.csis.org/feed/",
    },
    {
        "name": "Stimson Center",
        "url": "https://www.stimson.org/feed/",
    },
    {
        "name": "WRI - Insights",
        "url": "https://www.wri.org/insights/rss.xml",
    },
    {
        "name": "Google News - ASEAN Fisheries",
        "url": "https://news.google.com/rss/search?q=ASEAN+fisheries+aquaculture+Southeast+Asia&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "name": "Google News - SEA Coastal Fisheries",
        "url": "https://news.google.com/rss/search?q=Southeast+Asia+coastal+fisheries+community&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "name": "Google News - SEA Seafood Trade",
        "url": "https://news.google.com/rss/search?q=Southeast+Asia+seafood+trade+fisheries&hl=en-US&gl=US&ceid=US:en",
    },
]

SECTORS = [
    "Blue Economy",
    "Climate Change",
    "Maritime Security",
    "Sustainable Fisheries",
    "Marine Pollution",
]

SECTOR_KEYWORDS = {
    "Sustainable Fisheries": [
        "fisheries",
        "fishery",
        "fishing",
        "aquaculture",
        "fish stocks",
        "fishers",
        "fisherfolk",
        "small-scale fishers",
        "seafood",
        "seafood trade",
        "fish landing",
        "fish catch",
        "fish market",
        "fish supply chain",
        "hatchery",
        "tuna",
        "shrimp",
        "illegal fishing",
        "iuu",
        "stock assessment",
    ],
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
    "Blue Economy": [
        "blue economy",
        "ocean economy",
        "coastal livelihoods",
        "investment",
        "finance",
        "trade",
        "exports",
        "value chain",
        "ecotourism",
        "circular economy",
        "innovation",
        "startup",
        "technology",
        "shipping",
        "ports",
        "plastic reduction",
        "waste reduction",
        "recycling",
        "resource efficiency",
    ],
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
        "sampah",
        "limbah",
    ],
}

MAX_ITEMS_PER_SECTOR = int(os.getenv("MAX_ITEMS_PER_SECTOR", "8"))
MAX_ITEMS_PER_PUBLISHER = int(os.getenv("MAX_ITEMS_PER_PUBLISHER", "3"))
MAX_ITEMS_PER_COUNTRY = int(os.getenv("MAX_ITEMS_PER_COUNTRY", "6"))
MAX_FEED_ENTRIES_PER_SOURCE = int(os.getenv("MAX_FEED_ENTRIES_PER_SOURCE", "36"))
ENABLE_ARTICLE_EXCERPT_FETCH = os.getenv("ENABLE_ARTICLE_EXCERPT_FETCH", "0") == "1"
ENABLE_URL_RESOLVE = os.getenv("ENABLE_URL_RESOLVE", "0") == "1"
OUTPUT_PATH = "docs/data/latest.json"
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
}

RESOLVED_URL_CACHE: dict[str, str] = {}
EXCERPT_CACHE: dict[str, str] = {}

REGIONAL_CONTEXT_FEEDS = {
    "Channel News Asia - Asia",
    "The Straits Times - Asia",
    "The Straits Times - Global",
    "BenarNews - English",
    "Mongabay",
    "Mongabay - Asia",
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
    "Tatoli",
    "Myanmar Now",
    "ANTARA Indonesia",
    "VietnamPlus",
    "VNExpress International",
    "Vietnam News - Environment",
    "Rappler",
    "Inquirer",
    "Philstar",
    "Malay Mail",
    "The Star Malaysia",
    "Free Malaysia Today",
    "Bangkok Post",
    "Nation Thailand",
    "The Jakarta Post",
    "AP News ASEAN Hub",
    "IUCN - Asia",
    "WWF Asia Pacific - Newsroom",
    "Mangrove Alliance - Newsroom",
    "Eco-Business - News",
    "ISEAS Commentaries",
    "AMTI - CSIS",
    "Stimson Center",
    "WRI - Insights",
    "Google News - ASEAN Fisheries",
    "Google News - SEA Coastal Fisheries",
    "Google News - SEA Seafood Trade",
}

SEA_CONTEXT_MARKERS = (
    "southeast asia",
    "asean",
    "asia pacific",
    "asia-pacific",
    "indo-pacific",
    "mekong",
    "south china sea",
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
    "perikanan",
    "nelayan",
    "laut",
    "pesisir",
    "maritim",
    "sampah",
    "limbah",
)

COASTAL_COMMUNITY_MARKERS = (
    "coastal",
    "community",
    "communities",
    "grassroots",
    "livelihood",
    "livelihoods",
    "small-scale",
    "fishers",
    "fisherfolk",
    "fisheries",
    "fishing",
    "aquaculture",
    "mangrove",
    "reef",
    "seagrass",
    "marine pollution",
    "plastic",
    "wastewater",
    "sea level",
    "erosion",
    "adaptation",
    "resilience",
    "island",
    "delta",
)

OUT_OF_SCOPE_GLOBAL_MARKERS = (
    "iran",
    "israel",
    "gaza",
    "tehran",
    "qom",
    "ukraine",
    "russia",
    "persian gulf",
    "middle east",
    "hormuz",
    "assembly of experts",
)

COUNTRY_HINTS = {
    "vietnam": ["vietnam", "vietnamplus.vn", "vnanet", "hanoi", "ho chi minh"],
    "thailand": ["thailand", "bangkok", "thai"],
    "philippines": ["philippines", "philippine", "manila"],
    "indonesia": ["indonesia", "jakarta"],
    "malaysia": ["malaysia", "kuala lumpur"],
    "myanmar": ["myanmar", "yangon", "burma"],
    "cambodia": ["cambodia", "phnom penh"],
    "singapore": ["singapore"],
    "brunei": ["brunei"],
}

FEED_COUNTRY_HINTS = {
    "Rappler": "philippines",
    "Inquirer": "philippines",
    "Philstar": "philippines",
    "Malay Mail": "malaysia",
    "The Star Malaysia": "malaysia",
    "Free Malaysia Today": "malaysia",
    "Bangkok Post": "thailand",
    "Nation Thailand": "thailand",
    "VietnamPlus": "vietnam",
    "VNExpress International": "vietnam",
    "Vietnam News - Environment": "vietnam",
    "Tatoli": "timor_leste",
    "Myanmar Now": "myanmar",
    "ANTARA Indonesia": "indonesia",
    "Channel News Asia - Asia": "singapore",
    "The Straits Times - Asia": "singapore",
    "The Straits Times - Global": "singapore",
    "The Jakarta Post": "indonesia",
    "Mongabay - Asia": "regional",
    "AP News ASEAN Hub": "regional",
    "IUCN - Asia": "regional",
    "WWF Asia Pacific - Newsroom": "regional",
    "Mangrove Alliance - Newsroom": "regional",
    "Eco-Business - News": "regional",
    "ISEAS Commentaries": "regional",
    "AMTI - CSIS": "regional",
    "Stimson Center": "regional",
    "WRI - Insights": "regional",
    "Google News - ASEAN Fisheries": "regional",
    "Google News - SEA Coastal Fisheries": "regional",
    "Google News - SEA Seafood Trade": "regional",
}

WEB_SOURCE_BLOCKLIST = (
    "/tag/",
    "/tags/",
    "/topic/",
    "/topics/",
    "/category/",
    "/categories/",
    "/author/",
    "/search",
    "/about",
    "/contact",
    "/privacy",
    "/terms",
    "/advert",
    "/subscribe",
    "/account",
)

MAX_WEB_ARTICLES_PER_SOURCE = int(os.getenv("MAX_WEB_ARTICLES_PER_SOURCE", "16"))

COUNTRY_PRIORITY_WEIGHT = {
    "indonesia": 3.0,
    "philippines": 3.0,
    "malaysia": 3.0,
    "vietnam": 2.0,
    "thailand": 2.0,
    "timor_leste": 2.0,
    "myanmar": 1.2,
    "singapore": 1.2,
    "brunei": 1.2,
    "cambodia": 1.0,
    "regional": 1.0,
}

COUNTRY_MAX_CAPS = {
    "vietnam": int(os.getenv("MAX_ITEMS_VIETNAM", "3")),
}

OPPORTUNITY_PORTALS = [
    {"id": "adb-proc", "title": "ADB Procurement Opportunities", "url": "https://www.adb.org/work-with-us/procurement", "source": "ADB", "country": "regional", "type": "Portal", "deadline": "Rolling / check notice"},
    {"id": "ungm-notices", "title": "UNGM Tender Notices", "url": "https://www.ungm.org/Public/Notice", "source": "UNGM", "country": "regional", "type": "Tender Portal", "deadline": "Varies by notice"},
    {"id": "undp-proc", "title": "UNDP Procurement Notices", "url": "https://procurement-notices.undp.org/", "source": "UNDP", "country": "regional", "type": "Solicitations", "deadline": "Varies by notice"},
    {"id": "worldbank-proc", "title": "World Bank Procurement", "url": "https://projects.worldbank.org/en/projects-operations/procurement", "source": "World Bank", "country": "regional", "type": "Procurement", "deadline": "Varies by notice"},
    {"id": "reliefweb-asia-updates", "title": "ReliefWeb Asia Updates", "url": "https://reliefweb.int/updates?advanced-search=%28PC385%29", "source": "ReliefWeb", "country": "regional", "type": "Funding/Calls", "deadline": "Varies by posting"},
    {"id": "reliefweb-asia-jobs", "title": "ReliefWeb Asia Jobs", "url": "https://reliefweb.int/jobs?advanced-search=%28PC385%29", "source": "ReliefWeb", "country": "regional", "type": "Consultancies/Jobs", "deadline": "Varies by posting"},
    {"id": "thaingo-board", "title": "ThaiNGO Network Opportunities", "url": "https://www.thaingo.org/", "source": "ThaiNGO", "country": "thailand", "type": "NGO Opportunities", "deadline": "Check latest posts"},
    {"id": "fundsforngos", "title": "FundsforNGOs Opportunities", "url": "https://www2.fundsforngos.org/", "source": "FundsforNGOs", "country": "regional", "type": "Grant Calls", "deadline": "Varies by call"},
    {"id": "devex-funding", "title": "Devex Funding Overview", "url": "https://www.devex.com/funding-overview", "source": "Devex", "country": "regional", "type": "Funding Tracker", "deadline": "Varies by call"},
    {"id": "vn-eproc", "title": "Vietnam e-Procurement Portal", "url": "https://muasamcong.mpi.gov.vn/", "source": "Government", "country": "vietnam", "type": "RFP/RFQ", "deadline": "Varies by tender"},
    {"id": "th-egp", "title": "Thailand e-GP", "url": "https://www.gprocurement.go.th/", "source": "Government", "country": "thailand", "type": "RFP/RFQ", "deadline": "Varies by tender"},
    {"id": "ph-philgeps", "title": "PhilGEPS Opportunities", "url": "https://notices.philgeps.gov.ph/", "source": "Government", "country": "philippines", "type": "Bids", "deadline": "Varies by bid"},
    {"id": "id-lpse", "title": "Indonesia LPSE e-Procurement", "url": "https://lpse.lkpp.go.id/eproc4", "source": "Government", "country": "indonesia", "type": "RFP/RFQ", "deadline": "Varies by tender"},
    {"id": "my-eperolehan", "title": "Malaysia ePerolehan", "url": "https://www.eperolehan.gov.my/", "source": "Government", "country": "malaysia", "type": "Tenders", "deadline": "Varies by tender"},
    {"id": "sg-gebiz", "title": "Singapore GeBIZ", "url": "https://www.gebiz.gov.sg/", "source": "Government", "country": "singapore", "type": "Quotations/Tenders", "deadline": "Varies by tender"},
]

OPPORTUNITY_SEARCH_COUNTRIES = [
    ("vietnam", "Vietnam"),
    ("thailand", "Thailand"),
    ("philippines", "Philippines"),
    ("indonesia", "Indonesia"),
    ("malaysia", "Malaysia"),
    ("myanmar", "Myanmar"),
    ("cambodia", "Cambodia"),
    ("singapore", "Singapore"),
    ("brunei", "Brunei"),
]


def _build_opportunity_searches() -> list[dict]:
    items: list[dict] = []
    for key, label in OPPORTUNITY_SEARCH_COUNTRIES:
        query = f"{label} coastal community marine fisheries climate adaptation RFP RFQ tender solicitation"
        encoded = re.sub(r"\s+", "+", query.strip())
        items.append(
            {
                "id": f"search-{key}",
                "title": f"{label}: Coastal & Marine RFP/RFQ Search",
                "url": f"https://www.google.com/search?q={encoded}",
                "source": "Search",
                "country": key,
                "type": "Live Search",
                "deadline": "Rolling",
            }
        )

    items.append(
        {
            "id": "search-regional",
            "title": "Southeast Asia: Coastal & Marine Opportunities",
            "url": "https://www.google.com/search?q=Southeast+Asia+coastal+marine+community+RFP+RFQ+tender+solicitation",
            "source": "Search",
            "country": "regional",
            "type": "Live Search",
            "deadline": "Rolling",
        }
    )
    return items


def _build_opportunities() -> list[dict]:
    opportunities = OPPORTUNITY_PORTALS + _build_opportunity_searches()
    normalized: list[dict] = []
    for item in opportunities:
        payload = dict(item)
        payload["deadline"] = str(payload.get("deadline") or "Check notice")
        normalized.append(payload)
    return normalized


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


def _fetch_url_bytes(url: str, max_bytes: int = 900_000) -> tuple[bytes, str]:
    request = Request(url, headers=HTTP_HEADERS)
    with urlopen(request, timeout=8) as response:
        payload = response.read(max_bytes)
        final_url = response.geturl() or url
    return payload, final_url


def _parse_feed(feed_url: str):
    try:
        payload, _ = _fetch_url_bytes(feed_url)
        parsed = feedparser.parse(payload)
        return parsed
    except Exception:
        return feedparser.parse(b"")


def _resolve_verified_url(feed_url: str, summary: str) -> str:
    candidates = _extract_links_from_summary(summary)
    candidates.append(feed_url)

    if not ENABLE_URL_RESOLVE:
        for candidate in candidates:
            candidate = (candidate or "").strip()
            if candidate and not _is_google_host(candidate):
                return candidate
        return feed_url

    for candidate in candidates:
        resolved = _resolve_google_news_url(candidate)
        if resolved and not _is_google_host(resolved):
            return resolved

    resolved_feed = _resolve_google_news_url(feed_url)
    return resolved_feed or feed_url


def _make_id(url: str, title: str) -> str:
    raw = f"{url}|{title}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:12]


def _canonical_story_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").rstrip("/")
    return f"{host}{path}"


def _title_fingerprint(title: str, published_at: str = "") -> str:
    normalized_title = re.sub(r"\s+", " ", (title or "").strip().lower())
    normalized_title = re.sub(r"[^a-z0-9 ]+", "", normalized_title)
    date_bucket = (published_at or "")[:10]
    return f"{normalized_title}|{date_bucket}"


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


def _extract_web_candidates(source_url: str, max_links: int = 20) -> list[tuple[str, str]]:
    try:
        payload, final_url = _fetch_url_bytes(source_url)
        html = payload.decode("utf-8", errors="ignore")
    except Exception:
        return []

    base_url = final_url or source_url
    base_host = urlparse(base_url).netloc.lower().replace("www.", "")
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    for href, raw_label in re.findall(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>([\s\S]*?)</a>", html, flags=re.IGNORECASE):
        title = _clean_text(raw_label)
        if len(title) < 28 or len(title.split()) < 4:
            continue

        absolute_url = urljoin(base_url, unescape(href).strip())
        parsed = urlparse(absolute_url)
        if parsed.scheme not in {"http", "https"}:
            continue

        host = parsed.netloc.lower().replace("www.", "")
        if base_host and base_host not in host:
            continue

        lower_path = f"{parsed.path.lower()} {parsed.query.lower()}"
        if any(block in lower_path for block in WEB_SOURCE_BLOCKLIST):
            continue

        canonical_url = _canonical_story_url(absolute_url)
        if not canonical_url or canonical_url in seen_urls:
            continue

        seen_urls.add(canonical_url)
        candidates.append((title, absolute_url))

        if len(candidates) >= max_links:
            break

    return candidates


def _extract_items_from_web_page(feed_name: str, source_url: str) -> list[dict]:
    results: list[dict] = []
    candidates = _extract_web_candidates(source_url, MAX_WEB_ARTICLES_PER_SOURCE)

    for index, (title, article_url) in enumerate(candidates):
        publisher = _publisher_from_url(article_url)
        excerpt = ""
        if ENABLE_ARTICLE_EXCERPT_FETCH and index < 8:
            excerpt = _extract_article_excerpt(article_url, title, publisher)
        snippet = excerpt or _headline_fallback_summary(title)
        summary = snippet or ""

        if not _passes_sow_focus(title, summary, snippet):
            continue

        sector = _categorize(title, summary)
        if not sector:
            continue

        is_valid, _, _ = is_relevant(title, summary)
        if not is_valid:
            is_direct_context_match = feed_name in REGIONAL_CONTEXT_FEEDS and _passes_sow_focus(title, summary, snippet)
            if not is_direct_context_match:
                continue

        country = _detect_country(title, snippet, feed_name, publisher, article_url)
        results.append(
            {
                "id": _make_id(article_url, title),
                "title": title,
                "url": article_url,
                "originalUrl": article_url,
                "verifiedUrl": article_url,
                "publisher": publisher,
                "publishedAt": "",
                "sourcePublishedAt": "",
                "source": feed_name,
                "sector": sector,
                "country": country,
                "snippet": snippet[:320],
            }
        )

    return results


def _detect_country(title: str, snippet: str, source: str, publisher: str, url: str) -> str:
    text = f"{title} {snippet}".lower()
    best_country = "regional"
    best_score = 0

    for country, hints in COUNTRY_HINTS.items():
        score = sum(1 for hint in hints if hint in text)
        if score > best_score:
            best_country = country
            best_score = score

    if best_score > 0:
        return best_country

    url_text = f"{title} {snippet} {url}".lower()
    for country, hints in COUNTRY_HINTS.items():
        score = sum(1 for hint in hints if hint in url_text)
        if score > best_score:
            best_country = country
            best_score = score

    if best_score > 0:
        return best_country

    source_hint = FEED_COUNTRY_HINTS.get(source)
    if source_hint:
        return source_hint

    return "regional"


def _country_weight(country: str) -> float:
    return float(COUNTRY_PRIORITY_WEIGHT.get(country, 1.0))


def _country_cap(country: str, relaxed: bool = False) -> int:
    base_cap = int(COUNTRY_MAX_CAPS.get(country, MAX_ITEMS_PER_COUNTRY))
    return base_cap + 2 if relaxed else base_cap


def _passes_sow_focus(title: str, summary: str, snippet: str = "") -> bool:
    text = f"{title} {summary} {snippet}".lower()

    has_geo_marker = any(marker in text for marker in SEA_CONTEXT_MARKERS)
    has_marine_marker = any(marker in text for marker in MARINE_CONTEXT_MARKERS)
    has_community_marker = any(marker in text for marker in COASTAL_COMMUNITY_MARKERS)

    if not has_geo_marker or not has_marine_marker:
        return False

    has_out_of_scope_global = any(marker in text for marker in OUT_OF_SCOPE_GLOBAL_MARKERS)
    if has_out_of_scope_global and not has_community_marker:
        return False

    return True


def _extract_items(feed_name: str, feed_url: str, mode: str = "feed") -> list[dict]:
    if mode == "web":
        return _extract_items_from_web_page(feed_name, feed_url)

    parsed = _parse_feed(feed_url)
    results: list[dict] = []
    for entry in list(parsed.entries)[:MAX_FEED_ENTRIES_PER_SOURCE]:
        raw_title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        summary = (entry.get("summary") or entry.get("description") or "").strip()
        published = (entry.get("published") or entry.get("updated") or "").strip()
        title, publisher = _split_title_and_publisher(raw_title, feed_name)
        feed_excerpt = _extract_feed_summary_excerpt(summary)
        snippet = _best_snippet(feed_excerpt or summary, title, publisher)

        if not title or not link:
            continue

        if not _passes_sow_focus(title, summary, snippet):
            continue

        sector = _categorize(title, summary)
        if not sector:
            continue

        is_valid, _, _ = is_relevant(title, summary)
        if not is_valid:
            is_direct_context_match = feed_name in REGIONAL_CONTEXT_FEEDS and _passes_sow_focus(title, summary, snippet)
            if not is_direct_context_match:
                continue

        verified_url = _resolve_verified_url(link, summary)
        clean_publisher = publisher or _publisher_from_url(verified_url)
        excerpt = ""
        if ENABLE_ARTICLE_EXCERPT_FETCH:
            excerpt = _extract_article_excerpt(verified_url, title, clean_publisher)
        if excerpt:
            snippet = excerpt
        country = _detect_country(title, snippet, feed_name, clean_publisher, verified_url)

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
                "country": country,
                "snippet": snippet[:320],
            }
        )
    return results


def build_latest_json() -> dict:
    all_items: list[dict] = []
    seen_urls: set[str] = set()
    seen_title_signatures: set[str] = set()

    for feed in FEEDS:
        print(f"Fetching {feed['name']} …")
        try:
            items = _extract_items(feed["name"], feed["url"], str(feed.get("mode", "feed")))
        except Exception as exc:  # noqa: BLE001
            print(f"  [WARN] Failed: {type(exc).__name__}: {exc}")
            items = []

        for item in items:
            url = item["url"]
            canonical_url = _canonical_story_url(url)
            title_signature = _title_fingerprint(item.get("title", ""), item.get("publishedAt", ""))

            if canonical_url and canonical_url in seen_urls:
                continue
            if title_signature in seen_title_signatures:
                continue

            if canonical_url:
                seen_urls.add(canonical_url)
            seen_title_signatures.add(title_signature)
            all_items.append(item)

    all_items.sort(key=lambda i: (i.get("publishedAt") or ""), reverse=True)

    sectors_payload = []
    total = 0
    publisher_usage: dict[str, int] = {}
    country_usage: dict[str, int] = {}

    for sector in SECTORS:
        candidates = [item for item in all_items if item["sector"] == sector]
        selected: list[dict] = []

        remaining = list(candidates)
        while remaining and len(selected) < MAX_ITEMS_PER_SECTOR:
            ranked = sorted(
                remaining,
                key=lambda item: (
                    country_usage.get(str(item.get("country") or "regional").lower(), 0)
                    / max(_country_weight(str(item.get("country") or "regional").lower()), 0.1),
                    publisher_usage.get(str(item.get("publisher") or "unknown").lower(), 0),
                ),
            )
            item = ranked[0]
            publisher = str(item.get("publisher") or "unknown").lower()
            country = str(item.get("country") or "regional").lower()
            remaining.remove(item)

            if publisher_usage.get(publisher, 0) >= MAX_ITEMS_PER_PUBLISHER:
                continue
            if country_usage.get(country, 0) >= _country_cap(country):
                continue

            selected.append(item)
            publisher_usage[publisher] = publisher_usage.get(publisher, 0) + 1
            country_usage[country] = country_usage.get(country, 0) + 1

        if len(selected) < MAX_ITEMS_PER_SECTOR:
            for item in candidates:
                if item in selected:
                    continue
                publisher = str(item.get("publisher") or "unknown").lower()
                country = str(item.get("country") or "regional").lower()
                if publisher_usage.get(publisher, 0) >= MAX_ITEMS_PER_PUBLISHER + 2:
                    continue
                if country_usage.get(country, 0) >= _country_cap(country, relaxed=True):
                    continue
                selected.append(item)
                publisher_usage[publisher] = publisher_usage.get(publisher, 0) + 1
                country_usage[country] = country_usage.get(country, 0) + 1
                if len(selected) >= MAX_ITEMS_PER_SECTOR:
                    break

        if len(selected) < MAX_ITEMS_PER_SECTOR:
            for item in candidates:
                if item in selected:
                    continue
                selected.append(item)
                publisher = str(item.get("publisher") or "unknown").lower()
                country = str(item.get("country") or "regional").lower()
                publisher_usage[publisher] = publisher_usage.get(publisher, 0) + 1
                country_usage[country] = country_usage.get(country, 0) + 1
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
                "name": "Blue Economy",
                "items": [
                    {
                        "id": "placeholder-blue",
                        "title": "Southeast Asia blue economy initiatives for grassroots groups",
                        "url": "#",
                        "publisher": "placeholder",
                        "publishedAt": datetime.now(timezone.utc).date().isoformat(),
                        "sourcePublishedAt": datetime.now(timezone.utc).date().isoformat(),
                        "source": "Placeholder",
                        "sector": "Blue Economy",
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
            "opportunities": _build_opportunities(),
        }

    has_vietnam_selected = any(
        str(item.get("country") or "").lower() == "vietnam"
        for sector in sectors_payload
        for item in sector.get("items", [])
    )
    if not has_vietnam_selected:
        vietnam_candidates = [
            item
            for item in all_items
            if str(item.get("country") or "").lower() == "vietnam"
        ]
        vietnam_candidates.sort(key=lambda i: (i.get("publishedAt") or ""), reverse=True)

        for candidate in vietnam_candidates:
            sector_name = candidate.get("sector")
            target_sector = next((s for s in sectors_payload if s.get("name") == sector_name), None)
            if not target_sector:
                continue

            target_items = target_sector.get("items", [])
            if any(existing.get("id") == candidate.get("id") for existing in target_items):
                continue

            if len(target_items) < MAX_ITEMS_PER_SECTOR:
                target_items.append(candidate)
                total += 1
                break

            replace_index = next(
                (
                    index
                    for index, existing in enumerate(target_items)
                    if str(existing.get("country") or "").lower() != "vietnam"
                ),
                None,
            )
            if replace_index is not None:
                target_items[replace_index] = candidate
                break

    return {
        "runAt": datetime.now(timezone.utc).isoformat(),
        "totalItems": total,
        "sectors": sectors_payload,
        "opportunities": _build_opportunities(),
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
