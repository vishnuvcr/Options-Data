# NIFTY Options Research Dataset

This module materializes a point-in-time, variable-minute NIFTY options dataset from authorised input files. It produces a research table with spot, futures, synthetic futures, option microstructure, implied volatility, and Black-76 Greeks.

It intentionally does not download or scrape exchange data. Put data you are entitled to use in data/raw/ and record its source_id from the source catalog.

## Inputs

All timestamps must be ISO-8601 with an explicit offset, preferably IST (+05:30).

| File | Required columns |
|---|---|
| spot.csv | timestamp,close,source_id |
| futures.csv | timestamp,expiry_date,last,bid,ask,volume,open_interest,source_id |
| options.csv | timestamp,expiry_date,strike,option_type,bid,ask,last,volume,open_interest,source_id |

Optional option fields: iv_vendor, delta_vendor, gamma_vendor, theta_vendor, vega_vendor, rho_vendor.

## Build

python tools/build_nifty_options_dataset.py --spot data/raw/spot.csv --futures data/raw/futures.csv --options data/raw/options.csv --output data/derived/nifty_options_enriched.csv --risk-free-rate 0.065

The output is CSV for inspection. For production, partition the same output by trade_date and expiry_date in Parquet; retain the raw files unchanged.

## Calculations

- mid: bid/ask midpoint; falls back to last only when either quote is missing.
- synthetic_future: matched CE mid − PE mid + strike at the same timestamp/expiry/strike.
- basis: future mid − spot close.
- iv_computed: bisection-solved Black-76 volatility from the mid price.
- delta_B76, gamma_B76, vega_B76, theta_B76: derived from the computed IV and futures level.
- quote_quality: a transparent quality label; no price is silently imputed.

The calculations use a futures-based Black-76 convention. They are research estimates, not broker/exchange Greeks.

## Required lineage

Every raw and derived row carries source_id. Do not merge datasets with different timestamps, trading-session definitions, or contract symbology without keeping the original fields and a documented transformation.