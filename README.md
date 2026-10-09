# NIFTY Research Source Registry

This repository builds a **provenance-first catalog** of candidate sources for NIFTY spot, futures, option chains, volatility, constituent, macro and news research.

## Important data-rights boundary

It does not scrape NSE web pages or evade access controls. NSE's published terms prohibit systematic automated collection; historical order/trade data is a licensed product. Treat exchange-owned data as `restricted` until a written licence or an explicit redistribution/training right is recorded.

The generated catalog therefore separates:

- `approved_open` — licence verified, machine retrieval allowed
- `review_required` — relevant, but licence/automated-use needs human verification
- `restricted` — official/valuable but needs a contract or has terms incompatible with this pipeline
- `rejected` — irrelevant, duplicate, dead, or non-reproducible

A count of 2,000 is a discovery target, not a claim that 2,000 sources are suitable for training. Each candidate must be verified before it may enter a research dataset.

## Source definition

One source is a distinct upstream repository, dataset, documented API, official archive, or paper/data release. Mirrors and individual URL parameters are deduplicated. A source record stores its canonical URL, evidence URL, declared licence, applicable market surfaces, retrieval method, data-rights status and a stable source ID.

## Quick start

```powershell
$env:GH_TOKEN = "github_pat_..." # recommended; public API works with lower rate limits
python .\tools\discover_sources.py --target 2000
python .\tools\review_sources.py
```

The discovery job searches public GitHub repositories using the query family in `config/discovery_queries.json`, deduplicates repositories, and writes `catalog/candidates.jsonl`. It also adds official seed references in `catalog/official_seeds.jsonl`.

## Data model

| Field | Meaning |
|---|---|
| `source_id` | stable SHA-256-based ID |
| `canonical_url` | source's canonical location |
| `source_type` | repository, dataset, API, archive, or paper |
| `surfaces` | spot, futures, options, greeks, VIX, constituents, macro, or news |
| `license` | declared licence, or `UNKNOWN` |
| `rights_status` | approved_open, review_required, restricted, or rejected |
| `evidence_url` | page that supports the licence/retrieval decision |
| `last_verified_at` | ISO-8601 verification timestamp |

## Before using any data

- Verify dataset and upstream-exchange licences independently.
- Never infer a licence from a GitHub repository's code licence.
- Store raw data separately from this catalog and retain the source ID and retrieval timestamp with every partition.
- Calculate Greeks from retained inputs using a versioned convention; do not mix vendor Greeks without a vendor column.
