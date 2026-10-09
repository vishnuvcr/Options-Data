#!/usr/bin/env python3
"""Discover distinct public GitHub repositories relevant to NIFTY research.

This program creates a *candidate source catalog* only. It never downloads market
data and never requests NSE website endpoints. Review every candidate's licence
and upstream data rights before using its data in research or ML.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUERIES = ROOT / "config" / "discovery_queries.json"
DEFAULT_OUTPUT = ROOT / "catalog" / "candidates.jsonl"
API = "https://api.github.com/search/repositories"


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def existing_urls(path: Path) -> set[str]:
    if not path.exists():
        return set()
    urls: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            urls.add(json.loads(line)["canonical_url"])
        except (json.JSONDecodeError, KeyError):
            continue
    return urls


def fetch(query: str, page: int, token: str | None) -> dict[str, Any]:
    params = urllib.parse.urlencode({
        "q": query + " archived:false fork:false",
        "sort": "updated",
        "order": "desc",
        "per_page": 100,
        "page": page,
    })
    request = urllib.request.Request(
        API + "?" + params,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Options-Data-source-discovery/1.0",
            **({"Authorization": "Bearer " + token} if token else {}),
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def tags_for(text: str) -> list[str]:
    text = text.lower()
    labels = {
        "spot": ("spot", "ohlc", "candlestick", "index", "nifty 50"),
        "intraday": ("intraday", "minute", "1min", "5min", "15min", "tick"),
        "futures": ("future", "futures", "fo ", "f&o"),
        "options": ("option", "option-chain", "option chain"),
        "greeks": ("greek", "implied volatility", "black-scholes", "black scholes"),
        "open_interest": ("open interest", "oi "),
        "VIX": ("vix", "volatility index"),
        "backtesting": ("backtest", "backtesting", "strategy"),
        "machine_learning": ("machine learning", "ml", "forecast"),
    }
    return sorted(name for name, markers in labels.items() if any(x in text for x in markers))


def record(item: dict[str, Any], query: str) -> dict[str, Any]:
    url = item["html_url"].rstrip("/")
    snapshot = " ".join(filter(None, [
        item.get("full_name"), item.get("description"), " ".join(item.get("topics", []))
    ]))
    declared = (item.get("license") or {}).get("spdx_id") or "UNKNOWN"
    return {
        "source_id": "gh_" + hashlib.sha256(url.encode()).hexdigest()[:16],
        "canonical_url": url,
        "source_type": "github_repository",
        "name": item["full_name"],
        "description": item.get("description") or "",
        "surfaces": tags_for(snapshot),
        "license": declared,
        "rights_status": "review_required",
        "evidence_url": url,
        "retrieval": "GitHub Search API metadata only",
        "discovery_query": query,
        "github_stars": item.get("stargazers_count", 0),
        "updated_at": item.get("updated_at"),
        "last_verified_at": datetime.now(timezone.utc).isoformat(),
        "review_notes": "Repository licence does not establish rights to its market-data contents."
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=2000)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--delay", type=float, default=2.2,
                        help="Seconds between GitHub search calls; increase if rate-limited.")
    args = parser.parse_args()

    token = os.getenv("GH_TOKEN")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    seen = existing_urls(args.output)
    queries: list[str] = read_json(args.queries)
    found = len(seen)
    print(f"Resuming with {found} unique sources; target is {args.target}.")

    with args.output.open("a", encoding="utf-8") as output:
        for query in queries:
            if found >= args.target:
                break
            for page in range(1, 11):  # GitHub caps any one search at 1,000 results.
                if found >= args.target:
                    break
                try:
                    response = fetch(query, page, token)
                except Exception as exc:
                    print(f"Stopping on {query!r}, page {page}: {exc}")
                    print("Wait for the API rate-limit window and rerun; output is resumable.")
                    return 2
                items = response.get("items", [])
                if not items:
                    break
                for item in items:
                    url = item["html_url"].rstrip("/")
                    if url in seen:
                        continue
                    output.write(json.dumps(record(item, query), ensure_ascii=False) + "\n")
                    seen.add(url)
                    found += 1
                    if found >= args.target:
                        break
                output.flush()
                print(f"{found}/{args.target}: {query!r}, page {page}")
                time.sleep(args.delay)

    print(f"Finished with {found} unique candidate sources in {args.output}.")
    if found < args.target:
        print("Add more targeted queries in config/discovery_queries.json and rerun.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
