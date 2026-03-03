#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path


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


def is_allowed_headline(headline: str) -> bool:
    if not headline:
        return False

    lowered = headline.lower()

    if any(term in lowered for term in DISALLOWED_HEADLINE_TERMS):
        return False

    return any(pattern.search(headline) for pattern in REQUIRED_HEADLINE_PATTERNS)


def _headline_from_article(article: dict) -> str:
    return str(article.get("headline") or article.get("title") or "").strip()


def filter_articles(articles: list[dict]) -> list[dict]:
    filtered: list[dict] = []
    for article in articles:
        headline = _headline_from_article(article)
        if is_allowed_headline(headline):
            filtered.append(article)
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
