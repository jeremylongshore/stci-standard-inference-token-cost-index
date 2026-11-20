# STCI Methodology 2.1.0: facets, not verdicts

**Document ID:** 022
**Category:** DR (Design)
**Type:** STND (Standard)
**Status:** ACTIVE from 2026-11-21 (first date computed under 2.1.0)
**Supersedes:** `020-DR-STND-stci-methodology-2-0-0.md` for dates from 2026-11-21. 2.0.0 remains the rulebook for 2026-11-19 and 2026-11-20, archived as `data/fixtures/methodology-2.0.0.yaml`. Everything in 020 not changed here still applies.
**Refs:** #32

## Principle

STCI measures; it does not judge. A grade is a verdict, and a verdict written at collection time cannot be re-derived when the rule changes. 2.1.0 therefore writes only facets (what each endpoint reports about itself) and applies rules later, by id, in a view.

## 1. Private endpoint snapshot

For every open-weight model that clears the endpoint minimum, the collector keeps one row per priced endpoint: `model_id`, `provider`, `tag`, `quantization`, `context_length`, `max_completion_tokens`, `supported_parameters` (sorted), `price_in`, `price_out`, `cache_read`. Prices are kept as the source's own strings.

Rows are sorted and written as canonical JSON (sorted keys, no spaces) to `data/endpoints/{date}.jsonl`. The file is private and git-ignored, like observations (ADR 014). Its SHA-256 is recorded in the spread file as `endpoint_snapshot_sha256`. The rows are never published.

Uptime, throughput and latency, where the source reports them, go in a separate per-model `observed` block. They move minute to minute, so `observed` is excluded from every hash and is not published.

## 2. Facet cells

Per model, endpoints are cut into cells by:

- **precision** as reported (fp8, fp4, mxfp4, nvfp4, int4, bf16, fp16 ...). A missing or `unknown` value is its own `undisclosed` bucket. It is never folded into a named precision.
- **context_bucket**: `<=32k`, `32-128k`, `128k+`, `1M+` (`unknown` when not reported).
- **tools**: true when `supported_parameters` contains `tools`.

Each cell reports `n`, `min`, `p25`, `median`, `p75`, `max` and `p75_p25_ratio` of the blended price. When `n < 3` the statistics are null and `n` is still reported.

A dated snapshot id (suffix such as `-1017` or `-2026-10-17`) is a different model from the undated id. They are never pooled: cells are per exact `model_id`, each model carries `snapshot: dated|undated`, and an endpoint that names a different model id than the one requested is dropped.

## 3. Rules

`rules/grade-rules.yaml` is an append-only list. Each entry has an `effective_from` date; `rule_id` is the SHA-256 of the entry's canonical JSON. Editing an entry changes its id, so published ids stay verifiable and a changed rule is visibly a new rule.

The only shipped view is **disclosed vs undisclosed precision**, published per model as `precision_disclosure: {disclosed, undisclosed}`. There are no A/B/C grades.

## 4. Verification

The hash keeps its 16-hex-character convention. For methodology 2.1.0 and later it additionally covers the endpoint snapshot digest, the `rule_id` in force, and the canonical spread output with every `observed` block removed. For 2.0.0 dates the hash input is unchanged, so published hashes still verify. The indexer pipeline re-hashes `data/endpoints/{date}.jsonl` when present and refuses to run on a mismatch with the spread file; without the file (CI, a fresh clone) the recorded digest stands.

The daily output gains `rule_id` and `endpoint_snapshot_sha256` (additive). `schemas/stci_spread.schema.json` describes the spread file.

## 5. Publication

Facet cells, `precision_disclosure`, `rule_id` and `endpoint_snapshot_sha256` publish. `scripts/publish_static.py` allow-lists those keys and refuses to publish any document containing per-endpoint fields.
