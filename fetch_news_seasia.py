#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path


COUNTRIES = {
    "VN": {"name": "Vietnam", "lang": "vi"},
    "TH": {"name": "Thailand", "lang": "th"},
    "PH": {"name": "Philippines", "lang": "tl"},
    "ID": {"name": "Indonesia", "lang": "id"},
    "MY": {"name": "Malaysia", "lang": "ms"},
    "MM": {"name": "Myanmar", "lang": "my"},
    "KH": {"name": "Cambodia", "lang": "km"},
    "SG": {"name": "Singapore", "lang": "en"},
    "BN": {"name": "Brunei", "lang": "ms"},
}

MARINE_TOPICS = {
    "Sustainable Fisheries": [
        "fisheries",
        "sustainable fishing",
        "aquaculture",
        "fishing communities",
    ],
    "Climate Change": [
        "climate change",
        "sea level",
        "coastal erosion",
        "mangrove",
        "coral reef",
        "seagrass",
    ],
    "Maritime Security": [
        "marine security",
        "maritime",
        "eez",
        "exclusive economic zone",
        "sovereignty",
    ],
    "Sustainable Blue Economy": [
        "blue economy",
        "coastal livelihoods",
        "ocean economy",
        "port",
        "shipping",
    ],
    "Marine Pollution": [
        "marine pollution",
        "ocean pollution",
        "plastic",
        "microplastic",
        "oil spill",
        "waste",
    ],
}


DISALLOWED_HEADLINE_TERMS = ["venezuela"]

REQUIRED_HEADLINE_TERMS = [
    "SEA",
    "Southeast Asia",
    "ASEAN",
    "AEC",
    "ASCC",
    "SEAFDEC",
    "Timor Leste",
    "Thailand",
    "Indonesia",
    "Malaysia",
    "Vietnam",
    "Philippines",
    "Singapore",
    "Brunei",
    "Myanamar",
    "Myanmar",
    "Cambodia",
]


def _compile_required_patterns() -> list[re.Pattern]:
    patterns: list[re.Pattern] = []
    for term in REQUIRED_HEADLINE_TERMS:
        normalized = term.strip().lower()
        if normalized == "timor leste":
            patterns.append(re.compile(r"\btimor[-\s]+leste\b", re.IGNORECASE))
            continue

        escaped = re.escape(normalized)
        patterns.append(re.compile(rf"\b{escaped}\b", re.IGNORECASE))
    return patterns


REQUIRED_HEADLINE_PATTERNS = _compile_required_patterns()

COUNTRY_KEYWORDS = {
    "vietnam": "VN",
    "thailand": "TH",
    "philippines": "PH",
    "indonesia": "ID",
    "malaysia": "MY",
    "myanmar": "MM",
    "myanamar": "MM",
    "cambodia": "KH",
    "singapore": "SG",
    "brunei": "BN",
    "asean": None,
    "southeast asia": None,
    "timor leste": None,
}


def _normalize_text(*parts: str) -> str:
    return " ".join(parts).lower().strip()


def detect_countries(text: str) -> list[str]:
    lowered = text.lower()
    found: set[str] = set()
    for keyword, country_code in COUNTRY_KEYWORDS.items():
        if keyword in lowered and country_code:
            found.add(country_code)
    return sorted(found)


def detect_topics(text: str) -> list[str]:
    lowered = text.lower()
    topics: list[str] = []
    for topic, keywords in MARINE_TOPICS.items():
        if any(keyword in lowered for keyword in keywords):
            topics.append(topic)
    return topics


def is_allowed_headline(headline: str) -> bool:
    if not headline:
        return False

    lowered = headline.lower()

    if any(term in lowered for term in DISALLOWED_HEADLINE_TERMS):
        return False

    return any(pattern.search(headline) for pattern in REQUIRED_HEADLINE_PATTERNS)


def is_relevant(title: str, summary: str = "") -> tuple[bool, list[str], list[str]]:
    if not is_allowed_headline(title):
        return False, [], []

    text = _normalize_text(title, summary)
    countries = detect_countries(text)
    topics = detect_topics(text)

    has_geo_context = bool(countries) or any(
        phrase in text for phrase in ("southeast asia", "asean", "timor leste")
    )

    return has_geo_context and bool(topics), countries, topics


def _headline_from_article(article: dict) -> str:
    return str(article.get("headline") or article.get("title") or "").strip()


def filter_articles(articles: list[dict]) -> list[dict]:
    filtered: list[dict] = []
    for article in articles:
        headline = _headline_from_article(article)
        summary = str(article.get("summary") or article.get("snippet") or "")
        is_valid, countries, topics = is_relevant(headline, summary)
        if not is_valid:
            continue

        enriched = dict(article)
        if countries:
            enriched["countries"] = countries
        if topics:
            enriched["topics"] = topics
        filtered.append(enriched)
    return filtered


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Filter news articles by strict SEA headline rules."
    )
    parser.add_argument("input", help="Input JSON file containing an array of article objects")
    parser.add_argument(
        "-o",
        "--output",
        help="Optional output path. If omitted, prints JSON to stdout.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    with input_path.open("r", encoding="utf-8") as f:
        articles = json.load(f)

    if not isinstance(articles, list):
        raise ValueError("Input JSON must be an array of article objects.")

    filtered = filter_articles(articles)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(filtered, f, ensure_ascii=False, indent=2)
        print(f"Filtered {len(filtered)} of {len(articles)} articles -> {output_path}")
    else:
        print(json.dumps(filtered, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
