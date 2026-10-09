#!/usr/bin/env python3
"""Enrich authorised NIFTY option-chain CSV data with reproducible research fields."""
from __future__ import annotations

import argparse
import bisect
import csv
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

N = lambda x: 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
PDF = lambda x: math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

def number(value):
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None

def instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def mid(row):
    bid, ask, last = number(row.get("bid")), number(row.get("ask")), number(row.get("last"))
    if bid is not None and ask is not None and bid >= 0 and ask >= bid:
        return (bid + ask) / 2.0, "two_sided"
    if last is not None and last >= 0:
        return last, "last_only"
    return None, "missing"

def black76(forward, strike, years, rate, sigma, kind):
    if min(forward, strike, years, sigma) <= 0:
        return None
    root = sigma * math.sqrt(years)
    d1 = (math.log(forward / strike) + 0.5 * sigma * sigma * years) / root
    d2 = d1 - root
    discount = math.exp(-rate * years)
    if kind == "CE":
        return discount * (forward * N(d1) - strike * N(d2))
    return discount * (strike * N(-d2) - forward * N(-d1))

def implied_vol(price, forward, strike, years, rate, kind):
    if price is None or min(forward, strike, years) <= 0:
        return None
    intrinsic = max(0.0, (forward - strike) if kind == "CE" else (strike - forward))
    if price < math.exp(-rate * years) * intrinsic - 1e-8:
        return None
    low, high = 1e-4, 8.0
    if black76(forward, strike, years, rate, high, kind) < price:
        return None
    for _ in range(80):
        guess = (low + high) / 2.0
        if black76(forward, strike, years, rate, guess, kind) < price:
            low = guess
        else:
            high = guess
    return (low + high) / 2.0

def greeks(forward, strike, years, rate, sigma, kind):
    if sigma is None or min(forward, strike, years, sigma) <= 0:
        return {key: None for key in ("delta_B76", "gamma_B76", "vega_B76", "theta_B76")}
    root = sigma * math.sqrt(years)
    d1 = (math.log(forward / strike) + 0.5 * sigma * sigma * years) / root
    d2 = d1 - root
    discount = math.exp(-rate * years)
    sign = 1.0 if kind == "CE" else -1.0
    delta = sign * discount * (N(sign * d1))
    gamma = discount * PDF(d1) / (forward * root)
    vega = discount * forward * PDF(d1) * math.sqrt(years) / 100.0
    price = black76(forward, strike, years, rate, sigma, kind)
    theta = (-discount * forward * PDF(d1) * sigma / (2 * math.sqrt(years))
             + sign * rate * discount * (forward * N(sign * d1) - strike * N(sign * d2))) / 365.0
    return {"delta_B76": delta, "gamma_B76": gamma, "vega_B76": vega,
            "theta_B76": theta, "model_price_B76": price}

def asof(series, at):
    if not series:
        return None
    keys = [entry[0] for entry in series]
    pos = bisect.bisect_right(keys, at) - 1
    return series[pos][1] if pos >= 0 else None

def required(rows, columns, name):
    missing = columns - set(rows[0]) if rows else columns
    if missing:
        raise ValueError(name + " is missing columns: " + ", ".join(sorted(missing)))

def read_rows(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spot", required=True)
    parser.add_argument("--futures", required=True)
    parser.add_argument("--options", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--risk-free-rate", type=float, default=0.065)
    args = parser.parse_args()

    spot, futures, options = read_rows(args.spot), read_rows(args.futures), read_rows(args.options)
    required(spot, {"timestamp", "close", "source_id"}, "spot")
    required(futures, {"timestamp", "expiry_date", "last", "bid", "ask", "volume", "open_interest", "source_id"}, "futures")
    required(options, {"timestamp", "expiry_date", "strike", "option_type", "bid", "ask", "last", "volume", "open_interest", "source_id"}, "options")

    spot_series = sorted((instant(row["timestamp"]), row) for row in spot)
    future_series = defaultdict(list)
    for row in futures:
        future_series[row["expiry_date"]].append((instant(row["timestamp"]), row))
    for series in future_series.values():
        series.sort(key=lambda item: item[0])

    pairs = {}
    for row in options:
        key = (row["timestamp"], row["expiry_date"], row["strike"])
        pairs.setdefault(key, {})[row["option_type"].upper()] = row

    fieldnames = list(options[0].keys()) + [
        "trade_date", "spot_close", "future_mid", "future_source_id", "basis",
        "option_mid", "quote_quality", "synthetic_future", "put_call_parity_gap",
        "years_to_expiry", "iv_computed", "delta_B76", "gamma_B76", "vega_B76",
        "theta_B76", "model_price_B76", "calculation_version"
    ]
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in options:
            at, expiry = instant(row["timestamp"]), datetime.fromisoformat(row["expiry_date"])
            spot_row = asof(spot_series, at)
            future_row = asof(future_series.get(row["expiry_date"], []), at)
            option_mid, quality = mid(row)
            future_mid, _ = mid(future_row) if future_row else (None, "missing")
            spot_close = number(spot_row.get("close")) if spot_row else None
            strike = number(row["strike"])
            years = max(0.0, (expiry - at.replace(tzinfo=None)).total_seconds() / 31557600.0)
            kind = row["option_type"].upper()
            mate = pairs.get((row["timestamp"], row["expiry_date"], row["strike"]), {})
            call_mid, _ = mid(mate["CE"]) if "CE" in mate else (None, "missing")
            put_mid, _ = mid(mate["PE"]) if "PE" in mate else (None, "missing")
            synthetic = call_mid - put_mid + strike if None not in (call_mid, put_mid, strike) else None
            parity_gap = (future_mid - synthetic) if None not in (future_mid, synthetic) else None
            iv = implied_vol(option_mid, future_mid, strike, years, args.risk_free_rate, kind) if future_mid else None
            result = dict(row)
            result.update({
                "trade_date": at.date().isoformat(), "spot_close": spot_close, "future_mid": future_mid,
                "future_source_id": future_row.get("source_id") if future_row else None,
                "basis": future_mid - spot_close if None not in (future_mid, spot_close) else None,
                "option_mid": option_mid, "quote_quality": quality, "synthetic_future": synthetic,
                "put_call_parity_gap": parity_gap, "years_to_expiry": years, "iv_computed": iv,
                "calculation_version": "black76-v1",
            })
            result.update(greeks(future_mid, strike, years, args.risk_free_rate, iv, kind)
                          if future_mid else greeks(0, 0, 0, args.risk_free_rate, None, kind))
            writer.writerow(result)

if __name__ == "__main__":
    main()
