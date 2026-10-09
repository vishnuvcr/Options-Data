#!/usr/bin/env python3
"""Build a rights-reviewable catalog of public GitHub source candidates.

This discovers repository metadata only. It neither downloads market data nor
requests NSE web endpoints. A repository licence never proves rights to the
market data it may contain; all records therefore begin as review_required.
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
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUERIES = ROOT / "config" / "discovery_queries.json"
DEFAULT_OUTPUT = ROOT / "catalog" / "candidates.jsonl"
API = "https://api.github.com/search/repositories"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def existing_urls(path: Path) -> set[str]:
    if not path.exists():
        return set()
    result: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            result.add(json.loads(line)["canonical_url"])
        except (json.JSONDecodeError, KeyError):
            pass
    return result


def fetch(query: str, page: int, token: str | None) -> dict[str, Any]:
    params = urllib.parse.urlencode({
        "q": query + " archived:false fork:false",
        "sort": "updated", "order": "desc", "per_page": 100, "page": page,
    })
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "Options-Data-source-discovery/1.1"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(
        urllib.request.Request(API + "?" + params, headers=headers), timeout=45
    ) as response:
        return json.load(response)


def fetch_with_backoff(query: str, page: int, token: str | None,
                       max_retries: int = 12) -> dict[str, Any]:
    """Respect GitHub search-rate resets instead of discarding partial progress."""
    for attempt in range(max_retries):
        try:
            return fetch(query, page, token)
        except HTTPError as exc:
            if exc.code not in (403, 429):
                raise
            reset = exc.headers.get("X-RateLimit-Reset")
            retry_after = exc.headers.get("Retry-After")
            if retry_after:
                pause = max(2, int(float(retry_after)) + 2)
            elif reset and reset.isdigit():
                pause = max(5, int(reset) - int(time.time()) + 3)
            else:
                pause = min(120, 15 * (attempt + 1))
            print(f"Rate limited at {query!r}, page {page}; waiting {pause}s "
                  f"(retry {attempt + 1}/{max_retries}).", flush=True)
            time.sleep(pause)
    raise RuntimeError(f"GitHub search rate limit persisted for {query!r}, page {page}")


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
    return sorted(key for key, values in labels.items() if any(v in text for v in values))


def record(item: dict[str, Any], query: str) -> dict[str, Any]:
    url = item["html_url"].rstrip("/")
    text = " ".join(filter(None, [item.get("full_name"), item.get("description"),
                                   " ".join(item.get("topics", []))]))
    return {
        "source_id": "gh_" + hashlib.sha256(url.encode()).hexdigest()[:16],
        "canonical_url": url,
        "source_type": "github_repository",
        "name": item["full_name"],
        "description": item.get("description") or "",
        "surfaces": tags_for(text),
        "license": (item.get("license") or {}).get("spdx_id") or "UNKNOWN",
        "rights_status": "review_required",
        "evidence_url": url,
        "retrieval": "GitHub Search API metadata only",
        "discovery_query": query,
        "github_stars": item.get("stargazers_count", 0),
        "updated_at": item.get("updated_at"),
        "last_verified_at": datetime.now(timezone.utc).isoformat(),
        "review_notes": "Verify repository and upstream market-data rights before use.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=2000)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--delay", type=float, default=3.2)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    seen = existing_urls(args.output)
    found = len(seen)
    print(f"Resuming with {found} unique sources; target is {args.target}.", flush=True)

    with args.output.open("a", encoding="utf-8") as output:
        for query in read_json(args.queries):
            for page in range(1, 11):  # GitHub search caps each query at 1,000 results.
                if found >= args.target:
                    break
                response = fetch_with_backoff(query, page, os.getenv("GH_TOKEN"))
                items = response.get("items", [])
                if not items:
                    break
                for item in items:
                    url = item["html_url"].rstrip("/")
                    if url not in seen:
                        output.write(json.dumps(record(item, query), ensure_ascii=False) + "\n")
                        seen.add(url)
                        found += 1
                        if found >= args.target:
                            break
                output.flush()
                print(f"{found}/{args.target}: {query!r}, page {page}", flush=True)
                time.sleep(args.delay)
            if found >= args.target:
                break

    print(f"Finished with {found} unique candidates in {args.output}.", flush=True)
    return 0 if found >= args.target else 1


if __name__ == "__main__":
    raise SystemExit(main())
