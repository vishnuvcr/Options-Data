#!/usr/bin/env python3
"""Convert an authorised index/options Parquet layout into normalized CSV inputs."""
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

def rename(frame, aliases):
    for canonical, choices in aliases.items():
        found = next((column for column in choices if column in frame.columns), None)
        if found:
            frame = frame.rename(columns={found: canonical})
    return frame

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True,
                        help="Root containing index/NIFTY.parquet and options/NIFTY/*.parquet")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    args = parser.parse_args()

    index_path = args.input_root / "index" / "NIFTY.parquet"
    option_paths = sorted((args.input_root / "options" / "NIFTY").glob("*.parquet"))
    if not index_path.exists() or not option_paths:
        raise FileNotFoundError("Expected index/NIFTY.parquet and options/NIFTY/*.parquet")

    args.output_root.mkdir(parents=True, exist_ok=True)
    spot = rename(pd.read_parquet(index_path), {
        "timestamp": ["timestamp", "datetime", "date_time"],
        "close": ["close", "Close", "ltp"],
    })
    required_spot = {"timestamp", "close"}
    if not required_spot <= set(spot):
        raise ValueError("Index file requires timestamp and close columns")
    spot = spot[list(required_spot)].copy()
    spot["source_id"] = args.source_id
    spot.to_csv(args.output_root / "spot.csv", index=False)

    parts = []
    for path in option_paths:
        frame = rename(pd.read_parquet(path), {
            "timestamp": ["timestamp", "datetime", "date_time"],
            "expiry_date": ["expiry_date", "expiry", "expiryDate"],
            "strike": ["strike", "strike_price"],
            "option_type": ["option_type", "type", "instrument_type"],
            "bid": ["bid", "bid_price"],
            "ask": ["ask", "ask_price"],
            "last": ["last", "close", "ltp"],
            "volume": ["volume", "vol"],
            "open_interest": ["open_interest", "oi", "openInterest"],
        })
        frame["expiry_date"] = frame.get("expiry_date", path.stem)
        for column in ("bid", "ask", "last", "volume", "open_interest"):
            if column not in frame:
                frame[column] = None
        required = {"timestamp", "expiry_date", "strike", "option_type"}
        if not required <= set(frame):
            raise ValueError(f"{path} lacks: {sorted(required - set(frame))}")
        parts.append(frame[["timestamp", "expiry_date", "strike", "option_type",
                            "bid", "ask", "last", "volume", "open_interest"]])

    options = pd.concat(parts, ignore_index=True)
    options["source_id"] = args.source_id
    options.to_csv(args.output_root / "options.csv", index=False)
    print({"spot_rows": len(spot), "option_rows": len(options), "files": len(option_paths)})

if __name__ == "__main__":
    main()
