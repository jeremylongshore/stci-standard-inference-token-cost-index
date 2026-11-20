# Changelog

All notable changes to STCI (Standardized Token Cost Index) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Nightly refresh on the VPS** (`ops/vps/`, runbook `000-docs/021`): a systemd
  timer on the `intentsolutions` host runs collector -> spread -> indexer at
  06:30 UTC from a job-owned clone of `main`, verifies the four indices, and
  commits only `data/indices/<date>.json` and `data/spread/<date>.json` to
  `main` (which deploys the site). Failures page Buzz `sys-automation` through
  the governed alert floor; successes are audit-only. Replaces the GitHub
  Actions cron disabled on 2026-03-06. Since 2026-11-20 failures page the
  private Discord channel `#sys-alerts` (Buzz is retired; intent-os #957);
  failure path re-proven the same day (#40).
- **Price by serving precision on the site** (#39): each spread row reads
  "fp8 from $x / fp4 from $y / precision undisclosed from $z" from the 2.1
  facet cells; under 700px the table becomes stacked cards (no horizontal
  scroll at 390px); the OpenRouter accuracy counterpoint; methodology section
  "What a grade is and is not".
- **Rulebook and governance page** (`/governance`, `000-docs/024`, #38):
  administrator and conflict-of-interest statement, blend convention, data
  retention, IOSCO self-assessment (principle names pending a readable
  FR07/13).
- **Competitor and prior-art brief** (`000-docs/023`, #38) with a 2026-11-20
  verification addendum.

### Deferred

- Grade audit (paired prompts through reference vs low-precision endpoints):
  designed, not funded; no grade is published.


## [0.7.0] - 2026-11-20

### Added

- **Methodology 2.1.0, facets not verdicts** (`000-docs/022`, Refs #32). The
  spread keeps per-endpoint provider, tag, quantization, context, max
  completion tokens, supported parameters and prices in a private canonical
  snapshot (`data/endpoints/{date}.jsonl`, git-ignored); its sha256 is the
  spread file's `endpoint_snapshot_sha256`. Per model, facet cells by reported
  precision (missing is its own `undisclosed` bucket), context bucket and tool
  support, with null statistics below n=3. Uptime, throughput and latency sit in
  an `observed` block that no hash covers. Dated snapshot ids are never pooled
  with undated ids.
- `rules/grade-rules.yaml`: append-only rules, `rule_id` = sha256 of canonical
  content. Only view: disclosed vs undisclosed precision. No grades.
- `schemas/stci_spread.schema.json`; `rule_id` and `endpoint_snapshot_sha256`
  added to `stci_daily.schema.json`.

### Changed

- Verification hash for 2.1.0 also covers the endpoint snapshot digest, the rule
  id and the canonical spread output. 2.0.0 hashes are unchanged
  (`data/fixtures/methodology-2.0.0.yaml` archives that rulebook).
- `publish_static.py` publishes facet cells and refuses per-endpoint rows.
- VERSION 0.7.0; methodology version 2.1.0.

### Changed

- **Methodology 2.0.0** (`000-docs/020`): listing eligibility is now a rule
  (alias, `:free`, `:batch`, router and unpriced listings are excluded with a
  recorded reason; batch rates attach to the base model), FRONTIER and
  EFFICIENT constituents are rebuilt on the November 2026 market with each
  entry cited to the provider's own description, STCI-OPEN is rule-based
  (published weights plus at least 10 priced provider endpoints), and every
  daily output reports `constituents_missing`. Methodology 1.0.0 is archived
  as `data/fixtures/methodology-1.0.0.yaml` and still governs 2026-01-02 to
  2026-03-06.
- Observations gain `cached_rate_input`, `open_weights` and
  `hugging_face_id`. New observation files are no longer committed (ADR 014,
  amended); indices and the spread are.
- The collection resumed on 2026-11-19 after the gap from 2026-03-07.

### Added

- **Neocloud spread** (`services/collector/spread.py`, `data/spread/{date}.json`):
  per open-weight model, the blended price across every provider endpoint
  selling it, with min/p25/median/p75/max, the max/min and p75/p25 ratios,
  the serving-precision mix and the cheapest endpoint. The verification hash
  binds the endpoint counts whenever a basket used them.

- Rebuilt the public `stci-dataops` skill around evidence provenance,
  legal-review boundaries, the actual collector contract, explicit approvals,
  schema validation, and deterministic tests.
- Corrected public repository links and documented the intentionally paused
  daily pipeline.
- Refreshed locked development dependencies to clear all reported npm audit
  findings without changing production dependencies.

### Fixed

- Repair repository verification under `set -e` so counters no longer terminate
  the script on its first document or warning.
- Make pull-request browser and Lighthouse checks deterministic by testing the
  checked-out static site instead of the intentionally offline production domain.

## [0.2.0] - 2026-01-04

### Added

- **Pricing Intelligence Center** (`/intelligence.html`) - comprehensive LLM pricing analysis tool:
  - Historical pricing timeline with 19 curated events from major providers
  - Price velocity chart powered by Chart.js with linear/log scale toggle
  - Multiplicative savings calculator (quick, advanced, and contract benchmark modes)
  - Live market snapshot from daily index API
  - Evidence-backed data with source links and confidence levels
  - Cost optimization features explainer (caching, batching, routing)
  - Methodology and verification documentation
  - Email subscription form with honeypot protection

- **Testing Infrastructure**:
  - Playwright smoke test suite with 19 tests covering all major features
  - GitHub Actions CI pipeline with three jobs:
    - Data validation (JSON Schema + business rules)
    - E2E tests (Playwright)
    - Lighthouse audits with score thresholds

- **Build-Time Validation**:
  - JSON Schema validation for pricing events data
  - Business rules validation (duplicate IDs, severity rubric, HTTPS sources)
  - JSON-LD generation for SEO structured data

- **Legal Pages**:
  - Privacy policy (`/privacy.html`)
  - Terms of service (`/terms.html`)

### Changed

- Improved accessibility score from 84 to 97:
  - Fixed color contrast on hero stat labels
  - Corrected heading hierarchy (h4 → h3)
  - Added form labels and ARIA attributes
  - Added main landmark element

- Enhanced landing page UI/UX with better spacing and tier explanations

### Fixed

- Firestore initialization for Firebase Functions
- Python venv creation for Firebase Functions deployment
- Landing page comparison spacing and data loading
- Production URL in deploy summary

### Security

- All source URLs require HTTPS for high-confidence events
- Honeypot field for bot protection on subscription form
- CSP-ready with vendored dependencies (no CDN)

## [0.1.0] - 2026-01-02

### Added

- **OpenRouter Collector Pipeline**: Fetches LLM pricing data from OpenRouter API with automatic rate normalization to USD/1M tokens
- **Indexer Pipeline**: Computes daily reference rates for STCI-ALL, STCI-FRONTIER, STCI-EFFICIENT, and STCI-OPEN indices
- **Read-only HTTP API**: Serves index data, observations, and methodology via REST endpoints
- **JSON Schema Validation**: Canonical schemas for observations (`observation.schema.json`) and daily indices (`stci_daily.schema.json`)
- **Docker Support**: Multi-stage Dockerfile for API server and pipeline execution
- **GCP Cloud Run Deployment**: GitHub Actions workflow with Workload Identity Federation
- **Daily Automation**: Cron-based pipeline execution with systemd timer support
- **Comprehensive Test Suite**: 48 unit tests covering collector, indexer, and API services
- **CLAUDE.md**: Claude Code guidance for development workflows

### Infrastructure

- GitHub Actions workflows for CI (tests), CD (deployment), and daily pipeline
- Docker Compose for local development
- Storage backends for local filesystem and Google Cloud Storage

### Documentation

- Product Requirements Document (PRD)
- Architecture Decision Records (ADRs) for index-first strategy, OpenRouter integration, data pipeline, and licensing
- Observation schema specification
- STCI methodology specification
- Recompute runbook for deterministic verification

---

*STCI — Making LLM pricing transparent, reproducible, and trustworthy.*

[0.2.0]: https://github.com/jeremylongshore/stci-standard-inference-token-cost-index/releases/tag/v0.2.0
[0.1.0]: https://github.com/jeremylongshore/stci-standard-inference-token-cost-index/releases/tag/v0.1.0
