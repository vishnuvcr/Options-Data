# Internal Repository References

Reviewed on 2026-10-09 from your GitHub account. These references are implementation evidence, not a licence determination.

## Primary reference: Daily-Options

Repository: https://github.com/vishnuvcr/Daily-Options

The repository contains the strongest reusable NIFTY research conventions found in the crawl:

- Exact-expiry one-minute option panels, with timestamp/contract coverage gates.
- Schema expectations: option expiry, strike, option type, OHLCV and OI; spot and futures timestamp joins.
- Nearest non-expired futures selection and a 90% timestamp-overlap data gate.
- Point-in-time execution and explicit base/stress transaction-cost handling.
- Data-quality failures are preserved as data-limited outcomes rather than silently filled.

Relevant files:

- research/phase12_derivative_lead_options.py — futures/spot normalization, nearest-contract logic, overlap gate and lead features.
- research/phase25_falcon_rissin.py — exact-expiry options-chain selection using timestamp, strike, expiry and option_type.
- config/cost_model_2026.yaml — cost model inputs; validate rates before use.
- docs/error_log.md — prior data-coverage and timestamp-normalization defects to guard against.

## External candidates documented by Daily-Options

- Hugging Face: thetrademarkk/india-index-options-1m (pinned revision 51ca58c); expected layout index/NIFTY.parquet and options/NIFTY/{expiry}.parquet.
- Hugging Face: rissin/nse-options-intraday.
- GitHub: aeron7/nifty-banknifty-intraday-data.

Each is still review_required: determine the dataset licence and upstream market-data rights before ingestion.

## Integration decisions

The Options-Data builder will retain the following concepts from Daily-Options: exact expiry as a primary key, no forward-filled executable quotes, timestamp-overlap gates, source lineage, and separate raw/derived layers. It will not copy strategy results or treat them as predictive evidence.