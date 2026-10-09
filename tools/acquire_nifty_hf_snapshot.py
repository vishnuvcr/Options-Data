#!/usr/bin/env python3
"""Acquire the approved non-commercial NIFTY subset and write a file manifest."""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from huggingface_hub import snapshot_download

DATASET = "thetrademarkk/india-index-options-1m"
REVISION = "51ca58c"
PATTERNS = ["index/NIFTY.parquet", "options/NIFTY/*.parquet"]

def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    snapshot_download(repo_id=DATASET, repo_type="dataset", revision=REVISION,
                      local_dir=args.output, allow_patterns=PATTERNS)
    files = []
    for path in sorted(args.output.rglob("*.parquet")):
        files.append({"path": str(path.relative_to(args.output)).replace("\\", "/"),
                      "bytes": path.stat().st_size, "sha256": digest(path)})
    if not any(row["path"] == "index/NIFTY.parquet" for row in files):
        raise RuntimeError("NIFTY index partition was not acquired")
    if not any(row["path"].startswith("options/NIFTY/") for row in files):
        raise RuntimeError("No NIFTY option partitions were acquired")
    manifest = {
        "source_id": "hf_thetrademarkk_india_index_options_1m_51ca58c",
        "canonical_url": "https://huggingface.co/datasets/thetrademarkk/india-index-options-1m",
        "license": "CC-BY-NC-4.0",
        "use_constraint": "non-commercial",
        "revision": REVISION,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
        "total_bytes": sum(row["bytes"] for row in files),
    }
    (args.output / "acquisition_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"files": len(files), "total_bytes": manifest["total_bytes"]}))

if __name__ == "__main__":
    main()
